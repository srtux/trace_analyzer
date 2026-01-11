/**
 * A2UI (Agent-to-User Interface) Protocol Types
 *
 * A2UI is a declarative UI protocol for agent-driven interfaces. AI agents
 * generate rich, interactive UIs that render natively across platforms
 * without executing arbitrary code.
 *
 * @see https://a2ui.org/specification/v0.8-a2ui/
 */

// =============================================================================
// Core A2UI Types
// =============================================================================

/**
 * A2UI Response - The main payload from an agent
 */
export interface A2UIResponse {
  version: "0.8";
  surface: A2UISurface;
  dataModel?: A2UIDataModel;
  actions?: A2UIAction[];
  metadata?: Record<string, unknown>;
}

/**
 * Surface - The UI structure definition
 */
export interface A2UISurface {
  id: string;
  components: A2UIComponent[];
  layout?: A2UILayout;
}

/**
 * Data Model - Dynamic values that populate the UI
 */
export interface A2UIDataModel {
  [key: string]: unknown;
}

/**
 * Layout configuration for the surface
 */
export interface A2UILayout {
  type: "stack" | "grid" | "flow" | "tabs" | "split";
  direction?: "horizontal" | "vertical";
  gap?: number;
  columns?: number;
  padding?: number;
}

// =============================================================================
// Component Types
// =============================================================================

export type A2UIComponentType =
  // Basic
  | "text"
  | "heading"
  | "button"
  | "icon"
  | "image"
  | "divider"
  | "spacer"
  // Layout
  | "container"
  | "card"
  | "accordion"
  | "tabs"
  | "modal"
  // Data Display
  | "table"
  | "list"
  | "badge"
  | "progress"
  | "stat"
  | "code"
  // Input
  | "input"
  | "select"
  | "checkbox"
  | "radio"
  | "slider"
  | "datepicker"
  // Charts (SRE-specific)
  | "line-chart"
  | "bar-chart"
  | "area-chart"
  | "pie-chart"
  | "heatmap"
  | "gauge"
  // SRE Widgets (Custom)
  | "trace-waterfall"
  | "log-viewer"
  | "metric-chart"
  | "dependency-graph"
  | "timeline"
  | "health-status"
  | "alert-panel"
  | "command-block"
  | "remediation-card";

/**
 * Base component structure
 */
export interface A2UIComponentBase {
  id: string;
  type: A2UIComponentType;
  props?: Record<string, unknown>;
  dataBinding?: string; // JSON path to data model
  children?: A2UIComponent[];
  conditionalRender?: A2UICondition;
  style?: A2UIStyle;
  events?: A2UIEventBinding[];
}

/**
 * Style properties
 */
export interface A2UIStyle {
  width?: string | number;
  height?: string | number;
  padding?: string | number;
  margin?: string | number;
  backgroundColor?: string;
  borderRadius?: string | number;
  border?: string;
  className?: string; // For Tailwind classes
}

/**
 * Conditional rendering
 */
export interface A2UICondition {
  dataPath: string;
  operator: "eq" | "ne" | "gt" | "lt" | "gte" | "lte" | "contains" | "exists";
  value?: unknown;
}

/**
 * Event bindings
 */
export interface A2UIEventBinding {
  event: "click" | "change" | "submit" | "hover";
  action: A2UIAction;
}

// =============================================================================
// Specific Component Types
// =============================================================================

export interface TextComponent extends A2UIComponentBase {
  type: "text";
  props: {
    content: string;
    variant?: "body" | "caption" | "label" | "mono";
    color?: "default" | "muted" | "accent" | "success" | "warning" | "error";
  };
}

export interface HeadingComponent extends A2UIComponentBase {
  type: "heading";
  props: {
    content: string;
    level: 1 | 2 | 3 | 4 | 5 | 6;
  };
}

export interface ButtonComponent extends A2UIComponentBase {
  type: "button";
  props: {
    label: string;
    variant?: "primary" | "secondary" | "destructive" | "ghost" | "outline";
    size?: "sm" | "md" | "lg";
    disabled?: boolean;
    loading?: boolean;
    icon?: string;
  };
}

export interface CardComponent extends A2UIComponentBase {
  type: "card";
  props: {
    title?: string;
    description?: string;
    footer?: string;
    variant?: "default" | "outlined" | "elevated";
  };
}

export interface TableComponent extends A2UIComponentBase {
  type: "table";
  props: {
    columns: TableColumn[];
    sortable?: boolean;
    filterable?: boolean;
    pagination?: boolean;
    pageSize?: number;
  };
}

export interface TableColumn {
  key: string;
  header: string;
  width?: string | number;
  align?: "left" | "center" | "right";
  sortable?: boolean;
  render?: "text" | "badge" | "progress" | "time" | "code";
}

export interface StatComponent extends A2UIComponentBase {
  type: "stat";
  props: {
    label: string;
    value: string | number;
    unit?: string;
    trend?: "up" | "down" | "stable";
    trendValue?: string;
    trendColor?: "success" | "warning" | "error";
  };
}

export interface ProgressComponent extends A2UIComponentBase {
  type: "progress";
  props: {
    value: number;
    max?: number;
    label?: string;
    showValue?: boolean;
    color?: "default" | "success" | "warning" | "error";
    size?: "sm" | "md" | "lg";
  };
}

export interface BadgeComponent extends A2UIComponentBase {
  type: "badge";
  props: {
    label: string;
    variant?: "default" | "success" | "warning" | "error" | "info";
    size?: "sm" | "md";
  };
}

export interface CodeComponent extends A2UIComponentBase {
  type: "code";
  props: {
    content: string;
    language?: string;
    showLineNumbers?: boolean;
    copyable?: boolean;
    maxHeight?: string | number;
  };
}

// =============================================================================
// SRE-Specific Widget Components
// =============================================================================

export interface TraceWaterfallComponent extends A2UIComponentBase {
  type: "trace-waterfall";
  props: {
    traceId: string;
    showTimeline?: boolean;
    showSpanDetails?: boolean;
    highlightErrors?: boolean;
    highlightSlow?: boolean;
    slowThresholdMs?: number;
  };
}

export interface LogViewerComponent extends A2UIComponentBase {
  type: "log-viewer";
  props: {
    filter?: string;
    showTimestamps?: boolean;
    showSeverity?: boolean;
    highlightPatterns?: string[];
    maxLines?: number;
    autoScroll?: boolean;
  };
}

export interface MetricChartComponent extends A2UIComponentBase {
  type: "metric-chart";
  props: {
    metricName: string;
    chartType: "line" | "area" | "bar";
    showAnomalies?: boolean;
    showThreshold?: boolean;
    thresholdValue?: number;
    timeRange?: string;
    refreshInterval?: number;
  };
}

export interface DependencyGraphComponent extends A2UIComponentBase {
  type: "dependency-graph";
  props: {
    services: string[];
    layout?: "dagre" | "force" | "hierarchical";
    showLatency?: boolean;
    showErrorRate?: boolean;
    highlightCriticalPath?: boolean;
  };
}

export interface TimelineComponent extends A2UIComponentBase {
  type: "timeline";
  props: {
    events: TimelineEvent[];
    orientation?: "horizontal" | "vertical";
    showConnectors?: boolean;
  };
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  title: string;
  description?: string;
  type: "trace" | "log" | "metric" | "alert" | "deployment" | "incident";
  severity?: "info" | "warning" | "error" | "critical";
}

export interface HealthStatusComponent extends A2UIComponentBase {
  type: "health-status";
  props: {
    service: string;
    status: "healthy" | "degraded" | "unhealthy" | "unknown";
    metrics?: HealthMetric[];
    showDetails?: boolean;
  };
}

export interface HealthMetric {
  name: string;
  value: number | string;
  status: "good" | "warning" | "critical";
  threshold?: number;
}

export interface AlertPanelComponent extends A2UIComponentBase {
  type: "alert-panel";
  props: {
    alerts: Alert[];
    sortBy?: "time" | "severity";
    showAcknowledged?: boolean;
    groupBy?: "service" | "severity" | "type";
  };
}

export interface Alert {
  id: string;
  title: string;
  description: string;
  severity: "info" | "warning" | "error" | "critical";
  service?: string;
  timestamp: string;
  acknowledged?: boolean;
  link?: string;
}

export interface CommandBlockComponent extends A2UIComponentBase {
  type: "command-block";
  props: {
    commands: Command[];
    showCopyButton?: boolean;
    showRunButton?: boolean;
    collapsible?: boolean;
  };
}

export interface Command {
  description: string;
  command: string;
  dangerous?: boolean;
}

export interface RemediationCardComponent extends A2UIComponentBase {
  type: "remediation-card";
  props: {
    action: string;
    description: string;
    steps: string[];
    risk: "low" | "medium" | "high";
    effort: "low" | "medium" | "high";
    requiresApproval?: boolean;
  };
}

// =============================================================================
// Chart Components
// =============================================================================

export interface LineChartComponent extends A2UIComponentBase {
  type: "line-chart";
  props: {
    xAxisKey: string;
    yAxisKey: string;
    series?: ChartSeries[];
    showGrid?: boolean;
    showTooltip?: boolean;
    showLegend?: boolean;
    yAxisDomain?: [number, number];
    annotations?: ChartAnnotation[];
  };
}

export interface ChartSeries {
  name: string;
  dataKey: string;
  color?: string;
  type?: "line" | "area" | "bar";
  strokeDasharray?: string;
}

export interface ChartAnnotation {
  type: "line" | "area" | "dot";
  value?: number;
  range?: [number, number];
  label?: string;
  color?: string;
}

export interface GaugeComponent extends A2UIComponentBase {
  type: "gauge";
  props: {
    value: number;
    min?: number;
    max?: number;
    thresholds?: GaugeThreshold[];
    label?: string;
    unit?: string;
    size?: "sm" | "md" | "lg";
  };
}

export interface GaugeThreshold {
  value: number;
  color: string;
  label?: string;
}

export interface HeatmapComponent extends A2UIComponentBase {
  type: "heatmap";
  props: {
    xLabels: string[];
    yLabels: string[];
    colorScale?: string[];
    showValues?: boolean;
    cellSize?: number;
  };
}

// =============================================================================
// Union Type for All Components
// =============================================================================

export type A2UIComponent =
  | TextComponent
  | HeadingComponent
  | ButtonComponent
  | CardComponent
  | TableComponent
  | StatComponent
  | ProgressComponent
  | BadgeComponent
  | CodeComponent
  | TraceWaterfallComponent
  | LogViewerComponent
  | MetricChartComponent
  | DependencyGraphComponent
  | TimelineComponent
  | HealthStatusComponent
  | AlertPanelComponent
  | CommandBlockComponent
  | RemediationCardComponent
  | LineChartComponent
  | GaugeComponent
  | HeatmapComponent
  | A2UIComponentBase;

// =============================================================================
// Actions
// =============================================================================

export type A2UIActionType =
  | "navigate"
  | "submit"
  | "apiCall"
  | "updateState"
  | "showModal"
  | "closeModal"
  | "copyToClipboard"
  | "executeCommand"
  | "requestApproval";

export interface A2UIAction {
  type: A2UIActionType;
  payload: Record<string, unknown>;
  confirm?: {
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    destructive?: boolean;
  };
}

// =============================================================================
// Surface Updates (Incremental UI)
// =============================================================================

export type SurfaceUpdateType =
  | "add"
  | "remove"
  | "replace"
  | "update";

export interface SurfaceUpdate {
  type: SurfaceUpdateType;
  componentId: string;
  parentId?: string;
  index?: number;
  component?: A2UIComponent;
  props?: Record<string, unknown>;
}

export interface DataModelUpdate {
  path: string;
  operation: "set" | "merge" | "delete" | "append" | "prepend";
  value?: unknown;
}
