"""Request/response models for the HTTP API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# --- Supervisors ---
class SupervisorCreate(BaseModel):
    name: str
    base_instruction: str
    available_actions: list[str] | None = None
    default_wake_behavior: dict[str, Any] = Field(default_factory=dict)
    model_config_: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    wake_aggressiveness: str = "balanced"

    model_config = {"populate_by_name": True}


# --- Runs ---
class RunCreate(BaseModel):
    supervisor_id: str
    order_id: str
    order_context: dict[str, Any] = Field(default_factory=dict)
    # optional per-run overrides
    time_scale: float | None = None
    max_age_hours: float | None = None
    default_wake_hours: float | None = None
    wake_aggressiveness: str | None = None


class EventIn(BaseModel):
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class InstructionIn(BaseModel):
    text: str


class TerminateIn(BaseModel):
    reason: str = "manual_termination"
    hard: bool = False  # hard=True => client.terminate fallback


class InterruptIn(BaseModel):
    note: str | None = None
