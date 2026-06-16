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
        self._terminal_event_received: bool = False
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
            if self._terminate_requested:
                break
            if self._terminal_event_received or self._is_past_max_age():
                break

            if self._paused:
                await self._set_status("paused")
                await workflow.wait_condition(
                    lambda: (not self._paused) or self._terminate_requested
                )
                if self._terminate_requested:
                    break
                await self._set_status("active")
                continue

            timed_out = await self._sleep_until_wake()

            if self._terminate_requested or self._paused:
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
        if self._wake_deadline is None:
            return None  # sleep until a signal arrives
        remaining = (self._wake_deadline - workflow.now()).total_seconds()
        return timedelta(seconds=max(0.0, remaining))

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
            if etype in TERMINAL_EVENTS:
                self._terminal_event_received = True
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
            await workflow.execute_activity(
                execute_business_action,
                args=[self._inp.run_id, action.get("name", ""), action.get("args", {})],
                start_to_close_timeout=_DEFAULT_TO,
                retry_policy=_ACT_RETRY,
            )

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
    # Completion
    # ------------------------------------------------------------------ #
    def _is_past_max_age(self) -> bool:
        if self._started_at is None:
            return False
        max_real = self._inp.max_age_hours * self._inp.time_scale
        return (workflow.now() - self._started_at).total_seconds() >= max_real

    async def _finalize(self) -> None:
        if self._terminate_requested:
            reason, status = (self._terminate_reason or "terminated"), "terminated"
        elif self._terminal_event_received:
            reason, status = "terminal_event", "completed"
        else:
            reason, status = "max_age_reached", "completed"

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
            carryover={
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "rolling_summary": self._rolling_summary,
                "important_events": list(self._important_events),
                "wake_on": self._wake_on,
                "wake_note": self._wake_note,
                "wake_deadline": self._wake_deadline.isoformat() if self._wake_deadline else None,
                "turn": self._turn,
                "recommend_completion": self._recommend_completion,
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
        if c.get("wake_deadline"):
            self._wake_deadline = datetime.fromisoformat(c["wake_deadline"])
            self._next_wake_at = c["wake_deadline"]
        self._sleep_state = "sleeping"

    # ------------------------------------------------------------------ #
    # Persistence helpers (always via activities)
    # ------------------------------------------------------------------ #
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
