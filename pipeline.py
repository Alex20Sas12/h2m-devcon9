"""Core pipeline: headline -> validated MarketResult (draft or rejection).

Two validation layers with ONE repair turn between them:
  1. Pydantic parse (shape)
  2. rules.semantic_check (meaning)
If either fails, the exact problems go back to the model once ("here is what
is wrong with your draft, fix it"). If the repaired draft still fails, it is
demoted to a rejection citing the failed checks — a broken draft never
reaches an editor.
"""
from __future__ import annotations

import json

from llm import chat, extract_json
from prompt import build_messages
from rules import semantic_check
from schema import MarketDraft, MarketResult, Rejection

REPAIR_PROMPT = """\
Your draft failed validation. Problems found:
{problems}

Fix ONLY these problems and return the complete corrected JSON object
(same shape, kind="draft"). If the problems show the headline genuinely
cannot yield a settleable market, return kind="reject" instead with honest
reasons and a rewrite_hint. JSON only."""

# Explicit, finite retry caps (no open-ended loops):
MAX_REPAIR_TURNS = 1   # validation-failure repair attempts given to the model
MAX_JSON_RETRIES = 1   # "reply was not valid JSON" re-asks

TIMEOUT_S = 120        # per model call, passed to the HTTP client


def _parse(raw: dict, model: str) -> MarketResult:
    if raw.get("kind") == "reject":
        return MarketResult(
            verdict=Rejection(reasons=raw["reasons"], rewrite_hint=raw["rewrite_hint"]),
            model=model,
        )
    return MarketResult(verdict=MarketDraft(**raw), model=model)


def draft_market(headline: str, snippet: str = "", model: str | None = None) -> MarketResult:
    msgs = build_messages(headline, snippet)
    used_model = model or "default"

    # --- get one parseable reply, capped re-asks ---
    result = None
    for attempt in range(MAX_JSON_RETRIES + 1):
        raw_text = chat(msgs, model=model, timeout=TIMEOUT_S)
        try:
            result = _parse(extract_json(raw_text), used_model)
            break
        except (ValueError, KeyError, TypeError) as e:
            msgs.append({"role": "assistant", "content": raw_text[:1500]})
            msgs.append({"role": "user",
                         "content": f"That reply was not valid JSON ({e}). Return ONLY the JSON object."})
    if result is None:
        # Cap reached: defined user-visible fallback instead of an uncaught 500.
        return MarketResult(
            verdict=Rejection(
                reasons=["the model never returned parseable JSON (retries capped at "
                         f"{MAX_JSON_RETRIES}) — draft manually or retry later"],
                rewrite_hint="Nothing wrong with the headline; the drafter failed. Use 'draft manually' in the review desk.",
            ),
            model=used_model,
        )

    if result.verdict.kind == "reject":
        return result
    assert isinstance(result.verdict, MarketDraft)

    # --- semantic validation with a capped repair loop ---
    problems: list[str] = []
    for turn in range(MAX_REPAIR_TURNS + 1):
        problems = semantic_check(result.verdict)
        if not problems:
            return result
        if turn == MAX_REPAIR_TURNS:
            break
        msgs.append({"role": "assistant",
                     "content": json.dumps(result.verdict.model_dump(mode="json"), ensure_ascii=False)})
        msgs.append({"role": "user",
                     "content": REPAIR_PROMPT.format(problems="\n".join(f"- {p}" for p in problems))})
        try:
            repaired = _parse(extract_json(chat(msgs, model=model, timeout=TIMEOUT_S)), used_model)
        except (ValueError, KeyError, TypeError):
            break
        if repaired.verdict.kind == "reject":
            return repaired
        assert isinstance(repaired.verdict, MarketDraft)
        result = repaired

    # Still broken after the capped repair -> honest, user-visible fallback rejection.
    return MarketResult(
        verdict=Rejection(
            reasons=[f"validation failed, draft could not be made settleable: {p}" for p in problems],
            rewrite_hint="Rewrite the headline to name a metric, a threshold and a reporting body.",
        ),
        model=used_model,
    )


if __name__ == "__main__":
    # Smoke check without network: repair/demotion logic with a stubbed chat().
    import llm
    calls = {"n": 0}

    def fake_chat(messages, model=None, timeout=120):
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({
                "kind": "draft",
                "question": "Will Bengaluru traffic improve?",
                "close_date": "2099-01-01T00:00:00+00:00",
                "resolution_source_name": "official sources",
                "resolution_source_url": "https://example.com",
                "resolution_rule": "r", "yes_criteria": "y", "no_criteria": "y",
                "edge_cases": ["standard rules apply", "none"], "rationale": "x",
            })
        return json.dumps({"kind": "reject", "reasons": ["unmeasurable outcome"],
                           "rewrite_hint": "name a metric"})

    llm.chat = fake_chat
    globals()["chat"] = fake_chat  # draft_market reads the module global — rebind it here
    res = draft_market("Will Bengaluru traffic improve?")
    assert res.verdict.kind == "reject", res
    assert calls["n"] == 2  # exactly one repair turn
    print("pipeline.py self-check: PASS (bad draft -> 1 repair -> honest rejection)")
