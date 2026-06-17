"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, Run, Supervisor } from "@/lib/api";
import {
  Button,
  Card,
  Field,
  LiveDot,
  SectionTitle,
  StatusBadge,
  fmtTime,
  inputClass,
} from "@/lib/ui";

export default function RunsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<Run[]>([]);
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [err, setErr] = useState("");

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
        throw new Error("Order context is not valid JSON");
      }
      const run = await api.createRun({
        supervisor_id: supId,
        order_id: orderId || `ORDER-${Date.now().toString().slice(-6)}`,
        order_context,
        default_wake_hours: Number(defWake) || undefined,
      });
      router.push(`/runs/${run.id}`);
    } catch (e) {
      setErr(String(e));
      setCreating(false);
    }
  }

  const activeCount = runs.filter((r) => r.status === "active" || r.status === "paused").length;

  return (
    <div className="space-y-6">
      {err && <div className="rounded-md bg-rose-50 p-3 text-sm text-rose-700">{err}</div>}

      {/* Start a run */}
      <Card className="p-4">
        <SectionTitle>Start an order run</SectionTitle>
        {supervisors.length === 0 ? (
          <p className="mt-3 text-sm text-gray-500">
            No supervisors yet. Create one on the Supervisors page first.
          </p>
        ) : (
          <form onSubmit={startRun} className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="Supervisor template">
              <select value={supId} onChange={(e) => setSupId(e.target.value)} className={inputClass}>
                {supervisors.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} · {s.wake_aggressiveness}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Order ID (blank = auto)">
              <input value={orderId} onChange={(e) => setOrderId(e.target.value)} placeholder="ORDER-123" className={inputClass} />
            </Field>
            <div className="md:col-span-2">
              <Field label="Order context (JSON)">
                <textarea value={ctx} onChange={(e) => setCtx(e.target.value)} rows={2} className={`${inputClass} font-mono text-xs`} />
              </Field>
            </div>
            <Field label="Default wake (simulated hours)">
              <input value={defWake} onChange={(e) => setDefWake(e.target.value)} className={`${inputClass} w-32`} />
            </Field>
            <div className="flex items-end">
              <Button type="submit" variant="primary" loading={creating}>
                {creating ? "Starting…" : "Start run →"}
              </Button>
            </div>
          </form>
        )}
      </Card>

      {/* Runs */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <SectionTitle>Runs</SectionTitle>
          <span className="flex items-center gap-1.5 text-xs text-gray-500">
            <LiveDot on={activeCount > 0} /> {activeCount} live · {runs.length} total
          </span>
        </div>
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-200 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-2 font-medium">Order</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Sleep</th>
                <th className="px-4 py-2 font-medium">Next wake</th>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                    No runs yet — start one above.
                  </td>
                </tr>
              )}
              {runs.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => router.push(`/runs/${r.id}`)}
                  className="cursor-pointer border-b border-gray-100 last:border-0 transition-colors hover:bg-indigo-50/40"
                >
                  <td className="px-4 py-2.5 font-medium text-gray-900">{r.order_id}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={r.status} /></td>
                  <td className="px-4 py-2.5 text-gray-500">{r.sleep_state}</td>
                  <td className="px-4 py-2.5 text-gray-500">{fmtTime(r.next_wake_at)}</td>
                  <td className="px-4 py-2.5 text-gray-500">{fmtTime(r.created_at)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/runs/${r.id}`);
                      }}
                      className="rounded-lg border border-indigo-100 bg-indigo-50 px-3.5 py-1.5 text-[13px] font-semibold text-indigo-600 transition-colors hover:border-indigo-600 hover:bg-indigo-600 hover:text-white"
                    >
                      open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
