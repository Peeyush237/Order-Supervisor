"""Temporal workflow definitions.

Phase 0: a trivial HelloWorkflow to prove the FastAPI -> Temporal -> Worker
loop works and is visible in the Temporal UI.

IMPORTANT (carried through all later phases): workflow code must be
deterministic. No LLM calls, DB calls, datetime.now(), random, network, or env
reads here. Use workflow.now() for time, workflow.logger for logs, and push all
side effects into activities.
"""
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import say_hello


@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        workflow.logger.info("HelloWorkflow started for %s", name)
        greeting = await workflow.execute_activity(
            say_hello,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )
        return greeting
