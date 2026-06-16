"""Temporal activity definitions.

Activities are where all side effects live (LLM, DB, time, network).
Phase 0: a single trivial activity.
"""
from temporalio import activity


@activity.defn
async def say_hello(name: str) -> str:
    activity.logger.info("say_hello activity running for %s", name)
    return f"Hello, {name}! The Order Supervisor scaffold is alive."
