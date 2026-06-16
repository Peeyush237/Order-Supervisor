"""Temporal activity definitions.

Activities are where all side effects live (LLM, DB, time, network). Workflow
code stays deterministic and calls these.

  - say_hello                : Phase 0 smoke test
  - persist_*                : Phase 1 persistence (thin wrappers over app.db.repo)
  - agent_step               : Phase 2 STUB (deterministic) -> Phase 3 LLM
  - execute_business_action  : Phase 2 real (writes an activity record)
  - generate_final_output    : Phase 2 STUB -> Phase 6 LLM

The agent_step / final_output stubs let the whole workflow run end-to-end now;
Phase 3/6 swap the LLM in behind the same activity signatures, so the workflow
code does not change.
"""
from typing import Any

from temporalio import activity

from app.constants import BUSINESS_ACTIONS
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


# --------------------------------------------------------------------------- #
# Agent + actions (Phase 2 stubs / real action recorder)
# --------------------------------------------------------------------------- #
@activity.defn
async def agent_step(payload: dict[str, Any]) -> dict[str, Any]:
    """STUB agent inference (Phase 2).

    Returns a deterministic AgentDecision-shaped dict so the workflow can be
    exercised end-to-end without an LLM. Phase 3 replaces the body with a real
    structured LLM call behind this same signature.
    """
    trigger = payload.get("trigger", "unknown")
    order_id = payload.get("order_id", "?")
    default_wake_hours = float(payload.get("default_wake_hours", 6.0))
    events = payload.get("pending_events", [])
    instructions = payload.get("pending_instructions", [])

    actions: list[dict[str, Any]] = []
    reasoning_bits = [f"[stub] trigger={trigger}"]

    if trigger == "start":
        actions.append(
            {
                "name": "create_internal_note",
                "args": {"note": f"Supervisor started watching order {order_id}."},
            }
        )
        reasoning_bits.append("Opened supervision; recorded a starting note.")

    for ev in events:
        etype = ev.get("type")
        reasoning_bits.append(f"saw event '{etype}'")
        if etype == "payment_failed":
            actions.append(
                {
                    "name": "message_payments_team",
                    "args": {"message": f"Payment failed for order {order_id}; please investigate."},
                }
            )
        elif etype == "shipment_delayed":
            actions.append(
                {
                    "name": "message_customer",
                    "args": {"message": "Your shipment is delayed; we're on it and will update you."},
                }
            )
        elif etype == "refund_requested":
            actions.append(
                {
                    "name": "message_fulfillment_team",
                    "args": {"message": f"Refund requested on order {order_id}; please review."},
                }
            )

    for ins in instructions:
        reasoning_bits.append(f"noted instruction: {ins}")

    return {
        "reasoning": "; ".join(reasoning_bits),
        "actions": actions,
        "memory_update": None,
        "important_event": (events[-1].get("type") if events else None),
        "next_wake_seconds": int(default_wake_hours * 3600),
        "wake_guidance": None,
        "recommend_completion": False,
    }


@activity.defn
async def execute_business_action(
    run_id: str, name: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Execute one of the 5 business actions by recording an activity entry.

    Nothing is sent externally — the action *is* the activity record.
    """
    if name not in BUSINESS_ACTIONS:
        result = {"action": name, "args": args, "status": "rejected_unknown_action"}
        await repo.add_activity(run_id, "action", result)
        return result

    result = {"action": name, "args": args, "status": "recorded"}
    await repo.add_activity(run_id, "action", result)
    return result


@activity.defn
async def generate_final_output(payload: dict[str, Any]) -> dict[str, Any]:
    """STUB end-of-run output (Phase 2).

    Produces a basic summary from counts. Phase 6 replaces with an LLM-authored
    summary / learnings / recommendations behind this same signature.
    """
    run_id = payload["run_id"]
    reason = payload.get("reason", "completed")
    activities = await repo.list_activities(run_id)
    action_entries = [a for a in activities if a["kind"] == "action"]
    event_entries = [a for a in activities if a["kind"] == "event"]

    final = {
        "summary": (
            f"Run ended ({reason}). Processed {len(event_entries)} event(s) and "
            f"took {len(action_entries)} business action(s)."
        ),
        "important_actions": [a["payload"] for a in action_entries],
        "key_learnings": ["[stub] learnings are generated by the LLM in Phase 6."],
        "recommendations": ["[stub] recommendations are generated by the LLM in Phase 6."],
        "reason": reason,
    }
    await repo.add_activity(run_id, "final_output", final)
    return final
