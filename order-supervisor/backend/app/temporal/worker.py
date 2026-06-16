"""Temporal worker entrypoint.

Run with:  python -m app.temporal.worker
Registers the workflows and activities on the shared task queue.
"""
import asyncio
import logging

from temporalio.worker import Worker

from app.config import get_settings
from app.temporal.activities import (
    agent_step,
    execute_business_action,
    generate_final_output,
    persist_activity,
    persist_memory_update,
    persist_run_update,
    say_hello,
)
from app.temporal.client import get_temporal_client
from app.temporal.workflows import HelloWorkflow, OrderSupervisorWorkflow

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    settings = get_settings()
    client = await get_temporal_client()

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[HelloWorkflow, OrderSupervisorWorkflow],
        activities=[
            say_hello,
            persist_activity,
            persist_run_update,
            persist_memory_update,
            agent_step,
            execute_business_action,
            generate_final_output,
        ],
    )
    logging.info("Worker started on task queue '%s'", settings.temporal_task_queue)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
