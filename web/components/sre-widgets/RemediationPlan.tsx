"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  ExternalLink,
  Play,
  Shield,
  Terminal,
  Zap,
  XCircle,
  Loader2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type {
  RemediationSuggestion,
  RemediationStep,
  RiskAssessment,
} from "@/types/adk-schema";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface RemediationPlanProps {
  data: RemediationSuggestion;
  gcloudCommands?: {
    commands: Array<{ description: string; command: string }>;
    warning: string;
  };
  onExecute?: (action: RemediationStep) => void;
  onExplainRisk?: (action: RemediationStep) => void;
  className?: string;
}

// Risk level badge
function RiskBadge({ risk }: { risk: "low" | "medium" | "high" }) {
  const variants = {
    low: { variant: "success" as const, icon: CheckCircle2 },
    medium: { variant: "warning" as const, icon: AlertTriangle },
    high: { variant: "error" as const, icon: XCircle },
  };
  const config = variants[risk];
  const Icon = config.icon;

  return (
    <Badge variant={config.variant} className="text-xs">
      <Icon className="h-3 w-3 mr-1" />
      {risk.toUpperCase()} RISK
    </Badge>
  );
}

// Effort level badge
function EffortBadge({ effort }: { effort: "low" | "medium" | "high" }) {
  const colors = {
    low: "text-green-400",
    medium: "text-yellow-400",
    high: "text-orange-400",
  };

  return (
    <div className={cn("flex items-center gap-1 text-xs", colors[effort])}>
      <Clock className="h-3 w-3" />
      <span className="capitalize">{effort} effort</span>
    </div>
  );
}

// Single remediation step card
function RemediationStepCard({
  step,
  index,
  isRecommended,
  isQuickWin,
  onExecute,
  onExplainRisk,
}: {
  step: RemediationStep;
  index: number;
  isRecommended: boolean;
  isQuickWin: boolean;
  onExecute?: (step: RemediationStep) => void;
  onExplainRisk?: (step: RemediationStep) => void;
}) {
  const [expanded, setExpanded] = useState(isRecommended);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [executing, setExecuting] = useState(false);

  const handleExecute = () => {
    setExecuting(true);
    onExecute?.(step);
    // Simulated delay
    setTimeout(() => {
      setExecuting(false);
      setConfirmDialogOpen(false);
    }, 2000);
  };

  return (
    <div
      className={cn(
        "border rounded-lg transition-all",
        isRecommended
          ? "border-primary/50 bg-primary/5"
          : step.risk === "high"
            ? "border-red-500/30 bg-red-500/5"
            : "border-border"
      )}
    >
      {/* Header */}
      <button
        className="w-full p-3 flex items-start justify-between text-left hover:bg-muted/30 transition-colors rounded-t-lg"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-3">
          <div className="flex items-center justify-center w-6 h-6 rounded-full bg-muted text-xs font-medium mt-0.5">
            {index + 1}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm">{step.action}</span>
              {isRecommended && (
                <Badge variant="default" className="text-xs">
                  <Zap className="h-3 w-3 mr-1" />
                  Recommended
                </Badge>
              )}
              {isQuickWin && !isRecommended && (
                <Badge variant="success" className="text-xs">
                  Quick Win
                </Badge>
              )}
              {step.category && (
                <Badge variant="secondary" className="text-xs">
                  {step.category}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {step.description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 ml-4 flex-shrink-0">
          <RiskBadge risk={step.risk} />
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-3 pt-0 border-t border-border/50">
          {/* Steps */}
          <div className="mt-3">
            <p className="text-xs text-muted-foreground mb-2">
              Implementation Steps
            </p>
            <ol className="space-y-2">
              {step.steps.map((s, idx) => (
                <li key={idx} className="flex items-start gap-2 text-xs">
                  <span className="text-muted-foreground w-4 flex-shrink-0">
                    {idx + 1}.
                  </span>
                  <span>{s}</span>
                </li>
              ))}
            </ol>
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-between mt-4 pt-3 border-t border-border/50">
            <EffortBadge effort={step.effort} />
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => onExplainRisk?.(step)}
              >
                <Shield className="h-3.5 w-3.5 mr-1" />
                Explain Risk
              </Button>

              <Dialog
                open={confirmDialogOpen}
                onOpenChange={setConfirmDialogOpen}
              >
                <DialogTrigger asChild>
                  <Button
                    size="sm"
                    variant={step.risk === "high" ? "destructive" : "default"}
                    disabled={executing}
                  >
                    {executing ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                    ) : (
                      <Play className="h-3.5 w-3.5 mr-1" />
                    )}
                    Execute
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-card">
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                      {step.risk === "high" && (
                        <AlertTriangle className="h-5 w-5 text-red-500" />
                      )}
                      Confirm Execution
                    </DialogTitle>
                    <DialogDescription>
                      You are about to execute: <strong>{step.action}</strong>
                    </DialogDescription>
                  </DialogHeader>

                  <div className="py-4">
                    {step.risk === "high" && (
                      <Alert variant="destructive" className="mb-4">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertTitle>High Risk Action</AlertTitle>
                        <AlertDescription>
                          This action has been flagged as high risk. Ensure you
                          have reviewed all implications and have a rollback
                          plan ready.
                        </AlertDescription>
                      </Alert>
                    )}

                    <div className="space-y-2">
                      <p className="text-sm font-medium">This will:</p>
                      <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
                        {step.steps.slice(0, 3).map((s, idx) => (
                          <li key={idx}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => setConfirmDialogOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant={step.risk === "high" ? "destructive" : "default"}
                      onClick={handleExecute}
                      disabled={executing}
                    >
                      {executing ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Executing...
                        </>
                      ) : (
                        <>
                          <Play className="h-4 w-4 mr-2" />
                          Confirm & Execute
                        </>
                      )}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Command block with copy functionality
function CommandBlock({
  description,
  command,
}: {
  description: string;
  command: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground">{description}</p>
      <div className="flex items-start gap-2 bg-background/50 rounded border border-border/50 p-2">
        <code className="flex-1 text-xs font-mono break-all text-foreground">
          {command}
        </code>
        <Button
          size="icon-sm"
          variant="ghost"
          onClick={handleCopy}
          className="flex-shrink-0"
        >
          {copied ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>
    </div>
  );
}

export function RemediationPlan({
  data,
  gcloudCommands,
  onExecute,
  onExplainRisk,
  className,
}: RemediationPlanProps) {
  const quickWinIds = new Set(data.quick_wins.map((q) => q.action));
  const recommendedAction = data.recommended_first_action?.action;

  return (
    <Card
      className={cn(
        "bg-card border-yellow-600/30 shadow-lg",
        className
      )}
    >
      <CardHeader className="py-3 px-4 border-b border-yellow-600/30 bg-yellow-900/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-yellow-500" />
            <CardTitle className="text-sm font-medium text-yellow-400">
              Remediation Plan
            </CardTitle>
          </div>
          <div className="flex items-center gap-2">
            {data.matched_patterns.length > 0 && (
              <div className="flex gap-1">
                {data.matched_patterns.map((pattern) => (
                  <Badge key={pattern} variant="secondary" className="text-xs">
                    {pattern.replace(/_/g, " ")}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>
        {data.finding_summary && (
          <p className="text-sm text-muted-foreground mt-2">
            {data.finding_summary}
          </p>
        )}
      </CardHeader>

      <CardContent className="p-4">
        {/* Quick Wins section */}
        {data.quick_wins.length > 0 && (
          <Alert variant="success" className="mb-4">
            <Zap className="h-4 w-4" />
            <AlertTitle>Quick Wins Available</AlertTitle>
            <AlertDescription>
              {data.quick_wins.length} low-risk, low-effort actions can be
              executed immediately.
            </AlertDescription>
          </Alert>
        )}

        {/* Suggestions list */}
        <ScrollArea className="h-[400px] pr-2">
          <div className="space-y-3">
            {data.suggestions.map((step, index) => (
              <RemediationStepCard
                key={`${step.action}-${index}`}
                step={step}
                index={index}
                isRecommended={step.action === recommendedAction}
                isQuickWin={quickWinIds.has(step.action)}
                onExecute={onExecute}
                onExplainRisk={onExplainRisk}
              />
            ))}
          </div>
        </ScrollArea>

        {/* gcloud commands section */}
        {gcloudCommands && (
          <div className="mt-4 pt-4 border-t border-border">
            <div className="flex items-center gap-2 mb-3">
              <Terminal className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Ready-to-Run Commands</span>
            </div>

            <Alert variant="warning" className="mb-3">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription className="text-xs">
                {gcloudCommands.warning}
              </AlertDescription>
            </Alert>

            <div className="space-y-3">
              {gcloudCommands.commands.map((cmd, idx) => (
                <CommandBlock
                  key={idx}
                  description={cmd.description}
                  command={cmd.command}
                />
              ))}
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="py-3 px-4 border-t border-border bg-muted/30">
        <div className="flex items-center justify-between w-full text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <span>{data.suggestions.length} suggestions</span>
            <span>{data.quick_wins.length} quick wins</span>
          </div>
          <a
            href="https://cloud.google.com/run/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 hover:text-foreground transition-colors"
          >
            <ExternalLink className="h-3 w-3" />
            GCP Documentation
          </a>
        </div>
      </CardFooter>
    </Card>
  );
}

export default RemediationPlan;
