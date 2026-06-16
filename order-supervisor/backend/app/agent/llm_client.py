"""Provider-pluggable LLM client.

One small surface (`complete_json`) wraps every provider so the rest of the
codebase never knows which LLM is in use. Selected via env:
  LLM_PROVIDER = groq | openai | anthropic | mock
  LLM_MODEL, LLM_API_KEY

`mock` needs no API key and returns deterministic JSON built from the structured
context — so the whole system runs end-to-end offline (and in tests).

Lives in the activity/worker process only (does network + env reads) — never
imported into deterministic workflow code paths.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import get_settings

_OPENAI_COMPAT_URLS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
}


async def complete_json(system: str, user: str, context: dict[str, Any]) -> str:
    """Return a raw JSON string from the configured provider.

    `context` is the structured agent payload; only the mock provider uses it.
    Real providers receive the rendered system/user prompts.
    """
    settings = get_settings()
    provider = (settings.llm_provider or "mock").lower()

    try:
        if provider == "mock" or not settings.llm_api_key:
            return _mock_decision_json(context)
        if provider in _OPENAI_COMPAT_URLS:
            return await _openai_compatible(provider, settings, system, user)
        if provider == "anthropic":
            return await _anthropic(settings, system, user)
        # unknown provider -> safe deterministic fallback
        return _mock_decision_json(context)
    except Exception:  # network/parse error -> never crash the agent
        return _mock_decision_json(context)


async def _openai_compatible(provider: str, settings, system: str, user: str) -> str:
    url = _OPENAI_COMPAT_URLS[provider]
    payload = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _anthropic(settings, system: str, user: str) -> str:
    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": settings.llm_model,
        "max_tokens": 1024,
        "temperature": 0.2,
        "system": system + "\nRespond with a single JSON object and nothing else.",
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": settings.llm_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]


# --------------------------------------------------------------------------- #
# Mock provider: deterministic policy so the product runs with no API key.
# --------------------------------------------------------------------------- #
def _mock_decision_json(context: dict[str, Any]) -> str:
    trigger = context.get("trigger", "unknown")
    order_id = context.get("order_id", "?")
    default_wake_hours = float(context.get("default_wake_hours", 6.0))
    events = context.get("pending_events", []) or []
    instructions = context.get("pending_instructions", []) or []

    actions: list[dict[str, Any]] = []
    bits = [f"trigger={trigger}"]

    if trigger == "start":
        actions.append({
            "name": "create_internal_note",
            "args": {"note": f"Supervisor opened on order {order_id}."},
        })
        bits.append("opened supervision")

    recommend_completion = False
    next_wake_hours = default_wake_hours
    important_event = None

    for ev in events:
        etype = ev.get("type")
        important_event = etype
        bits.append(f"event:{etype}")
        if etype == "payment_failed":
            actions.append({"name": "message_payments_team",
                            "args": {"message": f"Payment failed on {order_id}; please investigate."}})
            actions.append({"name": "message_customer",
                            "args": {"message": "We hit a payment issue and are looking into it."}})
            next_wake_hours = min(next_wake_hours, 2.0)
        elif etype == "shipment_delayed":
            actions.append({"name": "message_logistics_team",
                            "args": {"message": f"Shipment delayed on {order_id}; need an ETA."}})
            actions.append({"name": "message_customer",
                            "args": {"message": "Your shipment is delayed; we're chasing an updated ETA."}})
            next_wake_hours = min(next_wake_hours, 3.0)
        elif etype == "refund_requested":
            actions.append({"name": "message_fulfillment_team",
                            "args": {"message": f"Refund requested on {order_id}; please review."}})
            next_wake_hours = min(next_wake_hours, 3.0)
        elif etype == "customer_message_received":
            actions.append({"name": "message_customer",
                            "args": {"message": "Thanks for reaching out — a teammate is on it."}})
        elif etype == "delivered":
            actions.append({"name": "create_internal_note",
                            "args": {"note": f"Order {order_id} delivered; wrapping up."}})
            recommend_completion = True

    for ins in instructions:
        bits.append(f"instruction:{ins[:40]}")
        actions.append({"name": "create_internal_note",
                        "args": {"note": f"Acknowledged run instruction: {ins}"}})

    decision = {
        "reasoning": "[mock] " + "; ".join(bits),
        "actions": actions,
        "memory_update": None,
        "important_event": important_event,
        "next_wake_seconds": int(next_wake_hours * 3600),
        "wake_guidance": None,
        "recommend_completion": recommend_completion,
    }
    return json.dumps(decision)
