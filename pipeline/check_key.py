"""Masked API-key check: loads .env, makes one tiny Haiku call, never prints the key.

Run from the project root:  python -m pipeline.check_key
"""
import json, os, urllib.error, urllib.request

from pipeline.common import ROOT

MODEL = "claude-haiku-5-5"


def load_env(path=ROOT / ".env"):
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env()
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    print("key present:", bool(key), "| length:", len(key))
    if not key:
        return 1
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({"model": MODEL, "max_tokens": 8,
                         "messages": [{"role": "user", "content": "Reply with: ok"}]}).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
        print("HTTP 200 | model:", body.get("model"), "| usage:", body.get("usage"))
        return 0
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:300].replace(key, "***"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
