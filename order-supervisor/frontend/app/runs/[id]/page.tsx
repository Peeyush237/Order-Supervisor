"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ActivityEntry, RunDetail, Supervisor, api, EVENT_TYPES } from "@/lib/api";
import {
  Button,
  Caption,
  Card,
  Chip,
  LiveDot,
  SectionTitle,
  StatusBadge,
  Toast,
  dotColor,
  fmtTime,
  inputClass,
  useToast,
} from "@/lib/ui";

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [sup, setSup] = useState<Supervisor | null>(null);
  const [err, setErr] = useState("");
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      const d = await api.getRun(id);
      setDetail(d);
      setErr("");
      if (!sup || sup.id !== d.run.supervisor_id) {
        const list = await api.listSupervisors();
        setSup(list.find((s) => s.id === d.run.supervisor_id) || null);
      }
    } catch (e) {
      setErr(String(e));
    }
  }, [id, sup]);

  useEffect(() => {
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [load]);

  async function act(label: string, fn: () => Promise<unknown>) {
    setBusy(true);
    setErr("");
    try {
      await fn();
      toast.show(label);
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!detail) {
    return (
      <div>
        <Back />
        <p className="mt-6 text-sm text-slate-400">{err || "Loading…"}</p>
      </div>
    );
  }

  const { run, memory, activities, live_state } = detail;
  const live = (live_state || {}) as Record<string, any>;
  const terminal = ["completed", "terminated", "expired"].includes(run.status);
  const sleepState = live.sleep_state || run.sleep_state;

  return (
    <div className="space-y-5">
      <Back />
      {err && <div className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{err}</div>}

      {/* ---- Summary header ---- */}
      <Card className="p-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-xl font-semibold tracking-tight">{run.order_id}</h1>
          <StatusBadge status={run.status} />
          {live.recommend_completion && !terminal && (
            <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
              agent recommends completion
            </span>
          )}
        </div>

        <div className="mt-5 grid grid-cols-2 gap-5 md:grid-cols-4">
          <Stat label="Supervisor" value={sup?.name || run.supervisor_id} />
          <Stat label="Sleep state" value={sleepState} />
          <Stat label="Next wake" value={fmtTime(live.next_wake_at || run.next_wake_at)} mono />
          <Stat label="Turn" value={live.turn ?? "—"} />
        </div>
        <div className="mt-4">
          <Caption>Order context</Caption>
          <div className="mt-1 font-mono text-xs text-slate-600">{JSON.stringify(run.order_context)}</div>
        </div>

        {!terminal && live.delivered && live.return_window_until && (
          <Banner tone="green">
            ✅ Delivered — return/refund window open until <b>{fmtTime(live.return_window_until)}</b>. Refunds are still handled.
          </Banner>
        )}
        {run.status === "expired" && (
          <Banner tone="orange">
            ⚠️ Expired without delivery — escalated to the fulfillment team and a refund was auto-initiated (see timeline & memory).
          </Banner>
        )}
      </Card>

      {/* ---- Lifecycle strip ---- */}
      <div className="flex items-center gap-2.5 px-1 text-xs text-slate-400">
        <span className="font-semibold text-slate-500">Lifecycle</span>
        <span className="font-mono">sleep → wake → evaluate → act → sleep</span>
      </div>

      {/* ---- Controls ---- */}
      {!terminal && (
        <div className="flex flex-wrap gap-2">
          {run.status === "paused" ? (
            <Button variant="primary" disabled={busy} onClick={() => act("Resumed", () => api.resume(id))}>
              ▶ Resume
            </Button>
          ) : (
            <Button variant="secondary" disabled={busy} onClick={() => act("Paused", () => api.pause(id))}>
              ❚❚ Pause
            </Button>
          )}
          <Button variant="primary" disabled={busy} onClick={() => act("Interrupt sent — acting now", () => api.interrupt(id))}>
            ⚡ Interrupt (act now)
          </Button>
          <Button variant="danger" disabled={busy} onClick={() => act("Termination requested", () => api.terminate(id, "manual_termination", false))}>
            Terminate
          </Button>
          <Button variant="danger" disabled={busy} onClick={() => act("Hard killed", () => api.terminate(id, "force", true))}>
            Hard kill
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">
        {/* ---- Left: inject / instruct / memory ---- */}
        <div className="space-y-5 lg:col-span-2">
          {!terminal && (
            <Card className="p-5">
              <SectionTitle>Inject event</SectionTitle>
              <p className="mb-3 mt-1 text-xs text-slate-400">Send an order event into the live workflow as a signal.</p>
              <div className="flex flex-wrap gap-2">
                {EVENT_TYPES.map((ev) => (
                  <Chip key={ev} disabled={busy} onClick={() => act(`Injected ${ev}`, () => api.injectEvent(id, ev))}>
                    {ev}
                  </Chip>
                ))}
              </div>
            </Card>
          )}

          {!terminal && (
            <Card className="p-5">
              <SectionTitle>Add instruction</SectionTitle>
              <p className="mb-3 mt-1 text-xs text-slate-400">Run-specific guidance added to the agent's context.</p>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                rows={3}
                placeholder="e.g. Prioritize speed; escalate any delay immediately."
                className={inputClass}
              />
              <div className="mt-2">
                <Button
                  variant="dark"
                  disabled={busy || !instruction.trim()}
                  onClick={() =>
                    act("Instruction sent", async () => {
                      await api.addInstruction(id, instruction.trim());
                      setInstruction("");
                    })
                  }
                >
                  Send instruction
                </Button>
              </div>
            </Card>
          )}

          <Card className="p-5">
            <SectionTitle>Memory</SectionTitle>
            <div className="mt-3">
              <Caption>Rolling summary</Caption>
              <p className="mt-1 text-sm leading-relaxed text-slate-700">
                {memory.rolling_summary || <span className="text-slate-400">— empty —</span>}
              </p>
            </div>
            <div className="mt-4">
              <Caption>Important events</Caption>
              <ul className="mt-1.5 space-y-1">
                {(memory.important_events || []).map((e, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="text-slate-300">•</span>
                    {e}
                  </li>
                ))}
                {(memory.important_events || []).length === 0 && <li className="text-sm text-slate-400">— none —</li>}
              </ul>
            </div>
          </Card>
        </div>

        {/* ---- Right: final output + timeline ---- */}
        <div className="space-y-5 lg:col-span-3">
          {run.final_output && <FinalOutput output={run.final_output} />}

          <Card className="p-6 pb-3">
            <SectionTitle
              right={<span className="text-xs text-slate-400">auto-refresh 2s</span>}
            >
              Timeline &amp; activity ({activities.length})
            </SectionTitle>
            <div className="mt-5 max-h-[64vh] overflow-auto pr-1">
              {activities.map((a, i) => (
                <TimelineNode key={a.id} entry={a} last={i === activities.length - 1 && terminal} />
              ))}
              {!terminal && <LiveNode sleepState={sleepState} nextWake={live.next_wake_at || run.next_wake_at} />}
              {activities.length === 0 && <p className="text-sm text-slate-400">No activity yet.</p>}
            </div>
          </Card>
        </div>
      </div>

      <Toast msg={toast.msg} />
    </div>
  );
}

/* ----------------------------- timeline node ---------------------------- */
function TimelineNode({ entry, last }: { entry: ActivityEntry; last: boolean }) {
  const v = describe(entry);
  return (
    <div className="flex gap-4">
      <div className="w-16 flex-none pt-px text-right font-mono text-xs text-slate-400">{fmtTime(entry.ts)}</div>
      <div className="flex w-3.5 flex-none flex-col items-center">
        <span
          className="mt-1.5 h-2.5 w-2.5 flex-none rounded-full"
          style={{ background: v.color, boxShadow: "0 0 0 3px #fff" }}
        />
        {!last && <span className="my-1 w-0.5 flex-1 bg-slate-200" />}
      </div>
      <div className="flex-1 pb-5">
        <div className="text-sm font-semibold text-slate-900">{v.title}</div>
        {v.sub && <div className="mt-0.5 text-[13px] leading-relaxed text-slate-500">{v.sub}</div>}

        {v.reasoning && (
          <div className="mt-2 rounded-r-md border-l-2 border-slate-300 bg-slate-50 px-3 py-2">
            <span className="text-[10.5px] font-bold tracking-wider text-slate-400">REASONING</span>
            <div className="mt-0.5 text-[12.5px] leading-relaxed text-slate-600">{v.reasoning}</div>
          </div>
        )}

        {v.actionName && (
          <div className="mt-2.5 overflow-hidden rounded-lg border border-line">
            <div className="flex items-center gap-2 bg-slate-900 px-3 py-2">
              <span className="text-[10px] font-bold tracking-wider text-indigo-400">ACTION</span>
              <span className="font-mono text-[12.5px] font-medium text-white">{v.actionName}</span>
              {v.actionStatus && v.actionStatus !== "recorded" && (
                <span className="ml-auto rounded bg-rose-500/20 px-1.5 text-[10px] text-rose-300">{v.actionStatus}</span>
              )}
            </div>
            {v.actionMsg && <div className="bg-white px-3 py-2.5 text-[13px] leading-relaxed text-slate-600">{v.actionMsg}</div>}
          </div>
        )}
      </div>
    </div>
  );
}

function LiveNode({ sleepState, nextWake }: { sleepState: string; nextWake: string | null }) {
  const awake = sleepState === "awake";
  return (
    <div className="flex gap-4">
      <div className="w-16 flex-none" />
      <div className="flex w-3.5 flex-none justify-center">
        <LiveDot tone={awake ? "live" : "sleep"} />
      </div>
      <div className="flex-1 pb-2">
        <div className={"text-sm font-semibold " + (awake ? "text-green-600" : "text-indigo-600")}>
          {awake ? "Awake — evaluating order" : "Sleeping"}
        </div>
        <div className="mt-0.5 text-[13px] text-slate-500">
          {awake ? "The supervisor is deciding whether to act." : <>Next scheduled wake at <b>{fmtTime(nextWake)}</b>.</>}
        </div>
      </div>
    </div>
  );
}

/* ----------------------- activity -> view model ------------------------- */
function describe(a: ActivityEntry): {
  title: string;
  sub?: string;
  reasoning?: string;
  actionName?: string;
  actionMsg?: string;
  actionStatus?: string;
  color: string;
} {
  const p: any = a.payload || {};
  let color = dotColor(a.kind);

  switch (a.kind) {
    case "lifecycle": {
      const ev = String(p.event || "");
      if (ev === "completed") color = "#16a34a";
      else if (ev === "expired") color = "#ea580c";
      else if (ev === "terminated") color = "#e11d48";
      const titles: Record<string, string> = {
        started: "Run started",
        completed: "Run completed",
        expired: "Run expired",
        terminated: "Run terminated",
        auto_refund_initiated: "Auto-refund initiated",
        wake_guidance_updated: "Wake guidance updated",
      };
      return { title: titles[ev] || `Lifecycle: ${ev}`, sub: p.reason ? `reason: ${p.reason}` : "", color };
    }
    case "event":
      return {
        title: `Event: ${p.type}`,
        sub: `${p.priority || ""}${p.data && Object.keys(p.data).length ? " · " + JSON.stringify(p.data) : ""}`,
        color,
      };
    case "wake_decision":
      return { title: "Woke the agent", sub: `${p.reason || ""}${p.events ? " · " + JSON.stringify(p.events) : ""}`, color };
    case "sleep_decision":
      return {
        title: p.next_wake_at ? "Back to sleep" : "Event deferred",
        sub: p.next_wake_at ? `until ${fmtTime(p.next_wake_at)}` : `${p.event || ""} (${p.reason || "low priority"})`,
        color,
      };
    case "agent_reasoning":
      return { title: `Agent evaluated (${p.trigger || "?"})`, reasoning: p.reasoning || "", color };
    case "action":
      return {
        title: "Action taken",
        actionName: p.action,
        actionMsg: p.args?.message || p.args?.note || (p.args ? JSON.stringify(p.args) : ""),
        actionStatus: p.status,
        color,
      };
    case "instruction":
      return { title: "Instruction added", sub: p.text, color };
    case "final_output":
      return { title: "Final report produced", sub: p.summary, color: "#16a34a" };
    default:
      return { title: a.kind, sub: JSON.stringify(p), color };
  }
}

/* ------------------------------ final output ---------------------------- */
function FinalOutput({ output }: { output: Record<string, any> }) {
  const arr = (k: string) => (Array.isArray(output[k]) ? output[k] : []);
  const acts = arr("important_actions").map((a: any) =>
    typeof a === "string" ? a : `${a.action} ${a.args ? JSON.stringify(a.args) : ""}`
  );
  return (
    <Card className="border-indigo-200 bg-indigo-50/40 p-6">
      <div className="flex items-center gap-2">
        <SectionTitle>End-of-run report</SectionTitle>
        {output.reason && <span className="rounded-full bg-white px-2 py-0.5 text-[11px] text-indigo-600">{output.reason}</span>}
      </div>
      <p className="mt-3 text-sm leading-relaxed text-slate-700">{output.summary}</p>
      <FinalList title="Important actions" items={acts} />
      <FinalList title="Key learnings" items={arr("key_learnings")} />
      <FinalList title="Recommendations" items={arr("recommendations")} />
    </Card>
  );
}

function FinalList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-3">
      <Caption>{title}</Caption>
      <ul className="mt-1 space-y-0.5">
        {items.map((x, i) => (
          <li key={i} className="flex gap-2 text-[13px] text-slate-700">
            <span className="text-indigo-300">•</span>
            {x}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* -------------------------------- bits ---------------------------------- */
function Back() {
  return (
    <Link href="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-indigo-600">
      ← Back to runs
    </Link>
  );
}

function Stat({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <Caption>{label}</Caption>
      <div className={"mt-1 text-sm font-medium text-slate-900 " + (mono ? "font-mono text-xs" : "")}>{value}</div>
    </div>
  );
}

function Banner({ tone, children }: { tone: "green" | "orange"; children: React.ReactNode }) {
  const cls = tone === "green" ? "bg-emerald-50 text-emerald-800" : "bg-orange-50 text-orange-800";
  return <div className={`mt-4 rounded-lg px-3 py-2 text-sm ${cls}`}>{children}</div>;
}
