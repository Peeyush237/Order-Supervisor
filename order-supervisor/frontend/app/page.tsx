"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, Run, Supervisor } from "@/lib/api";
import { StatusBadge, fmtTime } from "@/lib/ui";

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [err, setErr] = useState("");

  // create-run form
  const [supId, setSupId] = useState("");
  const [orderId, setOrderId] = useState("");
  const [ctx, setCtx] = useState('{"item":"Wireless Headphones","amount":199.0}');
  const [defWake, setDefWake] = useState("6");
  const [creating, setCreating] = useState(false);

  async function load() {
    try {
      const [r, s] = await Promise.all([api.listRuns(), api.listSupervisors()]);
      setRuns(r);
      setSupervisors(s);
      if (!supId && s.length) setSupId(s[0].id);
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []); // eslint-disable-line

  async function startRun(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setErr("");
    try {
      let order_context = {};
      try {
        order_context = ctx.trim() ? JSON.parse(ctx) : {};
      } catch {
        throw new Error("order_context is not valid JSON");
      }
      await api.createRun({
        supervisor_id: supId,
        order_id: orderId || `ORDER-${Date.now().toString().slice(-6)}`,
        order_context,
        default_wake_hours: Number(defWake) || undefined,
      });
      setOrderId("");
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="space-y-6">
      {err && <div className="rounded bg-rose-50 p-3 text-sm text-rose-700">{err}</div>}

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 font-medium">Start an order run</h2>
        {supervisors.length === 0 ? (
          <p className="text-sm text-slate-500">
            No supervisors yet — create one on the{" "}
            <Link href="/supervisors" className="text-slate-900 underline">Supervisors</Link> page.
          </p>
        ) : (
          <form onSubmit={startRun} className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Supervisor template</span>
              <select
                value={supId}
                onChange={(e) => setSupId(e.target.value)}
                className="w-full rounded border border-slate-300 px-2 py-1.5"
              >
                {supervisors.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.wake_aggressiveness})
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Order ID (blank = auto)</span>
              <input
                value={orderId}
                onChange={(e) => setOrderId(e.target.value)}
                placeholder="ORDER-123"
                className="w-full rounded border border-slate-300 px-2 py-1.5"
              />
            </label>
            <label className="text-sm md:col-span-2">
              <span className="mb-1 block text-slate-600">Order context (JSON)</span>
              <textarea
                value={ctx}
                onChange={(e) => setCtx(e.target.value)}
                rows={2}
                className="w-full rounded border border-slate-300 px-2 py-1.5 font-mono text-xs"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Default wake (sim hours)</span>
              <input
                value={defWake}
                onChange={(e) => setDefWake(e.target.value)}
                className="w-32 rounded border border-slate-300 px-2 py-1.5"
              />
            </label>
            <div className="flex items-end">
              <button
                disabled={creating}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {creating ? "Starting…" : "Start run"}
              </button>
            </div>
          </form>
        )}
      </section>

      <section>
        <h2 className="mb-3 font-medium">Runs</h2>
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500">
              <tr>
                <th className="px-3 py-2">Order</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Sleep</th>
                <th className="px-3 py-2">Next wake</th>
                <th className="px-3 py-2">Created</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-center text-slate-400">
                    No runs yet.
                  </td>
                </tr>
              )}
              {runs.map((r) => (
                <tr key={r.id} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">{r.order_id}</td>
                  <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
                  <td className="px-3 py-2 text-slate-500">{r.sleep_state}</td>
                  <td className="px-3 py-2 text-slate-500">{fmtTime(r.next_wake_at)}</td>
                  <td className="px-3 py-2 text-slate-500">{fmtTime(r.created_at)}</td>
                  <td className="px-3 py-2 text-right">
                    <Link href={`/runs/${r.id}`} className="text-slate-900 underline">
                      open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
