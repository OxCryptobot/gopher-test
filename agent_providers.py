"""Provider abstraction: tool-calling chat models with retry, fallback and usage accounting."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol
from urllib.parse import urlparse


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class Reply:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


class ProviderError(Exception):
    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class Provider(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply: ...


class OpenAICompatProvider:
    """Any /chat/completions endpoint that supports tool calling."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise ValueError("base_url must be an http(s) URL")
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.key, self.model, self.timeout = api_key, model, timeout

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
        body = {"model": self.model, "messages": messages}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        req = urllib.request.Request(
            self.url,
            json.dumps(body).encode(),
            {"Content-Type": "application/json", "Authorization": f"Bearer {self.key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"http {exc.code}", retryable=exc.code in (408, 429) or exc.code >= 500) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(str(exc)) from exc
        try:
            msg = data["choices"][0]["message"]
            calls = []
            for c in msg.get("tool_calls") or []:
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {"__invalid_json__": c["function"].get("arguments", "")}
                calls.append(ToolCall(c["id"], c["function"]["name"], args if isinstance(args, dict) else {}))
            usage = data.get("usage") or {}
            return Reply(msg.get("content") or "", calls, {k: int(v) for k, v in usage.items() if isinstance(v, int)})
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"malformed response: {exc}", retryable=False) from exc


class FallbackProvider:
    """Try providers in order; retry retryable errors with exponential backoff."""

    def __init__(self, providers: list[Provider], retries: int = 2, backoff: float = 0.5,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.providers, self.retries, self.backoff, self._sleep = providers, retries, backoff, sleep

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
        last: Exception | None = None
        for provider in self.providers:
            for attempt in range(self.retries + 1):
                try:
                    return provider.complete(messages, tools)
                except ProviderError as exc:
                    last = exc
                    if not exc.retryable:
                        break
                    if attempt < self.retries:
                        self._sleep(self.backoff * 2**attempt)
        raise ProviderError(f"all providers failed: {last}", retryable=False)


class ScriptedProvider:
    """Deterministic provider for tests and offline evals."""

    def __init__(self, replies: list[Reply]) -> None:
        self._replies = list(replies)
        self.calls = 0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
        self.calls += 1
        if not self._replies:
            return Reply(text="done")
        return self._replies.pop(0)


def provider_from_env(env: dict[str, str]) -> Provider | None:
    url, key, model = env.get("AGENT_LLM_URL"), env.get("AGENT_LLM_KEY"), env.get("AGENT_LLM_MODEL")
    if not (url and key and model):
        return None
    primary: list[Provider] = [OpenAICompatProvider(url, key, model)]
    fb_model = env.get("AGENT_LLM_FALLBACK_MODEL")
    if fb_model:
        primary.append(OpenAICompatProvider(url, key, fb_model))
    return FallbackProvider(primary)
