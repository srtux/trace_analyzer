/**
 * Service Dependency Graph Component
 *
 * Interactive visualization of service dependencies with:
 * - DAG layout for service topology
 * - Latency and error rate annotations
 * - Critical path highlighting
 * - Impact blast radius visualization
 */

"use client";

import React, { useCallback, useMemo, useState, useEffect, useRef } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Server,
  Database,
  Cloud,
  Globe,
  MessageSquare,
  Zap,
  AlertTriangle,
  CheckCircle,
  ArrowRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Target,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

export interface ServiceNode {
  id: string;
  name: string;
  type: "service" | "database" | "cache" | "queue" | "external" | "gateway";
  status: "healthy" | "degraded" | "unhealthy" | "unknown";
  metrics: {
    latencyP50: number;
    latencyP99: number;
    errorRate: number;
    requestsPerSecond: number;
  };
  metadata?: Record<string, string>;
  isOnCriticalPath?: boolean;
}

export interface ServiceEdge {
  source: string;
  target: string;
  latencyMs: number;
  errorRate: number;
  requestsPerSecond: number;
  protocol?: "http" | "grpc" | "tcp" | "pubsub";
  isOnCriticalPath?: boolean;
}

export interface ServiceGraph {
  nodes: ServiceNode[];
  edges: ServiceEdge[];
  criticalPath?: string[];
  rootService?: string;
}

// =============================================================================
// Graph Layout Algorithm (Simple Layered DAG)
// =============================================================================

interface LayoutNode {
  id: string;
  x: number;
  y: number;
  layer: number;
}

function computeLayout(graph: ServiceGraph): Map<string, LayoutNode> {
  const nodeMap = new Map<string, ServiceNode>();
  const inDegree = new Map<string, number>();
  const outEdges = new Map<string, string[]>();

  // Initialize
  for (const node of graph.nodes) {
    nodeMap.set(node.id, node);
    inDegree.set(node.id, 0);
    outEdges.set(node.id, []);
  }

  // Calculate in-degrees and out-edges
  for (const edge of graph.edges) {
    inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
    outEdges.get(edge.source)?.push(edge.target);
  }

  // Assign layers using topological sort
  const layers = new Map<string, number>();
  const queue: string[] = [];

  // Start with nodes that have no incoming edges
  for (const [nodeId, degree] of inDegree) {
    if (degree === 0) {
      queue.push(nodeId);
      layers.set(nodeId, 0);
    }
  }

  while (queue.length > 0) {
    const nodeId = queue.shift()!;
    const currentLayer = layers.get(nodeId) || 0;

    for (const targetId of outEdges.get(nodeId) || []) {
      const targetLayer = layers.get(targetId);
      if (targetLayer === undefined || targetLayer < currentLayer + 1) {
        layers.set(targetId, currentLayer + 1);
      }

      const newDegree = (inDegree.get(targetId) || 1) - 1;
      inDegree.set(targetId, newDegree);

      if (newDegree === 0) {
        queue.push(targetId);
      }
    }
  }

  // Handle cycles (nodes not assigned a layer)
  let maxLayer = 0;
  for (const layer of layers.values()) {
    maxLayer = Math.max(maxLayer, layer);
  }
  for (const node of graph.nodes) {
    if (!layers.has(node.id)) {
      layers.set(node.id, maxLayer + 1);
    }
  }

  // Group nodes by layer
  const layerGroups = new Map<number, string[]>();
  for (const [nodeId, layer] of layers) {
    if (!layerGroups.has(layer)) {
      layerGroups.set(layer, []);
    }
    layerGroups.get(layer)!.push(nodeId);
  }

  // Calculate positions
  const layoutNodes = new Map<string, LayoutNode>();
  const layerWidth = 200;
  const nodeHeight = 80;
  const padding = 60;

  for (const [layer, nodeIds] of layerGroups) {
    const totalHeight = nodeIds.length * nodeHeight;
    const startY = -totalHeight / 2;

    nodeIds.forEach((nodeId, index) => {
      layoutNodes.set(nodeId, {
        id: nodeId,
        x: layer * layerWidth + padding,
        y: startY + index * nodeHeight + padding,
        layer,
      });
    });
  }

  return layoutNodes;
}

// =============================================================================
// Sub-components
// =============================================================================

const ServiceIcon = ({ type }: { type: ServiceNode["type"] }) => {
  const icons: Record<string, React.ReactNode> = {
    service: <Server className="w-5 h-5" />,
    database: <Database className="w-5 h-5" />,
    cache: <Zap className="w-5 h-5" />,
    queue: <MessageSquare className="w-5 h-5" />,
    external: <Globe className="w-5 h-5" />,
    gateway: <Cloud className="w-5 h-5" />,
  };
  return icons[type] || icons.service;
};

function NodeCard({
  node,
  layout,
  isSelected,
  onClick,
  showCriticalPath,
}: {
  node: ServiceNode;
  layout: LayoutNode;
  isSelected: boolean;
  onClick: () => void;
  showCriticalPath: boolean;
}) {
  const statusColors: Record<string, string> = {
    healthy: "border-success bg-success/10",
    degraded: "border-warning bg-warning/10",
    unhealthy: "border-error bg-error/10",
    unknown: "border-muted bg-muted/50",
  };

  const criticalPathStyle = showCriticalPath && node.isOnCriticalPath
    ? "ring-2 ring-primary ring-offset-2"
    : "";

  return (
    <g transform={`translate(${layout.x}, ${layout.y})`}>
      <foreignObject width={160} height={70} x={-80} y={-35}>
        <Popover>
          <PopoverTrigger asChild>
            <div
              className={`
                h-full rounded-lg border-2 p-2 cursor-pointer transition-all
                ${statusColors[node.status]}
                ${isSelected ? "ring-2 ring-primary" : ""}
                ${criticalPathStyle}
                hover:scale-105
              `}
              onClick={onClick}
            >
              <div className="flex items-center gap-2 mb-1">
                <ServiceIcon type={node.type} />
                <span className="font-medium text-sm truncate">{node.name}</span>
              </div>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{node.metrics.latencyP50}ms</span>
                <span>{node.metrics.errorRate.toFixed(2)}%</span>
                <span>{node.metrics.requestsPerSecond}/s</span>
              </div>
            </div>
          </PopoverTrigger>
          <PopoverContent className="w-64" side="right">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="font-semibold">{node.name}</h4>
                <Badge variant={node.status === "healthy" ? "default" : "destructive"}>
                  {node.status}
                </Badge>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <p className="text-muted-foreground">P50 Latency</p>
                  <p className="font-mono">{node.metrics.latencyP50}ms</p>
                </div>
                <div>
                  <p className="text-muted-foreground">P99 Latency</p>
                  <p className="font-mono">{node.metrics.latencyP99}ms</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Error Rate</p>
                  <p className="font-mono">{node.metrics.errorRate.toFixed(2)}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">RPS</p>
                  <p className="font-mono">{node.metrics.requestsPerSecond}</p>
                </div>
              </div>
              {node.metadata && (
                <div className="pt-2 border-t">
                  {Object.entries(node.metadata).map(([key, value]) => (
                    <p key={key} className="text-xs text-muted-foreground">
                      {key}: <span className="text-foreground">{value}</span>
                    </p>
                  ))}
                </div>
              )}
            </div>
          </PopoverContent>
        </Popover>
      </foreignObject>
    </g>
  );
}

function EdgeLine({
  edge,
  sourceLayout,
  targetLayout,
  showCriticalPath,
}: {
  edge: ServiceEdge;
  sourceLayout: LayoutNode;
  targetLayout: LayoutNode;
  showCriticalPath: boolean;
}) {
  const isCritical = showCriticalPath && edge.isOnCriticalPath;
  const hasErrors = edge.errorRate > 1;

  // Calculate path
  const startX = sourceLayout.x + 80;
  const startY = sourceLayout.y;
  const endX = targetLayout.x - 80;
  const endY = targetLayout.y;

  // Create curved path
  const midX = (startX + endX) / 2;
  const path = `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`;

  return (
    <g>
      {/* Edge path */}
      <path
        d={path}
        fill="none"
        stroke={isCritical ? "hsl(var(--primary))" : hasErrors ? "hsl(var(--error))" : "hsl(var(--muted-foreground))"}
        strokeWidth={isCritical ? 3 : 1.5}
        strokeDasharray={hasErrors ? "4 2" : undefined}
        markerEnd="url(#arrowhead)"
        opacity={0.7}
      />

      {/* Edge label */}
      <foreignObject
        x={midX - 30}
        y={(startY + endY) / 2 - 12}
        width={60}
        height={24}
      >
        <div className="text-[10px] text-center bg-background/80 rounded px-1 py-0.5 border">
          {edge.latencyMs}ms
        </div>
      </foreignObject>
    </g>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export interface ServiceDependencyGraphProps {
  graph: ServiceGraph;
  onNodeSelect?: (node: ServiceNode | null) => void;
  showCriticalPath?: boolean;
  highlightedNodes?: string[];
  className?: string;
}

export function ServiceDependencyGraph({
  graph,
  onNodeSelect,
  showCriticalPath = false,
  highlightedNodes = [],
  className,
}: ServiceDependencyGraphProps) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  // Compute layout
  const layout = useMemo(() => computeLayout(graph), [graph]);

  // Calculate SVG viewBox
  const viewBox = useMemo(() => {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    for (const node of layout.values()) {
      minX = Math.min(minX, node.x - 100);
      minY = Math.min(minY, node.y - 50);
      maxX = Math.max(maxX, node.x + 100);
      maxY = Math.max(maxY, node.y + 50);
    }

    const width = maxX - minX + 100;
    const height = maxY - minY + 100;

    return { minX: minX - 50, minY: minY - 50, width, height };
  }, [layout]);

  // Get node map for quick lookup
  const nodeMap = useMemo(() => {
    const map = new Map<string, ServiceNode>();
    for (const node of graph.nodes) {
      map.set(node.id, node);
    }
    return map;
  }, [graph.nodes]);

  const handleNodeClick = useCallback((nodeId: string) => {
    setSelectedNode(nodeId === selectedNode ? null : nodeId);
    onNodeSelect?.(nodeId === selectedNode ? null : nodeMap.get(nodeId) || null);
  }, [selectedNode, nodeMap, onNodeSelect]);

  const handleZoomIn = () => setZoom((z) => Math.min(z * 1.2, 3));
  const handleZoomOut = () => setZoom((z) => Math.max(z / 1.2, 0.3));
  const handleReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Target className="w-4 h-4" />
              Service Dependency Graph
            </CardTitle>
            <CardDescription>
              {graph.nodes.length} services • {graph.edges.length} connections
            </CardDescription>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="icon" onClick={handleZoomOut}>
              <ZoomOut className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={handleZoomIn}>
              <ZoomIn className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={handleReset}>
              <Maximize2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="border rounded-lg bg-muted/20 overflow-hidden" style={{ height: 400 }}>
          <svg
            ref={svgRef}
            width="100%"
            height="100%"
            viewBox={`${viewBox.minX / zoom + pan.x} ${viewBox.minY / zoom + pan.y} ${viewBox.width / zoom} ${viewBox.height / zoom}`}
            style={{ cursor: "grab" }}
          >
            {/* Definitions */}
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon
                  points="0 0, 10 3.5, 0 7"
                  fill="hsl(var(--muted-foreground))"
                />
              </marker>
            </defs>

            {/* Edges */}
            <g className="edges">
              {graph.edges.map((edge) => {
                const sourceLayout = layout.get(edge.source);
                const targetLayout = layout.get(edge.target);
                if (!sourceLayout || !targetLayout) return null;

                return (
                  <EdgeLine
                    key={`${edge.source}-${edge.target}`}
                    edge={edge}
                    sourceLayout={sourceLayout}
                    targetLayout={targetLayout}
                    showCriticalPath={showCriticalPath}
                  />
                );
              })}
            </g>

            {/* Nodes */}
            <g className="nodes">
              {graph.nodes.map((node) => {
                const nodeLayout = layout.get(node.id);
                if (!nodeLayout) return null;

                return (
                  <NodeCard
                    key={node.id}
                    node={node}
                    layout={nodeLayout}
                    isSelected={selectedNode === node.id || highlightedNodes.includes(node.id)}
                    onClick={() => handleNodeClick(node.id)}
                    showCriticalPath={showCriticalPath}
                  />
                );
              })}
            </g>
          </svg>
        </div>

        {/* Legend */}
        <div className="flex items-center justify-center gap-6 mt-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded border-2 border-success bg-success/20" />
            <span>Healthy</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded border-2 border-warning bg-warning/20" />
            <span>Degraded</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded border-2 border-error bg-error/20" />
            <span>Unhealthy</span>
          </div>
          {showCriticalPath && (
            <div className="flex items-center gap-1">
              <div className="w-6 h-0.5 bg-primary" />
              <span>Critical Path</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default ServiceDependencyGraph;
