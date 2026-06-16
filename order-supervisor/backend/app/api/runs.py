"""Run endpoints: start, list, detail, plus events / instructions / controls.

Reads come from Postgres (the UI's source of truth); live in-memory state is
layered on via a Temporal query when the workflow is still running.
"""
import uuid

from fastapi import APIRouter, HTTPException

from app.api.schemas import EventIn, InstructionIn, InterruptIn, RunCreate, TerminateIn
from app.db import repo
from app.temporal import orchestration as orch

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("")
async def create_run(body: RunCreate) -> dict:
    supervisor = await repo.get_supervisor(body.supervisor_id)
    if supervisor is None:
        raise HTTPException(status_code=404, detail="supervisor not found")

    run_id = uuid.uuid4().hex
    wf_id = orch.workflow_id_for(run_id)
    run = await repo.create_run(
        {
            "id": run_id,
            "supervisor_id": body.supervisor_id,
            "order_id": body.order_id,
            "workflow_id": wf_id,
            "order_context": body.order_context,
        }
    )

    # Carry optional per-run overrides into the workflow input.
    run_overrides = {
        **run,
        "time_scale": body.time_scale,
        "max_age_hours": body.max_age_hours,
        "default_wake_hours": body.default_wake_hours,
        "wake_aggressiveness": body.wake_aggressiveness,
    }
    await orch.start_supervisor(run_id, body.order_id, supervisor, run_overrides)
    return run


@router.get("")
async def list_runs() -> list[dict]:
    return await repo.list_runs()


@router.get("/{run_id}")
async def get_run(run_id: str) -> dict:
    detail = await repo.get_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="run not found")
    # Layer live in-memory state on top (None if workflow no longer running).
    detail["live_state"] = await orch.query_state(run_id)
    return detail


@router.post("/{run_id}/events")
async def inject_event(run_id: str, body: EventIn) -> dict:
    await _require_run(run_id)
    await orch.send_event(run_id, {"type": body.type, "data": body.data})
    return {"ok": True, "delivered": body.type}


@router.post("/{run_id}/instructions")
async def add_instruction(run_id: str, body: InstructionIn) -> dict:
    await _require_run(run_id)
    await orch.send_instruction(run_id, body.text)
    return {"ok": True}


@router.post("/{run_id}/interrupt")
async def interrupt(run_id: str, body: InterruptIn) -> dict:
    """Force an immediate agent step by injecting a high-priority instruction."""
    await _require_run(run_id)
    note = body.note or "Interrupt: review the order now and decide whether to act."
    await orch.send_instruction(run_id, f"[interrupt] {note}")
    return {"ok": True}


@router.post("/{run_id}/pause")
async def pause(run_id: str) -> dict:
    await _require_run(run_id)
    await orch.set_paused(run_id, True)
    return {"ok": True}


@router.post("/{run_id}/resume")
async def resume(run_id: str) -> dict:
    await _require_run(run_id)
    await orch.set_paused(run_id, False)
    return {"ok": True}


@router.post("/{run_id}/terminate")
async def terminate(run_id: str, body: TerminateIn) -> dict:
    await _require_run(run_id)
    if body.hard:
        await orch.hard_terminate(run_id, body.reason)
        # hard terminate skips the graceful final output; reflect status in DB
        await repo.update_run(run_id, {"status": "terminated"})
    else:
        await orch.request_completion(run_id, body.reason)
    return {"ok": True, "mode": "hard" if body.hard else "graceful"}


async def _require_run(run_id: str) -> dict:
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run
