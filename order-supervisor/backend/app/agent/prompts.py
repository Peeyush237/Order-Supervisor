"""Prompt construction for the agent, memory compaction, and final output.

Kept here (not inline in activities) so prompts are easy to read and tune.
"""
from __future__ import annotations

import json
from typing import Any

from app.constants import BUSINESS_ACTIONS, EVENT_TYPES

_DECISION_SCHEMA = """Return ONLY a JSON object with exactly these keys:
{
  "reasoning": string,                       // brief why behind your decision
  "actions": [{"name": string, "args": object}],  // 0+ business actions to take now
  "memory_update": string | null,            // new rolling summary, or null to keep current
  "important_event": string | null,          // short note to pin to the timeline, or null
  "next_wake_seconds": integer | null,       // simulated seconds until next scheduled wake (null = use default)
  "wake_guidance": {"wake_on": [string], "note": string} | null,  // event types that should wake you early
  "recommend_completion": boolean            // true if you believe the order is done (workflow decides)
}"""


def build_agent_messages(payload: dict[str, Any]) -> tuple[str, str]:
    actions = payload.get("available_actions") or BUSINESS_ACTIONS
    aggr = payload.get("wake_aggressiveness", "balanced")

    system = f"""You are an AI Order Supervisor overseeing a single e-commerce order \
from creation to completion. You run intermittently — only on three triggers: \
the order's start, an important incoming event, or a scheduled wake-up. Between \
runs you sleep. Be deliberate: take high-value actions only, and otherwise sleep.

Your base instruction:
{payload.get('base_instruction', '')}

You may take ONLY these business actions (each just records an internal activity; \
nothing is sent externally): {', '.join(actions)}.

Wake aggressiveness for this run: {aggr}. Set next_wake_seconds shorter when the \
situation is active or risky, longer when things are calm.

You do NOT control completion — you may set recommend_completion, but the workflow \
ends the run on its own rules. Known event types: {', '.join(EVENT_TYPES)}.

{_DECISION_SCHEMA}"""

    context = {
        "trigger": payload.get("trigger"),
        "order_id": payload.get("order_id"),
        "order_context": payload.get("order_context", {}),
        "rolling_summary": payload.get("rolling_summary", ""),
        "important_events": payload.get("important_events", []),
        "new_events": payload.get("pending_events", []),
        "new_instructions": payload.get("pending_instructions", []),
        "current_wake_guidance": payload.get("wake_guidance"),
        "turn": payload.get("turn", 0),
    }
    user = (
        "Decide what to do now given the current situation. Respond with the JSON "
        "object only.\n\nSITUATION:\n" + json.dumps(context, indent=2, default=str)
    )
    return system, user


def build_compaction_messages(rolling_summary: str, events: list[str]) -> tuple[str, str]:
    system = (
        "You compact an order supervisor's memory. Merge the older timeline events "
        "into the existing rolling summary, preserving anything that affects future "
        "decisions (issues, customer sentiment, commitments made, deadlines). Be "
        "concise. Return ONLY a JSON object: {\"rolling_summary\": string}."
    )
    user = json.dumps(
        {"current_rolling_summary": rolling_summary, "older_events": events},
        indent=2,
        default=str,
    )
    return system, user


def build_final_output_messages(payload: dict[str, Any]) -> tuple[str, str]:
    system = (
        "You are closing out an order-supervision run. Produce a clear end-of-run "
        "report. Return ONLY a JSON object with keys: "
        '{"summary": string, "important_actions": [string], '
        '"key_learnings": [string], "recommendations": [string]}.'
    )
    user = (
        "Write the end-of-run report from this run data. JSON only.\n\n"
        + json.dumps(payload, indent=2, default=str)
    )
    return system, user
