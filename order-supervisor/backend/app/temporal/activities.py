"""Temporal activity definitions.

Activities are where all side effects live (LLM, DB, time, network). Workflow
code stays deterministic and calls these.

  - say_hello           : Phase 0 smoke test
  - persist_*           : Phase 1 persistence (thin wrappers over app.db.repo)

Agent / classifier / business-action / memory activities arrive in Phase 3.
"""
from typing import Any

from temporalio import activity

from app.db import repo


@activity.defn
async def say_hello(name: str) -> str:
    activity.logger.info("say_hello activity running for %s", name)
    return f"Hello, {name}! The Order Supervisor scaffold is alive."


# --------------------------------------------------------------------------- #
# Persistence activities (Phase 1)
# --------------------------------------------------------------------------- #
@activity.defn
async def persist_activity(run_id: str, kind: str, payload: dict[str, Any]) -> dict:
    """Append one entry to the run's activity log."""
    return await repo.add_activity(run_id, kind, payload)


@activity.defn
async def persist_run_update(run_id: str, fields: dict[str, Any]) -> dict | None:
    """Patch run fields (status, sleep_state, next_wake_at, final_output, ...)."""
    return await repo.update_run(run_id, fields)


@activity.defn
async def persist_memory_update(
    run_id: str,
    rolling_summary: str | None = None,
    important_events: list | None = None,
) -> dict:
    """Update the run's rolling summary and/or important-events list."""
    return await repo.update_memory(run_id, rolling_summary, important_events)
