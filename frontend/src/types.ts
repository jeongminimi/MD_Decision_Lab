export type Risk = "out_of_stock" | "data_insufficient" | "stockout_risk" | "overstock_risk" | "slow_moving" | "healthy";
export type ActionType = "replenish" | "promotion" | "live_exposure" | "content_test" | "monitor";

export interface ProductAnalysis {
  product_id: number;
  sku: string;
  name: string;
  category: string;
  season_group?: string | null;
  lifecycle_status?: string | null;
  reorderable?: boolean | null;
  launch_date?: string | null;
  event_start_date?: string | null;
  planning_note?: string | null;
  stock_on_hand: number;
  inbound_units: number;
  lead_time_days: number;
  target_cover_days: number;
  unit_price: number;
  unit_cost: number;
  units_7d: number;
  units_30d: number;
  sales_days_30d: number;
  revenue_30d: number;
  gross_margin_30d: number;
  gross_margin_rate_30d_pct: number | null;
  unit_markup_pct: number | null;
  margin_is_estimated: boolean;
  avg_daily_units: number;
  avg_daily_7d: number;
  decision_daily_units: number;
  demand_basis: "7d" | "30d" | "none";
  demand_explanation: string;
  data_warnings: string[];
  days_of_cover: number | null;
  cover_including_inbound: number | null;
  risk: Risk;
  risk_label: string;
  recommendation: string;
  recommendation_reason: string;
  suggested_replenishment_units: number | null;
}

export interface DashboardSummary {
  product_count: number;
  risk_counts: Record<Risk, number>;
  revenue_30d: number;
  gross_margin_30d: number;
  gross_margin_rate_30d_pct: number | null;
  units_30d: number;
  attention_count: number;
  demo_data: boolean;
}

export interface ActionRecord {
  id: number;
  product_id: number;
  product_name: string;
  sku: string;
  action_type: ActionType;
  note: string;
  status: string;
  stock_before: number;
  units_30d_before: number;
  revenue_30d_before: number;
  created_at: string;
}

export interface ActionOutcome {
  action_id: number;
  status: "planned" | "waiting_for_data" | "comparable";
  interpretation: string;
  action_date: string | null;
  before_period?: { start: string; end: string };
  after_period?: { start: string; end: string };
  before: { units: number; revenue: number; gross_margin: number | null } | null;
  after: { units: number; revenue: number; gross_margin: number | null } | null;
  stock_at_log: number;
  stock_now: number;
  stock_note: string;
  missing_before_days: number;
  missing_after_days: number;
}

