// Typed client for the Order Supervisor backend.

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export const EVENT_TYPES = [
  "order_created",
  "payment_confirmed",
  "payment_failed",
  "shipment_created",
  "shipment_delayed",
  "delivered",
  "refund_requested",
  "customer_message_received",
  "no_update_for_n_hours",
] as const;

export const BUSINESS_ACTIONS = [
  "message_fulfillment_team",
  "message_payments_team",
  "message_logistics_team",
  "message_customer",
  "create_internal_note",
] as const;

export interface Supervisor {
  id: string;
  name: string;
  base_instruction: string;
  available_actions: string[];
  default_wake_behavior: Record<string, unknown>;
  model_config: Record<string, unknown>;
  wake_aggressiveness: string;
  created_at: string | null;
}

export interface Run {
  id: string;
  supervisor_id: string;
  order_id: string;
  workflow_id: string;
  status: string;
  order_context: Record<string, unknown>;
  next_wake_at: string | null;
  sleep_state: string;
  final_output: Record<string, unknown> | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface ActivityEntry {
  id: string;
  run_id: string;
  ts: string | null;
  kind: string;
  payload: Record<string, unknown>;
}

export interface Memory {
  rolling_summary: string;
  important_events: string[];
  updated_at: string | null;
}

export interface RunDetail {
  run: Run;
  memory: Memory;
  activities: ActivityEntry[];
  live_state: Record<string, unknown> | null;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listSupervisors: () => req<Supervisor[]>("/api/supervisors"),
  createSupervisor: (body: Partial<Supervisor>) =>
    req<Supervisor>("/api/supervisors", { method: "POST", body: JSON.stringify(body) }),

  listRuns: () => req<Run[]>("/api/runs"),
  createRun: (body: {
    supervisor_id: string;
    order_id: string;
    order_context?: Record<string, unknown>;
    time_scale?: number;
    max_age_hours?: number;
    default_wake_hours?: number;
    wake_aggressiveness?: string;
  }) => req<Run>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  getRun: (id: string) => req<RunDetail>(`/api/runs/${id}`),

  injectEvent: (id: string, type: string, data: Record<string, unknown> = {}) =>
    req(`/api/runs/${id}/events`, { method: "POST", body: JSON.stringify({ type, data }) }),
  addInstruction: (id: string, text: string) =>
    req(`/api/runs/${id}/instructions`, { method: "POST", body: JSON.stringify({ text }) }),
  interrupt: (id: string, note?: string) =>
    req(`/api/runs/${id}/interrupt`, { method: "POST", body: JSON.stringify({ note }) }),
  pause: (id: string) => req(`/api/runs/${id}/pause`, { method: "POST", body: "{}" }),
  resume: (id: string) => req(`/api/runs/${id}/resume`, { method: "POST", body: "{}" }),
  terminate: (id: string, reason = "manual_termination", hard = false) =>
    req(`/api/runs/${id}/terminate`, { method: "POST", body: JSON.stringify({ reason, hard }) }),
};
