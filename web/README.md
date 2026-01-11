# SRE Mission Control Dashboard

A **Generative UI** frontend for the SRE Agent, providing an AI-powered "Mission Control" experience for investigating production incidents. Built with Next.js 14, CopilotKit, and Shadcn UI.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Directory Structure](#directory-structure)
- [Getting Started](#getting-started)
- [Component Reference](#component-reference)
- [Type System](#type-system)
- [CopilotKit Actions](#copilotkit-actions)
- [Mock Data](#mock-data)
- [Deployment](#deployment)
- [Extending the Dashboard](#extending-the-dashboard)
- [Troubleshooting](#troubleshooting)

---

## Overview

This dashboard serves as the visual interface for the SRE Agent's "Council of Experts" architecture. Instead of dumping raw JSON into a chat window, it renders **rich, interactive widgets** when the agent returns structured analysis data.

### Key Concepts

1. **Conversational Investigation**: Users interact via natural language in the sidebar
2. **Generative UI**: Agent responses trigger purpose-built visualizations on the canvas
3. **Dark Mode Only**: SRE tools are used in NOCs and on-call situations—dark mode reduces eye strain
4. **Information Density**: Designed for SREs who need data at a glance, not marketing whitespace

### What It Does

| User Query | Agent Action | Canvas Result |
|------------|--------------|---------------|
| "Analyze this trace" | `analyzeTrace` | TraceWaterfall component |
| "Show me log patterns" | `analyzeLogPatterns` | LogPatternViewer with Drain3 clusters |
| "Check latency metrics" | `analyzeMetrics` | MetricCorrelationChart with anomalies |
| "How do I fix this?" | `getRemediationPlan` | RemediationPlan with gcloud commands |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           BROWSER                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      Status Bar (10%)                             │   │
│  │  [Agent: Latency Specialist] Analyzing span hierarchy... [45%]   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────┐  ┌────────────────────────────────────────────┐   │
│  │                 │  │                                            │   │
│  │   CopilotKit    │  │              Main Canvas                   │   │
│  │    Sidebar      │  │                                            │   │
│  │     (25%)       │  │   ┌────────────────────────────────────┐   │   │
│  │                 │  │   │                                    │   │   │
│  │  "Analyze the   │  │   │      TraceWaterfall               │   │   │
│  │   checkout      │  │   │      LogPatternViewer             │   │   │
│  │   trace..."     │  │   │      MetricCorrelationChart       │   │   │
│  │                 │  │   │      RemediationPlan              │   │   │
│  │  [Agent Reply]  │  │   │                                    │   │   │
│  │                 │  │   └────────────────────────────────────┘   │   │
│  │                 │  │                  (75%)                     │   │
│  └─────────────────┘  └────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ useCopilotAction
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    /api/copilotkit (Next.js API Route)                  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    CopilotRuntime                                 │   │
│  │                         │                                         │   │
│  │    ┌────────────────────┼────────────────────┐                   │   │
│  │    ▼                    ▼                    ▼                   │   │
│  │ analyzeTrace    analyzeLogPatterns    getRemediationPlan         │   │
│  │ analyzeMetrics  compareTraces         runCausalAnalysis          │   │
│  │ executeRemediation                                                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Future: Connect to SRE Agent Backend
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      SRE Agent (Python/ADK)                             │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Trace     │  │    Log      │  │   Metrics   │  │ Remediation │   │
│  │ Specialist  │  │  Pattern    │  │ Correlator  │  │   Advisor   │   │
│  │             │  │   Engine    │  │             │  │             │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User Input** → CopilotSidebar sends message to `/api/copilotkit`
2. **Action Dispatch** → CopilotRuntime matches intent to a `useCopilotAction`
3. **Agent Status** → UI updates StatusBar with current agent and progress
4. **Data Fetch** → Action handler calls backend (or returns mock data)
5. **Canvas Update** → `setCanvasView()` triggers widget render
6. **Response** → CopilotKit shows text summary in chat

---

## Tech Stack

| Category | Technology | Why |
|----------|------------|-----|
| **Framework** | Next.js 14 (App Router) | Server components, API routes, standalone builds |
| **Language** | TypeScript | Type safety matching backend Pydantic schemas |
| **Styling** | Tailwind CSS | Utility-first, easy dark mode, small bundle |
| **Components** | Shadcn UI | Enterprise-grade, accessible, customizable |
| **AI Interface** | CopilotKit | React SDK for AI copilots with tool calling |
| **Charts** | Recharts | React-native charting, good TypeScript support |
| **Icons** | Lucide React | Consistent, tree-shakeable icon library |
| **Date/Time** | date-fns | Lightweight date formatting |
| **Utilities** | clsx + tailwind-merge | Class name composition |

### Key Dependencies

```json
{
  "@copilotkit/react-core": "^1.3.15",
  "@copilotkit/react-ui": "^1.3.15",
  "@copilotkit/runtime": "^1.3.15",
  "recharts": "^2.12.7",
  "lucide-react": "^0.435.0",
  "date-fns": "^3.6.0"
}
```

---

## Directory Structure

```
web/
├── app/                          # Next.js App Router
│   ├── api/
│   │   └── copilotkit/
│   │       └── route.ts          # CopilotKit API endpoint
│   ├── globals.css               # Tailwind + CSS variables (dark theme)
│   ├── layout.tsx                # Root layout with dark class
│   └── page.tsx                  # Main dashboard (CopilotKit provider)
│
├── components/
│   ├── layout/                   # Structural components
│   │   ├── Canvas.tsx            # Main visualization area + view switching
│   │   ├── StatusBar.tsx         # Agent activity indicator
│   │   └── index.ts              # Barrel export
│   │
│   ├── sre-widgets/              # Domain-specific visualizations
│   │   ├── TraceWaterfall.tsx    # Gantt-chart trace view
│   │   ├── LogPatternViewer.tsx  # Drain3 pattern table
│   │   ├── MetricCorrelationChart.tsx  # Time-series with anomalies
│   │   ├── RemediationPlan.tsx   # Action cards with commands
│   │   └── index.ts              # Barrel export
│   │
│   └── ui/                       # Shadcn UI primitives
│       ├── button.tsx
│       ├── card.tsx
│       ├── badge.tsx
│       ├── dialog.tsx
│       ├── popover.tsx
│       ├── scroll-area.tsx
│       ├── table.tsx
│       ├── tabs.tsx
│       ├── tooltip.tsx
│       ├── accordion.tsx
│       └── alert.tsx
│
├── lib/
│   ├── utils.ts                  # Utility functions (cn, formatDuration, etc.)
│   └── mock-data.ts              # Realistic test data for all widgets
│
├── types/
│   └── adk-schema.ts             # TypeScript interfaces matching backend
│
├── public/
│   └── favicon.ico
│
├── Dockerfile                    # Multi-stage build for Cloud Run
├── .dockerignore
├── .env.example                  # Environment variable template
├── .eslintrc.json
├── .gitignore
├── next.config.mjs               # Standalone output enabled
├── package.json
├── postcss.config.js
├── tailwind.config.ts            # Dark theme + custom SRE colors
└── tsconfig.json
```

---

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- OpenAI API key (for CopilotKit)

### Installation

```bash
# Clone the repository
cd sre-agent/web

# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-key-here
```

### Development

```bash
# Start development server
npm run dev

# Open http://localhost:3000
```

### Production Build

```bash
# Create optimized build
npm run build

# Start production server
npm start
```

---

## Component Reference

### Layout Components

#### `StatusBar`

Displays the current agent activity at the top of the screen.

```tsx
import { StatusBar } from "@/components/layout";

<StatusBar agentStatus={{
  currentAgent: "latency_specialist",
  message: "Analyzing span hierarchy...",
  progress: 45,
  startTime: "2024-01-15T10:30:00Z"
}} />
```

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `agentStatus` | `AgentStatus` | Current agent type, message, progress |

**Agent Types:**
- `orchestrator` - Main coordinator
- `latency_specialist` - Trace latency analysis
- `error_analyst` - Error pattern detection
- `log_pattern_engine` - Drain3 log clustering
- `metrics_correlator` - Cross-signal correlation
- `remediation_advisor` - Fix suggestions
- `idle` - Ready state

---

#### `Canvas`

The main visualization area that renders different widgets based on the current view.

```tsx
import { Canvas } from "@/components/layout";

<Canvas
  view={{ type: "trace", data: traceData }}
  onExecuteRemediation={(action) => console.log(action)}
/>
```

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `view` | `CanvasView` | Current view type and data |
| `onExecuteRemediation` | `(action) => void` | Callback for remediation execution |

**View Types:**
- `{ type: "empty" }` - Shows welcome screen
- `{ type: "trace", data: Trace }` - TraceWaterfall
- `{ type: "trace_comparison", data: TraceComparisonReport }` - Comparison view
- `{ type: "log_patterns", data: LogPatternSummary }` - LogPatternViewer
- `{ type: "metrics", data: MetricWithAnomalies }` - MetricCorrelationChart
- `{ type: "remediation", data: RemediationSuggestion }` - RemediationPlan
- `{ type: "causal_analysis", data: CausalAnalysisReport }` - Causal chain view

---

### SRE Widgets

#### `TraceWaterfall`

A Gantt-chart style visualization for distributed traces.

```tsx
import { TraceWaterfall } from "@/components/sre-widgets";

<TraceWaterfall
  trace={traceData}
  onSpanClick={(span) => console.log(span)}
  highlightSpanId="span-123"
/>
```

**Features:**
- Hierarchical span display (indentation by depth)
- Color coding: Blue (normal), Yellow (>1s), Red (error)
- Click-to-expand span details (attributes, timestamps)
- Timeline header with duration markers
- Animated span bars

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `trace` | `Trace` | Trace data with spans array |
| `onSpanClick` | `(span) => void` | Span selection callback |
| `highlightSpanId` | `string` | ID of span to highlight |

---

#### `LogPatternViewer`

Displays Drain3-clustered log patterns in a sortable table.

```tsx
import { LogPatternViewer } from "@/components/sre-widgets";

<LogPatternViewer
  data={logPatternSummary}
  onPatternClick={(pattern) => console.log(pattern)}
/>
```

**Features:**
- Filter by severity (All / Errors / Warnings)
- Occurrence count bar chart in each row
- Expandable rows with sample messages
- Severity distribution badges
- Compression ratio display

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `data` | `LogPatternSummary` | Pattern analysis results |
| `onPatternClick` | `(pattern) => void` | Pattern selection callback |

---

#### `MetricCorrelationChart`

A time-series chart with anomaly detection and incident window highlighting.

```tsx
import { MetricCorrelationChart } from "@/components/sre-widgets";

<MetricCorrelationChart
  data={metricData}
  title="HTTP Latency (p99)"
  height={300}
/>
```

**Features:**
- Recharts LineChart with dark theme
- ReferenceArea for incident window (red shading)
- ReferenceDot for anomaly points
- Custom tooltip with anomaly details
- Stats bar (current, avg, max, trend indicator)

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `data` | `MetricWithAnomalies` | Time series + anomalies |
| `title` | `string` | Chart title override |
| `height` | `number` | Chart height in pixels |

---

#### `RemediationPlan`

Displays actionable remediation suggestions with risk assessment.

```tsx
import { RemediationPlan } from "@/components/sre-widgets";

<RemediationPlan
  data={remediationSuggestion}
  gcloudCommands={gcloudCommands}
  onExecute={(action) => console.log("Executing:", action)}
  onExplainRisk={(action) => console.log("Explain:", action)}
/>
```

**Features:**
- Ranked suggestions with risk/effort badges
- Expandable implementation steps
- "Quick Wins" alert for low-risk actions
- gcloud command blocks with copy button
- Execute confirmation dialog (with danger warning for high-risk)

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `data` | `RemediationSuggestion` | Suggestions array |
| `gcloudCommands` | `object` | Ready-to-run commands |
| `onExecute` | `(action) => void` | Execution callback |
| `onExplainRisk` | `(action) => void` | Risk explanation callback |

---

## Type System

All types are defined in `types/adk-schema.ts` and mirror the backend Pydantic schemas.

### Core Types

```typescript
// Trace structures
interface Trace {
  trace_id: string;
  project_id?: string;
  spans: SpanInfo[];
  start_time: string;
  end_time: string;
  total_duration_ms: number;
}

interface SpanInfo {
  span_id: string;
  name: string;
  duration_ms?: number;
  parent_span_id?: string | null;
  has_error: boolean;
  labels: Record<string, string>;
}

// Log patterns
interface LogPattern {
  pattern_id: string;
  template: string;
  count: number;
  severity_counts: Record<string, number>;
  sample_messages: string[];
}

// Metrics
interface MetricWithAnomalies {
  series: TimeSeries;
  anomalies: Anomaly[];
  incident_window?: { start: string; end: string };
}

// Remediation
interface RemediationSuggestion {
  matched_patterns: string[];
  suggestions: RemediationStep[];
  quick_wins: RemediationStep[];
}
```

### UI State Types

```typescript
// Agent status for StatusBar
interface AgentStatus {
  currentAgent: AgentType;
  message: string;
  progress?: number;
  startTime?: string;
}

// Canvas view discriminated union
type CanvasView =
  | { type: "empty" }
  | { type: "trace"; data: Trace }
  | { type: "log_patterns"; data: LogPatternSummary }
  | { type: "metrics"; data: MetricWithAnomalies }
  | { type: "remediation"; data: RemediationSuggestion };
```

---

## CopilotKit Actions

Actions are defined in `app/page.tsx` using `useCopilotAction`.

### Available Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `analyzeTrace` | Fetch and visualize a trace | `traceId`, `projectId?` |
| `analyzeLogPatterns` | Cluster logs with Drain3 | `service?`, `timeRange?` |
| `analyzeMetrics` | Show time-series with anomalies | `metricType`, `service?` |
| `compareTraces` | Compare baseline vs target | `baselineTraceId`, `targetTraceId` |
| `runCausalAnalysis` | Multi-agent root cause analysis | `incidentDescription` |
| `getRemediationPlan` | Generate fix suggestions | `findingSummary` |
| `executeRemediation` | Execute a remediation action | `action`, `confirmed` |

### Adding New Actions

```tsx
useCopilotAction({
  name: "myNewAction",
  description: "What this action does",
  parameters: [
    {
      name: "param1",
      type: "string",
      description: "Parameter description",
      required: true,
    },
  ],
  handler: async ({ param1 }) => {
    // Update agent status
    setAgentStatus({
      currentAgent: "orchestrator",
      message: "Processing...",
      progress: 50,
    });

    // Fetch data (currently mocked)
    const data = await fetchFromBackend(param1);

    // Update canvas
    setCanvasView({ type: "myViewType", data });

    // Return text summary for chat
    return { success: true, message: "Analysis complete." };
  },
});
```

---

## Mock Data

Mock data is defined in `lib/mock-data.ts` for testing without a backend.

### Available Mocks

| Export | Type | Description |
|--------|------|-------------|
| `mockTrace` | `Trace` | E-commerce checkout flow (9 spans) |
| `mockErrorTrace` | `Trace` | Failed checkout with DB errors |
| `mockLogPatternSummary` | `LogPatternSummary` | 6 patterns including OOM, pool exhaustion |
| `mockMetricData` | `MetricWithAnomalies` | 24h latency with anomaly spikes |
| `mockRemediationSuggestion` | `RemediationSuggestion` | 4 suggestions for connection pool issues |
| `mockTraceComparison` | `TraceComparisonReport` | Before/after comparison |
| `mockCausalAnalysis` | `CausalAnalysisReport` | Root cause chain |
| `mockAgentStatuses` | `Record<string, AgentStatus>` | Various agent states |

### Using Mock Data

```tsx
import { mockTrace, mockLogPatternSummary } from "@/lib/mock-data";

// In action handler
handler: async () => {
  await delay(2000); // Simulate latency
  setCanvasView({ type: "trace", data: mockTrace });
  return { success: true };
}
```

---

## Deployment

### Docker (Cloud Run)

The included Dockerfile uses a multi-stage build for minimal image size.

```bash
# Build image
docker build -t sre-mission-control .

# Run locally
docker run -p 8080:8080 -e OPENAI_API_KEY=sk-xxx sre-mission-control

# Deploy to Cloud Run
gcloud run deploy sre-mission-control \
  --image gcr.io/PROJECT_ID/sre-mission-control \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=sk-xxx
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for CopilotKit |
| `SRE_AGENT_API_URL` | No | Backend API URL (future) |
| `GCP_PROJECT_ID` | No | Default GCP project |

### Dockerfile Details

```dockerfile
# Stage 1: deps - Install dependencies
FROM node:20-alpine AS deps

# Stage 2: builder - Build the app
FROM node:20-alpine AS builder
# Uses standalone output for minimal size

# Stage 3: runner - Production image
FROM node:20-alpine AS runner
# Non-root user for security
# Health check for Cloud Run
EXPOSE 8080
CMD ["node", "server.js"]
```

---

## Extending the Dashboard

### Adding a New Widget

1. **Create the component** in `components/sre-widgets/`:

```tsx
// components/sre-widgets/NewWidget.tsx
"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MyDataType } from "@/types/adk-schema";

interface NewWidgetProps {
  data: MyDataType;
  className?: string;
}

export function NewWidget({ data, className }: NewWidgetProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>New Widget</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Render data */}
      </CardContent>
    </Card>
  );
}
```

2. **Export from index**:

```tsx
// components/sre-widgets/index.ts
export { NewWidget } from "./NewWidget";
```

3. **Add type definitions**:

```typescript
// types/adk-schema.ts
export interface MyDataType {
  field1: string;
  field2: number;
}

// Add to CanvasView union
type CanvasView =
  | ...existing
  | { type: "new_widget"; data: MyDataType };
```

4. **Add to Canvas switch**:

```tsx
// components/layout/Canvas.tsx
case "new_widget":
  return <NewWidget data={view.data} />;
```

5. **Add CopilotKit action**:

```tsx
// app/page.tsx
useCopilotAction({
  name: "showNewWidget",
  handler: async () => {
    setCanvasView({ type: "new_widget", data: myData });
  }
});
```

### Adding a New Agent Type

1. **Add to AgentType enum**:

```typescript
// types/adk-schema.ts
export type AgentType =
  | ...existing
  | "my_new_agent";
```

2. **Add config in StatusBar**:

```tsx
// components/layout/StatusBar.tsx
const agentConfig = {
  ...existing,
  my_new_agent: {
    name: "My New Agent",
    icon: SomeIcon,
    color: "text-cyan-400",
    bgColor: "bg-cyan-500/10",
  },
};
```

### Connecting to Backend

Replace mock data with API calls in action handlers:

```tsx
handler: async ({ traceId }) => {
  const response = await fetch(
    `${process.env.SRE_AGENT_API_URL}/traces/${traceId}`
  );
  const trace = await response.json();
  setCanvasView({ type: "trace", data: trace });
}
```

---

## Troubleshooting

### Build Errors

**Font fetch failures:**
```
Failed to fetch font `Inter` from Google Fonts
```
→ Network issue. The layout uses system fonts as fallback.

**TypeScript errors:**
```
Type 'unknown' is not assignable to type 'ReactNode'
```
→ Use `String(value)` or explicit type assertions for unknown values.

### Runtime Issues

**CopilotKit not responding:**
1. Check `OPENAI_API_KEY` is set
2. Verify `/api/copilotkit` route is accessible
3. Check browser console for errors

**Canvas not updating:**
1. Ensure `setCanvasView` is called with correct type
2. Check view type matches Canvas switch case
3. Verify data shape matches TypeScript interface

### Performance

**Large trace visualization slow:**
- Traces with 1000+ spans may lag
- Consider implementing virtualization with `react-window`
- Limit displayed spans and add "Load more"

**Chart rendering issues:**
- Recharts requires fixed height container
- Use `ResponsiveContainer` wrapper
- Avoid rendering 10000+ data points

---

## Contributing

When adding new features:

1. **Types first**: Define interfaces in `adk-schema.ts`
2. **Mock data**: Add realistic test data in `mock-data.ts`
3. **Component**: Build widget with Shadcn UI primitives
4. **Integration**: Add Canvas case and CopilotKit action
5. **Test**: Verify with mock data before backend integration

---

## License

This project is part of the SRE Agent system. See the root LICENSE file for details.
