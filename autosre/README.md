# AutoSRE

A next-generation operation dashboard for SREs, built with **Flutter** and **GenUI**.

## Overview
AutoSRE connects to the SRE Agent (Python/ADK) and renders dynamic, generative UIs for distributed tracing, metric analysis, and incident remediation.

It is designed to be served by the unified SRE Agent server, but can also be run independently for development.

## Prerequisites
- **Flutter SDK**: [Install Flutter](https://docs.flutter.dev/get-started/install/macos)
- **SRE Agent Backend**: Can be run via `uv run poe dev` (Unified) or `uv run poe web` (Backend only).

## Getting Started

1.  **Install Dependencies**:
    ```bash
    cd autosre
    flutter pub get
    ```

2.  **Run the App**:
    For macOS desktop:
    ```bash
    flutter run -d macos
    ```
    For Web (Chrome):
    ```bash
    flutter run -d chrome
    ```

## Architecture
- **Framework**: Flutter
- **Protocol**: [GenUI](https://github.com/flutter/genui) + [A2UI](https://a2ui.org)
- **State Management**: Provider
- **Entry Point**: `lib/main.dart`
- **App Configuration**: `lib/app.dart` & `lib/theme/app_theme.dart`
- **Catalog Registry**: `lib/catalog.dart`
- **Screens**: `lib/pages/`
- **Agent Connection**: `lib/agent/adk_content_generator.dart`
- **Backend Adapter**: `sre_agent/tools/analysis/genui_adapter.py` (Python schema transformation)

## Key Widgets
- `SessionPanel`: Sidebar for viewing and managing investigation history sessions.
- `TraceWaterfall`: Gantt chart for distributed traces.
- `MetricCorrelationChart`: Timeline of metrics with anomaly detection.
- `LogPatternViewer`: Visualizes aggregated log patterns.
- `RemediationPlan`: Interactive checklist for fix actions.

## Canvas Widgets (GenUI Dynamic Visualization)

Advanced Canvas-style widgets for real-time, animated SRE visualizations:

| Widget | Component Name | Description |
|--------|---------------|-------------|
| `AgentActivityCanvas` | `x-sre-agent-activity` | Real-time visualization of agent workflow with animated node connections, status indicators, and phase tracking. Shows coordinator → sub-agents → data sources hierarchy. |
| `ServiceTopologyCanvas` | `x-sre-service-topology` | Interactive service dependency graph with health status, latency metrics, incident path highlighting, and pan/zoom support. |
| `IncidentTimelineCanvas` | `x-sre-incident-timeline` | Horizontal scrollable timeline showing incident progression with event correlation, severity color-coding, TTD/TTM metrics, and root cause analysis. |
| `MetricsDashboardCanvas` | `x-sre-metrics-dashboard` | Grid-based multi-metric display with sparklines, anomaly detection, threshold visualization, and status badges. |
| `AIReasoningCanvas` | `x-sre-ai-reasoning` | Agent thought process visualization showing reasoning steps (observation → analysis → hypothesis → conclusion), evidence collection, and confidence scores. |

### Canvas Widget Features
- **Animated Connections**: Flow particles and pulsing effects for active elements
- **Interactive Elements**: Tap/click nodes for details, hover for metrics
- **Real-time Updates**: Smooth animations when data changes
- **Neural Network Backgrounds**: AI Reasoning canvas features animated neural patterns
- **Glass-morphism UI**: Consistent with the app's modern dark theme
