"""LLM client: OpenAI-compatible chat endpoint with JSON output.

Provider-agnostic on purpose — set H2M_API_BASE / H2M_API_KEY / H2M_MODEL.
Defaults to the plakcel relay (OpenAI-compatible) which fronts Qwen models.
"""
from __future__ import annotations

import json
import os
import urllib.request


def _load_dotenv():
    # Minimal .env loader (stdlib only): `cp .env.example .env` then just works.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


_load_dotenv()

BASE = os.environ.get("H2M_API_BASE", "https://ai-fast-proxy.kirillena68.workers.dev/v1")
TOKEN = os.environ.get("H2M_API_KEY", "")
MODEL = os.environ.get("H2M_MODEL", "qwen3.8-max-0902")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")


def chat(messages: list[dict], model: str | None = None, timeout: int = 120) -> str:
    """One chat completion; returns the assistant's text."""
    body = json.dumps({
        "model": model or MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 3000,
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": " ".join(["Bearer", TOKEN]),
            "User-Agent": UA,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply (models love fences)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    start = t.find("{")
    if start < 0:
        raise ValueError(f"no JSON object in model reply: {text[:200]!r}")
    depth, end = 0, -1
    in_str, esc = False, False
    for i, ch in enumerate(t[start:], start):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
        elif ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
    if end < 0:
        raise ValueError("unterminated JSON object in model reply")
    return json.loads(t[start:end])
