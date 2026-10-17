"""SQLite persistence for drafts and editor decisions (stdlib sqlite3)."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("H2M_DB", Path(__file__).parent / "desk.sqlite3"))

_DDL = """
CREATE TABLE IF NOT EXISTS drafts (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  headline TEXT NOT NULL,
  snippet TEXT DEFAULT '',
  kind TEXT NOT NULL,               -- draft | reject
  verdict_json TEXT NOT NULL,       -- the MarketDraft/Rejection payload
  model TEXT DEFAULT '',
  status TEXT DEFAULT 'pending',    -- pending | approved | discarded
  editor_edits TEXT DEFAULT '',     -- JSON of fields the editor changed (audit trail)
  decided_at TEXT
);
"""


def connect() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript(_DDL)
    return c


def save(headline: str, snippet: str, kind: str, verdict_json: dict, model: str) -> str:
    did = uuid.uuid4().hex[:12]
    with connect() as c:
        c.execute(
            "INSERT INTO drafts (id, created_at, headline, snippet, kind, verdict_json, model) VALUES (?,?,?,?,?,?,?)",
            (did, datetime.now(timezone.utc).isoformat(), headline, snippet, kind,
             json.dumps(verdict_json, ensure_ascii=False), model),
        )
    return did


def list_drafts(limit: int = 50) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM drafts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["verdict"] = json.loads(d.pop("verdict_json"))
        d["editor_edits"] = json.loads(d["editor_edits"]) if d["editor_edits"] else {}
        out.append(d)
    return out


def get(did: str) -> dict | None:
    with connect() as c:
        r = c.execute("SELECT * FROM drafts WHERE id=?", (did,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["verdict"] = json.loads(d.pop("verdict_json"))
    d["editor_edits"] = json.loads(d["editor_edits"]) if d["editor_edits"] else {}
    return d


def decide(did: str, status: str) -> bool:
    assert status in ("approved", "discarded")
    with connect() as c:
        cur = c.execute(
            "UPDATE drafts SET status=?, decided_at=? WHERE id=? AND status='pending'",
            (status, datetime.now(timezone.utc).isoformat(), did),
        )
    return cur.rowcount == 1


def edit(did: str, fields: dict) -> bool:
    """Editor edits a pending draft; changes are recorded, not silently applied."""
    row = get(did)
    if not row or row["status"] != "pending":
        return False
    verdict = row["verdict"]
    known = {"question", "close_date", "resolution_source_name", "resolution_source_url",
             "resolution_rule", "yes_criteria", "no_criteria", "edge_cases", "rationale"}
    edits = row.get("editor_edits") or {}
    for k, v in fields.items():
        if k in known and k in verdict:
            edits[k] = {"was": verdict[k], "now": v}
            verdict[k] = v
    with connect() as c:
        c.execute("UPDATE drafts SET verdict_json=?, editor_edits=? WHERE id=?",
                  (json.dumps(verdict, ensure_ascii=False), json.dumps(edits, ensure_ascii=False), did))
    return True
