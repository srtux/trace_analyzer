# AutoSRE Deployment Guide

This directory contains the orchestration scripts for deploying the AutoSRE full-stack application.

## 🏗️ Architecture

AutoSRE uses a two-tier deployment architecture:

1.  **Backend (The Brain)**: Deployed to **Vertex AI Agent Engine**. This is the core Reasoning Engine (AdkApp) that executes tools and generates analysis.
2.  **Frontend (The Interface)**: Deployed to **Cloud Run**. This is a "Unified Container" that serves the **Flutter Web Dashboard** as static files and provides a **FastAPI Proxy** to communicate with the Backend.

The Frontend acts as a secure bridge, handling user requests and authenticating them before querying the Vertex AI Agent.

## 🚀 Unified Deployment (Recommended)

The easiest way to deploy the entire stack is using the `deploy_all.py` script.

```bash
uv run poe deploy-all
```

**What this script does:**
1.  **Backend**: Executes `deploy/deploy.py --create` to package and upload the `sre_agent` to Vertex AI.
2.  **Capture**: Parses the generated `ReasoningEngine` resource ID.
3.  **Permissions**: Runs `grant_permissions.py` to ensure the Cloud Run service account has access to analyze traces/logs and query the Vertex agent.
4.  **Frontend**: Executes `deploy/deploy_web.py` which:
    - Builds the Flutter Web app.
    - Contextualizes the `Dockerfile.unified`.
    - Deploys the container to Cloud Run with the `SRE_AGENT_ID` environment variable.

## 🛠️ Individual Scripts

### `deploy.py` (Backend Only)
Deploys the `sre_agent` package to Vertex AI reasoning engines.
- Requires `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and `GOOGLE_CLOUD_STORAGE_BUCKET`.
- Use `--create` to deploy a new version.
- Use `--list` to see existing agents.

### `deploy_web.py` (Frontend Only)
Deploys the Flutter dashboard and the Python proxy to Cloud Run.
- Automatically copies `deploy/Dockerfile.unified` to the root for the build.
- Requires an existing `SRE_AGENT_ID` (or URL) to connect to.
- Mounts the `gemini-api-key` secret from Secret Manager.

### `grant_permissions.py`
Automates the IAM policy bindings for the service account.
**Roles granted:**
- `roles/cloudtrace.user`
- `roles/logging.viewer`
- `roles/monitoring.viewer`
- `roles/bigquery.dataViewer`
- `roles/aiplatform.user`
- `roles/secretmanager.secretAccessor`
- `roles/datastore.user` (Required for session history)

## 🔐 Prerequisites & Secrets

1.  **Firestore Database**:
    - Enable Firestore in **Native Mode** in your GCP project.
    - This is used for persisting conversation sessions and user preferences.

2.  **Gemini API Key**:
    ```bash
    echo -n "YOUR_API_KEY" | gcloud secrets create gemini-api-key --data-file=-
    ```

3.  **Environment Configuration**:
    Ensure your `.env` file has the following:
    ```bash
    GOOGLE_CLOUD_PROJECT=your-project
    GOOGLE_CLOUD_LOCATION=us-central1
    GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket
    ```

## 🧪 Verification after Deployment

1.  Visit the Cloud Run URL provided by the deployment script.
2.  Open the dashboard.
3.  The "Ready" status indicator should be green (verified via `/openapi.json`).
4.  Ask: "List the GCP projects" to verify the end-to-end tool calling path.

## 📈 Evaluations

You can run agent evaluations to benchmark performance using the `run_eval.py` script.

```bash
uv run poe eval
```

This script:
1.  Loads test cases from `eval/`.
2.  Runs the agent against these cases.
3.  Reports success/failure rates and detailed logs.
