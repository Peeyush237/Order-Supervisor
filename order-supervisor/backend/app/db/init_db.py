"""Create tables (if missing) and seed default supervisor templates.

Idempotent: safe to call on every backend startup. For a POC we use
create_all instead of Alembic migrations.
"""
import asyncio

from sqlalchemy import select

from app.constants import BUSINESS_ACTIONS
from app.db.models import Base, Supervisor
from app.db.session import SessionLocal, engine

SEED_TEMPLATES = [
    {
        "name": "Standard Order Supervisor",
        "base_instruction": (
            "You supervise a single e-commerce order from creation to delivery. "
            "Watch the order lifecycle, intervene only when something needs "
            "attention, and otherwise sleep to conserve effort. Keep the customer "
            "informed on material changes, coordinate with internal teams when "
            "issues arise, and record concise internal notes. Prefer fewer, "
            "higher-value actions over chatter."
        ),
        "available_actions": BUSINESS_ACTIONS,
        "default_wake_behavior": {"default_wake_hours": 6},
        "model_config": {},
        "wake_aggressiveness": "balanced",
    },
    {
        "name": "High-Touch VIP Supervisor",
        "base_instruction": (
            "You supervise a high-value VIP order. Be proactive and protective of "
            "the customer experience. Reach out to the customer promptly on any "
            "delay or problem, escalate to the relevant internal team immediately, "
            "and check in frequently. Speed and communication matter more than cost."
        ),
        "available_actions": BUSINESS_ACTIONS,
        "default_wake_behavior": {"default_wake_hours": 2},
        "model_config": {},
        "wake_aggressiveness": "aggressive",
    },
]


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as s:
        existing = (await s.execute(select(Supervisor.id))).first()
        if existing is None:
            for tpl in SEED_TEMPLATES:
                s.add(
                    Supervisor(
                        name=tpl["name"],
                        base_instruction=tpl["base_instruction"],
                        available_actions=tpl["available_actions"],
                        default_wake_behavior=tpl["default_wake_behavior"],
                        llm_config=tpl["model_config"],
                        wake_aggressiveness=tpl["wake_aggressiveness"],
                    )
                )
            await s.commit()


if __name__ == "__main__":
    asyncio.run(init_db())
    print("DB initialized and seeded.")
