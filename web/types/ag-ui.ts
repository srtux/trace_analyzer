/**
 * AG-UI Protocol Types
 *
 * AG-UI (Agent-User Interaction Protocol) is an open, lightweight, event-based protocol
 * that standardizes how AI agents connect to user-facing applications.
 *
 * @see https://docs.ag-ui.com/introduction
 */

// =============================================================================
// Event Types (AG-UI Standard ~16 event types)
// =============================================================================

export type AGUIEventType =
  // Lifecycle events
  | "RUN_STARTED"
  | "RUN_FINISHED"
  | "RUN_ERROR"
  // Message events
  | "TEXT_MESSAGE_START"
  | "TEXT_MESSAGE_CONTENT"
  | "TEXT_MESSAGE_END"
  // Tool events
  | "TOOL_CALL_START"
  | "TOOL_CALL_ARGS"
  | "TOOL_CALL_END"
  // State events
  | "STATE_SNAPSHOT"
  | "STATE_DELTA"
  // Custom events
  | "CUSTOM"
  // Step events
  | "STEP_STARTED"
  | "STEP_FINISHED"
  // Raw events
  | "RAW";

// =============================================================================
// Base Event Structure
// =============================================================================

export interface BaseAGUIEvent {
  type: AGUIEventType;
  timestamp: string;
  runId: string;
  metadata?: Record<string, unknown>;
}

// =============================================================================
// Lifecycle Events
// =============================================================================

export interface RunStartedEvent extends BaseAGUIEvent {
  type: "RUN_STARTED";
  threadId?: string;
  agentName?: string;
}

export interface RunFinishedEvent extends BaseAGUIEvent {
  type: "RUN_FINISHED";
  result?: unknown;
}

export interface RunErrorEvent extends BaseAGUIEvent {
  type: "RUN_ERROR";
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

// =============================================================================
// Message Events (Text Streaming)
// =============================================================================

export interface TextMessageStartEvent extends BaseAGUIEvent {
  type: "TEXT_MESSAGE_START";
  messageId: string;
  role: "assistant" | "user" | "system";
}

export interface TextMessageContentEvent extends BaseAGUIEvent {
  type: "TEXT_MESSAGE_CONTENT";
  messageId: string;
  delta: string;
}

export interface TextMessageEndEvent extends BaseAGUIEvent {
  type: "TEXT_MESSAGE_END";
  messageId: string;
}

// =============================================================================
// Tool Call Events
// =============================================================================

export interface ToolCallStartEvent extends BaseAGUIEvent {
  type: "TOOL_CALL_START";
  toolCallId: string;
  toolName: string;
  parentToolCallId?: string;
}

export interface ToolCallArgsEvent extends BaseAGUIEvent {
  type: "TOOL_CALL_ARGS";
  toolCallId: string;
  delta?: string; // Streaming args
  args?: Record<string, unknown>; // Complete args
}

export interface ToolCallEndEvent extends BaseAGUIEvent {
  type: "TOOL_CALL_END";
  toolCallId: string;
  result?: unknown;
  error?: {
    code: string;
    message: string;
  };
}

// =============================================================================
// State Events (Shared State)
// =============================================================================

export interface StateSnapshotEvent extends BaseAGUIEvent {
  type: "STATE_SNAPSHOT";
  snapshot: Record<string, unknown>;
}

export interface StateDeltaEvent extends BaseAGUIEvent {
  type: "STATE_DELTA";
  delta: JSONPatchOperation[];
}

export interface JSONPatchOperation {
  op: "add" | "remove" | "replace" | "move" | "copy" | "test";
  path: string;
  value?: unknown;
  from?: string;
}

// =============================================================================
// Step Events (Multi-Agent Coordination)
// =============================================================================

export interface StepStartedEvent extends BaseAGUIEvent {
  type: "STEP_STARTED";
  stepId: string;
  stepName: string;
  agentName?: string;
  description?: string;
}

export interface StepFinishedEvent extends BaseAGUIEvent {
  type: "STEP_FINISHED";
  stepId: string;
  result?: unknown;
}

// =============================================================================
// Custom Event
// =============================================================================

export interface CustomEvent extends BaseAGUIEvent {
  type: "CUSTOM";
  eventName: string;
  payload: unknown;
}

// =============================================================================
// Raw Event
// =============================================================================

export interface RawEvent extends BaseAGUIEvent {
  type: "RAW";
  data: unknown;
}

// =============================================================================
// Union Type for All Events
// =============================================================================

export type AGUIEvent =
  | RunStartedEvent
  | RunFinishedEvent
  | RunErrorEvent
  | TextMessageStartEvent
  | TextMessageContentEvent
  | TextMessageEndEvent
  | ToolCallStartEvent
  | ToolCallArgsEvent
  | ToolCallEndEvent
  | StateSnapshotEvent
  | StateDeltaEvent
  | StepStartedEvent
  | StepFinishedEvent
  | CustomEvent
  | RawEvent;

// =============================================================================
// AG-UI Run State
// =============================================================================

export type RunStatus = "idle" | "running" | "completed" | "error" | "cancelled";

export interface AGUIRunState {
  runId: string | null;
  status: RunStatus;
  currentAgent: string | null;
  messages: AGUIMessage[];
  toolCalls: AGUIToolCall[];
  steps: AGUIStep[];
  sharedState: Record<string, unknown>;
  error: { code: string; message: string } | null;
}

export interface AGUIMessage {
  id: string;
  role: "assistant" | "user" | "system";
  content: string;
  timestamp: string;
  isStreaming: boolean;
}

export interface AGUIToolCall {
  id: string;
  toolName: string;
  args: Record<string, unknown>;
  result?: unknown;
  error?: { code: string; message: string };
  status: "pending" | "running" | "completed" | "error";
  startTime: string;
  endTime?: string;
  parentToolCallId?: string;
}

export interface AGUIStep {
  id: string;
  name: string;
  agentName?: string;
  description?: string;
  status: "pending" | "running" | "completed" | "error";
  startTime: string;
  endTime?: string;
  result?: unknown;
}

// =============================================================================
// SRE-Specific Tool Types
// =============================================================================

export type SREToolName =
  // Trace tools
  | "fetch_trace"
  | "list_traces"
  | "compare_span_timings"
  | "find_structural_differences"
  | "summarize_trace"
  | "analyze_critical_path"
  // Log tools
  | "list_log_entries"
  | "extract_log_patterns"
  | "compare_log_patterns"
  | "analyze_log_anomalies"
  // Metrics tools
  | "list_time_series"
  | "query_promql"
  | "detect_metric_anomalies"
  | "compare_metric_windows"
  // GKE tools
  | "get_gke_cluster_health"
  | "analyze_node_conditions"
  | "get_pod_restart_events"
  | "analyze_hpa_events"
  | "get_container_oom_events"
  | "get_workload_health_summary"
  // SLO tools
  | "list_slos"
  | "get_slo_status"
  | "analyze_error_budget_burn"
  | "get_golden_signals"
  // Remediation tools
  | "generate_remediation_suggestions"
  | "get_gcloud_commands"
  | "estimate_remediation_risk"
  // Correlation tools
  | "correlate_trace_with_metrics"
  | "correlate_trace_with_kubernetes"
  | "build_cross_signal_timeline"
  | "build_service_dependency_graph";

// =============================================================================
// Human-in-the-Loop Types
// =============================================================================

export type HITLRequestType =
  | "confirmation"
  | "approval"
  | "input"
  | "selection"
  | "escalation";

export interface HITLRequest {
  requestId: string;
  type: HITLRequestType;
  title: string;
  description: string;
  toolCallId?: string;
  options?: HITLOption[];
  inputSchema?: Record<string, unknown>;
  timeout?: number;
  defaultAction?: "approve" | "reject" | "timeout";
  riskLevel?: "low" | "medium" | "high" | "critical";
}

export interface HITLOption {
  id: string;
  label: string;
  description?: string;
  isDefault?: boolean;
  isDestructive?: boolean;
}

export interface HITLResponse {
  requestId: string;
  action: "approve" | "reject" | "modify" | "escalate";
  selectedOption?: string;
  modifiedInput?: unknown;
  reason?: string;
}
