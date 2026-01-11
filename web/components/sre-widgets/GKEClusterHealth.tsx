/**
 * GKE Cluster Health Dashboard Component
 *
 * Provides comprehensive visualization of GKE cluster health including:
 * - Cluster status overview
 * - Node pool health
 * - Pod status distribution
 * - Resource utilization
 */

"use client";

import React from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Server,
  Cpu,
  MemoryStick,
  HardDrive,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
  Box,
  Layers,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

export interface ClusterHealth {
  name: string;
  location: string;
  status: "RUNNING" | "PROVISIONING" | "STOPPING" | "ERROR" | "DEGRADED";
  version: string;
  nodeCount: number;
  nodePools: NodePool[];
  controlPlane: ControlPlaneStatus;
  workloads: WorkloadSummary;
  resources: ResourceUtilization;
  recentEvents: ClusterEvent[];
}

export interface NodePool {
  name: string;
  status: "RUNNING" | "PROVISIONING" | "STOPPING" | "ERROR" | "RECONCILING";
  nodeCount: number;
  machineType: string;
  diskSizeGb: number;
  autoscaling?: {
    enabled: boolean;
    minNodeCount: number;
    maxNodeCount: number;
  };
  conditions: NodeCondition[];
}

export interface NodeCondition {
  type: "Ready" | "MemoryPressure" | "DiskPressure" | "PIDPressure" | "NetworkUnavailable";
  status: "True" | "False" | "Unknown";
  reason?: string;
  message?: string;
  lastTransitionTime?: string;
}

export interface ControlPlaneStatus {
  status: "RUNNING" | "UPDATING" | "ERROR";
  version: string;
  lastHealthCheck: string;
}

export interface WorkloadSummary {
  totalPods: number;
  runningPods: number;
  pendingPods: number;
  failedPods: number;
  deployments: {
    total: number;
    available: number;
    progressing: number;
    failed: number;
  };
  services: number;
  configMaps: number;
  secrets: number;
}

export interface ResourceUtilization {
  cpu: {
    requested: number;
    limit: number;
    used: number;
    allocatable: number;
  };
  memory: {
    requestedGb: number;
    limitGb: number;
    usedGb: number;
    allocatableGb: number;
  };
  storage: {
    usedGb: number;
    totalGb: number;
  };
}

export interface ClusterEvent {
  type: "Normal" | "Warning";
  reason: string;
  message: string;
  source: string;
  timestamp: string;
  count: number;
}

// =============================================================================
// Sub-components
// =============================================================================

function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }> = {
    RUNNING: { variant: "default", icon: <CheckCircle className="w-3 h-3" /> },
    PROVISIONING: { variant: "secondary", icon: <Clock className="w-3 h-3 animate-spin" /> },
    STOPPING: { variant: "secondary", icon: <Clock className="w-3 h-3" /> },
    ERROR: { variant: "destructive", icon: <XCircle className="w-3 h-3" /> },
    DEGRADED: { variant: "destructive", icon: <AlertTriangle className="w-3 h-3" /> },
    RECONCILING: { variant: "secondary", icon: <Activity className="w-3 h-3 animate-pulse" /> },
    UPDATING: { variant: "secondary", icon: <Activity className="w-3 h-3 animate-pulse" /> },
  };

  const config = statusConfig[status] || { variant: "outline" as const, icon: null };

  return (
    <Badge variant={config.variant} className="gap-1">
      {config.icon}
      {status}
    </Badge>
  );
}

function ResourceGauge({
  label,
  used,
  total,
  icon: Icon,
  unit = "",
  warningThreshold = 70,
  criticalThreshold = 90,
}: {
  label: string;
  used: number;
  total: number;
  icon: typeof Cpu;
  unit?: string;
  warningThreshold?: number;
  criticalThreshold?: number;
}) {
  const percentage = total > 0 ? (used / total) * 100 : 0;
  const status = percentage >= criticalThreshold ? "critical" : percentage >= warningThreshold ? "warning" : "normal";

  const statusColors: Record<string, string> = {
    normal: "bg-success",
    warning: "bg-warning",
    critical: "bg-error",
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Icon className="w-4 h-4" />
          <span>{label}</span>
        </div>
        <span className="font-mono">
          {used.toFixed(1)}{unit} / {total.toFixed(1)}{unit}
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full transition-all ${statusColors[status]}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      <div className="text-xs text-muted-foreground text-right">
        {percentage.toFixed(1)}% utilized
      </div>
    </div>
  );
}

function NodePoolCard({ pool }: { pool: NodePool }) {
  const healthyConditions = pool.conditions.filter((c) => c.status === "False" || (c.type === "Ready" && c.status === "True"));
  const unhealthyConditions = pool.conditions.filter((c) => c.status === "True" && c.type !== "Ready");

  return (
    <Card className="border-l-4 border-l-primary">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-primary" />
            <CardTitle className="text-base">{pool.name}</CardTitle>
          </div>
          <StatusBadge status={pool.status} />
        </div>
        <CardDescription>
          {pool.machineType} • {pool.nodeCount} nodes • {pool.diskSizeGb}GB disk
        </CardDescription>
      </CardHeader>
      <CardContent>
        {pool.autoscaling?.enabled && (
          <div className="text-xs text-muted-foreground mb-2">
            Autoscaling: {pool.autoscaling.minNodeCount} - {pool.autoscaling.maxNodeCount} nodes
          </div>
        )}
        <div className="flex flex-wrap gap-1">
          {pool.conditions.map((condition) => (
            <Badge
              key={condition.type}
              variant={
                condition.type === "Ready"
                  ? condition.status === "True" ? "default" : "destructive"
                  : condition.status === "False" ? "outline" : "destructive"
              }
              className="text-xs"
            >
              {condition.type}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function PodStatusChart({ workloads }: { workloads: WorkloadSummary }) {
  const { runningPods, pendingPods, failedPods, totalPods } = workloads;
  const runningPercent = totalPods > 0 ? (runningPods / totalPods) * 100 : 0;
  const pendingPercent = totalPods > 0 ? (pendingPods / totalPods) * 100 : 0;
  const failedPercent = totalPods > 0 ? (failedPods / totalPods) * 100 : 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Pod Status</span>
        <span className="text-sm text-muted-foreground">{totalPods} total</span>
      </div>
      <div className="h-4 bg-muted rounded-full overflow-hidden flex">
        <div className="bg-success h-full" style={{ width: `${runningPercent}%` }} />
        <div className="bg-warning h-full" style={{ width: `${pendingPercent}%` }} />
        <div className="bg-error h-full" style={{ width: `${failedPercent}%` }} />
      </div>
      <div className="flex justify-between text-xs">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-success" />
          Running: {runningPods}
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-warning" />
          Pending: {pendingPods}
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-error" />
          Failed: {failedPods}
        </span>
      </div>
    </div>
  );
}

function EventsList({ events }: { events: ClusterEvent[] }) {
  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-2">
        {events.map((event, idx) => (
          <div
            key={idx}
            className={`p-2 rounded text-xs ${
              event.type === "Warning" ? "bg-warning/10 border-l-2 border-warning" : "bg-muted"
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium">{event.reason}</span>
              <span className="text-muted-foreground">{event.count}x</span>
            </div>
            <p className="text-muted-foreground line-clamp-2">{event.message}</p>
            <div className="flex items-center justify-between mt-1 text-muted-foreground">
              <span>{event.source}</span>
              <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export interface GKEClusterHealthProps {
  cluster: ClusterHealth;
  onNodePoolClick?: (pool: NodePool) => void;
  onEventClick?: (event: ClusterEvent) => void;
}

export function GKEClusterHealth({ cluster, onNodePoolClick, onEventClick }: GKEClusterHealthProps) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Server className="w-6 h-6 text-primary" />
              </div>
              <div>
                <CardTitle>{cluster.name}</CardTitle>
                <CardDescription>
                  {cluster.location} • v{cluster.version} • {cluster.nodeCount} nodes
                </CardDescription>
              </div>
            </div>
            <StatusBadge status={cluster.status} />
          </div>
        </CardHeader>
      </Card>

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="nodes">Node Pools</TabsTrigger>
          <TabsTrigger value="workloads">Workloads</TabsTrigger>
          <TabsTrigger value="events">Events</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Resource Utilization */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Resource Utilization</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <ResourceGauge
                  label="CPU"
                  used={cluster.resources.cpu.used}
                  total={cluster.resources.cpu.allocatable}
                  icon={Cpu}
                  unit=" cores"
                />
                <ResourceGauge
                  label="Memory"
                  used={cluster.resources.memory.usedGb}
                  total={cluster.resources.memory.allocatableGb}
                  icon={MemoryStick}
                  unit=" GB"
                />
                <ResourceGauge
                  label="Storage"
                  used={cluster.resources.storage.usedGb}
                  total={cluster.resources.storage.totalGb}
                  icon={HardDrive}
                  unit=" GB"
                />
              </CardContent>
            </Card>

            {/* Pod Status */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Workload Health</CardTitle>
              </CardHeader>
              <CardContent>
                <PodStatusChart workloads={cluster.workloads} />
                <div className="mt-4 pt-4 border-t grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Deployments</span>
                    <p className="font-mono">
                      {cluster.workloads.deployments.available}/{cluster.workloads.deployments.total}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Services</span>
                    <p className="font-mono">{cluster.workloads.services}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Control Plane Status */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Control Plane</CardTitle>
                <StatusBadge status={cluster.controlPlane.status} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground">
                Version: {cluster.controlPlane.version} • Last health check:{" "}
                {new Date(cluster.controlPlane.lastHealthCheck).toLocaleString()}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Node Pools Tab */}
        <TabsContent value="nodes" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cluster.nodePools.map((pool) => (
              <div key={pool.name} onClick={() => onNodePoolClick?.(pool)} className="cursor-pointer">
                <NodePoolCard pool={pool} />
              </div>
            ))}
          </div>
        </TabsContent>

        {/* Workloads Tab */}
        <TabsContent value="workloads">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Workload Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-lg bg-muted text-center">
                  <Box className="w-6 h-6 mx-auto mb-2 text-primary" />
                  <p className="text-2xl font-bold">{cluster.workloads.totalPods}</p>
                  <p className="text-xs text-muted-foreground">Total Pods</p>
                </div>
                <div className="p-4 rounded-lg bg-muted text-center">
                  <Layers className="w-6 h-6 mx-auto mb-2 text-primary" />
                  <p className="text-2xl font-bold">{cluster.workloads.deployments.total}</p>
                  <p className="text-xs text-muted-foreground">Deployments</p>
                </div>
                <div className="p-4 rounded-lg bg-muted text-center">
                  <Activity className="w-6 h-6 mx-auto mb-2 text-primary" />
                  <p className="text-2xl font-bold">{cluster.workloads.services}</p>
                  <p className="text-xs text-muted-foreground">Services</p>
                </div>
                <div className="p-4 rounded-lg bg-muted text-center">
                  <Server className="w-6 h-6 mx-auto mb-2 text-primary" />
                  <p className="text-2xl font-bold">{cluster.nodeCount}</p>
                  <p className="text-xs text-muted-foreground">Nodes</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Events Tab */}
        <TabsContent value="events">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Recent Events</CardTitle>
                <Badge variant="outline">
                  {cluster.recentEvents.filter((e) => e.type === "Warning").length} warnings
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <EventsList events={cluster.recentEvents} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default GKEClusterHealth;
