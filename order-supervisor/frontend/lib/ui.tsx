// Small shared presentational helpers.
import React from "react";

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  paused: "bg-amber-100 text-amber-800",
  completed: "bg-blue-100 text-blue-800",
  terminated: "bg-rose-100 text-rose-800",
  expired: "bg-orange-100 text-orange-800",
};

const KIND_STYLES: Record<string, string> = {
  event: "bg-indigo-100 text-indigo-800",
  wake_decision: "bg-green-100 text-green-800",
  sleep_decision: "bg-slate-200 text-slate-700",
  agent_reasoning: "bg-purple-100 text-purple-800",
  action: "bg-cyan-100 text-cyan-800",
  instruction: "bg-amber-100 text-amber-800",
  lifecycle: "bg-slate-100 text-slate-600",
  final_output: "bg-blue-100 text-blue-800",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status] || "bg-slate-100 text-slate-700"}`}>
      {status}
    </span>
  );
}

export function KindBadge({ kind }: { kind: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${KIND_STYLES[kind] || "bg-slate-100 text-slate-700"}`}>
      {kind}
    </span>
  );
}

export function fmtTime(ts: string | null | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return isNaN(d.getTime()) ? String(ts) : d.toLocaleTimeString();
}
