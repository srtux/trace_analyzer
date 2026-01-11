import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a duration in milliseconds to a human-readable string
 */
export function formatDuration(ms: number): string {
  if (ms < 1) {
    return `${(ms * 1000).toFixed(0)}µs`;
  }
  if (ms < 1000) {
    return `${ms.toFixed(1)}ms`;
  }
  if (ms < 60000) {
    return `${(ms / 1000).toFixed(2)}s`;
  }
  return `${(ms / 60000).toFixed(2)}m`;
}

/**
 * Format a timestamp to a relative time string
 */
export function formatRelativeTime(timestamp: string | Date): string {
  const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp;
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();

  if (diffMs < 60000) {
    return "just now";
  }
  if (diffMs < 3600000) {
    const mins = Math.floor(diffMs / 60000);
    return `${mins}m ago`;
  }
  if (diffMs < 86400000) {
    const hours = Math.floor(diffMs / 3600000);
    return `${hours}h ago`;
  }
  const days = Math.floor(diffMs / 86400000);
  return `${days}d ago`;
}

/**
 * Get a severity color class
 */
export function getSeverityColor(severity: string): string {
  const severityLower = severity.toLowerCase();
  switch (severityLower) {
    case "critical":
      return "text-red-500 bg-red-500/10 border-red-500/50";
    case "high":
    case "error":
      return "text-orange-500 bg-orange-500/10 border-orange-500/50";
    case "medium":
    case "warning":
      return "text-yellow-500 bg-yellow-500/10 border-yellow-500/50";
    case "low":
    case "info":
      return "text-blue-500 bg-blue-500/10 border-blue-500/50";
    default:
      return "text-gray-500 bg-gray-500/10 border-gray-500/50";
  }
}

/**
 * Get a status color class
 */
export function getStatusColor(status: string): string {
  const statusLower = status.toLowerCase();
  switch (statusLower) {
    case "success":
    case "healthy":
    case "ok":
      return "text-green-500 bg-green-500/10";
    case "degraded":
    case "warning":
      return "text-yellow-500 bg-yellow-500/10";
    case "critical":
    case "error":
    case "failed":
      return "text-red-500 bg-red-500/10";
    default:
      return "text-gray-500 bg-gray-500/10";
  }
}

/**
 * Truncate a string to a maximum length
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 3) + "...";
}

/**
 * Calculate the depth of a span in a trace hierarchy
 */
export function calculateSpanDepth(
  spanId: string,
  spans: Array<{ span_id: string; parent_span_id?: string | null }>
): number {
  const spanMap = new Map(spans.map((s) => [s.span_id, s]));
  let depth = 0;
  let current = spanMap.get(spanId);

  while (current?.parent_span_id) {
    depth++;
    current = spanMap.get(current.parent_span_id);
    if (depth > 50) break; // Prevent infinite loops
  }

  return depth;
}

/**
 * Convert bytes to human readable format
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

/**
 * Format a number with appropriate precision
 */
export function formatNumber(num: number, precision: number = 2): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(precision)}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(precision)}K`;
  }
  return num.toFixed(precision);
}
