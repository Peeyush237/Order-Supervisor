"""SQLAlchemy models — single activity-log persistence approach.

Tables:
  supervisors  — reusable config templates
  runs         — one row per order / workflow run
  run_memory   — rolling summary + important events (1:1 with runs)
  activity_log — append-only log of everything that happens in a run
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return uuid.uuid4().hex


# --- Activity log kinds (the single-table approach) ---
ACTIVITY_KINDS = (
    "event",            # incoming order event (signal)
    "wake_decision",    # classifier decided to wake the agent
    "sleep_decision",   # workflow went back to sleep
    "agent_reasoning",  # agent_step reasoning outcome
    "action",           # a business action was executed
    "instruction",      # manual run-specific instruction
    "lifecycle",        # workflow-owned status changes (started/paused/completed/...)
    "final_output",     # end-of-run summary/learnings/feedback
)

# --- Run statuses (workflow-owned) ---
# expired = ended on max age without delivery (escalated + auto-refunded)
RUN_STATUSES = ("active", "paused", "completed", "terminated", "expired")


class Supervisor(Base):
    __tablename__ = "supervisors"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    base_instruction: Mapped[str] = mapped_column(Text)
    available_actions: Mapped[list] = mapped_column(JSONB, default=list)
    default_wake_behavior: Mapped[dict] = mapped_column(JSONB, default=dict)
    # column name "model_config" per spec; attribute renamed to avoid pydantic clash
    llm_config: Mapped[dict] = mapped_column("model_config", JSONB, default=dict)
    wake_aggressiveness: Mapped[str] = mapped_column(String(20), default="balanced")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    runs: Mapped[list[Run]] = relationship(back_populates="supervisor")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    supervisor_id: Mapped[str] = mapped_column(ForeignKey("supervisors.id"))
    order_id: Mapped[str] = mapped_column(String(100), index=True)
    workflow_id: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    order_context: Mapped[dict] = mapped_column(JSONB, default=dict)
    next_wake_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sleep_state: Mapped[str] = mapped_column(String(20), default="awake")  # awake|sleeping
    final_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    supervisor: Mapped[Supervisor] = relationship(back_populates="runs")
    memory: Mapped[RunMemory | None] = relationship(
        back_populates="run", uselist=False, cascade="all, delete-orphan"
    )
    activities: Mapped[list[ActivityLog]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RunMemory(Base):
    __tablename__ = "run_memory"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id"), primary_key=True
    )
    rolling_summary: Mapped[str] = mapped_column(Text, default="")
    important_events: Mapped[list] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    run: Mapped[Run] = relationship(back_populates="memory")


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    kind: Mapped[str] = mapped_column(String(30), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)

    run: Mapped[Run] = relationship(back_populates="activities")
