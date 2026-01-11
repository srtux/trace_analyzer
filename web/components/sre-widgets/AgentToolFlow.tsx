/**
 * Agent Tool Execution Flow Visualization
 *
 * Real-time visualization of agent tool calls including:
 * - Hierarchical tool call tree
 * - Streaming argument display
 * - Result visualization
 * - Status indicators and duration tracking
 * - Error handling display
 */

"use client";

import React, { useState, useMemo, useCallback, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ChevronRight,
  ChevronDown,
  Play,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  Wrench,
  Code,
  FileJson,
  AlertTriangle,
  Copy,
  Check,
  Maximize2,
  Minimize2,
  Activity,
  Layers,
  Zap,
} from "lucide-react";
import { formatDuration } from "@/lib/utils";

// =============================================================================
// Types
// =============================================================================

export type ToolCallStatus = "pending" | "running" | "streaming" | "completed" | "error";

export interface ToolCall {
  id: string;
  toolName: string;
  displayName?: string;
  description?: string;
  status: ToolCallStatus;
  args: Record<string, unknown>;
  argsStreaming?: string; // For streaming args display
  result?: unknown;
  error?: {
    code: string;
    message: string;
    stack?: string;
  };
  startTime: string;
  endTime?: string;
  durationMs?: number;
  parentId?: string;
  children?: ToolCall[];
  metadata?: {
    agentName?: string;
    category?: string;
    isRetry?: boolean;
    retryCount?: number;
  };
}

export interface AgentRun {
  runId: string;
  status: "idle" | "running" | "completed" | "error";
  agentName: string;
  startTime: string;
  endTime?: string;
  toolCalls: ToolCall[];
  totalToolCalls: number;
  completedToolCalls: number;
  errorCount: number;
}

// =============================================================================
// Tool Icons by Category
// =============================================================================

const TOOL_ICONS: Record<string, React.ReactNode> = {
  // Trace tools
  fetch_trace: <Activity className="w-4 h-4" />,
  list_traces: <Layers className="w-4 h-4" />,
  compare_span_timings: <Activity className="w-4 h-4" />,
  analyze_critical_path: <Zap className="w-4 h-4" />,
  // Log tools
  list_log_entries: <FileJson className="w-4 h-4" />,
  extract_log_patterns: <Code className="w-4 h-4" />,
  // Default
  default: <Wrench className="w-4 h-4" />,
};

const getToolIcon = (toolName: string) => {
  return TOOL_ICONS[toolName] || TOOL_ICONS.default;
};

// =============================================================================
// Status Configuration
// =============================================================================

const STATUS_CONFIG: Record<ToolCallStatus, {
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  label: string;
}> = {
  pending: {
    icon: <Clock className="w-3 h-3" />,
    color: "text-muted-foreground",
    bgColor: "bg-muted",
    label: "Pending",
  },
  running: {
    icon: <Loader2 className="w-3 h-3 animate-spin" />,
    color: "text-primary",
    bgColor: "bg-primary/10",
    label: "Running",
  },
  streaming: {
    icon: <Loader2 className="w-3 h-3 animate-spin" />,
    color: "text-warning",
    bgColor: "bg-warning/10",
    label: "Streaming",
  },
  completed: {
    icon: <CheckCircle className="w-3 h-3" />,
    color: "text-success",
    bgColor: "bg-success/10",
    label: "Completed",
  },
  error: {
    icon: <XCircle className="w-3 h-3" />,
    color: "text-error",
    bgColor: "bg-error/10",
    label: "Error",
  },
};

// =============================================================================
// Sub-components
// =============================================================================

function StatusBadge({ status }: { status: ToolCallStatus }) {
  const config = STATUS_CONFIG[status];
  return (
    <Badge variant="outline" className={`gap-1 ${config.color} ${config.bgColor}`}>
      {config.icon}
      {config.label}
    </Badge>
  );
}

function DurationDisplay({ startTime, endTime, status }: {
  startTime: string;
  endTime?: string;
  status: ToolCallStatus;
}) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (status !== "running" && status !== "streaming") {
      if (endTime) {
        const duration = new Date(endTime).getTime() - new Date(startTime).getTime();
        setElapsed(duration);
      }
      return;
    }

    const interval = setInterval(() => {
      const now = new Date().getTime();
      const start = new Date(startTime).getTime();
      setElapsed(now - start);
    }, 100);

    return () => clearInterval(interval);
  }, [startTime, endTime, status]);

  return (
    <span className="font-mono text-xs text-muted-foreground">
      {formatDuration(elapsed)}
    </span>
  );
}

function JsonViewer({ data, maxHeight = 200 }: { data: unknown; maxHeight?: number }) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const jsonString = useMemo(() => {
    try {
      return JSON.stringify(data, null, 2);
    } catch {
      return String(data);
    }
  }, [data]);

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group">
      <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={handleCopy}
        >
          {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
        </Button>
      </div>
      <ScrollArea
        className="rounded-md bg-muted/50 border"
        style={{ maxHeight: expanded ? "none" : maxHeight }}
      >
        <pre className="p-3 text-xs font-mono overflow-x-auto">
          <code className="text-foreground">{jsonString}</code>
        </pre>
      </ScrollArea>
    </div>
  );
}

function StreamingArgsDisplay({ content }: { content: string }) {
  return (
    <div className="rounded-md bg-muted/50 border p-3">
      <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground">
        <Loader2 className="w-3 h-3 animate-spin" />
        <span>Streaming arguments...</span>
      </div>
      <pre className="text-xs font-mono text-foreground whitespace-pre-wrap">
        {content}
        <span className="animate-pulse">▌</span>
      </pre>
    </div>
  );
}

function ToolCallNode({
  call,
  depth = 0,
  isLast = false,
  onSelect,
  selectedId,
}: {
  call: ToolCall;
  depth?: number;
  isLast?: boolean;
  onSelect: (id: string) => void;
  selectedId: string | null;
}) {
  const [isExpanded, setIsExpanded] = useState(true);
  const hasChildren = call.children && call.children.length > 0;
  const isSelected = selectedId === call.id;
  const statusConfig = STATUS_CONFIG[call.status];

  return (
    <div className="relative">
      {/* Tree connector lines */}
      {depth > 0 && (
        <>
          {/* Vertical line from parent */}
          <div
            className="absolute border-l border-muted-foreground/30"
            style={{
              left: (depth - 1) * 24 + 11,
              top: 0,
              height: isLast ? 20 : "100%",
            }}
          />
          {/* Horizontal line to node */}
          <div
            className="absolute border-t border-muted-foreground/30"
            style={{
              left: (depth - 1) * 24 + 11,
              top: 20,
              width: 13,
            }}
          />
        </>
      )}

      {/* Node content */}
      <div
        className={`
          relative flex items-center gap-2 p-2 rounded-lg cursor-pointer
          transition-colors
          ${isSelected ? "bg-primary/10 border border-primary" : "hover:bg-muted/50"}
        `}
        style={{ marginLeft: depth * 24 }}
        onClick={() => onSelect(call.id)}
      >
        {/* Expand/collapse button */}
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            className="p-0.5 hover:bg-muted rounded"
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            )}
          </button>
        ) : (
          <div className="w-5" />
        )}

        {/* Status indicator */}
        <div className={`p-1.5 rounded ${statusConfig.bgColor}`}>
          <span className={statusConfig.color}>{getToolIcon(call.toolName)}</span>
        </div>

        {/* Tool name and info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm truncate">
              {call.displayName || call.toolName}
            </span>
            {call.metadata?.agentName && (
              <Badge variant="outline" className="text-xs">
                {call.metadata.agentName}
              </Badge>
            )}
            {call.metadata?.isRetry && (
              <Badge variant="secondary" className="text-xs">
                Retry #{call.metadata.retryCount}
              </Badge>
            )}
          </div>
          {call.description && (
            <p className="text-xs text-muted-foreground truncate">{call.description}</p>
          )}
        </div>

        {/* Duration and status */}
        <div className="flex items-center gap-2">
          <DurationDisplay
            startTime={call.startTime}
            endTime={call.endTime}
            status={call.status}
          />
          <StatusBadge status={call.status} />
        </div>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div>
          {call.children!.map((child, idx) => (
            <ToolCallNode
              key={child.id}
              call={child}
              depth={depth + 1}
              isLast={idx === call.children!.length - 1}
              onSelect={onSelect}
              selectedId={selectedId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ToolCallDetails({ call }: { call: ToolCall }) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${STATUS_CONFIG[call.status].bgColor}`}>
            <span className={STATUS_CONFIG[call.status].color}>
              {getToolIcon(call.toolName)}
            </span>
          </div>
          <div>
            <h3 className="font-semibold">{call.displayName || call.toolName}</h3>
            <p className="text-sm text-muted-foreground">
              {call.description || `Tool: ${call.toolName}`}
            </p>
          </div>
        </div>
        <StatusBadge status={call.status} />
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-4 p-3 rounded-lg bg-muted/30">
        <div>
          <span className="text-xs text-muted-foreground">Started</span>
          <p className="text-sm font-mono">{new Date(call.startTime).toLocaleTimeString()}</p>
        </div>
        {call.endTime && (
          <div>
            <span className="text-xs text-muted-foreground">Completed</span>
            <p className="text-sm font-mono">{new Date(call.endTime).toLocaleTimeString()}</p>
          </div>
        )}
        <div>
          <span className="text-xs text-muted-foreground">Duration</span>
          <p className="text-sm font-mono">
            {call.durationMs ? formatDuration(call.durationMs) : "-"}
          </p>
        </div>
        <div>
          <span className="text-xs text-muted-foreground">Tool ID</span>
          <p className="text-sm font-mono truncate">{call.id}</p>
        </div>
      </div>

      <Tabs defaultValue="args" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="args">Arguments</TabsTrigger>
          <TabsTrigger value="result">Result</TabsTrigger>
          <TabsTrigger value="error" disabled={call.status !== "error"}>
            Error
          </TabsTrigger>
        </TabsList>

        <TabsContent value="args" className="mt-4">
          {call.status === "streaming" && call.argsStreaming ? (
            <StreamingArgsDisplay content={call.argsStreaming} />
          ) : Object.keys(call.args).length > 0 ? (
            <JsonViewer data={call.args} maxHeight={300} />
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">
              No arguments provided
            </p>
          )}
        </TabsContent>

        <TabsContent value="result" className="mt-4">
          {call.status === "running" || call.status === "streaming" ? (
            <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Waiting for result...</span>
            </div>
          ) : call.result !== undefined ? (
            <JsonViewer data={call.result} maxHeight={400} />
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">
              No result available
            </p>
          )}
        </TabsContent>

        <TabsContent value="error" className="mt-4">
          {call.error ? (
            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-error/10 border border-error/30">
                <div className="flex items-center gap-2 text-error mb-2">
                  <AlertTriangle className="w-4 h-4" />
                  <span className="font-medium">{call.error.code}</span>
                </div>
                <p className="text-sm">{call.error.message}</p>
              </div>
              {call.error.stack && (
                <div>
                  <span className="text-xs text-muted-foreground">Stack Trace</span>
                  <ScrollArea className="h-[200px] mt-1">
                    <pre className="text-xs font-mono p-3 bg-muted/50 rounded">
                      {call.error.stack}
                    </pre>
                  </ScrollArea>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">
              No error information
            </p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function RunStats({ run }: { run: AgentRun }) {
  const successRate = run.totalToolCalls > 0
    ? ((run.completedToolCalls / run.totalToolCalls) * 100).toFixed(0)
    : "0";

  return (
    <div className="grid grid-cols-4 gap-3">
      <div className="p-3 rounded-lg bg-muted/30 text-center">
        <p className="text-xl font-bold">{run.totalToolCalls}</p>
        <p className="text-xs text-muted-foreground">Total Calls</p>
      </div>
      <div className="p-3 rounded-lg bg-success/10 text-center">
        <p className="text-xl font-bold text-success">{run.completedToolCalls}</p>
        <p className="text-xs text-muted-foreground">Completed</p>
      </div>
      <div className="p-3 rounded-lg bg-error/10 text-center">
        <p className="text-xl font-bold text-error">{run.errorCount}</p>
        <p className="text-xs text-muted-foreground">Errors</p>
      </div>
      <div className="p-3 rounded-lg bg-primary/10 text-center">
        <p className="text-xl font-bold text-primary">{successRate}%</p>
        <p className="text-xs text-muted-foreground">Success</p>
      </div>
    </div>
  );
}

// =============================================================================
// Helper Functions
// =============================================================================

function buildToolTree(toolCalls: ToolCall[]): ToolCall[] {
  const callMap = new Map<string, ToolCall>();
  const rootCalls: ToolCall[] = [];

  // First pass: create map
  for (const call of toolCalls) {
    callMap.set(call.id, { ...call, children: [] });
  }

  // Second pass: build tree
  for (const call of toolCalls) {
    const node = callMap.get(call.id)!;
    if (call.parentId && callMap.has(call.parentId)) {
      const parent = callMap.get(call.parentId)!;
      parent.children = parent.children || [];
      parent.children.push(node);
    } else {
      rootCalls.push(node);
    }
  }

  return rootCalls;
}

function findToolCall(calls: ToolCall[], id: string): ToolCall | null {
  for (const call of calls) {
    if (call.id === id) return call;
    if (call.children) {
      const found = findToolCall(call.children, id);
      if (found) return found;
    }
  }
  return null;
}

// =============================================================================
// Main Component
// =============================================================================

export interface AgentToolFlowProps {
  run: AgentRun;
  onToolCallClick?: (call: ToolCall) => void;
  className?: string;
  showStats?: boolean;
  autoSelectLatest?: boolean;
}

export function AgentToolFlow({
  run,
  onToolCallClick,
  className,
  showStats = true,
  autoSelectLatest = true,
}: AgentToolFlowProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Build tree structure
  const toolTree = useMemo(() => buildToolTree(run.toolCalls), [run.toolCalls]);

  // Find selected call
  const selectedCall = useMemo(() => {
    if (!selectedId) return null;
    return findToolCall(toolTree, selectedId);
  }, [selectedId, toolTree]);

  // Auto-select latest running/streaming call
  useEffect(() => {
    if (!autoSelectLatest) return;

    const runningCall = run.toolCalls.find(
      (c) => c.status === "running" || c.status === "streaming"
    );
    if (runningCall) {
      setSelectedId(runningCall.id);
    }
  }, [run.toolCalls, autoSelectLatest]);

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
    const call = findToolCall(toolTree, id);
    if (call) {
      onToolCallClick?.(call);
    }
  }, [toolTree, onToolCallClick]);

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Wrench className="w-5 h-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">Tool Execution Flow</CardTitle>
              <CardDescription>
                {run.agentName} • Run {run.runId.slice(0, 8)}...
              </CardDescription>
            </div>
          </div>
          <Badge
            variant={
              run.status === "running"
                ? "default"
                : run.status === "completed"
                ? "outline"
                : run.status === "error"
                ? "destructive"
                : "secondary"
            }
            className="gap-1"
          >
            {run.status === "running" && <Loader2 className="w-3 h-3 animate-spin" />}
            {run.status === "completed" && <CheckCircle className="w-3 h-3" />}
            {run.status === "error" && <XCircle className="w-3 h-3" />}
            {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {showStats && <RunStats run={run} />}

        <div className={`grid grid-cols-1 ${selectedCall ? "lg:grid-cols-2" : ""} gap-4 mt-4`}>
          {/* Tool Call Tree */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Execution Tree</span>
              <span className="text-xs text-muted-foreground">
                {run.toolCalls.length} tool calls
              </span>
            </div>
            <ScrollArea className="h-[400px] border rounded-lg p-2">
              {toolTree.length > 0 ? (
                <div className="space-y-1">
                  {toolTree.map((call, idx) => (
                    <ToolCallNode
                      key={call.id}
                      call={call}
                      isLast={idx === toolTree.length - 1}
                      onSelect={handleSelect}
                      selectedId={selectedId}
                    />
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                  <Wrench className="w-8 h-8 mb-2 opacity-50" />
                  <p>No tool calls yet</p>
                </div>
              )}
            </ScrollArea>
          </div>

          {/* Selected Call Details */}
          {selectedCall && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Call Details</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedId(null)}
                  className="text-xs"
                >
                  Close
                </Button>
              </div>
              <div className="border rounded-lg p-4 h-[400px] overflow-auto">
                <ToolCallDetails call={selectedCall} />
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default AgentToolFlow;
