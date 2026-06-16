"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function Home() {
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function ping() {
    setLoading(true);
    setResult("");
    try {
      const res = await fetch(`${API}/hello?name=supervisor`, { method: "POST" });
      const data = await res.json();
      setResult(`workflow ${data.workflow_id}: ${data.result}`);
    } catch (e) {
      setResult(`error: ${String(e)}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="space-y-4">
      <p className="text-slate-600">
        Phase 0 scaffold. The runs list, supervisor config, and run detail views
        land in Phase 5.
      </p>
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-2 font-medium">End-to-end smoke test</h2>
        <p className="mb-3 text-sm text-slate-500">
          Starts a HelloWorkflow in Temporal via FastAPI and shows the result.
        </p>
        <button
          onClick={ping}
          disabled={loading}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Running…" : "Run HelloWorkflow"}
        </button>
        {result && (
          <pre className="mt-3 whitespace-pre-wrap rounded bg-slate-100 p-3 text-sm">
            {result}
          </pre>
        )}
      </div>
    </main>
  );
}
