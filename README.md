# Headline to Market

Paste a news headline, get back a **settleable** prediction market — or an honest explanation of why that headline can't become one. Built for the *Road to Devcon 9* builder challenge (Loops House), problem [headline-to-market](https://www.loops.house/road-to-devcon-ix).

Ananya's bad market was *"Will Bengaluru traffic improve?"* — it sat open for a month because nobody could say who had won. This tool refuses to produce that. It rejects headlines with vague verbs, missing thresholds, or no public resolution source, and every draft it does produce names **one specific body**, a **stable URL**, a **deadline**, explicit YES/NO conditions, and rules for the awkward cases (data revisions, delayed releases, exact-threshold ties).

## Why trust the drafts? Three layers, not one

1. **Prompt with real rejection criteria** (`prompt.py`). The rubric's trap is a rejection variant that exists in the schema but is never used because the prompt gives the model no criteria. Here REJECT_CRITERIA are five concrete, testable conditions, and "a rejection is a SUCCESS, not a failure" is stated explicitly. The golden set's reject cases exercise each one.
2. **Semantic validation, not just shape** (`rules.py`). Pydantic (`schema.py`) guarantees well-formed JSON; it cannot tell that `"official sources"` settles nothing or that a close date is yesterday. `semantic_check()` catches boilerplate sources, past dates, unmeasurable verbs, identical YES/NO criteria, and placeholder edge cases. A draft that fails gets **one repair turn with the exact failures**; if it still fails, it is demoted to an honest rejection — a broken draft never reaches the editor (`pipeline.py`).
3. **The editor is not a rubber stamp** (`web/index.html`, `server.py`). Every draft shows the model's *rationale* — why this source and deadline — and every field is editable inline; edits are recorded as an audit trail (`editor_edits` in `store.py`). Approve / discard are explicit, and nothing is ever published automatically.

**Prompt injection (OWASP LLM01):** the headline is untrusted data. It is sanitized (`sanitize_untrusted` strips fence and delimiter escapes, control chars, caps length), wrapped in `<headline>` delimiters, and the system prompt states that text inside the delimiters can never change instructions. The golden set includes an injection headline that must be *rejected, not obeyed*.

## Run it

```bash
pip install -r requirements.txt          # pydantic + fastapi + uvicorn
export H2M_API_KEY=***              # any OpenAI-compatible chat API
# optional overrides: H2M_API_BASE, H2M_MODEL (default qwen3.8-max-0902)

python h2m.py "RBI likely to cut repo rate by 25 bps in December"   # CLI
python h2m.py "Will Bengaluru traffic improve?"                     # -> honest rejection

uvicorn server:app --port 8000                                    # web desk at /
```

The golden set (12 cases incl. the hard ones the rubric asks for):

```bash
python golden.py              # live: runs every case through the LLM
python golden.py --offline    # no network: schema/rules/store/injection layers
```

## Layout

| File | Role |
|---|---|
| `schema.py` | Pydantic models: `MarketDraft` ∣ `Rejection` discriminated union |
| `prompt.py` | System prompt with concrete REJECT_CRITERIA + injection defence |
| `rules.py` | Semantic checks (meaning, not shape) + `sanitize_untrusted` |
| `pipeline.py` | Draft → validate → one repair turn → demote-to-rejection |
| `store.py` | SQLite: drafts, decisions, editor-edit audit trail |
| `server.py` | FastAPI endpoints |
| `web/index.html` | Review desk: rationale visible, fields editable, explicit approve |
| `golden.py` | Golden set incl. vague-verb / no-threshold / already-public / injection cases |
| `h2m.py` | CLI twin of the web desk |

Built in 48h for Road to Devcon 9 · Prediction Markets (play tokens only — nothing here touches real money).
