"""Phase 2 validation: run OrderSupervisorWorkflow in a time-skipping test
environment with the DB mocked in-memory. No Docker/Postgres/LLM needed.

Run:  .venv/Scripts/python.exe -m scripts.test_workflow
"""
import asyncio
import uuid
from datetime import timedelta

# --- in-memory fake for app.db.repo (patched before activities import it) ---
import app.db.repo as repo

_LOG: list[dict] = []
_RUNS: dict[str, dict] = {}
_MEM: dict[str, dict] = {}


async def _add_activity(run_id, kind, payload):
    entry = {"id": uuid.uuid4().hex, "run_id": run_id, "kind": kind, "payload": payload}
    _LOG.append(entry)
    return entry


async def _list_activities(run_id, kinds=None):
    return [a for a in _LOG if a["run_id"] == run_id and (not kinds or a["kind"] in kinds)]


async def _update_run(run_id, fields):
    _RUNS.setdefault(run_id, {}).update(fields)
    return _RUNS[run_id]


async def _update_memory(run_id, rolling_summary=None, important_events=None):
    m = _MEM.setdefault(run_id, {"rolling_summary": "", "important_events": []})
    if rolling_summary is not None:
        m["rolling_summary"] = rolling_summary
    if important_events is not None:
        m["important_events"] = important_events
    return m


repo.add_activity = _add_activity
repo.list_activities = _list_activities
repo.update_run = _update_run
repo.update_memory = _update_memory

from temporalio.client import WorkflowFailureError  # noqa: E402
from temporalio.testing import WorkflowEnvironment  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

from app.temporal.activities import (  # noqa: E402
    agent_step,
    execute_business_action,
    generate_final_output,
    persist_activity,
    persist_memory_update,
    persist_run_update,
    say_hello,
)
from app.temporal.types import SupervisorConfig, WorkflowInput  # noqa: E402
from app.temporal.workflows import HelloWorkflow, OrderSupervisorWorkflow  # noqa: E402


def kinds_count():
    out: dict[str, int] = {}
    for a in _LOG:
        out[a["kind"]] = out.get(a["kind"], 0) + 1
    return out


async def main():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[HelloWorkflow, OrderSupervisorWorkflow],
            activities=[
                say_hello, persist_activity, persist_run_update, persist_memory_update,
                agent_step, execute_business_action, generate_final_output,
            ],
        ):
            run_id = "run-test-1"
            inp = WorkflowInput(
                run_id=run_id,
                order_id="ORDER-123",
                supervisor=SupervisorConfig(
                    base_instruction="Supervise the order.",
                    available_actions=["create_internal_note", "message_payments_team",
                                       "message_customer", "message_fulfillment_team",
                                       "message_logistics_team"],
                    wake_aggressiveness="balanced",
                    default_wake_hours=6.0,
                ),
                order_context={"item": "Widget", "amount": 99.0},
                time_scale=1.0,       # 1 sim-hour == 1 real sec (but time-skipped anyway)
                max_age_hours=720.0,
            )

            handle = await env.client.start_workflow(
                OrderSupervisorWorkflow.run, inp, id=run_id, task_queue="test"
            )

            # let the start trigger run
            await asyncio.sleep(0.2)
            st = await handle.query(OrderSupervisorWorkflow.get_state)
            assert st["status"] == "active", st
            assert st["sleep_state"] == "sleeping", st
            print("after start:", st["status"], st["sleep_state"], "turn", st["turn"])

            # 1) low-priority event -> should be deferred, NOT wake the agent
            turn_before = st["turn"]
            await handle.signal(OrderSupervisorWorkflow.submit_event,
                                {"type": "payment_confirmed", "data": {}})
            await asyncio.sleep(0.2)
            st = await handle.query(OrderSupervisorWorkflow.get_state)
            assert st["turn"] == turn_before, ("low-pri should not advance turn", st)
            print("low-pri deferred ok; turn still", st["turn"])

            # 2) high-priority event -> should wake the agent and act
            await handle.signal(OrderSupervisorWorkflow.submit_event,
                                {"type": "payment_failed", "data": {}})
            await asyncio.sleep(0.2)
            st = await handle.query(OrderSupervisorWorkflow.get_state)
            assert st["turn"] > turn_before, ("high-pri should advance turn", st)
            print("high-pri woke agent; turn now", st["turn"])

            # 3) instruction -> interrupt, acts immediately
            t2 = st["turn"]
            await handle.signal(OrderSupervisorWorkflow.add_instruction,
                                "Prioritize speed; escalate delays immediately.")
            await asyncio.sleep(0.2)
            st = await handle.query(OrderSupervisorWorkflow.get_state)
            assert st["turn"] > t2, ("instruction should advance turn", st)
            print("instruction interrupt ok; turn now", st["turn"])

            # 4) pause / resume
            await handle.signal(OrderSupervisorWorkflow.set_paused, True)
            await asyncio.sleep(0.2)
            st = await handle.query(OrderSupervisorWorkflow.get_state)
            assert st["status"] == "paused" and st["paused"], st
            print("paused ok")
            await handle.signal(OrderSupervisorWorkflow.set_paused, False)
            await asyncio.sleep(0.2)
            st = await handle.query(OrderSupervisorWorkflow.get_state)
            assert st["status"] == "active", st
            print("resumed ok")

            # 5) scheduled wake via time skip (sleep deadline ~6 real sec)
            t3 = st["turn"]
            await env.sleep(timedelta(seconds=8))
            await asyncio.sleep(0.2)
            st = await handle.query(OrderSupervisorWorkflow.get_state)
            assert st["turn"] > t3, ("scheduled wake should advance turn", st)
            print("scheduled wake ok; turn now", st["turn"])

            # 6) terminal event -> workflow-owned completion
            await handle.signal(OrderSupervisorWorkflow.submit_event,
                                {"type": "delivered", "data": {}})
            result = await handle.result()
            print("FINAL OUTPUT:", result["summary"])
            assert result["reason"] == "terminal_event", result
            assert _RUNS[run_id]["status"] == "completed", _RUNS[run_id]

            print("\nactivity_log kinds:", kinds_count())
            print("ALL PHASE 2 CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
