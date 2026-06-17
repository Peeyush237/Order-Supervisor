# Architecture

## Overview

One **Temporal workflow run per order** (`OrderSupervisorWorkflow`). The workflow
is the orchestrator and owns all control flow; the LLM only *proposes* actions.

```
                  signals                       activities (side effects)
  FastAPI ───────────────────────▶  Temporal  ───────────────────────▶  Postgres
 (REST API)   submit_event          Workflow      agent_step (LLM)        (UI source
              add_instruction      (deterministic, classify_event         of truth)
              set_paused            drain-loop,    business actions ×5
              request_completion    wait_condition compact_memory
                  ▲                  sleep/wake)   final_output
                  │ queries (live state)
  Next.js UI ─────┘ + reads Postgres for lists/timeline/memory
```

## Key design decisions

1. **Deterministic workflow.** No LLM/DB/`datetime.now()`/`random`/network/env
   inside the workflow. Time via `workflow.now()`; all side effects in activities.
2. **Agent is an activity, not a loop.** `agent_step` does one structured LLM
   inference returning JSON: `{reasoning, actions[], memory_update, next_wake_seconds, recommend_completion}`.
   The workflow executes the proposed business-action activities, persists, sets
   the next wake-up, and sleeps.
3. **Three inference triggers:** workflow start, important signal, scheduled wake-up.
4. **Sleep/wake** via `workflow.wait_condition(..., timeout=next_wake)`. Timeout
   with no pending work = the scheduled wake-up (also models `no_update_for_n_hours`).
5. **Signals enqueue; the loop drains.** `submit_event`, `add_instruction`,
   `set_paused`, `request_completion`. Queries expose live state.
6. **Lightweight classifier** (separate from the main agent) decides whether an
   event is important enough to wake the agent now vs. defer to next scheduled wake.
7. **Persistence is the UI's source of truth.** Activities write timeline,
   activity log, memory, status, final output. API reads Postgres + Temporal queries.
8. **`continue_as_new`** when history grows large, carrying compacted memory +
   current order state.
9. **Workflow-owned completion.** The agent may *recommend* completion, but a run
   only ends on workflow rules (see "Lifecycle & completion" below).

## Lifecycle & completion (workflow-owned)

Completion is decided by `_completion_decision()` in the workflow, never by the agent.
Delivered and undelivered orders follow separate rules so they never clash:

- **Delivered → return/refund window.** `delivered` does NOT end the run. It opens a
  return/refund window (`return_window_hours`, default 7 days). During the window the
  supervisor still handles refunds, customer messages, etc. The run completes
  (`return_window_closed`, status `completed`) when the window closes — or earlier on
  manual termination.
- **Undelivered → expired.** If an order is never delivered and reaches `max_age_hours`,
  the workflow escalates to the fulfillment team, auto-refunds the customer (a
  `message_customer` action + `auto_refund_initiated` lifecycle entry), records it in
  memory, and ends with status `expired` (reason `expired_undelivered`).
- **Manual termination.** `request_completion` ends gracefully (runs the final report);
  the API also supports a hard `client.terminate` fallback.

A delivered run is governed only by the return window (max age can't kill it); an
undelivered run is governed only by max age. `activity_log.kind` also includes
`lifecycle` (started, status changes, window opened, auto-refund, etc.).

## Data model (single activity-log approach)

- `supervisors` — config templates (name, base_instruction, available_actions, …).
- `runs` — one per order (status, order_context, next_wake_at, sleep_state, final_output).
- `run_memory` — rolling_summary + important_events.
- `activity_log` — append-only: `kind` ∈ {event, wake_decision, sleep_decision,
  agent_reasoning, action, instruction, lifecycle, final_output}.

## Triggers & control flow

The agent runs on exactly three triggers, then sleeps:
1. **workflow start** — initial inference with order context + base instruction.
2. **important signal** — an event the classifier rates high-priority, or any
   run instruction (treated as an interrupt → immediate inference).
3. **scheduled wake-up** — the `wait_condition` timeout fires with no pending work.

Low-priority events are logged and deferred; the workflow re-sleeps for the
*remaining* time until the existing wake deadline (the timer isn't reset).

## Wake/sleep classifier

Deterministic, in-workflow (so it stays replay-safe), separate from the agent:
- terminal events and unknown events → always wake (unknown-event escalation);
- agent-emitted `wake_guidance.wake_on` → wake;
- otherwise by `wake_aggressiveness`: `aggressive` wakes on all, `balanced` wakes
  on the high-priority set, `conservative` only on payment/refund failures.

Every wake/sleep decision is written to the activity log.

## Memory & compaction

A rolling summary + a capped list of important events. When the list exceeds a
threshold, `compact_memory` (LLM) folds the older entries into the rolling
summary and keeps the most recent few verbatim.

## Phasing (all complete)

- **Phase 0** — scaffold + Hello round trip
- **Phase 1** — DB & persistence layer (single `activity_log`)
- **Phase 2** — Temporal core (signals, drain-loop, wait_condition, queries, workflow-owned completion, continue_as_new hook)
- **Phase 3** — Agent runtime (pluggable LLM, strict decision schema + fallback, classifier, 5 business actions, memory compaction)
- **Phase 4** — FastAPI endpoints
- **Phase 5** — Next.js frontend
- **Phase 6** — LLM end-of-run output, docs, seeded demo script

## Testing

`scripts/test_workflow.py` runs the real workflow against Temporal's
time-skipping test server with the DB mocked in-memory, asserting start/
signal/scheduled-wake triggers, low-vs-high-priority classification, pause/
resume, and workflow-owned terminal completion — no Docker/Postgres/LLM needed.
