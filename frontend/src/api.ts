import type { ActionOutcome, ActionRecord, ActionType, DashboardSummary, FashionCase, FashionComparison, FashionDecision, FashionDecisionCreatePayload, FashionOptionInput, OlistComparison, OlistScenarioDetail, OlistScenarioSummary, OlistStatus, OlistTopProduct, ProductAnalysis } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "요청을 처리하지 못했습니다.");
  }
  return response.json() as Promise<T>;
}

export const api = {
  fashionStatus: () => request<{ imported: boolean; product_count: number; default_as_of_date: string; source: string }>("/api/fashion/status"),
  fashionImportSample: () => request<{ imported: boolean; product_count: number; sale_rows: number; as_of_date: string }>("/api/fashion/import-sample", { method: "POST" }),
  fashionAnalysis: () => request<FashionCase>("/api/fashion/analysis?as_of=2026-08-31"),
  fashionMarkdown: (sku: string, discountPct: number) => request<{ sku: string; discount_pct: number; current_price: number; proposed_price: number; unit_cost: number; proposed_unit_gross_margin: number; proposed_gross_margin_rate_pct: number | null; proposed_unit_markup_pct: number | null; baseline_units_30d: number; break_even_units_30d: number | null; additional_units_needed: number | null; note: string }>(`/api/fashion/markdown/${encodeURIComponent(sku)}?discount_pct=${discountPct}`),
  fashionCompareOptions: (sku: string, options: FashionOptionInput[]) => request<FashionComparison>("/api/fashion/compare-options", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sku, options }) }),
  fashionDecisions: () => request<FashionDecision[]>("/api/fashion/decisions"),
  fashionCreateDecision: (payloadOrSku: string | FashionDecisionCreatePayload, actionType?: string, rationale?: string) => {
    const body = typeof payloadOrSku === "string"
      ? { sku: payloadOrSku, action_type: actionType!, rationale: rationale! }
      : payloadOrSku;
    return request<FashionDecision>("/api/fashion/decisions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  },
  fashionUpdateProduct: (sku: string, values: { stock_on_hand: number; inbound_units: number; unit_price: number; unit_cost: number }) => request<ProductAnalysis>(`/api/fashion/products/${encodeURIComponent(sku)}/inputs`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) }),
  fashionImportSales: (file: File) => { const body = new FormData(); body.append("file", file); return request<{ updated: number; as_of_date: string }>("/api/fashion/sales/import", { method: "POST", body }); },
  dashboard: () => request<DashboardSummary>("/api/dashboard"),
  products: (q = "", risk = "all") => request<ProductAnalysis[]>(`/api/products?q=${encodeURIComponent(q)}&risk=${risk}`),
  actions: () => request<ActionRecord[]>("/api/actions"),
  createAction: (productId: number, actionType: ActionType, note: string) =>
    request<ActionRecord>("/api/actions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product_id: productId, action_type: actionType, note }) }),
  completeAction: (id: number) => request<ActionRecord>(`/api/actions/${id}/complete`, { method: "POST" }),
  actionOutcome: (id: number) => request<ActionOutcome>(`/api/actions/${id}/outcome`),
  importSales: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ imported: number; rejected: number; messages: string[] }>("/api/import/sales", { method: "POST", body });
  },
  importProducts: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ imported: number; rejected: number; messages: string[] }>("/api/import/products", { method: "POST", body });
  },
  olistStatus: () => request<OlistStatus>("/api/olist/status"),
  olistImport: () => request<OlistStatus>("/api/olist/import", { method: "POST" }),
  olistTopProducts: () => request<{ as_of_date: string; currency: "BRL"; products: OlistTopProduct[] }>("/api/olist/top-products"),
  olistScenarios: () => request<OlistScenarioSummary[]>("/api/olist/scenarios"),
  olistScenario: (id: number) => request<OlistScenarioDetail>(`/api/olist/scenarios/${id}`),
  olistCompare: (baselineId: number, candidateId: number) => request<OlistComparison>(`/api/olist/scenarios/${baselineId}/compare?against_id=${candidateId}`),
  olistImportScenario: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ scenario_id: number; name: string; product_count: number }>("/api/olist/scenarios/import", { method: "POST", body });
  },
  olistTemplate: async () => {
    const response = await fetch(`${API_BASE}/api/olist/scenario-template`);
    if (!response.ok) throw new Error("시나리오 양식을 받지 못했습니다.");
    return response.blob();
  },
  olistExport: async (id: number) => {
    const response = await fetch(`${API_BASE}/api/olist/scenarios/${id}/export.csv`);
    if (!response.ok) throw new Error("시나리오 분석 CSV를 받지 못했습니다.");
    return response.blob();
  },
};
