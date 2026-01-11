/**
 * Cloud Run Service Dashboard Component
 *
 * Provides comprehensive visualization of Cloud Run service health including:
 * - Service status and revision management
 * - Request latency and error rates
 * - Cold start analysis
 * - Traffic split visualization
 * - Container resource utilization
 */

"use client";

import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
  Legend,
} from "recharts";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Cloud,
  Zap,
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Activity,
  GitBranch,
  Server,
  Gauge,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import { formatDuration } from "@/lib/utils";

// =============================================================================
// Types
// =============================================================================

export interface CloudRunService {
  name: string;
  region: string;
  project: string;
  status: "READY" | "DEPLOYING" | "ERROR" | "UNKNOWN";
  url: string;
  latestRevision: string;
  revisions: Revision[];
  trafficSplit: TrafficSplit[];
  metrics: ServiceMetrics;
  coldStarts: ColdStartAnalysis;
  resourceConfig: ResourceConfig;
  recentRequests: RequestSample[];
}

export interface Revision {
  name: string;
  createTime: string;
  status: "READY" | "DEPLOYING" | "FAILED" | "RETIRED";
  image: string;
  concurrency: number;
  minInstances: number;
  maxInstances: number;
  cpu: string;
  memory: string;
  generation: number;
}

export interface TrafficSplit {
  revisionName: string;
  percent: number;
  tag?: string;
}

export interface ServiceMetrics {
  requestCount: number;
  errorRate: number;
  latencyP50: number;
  latencyP95: number;
  latencyP99: number;
  instanceCount: number;
  cpuUtilization: number;
  memoryUtilization: number;
  requestsPerSecond: number;
  timeSeries: TimeSeriesData[];
}

export interface TimeSeriesData {
  timestamp: string;
  requests: number;
  errors: number;
  latencyP50: number;
  latencyP95: number;
  instances: number;
}

export interface ColdStartAnalysis {
  coldStartCount: number;
  totalRequests: number;
  coldStartRate: number;
  avgColdStartLatency: number;
  avgWarmLatency: number;
  coldStartImpact: number; // % of latency attributed to cold starts
  coldStartsByHour: { hour: number; count: number }[];
}

export interface ResourceConfig {
  cpu: string;
  memory: string;
  minInstances: number;
  maxInstances: number;
  concurrency: number;
  timeout: number;
  executionEnvironment: "gen1" | "gen2";
}

export interface RequestSample {
  timestamp: string;
  path: string;
  method: string;
  status: number;
  latencyMs: number;
  isColdStart: boolean;
  instanceId: string;
}

// =============================================================================
// Sub-components
// =============================================================================

function ServiceStatusBadge({ status }: { status: string }) {
  const config: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }> = {
    READY: { variant: "default", icon: <CheckCircle className="w-3 h-3" /> },
    DEPLOYING: { variant: "secondary", icon: <Clock className="w-3 h-3 animate-spin" /> },
    ERROR: { variant: "destructive", icon: <XCircle className="w-3 h-3" /> },
    UNKNOWN: { variant: "outline", icon: <AlertTriangle className="w-3 h-3" /> },
  };

  const { variant, icon } = config[status] || config.UNKNOWN;

  return (
    <Badge variant={variant} className="gap-1">
      {icon}
      {status}
    </Badge>
  );
}

function MetricCard({
  label,
  value,
  unit,
  trend,
  trendValue,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  unit?: string;
  trend?: "up" | "down" | "stable";
  trendValue?: string;
  icon: typeof Activity;
}) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor = trend === "down" ? "text-success" : trend === "up" ? "text-warning" : "text-muted-foreground";

  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-center justify-between">
          <Icon className="w-4 h-4 text-muted-foreground" />
          {trend && (
            <div className={`flex items-center gap-1 text-xs ${trendColor}`}>
              <TrendIcon className="w-3 h-3" />
              {trendValue}
            </div>
          )}
        </div>
        <div className="mt-2">
          <span className="text-2xl font-bold">{value}</span>
          {unit && <span className="text-sm text-muted-foreground ml-1">{unit}</span>}
        </div>
        <p className="text-xs text-muted-foreground mt-1">{label}</p>
      </CardContent>
    </Card>
  );
}

function TrafficSplitChart({ splits }: { splits: TrafficSplit[] }) {
  const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

  return (
    <div className="space-y-4">
      <div className="h-4 rounded-full overflow-hidden flex bg-muted">
        {splits.map((split, idx) => (
          <div
            key={split.revisionName}
            className="h-full transition-all"
            style={{
              width: `${split.percent}%`,
              backgroundColor: COLORS[idx % COLORS.length],
            }}
          />
        ))}
      </div>
      <div className="space-y-2">
        {splits.map((split, idx) => (
          <div key={split.revisionName} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: COLORS[idx % COLORS.length] }}
              />
              <span className="font-mono text-xs">{split.revisionName}</span>
              {split.tag && <Badge variant="outline" className="text-xs">{split.tag}</Badge>}
            </div>
            <span className="font-medium">{split.percent}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LatencyChart({ data }: { data: TimeSeriesData[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="latencyP50" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="latencyP95" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
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
          tickFormatter={(value) => `${value}ms`}
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
          formatter={(value: number) => [`${value}ms`, ""]}
        />
        <Area
          type="monotone"
          dataKey="latencyP95"
          stroke="#f59e0b"
          fill="url(#latencyP95)"
          name="P95 Latency"
        />
        <Area
          type="monotone"
          dataKey="latencyP50"
          stroke="#3b82f6"
          fill="url(#latencyP50)"
          name="P50 Latency"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function ColdStartChart({ coldStarts }: { coldStarts: ColdStartAnalysis }) {
  const hourlyData = coldStarts.coldStartsByHour.map((d) => ({
    hour: `${d.hour}:00`,
    count: d.count,
  }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4 text-center">
        <div>
          <p className="text-2xl font-bold">{coldStarts.coldStartRate.toFixed(1)}%</p>
          <p className="text-xs text-muted-foreground">Cold Start Rate</p>
        </div>
        <div>
          <p className="text-2xl font-bold">{formatDuration(coldStarts.avgColdStartLatency)}</p>
          <p className="text-xs text-muted-foreground">Avg Cold Start</p>
        </div>
        <div>
          <p className="text-2xl font-bold">{formatDuration(coldStarts.avgWarmLatency)}</p>
          <p className="text-xs text-muted-foreground">Avg Warm</p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={150}>
        <BarChart data={hourlyData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="hour" stroke="hsl(var(--muted-foreground))" fontSize={10} />
          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={10} />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
            }}
          />
          <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} name="Cold Starts" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function RevisionsList({ revisions }: { revisions: Revision[] }) {
  return (
    <ScrollArea className="h-[300px]">
      <div className="space-y-3">
        {revisions.map((rev) => (
          <Card key={rev.name} className="border-l-4 border-l-primary">
            <CardContent className="p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <GitBranch className="w-4 h-4 text-primary" />
                  <span className="font-mono text-sm">{rev.name}</span>
                </div>
                <ServiceStatusBadge status={rev.status} />
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div>CPU: {rev.cpu}</div>
                <div>Memory: {rev.memory}</div>
                <div>Concurrency: {rev.concurrency}</div>
                <div>Instances: {rev.minInstances}-{rev.maxInstances}</div>
              </div>
              <p className="text-xs text-muted-foreground mt-2 truncate">
                {rev.image}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </ScrollArea>
  );
}

function RecentRequestsTable({ requests }: { requests: RequestSample[] }) {
  return (
    <ScrollArea className="h-[200px]">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-background">
          <tr className="border-b text-left">
            <th className="pb-2 font-medium">Time</th>
            <th className="pb-2 font-medium">Path</th>
            <th className="pb-2 font-medium">Status</th>
            <th className="pb-2 font-medium">Latency</th>
            <th className="pb-2 font-medium">Cold</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((req, idx) => (
            <tr key={idx} className="border-b border-muted">
              <td className="py-2 text-muted-foreground">
                {new Date(req.timestamp).toLocaleTimeString()}
              </td>
              <td className="py-2 font-mono text-xs">
                <span className="text-primary">{req.method}</span> {req.path}
              </td>
              <td className="py-2">
                <Badge
                  variant={req.status < 400 ? "default" : req.status < 500 ? "secondary" : "destructive"}
                  className="text-xs"
                >
                  {req.status}
                </Badge>
              </td>
              <td className="py-2 font-mono">{req.latencyMs}ms</td>
              <td className="py-2">
                {req.isColdStart && <Zap className="w-4 h-4 text-warning" />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollArea>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export interface CloudRunDashboardProps {
  service: CloudRunService;
  onRevisionClick?: (revision: Revision) => void;
  onRequestClick?: (request: RequestSample) => void;
}

export function CloudRunDashboard({ service, onRevisionClick, onRequestClick }: CloudRunDashboardProps) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Cloud className="w-6 h-6 text-primary" />
              </div>
              <div>
                <CardTitle>{service.name}</CardTitle>
                <CardDescription>
                  {service.region} • {service.project}
                </CardDescription>
              </div>
            </div>
            <ServiceStatusBadge status={service.status} />
          </div>
          <a
            href={service.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary hover:underline mt-2 block"
          >
            {service.url}
          </a>
        </CardHeader>
      </Card>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Requests/sec"
          value={service.metrics.requestsPerSecond.toFixed(1)}
          icon={Activity}
          trend="up"
          trendValue="+12%"
        />
        <MetricCard
          label="Error Rate"
          value={service.metrics.errorRate.toFixed(2)}
          unit="%"
          icon={AlertTriangle}
          trend={service.metrics.errorRate > 1 ? "up" : "down"}
          trendValue={service.metrics.errorRate > 1 ? "+0.5%" : "-0.3%"}
        />
        <MetricCard
          label="P95 Latency"
          value={service.metrics.latencyP95.toFixed(0)}
          unit="ms"
          icon={Gauge}
        />
        <MetricCard
          label="Instances"
          value={service.metrics.instanceCount}
          icon={Server}
        />
      </div>

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="traffic">Traffic</TabsTrigger>
          <TabsTrigger value="coldstarts">Cold Starts</TabsTrigger>
          <TabsTrigger value="revisions">Revisions</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Latency Over Time</CardTitle>
            </CardHeader>
            <CardContent>
              <LatencyChart data={service.metrics.timeSeries} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent Requests</CardTitle>
            </CardHeader>
            <CardContent>
              <RecentRequestsTable requests={service.recentRequests} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Traffic Tab */}
        <TabsContent value="traffic">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Traffic Split</CardTitle>
              <CardDescription>Current traffic distribution across revisions</CardDescription>
            </CardHeader>
            <CardContent>
              <TrafficSplitChart splits={service.trafficSplit} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Cold Starts Tab */}
        <TabsContent value="coldstarts">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Cold Start Analysis</CardTitle>
              <CardDescription>
                Cold starts account for {service.coldStarts.coldStartImpact.toFixed(1)}% of total latency
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ColdStartChart coldStarts={service.coldStarts} />
            </CardContent>
          </Card>

          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Min Instances</span>
                  <p className="font-mono">{service.resourceConfig.minInstances}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Max Instances</span>
                  <p className="font-mono">{service.resourceConfig.maxInstances}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Concurrency</span>
                  <p className="font-mono">{service.resourceConfig.concurrency}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">CPU</span>
                  <p className="font-mono">{service.resourceConfig.cpu}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Memory</span>
                  <p className="font-mono">{service.resourceConfig.memory}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Environment</span>
                  <p className="font-mono">{service.resourceConfig.executionEnvironment}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Revisions Tab */}
        <TabsContent value="revisions">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Revision History</CardTitle>
              <CardDescription>
                Latest: {service.latestRevision}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RevisionsList revisions={service.revisions} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default CloudRunDashboard;
