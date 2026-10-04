// Mirrors the Pydantic models in apps/api/app/models. Every analytical number
// rendered in the UI comes from these structured responses.

export type RiskLevel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type ApprovalStatus = "APPROVED" | "VALIDATION_REQUIRED" | "NOT_APPROVED" | "NONE";
export type EventType =
  | "COMPONENT_EOL"
  | "SUPPLIER_PRICE_INCREASE"
  | "MATERIAL_PRICE_CHANGE"
  | "FREIGHT_CHANGE"
  | "OTHER";

export interface ChangeEvent {
  event_id: string;
  event_type: EventType;
  title: string;
  summary: string;
  supplier_id: string | null;
  supplier_name: string | null;
  affected_item_id: string | null;
  affected_item_name: string | null;
  event_date: string;
  last_time_buy_date: string | null;
  last_ship_date: string | null;
  recommended_alternative_item_id: string | null;
  source: "seed" | "demo" | "upload" | "manual";
  source_document_name: string | null;
  extraction_method: string | null;
  status: "NEW" | "ANALYZED" | "MONITORING";
  created_at: string;
  analyzable: boolean;
  latest_analysis_id: string | null;
  latest_scenario_id: string | null;
}

export interface EventCreate {
  event_type: EventType;
  supplier_name?: string | null;
  part_id: string;
  last_time_buy_date?: string | null;
  last_ship_date?: string | null;
  recommended_alternative_part_id?: string | null;
  source?: ChangeEvent["source"];
  source_document_name?: string | null;
  extraction_method?: string | null;
}

export interface BomPath {
  product_id: string;
  nodes: string[];
  edge_qtys: number[];
  path_qty: number;
}

export interface CostBreakdown {
  purchase: number;
  material: number;
  freight: number;
  processing: number;
  total: number;
}

export interface AlternativeApproval {
  part_id: string;
  approval_status: ApprovalStatus;
  qualification_lead_time_days: number;
  notes: string;
}

export interface ProductImpact {
  product_id: string;
  name: string;
  product_family: string;
  effective_component_qty: number;
  paths_to_component: number;
  selling_price: number;
  unit_cost: number;
  current_margin: number;
  cost_breakdown: CostBreakdown;
  component_cost_share: number;
  horizon_forecast_qty: number;
  horizon_open_order_qty: number;
  revenue_exposure: number;
  component_requirement: number;
  finished_goods_available: number;
  finished_goods_days: number;
  inventory_coverage_days: number;
  alternative: AlternativeApproval | null;
  replacement_unit_cost_delta: number | null;
  replacement_margin: number | null;
  risk_level: RiskLevel;
  risk_reasons: string[];
}

export interface ImpactSummary {
  affected_product_count: number;
  product_family_count: number;
  product_families: string[];
  revenue_exposure: number;
  horizon_months: number;
  horizon_start: string;
  horizon_days: number;
  inventory_coverage_days: number;
  component_available_qty: number;
  component_daily_requirement: number;
  component_horizon_requirement: number;
  products_without_approved_alternative: number;
  margin_threshold: number;
  products_below_margin_threshold: number;
  average_current_margin: number;
  replacement_part_id: string | null;
  replacement_gross_profit_at_risk: number | null;
  risk_counts: Record<RiskLevel, number>;
}

export interface AlternativeComparison {
  part_id: string;
  name: string;
  supplier_name: string | null;
  unit_price: number | null;
  unit_price_delta_pct: number | null;
  lead_time_days: number | null;
  default_approval: ApprovalStatus;
  approved_products: number;
  validation_required_products: number;
  not_approved_products: number;
  max_qualification_lead_time_days: number;
  average_unit_cost_delta: number;
  average_margin_delta_points: number;
  products_below_margin_threshold: number;
  recommended: boolean;
}

export interface ComponentInfo {
  part_id: string;
  name: string;
  status: string;
  supplier_id: string | null;
  supplier_name: string | null;
  unit_price: number | null;
  unit_cost: number;
  lead_time_days: number | null;
  shipping_lane_id: string | null;
  available_qty: number;
}

export type GraphNodeData = {
  id: string;
  label: string;
  item_type: "FINISHED_GOOD" | "ASSEMBLY" | "COMPONENT";
  depth: number;
  risk_level: RiskLevel | null;
  effective_component_qty: number | null;
  status: string | null;
};

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  qty_per_parent: number;
}

export interface ImpactAnalysis {
  analysis_id: string;
  event_id: string | null;
  generated_at: string;
  as_of_date: string;
  data_source: string;
  trace_method: string;
  component: ComponentInfo;
  summary: ImpactSummary;
  products: ProductImpact[];
  paths: BomPath[];
  alternatives: AlternativeComparison[];
  graph: { nodes: GraphNodeData[]; edges: GraphEdgeData[] };
}

export interface ScenarioRequest {
  event_id?: string | null;
  part_id?: string | null;
  replacement_part_id?: string | null;
  commodity_adjustments: Record<string, number>;
  freight_adjustments: Record<string, number>;
  margin_threshold: number;
  name?: string | null;
}

export interface DeltaBreakdown {
  component_replacement: number;
  material: number;
  freight: number;
}

export interface ScenarioProduct {
  product_id: string;
  name: string;
  product_family: string;
  effective_component_qty: number;
  selling_price: number;
  current_unit_cost: number;
  scenario_unit_cost: number;
  unit_cost_delta: number;
  delta_breakdown: DeltaBreakdown;
  current_margin: number;
  scenario_margin: number;
  margin_delta_points: number;
  below_threshold: boolean;
  crosses_threshold: boolean;
  horizon_forecast_qty: number;
  revenue_exposure: number;
  gross_profit_impact: number;
  replacement_approval: ApprovalStatus | null;
  risk_level: RiskLevel;
  risk_reasons: string[];
}

export interface ScenarioSummary {
  product_count: number;
  average_current_unit_cost: number;
  average_scenario_unit_cost: number;
  average_unit_cost_delta: number;
  average_margin_delta_points: number;
  average_current_margin: number;
  average_scenario_margin: number;
  current_products_below_threshold: number;
  products_below_margin_threshold: number;
  products_newly_below_threshold: number;
  revenue_at_risk: number;
  total_revenue_exposure: number;
  gross_profit_impact: number;
  driver_average_delta: DeltaBreakdown;
  horizon_months: number;
}

export interface ScenarioResult {
  scenario_id: string;
  event_id: string | null;
  name: string;
  created_at: string;
  part_id: string;
  inputs: ScenarioRequest;
  summary: ScenarioSummary;
  products: ScenarioProduct[];
}

export interface Reference {
  materials: { material_code: string; price_per_kg: number; currency: string }[];
  shipping_lanes: {
    shipping_lane_id: string;
    origin: string;
    destination: string;
    mode: string;
    freight_rate_per_kg: number;
  }[];
  as_of_date: string;
  default_margin_threshold: number;
  horizon_months: number;
}

export interface Health {
  status: string;
  app_env: string;
  data_backend: string;
  gemini_configured: boolean;
  gemini_model: string;
}

export interface DataSummary {
  data_source: string;
  as_of_date: string;
  tables: { name: string; rows: number; columns: string[] }[];
}

export interface TablePage {
  name: string;
  columns: string[];
  total: number;
  rows: Record<string, unknown>[];
}

export interface NoticeValidation {
  part_found: boolean;
  part_name: string | null;
  part_status: string | null;
  supplier_name: string | null;
  supplier_matches: boolean;
  alternative_found: boolean;
  alternative_name: string | null;
  warnings: string[];
}

export interface ParsedNotice {
  fields: EventCreate;
  reason: string | null;
  confidence: number | null;
  extraction_method: "gemini" | "rules";
  model: string | null;
  fallback_reason: string | null;
  document_name: string | null;
  validation: NoticeValidation;
}

export interface Grounding {
  verified: boolean;
  unverified_values: string[];
}

export interface AssistantAnswer {
  answer: string;
  method: "adk_gemini" | "deterministic";
  model: string | null;
  tool_calls: { name: string; args: Record<string, unknown> }[];
  scenario_id: string | null;
  grounding: Grounding;
  notice: string | null;
}

export interface Explanation {
  text: string;
  method: "gemini" | "deterministic";
  model: string | null;
  grounding: Grounding;
}

export type Department = "Procurement" | "Engineering" | "Operations" | "Finance" | "Sales / Product";
export type ActionStatus = "PROPOSED" | "ACCEPTED" | "IN_PROGRESS" | "DONE";

export interface Action {
  action_id: string;
  event_id: string;
  department: Department;
  priority: "HIGH" | "MEDIUM" | "LOW";
  title: string;
  reason: string;
  facts: string[];
  related_products: string[];
  owner: string;
  status: ActionStatus;
  rule: string;
}

export interface ActionPlan {
  event_id: string;
  scenario_id: string | null;
  scenario_name: string;
  summary: string;
  method: "gemini" | "deterministic";
  model: string | null;
  generated_at: string;
  grounding: Grounding;
  actions: Action[];
}

export interface ActionsSummary {
  total: number;
  open: number;
  by_status: Record<string, number>;
}

export interface EventFormOptions {
  suppliers: { supplier_id: string; supplier_name: string; country: string }[];
  parts: { part_id: string; part_name: string; supplier_name: string | null; status: string }[];
  alternates: { source_part_id: string; alternative_part_id: string; approval_status: ApprovalStatus }[];
}

// -- sourcing ---------------------------------------------------------------

export type SourcingTier = "PREFERRED" | "VIABLE" | "BRIDGE_ONLY" | "NOT_RECOMMENDED" | "BLOCKED";

export interface SourcingCandidate {
  candidate_id: string;
  part_id: string;
  manufacturer: string;
  supplier_id: string;
  supplier_name: string;
  country: string;
  source: "INTERNAL_AVL" | "DISTRIBUTOR_CATALOG";
  channel: "MANUFACTURER" | "AUTHORIZED" | "BROKER" | "FACTORY_DIRECT";
  match_type: string;
  pin_compatible: boolean;
  is_new_supplier: boolean;
  approval_status: string;
  products_approved: number;
  products_needing_validation: string[];
  qualification_lead_time_days: number;
  unit_price: number;
  price_delta_pct: number;
  lead_time_days: number;
  available_stock: number | null;
  notes: string;
}

export interface SourcingResult {
  event_id: string | null;
  part_id: string;
  part_name: string;
  current_supplier: string | null;
  current_unit_price: number;
  affected_products: number;
  catalog_provider: string;
  candidates: SourcingCandidate[];
}

export interface ScoreComponent {
  criterion: string;
  weight: number;
  score: number;
  evidence: string;
}

export interface Scorecard {
  candidate_id: string;
  part_id: string;
  supplier_name: string;
  total_score: number;
  tier: SourcingTier;
  components: ScoreComponent[];
  flags: string[];
}

export interface NewsItem {
  date: string;
  category: string;
  severity: string;
  source: string;
  headline: string;
  summary: string;
}

export interface SanctionsHit {
  entity_id: string;
  listed_name: string;
  list_name: string;
  program: string;
  listed_on: string;
}

export interface SupplierEvidence {
  supplier_id: string;
  supplier_name: string;
  performance: {
    quarters: number;
    on_time_delivery_rate: number;
    quality_ppm: number;
    avg_lead_time_days: number;
    lead_time_variance_days: number;
    on_time_trend_points: number;
  } | null;
  sanctions_screened: boolean;
  sanctions_hits: SanctionsHit[];
  news: NewsItem[];
}

export interface SupplierAssessment {
  event_id: string | null;
  part_id: string;
  weights: Record<string, number>;
  evidence: SupplierEvidence[];
  scorecards: Scorecard[];
  recommended_candidate_id: string | null;
  second_source_candidate_id: string | null;
  bridge_candidate_id: string | null;
  blocked_candidate_ids: string[];
  providers: Record<string, string>;
}

export interface SourcingView {
  sourcing: SourcingResult;
  assessment: SupplierAssessment;
}

// -- planning ---------------------------------------------------------------

export interface ForecastPoint {
  month: string;
  plan_qty: number;
  forecast_qty: number;
  lower: number;
  upper: number;
}

export interface ProductForecast {
  product_id: string;
  name: string;
  history: { month: string; qty: number }[];
  points: ForecastPoint[];
  plan_total: number;
  forecast_total: number;
  delta_pct: number;
}

export interface DemandForecast {
  method: "bigquery_timesfm" | "seasonal_trend";
  model: string;
  horizon_months: number;
  confidence_level: number;
  products: ProductForecast[];
  notice: string | null;
}

export interface MaterialWeek {
  week: string;
  requirement: number;
  requirement_forecast: number;
  projected_available: number;
  projected_available_forecast: number;
}

export interface MaterialPlan {
  part_id: string;
  available_qty: number;
  weeks: MaterialWeek[];
  total_requirement: number;
  stockout_week: string | null;
  stockout_week_forecast: string | null;
  products: Record<string, number>;
}

export interface PlanKpis {
  demand_units: number;
  built_units: number;
  unmet_units: number;
  fill_rate: number;
  affected_fill_rate: number;
  strategic_fill_rate: number;
  late_unit_weeks: number;
  gross_margin: number;
  bridge_premium: number;
  component_used: number;
  component_supply: number;
  component_remaining: number;
  alternative_used: number;
}

export interface LineWeekLoad {
  line_id: string;
  week: string;
  capacity_hours: number;
  planned_hours: number;
  utilization: number;
}

export interface ProductPlanRow {
  product_id: string;
  name: string;
  affected: boolean;
  strategic: boolean;
  primary_line: string;
  demand: number;
  baseline_built: number;
  built: number;
  built_with_original: number;
  built_with_alternative: number;
  built_on_alternate_line: number;
  unmet: number;
  alternative_from_week: string | null;
  unit_margin_original: number;
  unit_margin_alternative: number | null;
}

export interface PlanChange {
  kind: "SWITCH_COMPONENT" | "RESERVE_STOCK" | "MOVE_LINE" | "UNMET_DEMAND" | "BRIDGE_BUY";
  product_ids: string[];
  units: number;
  description: string;
}

export type PlanStatus = "DRAFT" | "PROPOSED" | "APPROVED" | "REJECTED";

export interface ProductionPlan {
  plan_id: string;
  event_id: string | null;
  label: string;
  weeks: string[];
  inputs: {
    part_id: string;
    alternative_part_id: string | null;
    bridge_buy_qty: number;
    bridge_arrival_week: string | null;
    component_on_hand: number;
    alternative_early_supply: number;
    alternative_lead_time_weeks: number;
  };
  solver: {
    name: string;
    status: string;
    objective: number;
    variables: number;
    constraints: number;
    solve_ms: number;
    gap_limit: number;
  };
  baseline: PlanKpis;
  optimized: PlanKpis;
  products: ProductPlanRow[];
  schedule: { product_id: string; line_id: string; week: string; qty: number; alternative_qty: number }[];
  line_loads: LineWeekLoad[];
  baseline_line_loads: LineWeekLoad[];
  lines: Record<string, string>;
  changes: PlanChange[];
  status: PlanStatus;
  proposal_note: string | null;
  decided_by: string | null;
  decided_at: string | null;
}

export interface PlanningView {
  forecast: DemandForecast;
  materials: MaterialPlan;
  plans: ProductionPlan[];
  proposed_plan_id: string | null;
}

// -- multi-agent workflow ---------------------------------------------------

export interface AgentNode {
  name: string;
  label: string;
  kind: "sequential" | "parallel" | "llm";
  description: string;
  tools: string[];
  children: AgentNode[];
}

export type StepType =
  | "run_started"
  | "agent_started"
  | "tool_call"
  | "tool_result"
  | "agent_finished"
  | "run_finished"
  | "error";

export interface AgentStep {
  seq: number;
  type: StepType;
  agent: string | null;
  tool: string | null;
  args: Record<string, unknown> | null;
  summary: string | null;
  text: string | null;
  at_ms: number;
}

export interface AgentFinding {
  agent: string;
  label: string;
  text: string;
  method: "adk_gemini" | "deterministic";
  grounded: boolean;
  unverified_values: string[];
}

export interface WorkflowRun {
  run_id: string;
  event_id: string;
  mode: "adk_gemini" | "deterministic";
  model: string | null;
  status: "RUNNING" | "COMPLETED" | "FAILED";
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  tree: AgentNode;
  steps: AgentStep[];
  findings: AgentFinding[];
  analysis_id: string | null;
  proposed_plan_id: string | null;
  notice: string | null;
  error: string | null;
}
