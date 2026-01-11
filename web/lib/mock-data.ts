/**
 * Mock data for testing SRE Mission Control components.
 * Realistic Google Cloud Trace, Log, and Metrics data.
 */

import type {
  Trace,
  SpanInfo,
  LogPattern,
  LogPatternSummary,
  MetricWithAnomalies,
  TimeSeriesPoint,
  RemediationSuggestion,
  RiskAssessment,
  AgentStatus,
  TraceComparisonReport,
  CausalAnalysisReport,
} from "@/types/adk-schema";

// =============================================================================
// Sample Trace Data - E-commerce Checkout Flow
// =============================================================================

export const mockSpans: SpanInfo[] = [
  {
    span_id: "span-001",
    name: "POST /api/checkout",
    duration_ms: 2847.5,
    parent_span_id: null,
    has_error: false,
    labels: {
      "http.method": "POST",
      "http.url": "/api/checkout",
      "http.status_code": "200",
      service: "api-gateway",
    },
    start_time: "2024-01-15T10:30:00.000Z",
    end_time: "2024-01-15T10:30:02.847Z",
    service_name: "api-gateway",
  },
  {
    span_id: "span-002",
    name: "ValidateCart",
    duration_ms: 125.3,
    parent_span_id: "span-001",
    has_error: false,
    labels: {
      service: "cart-service",
      "cart.items": "3",
    },
    start_time: "2024-01-15T10:30:00.050Z",
    end_time: "2024-01-15T10:30:00.175Z",
    service_name: "cart-service",
  },
  {
    span_id: "span-003",
    name: "SELECT * FROM inventory",
    duration_ms: 890.2,
    parent_span_id: "span-002",
    has_error: false,
    labels: {
      "db.system": "postgresql",
      "db.name": "inventory_db",
      "db.statement": "SELECT * FROM inventory WHERE sku IN (...)",
    },
    start_time: "2024-01-15T10:30:00.080Z",
    end_time: "2024-01-15T10:30:00.970Z",
    service_name: "inventory-db",
  },
  {
    span_id: "span-004",
    name: "ProcessPayment",
    duration_ms: 1523.7,
    parent_span_id: "span-001",
    has_error: false,
    labels: {
      service: "payment-service",
      "payment.provider": "stripe",
      "payment.amount": "149.99",
    },
    start_time: "2024-01-15T10:30:00.200Z",
    end_time: "2024-01-15T10:30:01.723Z",
    service_name: "payment-service",
  },
  {
    span_id: "span-005",
    name: "Stripe API Call",
    duration_ms: 1245.5,
    parent_span_id: "span-004",
    has_error: false,
    labels: {
      "http.method": "POST",
      "http.url": "https://api.stripe.com/v1/charges",
      "http.status_code": "200",
    },
    start_time: "2024-01-15T10:30:00.300Z",
    end_time: "2024-01-15T10:30:01.545Z",
    service_name: "stripe-api",
  },
  {
    span_id: "span-006",
    name: "UpdateInventory",
    duration_ms: 342.1,
    parent_span_id: "span-001",
    has_error: false,
    labels: {
      service: "inventory-service",
      "items.updated": "3",
    },
    start_time: "2024-01-15T10:30:01.750Z",
    end_time: "2024-01-15T10:30:02.092Z",
    service_name: "inventory-service",
  },
  {
    span_id: "span-007",
    name: "INSERT INTO orders",
    duration_ms: 156.8,
    parent_span_id: "span-006",
    has_error: false,
    labels: {
      "db.system": "postgresql",
      "db.name": "orders_db",
    },
    start_time: "2024-01-15T10:30:01.800Z",
    end_time: "2024-01-15T10:30:01.956Z",
    service_name: "orders-db",
  },
  {
    span_id: "span-008",
    name: "SendConfirmationEmail",
    duration_ms: 678.4,
    parent_span_id: "span-001",
    has_error: true,
    labels: {
      service: "notification-service",
      "email.template": "order_confirmation",
      error: "SMTP connection timeout",
    },
    start_time: "2024-01-15T10:30:02.100Z",
    end_time: "2024-01-15T10:30:02.778Z",
    service_name: "notification-service",
    status_code: 500,
  },
  {
    span_id: "span-009",
    name: "PublishEvent:OrderCreated",
    duration_ms: 45.2,
    parent_span_id: "span-001",
    has_error: false,
    labels: {
      service: "event-bus",
      "event.type": "OrderCreated",
      "pubsub.topic": "orders",
    },
    start_time: "2024-01-15T10:30:02.780Z",
    end_time: "2024-01-15T10:30:02.825Z",
    service_name: "pubsub",
  },
];

export const mockTrace: Trace = {
  trace_id: "projects/my-gcp-project/traces/abc123def456789",
  project_id: "my-gcp-project",
  spans: mockSpans,
  start_time: "2024-01-15T10:30:00.000Z",
  end_time: "2024-01-15T10:30:02.847Z",
  total_duration_ms: 2847.5,
  root_span_id: "span-001",
};

// Trace with errors - problematic scenario
export const mockErrorTrace: Trace = {
  trace_id: "projects/my-gcp-project/traces/error-trace-789",
  project_id: "my-gcp-project",
  spans: [
    {
      span_id: "err-span-001",
      name: "POST /api/checkout",
      duration_ms: 5234.8,
      parent_span_id: null,
      has_error: true,
      labels: {
        "http.method": "POST",
        "http.status_code": "500",
        service: "api-gateway",
      },
      start_time: "2024-01-15T11:45:00.000Z",
      end_time: "2024-01-15T11:45:05.234Z",
      service_name: "api-gateway",
      status_code: 500,
    },
    {
      span_id: "err-span-002",
      name: "ProcessPayment",
      duration_ms: 4890.3,
      parent_span_id: "err-span-001",
      has_error: true,
      labels: {
        service: "payment-service",
        error: "Connection pool exhausted",
      },
      start_time: "2024-01-15T11:45:00.100Z",
      end_time: "2024-01-15T11:45:04.990Z",
      service_name: "payment-service",
      status_code: 503,
    },
    {
      span_id: "err-span-003",
      name: "DB Connection",
      duration_ms: 4500.0,
      parent_span_id: "err-span-002",
      has_error: true,
      labels: {
        "db.system": "postgresql",
        error: "timeout waiting for connection",
      },
      start_time: "2024-01-15T11:45:00.200Z",
      end_time: "2024-01-15T11:45:04.700Z",
      service_name: "payment-db",
      status_code: 504,
    },
  ],
  start_time: "2024-01-15T11:45:00.000Z",
  end_time: "2024-01-15T11:45:05.234Z",
  total_duration_ms: 5234.8,
  root_span_id: "err-span-001",
};

// =============================================================================
// Log Pattern Data
// =============================================================================

export const mockLogPatterns: LogPattern[] = [
  {
    pattern_id: "pat-001",
    template:
      "Request completed successfully for user <ID> in <DURATION> with status 200",
    count: 15234,
    first_seen: "2024-01-15T00:00:00Z",
    last_seen: "2024-01-15T23:59:59Z",
    severity_counts: { INFO: 15234 },
    sample_messages: [
      "Request completed successfully for user abc123 in 145ms with status 200",
      "Request completed successfully for user def456 in 89ms with status 200",
    ],
    resources: ["gke-cluster/api-gateway", "gke-cluster/frontend"],
  },
  {
    pattern_id: "pat-002",
    template:
      "Connection pool exhausted: <NUM> active connections, max <NUM>. Waiting for available connection.",
    count: 847,
    first_seen: "2024-01-15T10:30:00Z",
    last_seen: "2024-01-15T12:45:00Z",
    severity_counts: { ERROR: 623, WARNING: 224 },
    sample_messages: [
      "Connection pool exhausted: 100 active connections, max 100. Waiting for available connection.",
      "Connection pool exhausted: 100 active connections, max 100. Waiting for available connection.",
    ],
    resources: ["gke-cluster/payment-service", "gke-cluster/order-service"],
  },
  {
    pattern_id: "pat-003",
    template: "OOMKilled: Container <ID> exceeded memory limit of <SIZE>",
    count: 23,
    first_seen: "2024-01-15T11:00:00Z",
    last_seen: "2024-01-15T11:30:00Z",
    severity_counts: { CRITICAL: 23 },
    sample_messages: [
      "OOMKilled: Container abc123 exceeded memory limit of 512Mi",
      "OOMKilled: Container def456 exceeded memory limit of 512Mi",
    ],
    resources: ["gke-cluster/data-processor"],
  },
  {
    pattern_id: "pat-004",
    template:
      "Slow query detected: <QUERY> took <DURATION> (threshold: <DURATION>)",
    count: 156,
    first_seen: "2024-01-15T09:00:00Z",
    last_seen: "2024-01-15T23:00:00Z",
    severity_counts: { WARNING: 156 },
    sample_messages: [
      "Slow query detected: SELECT * FROM orders WHERE... took 2.5s (threshold: 500ms)",
    ],
    resources: ["cloudsql/orders-db"],
  },
  {
    pattern_id: "pat-005",
    template: "Health check passed for service <SERVICE> on port <PORT>",
    count: 43200,
    first_seen: "2024-01-15T00:00:00Z",
    last_seen: "2024-01-15T23:59:59Z",
    severity_counts: { INFO: 43200 },
    sample_messages: [
      "Health check passed for service api-gateway on port 8080",
    ],
    resources: ["gke-cluster/*"],
  },
  {
    pattern_id: "pat-006",
    template:
      "Failed to connect to Redis: <ERROR>. Retry attempt <NUM> of <NUM>",
    count: 89,
    first_seen: "2024-01-15T14:00:00Z",
    last_seen: "2024-01-15T14:15:00Z",
    severity_counts: { ERROR: 67, WARNING: 22 },
    sample_messages: [
      "Failed to connect to Redis: Connection refused. Retry attempt 1 of 3",
    ],
    resources: ["gke-cluster/session-service"],
  },
];

export const mockLogPatternSummary: LogPatternSummary = {
  total_logs_processed: 89542,
  unique_patterns: 47,
  severity_distribution: {
    INFO: 78234,
    WARNING: 8923,
    ERROR: 2108,
    CRITICAL: 277,
  },
  compression_ratio: 1905.14,
  top_patterns: mockLogPatterns,
  error_patterns: mockLogPatterns.filter(
    (p) => p.severity_counts["ERROR"] || p.severity_counts["CRITICAL"]
  ),
};

// =============================================================================
// Metrics Data
// =============================================================================

function generateTimeSeriesPoints(
  baseValue: number,
  variance: number,
  hours: number = 24,
  intervalMinutes: number = 5
): TimeSeriesPoint[] {
  const points: TimeSeriesPoint[] = [];
  const now = new Date();
  const totalPoints = (hours * 60) / intervalMinutes;

  for (let i = 0; i < totalPoints; i++) {
    const timestamp = new Date(
      now.getTime() - (totalPoints - i) * intervalMinutes * 60 * 1000
    );

    // Add some realistic patterns
    const hourOfDay = timestamp.getHours();
    const dailyPattern =
      hourOfDay >= 9 && hourOfDay <= 17 ? 1.5 : hourOfDay >= 2 && hourOfDay <= 5 ? 0.5 : 1;
    const randomVariance = (Math.random() - 0.5) * 2 * variance;

    // Add an anomaly spike around 10:30-11:00
    const isAnomalyWindow =
      hourOfDay === 10 && timestamp.getMinutes() >= 30 ||
      hourOfDay === 11 && timestamp.getMinutes() <= 30;
    const anomalyMultiplier = isAnomalyWindow ? 2.5 + Math.random() : 1;

    points.push({
      timestamp: timestamp.toISOString(),
      value: Math.max(0, baseValue * dailyPattern * anomalyMultiplier + randomVariance),
    });
  }

  return points;
}

export const mockMetricData: MetricWithAnomalies = {
  series: {
    metric: {
      type: "custom.googleapis.com/http/server/latency",
      labels: {
        service: "checkout-service",
        method: "POST",
        path: "/api/checkout",
      },
    },
    resource: {
      type: "gke_container",
      labels: {
        project_id: "my-gcp-project",
        cluster_name: "prod-cluster",
        namespace_name: "default",
        pod_name: "checkout-service-abc123",
      },
    },
    points: generateTimeSeriesPoints(250, 50, 24, 5),
    metric_name: "HTTP Latency (p99)",
  },
  anomalies: [
    {
      timestamp: new Date(Date.now() - 13.5 * 60 * 60 * 1000).toISOString(),
      value: 892.5,
      expected_value: 275.3,
      deviation: 3.2,
      severity: "high",
      description: "Latency spike correlates with connection pool exhaustion",
    },
    {
      timestamp: new Date(Date.now() - 13 * 60 * 60 * 1000).toISOString(),
      value: 1245.8,
      expected_value: 268.1,
      deviation: 4.1,
      severity: "critical",
      description: "Peak latency - database connection timeout",
    },
    {
      timestamp: new Date(Date.now() - 12.5 * 60 * 60 * 1000).toISOString(),
      value: 678.3,
      expected_value: 271.5,
      deviation: 2.4,
      severity: "medium",
      description: "Elevated latency - connection pool recovering",
    },
  ],
  incident_window: {
    start: new Date(Date.now() - 14 * 60 * 60 * 1000).toISOString(),
    end: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
  },
};

export const mockErrorRateMetric: MetricWithAnomalies = {
  series: {
    metric: {
      type: "custom.googleapis.com/http/server/error_rate",
      labels: {
        service: "payment-service",
      },
    },
    resource: {
      type: "gke_container",
      labels: {
        project_id: "my-gcp-project",
        cluster_name: "prod-cluster",
      },
    },
    points: generateTimeSeriesPoints(0.5, 0.2, 24, 5).map((p) => ({
      ...p,
      value: Math.min(100, p.value), // Cap at 100%
    })),
    metric_name: "Error Rate (%)",
  },
  anomalies: [
    {
      timestamp: new Date(Date.now() - 13 * 60 * 60 * 1000).toISOString(),
      value: 45.2,
      expected_value: 0.8,
      severity: "critical",
      description: "Error rate spike - database connectivity issues",
    },
  ],
  incident_window: {
    start: new Date(Date.now() - 14 * 60 * 60 * 1000).toISOString(),
    end: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
  },
};

// =============================================================================
// Remediation Data
// =============================================================================

export const mockRemediationSuggestion: RemediationSuggestion = {
  matched_patterns: ["connection_pool", "high_latency"],
  categories: ["database", "performance"],
  finding_summary:
    "Database connection pool exhaustion detected in payment-service causing checkout failures and high latency",
  suggestions: [
    {
      action: "Increase connection pool size",
      description:
        "The payment-service is running out of database connections under load.",
      steps: [
        "Review current pool size configuration (currently 100)",
        "Increase pool size to 150-200 based on traffic patterns",
        "Add connection pool metrics to monitoring dashboard",
        "Set up alerts for pool utilization > 80%",
      ],
      risk: "low",
      effort: "low",
      category: "database",
    },
    {
      action: "Fix connection leaks",
      description:
        "Connections may not be properly returned to pool in error paths.",
      steps: [
        "Review code for proper connection handling (try-finally)",
        "Add connection leak detection logging",
        "Ensure connections are closed in all error paths",
        "Add unit tests for connection lifecycle",
      ],
      risk: "medium",
      effort: "medium",
      category: "database",
    },
    {
      action: "Add PgBouncer connection pooler",
      description:
        "Use PgBouncer for more efficient connection management at scale.",
      steps: [
        "Deploy PgBouncer in front of Cloud SQL",
        "Configure transaction pooling mode",
        "Update application connection strings",
        "Validate with load testing",
      ],
      risk: "medium",
      effort: "high",
      category: "database",
    },
    {
      action: "Scale horizontally",
      description: "Add more payment-service replicas to distribute load.",
      steps: [
        "Increase min replicas from 3 to 5",
        "Verify HPA max is sufficient",
        "Monitor resource utilization after scaling",
      ],
      risk: "low",
      effort: "low",
      category: "performance",
    },
  ],
  recommended_first_action: {
    action: "Increase connection pool size",
    description:
      "The payment-service is running out of database connections under load.",
    steps: [
      "Review current pool size configuration (currently 100)",
      "Increase pool size to 150-200 based on traffic patterns",
      "Add connection pool metrics to monitoring dashboard",
    ],
    risk: "low",
    effort: "low",
    category: "database",
  },
  quick_wins: [
    {
      action: "Increase connection pool size",
      description:
        "The payment-service is running out of database connections under load.",
      steps: [
        "Review current pool size configuration",
        "Increase pool size to 150-200",
      ],
      risk: "low",
      effort: "low",
    },
    {
      action: "Scale horizontally",
      description: "Add more payment-service replicas to distribute load.",
      steps: ["Increase min replicas from 3 to 5"],
      risk: "low",
      effort: "low",
    },
  ],
};

export const mockGcloudCommands = {
  remediation_type: "scale_up",
  resource: "payment-service",
  project: "my-gcp-project",
  commands: [
    {
      description: "Scale Cloud Run service to 5 min instances",
      command:
        "gcloud run services update payment-service --min-instances=5 --region=us-central1 --project=my-gcp-project",
    },
    {
      description: "Verify the update",
      command:
        "gcloud run services describe payment-service --region=us-central1 --project=my-gcp-project --format='value(spec.template.spec.containerConcurrency)'",
    },
  ],
  warning:
    "Review commands before executing. Some changes may cause brief service interruption.",
};

export const mockRiskAssessment: RiskAssessment = {
  action: "Increase connection pool size",
  service: "payment-service",
  change: "Increase database connection pool from 100 to 200 connections",
  risk_assessment: {
    level: "low",
    confidence: "high",
    factors: [
      "Change is additive, not destructive",
      "Database has capacity for additional connections",
      "Can be rolled back by redeploying previous config",
    ],
  },
  recommendations: {
    proceed: true,
    require_approval: false,
    mitigations: [
      "Monitor database CPU and memory after change",
      "Verify max_connections limit on Cloud SQL instance",
      "Have rollback plan ready (redeploy previous config)",
      "Apply during low-traffic window if possible",
    ],
  },
  checklist: [
    "[ ] Review change: Increase pool size from 100 to 200",
    "[ ] Verify Cloud SQL max_connections > 200",
    "[ ] Notify on-call if outside business hours",
    "[ ] Prepare rollback procedure",
    "[ ] Execute change",
    "[ ] Monitor for 15 minutes post-change",
    "[ ] Document outcome",
  ],
};

// =============================================================================
// Agent Status Data
// =============================================================================

export const mockAgentStatuses: Record<string, AgentStatus> = {
  idle: {
    currentAgent: "idle",
    message: "Ready for investigation",
  },
  analyzing_trace: {
    currentAgent: "latency_specialist",
    message: "Analyzing trace span hierarchy for latency bottlenecks...",
    progress: 45,
    startTime: new Date(Date.now() - 30000).toISOString(),
  },
  processing_logs: {
    currentAgent: "log_pattern_engine",
    message: "Drain3 engine clustering 89,542 log entries...",
    progress: 72,
    startTime: new Date(Date.now() - 45000).toISOString(),
  },
  correlating: {
    currentAgent: "metrics_correlator",
    message:
      "Cross-correlating metrics with trace anomalies in incident window...",
    progress: 88,
    startTime: new Date(Date.now() - 60000).toISOString(),
  },
  generating_remediation: {
    currentAgent: "remediation_advisor",
    message: "Generating remediation plan based on root cause analysis...",
    progress: 95,
    startTime: new Date(Date.now() - 15000).toISOString(),
  },
};

// =============================================================================
// Trace Comparison Data
// =============================================================================

export const mockTraceComparison: TraceComparisonReport = {
  baseline_summary: {
    trace_id: "baseline-trace-123",
    span_count: 12,
    total_duration_ms: 245.6,
    error_count: 0,
    max_depth: 4,
  },
  target_summary: {
    trace_id: "target-trace-456",
    span_count: 12,
    total_duration_ms: 2847.5,
    error_count: 2,
    max_depth: 4,
  },
  overall_assessment: "critical",
  latency_findings: [
    {
      span_name: "ProcessPayment",
      baseline_ms: 150.2,
      target_ms: 1523.7,
      diff_ms: 1373.5,
      diff_percent: 914.5,
      severity: "critical",
    },
    {
      span_name: "SELECT * FROM inventory",
      baseline_ms: 45.3,
      target_ms: 890.2,
      diff_ms: 844.9,
      diff_percent: 1865.3,
      severity: "critical",
    },
    {
      span_name: "Stripe API Call",
      baseline_ms: 120.5,
      target_ms: 1245.5,
      diff_ms: 1125.0,
      diff_percent: 933.6,
      severity: "high",
    },
  ],
  error_findings: [
    {
      span_name: "SendConfirmationEmail",
      error_type: "SMTP_TIMEOUT",
      error_message: "SMTP connection timeout after 5000ms",
      status_code: 500,
      is_new: true,
    },
  ],
  structure_findings: [],
  root_cause_hypothesis:
    "Database connection pool exhaustion is causing cascading latency across multiple services. The payment service is most affected, with a 914% increase in latency. This is likely caused by connection leaks or insufficient pool size during peak traffic.",
  recommendations: [
    "Immediately increase connection pool size from 100 to 200",
    "Add connection leak detection logging",
    "Implement circuit breaker for database calls",
    "Review connection handling in error paths",
  ],
};

// =============================================================================
// Causal Analysis Data
// =============================================================================

export const mockCausalAnalysis: CausalAnalysisReport = {
  causal_chain: [
    {
      span_name: "Database Connection Pool",
      effect_type: "root_cause",
      latency_contribution_ms: 4500,
    },
    {
      span_name: "ProcessPayment",
      effect_type: "direct_effect",
      latency_contribution_ms: 1373.5,
    },
    {
      span_name: "Stripe API Call",
      effect_type: "cascaded_effect",
      latency_contribution_ms: 1125,
    },
    {
      span_name: "POST /api/checkout",
      effect_type: "cascaded_effect",
      latency_contribution_ms: 2600,
    },
  ],
  root_cause_candidates: [
    {
      rank: 1,
      span_name: "Database Connection Pool",
      slowdown_ms: 4500,
      confidence: "high",
      reasoning:
        "Connection pool exhaustion logs correlate exactly with latency spike. All downstream services show proportional degradation.",
    },
    {
      rank: 2,
      span_name: "Cloud SQL Instance",
      slowdown_ms: 890,
      confidence: "medium",
      reasoning:
        "Elevated query latency may indicate database resource contention, but metrics show CPU/memory within limits.",
    },
  ],
  propagation_depth: 4,
  primary_root_cause: "Database connection pool exhaustion",
  confidence: "high",
  conclusion:
    "The root cause is database connection pool exhaustion in the payment-service. When the pool reached its limit of 100 connections, new requests were forced to wait for available connections, causing a cascading latency increase across the checkout flow. The error in SendConfirmationEmail is a secondary effect of the overall request timeout.",
  recommended_actions: [
    "Increase connection pool size to 200",
    "Add connection pool utilization metrics and alerts",
    "Implement connection timeout with graceful degradation",
    "Review and fix potential connection leaks",
  ],
};
