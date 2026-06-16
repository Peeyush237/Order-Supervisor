"""Data-access functions.

Each function is self-contained (opens its own session), so it can be called
both from Temporal activities and from FastAPI routes without threading a
session through. Returns plain dicts (JSON-serializable) to keep activity
boundaries clean.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import ActivityLog, Run, RunMemory, Supervisor
from app.db.session import SessionLocal


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #
def _supervisor_dict(s: Supervisor) -> dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "base_instruction": s.base_instruction,
        "available_actions": s.available_actions,
        "default_wake_behavior": s.default_wake_behavior,
        "model_config": s.llm_config,
        "wake_aggressiveness": s.wake_aggressiveness,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _run_dict(r: Run) -> dict[str, Any]:
    return {
        "id": r.id,
        "supervisor_id": r.supervisor_id,
        "order_id": r.order_id,
        "workflow_id": r.workflow_id,
        "status": r.status,
        "order_context": r.order_context,
        "next_wake_at": r.next_wake_at.isoformat() if r.next_wake_at else None,
        "sleep_state": r.sleep_state,
        "final_output": r.final_output,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }


def _activity_dict(a: ActivityLog) -> dict[str, Any]:
    return {
        "id": a.id,
        "run_id": a.run_id,
        "ts": a.ts.isoformat() if a.ts else None,
        "kind": a.kind,
        "payload": a.payload,
    }


def _memory_dict(m: RunMemory | None) -> dict[str, Any]:
    if m is None:
        return {"rolling_summary": "", "important_events": [], "updated_at": None}
    return {
        "rolling_summary": m.rolling_summary,
        "important_events": m.important_events,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


# --------------------------------------------------------------------------- #
# Supervisors
# --------------------------------------------------------------------------- #
async def create_supervisor(data: dict[str, Any]) -> dict[str, Any]:
    async with SessionLocal() as s:
        sup = Supervisor(
            name=data["name"],
            base_instruction=data["base_instruction"],
            available_actions=data.get("available_actions", []),
            default_wake_behavior=data.get("default_wake_behavior", {}),
            llm_config=data.get("model_config", {}),
            wake_aggressiveness=data.get("wake_aggressiveness", "balanced"),
        )
        s.add(sup)
        await s.commit()
        await s.refresh(sup)
        return _supervisor_dict(sup)


async def list_supervisors() -> list[dict[str, Any]]:
    async with SessionLocal() as s:
        rows = (await s.execute(select(Supervisor).order_by(Supervisor.created_at))).scalars().all()
        return [_supervisor_dict(x) for x in rows]


async def get_supervisor(supervisor_id: str) -> dict[str, Any] | None:
    async with SessionLocal() as s:
        sup = await s.get(Supervisor, supervisor_id)
        return _supervisor_dict(sup) if sup else None


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #
async def create_run(data: dict[str, Any]) -> dict[str, Any]:
    async with SessionLocal() as s:
        run = Run(
            # Honor a caller-supplied id so the run's PK matches the value passed
            # to the workflow (workflow persists activities keyed by this id).
            **({"id": data["id"]} if data.get("id") else {}),
            supervisor_id=data["supervisor_id"],
            order_id=data["order_id"],
            workflow_id=data["workflow_id"],
            status=data.get("status", "active"),
            order_context=data.get("order_context", {}),
        )
        s.add(run)
        await s.flush()
        s.add(RunMemory(run_id=run.id, rolling_summary="", important_events=[]))
        await s.commit()
        await s.refresh(run)
        return _run_dict(run)


async def list_runs() -> list[dict[str, Any]]:
    async with SessionLocal() as s:
        rows = (
            await s.execute(select(Run).order_by(Run.created_at.desc()))
        ).scalars().all()
        return [_run_dict(x) for x in rows]


async def get_run(run_id: str) -> dict[str, Any] | None:
    async with SessionLocal() as s:
        run = await s.get(Run, run_id)
        return _run_dict(run) if run else None


async def get_run_by_workflow(workflow_id: str) -> dict[str, Any] | None:
    async with SessionLocal() as s:
        run = (
            await s.execute(select(Run).where(Run.workflow_id == workflow_id))
        ).scalar_one_or_none()
        return _run_dict(run) if run else None


async def update_run(run_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    """Patch a run. `next_wake_at`/`completed_at` accept ISO strings or datetimes."""
    async with SessionLocal() as s:
        run = await s.get(Run, run_id)
        if run is None:
            return None
        for key, value in fields.items():
            if key in ("next_wake_at", "completed_at") and isinstance(value, str):
                value = datetime.fromisoformat(value)
            setattr(run, key, value)
        await s.commit()
        await s.refresh(run)
        return _run_dict(run)


# --------------------------------------------------------------------------- #
# Memory
# --------------------------------------------------------------------------- #
async def get_memory(run_id: str) -> dict[str, Any]:
    async with SessionLocal() as s:
        mem = await s.get(RunMemory, run_id)
        return _memory_dict(mem)


async def update_memory(
    run_id: str,
    rolling_summary: str | None = None,
    important_events: list | None = None,
) -> dict[str, Any]:
    async with SessionLocal() as s:
        mem = await s.get(RunMemory, run_id)
        if mem is None:
            mem = RunMemory(run_id=run_id, rolling_summary="", important_events=[])
            s.add(mem)
        if rolling_summary is not None:
            mem.rolling_summary = rolling_summary
        if important_events is not None:
            mem.important_events = important_events
        await s.commit()
        await s.refresh(mem)
        return _memory_dict(mem)


# --------------------------------------------------------------------------- #
# Activity log
# --------------------------------------------------------------------------- #
async def add_activity(run_id: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with SessionLocal() as s:
        entry = ActivityLog(run_id=run_id, kind=kind, payload=payload)
        s.add(entry)
        await s.commit()
        await s.refresh(entry)
        return _activity_dict(entry)


async def list_activities(
    run_id: str, kinds: list[str] | None = None
) -> list[dict[str, Any]]:
    async with SessionLocal() as s:
        q = select(ActivityLog).where(ActivityLog.run_id == run_id)
        if kinds:
            q = q.where(ActivityLog.kind.in_(kinds))
        q = q.order_by(ActivityLog.ts.asc())
        rows = (await s.execute(q)).scalars().all()
        return [_activity_dict(x) for x in rows]


async def get_run_detail(run_id: str) -> dict[str, Any] | None:
    """Full run view for the UI: run + memory + activities in one shot."""
    async with SessionLocal() as s:
        run = (
            await s.execute(
                select(Run)
                .where(Run.id == run_id)
                .options(selectinload(Run.memory), selectinload(Run.activities))
            )
        ).scalar_one_or_none()
        if run is None:
            return None
        activities = sorted(run.activities, key=lambda a: (a.ts or datetime.min))
        return {
            "run": _run_dict(run),
            "memory": _memory_dict(run.memory),
            "activities": [_activity_dict(a) for a in activities],
        }
