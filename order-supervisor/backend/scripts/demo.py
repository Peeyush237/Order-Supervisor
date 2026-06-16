"""Seeded demo / event generator.

Drives the live HTTP API end-to-end: picks a seeded supervisor, starts a run,
then injects a realistic event sequence with pauses so you can watch the agent
wake, act, and sleep. Doubles as the script-based event generator.

Prereqs: docker compose up, the worker, and uvicorn all running.
Run:  .venv/Scripts/python.exe -m scripts.demo
"""
import asyncio
import os

import httpx

API = os.environ.get("API_BASE", "http://localhost:8000")
PAUSE = float(os.environ.get("DEMO_PAUSE", "4"))  # seconds between steps


async def main():
    async with httpx.AsyncClient(base_url=API, timeout=30) as c:
        sups = (await c.get("/api/supervisors")).json()
        if not sups:
            print("No supervisors seeded — start the backend first."); return
        sup = sups[0]
        print(f"Using supervisor: {sup['name']} ({sup['id']})")

        run = (await c.post("/api/runs", json={
            "supervisor_id": sup["id"],
            "order_id": "ORDER-DEMO-1",
            "order_context": {"item": "Wireless Headphones", "amount": 199.0, "tier": "standard"},
            "default_wake_hours": 6,
        })).json()
        run_id = run["id"]
        print(f"Started run {run_id} (workflow {run['workflow_id']})")
        await show(c, run_id)

        # A believable order lifecycle with a payment hiccup and a shipment delay.
        sequence = [
            ("payment_failed", {"reason": "card_declined"}),
            ("payment_confirmed", {}),
            ("shipment_created", {"carrier": "UPS"}),
            ("shipment_delayed", {"eta_days": 3}),
            ("customer_message_received", {"text": "Where is my order?"}),
        ]
        for etype, data in sequence:
            await asyncio.sleep(PAUSE)
            print(f"\n>>> inject {etype}")
            await c.post(f"/api/runs/{run_id}/events", json={"type": etype, "data": data})
            await asyncio.sleep(1.5)
            await show(c, run_id)

        # Add a run-specific instruction mid-flight.
        await asyncio.sleep(PAUSE)
        print("\n>>> add instruction")
        await c.post(f"/api/runs/{run_id}/instructions",
                     json={"text": "Prioritize speed; escalate any further delay immediately."})
        await asyncio.sleep(1.5)
        await show(c, run_id)

        # Terminal event -> workflow-owned completion + final output.
        await asyncio.sleep(PAUSE)
        print("\n>>> inject delivered (terminal)")
        await c.post(f"/api/runs/{run_id}/events", json={"type": "delivered", "data": {}})
        await asyncio.sleep(3)
        detail = (await c.get(f"/api/runs/{run_id}")).json()
        print(f"\nfinal status: {detail['run']['status']}")
        fo = detail["run"].get("final_output")
        if fo:
            print("SUMMARY:", fo.get("summary"))
            print("LEARNINGS:", fo.get("key_learnings"))
            print("RECOMMENDATIONS:", fo.get("recommendations"))


async def show(c, run_id):
    d = (await c.get(f"/api/runs/{run_id}")).json()
    live = d.get("live_state") or {}
    r = d["run"]
    print(f"  status={r['status']} sleep={live.get('sleep_state', r['sleep_state'])} "
          f"turn={live.get('turn')} activities={len(d['activities'])} "
          f"recommend_completion={live.get('recommend_completion')}")


if __name__ == "__main__":
    asyncio.run(main())
