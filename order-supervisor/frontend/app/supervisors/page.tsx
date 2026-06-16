"use client";

import { useEffect, useState } from "react";

import { api, BUSINESS_ACTIONS, Supervisor } from "@/lib/api";

export default function SupervisorsPage() {
  const [items, setItems] = useState<Supervisor[]>([]);
  const [err, setErr] = useState("");

  const [name, setName] = useState("");
  const [instr, setInstr] = useState("");
  const [aggr, setAggr] = useState("balanced");
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
    <main className="space-y-6">
      {err && <div className="rounded bg-rose-50 p-3 text-sm text-rose-700">{err}</div>}

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 font-medium">New supervisor template</h2>
        <form onSubmit={create} className="space-y-3">
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full rounded border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Base instruction</span>
            <textarea
              value={instr}
              onChange={(e) => setInstr(e.target.value)}
              required
              rows={3}
              className="w-full rounded border border-slate-300 px-2 py-1.5"
            />
          </label>
          <div className="flex flex-wrap gap-4">
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Wake aggressiveness</span>
              <select
                value={aggr}
                onChange={(e) => setAggr(e.target.value)}
                className="rounded border border-slate-300 px-2 py-1.5"
              >
                <option value="conservative">conservative</option>
                <option value="balanced">balanced</option>
                <option value="aggressive">aggressive</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Default wake (sim hours)</span>
              <input
                value={wakeHours}
                onChange={(e) => setWakeHours(e.target.value)}
                className="w-28 rounded border border-slate-300 px-2 py-1.5"
              />
            </label>
          </div>
          <div className="text-sm">
            <span className="mb-1 block text-slate-600">Available actions</span>
            <div className="flex flex-wrap gap-3">
              {BUSINESS_ACTIONS.map((a) => (
                <label key={a} className="flex items-center gap-1.5">
                  <input type="checkbox" checked={actions.includes(a)} onChange={() => toggle(a)} />
                  <span className="font-mono text-xs">{a}</span>
                </label>
              ))}
            </div>
          </div>
          <button
            disabled={saving}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {saving ? "Saving…" : "Create template"}
          </button>
        </form>
      </section>

      <section>
        <h2 className="mb-3 font-medium">Templates</h2>
        <div className="space-y-3">
          {items.map((s) => (
            <div key={s.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">{s.name}</h3>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">
                  {s.wake_aggressiveness}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-600">{s.base_instruction}</p>
              <p className="mt-2 font-mono text-[11px] text-slate-400">
                {(s.available_actions || []).join(" · ")}
              </p>
            </div>
          ))}
          {items.length === 0 && <p className="text-sm text-slate-400">No templates.</p>}
        </div>
      </section>
    </main>
  );
}
