"""Quick LLM connectivity check — runs ONE agent_step via the configured
provider (reads backend/.env) and prints the validated decision.

Run:  .venv/Scripts/python.exe -m scripts.check_llm
No Postgres/Temporal needed.
"""
import asyncio

from app.agent.llm_client import complete_json
from app.agent.prompts import build_agent_messages
from app.agent.schemas import parse_decision
from app.config import get_settings


async def main():
    s = get_settings()
    print(f"provider={s.llm_provider} model={s.llm_model} key_set={bool(s.llm_api_key)}")

    payload = {
        "trigger": "signal",
        "order_id": "ORDER-DEMO",
        "base_instruction": "Supervise the order; act on issues, otherwise sleep.",
        "available_actions": [
            "message_fulfillment_team", "message_payments_team",
            "message_logistics_team", "message_customer", "create_internal_note",
        ],
        "wake_aggressiveness": "balanced",
        "default_wake_hours": 6.0,
        "order_context": {"item": "Wireless Headphones", "amount": 199.0},
        "rolling_summary": "",
        "important_events": [],
        "pending_events": [{"type": "payment_failed", "data": {"reason": "card_declined"}}],
        "pending_instructions": [],
        "wake_guidance": None,
        "turn": 1,
    }
    system, user = build_agent_messages(payload)
    raw = await complete_json(system, user, payload)
    print("\n--- RAW ---\n", raw[:1500])
    decision = parse_decision(raw, default_wake_hours=6.0)
    print("\n--- VALIDATED DECISION ---")
    print("reasoning:", decision["reasoning"])
    print("actions:", [a["name"] for a in decision["actions"]])
    print("next_wake_seconds:", decision["next_wake_seconds"])
    print("recommend_completion:", decision["recommend_completion"])


if __name__ == "__main__":
    asyncio.run(main())
