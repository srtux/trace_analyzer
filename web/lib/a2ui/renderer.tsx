/**
 * A2UI Renderer
 *
 * The A2UI Renderer parses A2UI JSON payloads and maps abstract components
 * to concrete React implementations using the widget registry.
 */

"use client";

import React, { ReactNode, useCallback, useMemo } from "react";
import type {
  A2UIResponse,
  A2UISurface,
  A2UIComponent,
  A2UIDataModel,
  A2UILayout,
  A2UIAction,
} from "@/types/a2ui";
import { getWidget, resolveBinding, hasWidget } from "./registry";
import { cn } from "@/lib/utils";

// =============================================================================
// Types
// =============================================================================

export interface A2UIRendererProps {
  response: A2UIResponse;
  className?: string;
  onAction?: (action: A2UIAction) => void;
  fallback?: (component: A2UIComponent) => ReactNode;
}

export interface SurfaceRendererProps {
  surface: A2UISurface;
  dataModel: A2UIDataModel;
  onAction?: (action: A2UIAction) => void;
  fallback?: (component: A2UIComponent) => ReactNode;
}

export interface ComponentRendererProps {
  component: A2UIComponent;
  dataModel: A2UIDataModel;
  onAction?: (action: A2UIAction) => void;
  fallback?: (component: A2UIComponent) => ReactNode;
}

// =============================================================================
// Layout Renderer
// =============================================================================

function LayoutWrapper({
  layout,
  children,
  className,
}: {
  layout?: A2UILayout;
  children: ReactNode;
  className?: string;
}) {
  if (!layout) {
    return <div className={cn("flex flex-col gap-4", className)}>{children}</div>;
  }

  const layoutClasses: Record<string, string> = {
    stack: layout.direction === "horizontal" ? "flex flex-row" : "flex flex-col",
    grid: "grid",
    flow: "flex flex-wrap",
    split: "flex",
  };

  const gapClass = layout.gap ? `gap-${layout.gap}` : "gap-4";
  const paddingClass = layout.padding ? `p-${layout.padding}` : "";
  const columnsClass = layout.columns ? `grid-cols-${layout.columns}` : "";

  return (
    <div
      className={cn(
        layoutClasses[layout.type] || "flex flex-col",
        gapClass,
        paddingClass,
        columnsClass,
        className
      )}
    >
      {children}
    </div>
  );
}

// =============================================================================
// Component Renderer
// =============================================================================

function ComponentRenderer({
  component,
  dataModel,
  onAction,
  fallback,
}: ComponentRendererProps): ReactNode {
  // Check conditional rendering
  if (component.conditionalRender) {
    const { dataPath, operator, value } = component.conditionalRender;
    const actualValue = resolveBinding(`{{${dataPath}}}`, dataModel);

    let shouldRender = false;
    switch (operator) {
      case "eq":
        shouldRender = actualValue === value;
        break;
      case "ne":
        shouldRender = actualValue !== value;
        break;
      case "gt":
        shouldRender = Number(actualValue) > Number(value);
        break;
      case "lt":
        shouldRender = Number(actualValue) < Number(value);
        break;
      case "gte":
        shouldRender = Number(actualValue) >= Number(value);
        break;
      case "lte":
        shouldRender = Number(actualValue) <= Number(value);
        break;
      case "contains":
        shouldRender = String(actualValue).includes(String(value));
        break;
      case "exists":
        shouldRender = actualValue !== undefined && actualValue !== null;
        break;
    }

    if (!shouldRender) return null;
  }

  // Get widget from registry
  const Widget = getWidget(component.type);

  // Handle unknown component types
  if (!Widget) {
    if (fallback) {
      return fallback(component);
    }
    console.warn(`Unknown A2UI component type: ${component.type}`);
    return (
      <div className="p-2 border border-dashed border-warning rounded text-xs text-warning">
        Unknown component: {component.type}
      </div>
    );
  }

  // Render children if any
  const children = component.children?.map((child, index) => (
    <ComponentRenderer
      key={child.id || index}
      component={child}
      dataModel={dataModel}
      onAction={onAction}
      fallback={fallback}
    />
  ));

  // Apply custom styles
  const style: React.CSSProperties = {};
  if (component.style) {
    if (component.style.width) style.width = component.style.width;
    if (component.style.height) style.height = component.style.height;
    if (component.style.padding) style.padding = component.style.padding;
    if (component.style.margin) style.margin = component.style.margin;
    if (component.style.backgroundColor) style.backgroundColor = component.style.backgroundColor;
    if (component.style.borderRadius) style.borderRadius = component.style.borderRadius;
    if (component.style.border) style.border = component.style.border;
  }

  const wrapperClassName = component.style?.className || "";

  return (
    <div style={style} className={wrapperClassName}>
      <Widget
        component={component}
        props={component.props || {}}
        dataModel={dataModel}
        onAction={onAction}
      >
        {children}
      </Widget>
    </div>
  );
}

// =============================================================================
// Surface Renderer
// =============================================================================

function SurfaceRenderer({
  surface,
  dataModel,
  onAction,
  fallback,
}: SurfaceRendererProps): ReactNode {
  return (
    <LayoutWrapper layout={surface.layout}>
      {surface.components.map((component, index) => (
        <ComponentRenderer
          key={component.id || index}
          component={component}
          dataModel={dataModel}
          onAction={onAction}
          fallback={fallback}
        />
      ))}
    </LayoutWrapper>
  );
}

// =============================================================================
// Main Renderer Component
// =============================================================================

export function A2UIRenderer({
  response,
  className,
  onAction,
  fallback,
}: A2UIRendererProps): ReactNode {
  const dataModel = useMemo(() => response.dataModel || {}, [response.dataModel]);

  const handleAction = useCallback(
    (action: A2UIAction) => {
      // Handle confirm dialogs
      if (action.confirm) {
        const confirmed = window.confirm(
          `${action.confirm.title}\n\n${action.confirm.message}`
        );
        if (!confirmed) return;
      }

      onAction?.(action);
    },
    [onAction]
  );

  return (
    <div className={cn("a2ui-surface", className)}>
      <SurfaceRenderer
        surface={response.surface}
        dataModel={dataModel}
        onAction={handleAction}
        fallback={fallback}
      />
    </div>
  );
}

// =============================================================================
// Incremental Update Handler
// =============================================================================

export function applyDataModelUpdate(
  dataModel: A2UIDataModel,
  update: { path: string; operation: string; value?: unknown }
): A2UIDataModel {
  const newModel = { ...dataModel };
  const keys = update.path.split(".");

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let current: any = newModel;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i];
    if (!(key in current)) {
      current[key] = {};
    }
    current = current[key];
  }

  const lastKey = keys[keys.length - 1];

  switch (update.operation) {
    case "set":
      current[lastKey] = update.value;
      break;
    case "merge":
      current[lastKey] = { ...current[lastKey], ...(update.value as object) };
      break;
    case "delete":
      delete current[lastKey];
      break;
    case "append":
      if (Array.isArray(current[lastKey])) {
        current[lastKey] = [...current[lastKey], update.value];
      }
      break;
    case "prepend":
      if (Array.isArray(current[lastKey])) {
        current[lastKey] = [update.value, ...current[lastKey]];
      }
      break;
  }

  return newModel;
}

// =============================================================================
// Hooks
// =============================================================================

export function useA2UIState(initialResponse?: A2UIResponse) {
  const [response, setResponse] = React.useState<A2UIResponse | null>(
    initialResponse || null
  );

  const updateSurface = useCallback((surface: A2UISurface) => {
    setResponse((prev) =>
      prev ? { ...prev, surface } : null
    );
  }, []);

  const updateDataModel = useCallback(
    (update: { path: string; operation: string; value?: unknown }) => {
      setResponse((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          dataModel: applyDataModelUpdate(prev.dataModel || {}, update),
        };
      });
    },
    []
  );

  const reset = useCallback(() => {
    setResponse(initialResponse || null);
  }, [initialResponse]);

  return {
    response,
    setResponse,
    updateSurface,
    updateDataModel,
    reset,
  };
}
