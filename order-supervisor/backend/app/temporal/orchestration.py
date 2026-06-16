"""Thin orchestration helpers used by the API to drive Temporal.

Keeps Temporal-specific calls (start / signal / query / terminate) out of the
route handlers.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.temporal.client import get_temporal_client
from app.temporal.types import SupervisorConfig, WorkflowInput
from app.temporal.workflows import OrderSupervisorWorkflow


def workflow_id_for(run_id: str) -> str:
    return f"order-supervisor-{run_id}"


async def start_supervisor(run_id: str, order_id: str, supervisor: dict, run: dict) -> str:
    """Start one OrderSupervisorWorkflow for a run. Returns the workflow id."""
    settings = get_settings()
    client = await get_temporal_client()

    wake_hours = float(
        (supervisor.get("default_wake_behavior") or {}).get("default_wake_hours", 6.0)
    )
    config = SupervisorConfig(
        base_instruction=supervisor["base_instruction"],
        available_actions=supervisor.get("available_actions") or [],
        wake_aggressiveness=run.get("wake_aggressiveness") or supervisor.get("wake_aggressiveness", "balanced"),
        default_wake_hours=run.get("default_wake_hours") or wake_hours,
        llm_config=supervisor.get("model_config") or {},
    )
    inp = WorkflowInput(
        run_id=run_id,
        order_id=order_id,
        supervisor=config,
        order_context=run.get("order_context") or {},
        time_scale=run.get("time_scale") if run.get("time_scale") is not None else settings.time_scale,
        max_age_hours=run.get("max_age_hours") if run.get("max_age_hours") is not None else 720.0,
    )

    wf_id = workflow_id_for(run_id)
    await client.start_workflow(
        OrderSupervisorWorkflow.run,
        inp,
        id=wf_id,
        task_queue=settings.temporal_task_queue,
    )
    return wf_id


async def _handle(run_id: str):
    client = await get_temporal_client()
    return client.get_workflow_handle(workflow_id_for(run_id))


async def send_event(run_id: str, event: dict) -> None:
    h = await _handle(run_id)
    await h.signal(OrderSupervisorWorkflow.submit_event, event)


async def send_instruction(run_id: str, text: str) -> None:
    h = await _handle(run_id)
    await h.signal(OrderSupervisorWorkflow.add_instruction, text)


async def set_paused(run_id: str, paused: bool) -> None:
    h = await _handle(run_id)
    await h.signal(OrderSupervisorWorkflow.set_paused, paused)


async def request_completion(run_id: str, reason: str) -> None:
    h = await _handle(run_id)
    await h.signal(OrderSupervisorWorkflow.request_completion, reason)


async def hard_terminate(run_id: str, reason: str) -> None:
    h = await _handle(run_id)
    await h.terminate(reason=reason)


async def query_state(run_id: str) -> dict[str, Any] | None:
    """Live in-memory state via Temporal query. Returns None if the workflow is
    not running (e.g. completed/terminated) so the caller can fall back to DB."""
    try:
        h = await _handle(run_id)
        return await h.query(OrderSupervisorWorkflow.get_state)
    except Exception:
        return None
