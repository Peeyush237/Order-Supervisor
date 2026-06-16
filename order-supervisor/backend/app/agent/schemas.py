"""Strict decision schema + tolerant parser.

The LLM is asked for a JSON object; we validate it with pydantic and normalize
to a plain dict. On any malformed output we return a safe fallback decision
(no actions, default wake) so the workflow always gets a usable result.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.constants import BUSINESS_ACTIONS


class ActionCall(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class WakeGuidance(BaseModel):
    wake_on: list[str] = Field(default_factory=list)
    note: str = ""


class AgentDecisionModel(BaseModel):
    reasoning: str = ""
    actions: list[ActionCall] = Field(default_factory=list)
    memory_update: str | None = None
    important_event: str | None = None
    next_wake_seconds: int | None = None
    wake_guidance: WakeGuidance | None = None
    recommend_completion: bool = False


def _fallback(reason: str, default_wake_hours: float) -> dict[str, Any]:
    return {
        "reasoning": f"[fallback] {reason}",
        "actions": [],
        "memory_update": None,
        "important_event": None,
        "next_wake_seconds": int(default_wake_hours * 3600),
        "wake_guidance": None,
        "recommend_completion": False,
    }


def parse_decision(raw: str, default_wake_hours: float = 6.0) -> dict[str, Any]:
    """Parse + validate raw LLM JSON into a normalized decision dict."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        # Some models wrap JSON in prose/fences; try to recover the object.
        data = _extract_json(raw)
        if data is None:
            return _fallback("could not parse JSON", default_wake_hours)

    try:
        model = AgentDecisionModel.model_validate(data)
    except ValidationError as e:
        return _fallback(f"schema validation failed: {e.error_count()} error(s)", default_wake_hours)

    # Drop actions that aren't one of the 5 allowed business actions.
    valid_actions = [
        {"name": a.name, "args": a.args}
        for a in model.actions
        if a.name in BUSINESS_ACTIONS
    ]

    return {
        "reasoning": model.reasoning,
        "actions": valid_actions,
        "memory_update": model.memory_update,
        "important_event": model.important_event,
        "next_wake_seconds": model.next_wake_seconds,
        "wake_guidance": (
            {"wake_on": model.wake_guidance.wake_on, "note": model.wake_guidance.note}
            if model.wake_guidance
            else None
        ),
        "recommend_completion": model.recommend_completion,
    }


def _extract_json(raw: str) -> dict | None:
    if not isinstance(raw, str):
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
