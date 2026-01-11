"use client";

import React from "react";
import { format } from "date-fns";
import {
  Activity,
  Bot,
  Brain,
  ChartLine,
  CircleDot,
  Clock,
  FileSearch,
  Loader2,
  Shield,
  Sparkles,
  Zap,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { AgentStatus, AgentType } from "@/types/adk-schema";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface StatusBarProps {
  agentStatus: AgentStatus;
  className?: string;
}

// Agent configurations
const agentConfig: Record<
  AgentType,
  {
    name: string;
    icon: typeof Bot;
    color: string;
    bgColor: string;
  }
> = {
  orchestrator: {
    name: "Orchestrator",
    icon: Brain,
    color: "text-purple-400",
    bgColor: "bg-purple-500/10",
  },
  latency_specialist: {
    name: "Latency Specialist",
    icon: Activity,
    color: "text-blue-400",
    bgColor: "bg-blue-500/10",
  },
  error_analyst: {
    name: "Error Analyst",
    icon: Shield,
    color: "text-red-400",
    bgColor: "bg-red-500/10",
  },
  log_pattern_engine: {
    name: "Drain3 Engine",
    icon: FileSearch,
    color: "text-green-400",
    bgColor: "bg-green-500/10",
  },
  metrics_correlator: {
    name: "Metrics Correlator",
    icon: ChartLine,
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/10",
  },
  remediation_advisor: {
    name: "Remediation Advisor",
    icon: Zap,
    color: "text-orange-400",
    bgColor: "bg-orange-500/10",
  },
  idle: {
    name: "Ready",
    icon: CircleDot,
    color: "text-muted-foreground",
    bgColor: "bg-muted",
  },
};

export function StatusBar({ agentStatus, className }: StatusBarProps) {
  const config = agentConfig[agentStatus.currentAgent];
  const Icon = config.icon;
  const isActive = agentStatus.currentAgent !== "idle";

  // Calculate elapsed time
  const elapsedTime = agentStatus.startTime
    ? Math.floor(
        (Date.now() - new Date(agentStatus.startTime).getTime()) / 1000
      )
    : 0;

  return (
    <TooltipProvider>
      <div
        className={cn(
          "flex items-center justify-between px-4 h-10 border-b border-border bg-card",
          className
        )}
      >
        {/* Left side - Agent status */}
        <div className="flex items-center gap-3">
          {/* Agent indicator */}
          <div
            className={cn(
              "flex items-center gap-2 px-2.5 py-1 rounded-full",
              config.bgColor
            )}
          >
            {isActive ? (
              <Loader2 className={cn("h-3.5 w-3.5 animate-spin", config.color)} />
            ) : (
              <Icon className={cn("h-3.5 w-3.5", config.color)} />
            )}
            <span className={cn("text-xs font-medium", config.color)}>
              {config.name}
            </span>
          </div>

          {/* Status message */}
          <span className="text-xs text-muted-foreground max-w-[400px] truncate">
            {agentStatus.message}
          </span>

          {/* Progress indicator */}
          {agentStatus.progress !== undefined && (
            <div className="flex items-center gap-2">
              <div className="w-24 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${agentStatus.progress}%` }}
                />
              </div>
              <span className="text-xs text-muted-foreground font-mono">
                {agentStatus.progress}%
              </span>
            </div>
          )}

          {/* Elapsed time */}
          {isActive && agentStatus.startTime && (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  <span className="font-mono">{elapsedTime}s</span>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                Started at{" "}
                {format(new Date(agentStatus.startTime), "HH:mm:ss")}
              </TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Right side - System info */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          {/* Council of Experts badge */}
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                <span>Council of Experts</span>
              </div>
            </TooltipTrigger>
            <TooltipContent>
              Multi-agent SRE system with specialized sub-agents
            </TooltipContent>
          </Tooltip>

          {/* Divider */}
          <div className="h-4 w-px bg-border" />

          {/* Connection status */}
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-2 rounded-full bg-green-500 status-indicator" />
            <span>Connected</span>
          </div>

          {/* Current time */}
          <div className="font-mono">
            {format(new Date(), "HH:mm:ss")}
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}

export default StatusBar;
