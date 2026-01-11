/**
 * SLO/SLI Dashboard Component
 *
 * Provides comprehensive SRE golden signals visualization including:
 * - SLO compliance tracking
 * - Error budget burn rate analysis
 * - SLI metrics visualization
 * - Alert threshold management
 */

"use client";

import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from "recharts";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Target,
  AlertTriangle,
  CheckCircle,
  XCircle,
  TrendingDown,
  TrendingUp,
  Clock,
  Flame,
  Shield,
  Activity,
  BarChart3,
  Gauge,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

export interface SLO {
  name: string;
  displayName: string;
  service: string;
  goal: number; // Target SLO percentage (e.g., 99.9)
  rollingPeriodDays: number;
  sliType: "availability" | "latency" | "throughput" | "error_rate" | "freshness";
  currentCompliance: number;
  status: "healthy" | "warning" | "critical" | "breached";
  errorBudget: ErrorBudget;
  burnRate: BurnRate;
  timeSeries: SLOTimeSeriesPoint[];
  alerts: SLOAlert[];
}

export interface ErrorBudget {
  totalMinutes: number;
  consumedMinutes: number;
  remainingMinutes: number;
  consumedPercent: number;
  projectedExhaustionDate?: string;
  burnRateLast1h: number;
  burnRateLast6h: number;
  burnRateLast24h: number;
}

export interface BurnRate {
  current: number;
  shortWindow: number;
  longWindow: number;
  alertThreshold: number;
  status: "normal" | "elevated" | "critical";
}

export interface SLOTimeSeriesPoint {
  timestamp: string;
  compliance: number;
  errorBudgetRemaining: number;
  burnRate: number;
}

export interface SLOAlert {
  id: string;
  type: "fast_burn" | "slow_burn" | "budget_exhausted" | "compliance_drop";
  severity: "warning" | "critical";
  message: string;
  triggeredAt: string;
  acknowledged: boolean;
}

export interface GoldenSignals {
  latency: {
    p50: number;
    p95: number;
    p99: number;
    trend: "up" | "down" | "stable";
    trendPercent: number;
  };
  traffic: {
    requestsPerSecond: number;
    trend: "up" | "down" | "stable";
    trendPercent: number;
  };
  errors: {
    rate: number;
    count: number;
    trend: "up" | "down" | "stable";
    trendPercent: number;
  };
  saturation: {
    cpu: number;
    memory: number;
    connections: number;
  };
}

// =============================================================================
// Sub-components
// =============================================================================

function SLOStatusBadge({ status }: { status: string }) {
  const config: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }> = {
    healthy: { variant: "default", icon: <CheckCircle className="w-3 h-3" /> },
    warning: { variant: "secondary", icon: <AlertTriangle className="w-3 h-3" /> },
    critical: { variant: "destructive", icon: <Flame className="w-3 h-3" /> },
    breached: { variant: "destructive", icon: <XCircle className="w-3 h-3" /> },
  };

  const { variant, icon } = config[status] || config.healthy;

  return (
    <Badge variant={variant} className="gap-1">
      {icon}
      {status.toUpperCase()}
    </Badge>
  );
}

function ErrorBudgetGauge({ budget }: { budget: ErrorBudget }) {
  const remainingPercent = 100 - budget.consumedPercent;
  const status = remainingPercent < 10 ? "critical" : remainingPercent < 30 ? "warning" : "healthy";

  const statusColors: Record<string, string> = {
    healthy: "bg-success",
    warning: "bg-warning",
    critical: "bg-error",
  };

  const formatMinutes = (minutes: number) => {
    if (minutes < 60) return `${minutes.toFixed(0)}m`;
    if (minutes < 1440) return `${(minutes / 60).toFixed(1)}h`;
    return `${(minutes / 1440).toFixed(1)}d`;
  };

  return (
    <div className="space-y-4">
      <div className="relative pt-4">
        <svg viewBox="0 0 200 100" className="w-full h-32">
          {/* Background arc */}
          <path
            d="M 20 90 A 70 70 0 0 1 180 90"
            fill="none"
            stroke="hsl(var(--muted))"
            strokeWidth="12"
            strokeLinecap="round"
          />
          {/* Foreground arc */}
          <path
            d="M 20 90 A 70 70 0 0 1 180 90"
            fill="none"
            stroke={
              status === "critical"
                ? "hsl(var(--error))"
                : status === "warning"
                ? "hsl(var(--warning))"
                : "hsl(var(--success))"
            }
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${remainingPercent * 2.2} 220`}
          />
          {/* Center text */}
          <text
            x="100"
            y="75"
            textAnchor="middle"
            className="fill-foreground text-3xl font-bold"
          >
            {remainingPercent.toFixed(1)}%
          </text>
          <text
            x="100"
            y="92"
            textAnchor="middle"
            className="fill-muted-foreground text-xs"
          >
            Budget Remaining
          </text>
        </svg>
      </div>

      <div className="grid grid-cols-3 gap-4 text-center text-sm">
        <div>
          <p className="font-mono font-bold">{formatMinutes(budget.remainingMinutes)}</p>
          <p className="text-xs text-muted-foreground">Remaining</p>
        </div>
        <div>
          <p className="font-mono font-bold">{formatMinutes(budget.consumedMinutes)}</p>
          <p className="text-xs text-muted-foreground">Consumed</p>
        </div>
        <div>
          <p className="font-mono font-bold">{formatMinutes(budget.totalMinutes)}</p>
          <p className="text-xs text-muted-foreground">Total</p>
        </div>
      </div>

      {budget.projectedExhaustionDate && (
        <div className="text-center p-2 rounded bg-warning/10 text-warning text-sm">
          <Clock className="w-4 h-4 inline mr-1" />
          Projected exhaustion: {new Date(budget.projectedExhaustionDate).toLocaleDateString()}
        </div>
      )}
    </div>
  );
}

function BurnRateChart({ data }: { data: SLOTimeSeriesPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="burnRateGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="timestamp"
          tickFormatter={(value) => new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          stroke="hsl(var(--muted-foreground))"
          fontSize={10}
        />
        <YAxis
          stroke="hsl(var(--muted-foreground))"
          fontSize={10}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          labelFormatter={(value) => new Date(value).toLocaleString()}
        />
        <ReferenceLine y={1} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: "1x", fill: "#f59e0b", fontSize: 10 }} />
        <ReferenceLine y={6} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "6x Fast", fill: "#ef4444", fontSize: 10 }} />
        <Area
          type="monotone"
          dataKey="burnRate"
          stroke="#ef4444"
          fill="url(#burnRateGradient)"
          name="Burn Rate"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function ComplianceChart({ data, goal }: { data: SLOTimeSeriesPoint[]; goal: number }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="timestamp"
          tickFormatter={(value) => new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          stroke="hsl(var(--muted-foreground))"
          fontSize={10}
        />
        <YAxis
          domain={[Math.min(goal - 2, 95), 100]}
          tickFormatter={(value) => `${value}%`}
          stroke="hsl(var(--muted-foreground))"
          fontSize={10}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          labelFormatter={(value) => new Date(value).toLocaleString()}
          formatter={(value: number) => [`${value.toFixed(3)}%`, "Compliance"]}
        />
        <ReferenceLine y={goal} stroke="#10b981" strokeDasharray="3 3" label={{ value: `SLO: ${goal}%`, fill: "#10b981", fontSize: 10 }} />
        <ReferenceArea y1={goal} y2={100} fill="#10b981" fillOpacity={0.1} />
        <Line
          type="monotone"
          dataKey="compliance"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
          name="Compliance"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function GoldenSignalsPanel({ signals }: { signals: GoldenSignals }) {
  const TrendIcon = ({ trend }: { trend: "up" | "down" | "stable" }) => {
    if (trend === "up") return <TrendingUp className="w-4 h-4" />;
    if (trend === "down") return <TrendingDown className="w-4 h-4" />;
    return <Activity className="w-4 h-4" />;
  };

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Latency */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Gauge className="w-4 h-4" />
            Latency
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-lg font-bold">{signals.latency.p50}ms</p>
              <p className="text-xs text-muted-foreground">P50</p>
            </div>
            <div>
              <p className="text-lg font-bold">{signals.latency.p95}ms</p>
              <p className="text-xs text-muted-foreground">P95</p>
            </div>
            <div>
              <p className="text-lg font-bold">{signals.latency.p99}ms</p>
              <p className="text-xs text-muted-foreground">P99</p>
            </div>
          </div>
          <div className={`flex items-center justify-center gap-1 mt-2 text-xs ${
            signals.latency.trend === "up" ? "text-warning" : "text-success"
          }`}>
            <TrendIcon trend={signals.latency.trend} />
            {signals.latency.trendPercent > 0 ? "+" : ""}{signals.latency.trendPercent}%
          </div>
        </CardContent>
      </Card>

      {/* Traffic */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Traffic
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-center">{signals.traffic.requestsPerSecond.toFixed(1)}</p>
          <p className="text-xs text-muted-foreground text-center">req/sec</p>
          <div className={`flex items-center justify-center gap-1 mt-2 text-xs ${
            signals.traffic.trend === "up" ? "text-success" : "text-muted-foreground"
          }`}>
            <TrendIcon trend={signals.traffic.trend} />
            {signals.traffic.trendPercent > 0 ? "+" : ""}{signals.traffic.trendPercent}%
          </div>
        </CardContent>
      </Card>

      {/* Errors */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Errors
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold text-center">{signals.errors.rate.toFixed(2)}%</p>
          <p className="text-xs text-muted-foreground text-center">{signals.errors.count} errors</p>
          <div className={`flex items-center justify-center gap-1 mt-2 text-xs ${
            signals.errors.trend === "down" ? "text-success" : "text-error"
          }`}>
            <TrendIcon trend={signals.errors.trend} />
            {signals.errors.trendPercent > 0 ? "+" : ""}{signals.errors.trendPercent}%
          </div>
        </CardContent>
      </Card>

      {/* Saturation */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Saturation
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span>CPU</span>
            <span>{signals.saturation.cpu}%</span>
          </div>
          <Progress value={signals.saturation.cpu} className="h-1" />
          <div className="flex items-center justify-between text-xs">
            <span>Memory</span>
            <span>{signals.saturation.memory}%</span>
          </div>
          <Progress value={signals.saturation.memory} className="h-1" />
        </CardContent>
      </Card>
    </div>
  );
}

function AlertsList({ alerts }: { alerts: SLOAlert[] }) {
  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-2">
        {alerts.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">
            <Shield className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No active alerts</p>
          </div>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className={`p-3 rounded-lg border-l-4 ${
                alert.severity === "critical"
                  ? "border-l-error bg-error/10"
                  : "border-l-warning bg-warning/10"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <Badge variant={alert.severity === "critical" ? "destructive" : "secondary"}>
                  {alert.type.replace("_", " ")}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {new Date(alert.triggeredAt).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-sm">{alert.message}</p>
            </div>
          ))
        )}
      </div>
    </ScrollArea>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export interface SLODashboardProps {
  slo: SLO;
  goldenSignals?: GoldenSignals;
  onAlertClick?: (alert: SLOAlert) => void;
}

export function SLODashboard({ slo, goldenSignals, onAlertClick }: SLODashboardProps) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Target className="w-6 h-6 text-primary" />
              </div>
              <div>
                <CardTitle>{slo.displayName}</CardTitle>
                <CardDescription>
                  {slo.service} • {slo.rollingPeriodDays}-day rolling window • {slo.sliType}
                </CardDescription>
              </div>
            </div>
            <SLOStatusBadge status={slo.status} />
          </div>

          {/* Current Compliance */}
          <div className="mt-4 p-4 rounded-lg bg-muted">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Current Compliance</p>
                <p className="text-3xl font-bold">{slo.currentCompliance.toFixed(3)}%</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Target SLO</p>
                <p className="text-3xl font-bold text-success">{slo.goal}%</p>
              </div>
            </div>
            <Progress
              value={(slo.currentCompliance / slo.goal) * 100}
              className="mt-4 h-2"
            />
          </div>
        </CardHeader>
      </Card>

      <Tabs defaultValue="budget" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="budget">Error Budget</TabsTrigger>
          <TabsTrigger value="burnrate">Burn Rate</TabsTrigger>
          <TabsTrigger value="compliance">Compliance</TabsTrigger>
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
        </TabsList>

        {/* Error Budget Tab */}
        <TabsContent value="budget">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Error Budget Status</CardTitle>
              <CardDescription>
                Time-based budget for acceptable SLO violations
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ErrorBudgetGauge budget={slo.errorBudget} />
            </CardContent>
          </Card>

          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Burn Rates</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4 rounded-lg bg-muted">
                  <p className="text-2xl font-bold">{slo.errorBudget.burnRateLast1h.toFixed(2)}x</p>
                  <p className="text-xs text-muted-foreground">Last 1 hour</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-muted">
                  <p className="text-2xl font-bold">{slo.errorBudget.burnRateLast6h.toFixed(2)}x</p>
                  <p className="text-xs text-muted-foreground">Last 6 hours</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-muted">
                  <p className="text-2xl font-bold">{slo.errorBudget.burnRateLast24h.toFixed(2)}x</p>
                  <p className="text-xs text-muted-foreground">Last 24 hours</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Burn Rate Tab */}
        <TabsContent value="burnrate">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Burn Rate Over Time</CardTitle>
              <CardDescription>
                Rate at which error budget is being consumed (1x = normal, &gt;6x = fast burn alert)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <BurnRateChart data={slo.timeSeries} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Compliance Tab */}
        <TabsContent value="compliance">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">SLO Compliance Over Time</CardTitle>
              <CardDescription>
                Service level compliance relative to {slo.goal}% target
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ComplianceChart data={slo.timeSeries} goal={slo.goal} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Alerts Tab */}
        <TabsContent value="alerts">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Active Alerts</CardTitle>
              <CardDescription>
                SLO-based alerts triggered by burn rate or compliance thresholds
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AlertsList alerts={slo.alerts} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Golden Signals */}
      {goldenSignals && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Golden Signals</CardTitle>
            <CardDescription>
              The four golden signals of monitoring: Latency, Traffic, Errors, Saturation
            </CardDescription>
          </CardHeader>
          <CardContent>
            <GoldenSignalsPanel signals={goldenSignals} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default SLODashboard;
