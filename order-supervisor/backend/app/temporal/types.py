"""Dataclasses passed across the workflow boundary.

Kept dependency-free (no pydantic, no side effects) so they are safe to import
inside deterministic workflow code via workflow.unsafe.imports_passed_through().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SupervisorConfig:
    base_instruction: str
    available_actions: list[str] = field(default_factory=list)
    wake_aggressiveness: str = "balanced"  # conservative | balanced | aggressive
    default_wake_hours: float = 6.0
    llm_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowInput:
    run_id: str
    order_id: str
    supervisor: SupervisorConfig
    order_context: dict[str, Any] = field(default_factory=dict)
    # Demo time scaling: real_sleep_seconds = sim_seconds * time_scale / 3600.
    # time_scale = "real seconds per simulated hour". 1.0 => 1 sim-hour == 1 real sec.
    time_scale: float = 1.0
    # Workflow-owned max age (in simulated hours) after which the run completes.
    max_age_hours: float = 720.0
    # Populated only by continue_as_new to resume state across history resets.
    carryover: dict[str, Any] | None = None


@dataclass
class AgentDecision:
    """Shape returned by the agent_step activity (validated there)."""

    reasoning: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)
    memory_update: str | None = None
    important_event: str | None = None
    next_wake_seconds: int | None = None  # simulated seconds; None => default
    wake_guidance: dict[str, Any] | None = None  # {"wake_on": [...], "note": str}
    recommend_completion: bool = False
