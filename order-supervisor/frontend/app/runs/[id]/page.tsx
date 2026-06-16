"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, EVENT_TYPES, RunDetail } from "@/lib/api";
import { KindBadge, StatusBadge, fmtTime } from "@/lib/ui";

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [err, setErr] = useState("");
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      setDetail(await api.getRun(id));
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
  }, [id]);

  useEffect(() => {
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [load]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setErr("");
    try {
      await fn();
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!detail) {
    return (
      <main>
        <Link href="/" className="text-sm text-slate-500 underline">← runs</Link>
        <p className="mt-4 text-slate-400">{err || "Loading…"}</p>
      </main>
    );
  }

  const { run, memory, activities, live_state } = detail;
  const live = (live_state || {}) as Record<string, any>;
  const terminal =
    run.status === "completed" ||
    run.status === "terminated" ||
    run.status === "expired";

  return (
    <main className="space-y-5">
      <Link href="/" className="text-sm text-slate-500 underline">← runs</Link>
      {err && <div className="rounded bg-rose-50 p-3 text-sm text-rose-700">{err}</div>}

      {/* Header / live state */}
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">{run.order_id}</h2>
          <StatusBadge status={run.status} />
          <span className="text-sm text-slate-500">
            sleep: <b>{live.sleep_state || run.sleep_state}</b>
          </span>
          <span className="text-sm text-slate-500">
            next wake: <b>{fmtTime(live.next_wake_at || run.next_wake_at)}</b>
          </span>
          <span className="text-sm text-slate-500">turn: <b>{live.turn ?? "—"}</b></span>
          {live.recommend_completion && (
            <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
              agent recommends completion
            </span>
          )}
        </div>
        <p className="mt-2 font-mono text-xs text-slate-400">
          workflow: {run.workflow_id}
        </p>
        {!terminal && live.delivered && live.return_window_until && (
          <div className="mt-3 rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            ✅ Delivered — return/refund window open until{" "}
            <b>{fmtTime(live.return_window_until)}</b>. Refund requests are still handled.
          </div>
        )}
        {run.status === "expired" && (
          <div className="mt-3 rounded bg-orange-50 px-3 py-2 text-sm text-orange-800">
            ⚠️ Expired without delivery — escalated to the fulfillment team and a refund
            was auto-initiated (see activity log & memory).
          </div>
        )}
      </section>

      {/* Controls */}
      {!terminal && (
        <section className="flex flex-wrap gap-2">
          {run.status === "paused" ? (
            <button onClick={() => act(() => api.resume(id))} disabled={busy}
              className="rounded bg-green-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Resume</button>
          ) : (
            <button onClick={() => act(() => api.pause(id))} disabled={busy}
              className="rounded bg-amber-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Pause</button>
          )}
          <button onClick={() => act(() => api.interrupt(id))} disabled={busy}
            className="rounded bg-purple-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Interrupt (act now)</button>
          <button onClick={() => act(() => api.terminate(id, "manual_termination", false))} disabled={busy}
            className="rounded bg-rose-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Terminate (graceful)</button>
          <button onClick={() => act(() => api.terminate(id, "force", true))} disabled={busy}
            className="rounded border border-rose-300 px-3 py-1.5 text-sm text-rose-700 disabled:opacity-50">Hard kill</button>
        </section>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Left column: injectors + memory */}
        <div className="space-y-5">
          {!terminal && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h3 className="mb-2 font-medium">Inject event</h3>
              <div className="flex flex-wrap gap-2">
                {EVENT_TYPES.map((ev) => (
                  <button
                    key={ev}
                    onClick={() => act(() => api.injectEvent(id, ev))}
                    disabled={busy}
                    className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
                  >
                    {ev}
                  </button>
                ))}
              </div>
            </section>
          )}

          {!terminal && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h3 className="mb-2 font-medium">Add run instruction</h3>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                rows={3}
                placeholder="e.g. For this order, prioritize speed; escalate delays immediately."
                className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              />
              <button
                onClick={() =>
                  act(async () => {
                    if (instruction.trim()) {
                      await api.addInstruction(id, instruction.trim());
                      setInstruction("");
                    }
                  })
                }
                disabled={busy || !instruction.trim()}
                className="mt-2 rounded bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
              >
                Send instruction
              </button>
            </section>
          )}

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-2 font-medium">Memory</h3>
            <p className="text-xs uppercase tracking-wide text-slate-400">Rolling summary</p>
            <p className="mb-3 text-sm text-slate-700">
              {memory.rolling_summary || <span className="text-slate-400">— empty —</span>}
            </p>
            <p className="text-xs uppercase tracking-wide text-slate-400">Important events</p>
            <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
              {(memory.important_events || []).map((e, i) => <li key={i}>{e}</li>)}
              {(memory.important_events || []).length === 0 && (
                <li className="list-none text-slate-400">— none —</li>
              )}
            </ul>
          </section>
        </div>

        {/* Right: timeline + final output */}
        <div className="space-y-5 lg:col-span-2">
          {run.final_output && (
            <section className="rounded-lg border border-blue-200 bg-blue-50 p-4">
              <h3 className="mb-2 font-medium text-blue-900">End-of-run output</h3>
              <FinalOutput output={run.final_output} />
            </section>
          )}

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-medium">Timeline & activity ({activities.length})</h3>
              <span className="text-xs text-slate-400">auto-refresh 2s</span>
            </div>
            <div ref={logRef} className="max-h-[60vh] space-y-2 overflow-auto">
              {activities.map((a) => (
                <div key={a.id} className="rounded border border-slate-100 bg-slate-50 p-2">
                  <div className="flex items-center gap-2">
                    <KindBadge kind={a.kind} />
                    <span className="text-[11px] text-slate-400">{fmtTime(a.ts)}</span>
                  </div>
                  <pre className="mt-1 whitespace-pre-wrap break-words text-xs text-slate-700">
                    {summarize(a.kind, a.payload)}
                  </pre>
                </div>
              ))}
              {activities.length === 0 && (
                <p className="text-sm text-slate-400">No activity yet.</p>
              )}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

function summarize(kind: string, p: Record<string, any>): string {
  if (kind === "action") {
    const args = p.args ? JSON.stringify(p.args) : "";
    return `${p.action} ${args}${p.status && p.status !== "recorded" ? ` [${p.status}]` : ""}`;
  }
  if (kind === "event") return `${p.type} (${p.priority})${p.data && Object.keys(p.data).length ? " " + JSON.stringify(p.data) : ""}`;
  if (kind === "agent_reasoning") return `(${p.trigger}) ${p.reasoning}`;
  if (kind === "instruction") return p.text || JSON.stringify(p);
  if (kind === "sleep_decision") return p.next_wake_at ? `sleep until ${fmtTime(p.next_wake_at)}` : (p.reason || JSON.stringify(p));
  if (kind === "wake_decision") return `${p.reason} ${p.events ? JSON.stringify(p.events) : ""}`;
  return JSON.stringify(p);
}

function FinalOutput({ output }: { output: Record<string, any> }) {
  const arr = (k: string) => (Array.isArray(output[k]) ? output[k] : []);
  return (
    <div className="space-y-2 text-sm text-blue-900">
      <p><b>Summary:</b> {output.summary}</p>
      <Section title="Important actions" items={arr("important_actions").map((a: any) => typeof a === "string" ? a : `${a.action} ${a.args ? JSON.stringify(a.args) : ""}`)} />
      <Section title="Key learnings" items={arr("key_learnings")} />
      <Section title="Recommendations" items={arr("recommendations")} />
      {output.reason && <p className="text-xs text-blue-700">reason: {output.reason}</p>}
    </div>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="font-medium">{title}</p>
      <ul className="list-disc pl-5">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  );
}
