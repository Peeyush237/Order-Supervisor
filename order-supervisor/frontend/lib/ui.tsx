// UI kit styled after the design comp: Inter/JetBrains Mono, soft gray canvas,
// indigo accent, dark CTAs, colored status pills, timeline dots.
"use client";

import React from "react";

/* ------------------------------- Button --------------------------------- */
type Variant = "dark" | "primary" | "secondary" | "danger" | "ghost";

export function Button({
  variant = "secondary",
  loading = false,
  className = "",
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  const base =
    "inline-flex items-center justify-center gap-1.5 rounded-lg text-sm font-semibold transition-all duration-100 " +
    "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:opacity-40 " +
    "disabled:cursor-not-allowed cursor-pointer select-none";
  const variants: Record<Variant, string> = {
    dark: "h-11 px-5 text-white bg-slate-900 hover:bg-slate-950 hover:-translate-y-px hover:shadow-lg active:translate-y-0 active:shadow-none",
    primary: "h-10 px-4 text-white bg-indigo-600 hover:bg-indigo-700 hover:-translate-y-px hover:shadow-md active:translate-y-0",
    secondary: "h-10 px-4 border border-slate-300 bg-white text-slate-700 hover:border-indigo-400 hover:text-indigo-600 active:bg-indigo-50",
    danger: "h-10 px-4 border border-slate-300 bg-white text-slate-600 hover:border-rose-400 hover:text-rose-600 active:bg-rose-50",
    ghost: "h-10 px-3 text-slate-500 hover:bg-slate-100 hover:text-indigo-600",
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} disabled={loading || props.disabled} {...props}>
      {loading && <Spinner />}
      {children}
    </button>
  );
}

/* --------------------------- Pressable chip ----------------------------- */
export function Chip({ className = "", children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={
        "cursor-pointer select-none rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-mono text-xs text-slate-700 " +
        "transition-colors hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-600 active:bg-indigo-100 " +
        "focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed " +
        className
      }
      {...props}
    >
      {children}
    </button>
  );
}

/* ------------------------------- Card ----------------------------------- */
export function Card({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return <div className={`rounded-xl border border-line bg-white ${className}`}>{children}</div>;
}

// Card / section heading (16px, dark) — matches the comp's <h2>.
export function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-base font-semibold text-slate-900">{children}</h2>
      {right}
    </div>
  );
}

// Small uppercase caption used for field labels and stat keys.
export function Caption({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{children}</div>;
}

export function Label({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <span className="mb-1.5 block text-[13px] font-medium text-slate-500">
      {children}
      {hint && <span className="ml-1 font-normal text-slate-300">{hint}</span>}
    </span>
  );
}

export function Field({ label, hint, children }: { label: React.ReactNode; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <Label hint={hint}>{label}</Label>
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 " +
  "transition-shadow focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100";

/* ------------------------------ Spinner --------------------------------- */
export function Spinner() {
  return <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />;
}

/* ----------------------------- Live dot --------------------------------- */
export function LiveDot({ on, tone }: { on?: boolean; tone?: "live" | "sleep" | "idle" }) {
  const t: "live" | "sleep" | "idle" = tone ?? (on ? "live" : "idle");
  const color = t === "live" ? "bg-green-500" : t === "sleep" ? "bg-indigo-500" : "bg-slate-300";
  if (t === "idle") return <span className={`inline-block h-2 w-2 rounded-full ${color}`} />;
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} style={{ animation: "os-pulse 1.4s ease-in-out infinite" }} />;
}

/* ---------------------------- Status badge ------------------------------ */
const STATUS: Record<string, string> = {
  completed: "bg-indigo-50 text-indigo-600",
  active: "bg-green-50 text-green-700",
  paused: "bg-amber-50 text-amber-700",
  expired: "bg-orange-50 text-orange-700",
  terminated: "bg-rose-50 text-rose-600",
};
export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS[status] || STATUS.completed}`}>
      {status}
    </span>
  );
}

const AGG: Record<string, string> = {
  balanced: "bg-indigo-50 text-indigo-600",
  aggressive: "bg-rose-50 text-rose-600",
  conservative: "bg-slate-100 text-slate-500",
};
export function AggBadge({ agg }: { agg: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${AGG[agg] || AGG.balanced}`}>
      {agg}
    </span>
  );
}

/* --------------------------- Timeline dot ------------------------------- */
// Colors per activity_log kind, matching the comp's dot language.
export function dotColor(kind: string): string {
  return (
    {
      lifecycle: "#94a3b8",
      sleep_decision: "#cbd5e1",
      wake_decision: "#4f46e5",
      event: "#64748b",
      instruction: "#b45309",
      agent_reasoning: "#4f46e5",
      action: "#111827",
      final_output: "#16a34a",
    }[kind] || "#cbd5e1"
  );
}

/* ------------------------------- Toast ---------------------------------- */
export function Toast({ msg }: { msg: string }) {
  if (!msg) return null;
  return (
    <div
      className="fixed bottom-7 left-1/2 z-50 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white shadow-2xl"
      style={{ transform: "translateX(-50%)", animation: "os-toast .22s ease both" }}
    >
      {msg}
    </div>
  );
}

/* ------------------------------- utils ---------------------------------- */
export function fmtTime(ts: string | null | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return isNaN(d.getTime()) ? String(ts) : d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

export function sinceSeconds(ts: number): string {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  return s < 2 ? "just now" : `${s}s ago`;
}

/* --------------------------- toast hook --------------------------------- */
export function useToast() {
  const [msg, setMsg] = React.useState("");
  const ref = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const show = React.useCallback((m: string) => {
    setMsg(m);
    clearTimeout(ref.current);
    ref.current = setTimeout(() => setMsg(""), 2400);
  }, []);
  return { msg, show };
}
