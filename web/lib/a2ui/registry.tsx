/**
 * A2UI Component Registry
 *
 * The Widget Registry (The "Catalog") - A client-defined mapping of component types
 * to concrete, native widget implementations.
 *
 * This registry follows the A2UI principle: agents output abstract component definitions,
 * and the client maps them to native React components.
 */

import React, { ComponentType, ReactNode } from "react";
import type { A2UIComponent, A2UIComponentType, A2UIDataModel } from "@/types/a2ui";

// Import UI components
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";

// =============================================================================
// Registry Types
// =============================================================================

export interface A2UIWidgetProps<P = Record<string, unknown>> {
  component: A2UIComponent;
  props: P;
  dataModel: A2UIDataModel;
  children?: ReactNode;
  onAction?: (action: { type: string; payload: unknown }) => void;
}

export type A2UIWidget<P = Record<string, unknown>> = ComponentType<A2UIWidgetProps<P>>;

// =============================================================================
// Widget Implementations
// =============================================================================

// Text Widget
const TextWidget: A2UIWidget<{
  content: string;
  variant?: string;
  color?: string;
}> = ({ props, dataModel }) => {
  const content = resolveBinding(props.content, dataModel);
  const colorClasses: Record<string, string> = {
    default: "text-foreground",
    muted: "text-muted-foreground",
    accent: "text-primary",
    success: "text-success",
    warning: "text-warning",
    error: "text-error",
  };

  const variantClasses: Record<string, string> = {
    body: "text-sm",
    caption: "text-xs text-muted-foreground",
    label: "text-sm font-medium",
    mono: "text-sm font-mono",
  };

  return (
    <span
      className={`${variantClasses[props.variant || "body"]} ${colorClasses[props.color || "default"]}`}
    >
      {content}
    </span>
  );
};

// Heading Widget
const HeadingWidget: A2UIWidget<{
  content: string;
  level: 1 | 2 | 3 | 4 | 5 | 6;
}> = ({ props, dataModel }) => {
  const content = resolveBinding(props.content, dataModel);
  const Tag = `h${props.level}` as keyof JSX.IntrinsicElements;
  const sizeClasses: Record<number, string> = {
    1: "text-3xl font-bold",
    2: "text-2xl font-semibold",
    3: "text-xl font-semibold",
    4: "text-lg font-medium",
    5: "text-base font-medium",
    6: "text-sm font-medium",
  };

  return <Tag className={sizeClasses[props.level]}>{content}</Tag>;
};

// Button Widget
const ButtonWidget: A2UIWidget<{
  label: string;
  variant?: "primary" | "secondary" | "destructive" | "ghost" | "outline";
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  loading?: boolean;
  icon?: string;
}> = ({ props, dataModel, onAction, component }) => {
  const label = resolveBinding(props.label, dataModel);
  const variantMap: Record<string, "default" | "secondary" | "destructive" | "ghost" | "outline"> = {
    primary: "default",
    secondary: "secondary",
    destructive: "destructive",
    ghost: "ghost",
    outline: "outline",
  };

  return (
    <Button
      variant={variantMap[props.variant || "primary"]}
      size={props.size === "md" ? "default" : props.size}
      disabled={props.disabled || props.loading}
      onClick={() => {
        component.events?.forEach((event) => {
          if (event.event === "click") {
            onAction?.({ type: event.action.type, payload: event.action.payload });
          }
        });
      }}
    >
      {props.loading && <span className="mr-2 animate-spin">⟳</span>}
      {label}
    </Button>
  );
};

// Card Widget
const CardWidget: A2UIWidget<{
  title?: string;
  description?: string;
  footer?: string;
  variant?: "default" | "outlined" | "elevated";
}> = ({ props, dataModel, children }) => {
  const title = props.title ? resolveBinding(props.title, dataModel) : undefined;
  const description = props.description ? resolveBinding(props.description, dataModel) : undefined;
  const footer = props.footer ? resolveBinding(props.footer, dataModel) : undefined;

  const variantClasses: Record<string, string> = {
    default: "",
    outlined: "border-2",
    elevated: "shadow-lg",
  };

  return (
    <Card className={variantClasses[props.variant || "default"]}>
      {(title || description) && (
        <CardHeader>
          {title && <CardTitle>{title}</CardTitle>}
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
      )}
      <CardContent>{children}</CardContent>
      {footer && <CardFooter>{footer}</CardFooter>}
    </Card>
  );
};

// Badge Widget
const BadgeWidget: A2UIWidget<{
  label: string;
  variant?: "default" | "success" | "warning" | "error" | "info";
  size?: "sm" | "md";
}> = ({ props, dataModel }) => {
  const label = resolveBinding(props.label, dataModel);
  const variantMap: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
    default: "default",
    success: "default",
    warning: "secondary",
    error: "destructive",
    info: "outline",
  };

  return (
    <Badge
      variant={variantMap[props.variant || "default"]}
      className={props.size === "sm" ? "text-xs px-1.5 py-0" : ""}
    >
      {label}
    </Badge>
  );
};

// Progress Widget
const ProgressWidget: A2UIWidget<{
  value: number;
  max?: number;
  label?: string;
  showValue?: boolean;
  color?: "default" | "success" | "warning" | "error";
  size?: "sm" | "md" | "lg";
}> = ({ props, dataModel }) => {
  const value = typeof props.value === "string"
    ? resolveBinding(props.value, dataModel) as number
    : props.value;
  const max = props.max || 100;
  const percentage = (value / max) * 100;

  const sizeClasses: Record<string, string> = {
    sm: "h-1",
    md: "h-2",
    lg: "h-3",
  };

  return (
    <div className="w-full space-y-1">
      {(props.label || props.showValue) && (
        <div className="flex justify-between text-xs text-muted-foreground">
          {props.label && <span>{props.label}</span>}
          {props.showValue && <span>{value}/{max}</span>}
        </div>
      )}
      <Progress value={percentage} className={sizeClasses[props.size || "md"]} />
    </div>
  );
};

// Stat Widget
const StatWidget: A2UIWidget<{
  label: string;
  value: string | number;
  unit?: string;
  trend?: "up" | "down" | "stable";
  trendValue?: string;
  trendColor?: "success" | "warning" | "error";
}> = ({ props, dataModel }) => {
  const label = resolveBinding(props.label, dataModel);
  const value = resolveBinding(String(props.value), dataModel);

  const trendIcons: Record<string, string> = {
    up: "↑",
    down: "↓",
    stable: "→",
  };

  const trendColors: Record<string, string> = {
    success: "text-success",
    warning: "text-warning",
    error: "text-error",
  };

  return (
    <div className="flex flex-col space-y-1">
      <span className="text-xs text-muted-foreground uppercase tracking-wide">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold">{value}</span>
        {props.unit && <span className="text-sm text-muted-foreground">{props.unit}</span>}
        {props.trend && props.trendValue && (
          <span className={`text-xs ${trendColors[props.trendColor || "success"]}`}>
            {trendIcons[props.trend]} {props.trendValue}
          </span>
        )}
      </div>
    </div>
  );
};

// Code Widget
const CodeWidget: A2UIWidget<{
  content: string;
  language?: string;
  showLineNumbers?: boolean;
  copyable?: boolean;
  maxHeight?: string | number;
}> = ({ props, dataModel }) => {
  const content = resolveBinding(props.content, dataModel);
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group">
      <ScrollArea
        className="rounded-md bg-muted/50 border"
        style={{ maxHeight: props.maxHeight || "300px" }}
      >
        <pre className="p-4 text-sm font-mono overflow-x-auto">
          <code>{content}</code>
        </pre>
      </ScrollArea>
      {props.copyable !== false && (
        <button
          onClick={handleCopy}
          className="absolute top-2 right-2 p-1.5 rounded bg-background/80 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          {copied ? "✓" : "📋"}
        </button>
      )}
    </div>
  );
};

// Table Widget
const TableWidget: A2UIWidget<{
  columns: Array<{
    key: string;
    header: string;
    width?: string | number;
    align?: "left" | "center" | "right";
    render?: string;
  }>;
  sortable?: boolean;
  filterable?: boolean;
  pagination?: boolean;
  pageSize?: number;
}> = ({ props, dataModel, component }) => {
  const data = component.dataBinding
    ? (resolveBinding(component.dataBinding, dataModel) as unknown[]) || []
    : [];

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            {props.columns.map((col) => (
              <TableHead
                key={col.key}
                style={{ width: col.width }}
                className={col.align === "center" ? "text-center" : col.align === "right" ? "text-right" : ""}
              >
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row: unknown, idx) => (
            <TableRow key={idx}>
              {props.columns.map((col) => (
                <TableCell
                  key={col.key}
                  className={col.align === "center" ? "text-center" : col.align === "right" ? "text-right" : ""}
                >
                  {renderCellValue((row as Record<string, unknown>)[col.key], col.render)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};

// Helper for table cell rendering
function renderCellValue(value: unknown, render?: string): ReactNode {
  if (value === null || value === undefined) return "-";

  switch (render) {
    case "badge":
      return <Badge variant="outline">{String(value)}</Badge>;
    case "progress":
      return <Progress value={Number(value)} className="h-2 w-20" />;
    case "time":
      return new Date(String(value)).toLocaleString();
    case "code":
      return <code className="text-xs bg-muted px-1 rounded">{String(value)}</code>;
    default:
      return String(value);
  }
}

// =============================================================================
// Registry
// =============================================================================

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const componentRegistry: Map<A2UIComponentType, A2UIWidget<any>> = new Map([
  ["text", TextWidget],
  ["heading", HeadingWidget],
  ["button", ButtonWidget],
  ["card", CardWidget],
  ["badge", BadgeWidget],
  ["progress", ProgressWidget],
  ["stat", StatWidget],
  ["code", CodeWidget],
  ["table", TableWidget],
]);

// =============================================================================
// Registry API
// =============================================================================

export function registerWidget<P>(type: A2UIComponentType, widget: A2UIWidget<P>): void {
  componentRegistry.set(type, widget);
}

export function getWidget(type: A2UIComponentType): A2UIWidget | undefined {
  return componentRegistry.get(type);
}

export function hasWidget(type: A2UIComponentType): boolean {
  return componentRegistry.has(type);
}

export function listWidgets(): A2UIComponentType[] {
  return Array.from(componentRegistry.keys());
}

// =============================================================================
// Data Binding Resolution
// =============================================================================

export function resolveBinding(value: string | unknown, dataModel: A2UIDataModel): unknown {
  if (typeof value !== "string") return value;

  // Check if it's a data binding expression (e.g., "{{path.to.value}}")
  const bindingMatch = value.match(/^\{\{(.+)\}\}$/);
  if (!bindingMatch) return value;

  const path = bindingMatch[1];
  return getNestedValue(dataModel, path);
}

function getNestedValue(obj: A2UIDataModel, path: string): unknown {
  const keys = path.split(".");
  let value: unknown = obj;

  for (const key of keys) {
    if (value && typeof value === "object" && key in value) {
      value = (value as Record<string, unknown>)[key];
    } else {
      return undefined;
    }
  }

  return value;
}

// =============================================================================
// Default Export
// =============================================================================

export default {
  register: registerWidget,
  get: getWidget,
  has: hasWidget,
  list: listWidgets,
  resolve: resolveBinding,
};
