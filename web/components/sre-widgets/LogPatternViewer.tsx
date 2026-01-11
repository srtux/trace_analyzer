"use client";

import React, { useState, useMemo } from "react";
import { format } from "date-fns";
import {
  AlertCircle,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Info,
  FileText,
  Clock,
  Server,
  Filter,
} from "lucide-react";

import { cn, truncate, getSeverityColor } from "@/lib/utils";
import type { LogPattern, LogPatternSummary } from "@/types/adk-schema";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface LogPatternViewerProps {
  data: LogPatternSummary;
  onPatternClick?: (pattern: LogPattern) => void;
  className?: string;
}

// Get primary severity from severity counts
function getPrimarySeverity(
  severityCounts: Record<string, number>
): string {
  const priorities = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"];
  for (const severity of priorities) {
    if (severityCounts[severity] && severityCounts[severity] > 0) {
      return severity;
    }
  }
  return "INFO";
}

// Get severity icon
function getSeverityIcon(severity: string) {
  switch (severity.toUpperCase()) {
    case "CRITICAL":
    case "ERROR":
      return <AlertCircle className="h-3.5 w-3.5" />;
    case "WARNING":
      return <AlertTriangle className="h-3.5 w-3.5" />;
    default:
      return <Info className="h-3.5 w-3.5" />;
  }
}

// Get badge variant for severity
function getSeverityBadgeVariant(
  severity: string
): "critical" | "error" | "warning" | "info" | "secondary" {
  switch (severity.toUpperCase()) {
    case "CRITICAL":
      return "critical";
    case "ERROR":
      return "error";
    case "WARNING":
      return "warning";
    case "INFO":
      return "info";
    default:
      return "secondary";
  }
}

// Bar chart for occurrence count
function OccurrenceBar({
  count,
  maxCount,
}: {
  count: number;
  maxCount: number;
}) {
  const widthPercent = Math.max(5, (count / maxCount) * 100);

  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-4 bg-muted rounded overflow-hidden">
        <div
          className="h-full bg-primary/60 rounded transition-all"
          style={{ width: `${widthPercent}%` }}
        />
      </div>
      <span className="text-xs font-mono w-12 text-right">
        {count.toLocaleString()}
      </span>
    </div>
  );
}

// Pattern detail row
function PatternDetailRow({
  pattern,
  maxCount,
  onPatternClick,
}: {
  pattern: LogPattern;
  maxCount: number;
  onPatternClick?: (pattern: LogPattern) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const primarySeverity = getPrimarySeverity(pattern.severity_counts);

  return (
    <>
      <TableRow
        className="hover:bg-muted/30 cursor-pointer"
        onClick={() => {
          setExpanded(!expanded);
          onPatternClick?.(pattern);
        }}
      >
        <TableCell className="py-2 w-10">
          <button className="p-0.5 hover:bg-muted rounded">
            {expanded ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
        </TableCell>
        <TableCell className="py-2 font-mono text-xs w-20">
          {pattern.pattern_id}
        </TableCell>
        <TableCell className="py-2 w-40">
          <OccurrenceBar count={pattern.count} maxCount={maxCount} />
        </TableCell>
        <TableCell className="py-2">
          <div className="font-mono text-xs text-muted-foreground leading-relaxed max-w-[400px]">
            {truncate(pattern.template, 80)}
          </div>
        </TableCell>
        <TableCell className="py-2 w-24">
          <Badge variant={getSeverityBadgeVariant(primarySeverity)} className="text-xs">
            {getSeverityIcon(primarySeverity)}
            <span className="ml-1">{primarySeverity}</span>
          </Badge>
        </TableCell>
      </TableRow>

      {/* Expanded detail row */}
      {expanded && (
        <TableRow className="bg-muted/20">
          <TableCell colSpan={5} className="py-3">
            <div className="px-4 space-y-3">
              {/* Full template */}
              <div>
                <p className="text-xs text-muted-foreground mb-1">Template</p>
                <div className="bg-background/50 rounded p-2">
                  <code className="text-xs font-mono text-foreground break-all">
                    {pattern.template}
                  </code>
                </div>
              </div>

              {/* Severity breakdown */}
              <div className="flex gap-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">
                    Severity Distribution
                  </p>
                  <div className="flex gap-2">
                    {Object.entries(pattern.severity_counts).map(
                      ([sev, count]) => (
                        <Badge
                          key={sev}
                          variant={getSeverityBadgeVariant(sev)}
                          className="text-xs"
                        >
                          {sev}: {count.toLocaleString()}
                        </Badge>
                      )
                    )}
                  </div>
                </div>

                {/* Time range */}
                {pattern.first_seen && pattern.last_seen && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">
                      Time Range
                    </p>
                    <div className="flex items-center gap-1 text-xs">
                      <Clock className="h-3 w-3" />
                      <span className="font-mono">
                        {format(new Date(pattern.first_seen), "HH:mm:ss")} -{" "}
                        {format(new Date(pattern.last_seen), "HH:mm:ss")}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Sample messages */}
              {pattern.sample_messages.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">
                    Sample Messages
                  </p>
                  <div className="space-y-1">
                    {pattern.sample_messages.slice(0, 2).map((msg, idx) => (
                      <div
                        key={idx}
                        className="bg-background/50 rounded p-2 text-xs font-mono text-muted-foreground overflow-x-auto"
                      >
                        {msg}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Resources */}
              {pattern.resources.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Resources</p>
                  <div className="flex flex-wrap gap-1">
                    {pattern.resources.map((resource, idx) => (
                      <Badge key={idx} variant="secondary" className="text-xs">
                        <Server className="h-3 w-3 mr-1" />
                        {resource}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export function LogPatternViewer({
  data,
  onPatternClick,
  className,
}: LogPatternViewerProps) {
  const [filter, setFilter] = useState<"all" | "errors" | "warnings">("all");

  // Get max count for normalization
  const maxCount = useMemo(() => {
    return Math.max(...data.top_patterns.map((p) => p.count));
  }, [data.top_patterns]);

  // Filter patterns
  const filteredPatterns = useMemo(() => {
    if (filter === "all") return data.top_patterns;
    if (filter === "errors") {
      return data.top_patterns.filter(
        (p) =>
          p.severity_counts["ERROR"] > 0 || p.severity_counts["CRITICAL"] > 0
      );
    }
    if (filter === "warnings") {
      return data.top_patterns.filter((p) => p.severity_counts["WARNING"] > 0);
    }
    return data.top_patterns;
  }, [data.top_patterns, filter]);

  return (
    <Card className={cn("bg-card border-border", className)}>
      <CardHeader className="py-3 px-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-sm font-medium">Log Patterns</CardTitle>
            <Badge variant="secondary" className="text-xs">
              Drain3 Engine
            </Badge>
          </div>

          {/* Filter buttons */}
          <div className="flex items-center gap-1">
            <Filter className="h-3.5 w-3.5 text-muted-foreground mr-1" />
            <Button
              size="xs"
              variant={filter === "all" ? "secondary" : "ghost"}
              onClick={() => setFilter("all")}
            >
              All
            </Button>
            <Button
              size="xs"
              variant={filter === "errors" ? "secondary" : "ghost"}
              onClick={() => setFilter("errors")}
              className="text-red-400"
            >
              Errors
            </Button>
            <Button
              size="xs"
              variant={filter === "warnings" ? "secondary" : "ghost"}
              onClick={() => setFilter("warnings")}
              className="text-yellow-400"
            >
              Warnings
            </Button>
          </div>
        </div>

        {/* Summary stats */}
        <div className="flex items-center gap-6 mt-2 text-xs">
          <div>
            <span className="text-muted-foreground">Logs processed:</span>{" "}
            <span className="font-mono font-medium">
              {data.total_logs_processed.toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Unique patterns:</span>{" "}
            <span className="font-mono font-medium">{data.unique_patterns}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Compression:</span>{" "}
            <span className="font-mono font-medium text-green-400">
              {data.compression_ratio.toFixed(1)}x
            </span>
          </div>
          <div className="flex items-center gap-2">
            {Object.entries(data.severity_distribution).map(([sev, count]) => (
              <Badge
                key={sev}
                variant={getSeverityBadgeVariant(sev)}
                className="text-xs"
              >
                {sev}: {count.toLocaleString()}
              </Badge>
            ))}
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <ScrollArea className="h-[400px]">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-b border-border">
                <TableHead className="w-10 py-2"></TableHead>
                <TableHead className="w-20 py-2 text-xs">Pattern ID</TableHead>
                <TableHead className="w-40 py-2 text-xs">Occurrences</TableHead>
                <TableHead className="py-2 text-xs">Template</TableHead>
                <TableHead className="w-24 py-2 text-xs">Severity</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredPatterns.map((pattern) => (
                <PatternDetailRow
                  key={pattern.pattern_id}
                  pattern={pattern}
                  maxCount={maxCount}
                  onPatternClick={onPatternClick}
                />
              ))}
              {filteredPatterns.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="text-center py-8 text-muted-foreground"
                  >
                    No patterns match the current filter
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

export default LogPatternViewer;
