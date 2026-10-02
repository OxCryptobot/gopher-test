#!/usr/bin/env python3
"""CLI: python agent.py "goal" [--workspace DIR] [--allow read,write,exec]"""
import argparse
import os
import sys

from agent_loop import Agent
from agent_providers import provider_from_env
from agent_store import Store
from agent_tools import ToolRegistry, Workspace


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("goal")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--allow", default="read", help="comma list of: read,write,exec")
    ap.add_argument("--db", default=os.path.expanduser("~/.gopher_agent.db"))
    ap.add_argument("--max-steps", type=int, default=25)
    args = ap.parse_args()
    provider = provider_from_env(dict(os.environ))
    if provider is None:
        print("Set AGENT_LLM_URL, AGENT_LLM_KEY and AGENT_LLM_MODEL.", file=sys.stderr)
        return 2
    registry = ToolRegistry(allow=set(args.allow.split(",")))
    Workspace(args.workspace).register_all(registry)
    result = Agent(provider, registry, Store(args.db), max_steps=args.max_steps).run(args.goal)
    print(f"[{'ok' if result.ok else 'FAILED'}] {result.summary}\nrun={result.run_id} steps={result.steps} tokens={result.tokens}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
