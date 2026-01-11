"use client";

import React, { useMemo } from "react";
import { format } from "date-fns";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceArea,
  ReferenceDot,
  Legend,
} from "recharts";
import {
  Activity,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";

import { cn, formatDuration } from "@/lib/utils";
import type { MetricWithAnomalies, Anomaly } from "@/types/adk-schema";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface MetricCorrelationChartProps {
  data: MetricWithAnomalies;
  title?: string;
  className?: string;
  height?: number;
}

interface ChartDataPoint {
  timestamp: string;
  value: number;
  displayTime: string;
  anomaly?: Anomaly;
  isIncidentWindow?: boolean;
}

// Resource labels component to avoid type issues
function ResourceLabels({ labels }: { labels?: Record<string, string> }) {
  if (!labels) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {Object.entries(labels)
        .slice(0, 4)
        .map(([key, value]) => (
          <Badge key={key} variant="secondary" className="text-xs">
            {key.replace(/_/g, " ")}: {String(value)}
          </Badge>
        ))}
    </div>
  );
}

// Custom tooltip component
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0]?.payload as ChartDataPoint;
  const anomaly = data?.anomaly;

  return (
    <div className="bg-popover border border-border rounded-lg shadow-lg p-3 text-xs">
      <p className="font-mono text-muted-foreground mb-1">{data.displayTime}</p>
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-primary" />
        <span className="font-mono font-medium">
          {data.value.toFixed(2)}
        </span>
      </div>

      {anomaly && (
        <div className="mt-2 pt-2 border-t border-border">
          <div className="flex items-center gap-1 text-red-400 mb-1">
            <AlertCircle className="h-3 w-3" />
            <span className="font-medium">Anomaly Detected</span>
          </div>
          {anomaly.expected_value && (
            <p className="text-muted-foreground">
              Expected: {anomaly.expected_value.toFixed(2)}
            </p>
          )}
          {anomaly.deviation && (
            <p className="text-muted-foreground">
              Deviation: {anomaly.deviation.toFixed(1)}σ
            </p>
          )}
          {anomaly.description && (
            <p className="text-foreground mt-1">{anomaly.description}</p>
          )}
        </div>
      )}

      {data.isIncidentWindow && !anomaly && (
        <div className="mt-2 pt-2 border-t border-border">
          <Badge variant="warning" className="text-xs">
            Incident Window
          </Badge>
        </div>
      )}
    </div>
  );
}

// Calculate trend
function calculateTrend(points: { value: number }[]): "up" | "down" | "stable" {
  if (points.length < 10) return "stable";

  const recentHalf = points.slice(-Math.floor(points.length / 2));
  const olderHalf = points.slice(0, Math.floor(points.length / 2));

  const recentAvg =
    recentHalf.reduce((sum, p) => sum + p.value, 0) / recentHalf.length;
  const olderAvg =
    olderHalf.reduce((sum, p) => sum + p.value, 0) / olderHalf.length;

  const changePercent = ((recentAvg - olderAvg) / olderAvg) * 100;

  if (changePercent > 10) return "up";
  if (changePercent < -10) return "down";
  return "stable";
}

export function MetricCorrelationChart({
  data,
  title,
  className,
  height = 300,
}: MetricCorrelationChartProps) {
  // Process data for the chart
  const { chartData, incidentStart, incidentEnd, stats } = useMemo(() => {
    const anomalyMap = new Map(
      data.anomalies.map((a) => [new Date(a.timestamp).getTime(), a])
    );

    const incidentStartTime = data.incident_window
      ? new Date(data.incident_window.start).getTime()
      : null;
    const incidentEndTime = data.incident_window
      ? new Date(data.incident_window.end).getTime()
      : null;

    const chartData: ChartDataPoint[] = data.series.points.map((point) => {
      const timestamp = new Date(point.timestamp).getTime();
      const isIncidentWindow =
        incidentStartTime &&
        incidentEndTime &&
        timestamp >= incidentStartTime &&
        timestamp <= incidentEndTime;

      return {
        timestamp: point.timestamp,
        value: point.value,
        displayTime: format(new Date(point.timestamp), "HH:mm"),
        anomaly: anomalyMap.get(timestamp),
        isIncidentWindow: Boolean(isIncidentWindow),
      };
    });

    // Calculate stats
    const values = chartData.map((d) => d.value);
    const stats = {
      min: Math.min(...values),
      max: Math.max(...values),
      avg: values.reduce((a, b) => a + b, 0) / values.length,
      current: values[values.length - 1] || 0,
      trend: calculateTrend(chartData),
    };

    return {
      chartData,
      incidentStart: incidentStartTime
        ? format(new Date(incidentStartTime), "HH:mm")
        : null,
      incidentEnd: incidentEndTime
        ? format(new Date(incidentEndTime), "HH:mm")
        : null,
      stats,
    };
  }, [data]);

  const metricName =
    title ||
    data.series.metric_name ||
    (data.series.metric.type as string)?.split("/").pop() ||
    "Metric";

  const TrendIcon =
    stats.trend === "up"
      ? TrendingUp
      : stats.trend === "down"
        ? TrendingDown
        : Minus;
  const trendColor =
    stats.trend === "up"
      ? "text-red-400"
      : stats.trend === "down"
        ? "text-green-400"
        : "text-muted-foreground";

  return (
    <Card className={cn("bg-card border-border", className)}>
      <CardHeader className="py-3 px-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-sm font-medium">{metricName}</CardTitle>
            {data.anomalies.length > 0 && (
              <Badge variant="error" className="text-xs">
                <AlertCircle className="h-3 w-3 mr-1" />
                {data.anomalies.length} Anomalies
              </Badge>
            )}
          </div>

          {/* Stats */}
          <div className="flex items-center gap-4 text-xs">
            <div>
              <span className="text-muted-foreground">Current:</span>{" "}
              <span className="font-mono font-medium">
                {stats.current.toFixed(1)}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Avg:</span>{" "}
              <span className="font-mono">{stats.avg.toFixed(1)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Max:</span>{" "}
              <span className="font-mono text-yellow-400">
                {stats.max.toFixed(1)}
              </span>
            </div>
            <div className={cn("flex items-center gap-1", trendColor)}>
              <TrendIcon className="h-3.5 w-3.5" />
              <span className="capitalize">{stats.trend}</span>
            </div>
          </div>
        </div>

        {/* Resource labels */}
        <ResourceLabels labels={data.series.resource.labels as Record<string, string> | undefined} />
      </CardHeader>

      <CardContent className="p-4">
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={chartData}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="hsl(var(--border))"
              opacity={0.5}
            />

            <XAxis
              dataKey="displayTime"
              stroke="hsl(var(--muted-foreground))"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />

            <YAxis
              stroke="hsl(var(--muted-foreground))"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => value.toFixed(0)}
              domain={["auto", "auto"]}
            />

            <RechartsTooltip content={<CustomTooltip />} />

            {/* Incident window reference area */}
            {incidentStart && incidentEnd && (
              <ReferenceArea
                x1={incidentStart}
                x2={incidentEnd}
                fill="hsl(0, 84%, 60%)"
                fillOpacity={0.1}
                stroke="hsl(0, 84%, 60%)"
                strokeOpacity={0.3}
                strokeDasharray="4 4"
              />
            )}

            {/* Main line */}
            <Line
              type="monotone"
              dataKey="value"
              stroke="hsl(var(--primary))"
              strokeWidth={1.5}
              dot={false}
              activeDot={{
                r: 4,
                fill: "hsl(var(--primary))",
                stroke: "hsl(var(--background))",
                strokeWidth: 2,
              }}
            />

            {/* Anomaly dots */}
            {data.anomalies.map((anomaly, idx) => {
              const point = chartData.find(
                (d) =>
                  new Date(d.timestamp).getTime() ===
                  new Date(anomaly.timestamp).getTime()
              );
              if (!point) return null;

              return (
                <ReferenceDot
                  key={idx}
                  x={point.displayTime}
                  y={anomaly.value}
                  r={6}
                  fill={
                    anomaly.severity === "critical"
                      ? "hsl(0, 84%, 60%)"
                      : anomaly.severity === "high"
                        ? "hsl(38, 92%, 50%)"
                        : "hsl(38, 92%, 50%)"
                  }
                  stroke="hsl(var(--background))"
                  strokeWidth={2}
                />
              );
            })}

            <Legend
              verticalAlign="bottom"
              height={36}
              content={() => (
                <div className="flex items-center justify-center gap-6 mt-2 text-xs">
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-0.5 bg-primary rounded" />
                    <span className="text-muted-foreground">{metricName}</span>
                  </div>
                  {incidentStart && (
                    <div className="flex items-center gap-1.5">
                      <div className="w-3 h-3 bg-red-500/20 border border-red-500/50 rounded" />
                      <span className="text-muted-foreground">
                        Incident Window
                      </span>
                    </div>
                  )}
                  {data.anomalies.length > 0 && (
                    <div className="flex items-center gap-1.5">
                      <div className="w-3 h-3 bg-red-500 rounded-full" />
                      <span className="text-muted-foreground">Anomaly</span>
                    </div>
                  )}
                </div>
              )}
            />
          </LineChart>
        </ResponsiveContainer>

        {/* Anomaly list */}
        {data.anomalies.length > 0 && (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs text-muted-foreground mb-2">
              Detected Anomalies
            </p>
            <div className="space-y-2">
              {data.anomalies.map((anomaly, idx) => (
                <div
                  key={idx}
                  className={cn(
                    "flex items-start gap-3 p-2 rounded text-xs",
                    anomaly.severity === "critical"
                      ? "bg-red-900/20 border border-red-900/50"
                      : anomaly.severity === "high"
                        ? "bg-orange-900/20 border border-orange-900/50"
                        : "bg-yellow-900/20 border border-yellow-900/50"
                  )}
                >
                  <AlertCircle
                    className={cn(
                      "h-4 w-4 mt-0.5 flex-shrink-0",
                      anomaly.severity === "critical"
                        ? "text-red-400"
                        : anomaly.severity === "high"
                          ? "text-orange-400"
                          : "text-yellow-400"
                    )}
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-mono">
                        {format(new Date(anomaly.timestamp), "HH:mm:ss")}
                      </span>
                      <Badge
                        variant={
                          anomaly.severity === "critical"
                            ? "critical"
                            : anomaly.severity === "high"
                              ? "error"
                              : "warning"
                        }
                        className="text-xs"
                      >
                        {anomaly.severity.toUpperCase()}
                      </Badge>
                    </div>
                    <p className="text-muted-foreground">
                      Value: {anomaly.value.toFixed(2)}
                      {anomaly.expected_value && (
                        <> (expected: {anomaly.expected_value.toFixed(2)})</>
                      )}
                    </p>
                    {anomaly.description && (
                      <p className="text-foreground mt-1">
                        {anomaly.description}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default MetricCorrelationChart;
