/**
 * Cross-Signal Correlation Timeline Component
 *
 * Unified timeline visualization correlating:
 * - Traces
 * - Logs
 * - Metrics
 * - Alerts
 * - Deployments
 * - Incidents
 */

"use client";

import React, { useMemo, useState, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Activity,
  FileText,
  BarChart2,
  AlertTriangle,
  GitBranch,
  Flame,
  Clock,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Filter,
  Link2,
} from "lucide-react";
import { formatDuration, formatRelativeTime } from "@/lib/utils";

// =============================================================================
// Types
// =============================================================================

export type TimelineEventType = "trace" | "log" | "metric" | "alert" | "deployment" | "incident";

export interface TimelineEvent {
  id: string;
  type: TimelineEventType;
  timestamp: string;
  title: string;
  description?: string;
  severity?: "info" | "warning" | "error" | "critical";
  service?: string;
  correlationId?: string;
  metadata?: Record<string, unknown>;
  duration?: number; // For spans/incidents
  children?: TimelineEvent[]; // For grouped events
}

export interface TimelineTraceEvent extends TimelineEvent {
  type: "trace";
  traceId: string;
  spanCount: number;
  errorCount: number;
  latencyMs: number;
}

export interface TimelineLogEvent extends TimelineEvent {
  type: "log";
  logLevel: string;
  message: string;
  source: string;
}

export interface TimelineMetricEvent extends TimelineEvent {
  type: "metric";
  metricName: string;
  value: number;
  threshold?: number;
  isAnomaly?: boolean;
}

export interface TimelineAlertEvent extends TimelineEvent {
  type: "alert";
  alertName: string;
  alertState: "firing" | "resolved" | "pending";
  labels: Record<string, string>;
}

export interface TimelineDeploymentEvent extends TimelineEvent {
  type: "deployment";
  revision: string;
  image: string;
  status: "success" | "failed" | "in_progress";
  changedBy?: string;
}

export interface TimelineIncidentEvent extends TimelineEvent {
  type: "incident";
  incidentId: string;
  impactedServices: string[];
  status: "open" | "investigating" | "mitigating" | "resolved";
  ttd?: number; // Time to detect
  ttr?: number; // Time to resolve
}

export interface TimelineData {
  events: TimelineEvent[];
  startTime: string;
  endTime: string;
  correlations?: Correlation[];
}

export interface Correlation {
  sourceEventId: string;
  targetEventId: string;
  type: "caused_by" | "related_to" | "triggered" | "exemplar";
  confidence: number;
}

// =============================================================================
// Constants
// =============================================================================

const EVENT_COLORS: Record<TimelineEventType, string> = {
  trace: "bg-blue-500",
  log: "bg-gray-500",
  metric: "bg-green-500",
  alert: "bg-red-500",
  deployment: "bg-purple-500",
  incident: "bg-orange-500",
};

const EVENT_ICONS: Record<TimelineEventType, React.ReactNode> = {
  trace: <Activity className="w-3 h-3" />,
  log: <FileText className="w-3 h-3" />,
  metric: <BarChart2 className="w-3 h-3" />,
  alert: <AlertTriangle className="w-3 h-3" />,
  deployment: <GitBranch className="w-3 h-3" />,
  incident: <Flame className="w-3 h-3" />,
};

// =============================================================================
// Sub-components
// =============================================================================

function TimeMarker({ time, position }: { time: Date; position: number }) {
  return (
    <div
      className="absolute top-0 h-full border-l border-dashed border-muted-foreground/30"
      style={{ left: `${position}%` }}
    >
      <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] text-muted-foreground whitespace-nowrap">
        {time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </span>
    </div>
  );
}

function EventDot({
  event,
  position,
  lane,
  isSelected,
  isHighlighted,
  onClick,
}: {
  event: TimelineEvent;
  position: number;
  lane: number;
  isSelected: boolean;
  isHighlighted: boolean;
  onClick: () => void;
}) {
  const severityRing: Record<string, string> = {
    info: "",
    warning: "ring-2 ring-warning ring-offset-1",
    error: "ring-2 ring-error ring-offset-1",
    critical: "ring-2 ring-error ring-offset-2 animate-pulse",
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className={`
            absolute w-4 h-4 rounded-full transition-all flex items-center justify-center
            ${EVENT_COLORS[event.type]}
            ${isSelected ? "ring-2 ring-primary ring-offset-2 scale-125" : ""}
            ${isHighlighted ? "scale-110 brightness-125" : ""}
            ${event.severity ? severityRing[event.severity] : ""}
            hover:scale-125
          `}
          style={{
            left: `${position}%`,
            top: `${lane * 30 + 20}px`,
            transform: "translate(-50%, -50%)",
          }}
          onClick={onClick}
        >
          {EVENT_ICONS[event.type]}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80" side="top">
        <EventDetails event={event} />
      </PopoverContent>
    </Popover>
  );
}

function EventDetails({ event }: { event: TimelineEvent }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded ${EVENT_COLORS[event.type]}`}>
            {EVENT_ICONS[event.type]}
          </div>
          <span className="font-semibold">{event.title}</span>
        </div>
        {event.severity && (
          <Badge variant={event.severity === "critical" || event.severity === "error" ? "destructive" : "secondary"}>
            {event.severity}
          </Badge>
        )}
      </div>

      {event.description && (
        <p className="text-sm text-muted-foreground">{event.description}</p>
      )}

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-muted-foreground">Time</span>
          <p className="font-mono">{new Date(event.timestamp).toLocaleString()}</p>
        </div>
        {event.service && (
          <div>
            <span className="text-muted-foreground">Service</span>
            <p>{event.service}</p>
          </div>
        )}
        {event.duration && (
          <div>
            <span className="text-muted-foreground">Duration</span>
            <p className="font-mono">{formatDuration(event.duration)}</p>
          </div>
        )}
        {event.correlationId && (
          <div>
            <span className="text-muted-foreground">Correlation ID</span>
            <p className="font-mono text-xs truncate">{event.correlationId}</p>
          </div>
        )}
      </div>

      {/* Type-specific details */}
      {event.type === "trace" && (
        <TraceEventDetails event={event as TimelineTraceEvent} />
      )}
      {event.type === "alert" && (
        <AlertEventDetails event={event as TimelineAlertEvent} />
      )}
      {event.type === "deployment" && (
        <DeploymentEventDetails event={event as TimelineDeploymentEvent} />
      )}
      {event.type === "incident" && (
        <IncidentEventDetails event={event as TimelineIncidentEvent} />
      )}
    </div>
  );
}

function TraceEventDetails({ event }: { event: TimelineTraceEvent }) {
  return (
    <div className="pt-2 border-t">
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-lg font-bold">{event.spanCount}</p>
          <p className="text-xs text-muted-foreground">Spans</p>
        </div>
        <div>
          <p className="text-lg font-bold text-error">{event.errorCount}</p>
          <p className="text-xs text-muted-foreground">Errors</p>
        </div>
        <div>
          <p className="text-lg font-bold">{event.latencyMs}ms</p>
          <p className="text-xs text-muted-foreground">Latency</p>
        </div>
      </div>
    </div>
  );
}

function AlertEventDetails({ event }: { event: TimelineAlertEvent }) {
  return (
    <div className="pt-2 border-t">
      <Badge variant={event.alertState === "firing" ? "destructive" : event.alertState === "resolved" ? "default" : "secondary"}>
        {event.alertState}
      </Badge>
      <div className="mt-2 flex flex-wrap gap-1">
        {Object.entries(event.labels).map(([key, value]) => (
          <Badge key={key} variant="outline" className="text-xs">
            {key}={value}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function DeploymentEventDetails({ event }: { event: TimelineDeploymentEvent }) {
  return (
    <div className="pt-2 border-t">
      <div className="space-y-1 text-sm">
        <p>
          <span className="text-muted-foreground">Revision:</span>{" "}
          <code className="text-xs bg-muted px-1 rounded">{event.revision}</code>
        </p>
        <p className="truncate">
          <span className="text-muted-foreground">Image:</span>{" "}
          <code className="text-xs">{event.image}</code>
        </p>
        {event.changedBy && (
          <p>
            <span className="text-muted-foreground">By:</span> {event.changedBy}
          </p>
        )}
      </div>
    </div>
  );
}

function IncidentEventDetails({ event }: { event: TimelineIncidentEvent }) {
  return (
    <div className="pt-2 border-t space-y-2">
      <Badge variant={event.status === "resolved" ? "default" : "destructive"}>
        {event.status}
      </Badge>
      <div className="flex flex-wrap gap-1">
        {event.impactedServices.map((service) => (
          <Badge key={service} variant="outline" className="text-xs">
            {service}
          </Badge>
        ))}
      </div>
      {(event.ttd || event.ttr) && (
        <div className="grid grid-cols-2 gap-2 text-sm">
          {event.ttd && (
            <div>
              <span className="text-muted-foreground">TTD</span>
              <p className="font-mono">{formatDuration(event.ttd)}</p>
            </div>
          )}
          {event.ttr && (
            <div>
              <span className="text-muted-foreground">TTR</span>
              <p className="font-mono">{formatDuration(event.ttr)}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CorrelationLine({
  source,
  target,
  correlation,
}: {
  source: { x: number; y: number };
  target: { x: number; y: number };
  correlation: Correlation;
}) {
  const strokeColor = correlation.type === "caused_by"
    ? "hsl(var(--error))"
    : correlation.type === "triggered"
    ? "hsl(var(--warning))"
    : "hsl(var(--muted-foreground))";

  return (
    <svg
      className="absolute top-0 left-0 w-full h-full pointer-events-none"
      style={{ zIndex: -1 }}
    >
      <path
        d={`M ${source.x} ${source.y} Q ${(source.x + target.x) / 2} ${Math.min(source.y, target.y) - 30} ${target.x} ${target.y}`}
        fill="none"
        stroke={strokeColor}
        strokeWidth={1.5}
        strokeDasharray={correlation.type === "related_to" ? "4 2" : undefined}
        opacity={correlation.confidence}
      />
    </svg>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export interface CrossSignalTimelineProps {
  data: TimelineData;
  onEventSelect?: (event: TimelineEvent | null) => void;
  showCorrelations?: boolean;
  filterTypes?: TimelineEventType[];
  className?: string;
}

export function CrossSignalTimeline({
  data,
  onEventSelect,
  showCorrelations = true,
  filterTypes,
  className,
}: CrossSignalTimelineProps) {
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [activeFilters, setActiveFilters] = useState<Set<TimelineEventType>>(
    new Set(filterTypes || ["trace", "log", "metric", "alert", "deployment", "incident"])
  );
  const [zoomLevel, setZoomLevel] = useState(1);

  // Calculate time range
  const timeRange = useMemo(() => {
    const start = new Date(data.startTime).getTime();
    const end = new Date(data.endTime).getTime();
    return { start, end, duration: end - start };
  }, [data.startTime, data.endTime]);

  // Filter and sort events
  const filteredEvents = useMemo(() => {
    return data.events
      .filter((e) => activeFilters.has(e.type))
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }, [data.events, activeFilters]);

  // Assign lanes to events (group by type)
  const eventLanes = useMemo(() => {
    const typeOrder: TimelineEventType[] = ["incident", "alert", "metric", "trace", "log", "deployment"];
    const activeLanes = typeOrder.filter((t) => activeFilters.has(t));
    const laneMap = new Map<TimelineEventType, number>();
    activeLanes.forEach((type, idx) => laneMap.set(type, idx));
    return laneMap;
  }, [activeFilters]);

  // Calculate positions
  const eventPositions = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();

    for (const event of filteredEvents) {
      const eventTime = new Date(event.timestamp).getTime();
      const position = ((eventTime - timeRange.start) / timeRange.duration) * 100;
      const lane = eventLanes.get(event.type) || 0;

      positions.set(event.id, {
        x: position,
        y: lane * 30 + 20,
      });
    }

    return positions;
  }, [filteredEvents, timeRange, eventLanes]);

  // Generate time markers
  const timeMarkers = useMemo(() => {
    const markers: { time: Date; position: number }[] = [];
    const markerCount = 5;
    const interval = timeRange.duration / (markerCount - 1);

    for (let i = 0; i < markerCount; i++) {
      const time = new Date(timeRange.start + interval * i);
      markers.push({ time, position: (i / (markerCount - 1)) * 100 });
    }

    return markers;
  }, [timeRange]);

  // Get correlated events
  const correlatedEventIds = useMemo(() => {
    if (!selectedEventId || !data.correlations) return new Set<string>();

    const ids = new Set<string>();
    for (const corr of data.correlations) {
      if (corr.sourceEventId === selectedEventId) {
        ids.add(corr.targetEventId);
      }
      if (corr.targetEventId === selectedEventId) {
        ids.add(corr.sourceEventId);
      }
    }
    return ids;
  }, [selectedEventId, data.correlations]);

  const handleEventClick = useCallback((eventId: string) => {
    const newSelection = eventId === selectedEventId ? null : eventId;
    setSelectedEventId(newSelection);
    onEventSelect?.(newSelection ? filteredEvents.find((e) => e.id === newSelection) || null : null);
  }, [selectedEventId, filteredEvents, onEventSelect]);

  const toggleFilter = (type: TimelineEventType) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Cross-Signal Timeline
            </CardTitle>
            <CardDescription>
              {formatRelativeTime(data.startTime)} to {formatRelativeTime(data.endTime)} •{" "}
              {filteredEvents.length} events
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setZoomLevel((z) => Math.max(z / 1.5, 0.5))}>
              <ZoomOut className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={() => setZoomLevel((z) => Math.min(z * 1.5, 4))}>
              <ZoomIn className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 mt-4">
          <Filter className="w-4 h-4 text-muted-foreground" />
          {(["trace", "log", "metric", "alert", "deployment", "incident"] as TimelineEventType[]).map((type) => (
            <Button
              key={type}
              variant={activeFilters.has(type) ? "default" : "outline"}
              size="sm"
              className="gap-1 text-xs"
              onClick={() => toggleFilter(type)}
            >
              <div className={`w-2 h-2 rounded-full ${EVENT_COLORS[type]}`} />
              {type}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative overflow-x-auto">
          {/* Timeline container */}
          <div
            className="relative h-[200px] min-w-[600px]"
            style={{ width: `${100 * zoomLevel}%` }}
          >
            {/* Background grid */}
            <div className="absolute inset-0 bg-muted/20 rounded-lg">
              {/* Time markers */}
              {timeMarkers.map((marker, idx) => (
                <TimeMarker key={idx} time={marker.time} position={marker.position} />
              ))}

              {/* Lane labels */}
              <div className="absolute left-2 top-8 space-y-[18px]">
                {Array.from(eventLanes.entries()).map(([type, lane]) => (
                  <div
                    key={type}
                    className="flex items-center gap-1 text-xs text-muted-foreground"
                    style={{ transform: `translateY(${lane * 30}px)` }}
                  >
                    <div className={`w-2 h-2 rounded-full ${EVENT_COLORS[type]}`} />
                    {type}
                  </div>
                ))}
              </div>

              {/* Correlation lines */}
              {showCorrelations && selectedEventId && data.correlations && (
                <>
                  {data.correlations
                    .filter((c) => c.sourceEventId === selectedEventId || c.targetEventId === selectedEventId)
                    .map((corr) => {
                      const sourcePos = eventPositions.get(corr.sourceEventId);
                      const targetPos = eventPositions.get(corr.targetEventId);
                      if (!sourcePos || !targetPos) return null;

                      return (
                        <CorrelationLine
                          key={`${corr.sourceEventId}-${corr.targetEventId}`}
                          source={{ x: sourcePos.x * 6, y: sourcePos.y }}
                          target={{ x: targetPos.x * 6, y: targetPos.y }}
                          correlation={corr}
                        />
                      );
                    })}
                </>
              )}

              {/* Events */}
              {filteredEvents.map((event) => {
                const pos = eventPositions.get(event.id);
                if (!pos) return null;

                return (
                  <EventDot
                    key={event.id}
                    event={event}
                    position={pos.x}
                    lane={eventLanes.get(event.type) || 0}
                    isSelected={selectedEventId === event.id}
                    isHighlighted={correlatedEventIds.has(event.id)}
                    onClick={() => handleEventClick(event.id)}
                  />
                );
              })}
            </div>
          </div>
        </div>

        {/* Correlation indicator */}
        {showCorrelations && selectedEventId && correlatedEventIds.size > 0 && (
          <div className="mt-4 p-2 rounded bg-muted flex items-center gap-2 text-sm">
            <Link2 className="w-4 h-4 text-primary" />
            <span>{correlatedEventIds.size} correlated events</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default CrossSignalTimeline;
