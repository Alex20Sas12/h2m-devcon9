"""FastAPI app: the one screen the editor uses.

POST /api/draft     headline (+optional snippet) -> saved verdict
GET  /api/drafts    review queue
GET  /api/drafts/{id}
POST /api/drafts/{id}/edit      editor changes fields (recorded, auditable)
POST /api/drafts/{id}/approve   nothing goes live until this happens
POST /api/drafts/{id}/discard
GET  /              the review UI (web/index.html)
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import store
from pipeline import draft_market

app = FastAPI(title="Headline to Market")


class DraftIn(BaseModel):
    headline: str
    snippet: str = ""
    model: str | None = None


class EditIn(BaseModel):
    fields: dict


@app.post("/api/draft")
def api_draft(body: DraftIn):
    if not body.headline.strip():
        raise HTTPException(400, "headline is empty")
    try:
        result = draft_market(body.headline, body.snippet, model=body.model)
    except Exception as e:  # LLM outage etc. — say so, don't hang the editor
        return JSONResponse({"error": f"LLM call failed: {e}"}, status_code=502)
    did = store.save(body.headline, body.snippet, result.verdict.kind,
                     result.verdict.model_dump(mode="json"), result.model)
    return {"id": did, **result.model_dump(mode="json")}


@app.get("/api/drafts")
def api_list():
    return store.list_drafts()


@app.get("/api/drafts/{did}")
def api_get(did: str):
    row = store.get(did)
    if not row:
        raise HTTPException(404, "no such draft")
    return row


@app.post("/api/drafts/{did}/edit")
def api_edit(did: str, body: EditIn):
    if not store.edit(did, body.fields):
        raise HTTPException(409, "draft missing or not pending")
    return store.get(did)


@app.post("/api/drafts/{did}/approve")
def api_approve(did: str):
    if not store.decide(did, "approved"):
        raise HTTPException(409, "draft missing or already decided")
    return store.get(did)


@app.post("/api/drafts/{did}/discard")
def api_discard(did: str):
    if not store.decide(did, "discarded"):
        raise HTTPException(409, "draft missing or already decided")
    return store.get(did)


@app.get("/")
@app.get("/api/index")
def index():
    # Vercel rewrites non-API paths to /api/index (2026 rewrite routing),
    # so serve the UI under both. local: repo-root/web; serverless: bundled.
    for cand in (Path(__file__).parent.parent / "web" / "index.html",
                 Path(__file__).parent / "web" / "index.html",
                 Path("/var/task/web/index.html")):
        if cand.exists():
            return FileResponse(cand)
    raise HTTPException(404, "web UI not bundled; use /docs for the API")
