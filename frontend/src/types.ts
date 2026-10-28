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

export interface FashionAnalysis extends ProductAnalysis {
  prior_30d_units: number | null;
  units_change_pct: number | null;
  trend_note: string;
}

export interface FashionCase {
  as_of_date: string;
  source: string;
  currency: "KRW";
  note: string;
  products: FashionAnalysis[];
  summary_by_season: Record<string, { stock_cost_value: number; revenue_30d: number; gross_margin_30d: number; gross_margin_rate_30d_pct: number | null; margin_is_estimated: boolean; attention_count: number }>;
}

export interface FashionPlanning {
  source: string;
  as_of_date: string;
  growth_pct: number;
  target_sell_through_pct: number;
  warning: string;
  flow_summary: Array<{
    sku: string; name: string; season_group: string; opening_stock: number; receipts: number;
    customer_returns: number; removed_units: number; sold_units: number; closing_stock: number;
    sell_through_pct: number | null; reconciled_with_current_inputs: boolean; note: string;
  }>;
  plans: Array<{
    sku: string; name: string; reference_name: string; prior_available_units: number;
    prior_sold_units: number; prior_end_stock: number; prior_revenue: number;
    prior_gross_profit: number; prior_sell_through_pct: number; current_stock: number;
    inbound_units: number; current_supply: number; assumed_demand: number;
    target_supply: number; additional_order_to_review: number; planned_supply: number;
    excess_units_to_review: number; inbound_reduction_to_review: number; recommended_action: string;
    projected_sales: number; projected_end_stock: number; projected_revenue: number;
    projected_gross_profit: number; note: string;
  }>;
}

export interface FashionPlanDecision {
  id: number; sku: string; name: string; growth_pct: number;
  target_sell_through_pct: number; prior_sold_units: number;
  current_supply: number; assumed_demand: number; target_supply: number;
  additional_order_to_review: number; excess_units_to_review: number;
  rationale: string; created_at: string;
}

export interface FashionDecision {
  id: number;
  sku: string;
  as_of_date: string;
  action_type: string;
  rationale: string;
  observed_units_7d: number;
  observed_units_30d: number;
  assumed_stock_on_hand: number;
  chosen_option?: string | null;
  discount_pct?: number | null;
  expected_units_30d?: number | null;
  purchase_units?: number | null;
  estimated_revenue?: number | null;
  estimated_gross_profit?: number | null;
  estimated_remaining_stock?: number | null;
  feasible?: boolean | null;
  created_at: string;
}

export interface FashionDecisionCreatePayload {
  sku: string;
  action_type: string;
  rationale: string;
  chosen_option?: string | null;
  discount_pct?: number | null;
  expected_units_30d?: number | null;
  purchase_units?: number | null;
  estimated_revenue?: number | null;
  estimated_gross_profit?: number | null;
  estimated_remaining_stock?: number | null;
  feasible?: boolean | null;
}

export interface FashionOptionInput {
  label: string;
  discount_pct: number;
  expected_units_30d: number;
  purchase_units: number;
}

export interface FashionComparisonOption extends FashionOptionInput {
  unit_price: number;
  available_units: number;
  shortfall_units: number;
  feasible: boolean;
  estimated_revenue: number | null;
  estimated_gross_profit: number | null;
  estimated_gross_margin_rate_pct: number | null;
  estimated_remaining_stock: number | null;
  purchase_cash_required: number;
}

export interface FashionComparison {
  sku: string;
  as_of_date: string;
  observed: { units_30d: number; revenue_30d: number; gross_margin_30d: number };
  snapshot: { stock_on_hand: number; inbound_units: number; unit_price: number; unit_cost: number; reorderable: boolean };
  options: FashionComparisonOption[];
  note: string;
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

export interface OlistStatus {
  imported: boolean;
  source_revision?: string;
  period_start?: string;
  period_end?: string;
  order_count?: number;
  item_count?: number;
  product_count?: number;
  demand_definition?: string;
}

export interface OlistScenarioSummary { id: number; name: string; as_of_date: string; product_count: number; }
export interface OlistScenarioDetail extends OlistScenarioSummary {
  currency: "BRL";
  demand_source: string;
  inventory_source: string;
  margin_source: string;
  products: ProductAnalysis[];
}
export interface OlistTopProduct {
  id: number; sku: string; name: string; category: string; units_30d: number; revenue_30d: number;
}

export interface OlistComparisonSide {
  id: number; name: string;
  stockout_count: number; overstock_count: number; stock_units: number;
  stock_value: number; suggested_replenishment_units: number;
}
export interface OlistComparison {
  baseline: OlistComparisonSide;
  candidate: OlistComparisonSide;
  as_of_date: string;
  currency: "BRL";
  interpretation: string;
  products: Array<{
    sku: string; name: string; observed_units_30d: number; observed_revenue_30d: number;
    baseline_risk: Risk; candidate_risk: Risk;
    baseline_stock: number; candidate_stock: number;
    baseline_cover: number | null; candidate_cover: number | null;
    baseline_stock_value: number; candidate_stock_value: number;
    baseline_replenishment: number; candidate_replenishment: number;
  }>;
}
