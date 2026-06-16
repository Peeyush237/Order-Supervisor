"""FastAPI application entrypoint.

Phase 0: health check + a /hello endpoint that starts the HelloWorkflow in
Temporal and waits for the result, proving the FastAPI -> Temporal -> Worker
round trip.
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import get_settings
from app.db.init_db import init_db
from app.temporal.client import get_temporal_client
from app.temporal.workflows import HelloWorkflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Order Supervisor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


class HelloResponse(BaseModel):
    workflow_id: str
    result: str


@app.post("/hello", response_model=HelloResponse)
async def hello(name: str = "world") -> HelloResponse:
    """Start a HelloWorkflow and return its result (Phase 0 smoke test)."""
    settings = get_settings()
    client = await get_temporal_client()
    workflow_id = f"hello-{uuid.uuid4().hex[:8]}"
    handle = await client.start_workflow(
        HelloWorkflow.run,
        name,
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    result = await handle.result()
    return HelloResponse(workflow_id=workflow_id, result=result)
