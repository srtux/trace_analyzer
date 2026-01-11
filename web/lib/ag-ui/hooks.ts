/**
 * AG-UI Protocol Hooks
 *
 * React hooks for managing AG-UI protocol state, event streaming,
 * and agent interactions.
 */

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type {
  AGUIEvent,
  AGUIRunState,
  AGUIMessage,
  AGUIToolCall,
  AGUIStep,
  RunStatus,
  HITLRequest,
  HITLResponse,
} from "@/types/ag-ui";

// =============================================================================
// Initial State
// =============================================================================

const initialRunState: AGUIRunState = {
  runId: null,
  status: "idle",
  currentAgent: null,
  messages: [],
  toolCalls: [],
  steps: [],
  sharedState: {},
  error: null,
};

// =============================================================================
// Actions
// =============================================================================

type AGUIAction =
  | { type: "RUN_STARTED"; payload: { runId: string; agentName?: string } }
  | { type: "RUN_FINISHED"; payload: { result?: unknown } }
  | { type: "RUN_ERROR"; payload: { code: string; message: string } }
  | { type: "MESSAGE_START"; payload: AGUIMessage }
  | { type: "MESSAGE_CONTENT"; payload: { messageId: string; delta: string } }
  | { type: "MESSAGE_END"; payload: { messageId: string } }
  | { type: "TOOL_CALL_START"; payload: AGUIToolCall }
  | { type: "TOOL_CALL_ARGS"; payload: { toolCallId: string; args: Record<string, unknown> } }
  | { type: "TOOL_CALL_END"; payload: { toolCallId: string; result?: unknown; error?: { code: string; message: string } } }
  | { type: "STATE_SNAPSHOT"; payload: Record<string, unknown> }
  | { type: "STATE_DELTA"; payload: { path: string; value: unknown }[] }
  | { type: "STEP_STARTED"; payload: AGUIStep }
  | { type: "STEP_FINISHED"; payload: { stepId: string; result?: unknown } }
  | { type: "RESET" };

// =============================================================================
// Reducer
// =============================================================================

function aguiReducer(state: AGUIRunState, action: AGUIAction): AGUIRunState {
  switch (action.type) {
    case "RUN_STARTED":
      return {
        ...initialRunState,
        runId: action.payload.runId,
        status: "running",
        currentAgent: action.payload.agentName || null,
      };

    case "RUN_FINISHED":
      return {
        ...state,
        status: "completed",
      };

    case "RUN_ERROR":
      return {
        ...state,
        status: "error",
        error: action.payload,
      };

    case "MESSAGE_START":
      return {
        ...state,
        messages: [...state.messages, action.payload],
      };

    case "MESSAGE_CONTENT":
      return {
        ...state,
        messages: state.messages.map((msg) =>
          msg.id === action.payload.messageId
            ? { ...msg, content: msg.content + action.payload.delta }
            : msg
        ),
      };

    case "MESSAGE_END":
      return {
        ...state,
        messages: state.messages.map((msg) =>
          msg.id === action.payload.messageId
            ? { ...msg, isStreaming: false }
            : msg
        ),
      };

    case "TOOL_CALL_START":
      return {
        ...state,
        toolCalls: [...state.toolCalls, action.payload],
      };

    case "TOOL_CALL_ARGS":
      return {
        ...state,
        toolCalls: state.toolCalls.map((tc) =>
          tc.id === action.payload.toolCallId
            ? { ...tc, args: { ...tc.args, ...action.payload.args } }
            : tc
        ),
      };

    case "TOOL_CALL_END":
      return {
        ...state,
        toolCalls: state.toolCalls.map((tc) =>
          tc.id === action.payload.toolCallId
            ? {
                ...tc,
                status: action.payload.error ? "error" : "completed",
                result: action.payload.result,
                error: action.payload.error,
                endTime: new Date().toISOString(),
              }
            : tc
        ),
      };

    case "STATE_SNAPSHOT":
      return {
        ...state,
        sharedState: action.payload,
      };

    case "STATE_DELTA":
      const newState = { ...state.sharedState };
      for (const { path, value } of action.payload) {
        setNestedValue(newState, path, value);
      }
      return {
        ...state,
        sharedState: newState,
      };

    case "STEP_STARTED":
      return {
        ...state,
        steps: [...state.steps, action.payload],
        currentAgent: action.payload.agentName || state.currentAgent,
      };

    case "STEP_FINISHED":
      return {
        ...state,
        steps: state.steps.map((step) =>
          step.id === action.payload.stepId
            ? {
                ...step,
                status: "completed",
                result: action.payload.result,
                endTime: new Date().toISOString(),
              }
            : step
        ),
      };

    case "RESET":
      return initialRunState;

    default:
      return state;
  }
}

// Helper to set nested values
function setNestedValue(obj: Record<string, unknown>, path: string, value: unknown): void {
  const keys = path.split(".");
  let current = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i];
    if (!(key in current)) {
      current[key] = {};
    }
    current = current[key] as Record<string, unknown>;
  }
  current[keys[keys.length - 1]] = value;
}

// =============================================================================
// Main Hook: useAGUI
// =============================================================================

export interface UseAGUIOptions {
  endpoint?: string;
  onEvent?: (event: AGUIEvent) => void;
  onHITLRequest?: (request: HITLRequest) => Promise<HITLResponse>;
}

export interface UseAGUIReturn {
  state: AGUIRunState;
  isRunning: boolean;
  isStreaming: boolean;
  currentMessage: AGUIMessage | null;
  activeToolCalls: AGUIToolCall[];
  pendingHITL: HITLRequest | null;

  // Actions
  startRun: (input: string, context?: Record<string, unknown>) => Promise<void>;
  cancelRun: () => void;
  respondToHITL: (response: HITLResponse) => void;
  reset: () => void;

  // Subscriptions
  subscribe: (callback: (event: AGUIEvent) => void) => () => void;
}

export function useAGUI(options: UseAGUIOptions = {}): UseAGUIReturn {
  const { endpoint = "/api/copilotkit", onEvent, onHITLRequest } = options;

  const [state, dispatch] = useReducer(aguiReducer, initialRunState);
  const [pendingHITL, setPendingHITL] = useState<HITLRequest | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const subscribersRef = useRef<Set<(event: AGUIEvent) => void>>(new Set());

  const isRunning = state.status === "running";
  const isStreaming = state.messages.some((m) => m.isStreaming);
  const currentMessage = state.messages.find((m) => m.isStreaming) || null;
  const activeToolCalls = state.toolCalls.filter((tc) => tc.status === "running");

  // Process incoming AG-UI events
  const processEvent = useCallback((event: AGUIEvent) => {
    // Notify subscribers
    subscribersRef.current.forEach((callback) => callback(event));
    onEvent?.(event);

    // Update state based on event type
    switch (event.type) {
      case "RUN_STARTED":
        dispatch({
          type: "RUN_STARTED",
          payload: { runId: event.runId, agentName: event.agentName },
        });
        break;

      case "RUN_FINISHED":
        dispatch({ type: "RUN_FINISHED", payload: { result: event.result } });
        break;

      case "RUN_ERROR":
        dispatch({ type: "RUN_ERROR", payload: event.error });
        break;

      case "TEXT_MESSAGE_START":
        dispatch({
          type: "MESSAGE_START",
          payload: {
            id: event.messageId,
            role: event.role,
            content: "",
            timestamp: event.timestamp,
            isStreaming: true,
          },
        });
        break;

      case "TEXT_MESSAGE_CONTENT":
        dispatch({
          type: "MESSAGE_CONTENT",
          payload: { messageId: event.messageId, delta: event.delta },
        });
        break;

      case "TEXT_MESSAGE_END":
        dispatch({ type: "MESSAGE_END", payload: { messageId: event.messageId } });
        break;

      case "TOOL_CALL_START":
        dispatch({
          type: "TOOL_CALL_START",
          payload: {
            id: event.toolCallId,
            toolName: event.toolName,
            args: {},
            status: "running",
            startTime: event.timestamp,
            parentToolCallId: event.parentToolCallId,
          },
        });
        break;

      case "TOOL_CALL_ARGS":
        if (event.args) {
          dispatch({
            type: "TOOL_CALL_ARGS",
            payload: { toolCallId: event.toolCallId, args: event.args },
          });
        }
        break;

      case "TOOL_CALL_END":
        dispatch({
          type: "TOOL_CALL_END",
          payload: {
            toolCallId: event.toolCallId,
            result: event.result,
            error: event.error,
          },
        });
        break;

      case "STATE_SNAPSHOT":
        dispatch({ type: "STATE_SNAPSHOT", payload: event.snapshot });
        break;

      case "STATE_DELTA":
        dispatch({
          type: "STATE_DELTA",
          payload: event.delta.map((op) => ({ path: op.path, value: op.value })),
        });
        break;

      case "STEP_STARTED":
        dispatch({
          type: "STEP_STARTED",
          payload: {
            id: event.stepId,
            name: event.stepName,
            agentName: event.agentName,
            description: event.description,
            status: "running",
            startTime: event.timestamp,
          },
        });
        break;

      case "STEP_FINISHED":
        dispatch({
          type: "STEP_FINISHED",
          payload: { stepId: event.stepId, result: event.result },
        });
        break;

      case "CUSTOM":
        // Handle custom events (like HITL requests)
        if (event.eventName === "HITL_REQUEST" && onHITLRequest) {
          const request = event.payload as HITLRequest;
          setPendingHITL(request);
          onHITLRequest(request).then((response) => {
            setPendingHITL(null);
            // Send response back (implementation depends on transport)
          });
        }
        break;
    }
  }, [onEvent, onHITLRequest]);

  // Start a new run
  const startRun = useCallback(async (input: string, context?: Record<string, unknown>) => {
    // Cancel any existing run
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input, context }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Handle SSE stream
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6)) as AGUIEvent;
              processEvent(event);
            } catch {
              // Ignore parse errors for non-JSON data
            }
          }
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name !== "AbortError") {
        dispatch({
          type: "RUN_ERROR",
          payload: { code: "FETCH_ERROR", message: error.message },
        });
      }
    }
  }, [endpoint, processEvent]);

  // Cancel current run
  const cancelRun = useCallback(() => {
    abortControllerRef.current?.abort();
    dispatch({ type: "RUN_FINISHED", payload: {} });
  }, []);

  // Respond to HITL request
  const respondToHITL = useCallback((response: HITLResponse) => {
    setPendingHITL(null);
    // Implementation depends on transport mechanism
  }, []);

  // Reset state
  const reset = useCallback(() => {
    abortControllerRef.current?.abort();
    dispatch({ type: "RESET" });
    setPendingHITL(null);
  }, []);

  // Subscribe to events
  const subscribe = useCallback((callback: (event: AGUIEvent) => void) => {
    subscribersRef.current.add(callback);
    return () => {
      subscribersRef.current.delete(callback);
    };
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  return {
    state,
    isRunning,
    isStreaming,
    currentMessage,
    activeToolCalls,
    pendingHITL,
    startRun,
    cancelRun,
    respondToHITL,
    reset,
    subscribe,
  };
}

// =============================================================================
// Hook: useAGUISharedState
// =============================================================================

export function useAGUISharedState<T>(
  state: AGUIRunState,
  path: string
): T | undefined {
  const keys = path.split(".");
  let value: unknown = state.sharedState;

  for (const key of keys) {
    if (value && typeof value === "object" && key in value) {
      value = (value as Record<string, unknown>)[key];
    } else {
      return undefined;
    }
  }

  return value as T;
}

// =============================================================================
// Hook: useAGUIToolCalls
// =============================================================================

export interface UseAGUIToolCallsOptions {
  toolName?: string;
  status?: AGUIToolCall["status"];
}

export function useAGUIToolCalls(
  state: AGUIRunState,
  options: UseAGUIToolCallsOptions = {}
): AGUIToolCall[] {
  const { toolName, status } = options;

  return state.toolCalls.filter((tc) => {
    if (toolName && tc.toolName !== toolName) return false;
    if (status && tc.status !== status) return false;
    return true;
  });
}

// =============================================================================
// Hook: useAGUISteps
// =============================================================================

export function useAGUISteps(state: AGUIRunState): {
  steps: AGUIStep[];
  currentStep: AGUIStep | null;
  completedSteps: AGUIStep[];
  progress: number;
} {
  const currentStep = state.steps.find((s) => s.status === "running") || null;
  const completedSteps = state.steps.filter((s) => s.status === "completed");
  const progress = state.steps.length > 0
    ? (completedSteps.length / state.steps.length) * 100
    : 0;

  return {
    steps: state.steps,
    currentStep,
    completedSteps,
    progress,
  };
}
