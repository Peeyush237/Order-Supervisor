"""Supervisor (template) endpoints."""
from fastapi import APIRouter, HTTPException

from app.api.schemas import SupervisorCreate
from app.constants import BUSINESS_ACTIONS
from app.db import repo

router = APIRouter(prefix="/api/supervisors", tags=["supervisors"])


@router.post("")
async def create_supervisor(body: SupervisorCreate) -> dict:
    data = {
        "name": body.name,
        "base_instruction": body.base_instruction,
        "available_actions": body.available_actions or BUSINESS_ACTIONS,
        "default_wake_behavior": body.default_wake_behavior,
        "model_config": body.model_config_,
        "wake_aggressiveness": body.wake_aggressiveness,
    }
    return await repo.create_supervisor(data)


@router.get("")
async def list_supervisors() -> list[dict]:
    return await repo.list_supervisors()


@router.get("/{supervisor_id}")
async def get_supervisor(supervisor_id: str) -> dict:
    sup = await repo.get_supervisor(supervisor_id)
    if sup is None:
        raise HTTPException(status_code=404, detail="supervisor not found")
    return sup
