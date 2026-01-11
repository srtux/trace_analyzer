"use client";

import React, { useState, useCallback, useEffect } from "react";
import {
  CopilotKit,
  useCopilotAction,
  useCopilotReadable,
} from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";

import type {
  AgentStatus,
  CanvasView,
  Trace,
  LogPatternSummary,
  MetricWithAnomalies,
  RemediationSuggestion,
  TraceComparisonReport,
  CausalAnalysisReport,
} from "@/types/adk-schema";
import { StatusBar } from "@/components/layout/StatusBar";
import { Canvas } from "@/components/layout/Canvas";

import { sreClient } from "@/lib/api-client";

// Import mock data for demo (fallback)
import {
  mockTrace,
  mockErrorTrace,
  mockLogPatternSummary,
  mockMetricData,
  mockRemediationSuggestion,
  mockAgentStatuses,
  mockTraceComparison,
  mockCausalAnalysis,
  mockGcloudCommands,
} from "@/lib/mock-data";

// Main dashboard component with CopilotKit context
function MissionControlDashboard() {
  const [agentStatus, setAgentStatus] = useState<AgentStatus>(
    mockAgentStatuses.idle
  );
  const [canvasView, setCanvasView] = useState<CanvasView>({ type: "empty" });
  const [currentProject, setCurrentProject] = useState("my-gcp-project");

  // Make project context readable to CopilotKit
  useCopilotReadable({
    description: "Current GCP project being analyzed",
    value: currentProject,
  });

  useCopilotReadable({
    description: "Current canvas view type",
    value: canvasView.type,
  });

  // Action: Analyze a trace
  useCopilotAction({
    name: "analyzeTrace",
    description:
      "Analyze a distributed trace for latency issues and errors. Returns a trace waterfall visualization.",
    parameters: [
      {
        name: "traceId",
        type: "string",
        description: "The trace ID to analyze",
        required: true,
      },
      {
        name: "projectId",
        type: "string",
        description: "GCP project ID",
        required: false,
      },
    ],
    handler: async ({ traceId, projectId }) => {
      setAgentStatus(mockAgentStatuses.analyzing_trace);

      try {
        const trace = await sreClient.getTrace(traceId, projectId);
        setCanvasView({ type: "trace", data: trace });
        setAgentStatus(mockAgentStatuses.idle);

        return {
          success: true,
          message: `Analyzed trace ${traceId}. Found ${trace.spans.length} spans. Total duration: ${trace.total_duration_ms.toFixed(1)}ms.`,
        };
      } catch (error) {
        console.error("Error analyzing trace:", error);
        setAgentStatus(mockAgentStatuses.idle);
        return {
          success: false,
          message: `Failed to analyze trace ${traceId}: ${error instanceof Error ? error.message : String(error)}`,
        };
      }
    },
  });

  // Action: Analyze log patterns
  useCopilotAction({
    name: "analyzeLogPatterns",
    description:
      "Extract and analyze log patterns using the Drain3 algorithm. Clusters similar logs and identifies anomalies.",
    parameters: [
      {
        name: "service",
        type: "string",
        description: "Service name to analyze logs for",
        required: false,
      },
      {
        name: "timeRange",
        type: "string",
        description: "Time range (e.g., '1h', '24h', '7d')",
        required: false,
      },
      {
        name: "projectId",
        type: "string",
        description: "GCP project ID",
        required: false,
      },
    ],
    handler: async ({ service, timeRange, projectId }) => {
      setAgentStatus(mockAgentStatuses.processing_logs);

      try {
        // Construct filter based on service/timeRange if needed
        const filter = service ? `resource.labels.service_name="${service}"` : "";

        const result = await sreClient.analyzeLogs({
          filter,
          baseline_start: "1h-ago", // Placeholder; would ideally be dynamic
          baseline_end: "30m-ago",
          comparison_start: "30m-ago",
          comparison_end: "now",
          project_id: projectId
        });

        setCanvasView({ type: "log_patterns", data: result });
        setAgentStatus(mockAgentStatuses.idle);

        return {
          success: true,
          message: `Analyzed log patterns. Found ${result.unique_patterns} unique clusters.`,
        };
      } catch (error) {
        console.error("Error analyzing logs:", error);
        setAgentStatus(mockAgentStatuses.idle);
        return {
          success: false,
          message: `Failed to analyze log patterns: ${error instanceof Error ? error.message : String(error)}`,
        };
      }
    },
  });

  // Action: Analyze metrics
  useCopilotAction({
    name: "analyzeMetrics",
    description:
      "Analyze time-series metrics for anomalies and correlations with incidents.",
    parameters: [
      {
        name: "metricType",
        type: "string",
        description: "Type of metric (latency, error_rate, throughput)",
        required: true,
      },
      {
        name: "service",
        type: "string",
        description: "Service name",
        required: false,
      },
    ],
    handler: async ({ metricType, service }) => {
      setAgentStatus(mockAgentStatuses.correlating);

      await new Promise((resolve) => setTimeout(resolve, 2000));

      setCanvasView({ type: "metrics", data: mockMetricData });
      setAgentStatus(mockAgentStatuses.idle);

      const anomalyCount = mockMetricData.anomalies.length;

      return {
        success: true,
        message: `Analyzed ${metricType} metrics for ${service || "all services"}. Detected ${anomalyCount} anomalies. Incident window identified from 10:30 to 12:00.`,
      };
    },
  });

  // Action: Compare traces
  useCopilotAction({
    name: "compareTraces",
    description:
      "Compare a baseline trace with a target trace to identify regressions and differences.",
    parameters: [
      {
        name: "baselineTraceId",
        type: "string",
        description: "Baseline (good) trace ID",
        required: true,
      },
      {
        name: "targetTraceId",
        type: "string",
        description: "Target (problematic) trace ID",
        required: true,
      },
    ],
    handler: async ({ baselineTraceId, targetTraceId }) => {
      setAgentStatus({
        currentAgent: "latency_specialist",
        message: `Comparing traces ${baselineTraceId} and ${targetTraceId}...`,
        progress: 30,
        startTime: new Date().toISOString(),
      });

      await new Promise((resolve) => setTimeout(resolve, 3000));

      setCanvasView({ type: "trace_comparison", data: mockTraceComparison });
      setAgentStatus(mockAgentStatuses.idle);

      return {
        success: true,
        message: `Compared traces. Overall assessment: ${mockTraceComparison.overall_assessment.toUpperCase()}. Found ${mockTraceComparison.latency_findings.length} latency regressions and ${mockTraceComparison.error_findings.length} new errors. Root cause hypothesis: ${mockTraceComparison.root_cause_hypothesis.slice(0, 100)}...`,
      };
    },
  });

  // Action: Get remediation suggestions
  useCopilotAction({
    name: "getRemediationPlan",
    description:
      "Generate a remediation plan based on the current analysis findings.",
    parameters: [
      {
        name: "findingSummary",
        type: "string",
        description: "Summary of the issue to remediate",
        required: true,
      },
    ],
    handler: async ({ findingSummary }) => {
      setAgentStatus(mockAgentStatuses.generating_remediation);

      await new Promise((resolve) => setTimeout(resolve, 1500));

      setCanvasView({ type: "remediation", data: mockRemediationSuggestion });
      setAgentStatus(mockAgentStatuses.idle);

      return {
        success: true,
        message: `Generated remediation plan with ${mockRemediationSuggestion.suggestions.length} suggestions. ${mockRemediationSuggestion.quick_wins.length} quick wins available. Recommended first action: ${mockRemediationSuggestion.recommended_first_action?.action}.`,
      };
    },
  });

  // Action: Run causal analysis
  useCopilotAction({
    name: "runCausalAnalysis",
    description:
      "Run causal analysis to identify the root cause of an incident.",
    parameters: [
      {
        name: "incidentDescription",
        type: "string",
        description: "Description of the incident",
        required: true,
      },
    ],
    handler: async ({ incidentDescription }) => {
      setAgentStatus({
        currentAgent: "orchestrator",
        message: "Running multi-agent causal analysis...",
        progress: 25,
        startTime: new Date().toISOString(),
      });

      await new Promise((resolve) => setTimeout(resolve, 1000));

      setAgentStatus({
        currentAgent: "latency_specialist",
        message: "Latency specialist analyzing span durations...",
        progress: 50,
        startTime: new Date().toISOString(),
      });

      await new Promise((resolve) => setTimeout(resolve, 1000));

      setAgentStatus({
        currentAgent: "error_analyst",
        message: "Error analyst examining failure patterns...",
        progress: 75,
        startTime: new Date().toISOString(),
      });

      await new Promise((resolve) => setTimeout(resolve, 1000));

      setCanvasView({ type: "causal_analysis", data: mockCausalAnalysis });
      setAgentStatus(mockAgentStatuses.idle);

      return {
        success: true,
        message: `Causal analysis complete. Primary root cause: ${mockCausalAnalysis.primary_root_cause}. Confidence: ${mockCausalAnalysis.confidence.toUpperCase()}. Propagation depth: ${mockCausalAnalysis.propagation_depth} services affected.`,
      };
    },
  });

  // Action: Execute remediation
  useCopilotAction({
    name: "executeRemediation",
    description:
      "Execute a specific remediation action. Requires user confirmation.",
    parameters: [
      {
        name: "action",
        type: "string",
        description: "The remediation action to execute",
        required: true,
      },
      {
        name: "confirmed",
        type: "boolean",
        description: "Whether the user has confirmed the action",
        required: true,
      },
    ],
    handler: async ({ action, confirmed }) => {
      if (!confirmed) {
        return {
          success: false,
          message:
            "Action requires confirmation. Please confirm you want to execute this remediation.",
          requiresConfirmation: true,
        };
      }

      setAgentStatus({
        currentAgent: "remediation_advisor",
        message: `Executing: ${action}...`,
        progress: 50,
        startTime: new Date().toISOString(),
      });

      await new Promise((resolve) => setTimeout(resolve, 2000));

      setAgentStatus(mockAgentStatuses.idle);

      return {
        success: true,
        message: `Successfully executed: ${action}. Monitor the affected services for the next 15 minutes.`,
      };
    },
  });

  // Handler for remediation execution from UI
  const handleExecuteRemediation = useCallback((action: any) => {
    console.log("Executing remediation:", action);
    // This would trigger the CopilotKit action
  }, []);

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Status Bar */}
      <StatusBar agentStatus={agentStatus} />

      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat Sidebar (25%) */}
        <div className="w-[25%] min-w-[300px] border-r border-border">
          <CopilotChat
            labels={{
              title: "SRE Agent",
              initial:
                "I'm your SRE copilot. I can help you investigate incidents, analyze traces, detect log patterns, and suggest remediations. What would you like to investigate?",
              placeholder: "Describe the issue or ask for analysis...",
            }}
            className="h-full"
          />
        </div>

        {/* Main Canvas (75%) */}
        <div className="flex-1 overflow-hidden">
          <Canvas
            view={canvasView}
            onExecuteRemediation={handleExecuteRemediation}
          />
        </div>
      </div>
    </div>
  );
}

// Root page with CopilotKit provider
export default function Page() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <MissionControlDashboard />
    </CopilotKit>
  );
}
