/**
 * useToolFlowState Hook
 *
 * Integrates AG-UI protocol events with the AgentToolFlow component.
 * Converts streaming events into the AgentRun data structure.
 */

import { useCallback, useReducer, useEffect } from "react";
import type { AGUIEvent, AGUIRunState } from "@/types/ag-ui";
import type { ToolCall, AgentRun, ToolCallStatus } from "@/components/sre-widgets/AgentToolFlow";

// =============================================================================
// State Types
// =============================================================================

interface ToolFlowState {
  run: AgentRun | null;
  toolCallMap: Map<string, ToolCall>;
}

type ToolFlowAction =
  | { type: "RUN_START"; payload: { runId: string; agentName: string } }
  | { type: "RUN_END"; payload: { error?: boolean } }
  | { type: "TOOL_START"; payload: { id: string; toolName: string; parentId?: string; agentName?: string } }
  | { type: "TOOL_ARGS"; payload: { id: string; args?: Record<string, unknown>; argsStreaming?: string } }
  | { type: "TOOL_END"; payload: { id: string; result?: unknown; error?: { code: string; message: string } } }
  | { type: "RESET" };

// =============================================================================
// Reducer
// =============================================================================

function toolFlowReducer(state: ToolFlowState, action: ToolFlowAction): ToolFlowState {
  switch (action.type) {
    case "RUN_START": {
      return {
        run: {
          runId: action.payload.runId,
          status: "running",
          agentName: action.payload.agentName,
          startTime: new Date().toISOString(),
          toolCalls: [],
          totalToolCalls: 0,
          completedToolCalls: 0,
          errorCount: 0,
        },
        toolCallMap: new Map(),
      };
    }

    case "RUN_END": {
      if (!state.run) return state;
      return {
        ...state,
        run: {
          ...state.run,
          status: action.payload.error ? "error" : "completed",
          endTime: new Date().toISOString(),
        },
      };
    }

    case "TOOL_START": {
      if (!state.run) return state;

      const newCall: ToolCall = {
        id: action.payload.id,
        toolName: action.payload.toolName,
        displayName: formatToolName(action.payload.toolName),
        status: "running",
        args: {},
        startTime: new Date().toISOString(),
        parentId: action.payload.parentId,
        metadata: {
          agentName: action.payload.agentName,
        },
      };

      const newMap = new Map(state.toolCallMap);
      newMap.set(action.payload.id, newCall);

      return {
        run: {
          ...state.run,
          toolCalls: [...state.run.toolCalls, newCall],
          totalToolCalls: state.run.totalToolCalls + 1,
        },
        toolCallMap: newMap,
      };
    }

    case "TOOL_ARGS": {
      if (!state.run) return state;

      const call = state.toolCallMap.get(action.payload.id);
      if (!call) return state;

      const updatedCall: ToolCall = {
        ...call,
        status: action.payload.argsStreaming ? "streaming" : call.status,
        args: action.payload.args || call.args,
        argsStreaming: action.payload.argsStreaming,
      };

      const newMap = new Map(state.toolCallMap);
      newMap.set(action.payload.id, updatedCall);

      return {
        run: {
          ...state.run,
          toolCalls: state.run.toolCalls.map((c) =>
            c.id === action.payload.id ? updatedCall : c
          ),
        },
        toolCallMap: newMap,
      };
    }

    case "TOOL_END": {
      if (!state.run) return state;

      const call = state.toolCallMap.get(action.payload.id);
      if (!call) return state;

      const endTime = new Date().toISOString();
      const status: ToolCallStatus = action.payload.error ? "error" : "completed";

      const updatedCall: ToolCall = {
        ...call,
        status,
        result: action.payload.result,
        error: action.payload.error,
        endTime,
        durationMs: new Date(endTime).getTime() - new Date(call.startTime).getTime(),
        argsStreaming: undefined, // Clear streaming state
      };

      const newMap = new Map(state.toolCallMap);
      newMap.set(action.payload.id, updatedCall);

      return {
        run: {
          ...state.run,
          toolCalls: state.run.toolCalls.map((c) =>
            c.id === action.payload.id ? updatedCall : c
          ),
          completedToolCalls: action.payload.error
            ? state.run.completedToolCalls
            : state.run.completedToolCalls + 1,
          errorCount: action.payload.error
            ? state.run.errorCount + 1
            : state.run.errorCount,
        },
        toolCallMap: newMap,
      };
    }

    case "RESET": {
      return {
        run: null,
        toolCallMap: new Map(),
      };
    }

    default:
      return state;
  }
}

// =============================================================================
// Helper Functions
// =============================================================================

function formatToolName(toolName: string): string {
  return toolName
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// =============================================================================
// Main Hook
// =============================================================================

export interface UseToolFlowStateOptions {
  onToolStart?: (call: ToolCall) => void;
  onToolEnd?: (call: ToolCall) => void;
  onRunEnd?: (run: AgentRun) => void;
}

export interface UseToolFlowStateReturn {
  run: AgentRun | null;
  processEvent: (event: AGUIEvent) => void;
  reset: () => void;
  getToolCall: (id: string) => ToolCall | undefined;
}

export function useToolFlowState(
  options: UseToolFlowStateOptions = {}
): UseToolFlowStateReturn {
  const { onToolStart, onToolEnd, onRunEnd } = options;

  const [state, dispatch] = useReducer(toolFlowReducer, {
    run: null,
    toolCallMap: new Map(),
  });

  const processEvent = useCallback((event: AGUIEvent) => {
    switch (event.type) {
      case "RUN_STARTED":
        dispatch({
          type: "RUN_START",
          payload: {
            runId: event.runId,
            agentName: event.agentName || "Agent",
          },
        });
        break;

      case "RUN_FINISHED":
        dispatch({ type: "RUN_END", payload: {} });
        break;

      case "RUN_ERROR":
        dispatch({ type: "RUN_END", payload: { error: true } });
        break;

      case "TOOL_CALL_START":
        dispatch({
          type: "TOOL_START",
          payload: {
            id: event.toolCallId,
            toolName: event.toolName,
            parentId: event.parentToolCallId,
          },
        });
        break;

      case "TOOL_CALL_ARGS":
        dispatch({
          type: "TOOL_ARGS",
          payload: {
            id: event.toolCallId,
            args: event.args,
            argsStreaming: event.delta,
          },
        });
        break;

      case "TOOL_CALL_END":
        dispatch({
          type: "TOOL_END",
          payload: {
            id: event.toolCallId,
            result: event.result,
            error: event.error,
          },
        });
        break;

      case "STEP_STARTED":
        // Could track agent steps separately if needed
        break;
    }
  }, []);

  // Call callbacks when state changes
  useEffect(() => {
    if (!state.run) return;

    // Check for newly started tools
    for (const call of state.run.toolCalls) {
      if (call.status === "running" && onToolStart) {
        onToolStart(call);
      }
    }
  }, [state.run?.toolCalls, onToolStart]);

  useEffect(() => {
    if (!state.run) return;

    // Check for completed tools
    for (const call of state.run.toolCalls) {
      if ((call.status === "completed" || call.status === "error") && onToolEnd) {
        onToolEnd(call);
      }
    }
  }, [state.run?.toolCalls, onToolEnd]);

  useEffect(() => {
    if (state.run?.status === "completed" || state.run?.status === "error") {
      onRunEnd?.(state.run);
    }
  }, [state.run?.status, onRunEnd]);

  const reset = useCallback(() => {
    dispatch({ type: "RESET" });
  }, []);

  const getToolCall = useCallback((id: string) => {
    return state.toolCallMap.get(id);
  }, [state.toolCallMap]);

  return {
    run: state.run,
    processEvent,
    reset,
    getToolCall,
  };
}

// =============================================================================
// Integration with useAGUI
// =============================================================================

export function useAGUIToolFlow(aguiState: AGUIRunState): AgentRun | null {
  // Convert AGUI state to AgentRun format
  if (!aguiState.runId) return null;

  const toolCalls: ToolCall[] = aguiState.toolCalls.map((tc) => ({
    id: tc.id,
    toolName: tc.toolName,
    displayName: formatToolName(tc.toolName),
    status: tc.status === "pending" ? "pending"
      : tc.status === "running" ? "running"
      : tc.status === "completed" ? "completed"
      : "error",
    args: tc.args,
    result: tc.result,
    error: tc.error,
    startTime: tc.startTime,
    endTime: tc.endTime,
    durationMs: tc.endTime
      ? new Date(tc.endTime).getTime() - new Date(tc.startTime).getTime()
      : undefined,
    parentId: tc.parentToolCallId,
  }));

  const completedCalls = toolCalls.filter((c) => c.status === "completed").length;
  const errorCalls = toolCalls.filter((c) => c.status === "error").length;

  return {
    runId: aguiState.runId,
    status: aguiState.status === "idle" ? "idle"
      : aguiState.status === "running" ? "running"
      : aguiState.status === "completed" ? "completed"
      : "error",
    agentName: aguiState.currentAgent || "Agent",
    startTime: toolCalls[0]?.startTime || new Date().toISOString(),
    endTime: aguiState.status === "completed" || aguiState.status === "error"
      ? toolCalls[toolCalls.length - 1]?.endTime
      : undefined,
    toolCalls,
    totalToolCalls: toolCalls.length,
    completedToolCalls: completedCalls,
    errorCount: errorCalls,
  };
}
