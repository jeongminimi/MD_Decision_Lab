const base = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, init);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : "요청을 처리하지 못했습니다.");
  }
  return response.json() as Promise<T>;
}

export interface WorkDataset {
  id: number; name: string; kind: "hm" | "company"; start_date: string; end_date: string;
  source_note: string; complete_calendar: boolean;
}

export interface WorkProduct {
  sku: string; name: string; category: string; section: string; image_ref: string | null;
  lifecycle: string | null; units_7d: number; units_14d: number; prior_14d: number;
  units_30d: number; prior_30d: number; year_ago_30d: number | null;
  channel_units_30d: Record<string, number>;
  observed_revenue_30d: number | null; observed_gross_profit_30d: number | null;
  stock_on_hand: number | null; inbound_units: number | null; lead_time_days: number | null;
  unit_price_krw: number | null; unit_cost_krw: number | null; reorderable: boolean | null;
  input_source: string | null; input_as_of_date: string | null; days_of_cover: number | null;
  risk: string; reason: string; action: string;
}

export interface WorkAnalysis {
  dataset: Pick<WorkDataset, "id" | "name" | "kind" | "source_note" | "complete_calendar">;
  as_of_date: string; chart_start: string; sections: string[]; products: WorkProduct[];
  daily_chart: { date: string; units: number }[];
  summary: { total_products: number; attention_count: number; units_30d: number };
}

export interface WorkComparison {
  sku: string; dataset_kind: string; source: string; discount_pct: number;
  expected_units_30d: number; purchase_units: number; available_units: number;
  proposed_unit_price_krw: number; feasible: boolean; estimated_revenue_krw: number | null;
  estimated_gross_profit_krw: number | null; estimated_remaining_units: number | null; note: string;
}

export interface WorkDecision {
  id: number; sku: string; name: string; as_of_date: string; action: string;
  rationale: string; observed_units_14d: number; discount_pct: number | null;
  expected_units_30d: number | null; purchase_units: number | null;
  assumed_stock: number | null; estimated_gross_profit_krw: number | null;
  executed_at: string | null; created_at: string;
}

export interface WorkInputs {
  as_of_date: string; stock_on_hand: number | null; inbound_units: number | null;
  lead_time_days: number | null; unit_price_krw: number | null;
  unit_cost_krw: number | null; reorderable: boolean | null; lifecycle: string | null;
}

export interface WorkOption {
  dataset_id: number; sku: string; as_of_date: string; discount_pct: number;
  expected_units_30d: number; purchase_units: number;
}

export const workApi = {
  datasets: () => call<WorkDataset[]>("/api/work/datasets"),
  analysis: (id: number, asOf?: string, section?: string, start?: string) => {
    const query = new URLSearchParams({ dataset_id: String(id) });
    if (asOf) query.set("as_of", asOf);
    if (section) query.set("section", section);
    if (start) query.set("chart_start", start);
    return call<WorkAnalysis>(`/api/work/analysis?${query}`);
  },
  upload: (name: string, snapshotDate: string, complete: boolean, products: File, sales: File) => {
    const body = new FormData();
    body.set("name", name); body.set("snapshot_date", snapshotDate);
    body.set("complete_calendar", String(complete));
    body.set("products_file", products); body.set("sales_file", sales);
    return call<{ id: number; product_count: number; daily_rows: number }>("/api/work/datasets/upload", { method: "POST", body });
  },
  appendSales: (id: number, file: File, complete: boolean) => {
    const body = new FormData(); body.set("sales_file", file); body.set("complete_calendar", String(complete));
    return call<{ updated: number; end_date: string; complete_calendar: boolean }>(
      `/api/work/datasets/${id}/sales/import`, { method: "POST", body });
  },
  updateInputs: (id: number, sku: string, body: WorkInputs) => call<{ sku: string }>(
    `/api/work/datasets/${id}/products/${encodeURIComponent(sku)}/inputs`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),
  compare: (body: WorkOption) => call<WorkComparison>("/api/work/compare", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }),
  decisions: (id: number) => call<WorkDecision[]>(`/api/work/datasets/${id}/decisions`),
  saveDecision: (body: WorkOption & { action: string; rationale: string }) => call<{ id: number; saved: boolean }>(
    "/api/work/decisions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  execute: (id: number, date: string) => call<{ id: number; executed_at: string }>(
    `/api/work/decisions/${id}/execute`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ executed_at: date }) }),
  outcome: (id: number) => call<{ status: string; note: string; before_units_7d?: number; after_units_7d?: number }>(
    `/api/work/decisions/${id}/outcome`),
};

export interface SimScenario {
  id: number; dataset_id: number; name: string; as_of_date: string; ledger_start: string; ledger_end: string;
  source_note: string; bias_note: string; shortfall_note: string;
  sources: { sales: string; conditions: string; results: string };
}

export interface SimProduct {
  product_id: number; sku: string; name: string; section: string; category: string; image_ref: string | null;
  observed: { units_7d: number; units_14d: number; prior_14d: number; units_30d: number; prior_30d: number;
    first_sale_date: string | null; source: string };
  conditions: { stock_on_hand: number; planned_inbound_after_as_of: number; planned_inbound_30d: number;
    lead_time_days: number; reorderable: boolean; reorder_stop_date: string | null; scenario_lifecycle: string;
    lifecycle_label: string; list_price_krw: number; selling_price_krw: number; unit_cost_krw: number; source: string };
  signal: { risk: string; reason: string; action: string; days_of_cover: number | null;
    simulated_revenue_30d_krw: number; simulated_gross_profit_30d_krw: number; source: string };
  post_as_of: { start: string; end: string; observed_units: number; supplied_units: number;
    policy_shortfall_units: number; first_shortfall_date: string | null; closing_stock: number };
}

export interface SimAnalysis {
  scenario: SimScenario; as_of_date: string; products: SimProduct[];
  summary: { total_products: number; risk_counts: Record<string, number>; attention_count: number;
    units_30d: number; simulated_gross_profit_30d_krw: number };
  post_as_of_summary: { start: string; end: string; observed_units: number; supplied_units: number;
    policy_shortfall_units: number; products_with_shortfall: number; note: string };
}

export interface SimProductDetail extends SimProduct {
  scenario: SimScenario;
  policy: { selection_reason: string; assumption_reason: string };
  ledger: { date: string; period: "as_of_window" | "post_as_of_observed"; opening_stock: number; inbound_units: number;
    observed_units: number; supplied_units: number; policy_shortfall_units: number; closing_stock: number }[];
  planned_orders: { po_code: string; order_date: string; expected_receipt_date: string; actual_receipt_date: string | null;
    ordered_units: number; received_units: number; status: string; timing: string; assumption_reason: string }[];
  prices: { valid_from: string; valid_to: string; list_price_krw: number; selling_price_krw: number;
    unit_cost_krw: number; price_tier_rule: string; cost_rule: string }[];
}

export interface SimComparison {
  sku: string; as_of_date: string; discount_pct: number; expected_units_30d: number; purchase_units: number;
  purchase_arrival_date: string | null; purchase_counted_in_30d: boolean | null; available_units_30d: number;
  proposed_unit_price_krw: number; unit_cost_krw: number; feasible: boolean; estimated_revenue_krw: number | null;
  estimated_gross_profit_krw: number | null; estimated_remaining_units: number | null; source: string; note: string;
}

export interface SimDecision {
  id: number; sku: string; name: string; as_of_date: string; action: string; rationale: string; created_at: string;
  snapshot: { scenario: { id: number; name: string; as_of_date: string };
    observed: SimProduct["observed"]; conditions: SimProduct["conditions"]; signal: SimProduct["signal"];
    comparison: SimComparison; bias_note: string };
}

export interface SimOption { scenario_id: number; sku: string; discount_pct: number; expected_units_30d: number; purchase_units: number }

const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const simApi = {
  scenarios: (datasetId: number) => call<SimScenario[]>(`/api/work/sim/scenarios?dataset_id=${datasetId}`),
  importSample: (datasetId: number) => call<SimScenario>(`/api/work/sim/import-sample?dataset_id=${datasetId}`, { method: "POST" }),
  analysis: (scenarioId: number) => call<SimAnalysis>(`/api/work/sim/analysis?scenario_id=${scenarioId}`),
  product: (scenarioId: number, sku: string) =>
    call<SimProductDetail>(`/api/work/sim/products/${encodeURIComponent(sku)}?scenario_id=${scenarioId}`),
  compare: (body: SimOption) => call<SimComparison>("/api/work/sim/compare", json(body)),
  decisions: (scenarioId: number) => call<SimDecision[]>(`/api/work/sim/decisions?scenario_id=${scenarioId}`),
  saveDecision: (body: SimOption & { action: string; rationale: string }) => call<SimDecision>("/api/work/sim/decisions", json(body)),
};
