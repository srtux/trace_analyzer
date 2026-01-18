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

## Session Management
AutoSRE uses the backend's `SessionService` to persist conversation history.
- **API**: Connects to `/api/sessions` for listing and managing sessions.
- **Context**: Maintains `session_id` to allow the backend to restore conversation history from ADK storage (SQLite/Firestore).
- **History**: Chat history is rehydrated from backend events, ensuring state consistency across reloads.

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

## Authentication Setup

1. **Google Cloud Project**:
    - Ensure you have a Google Cloud Project with the "Google People API" enabled (if user profile data is needed in future) or just basic profile rights.
    - Create an **OAuth 2.0 Client ID** for **Web Application**.
        - **Authorized JavaScript Origins**: `http://localhost`, `http://localhost:8080`, or your dev server address.
        - **Authorized Redirect URIs**: `http://localhost`, `http://localhost:8080` (often optional for current implicit flow, but recommended).

2. **Environment Configuration**:
    - Copy the example environment file:
      ```bash
      cp .env.example .env
      ```
    - Edit `.env` and set your `GOOGLE_CLIENT_ID`:
      ```bash
      # In .env
      GOOGLE_CLIENT_ID=your-cliend-id.apps.googleusercontent.com
      ```

3. **Running on Web (Important)**:
    - Flutter Web requires the Client ID to be in the `index.html` meta tag at load time.
    - We use a placeholder `$GOOGLE_CLIENT_ID` in `web/index.html`.
    - **Before running**, you must inject your ID.

    **Option A: Quick generic substitution (MacOS/Linux)**:
    ```bash
    # Inject ID from .env
    sed -i '' "s/\$GOOGLE_CLIENT_ID/$(grep GOOGLE_CLIENT_ID .env | cut -d '=' -f2)/" web/index.html

    # Run App
    flutter run -d chrome

    # Revert before commit (to keep repo clean)
    git checkout web/index.html
    ```

    **Option B: Hardcode for local dev**:
    - Just paste your ID into `web/index.html` manually.
    - Run: `git update-index --skip-worktree web/index.html` to prevent accidental commits of your ID if you wish.
    - Run: `git update-index --skip-worktree web/index.html` to prevent accidental commits of your ID if you wish.

4.  **Deploying to Cloud Run**:
    - When deploying to production/Cloud Run, the deployment scripts will automatically inject the `GOOGLE_CLIENT_ID` from your local `.env` (or CI environment) into the container at startup.
    - **CRITICAL Step**:
        1.  Deploy the app first to get your Cloud Run URL (e.g., `https://autosre-xyz.a.run.app`).
        2.  Go to **Google Cloud Console > Credentials** -> "AutoSRE Web".
        3.  Add this new URL to **Authorized JavaScript Origins**.
        4.  Save and wait a few minutes for propagation.
