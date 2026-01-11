"use client";

import React from "react";
import {
  Activity,
  AlertCircle,
  FileSearch,
  GitCompare,
  Layers,
  Shield,
  Zap,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { CanvasView } from "@/types/adk-schema";
import { TraceWaterfall } from "@/components/sre-widgets/TraceWaterfall";
import { LogPatternViewer } from "@/components/sre-widgets/LogPatternViewer";
import { MetricCorrelationChart } from "@/components/sre-widgets/MetricCorrelationChart";
import { RemediationPlan } from "@/components/sre-widgets/RemediationPlan";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface CanvasProps {
  view: CanvasView;
  onExecuteRemediation?: (action: any) => void;
  className?: string;
}

// Empty state component
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
        <Layers className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium mb-2">Situation Room</h3>
      <p className="text-muted-foreground text-sm max-w-md mb-6">
        Start an investigation by asking the SRE Agent a question. Analysis
        results will appear here as interactive visualizations.
      </p>
      <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-2 p-3 rounded-lg bg-muted/50">
          <Activity className="h-4 w-4 text-blue-400" />
          <span>Trace Analysis</span>
        </div>
        <div className="flex items-center gap-2 p-3 rounded-lg bg-muted/50">
          <FileSearch className="h-4 w-4 text-green-400" />
          <span>Log Patterns</span>
        </div>
        <div className="flex items-center gap-2 p-3 rounded-lg bg-muted/50">
          <AlertCircle className="h-4 w-4 text-yellow-400" />
          <span>Anomaly Detection</span>
        </div>
        <div className="flex items-center gap-2 p-3 rounded-lg bg-muted/50">
          <Zap className="h-4 w-4 text-orange-400" />
          <span>Remediation Plans</span>
        </div>
      </div>
    </div>
  );
}

// Trace comparison view
function TraceComparisonView({ data }: { data: any }) {
  return (
    <div className="space-y-4">
      <Card className="bg-card border-border">
        <CardHeader className="py-3 px-4 border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitCompare className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-sm font-medium">
                Trace Comparison
              </CardTitle>
            </div>
            <Badge
              variant={
                data.overall_assessment === "healthy"
                  ? "success"
                  : data.overall_assessment === "degraded"
                    ? "warning"
                    : "error"
              }
            >
              {data.overall_assessment.toUpperCase()}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-4">
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="p-3 rounded-lg bg-muted/50">
              <p className="text-xs text-muted-foreground mb-1">Baseline</p>
              <p className="text-sm font-mono">
                {data.baseline_summary.total_duration_ms.toFixed(1)}ms
              </p>
              <p className="text-xs text-muted-foreground">
                {data.baseline_summary.span_count} spans
              </p>
            </div>
            <div className="p-3 rounded-lg bg-muted/50">
              <p className="text-xs text-muted-foreground mb-1">Target</p>
              <p className="text-sm font-mono text-red-400">
                {data.target_summary.total_duration_ms.toFixed(1)}ms
              </p>
              <p className="text-xs text-muted-foreground">
                {data.target_summary.error_count} errors
              </p>
            </div>
          </div>

          {/* Root cause hypothesis */}
          <div className="p-3 rounded-lg bg-red-900/20 border border-red-900/50 mb-4">
            <p className="text-xs text-red-400 font-medium mb-1">
              Root Cause Hypothesis
            </p>
            <p className="text-sm text-foreground">
              {data.root_cause_hypothesis}
            </p>
          </div>

          {/* Latency findings */}
          {data.latency_findings.length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground mb-2">
                Latency Regressions
              </p>
              <div className="space-y-2">
                {data.latency_findings.slice(0, 5).map((finding: any, idx: number) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded bg-muted/30 text-xs"
                  >
                    <span className="font-mono">{finding.span_name}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-muted-foreground">
                        {finding.baseline_ms.toFixed(1)}ms →{" "}
                        <span className="text-red-400">
                          {finding.target_ms.toFixed(1)}ms
                        </span>
                      </span>
                      <Badge variant="error">
                        +{finding.diff_percent.toFixed(0)}%
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Causal analysis view
function CausalAnalysisView({ data }: { data: any }) {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="py-3 px-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-sm font-medium">
              Causal Analysis
            </CardTitle>
          </div>
          <Badge
            variant={
              data.confidence === "high"
                ? "success"
                : data.confidence === "medium"
                  ? "warning"
                  : "error"
            }
          >
            {data.confidence.toUpperCase()} CONFIDENCE
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-4">
        {/* Primary root cause */}
        <div className="p-3 rounded-lg bg-red-900/20 border border-red-900/50 mb-4">
          <p className="text-xs text-red-400 font-medium mb-1">
            Primary Root Cause
          </p>
          <p className="text-sm text-foreground font-medium">
            {data.primary_root_cause}
          </p>
        </div>

        {/* Causal chain visualization */}
        <div className="mb-4">
          <p className="text-xs text-muted-foreground mb-2">Causal Chain</p>
          <div className="flex items-center gap-2 overflow-x-auto py-2">
            {data.causal_chain.map((link: any, idx: number) => (
              <React.Fragment key={idx}>
                <div
                  className={cn(
                    "px-3 py-2 rounded text-xs font-mono whitespace-nowrap",
                    link.effect_type === "root_cause"
                      ? "bg-red-500/20 border border-red-500/50 text-red-400"
                      : link.effect_type === "direct_effect"
                        ? "bg-orange-500/20 border border-orange-500/50 text-orange-400"
                        : "bg-yellow-500/20 border border-yellow-500/50 text-yellow-400"
                  )}
                >
                  {link.span_name}
                  <span className="block text-[10px] opacity-75">
                    +{link.latency_contribution_ms.toFixed(0)}ms
                  </span>
                </div>
                {idx < data.causal_chain.length - 1 && (
                  <span className="text-muted-foreground">→</span>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Conclusion */}
        <div className="p-3 rounded-lg bg-muted/50">
          <p className="text-xs text-muted-foreground mb-1">Conclusion</p>
          <p className="text-sm">{data.conclusion}</p>
        </div>

        {/* Recommended actions */}
        {data.recommended_actions.length > 0 && (
          <div className="mt-4">
            <p className="text-xs text-muted-foreground mb-2">
              Recommended Actions
            </p>
            <ul className="space-y-1">
              {data.recommended_actions.map((action: string, idx: number) => (
                <li key={idx} className="text-xs flex items-start gap-2">
                  <span className="text-primary">•</span>
                  <span>{action}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function Canvas({ view, onExecuteRemediation, className }: CanvasProps) {
  const renderContent = () => {
    switch (view.type) {
      case "empty":
        return <EmptyState />;

      case "trace":
        return <TraceWaterfall trace={view.data} />;

      case "trace_comparison":
        return <TraceComparisonView data={view.data} />;

      case "log_patterns":
        return <LogPatternViewer data={view.data} />;

      case "metrics":
        return <MetricCorrelationChart data={view.data} />;

      case "remediation":
        return (
          <RemediationPlan
            data={view.data}
            onExecute={onExecuteRemediation}
          />
        );

      case "causal_analysis":
        return <CausalAnalysisView data={view.data} />;

      default:
        return <EmptyState />;
    }
  };

  return (
    <div className={cn("h-full overflow-hidden bg-background", className)}>
      <ScrollArea className="h-full">
        <div className="p-4">{renderContent()}</div>
      </ScrollArea>
    </div>
  );
}

export default Canvas;
