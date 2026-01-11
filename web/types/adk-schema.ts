/**
 * TypeScript type definitions for SRE Agent data structures.
 * These types mirror the Pydantic schemas from the backend.
 */

// =============================================================================
// Enums
// =============================================================================

export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type Confidence = "high" | "medium" | "low";
export type ToolStatus = "success" | "error" | "partial";
export type OverallAssessment = "healthy" | "degraded" | "critical";
export type ChangeType = "added" | "removed" | "modified" | "depth_change" | "fanout_change";
export type EffectType = "root_cause" | "direct_effect" | "cascaded_effect";
export type ImpactType = "latency" | "error_rate" | "throughput" | "availability";

// =============================================================================
// Base Types
// =============================================================================

export interface BaseToolResponse<T = unknown> {
  status: ToolStatus;
  result?: T;
  error?: string;
  metadata: Record<string, unknown>;
}

// =============================================================================
// Trace Types
// =============================================================================

export interface SpanInfo {
  span_id: string;
  name: string;
  duration_ms?: number;
  parent_span_id?: string | null;
  has_error: boolean;
  labels: Record<string, string>;
  start_time?: string;
  end_time?: string;
  service_name?: string;
  status_code?: number | string;
}

export interface Trace {
  trace_id: string;
  project_id?: string;
  spans: SpanInfo[];
  start_time: string;
  end_time: string;
  total_duration_ms: number;
  root_span_id?: string;
}

export interface TraceSummary {
  trace_id: string;
  span_count: number;
  total_duration_ms: number;
  error_count: number;
  max_depth: number;
}

export interface LatencyDiff {
  span_name: string;
  baseline_ms: number;
  target_ms: number;
  diff_ms: number;
  diff_percent: number;
  severity: Severity;
}

export interface ErrorDiff {
  span_name: string;
  error_type: string;
  error_message?: string;
  status_code?: number | string;
  is_new: boolean;
}

export interface StructureDiff {
  change_type: ChangeType;
  span_name: string;
  description: string;
}

export interface TraceComparisonReport {
  baseline_summary: TraceSummary;
  target_summary: TraceSummary;
  overall_assessment: OverallAssessment;
  latency_findings: LatencyDiff[];
  error_findings: ErrorDiff[];
  structure_findings: StructureDiff[];
  root_cause_hypothesis: string;
  recommendations: string[];
}

// =============================================================================
// Log Types
// =============================================================================

export interface LogEntry {
  timestamp: string;
  severity: string;
  payload: string;
  resource: Record<string, unknown>;
  labels?: Record<string, string>;
}

export interface LogPattern {
  pattern_id: string;
  template: string;
  count: number;
  first_seen?: string;
  last_seen?: string;
  severity_counts: Record<string, number>;
  sample_messages: string[];
  resources: string[];
}

export interface LogPatternSummary {
  total_logs_processed: number;
  unique_patterns: number;
  severity_distribution: Record<string, number>;
  compression_ratio: number;
  top_patterns: LogPattern[];
  error_patterns: LogPattern[];
}

export interface PatternComparison {
  new_patterns: LogPattern[];
  disappeared_patterns: LogPattern[];
  increased_patterns: Array<{ pattern: LogPattern; increase_pct: number }>;
  decreased_patterns: Array<{ pattern: LogPattern; decrease_pct: number }>;
  stable_patterns_count: number;
}

export interface LogComparisonResult {
  baseline_summary: {
    total_logs: number;
    unique_patterns: number;
  };
  comparison_summary: {
    total_logs: number;
    unique_patterns: number;
  };
  anomalies: PatternComparison;
  alert_level: string;
}

// =============================================================================
// Metrics Types
// =============================================================================

export interface TimeSeriesPoint {
  timestamp: string;
  value: number;
}

export interface TimeSeries {
  metric: Record<string, unknown>;
  resource: Record<string, unknown>;
  points: TimeSeriesPoint[];
  metric_name?: string;
}

export interface Anomaly {
  timestamp: string;
  value: number;
  expected_value?: number;
  deviation?: number;
  severity: Severity;
  description?: string;
}

export interface MetricWithAnomalies {
  series: TimeSeries;
  anomalies: Anomaly[];
  incident_window?: {
    start: string;
    end: string;
  };
}

export interface LatencyDistribution {
  sample_size: number;
  mean_ms: number;
  median_ms: number;
  p90_ms: number;
  p95_ms: number;
  p99_ms: number;
  std_dev_ms: number;
  coefficient_of_variation: number;
}

// =============================================================================
// Analysis Types
// =============================================================================

export interface AnomalyFinding {
  span_name: string;
  observed_ms: number;
  expected_ms: number;
  z_score: number;
  severity: Severity;
}

export interface CriticalPathSegment {
  span_name: string;
  duration_ms: number;
  percentage_of_total: number;
  is_optimization_target: boolean;
}

export interface StatisticalAnalysisReport {
  latency_distribution: LatencyDistribution;
  anomaly_threshold: number;
  anomalies: AnomalyFinding[];
  critical_path: CriticalPathSegment[];
  optimization_opportunities: string[];
}

export interface RootCauseCandidate {
  rank: number;
  span_name: string;
  slowdown_ms: number;
  confidence: Confidence;
  reasoning: string;
}

export interface CausalChainLink {
  span_name: string;
  effect_type: EffectType;
  latency_contribution_ms: number;
}

export interface CausalAnalysisReport {
  causal_chain: CausalChainLink[];
  root_cause_candidates: RootCauseCandidate[];
  propagation_depth: number;
  primary_root_cause: string;
  confidence: Confidence;
  conclusion: string;
  recommended_actions: string[];
}

export interface ServiceImpact {
  service_name: string;
  impact_type: ImpactType;
  severity: Severity;
  baseline_value: number;
  current_value: number;
  change_percent: number;
  affected_operations: string[];
}

export interface ServiceImpactReport {
  total_services_analyzed: number;
  impacted_services_count: number;
  service_impacts: ServiceImpact[];
  cross_service_effects: string[];
  blast_radius_assessment: string;
}

// =============================================================================
// Remediation Types
// =============================================================================

export interface RemediationStep {
  action: string;
  description: string;
  steps: string[];
  risk: "low" | "medium" | "high";
  effort: "low" | "medium" | "high";
  category?: string;
  source_pattern?: string;
}

export interface RemediationSuggestion {
  matched_patterns: string[];
  categories?: string[];
  finding_summary?: string;
  suggestions: RemediationStep[];
  recommended_first_action?: RemediationStep;
  quick_wins: RemediationStep[];
}

export interface GcloudCommand {
  description: string;
  command: string;
}

export interface RemediationCommands {
  remediation_type: string;
  resource: string;
  project: string;
  commands: GcloudCommand[];
  warning: string;
}

export interface RiskAssessment {
  action: string;
  service: string;
  change: string;
  risk_assessment: {
    level: "low" | "medium" | "high";
    confidence: string;
    factors: string[];
  };
  recommendations: {
    proceed: boolean;
    require_approval: boolean;
    mitigations: string[];
  };
  checklist: string[];
}

// =============================================================================
// UI State Types
// =============================================================================

export type AgentType =
  | "orchestrator"
  | "latency_specialist"
  | "error_analyst"
  | "log_pattern_engine"
  | "metrics_correlator"
  | "remediation_advisor"
  | "idle";

export interface AgentStatus {
  currentAgent: AgentType;
  message: string;
  progress?: number;
  startTime?: string;
}

export type CanvasView =
  | { type: "empty" }
  | { type: "trace"; data: Trace }
  | { type: "trace_comparison"; data: TraceComparisonReport }
  | { type: "log_patterns"; data: LogPatternSummary }
  | { type: "log_comparison"; data: LogComparisonResult }
  | { type: "metrics"; data: MetricWithAnomalies }
  | { type: "remediation"; data: RemediationSuggestion }
  | { type: "risk_assessment"; data: RiskAssessment }
  | { type: "service_impact"; data: ServiceImpactReport }
  | { type: "causal_analysis"; data: CausalAnalysisReport };

// =============================================================================
// Error Types
// =============================================================================

export interface ErrorInfo {
  span_name: string;
  error_type: string;
  status_code?: number | string;
  error_message?: string;
  service_name?: string;
}

export interface ErrorAnalysisReport {
  baseline_error_count: number;
  target_error_count: number;
  net_change: number;
  new_errors: ErrorInfo[];
  resolved_errors: ErrorInfo[];
  common_errors: ErrorInfo[];
  error_pattern_analysis: string;
  recommendations: string[];
}
