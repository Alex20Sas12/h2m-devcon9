"""Pydantic schema for a settleable prediction-market draft.

The schema carries a discriminated union: a headline either yields a
DRAFT (with question, deadline, resolution source, YES/NO rules, edge
cases) or a REJECTION with editor-actionable reasons. Shape is enforced
here; *meaning* is enforced by semantic checks in rules.py — a valid
close_date can still be in the past, and "official sources" still passes
JSON validation. Both layers must agree before an editor sees a draft.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Union

from pydantic import BaseModel, Field, field_validator


class MarketDraft(BaseModel):
    """A market an editor could plausibly settle."""

    kind: Literal["draft"] = "draft"
    question: str = Field(
        description="Binary, measurable question ending in '?'. "
        "Must name the metric, the threshold and the measuring body."
    )
    close_date: datetime = Field(
        description="ISO-8601 UTC instant when the market closes. Must be in the future."
    )
    resolution_source_name: str = Field(
        description="The ONE named body that decides the outcome, e.g. 'US Bureau of Labor Statistics'."
    )
    resolution_source_url: str = Field(
        description="Stable URL where the resolution source publishes the deciding number/fact."
    )
    resolution_rule: str = Field(
        description="Exactly which release/figure decides YES vs NO, and where it is read."
    )
    yes_criteria: str = Field(description="Precise condition under which the market resolves YES.")
    no_criteria: str = Field(description="Precise condition under which the market resolves NO.")
    edge_cases: list[str] = Field(
        description="Awkward-case rules: data revision, delayed release, source URL dies, "
        "threshold exactly hit, event partially happens."
    )
    rationale: str = Field(
        description="Why THIS question/source/deadline was chosen, in editor-readable terms. "
        "Shown in the review UI so approval is never a rubber stamp."
    )

    @field_validator("question", "close_date", "resolution_source_name",
                     "resolution_source_url", "resolution_rule",
                     "yes_criteria", "no_criteria", "rationale")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("field must not be blank")
        return v.strip() if isinstance(v, str) else v

    @field_validator("edge_cases")
    @classmethod
    def _needs_edge_rules(cls, v: list[str]) -> list[str]:
        if len([e for e in v if e.strip()]) < 2:
            raise ValueError("at least two edge-case rules are required")
        return v


class Rejection(BaseModel):
    """An honest 'this headline cannot become a fair market' — with reasons
    that help the editor rewrite the headline, not a shrug."""

    kind: Literal["reject"] = "reject"
    reasons: list[str] = Field(min_length=1)
    rewrite_hint: str = Field(
        description="Concrete suggestion: what the headline would need to become "
        "for a market to be resolvable."
    )


class MarketResult(BaseModel):
    verdict: Union[MarketDraft, Rejection]
    model: str = "unknown"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
