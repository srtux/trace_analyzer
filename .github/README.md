# CI/CD Pipeline

The project uses **GitHub Actions** for continuous integration and deployment.

## Automated Workflow
Every push to the `main` branch triggers the pipeline defined in `.github/workflows/deploy.yml`:
1.  **Test Job**: Installs dependencies (`uv`), runs lint (`ruff`), and executes the full test suite (`pytest`).
2.  **Deploy Job**: PROCEEDS ONLY IF TESTS PASS.
    -   Authenticates with Google Cloud.
    -   Installs production dependencies.
    -   Deploys the agent to Vertex AI Agent Engine using `uv run poe deploy`.

## Required GitHub Secrets
To enable automated deployment, configure the following **Secrets** in your GitHub repository settings:

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | JSON service account key (base64 or raw JSON) with permissions to deploy (Vertex AI User, Storage Admin). |
| `GOOGLE_CLOUD_PROJECT` | Target GCP Project ID (e.g., `my-observability-project`). |
| `GOOGLE_CLOUD_LOCATION` | Target GCP Region (e.g., `us-central1`). |
| `GOOGLE_CLOUD_STORAGE_BUCKET` | Cloud Storage bucket name for staging artifacts (e.g., `agent-staging-bucket`). |

## Manual Trigger
You can also manually trigger a deployment from the "Actions" tab in GitHub by selecting the "Deploy SRE Agent" workflow.
