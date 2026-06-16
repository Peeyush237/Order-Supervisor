"""Shared helper for connecting to the Temporal server."""
from temporalio.client import Client

from app.config import get_settings


async def get_temporal_client() -> Client:
    settings = get_settings()
    return await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )
