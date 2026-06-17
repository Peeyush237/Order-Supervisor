"use client";

import { useEffect, useState } from "react";

import { api, BUSINESS_ACTIONS, Supervisor } from "@/lib/api";
import { Button, Card, Field, SectionTitle, inputClass } from "@/lib/ui";

const AGGR = ["conservative", "balanced", "aggressive"] as const;

export default function SupervisorsPage() {
  const [items, setItems] = useState<Supervisor[]>([]);
  const [err, setErr] = useState("");

  const [name, setName] = useState("");
  const [instr, setInstr] = useState("");
  const [aggr, setAggr] = useState<string>("balanced");
  const [wakeHours, setWakeHours] = useState("6");
  const [actions, setActions] = useState<string[]>([...BUSINESS_ACTIONS]);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      setItems(await api.listSupervisors());
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
  }
  useEffect(() => {
    load();
  }, []);

  function toggle(a: string) {
    setActions((cur) => (cur.includes(a) ? cur.filter((x) => x !== a) : [...cur, a]));
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      await api.createSupervisor({
        name,
        base_instruction: instr,
        available_actions: actions,
        wake_aggressiveness: aggr,
        default_wake_behavior: { default_wake_hours: Number(wakeHours) || 6 },
      } as Partial<Supervisor>);
      setName("");
      setInstr("");
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
      {err && (
        <div className="rounded-md bg-rose-50 p-3 text-sm text-rose-700 lg:col-span-5">{err}</div>
      )}

      {/* Configure behavior */}
      <Card className="p-4 lg:col-span-2">
        <SectionTitle>Configure a supervisor</SectionTitle>
        <form onSubmit={create} className="mt-3 space-y-3">
          <Field label="Name">
            <input value={name} onChange={(e) => setName(e.target.value)} required className={inputClass} />
          </Field>
          <Field label="Base instruction">
            <textarea
              value={instr}
              onChange={(e) => setInstr(e.target.value)}
              required
              rows={4}
              placeholder="How should this supervisor behave? e.g. Watch the order; act on issues, otherwise sleep."
              className={inputClass}
            />
          </Field>

          <div>
            <span className="mb-1 block text-sm text-gray-600">Wake aggressiveness</span>
            <div className="flex gap-1 rounded-md border border-gray-300 bg-white p-1">
              {AGGR.map((a) => (
                <button
                  key={a}
                  type="button"
                  onClick={() => setAggr(a)}
                  className={
                    "flex-1 cursor-pointer rounded px-2 py-1 text-xs font-medium capitalize transition-colors " +
                    (aggr === a ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-100")
                  }
                >
                  {a}
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-gray-400">
              How readily an event wakes the agent vs. waiting for the next scheduled check.
            </p>
          </div>

          <Field label="Default wake (simulated hours)">
            <input value={wakeHours} onChange={(e) => setWakeHours(e.target.value)} className={`${inputClass} w-28`} />
          </Field>

          <div>
            <span className="mb-1 block text-sm text-gray-600">Available actions</span>
            <div className="grid grid-cols-1 gap-1.5">
              {BUSINESS_ACTIONS.map((a) => {
                const on = actions.includes(a);
                return (
                  <button
                    key={a}
                    type="button"
                    onClick={() => toggle(a)}
                    className={
                      "flex cursor-pointer items-center justify-between rounded-md border px-2.5 py-1.5 text-left transition-colors " +
                      (on
                        ? "border-indigo-300 bg-indigo-50"
                        : "border-gray-200 bg-white hover:border-gray-300")
                    }
                  >
                    <span className="font-mono text-xs text-gray-700">{a}</span>
                    <span
                      className={
                        "ml-2 inline-flex h-4 w-4 items-center justify-center rounded text-[10px] text-white " +
                        (on ? "bg-indigo-600" : "bg-gray-300")
                      }
                    >
                      {on ? "✓" : ""}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <Button type="submit" variant="primary" loading={saving}>
            {saving ? "Saving…" : "Create template"}
          </Button>
        </form>
      </Card>

      {/* Templates */}
      <div className="space-y-3 lg:col-span-3">
        <SectionTitle>Templates</SectionTitle>
        {items.length === 0 && <p className="text-sm text-gray-400">No templates yet.</p>}
        {items.map((s) => (
          <Card key={s.id} className="p-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-gray-900">{s.name}</h3>
              <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs capitalize text-gray-600">
                {s.wake_aggressiveness}
              </span>
            </div>
            <p className="mt-1.5 text-sm text-gray-600">{s.base_instruction}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {(s.available_actions || []).map((a) => (
                <span key={a} className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 font-mono text-[11px] text-gray-500">
                  {a}
                </span>
              ))}
            </div>
            <p className="mt-2 text-xs text-gray-400">
              default wake: {(s.default_wake_behavior as any)?.default_wake_hours ?? "—"} sim-h
            </p>
          </Card>
        ))}
      </div>
    </div>
  );
}
