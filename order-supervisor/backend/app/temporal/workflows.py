"""Temporal workflow definitions.

HelloWorkflow      — Phase 0 smoke test (kept for /hello).
OrderSupervisorWorkflow — the long-running, one-per-order supervisor.

DETERMINISM RULES (apply to all workflow code in this file):
  no LLM/DB/network calls, no datetime.now()/random/env reads. Use
  workflow.now() for time, workflow.logger for logs, and push every side effect
  into an activity. Pure helpers may import app.constants / app.temporal.types
  (no side effects) via imports_passed_through below.
"""
import asyncio
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.constants import (
        EVENT_TYPES,
        HIGH_PRIORITY_EVENTS,
        TERMINAL_EVENTS,
    )
    from app.temporal.activities import (
        agent_step,
        compact_memory,
        execute_business_action,
        generate_final_output,
        persist_activity,
        persist_memory_update,
        persist_run_update,
        say_hello,
    )
    from app.temporal.types import WorkflowInput

# Tunables
CONTINUE_AS_NEW_THRESHOLD = 4000  # history events before we reset history
MAX_IMPORTANT_EVENTS = 50         # hard in-memory cap
COMPACT_THRESHOLD = 12            # compact when important_events exceeds this
COMPACT_KEEP_RECENT = 6           # entries kept verbatim after compaction
MIN_REAL_SLEEP_SECONDS = 1.0

_ACT_RETRY = RetryPolicy(maximum_attempts=5)
_DEFAULT_TO = timedelta(seconds=60)


@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        workflow.logger.info("HelloWorkflow started for %s", name)
        return await workflow.execute_activity(
            say_hello, name, start_to_close_timeout=timedelta(seconds=10)
        )


@workflow.defn
class OrderSupervisorWorkflow:
    """One run per order. The workflow owns control flow and completion; the LLM
    (via agent_step) only proposes actions and a next wake-up."""

    def __init__(self) -> None:
        # --- queues filled by signals, drained by the loop ---
        self._pending_events: list[dict] = []
        self._pending_instructions: list[str] = []
        # --- control flags ---
        self._paused: bool = False
        self._terminate_requested: bool = False
        self._terminate_reason: str = ""
        # delivery / post-delivery return window
        self._delivered: bool = False
        self._post_delivery_deadline: datetime | None = None
        # decided in the loop, consumed by _finalize
        self._end_reason: str = ""
        self._end_status: str = ""
        # --- live state (exposed via query) ---
        self._status: str = "active"
        self._sleep_state: str = "awake"
        self._next_wake_at: str | None = None  # ISO wall-clock deadline
        self._rolling_summary: str = ""
        self._important_events: list[str] = []
        self._wake_on: list[str] = []          # agent-provided wake guidance
        self._wake_note: str = ""
        self._recommend_completion: bool = False
        self._turn: int = 0
        # set in run()
        self._inp: WorkflowInput | None = None
        self._started_at: datetime | None = None
        self._wake_deadline: datetime | None = None  # workflow-time deadline

    # ------------------------------------------------------------------ #
    # Signals
    # ------------------------------------------------------------------ #
    @workflow.signal
    def submit_event(self, event: dict) -> None:
        self._pending_events.append(event)

    @workflow.signal
    def add_instruction(self, text: str) -> None:
        self._pending_instructions.append(text)

    @workflow.signal
    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    @workflow.signal
    def request_completion(self, reason: str) -> None:
        self._terminate_requested = True
        self._terminate_reason = reason or "manual_termination"

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #
    @workflow.query
    def get_state(self) -> dict:
        return {
            "run_id": self._inp.run_id if self._inp else None,
            "order_id": self._inp.order_id if self._inp else None,
            "status": self._status,
            "sleep_state": self._sleep_state,
            "next_wake_at": self._next_wake_at,
            "rolling_summary": self._rolling_summary,
            "important_events": list(self._important_events),
            "pending_events": len(self._pending_events),
            "pending_instructions": len(self._pending_instructions),
            "paused": self._paused,
            "turn": self._turn,
            "recommend_completion": self._recommend_completion,
            "wake_guidance": {"wake_on": self._wake_on, "note": self._wake_note},
            "delivered": self._delivered,
            "return_window_until": (
                self._post_delivery_deadline.isoformat()
                if self._post_delivery_deadline
                else None
            ),
        }

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #
    @workflow.run
    async def run(self, inp: WorkflowInput) -> dict:
        self._inp = inp
        resuming = inp.carryover is not None
        self._init_from_carryover(inp.carryover)

        if not resuming:
            self._started_at = workflow.now()
            await self._persist("lifecycle", {"event": "started", "order_id": inp.order_id})
            await self._set_status("active")
            await self._run_agent("start")

        # --- main supervise loop ---
        while True:
            decision = self._completion_decision()
            if decision:
                self._end_reason, self._end_status = decision
                break

            if self._paused:
                await self._set_status("paused")
                await workflow.wait_condition(
                    lambda: (not self._paused) or self._terminate_requested
                )
                if self._terminate_requested:
                    continue
                await self._set_status("active")
                continue

            timed_out = await self._sleep_until_wake()

            if self._terminate_requested or self._paused:
                continue
            # If a completion condition just became true (e.g. window/age elapsed),
            # let the loop top handle it rather than running a pointless agent step.
            if self._completion_decision():
                continue
            if timed_out:
                await self._run_agent("scheduled_wake")
            else:
                await self._handle_pending()

            if workflow.info().get_current_history_length() >= CONTINUE_AS_NEW_THRESHOLD:
                workflow.logger.info("History large; continuing as new")
                workflow.continue_as_new(self._carryover_input())

        await self._finalize()
        return self._inp_final_output

    # ------------------------------------------------------------------ #
    # Sleep / wake
    # ------------------------------------------------------------------ #
    async def _sleep_until_wake(self) -> bool:
        """Wait for pending work or the scheduled deadline. Returns True if it
        woke from the timeout (the scheduled wake-up), False if from a signal."""
        self._sleep_state = "sleeping"
        timeout = self._remaining_timeout()
        try:
            await workflow.wait_condition(
                lambda: bool(self._pending_events)
                or bool(self._pending_instructions)
                or self._terminate_requested
                or self._paused,
                timeout=timeout,
            )
            self._sleep_state = "awake"
            return False
        except asyncio.TimeoutError:
            self._sleep_state = "awake"
            return True

    def _remaining_timeout(self) -> timedelta | None:
        deadline = self._effective_deadline()
        if deadline is None:
            return None  # sleep until a signal arrives
        remaining = (deadline - workflow.now()).total_seconds()
        return timedelta(seconds=max(0.0, remaining))

    def _effective_deadline(self) -> datetime | None:
        """Soonest moment the loop must wake: the agent's next wake-up, plus the
        governing lifecycle deadline (return window if delivered, else max age)."""
        candidates: list[datetime] = []
        if self._wake_deadline is not None:
            candidates.append(self._wake_deadline)
        if self._delivered and self._post_delivery_deadline is not None:
            candidates.append(self._post_delivery_deadline)
        elif not self._delivered and self._started_at is not None:
            candidates.append(
                self._started_at
                + timedelta(seconds=self._inp.max_age_hours * self._inp.time_scale)
            )
        return min(candidates) if candidates else None

    def _set_next_wake(self, sim_seconds: int | None) -> None:
        if sim_seconds is None:
            sim_seconds = int(self._inp.supervisor.default_wake_hours * 3600)
        real = max(MIN_REAL_SLEEP_SECONDS, sim_seconds * self._inp.time_scale / 3600.0)
        self._wake_deadline = workflow.now() + timedelta(seconds=real)
        self._next_wake_at = self._wake_deadline.isoformat()

    # ------------------------------------------------------------------ #
    # Pending events / instructions
    # ------------------------------------------------------------------ #
    async def _handle_pending(self) -> None:
        instructions = self._pending_instructions
        self._pending_instructions = []
        events = self._pending_events
        self._pending_events = []

        wake_now = False

        for text in instructions:
            await self._persist("instruction", {"text": text})
            # A run-specific instruction is an interrupt: act immediately.
            wake_now = True

        important: list[dict] = []
        for ev in events:
            etype = ev.get("type", "unknown")
            high, reason = self._classify(etype)
            await self._persist(
                "event", {"type": etype, "data": ev.get("data", {}), "priority": "high" if high else "low"}
            )
            if etype == "delivered" and not self._delivered:
                self._open_return_window()
            if high:
                wake_now = True
                important.append(ev)
            else:
                await self._persist(
                    "sleep_decision",
                    {"event": etype, "reason": reason, "decision": "defer_to_scheduled_wake"},
                )

        if wake_now:
            await self._persist(
                "wake_decision",
                {"reason": "important_event_or_instruction", "events": [e.get("type") for e in important]},
            )
            await self._run_agent(
                "signal", events=important or events, instructions=instructions
            )
        # else: low-priority only -> we already deferred; loop re-sleeps for the
        # remaining time until the existing scheduled wake deadline.

    def _classify(self, event_type: str) -> tuple[bool, str]:
        """Lightweight wake/sleep policy (deterministic, separate from the agent)."""
        if event_type in TERMINAL_EVENTS:
            return True, "terminal_event"
        if event_type not in EVENT_TYPES:
            return True, "unknown_event_escalation"
        if event_type in self._wake_on:
            return True, "agent_wake_guidance"

        aggr = self._inp.supervisor.wake_aggressiveness
        if aggr == "aggressive":
            return True, "aggressive_policy"
        if aggr == "conservative":
            high = event_type in {"payment_failed", "refund_requested"}
            return high, "conservative_policy"
        # balanced (default)
        return event_type in HIGH_PRIORITY_EVENTS, "balanced_policy"

    # ------------------------------------------------------------------ #
    # Agent step
    # ------------------------------------------------------------------ #
    async def _run_agent(self, trigger: str, events=None, instructions=None) -> None:
        payload = {
            "trigger": trigger,
            "run_id": self._inp.run_id,
            "order_id": self._inp.order_id,
            "base_instruction": self._inp.supervisor.base_instruction,
            "available_actions": self._inp.supervisor.available_actions,
            "wake_aggressiveness": self._inp.supervisor.wake_aggressiveness,
            "default_wake_hours": self._inp.supervisor.default_wake_hours,
            "order_context": self._inp.order_context,
            "rolling_summary": self._rolling_summary,
            "important_events": list(self._important_events),
            "pending_events": events or [],
            "pending_instructions": instructions or [],
            "wake_guidance": {"wake_on": self._wake_on, "note": self._wake_note},
            "turn": self._turn,
        }
        decision = await workflow.execute_activity(
            agent_step,
            payload,
            start_to_close_timeout=_DEFAULT_TO,
            retry_policy=_ACT_RETRY,
        )

        await self._persist(
            "agent_reasoning",
            {
                "trigger": trigger,
                "reasoning": decision.get("reasoning", ""),
                "recommend_completion": bool(decision.get("recommend_completion")),
            },
        )

        for action in decision.get("actions", []):
            await self._action(action.get("name", ""), action.get("args", {}))

        mem_update = decision.get("memory_update")
        imp = decision.get("important_event")
        if imp:
            self._important_events.append(str(imp))
            self._important_events = self._important_events[-MAX_IMPORTANT_EVENTS:]
        if mem_update is not None:
            self._rolling_summary = str(mem_update)
        if mem_update is not None or imp:
            await workflow.execute_activity(
                persist_memory_update,
                args=[self._inp.run_id, self._rolling_summary, list(self._important_events)],
                start_to_close_timeout=_DEFAULT_TO,
                retry_policy=_ACT_RETRY,
            )

        await self._maybe_compact()

        guidance = decision.get("wake_guidance")
        if guidance:
            self._wake_on = list(guidance.get("wake_on", []))
            self._wake_note = str(guidance.get("note", ""))
            await self._persist("lifecycle", {"event": "wake_guidance_updated", **guidance})

        self._recommend_completion = bool(decision.get("recommend_completion"))

        self._set_next_wake(decision.get("next_wake_seconds"))
        await self._persist(
            "sleep_decision",
            {"next_wake_at": self._next_wake_at, "decision": "sleep"},
        )
        await self._persist_run_fields(
            {"next_wake_at": self._next_wake_at, "sleep_state": "sleeping"}
        )
        self._turn += 1

    async def _maybe_compact(self) -> None:
        """Context compaction: fold older important events into the rolling
        summary once the list grows past the threshold."""
        if len(self._important_events) <= COMPACT_THRESHOLD:
            return
        older = self._important_events[:-COMPACT_KEEP_RECENT]
        recent = self._important_events[-COMPACT_KEEP_RECENT:]
        result = await workflow.execute_activity(
            compact_memory,
            args=[self._inp.run_id, self._rolling_summary, older],
            start_to_close_timeout=_DEFAULT_TO,
            retry_policy=_ACT_RETRY,
        )
        self._rolling_summary = result.get("rolling_summary", self._rolling_summary)
        self._important_events = recent
        await workflow.execute_activity(
            persist_memory_update,
            args=[self._inp.run_id, self._rolling_summary, list(self._important_events)],
            start_to_close_timeout=_DEFAULT_TO,
            retry_policy=_ACT_RETRY,
        )

    # ------------------------------------------------------------------ #
    # Completion (workflow-owned)
    # ------------------------------------------------------------------ #
    def _open_return_window(self) -> None:
        """`delivered` arrived: keep the run alive to handle returns/refunds."""
        self._delivered = True
        secs = self._inp.return_window_hours * self._inp.time_scale
        self._post_delivery_deadline = workflow.now() + timedelta(seconds=secs)

    def _is_past_max_age(self) -> bool:
        if self._started_at is None:
            return False
        max_real = self._inp.max_age_hours * self._inp.time_scale
        return (workflow.now() - self._started_at).total_seconds() >= max_real

    def _completion_decision(self) -> tuple[str, str] | None:
        """Return (reason, status) if the run should end now, else None.
        Delivered and undelivered runs are governed by separate rules so they
        never clash."""
        if self._terminate_requested:
            return (self._terminate_reason or "manual_termination", "terminated")
        if self._delivered:
            # Governed ONLY by the return/refund window (max-age can't kill it).
            if (
                self._post_delivery_deadline is not None
                and workflow.now() >= self._post_delivery_deadline
            ):
                return ("return_window_closed", "completed")
            return None
        # Undelivered: governed ONLY by max age -> escalate + auto-refund.
        if self._is_past_max_age():
            return ("expired_undelivered", "expired")
        return None

    async def _escalate_and_refund_undelivered(self) -> None:
        """Final handling when a run expires without delivery: hand off to a human
        and auto-initiate a refund, recorded in activities + memory."""
        oid = self._inp.order_id
        hours = self._inp.max_age_hours
        span = f"~{int(hours / 24)} days" if hours >= 24 else f"~{int(hours)} hours"
        await self._action(
            "message_fulfillment_team",
            {"message": f"Order {oid} stalled {span} with no delivery — needs human review."},
        )
        await self._action(
            "create_internal_note",
            {"note": f"Order {oid} not delivered within the max supervision window. "
                     f"Auto-refund initiated; customer notified."},
        )
        await self._action(
            "message_customer",
            {"message": "Unfortunately your order could not be delivered in time. "
                        "We have initiated a full refund, which will be completed "
                        "within 7 working days."},
        )
        note = "Auto-refund initiated due to non-delivery; customer notified (7 working days)."
        self._important_events.append(note)
        self._important_events = self._important_events[-MAX_IMPORTANT_EVENTS:]
        self._rolling_summary = (self._rolling_summary + " | " + note).strip(" |")
        await workflow.execute_activity(
            persist_memory_update,
            args=[self._inp.run_id, self._rolling_summary, list(self._important_events)],
            start_to_close_timeout=_DEFAULT_TO,
            retry_policy=_ACT_RETRY,
        )
        await self._persist(
            "lifecycle", {"event": "auto_refund_initiated", "reason": "non_delivery"}
        )

    async def _finalize(self) -> None:
        reason = self._end_reason or "completed"
        status = self._end_status or "completed"

        if status == "expired":
            await self._escalate_and_refund_undelivered()

        final = await workflow.execute_activity(
            generate_final_output,
            {
                "run_id": self._inp.run_id,
                "reason": reason,
                "rolling_summary": self._rolling_summary,
                "important_events": list(self._important_events),
            },
            start_to_close_timeout=_DEFAULT_TO,
            retry_policy=_ACT_RETRY,
        )
        self._inp_final_output = final
        self._status = status
        self._sleep_state = "ended"
        await self._persist_run_fields(
            {
                "status": status,
                "sleep_state": "ended",
                "final_output": final,
                "completed_at": workflow.now().isoformat(),
            }
        )
        await self._persist("lifecycle", {"event": status, "reason": reason})

    # ------------------------------------------------------------------ #
    # continue_as_new
    # ------------------------------------------------------------------ #
    def _carryover_input(self) -> WorkflowInput:
        new = WorkflowInput(
            run_id=self._inp.run_id,
            order_id=self._inp.order_id,
            supervisor=self._inp.supervisor,
            order_context=self._inp.order_context,
            time_scale=self._inp.time_scale,
            max_age_hours=self._inp.max_age_hours,
            return_window_hours=self._inp.return_window_hours,
            carryover={
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "rolling_summary": self._rolling_summary,
                "important_events": list(self._important_events),
                "wake_on": self._wake_on,
                "wake_note": self._wake_note,
                "wake_deadline": self._wake_deadline.isoformat() if self._wake_deadline else None,
                "turn": self._turn,
                "recommend_completion": self._recommend_completion,
                "delivered": self._delivered,
                "post_delivery_deadline": (
                    self._post_delivery_deadline.isoformat()
                    if self._post_delivery_deadline
                    else None
                ),
            },
        )
        return new

    def _init_from_carryover(self, c: dict | None) -> None:
        if not c:
            return
        self._started_at = datetime.fromisoformat(c["started_at"]) if c.get("started_at") else workflow.now()
        self._rolling_summary = c.get("rolling_summary", "")
        self._important_events = list(c.get("important_events", []))
        self._wake_on = list(c.get("wake_on", []))
        self._wake_note = c.get("wake_note", "")
        self._turn = c.get("turn", 0)
        self._recommend_completion = c.get("recommend_completion", False)
        self._delivered = c.get("delivered", False)
        if c.get("post_delivery_deadline"):
            self._post_delivery_deadline = datetime.fromisoformat(c["post_delivery_deadline"])
        if c.get("wake_deadline"):
            self._wake_deadline = datetime.fromisoformat(c["wake_deadline"])
            self._next_wake_at = c["wake_deadline"]
        self._sleep_state = "sleeping"

    # ------------------------------------------------------------------ #
    # Persistence helpers (always via activities)
    # ------------------------------------------------------------------ #
    async def _action(self, name: str, args: dict) -> None:
        """Execute one business action (records an activity entry)."""
        await workflow.execute_activity(
            execute_business_action,
            args=[self._inp.run_id, name, args],
            start_to_close_timeout=_DEFAULT_TO,
            retry_policy=_ACT_RETRY,
        )

    async def _persist(self, kind: str, payload: dict) -> None:
        await workflow.execute_activity(
            persist_activity,
            args=[self._inp.run_id, kind, payload],
            start_to_close_timeout=_DEFAULT_TO,
            retry_policy=_ACT_RETRY,
        )

    async def _persist_run_fields(self, fields: dict) -> None:
        await workflow.execute_activity(
            persist_run_update,
            args=[self._inp.run_id, fields],
            start_to_close_timeout=_DEFAULT_TO,
            retry_policy=_ACT_RETRY,
        )

    async def _set_status(self, status: str) -> None:
        self._status = status
        await self._persist_run_fields({"status": status})

    # default attribute so return works even if finalize set nothing
    _inp_final_output: dict = {}
