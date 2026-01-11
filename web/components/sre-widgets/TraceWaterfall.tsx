"use client";

import React, { useMemo, useState } from "react";
import { format } from "date-fns";
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Server,
  Database,
  Globe,
  Zap,
  X,
} from "lucide-react";

import { cn, formatDuration, calculateSpanDepth, truncate } from "@/lib/utils";
import type { Trace, SpanInfo } from "@/types/adk-schema";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface TraceWaterfallProps {
  trace: Trace;
  onSpanClick?: (span: SpanInfo) => void;
  highlightSpanId?: string;
  className?: string;
}

interface ProcessedSpan extends SpanInfo {
  depth: number;
  offsetMs: number;
  children: string[];
}

// Get icon based on service/span type
function getSpanIcon(span: SpanInfo) {
  const name = span.name.toLowerCase();
  const labels = span.labels || {};

  if (labels["db.system"] || name.includes("select") || name.includes("insert")) {
    return <Database className="h-3 w-3" />;
  }
  if (labels["http.url"]?.includes("api.stripe") || name.includes("stripe")) {
    return <Globe className="h-3 w-3" />;
  }
  if (name.includes("http") || name.includes("post") || name.includes("get")) {
    return <Globe className="h-3 w-3" />;
  }
  if (name.includes("publish") || name.includes("event")) {
    return <Zap className="h-3 w-3" />;
  }
  return <Server className="h-3 w-3" />;
}

// Get color based on span status
function getSpanColor(span: SpanInfo): string {
  if (span.has_error) {
    return "bg-red-500/80 hover:bg-red-500";
  }
  if ((span.duration_ms || 0) > 1000) {
    return "bg-yellow-500/80 hover:bg-yellow-500";
  }
  return "bg-blue-500/80 hover:bg-blue-500";
}

// Span detail popover
function SpanDetailPopover({
  span,
  children,
}: {
  span: SpanInfo;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent
        className="w-96 bg-card border-border p-0"
        align="start"
        side="right"
      >
        <div className="p-3 border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {getSpanIcon(span)}
              <span className="font-mono text-sm font-medium">
                {truncate(span.name, 40)}
              </span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          {span.service_name && (
            <p className="text-xs text-muted-foreground mt-1">
              {span.service_name}
            </p>
          )}
        </div>

        <div className="p-3 space-y-3">
          {/* Duration and Status */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-sm font-mono">
                {formatDuration(span.duration_ms || 0)}
              </span>
            </div>
            {span.has_error ? (
              <Badge variant="error" className="text-xs">
                <AlertCircle className="h-3 w-3 mr-1" />
                Error
              </Badge>
            ) : (
              <Badge variant="success" className="text-xs">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Success
              </Badge>
            )}
            {span.status_code && (
              <Badge
                variant={
                  Number(span.status_code) >= 400
                    ? "error"
                    : Number(span.status_code) >= 300
                      ? "warning"
                      : "success"
                }
                className="text-xs"
              >
                {span.status_code}
              </Badge>
            )}
          </div>

          {/* Timestamps */}
          {span.start_time && (
            <div className="text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Start:</span>
                <span className="font-mono">
                  {format(new Date(span.start_time), "HH:mm:ss.SSS")}
                </span>
              </div>
              {span.end_time && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">End:</span>
                  <span className="font-mono">
                    {format(new Date(span.end_time), "HH:mm:ss.SSS")}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Labels/Attributes */}
          {Object.keys(span.labels).length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground mb-1.5">Attributes</p>
              <ScrollArea className="h-32">
                <div className="space-y-1">
                  {Object.entries(span.labels).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex justify-between text-xs py-1 px-2 rounded bg-muted/50"
                    >
                      <span className="text-muted-foreground font-mono">
                        {key}
                      </span>
                      <span className="font-mono text-foreground ml-2 truncate max-w-[180px]">
                        {value}
                      </span>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}

          {/* Span IDs */}
          <div className="text-xs space-y-1 pt-2 border-t border-border">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Span ID:</span>
              <span className="font-mono text-muted-foreground">
                {span.span_id}
              </span>
            </div>
            {span.parent_span_id && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Parent:</span>
                <span className="font-mono text-muted-foreground">
                  {span.parent_span_id}
                </span>
              </div>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function TraceWaterfall({
  trace,
  onSpanClick,
  highlightSpanId,
  className,
}: TraceWaterfallProps) {
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);

  // Process spans into a hierarchical structure with computed offsets
  const { processedSpans, totalDuration, minTime } = useMemo(() => {
    const spanMap = new Map<string, SpanInfo>(
      trace.spans.map((s) => [s.span_id, s])
    );

    // Find min time for offset calculation
    const times = trace.spans
      .filter((s) => s.start_time)
      .map((s) => new Date(s.start_time!).getTime());
    const minTime = Math.min(...times);
    const maxTime = Math.max(
      ...trace.spans
        .filter((s) => s.end_time)
        .map((s) => new Date(s.end_time!).getTime())
    );
    const totalDuration = maxTime - minTime;

    // Process spans
    const processed: ProcessedSpan[] = trace.spans.map((span) => {
      const startTime = span.start_time
        ? new Date(span.start_time).getTime()
        : minTime;
      const offsetMs = startTime - minTime;
      const depth = calculateSpanDepth(span.span_id, trace.spans);

      // Find children
      const children = trace.spans
        .filter((s) => s.parent_span_id === span.span_id)
        .map((s) => s.span_id);

      return {
        ...span,
        depth,
        offsetMs,
        children,
      };
    });

    // Sort by offset (to show spans in chronological order)
    processed.sort((a, b) => {
      // First by depth (root first)
      if (a.depth !== b.depth) return a.depth - b.depth;
      // Then by offset
      return a.offsetMs - b.offsetMs;
    });

    return { processedSpans: processed, totalDuration, minTime };
  }, [trace.spans]);

  const handleSpanClick = (span: SpanInfo) => {
    setSelectedSpanId(span.span_id);
    onSpanClick?.(span);
  };

  return (
    <Card className={cn("bg-card border-border", className)}>
      <CardHeader className="py-3 px-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm font-medium">Trace Waterfall</CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5 font-mono">
              {trace.trace_id}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-mono">{formatDuration(totalDuration)}</span>
            </div>
            <Badge variant="secondary" className="text-xs">
              {trace.spans.length} spans
            </Badge>
            {trace.spans.some((s) => s.has_error) && (
              <Badge variant="error" className="text-xs">
                <AlertCircle className="h-3 w-3 mr-1" />
                Errors
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {/* Timeline header */}
        <div className="flex border-b border-border text-xs text-muted-foreground">
          <div className="w-64 min-w-64 px-3 py-2 border-r border-border">
            Operation
          </div>
          <div className="flex-1 px-3 py-2 flex justify-between">
            <span>0ms</span>
            <span>{formatDuration(totalDuration / 4)}</span>
            <span>{formatDuration(totalDuration / 2)}</span>
            <span>{formatDuration((totalDuration * 3) / 4)}</span>
            <span>{formatDuration(totalDuration)}</span>
          </div>
        </div>

        {/* Span rows */}
        <ScrollArea className="h-[400px]">
          <TooltipProvider>
            <div>
              {processedSpans.map((span) => {
                const widthPercent = Math.max(
                  0.5,
                  ((span.duration_ms || 0) / totalDuration) * 100
                );
                const offsetPercent = (span.offsetMs / totalDuration) * 100;
                const isSelected =
                  selectedSpanId === span.span_id ||
                  highlightSpanId === span.span_id;

                return (
                  <div
                    key={span.span_id}
                    className={cn(
                      "flex border-b border-border/50 hover:bg-muted/30 transition-colors",
                      isSelected && "bg-muted/50"
                    )}
                  >
                    {/* Operation name column */}
                    <div
                      className="w-64 min-w-64 px-3 py-2 border-r border-border/50 flex items-center gap-1"
                      style={{ paddingLeft: `${12 + span.depth * 16}px` }}
                    >
                      {span.children.length > 0 && (
                        <ChevronRight className="h-3 w-3 text-muted-foreground" />
                      )}
                      <SpanDetailPopover span={span}>
                        <button
                          className="flex items-center gap-1.5 text-left hover:text-primary transition-colors"
                          onClick={() => handleSpanClick(span)}
                        >
                          {getSpanIcon(span)}
                          <span className="font-mono text-xs truncate max-w-[180px]">
                            {span.name}
                          </span>
                          {span.has_error && (
                            <AlertCircle className="h-3 w-3 text-red-500 flex-shrink-0" />
                          )}
                        </button>
                      </SpanDetailPopover>
                    </div>

                    {/* Timeline column */}
                    <div className="flex-1 px-2 py-2 relative">
                      {/* Grid lines */}
                      <div className="absolute inset-0 flex pointer-events-none">
                        {[0, 25, 50, 75, 100].map((pct) => (
                          <div
                            key={pct}
                            className="border-l border-border/30"
                            style={{ left: `${pct}%`, position: "absolute", height: "100%" }}
                          />
                        ))}
                      </div>

                      {/* Span bar */}
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <SpanDetailPopover span={span}>
                            <button
                              className={cn(
                                "h-5 rounded-sm relative trace-span-bar cursor-pointer transition-all",
                                getSpanColor(span),
                                isSelected && "ring-2 ring-primary ring-offset-1 ring-offset-background"
                              )}
                              style={{
                                width: `${widthPercent}%`,
                                minWidth: "4px",
                                marginLeft: `${offsetPercent}%`,
                              }}
                              onClick={() => handleSpanClick(span)}
                            >
                              {/* Duration label inside bar if it fits */}
                              {widthPercent > 8 && (
                                <span className="absolute inset-0 flex items-center justify-center text-[10px] text-white font-mono">
                                  {formatDuration(span.duration_ms || 0)}
                                </span>
                              )}
                            </button>
                          </SpanDetailPopover>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="text-xs">
                          <div className="font-mono">
                            {span.name}: {formatDuration(span.duration_ms || 0)}
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </div>
                );
              })}
            </div>
          </TooltipProvider>
        </ScrollArea>

        {/* Legend */}
        <div className="flex items-center gap-4 px-4 py-2 border-t border-border text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-sm bg-blue-500" />
            <span className="text-muted-foreground">Normal</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-sm bg-yellow-500" />
            <span className="text-muted-foreground">Slow (&gt;1s)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-sm bg-red-500" />
            <span className="text-muted-foreground">Error</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default TraceWaterfall;
