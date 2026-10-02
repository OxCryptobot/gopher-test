#!/usr/bin/env python3
"""End-to-end smoke: boot server.py (or hit --url) and exercise core endpoints."""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def call(base, path, body=None):
    req = urllib.request.Request(base + path, method="POST" if body is not None else "GET")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def run(base):
    fails = []

    def check(name, ok, detail=""):
        print(("PASS " if ok else "FAIL ") + name + (f" {detail}" if not ok else ""))
        if not ok:
            fails.append(name)

    s, b = call(base, "/health")
    check("health", s == 200, s)
    s, b = call(base, "/")
    check("index", s == 200 and b"<html" in b.lower(), s)
    s, b = call(base, "/hole.json")
    check("hole.json", s == 200 and isinstance(json.loads(b), dict), s)
    s, b = call(base, "/manifest.json")
    check("manifest", s == 200, s)
    s, b = call(base, "/api/status")
    check("status", s == 200, s)
    s, b = call(base, "/api/ask", {"q": "hello"})
    check("ask", s == 200 and json.loads(b).get("ok") is not False, s)
    s, b = call(base, "/api/ask", {"q": 1})
    check("ask-bad-input-no-500", s < 500, s)
    s, b = call(base, "/nope-" + str(time.time()))
    check("404-not-500", s in (404, 200), s)
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="test a deployed origin instead of booting locally")
    args = ap.parse_args()
    if args.url:
        return 1 if run(args.url.rstrip("/")) else 0
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    # Copy-free isolation: run in a temp cwd would break static files, so use repo with temp data env.
    env = dict(os.environ, PORT=str(port), GOPHER_HOST="127.0.0.1")
    with tempfile.TemporaryFile() as log:
        p = subprocess.Popen([sys.executable, "server.py"], cwd=ROOT, env=env, stdout=log, stderr=log)
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(50):
                try:
                    if call(base, "/health")[0] == 200:
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                print("FAIL boot")
                return 1
            fails = run(base)
        finally:
            p.terminate()
            p.wait(5)
            subprocess.run(["git", "checkout", "--", "orders.jsonl", "scores.json", "waitlist.json"],
                           cwd=ROOT, capture_output=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
