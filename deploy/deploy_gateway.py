import argparse
import os
import subprocess
import sys


def get_project_id():
    """Get the GCP Project ID from gcloud config or environment."""
    project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    if not project_id:
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                check=True,
            )
            project_id = result.stdout.strip()
        except subprocess.CalledProcessError:
            # If gcloud command fails, project_id remains None
            pass
    return project_id


def main():
    parser = argparse.ArgumentParser(
        description="Deploy SRE Agent Gateway to Cloud Run"
    )
    parser.add_argument(
        "--agent-id", required=True, help="Vertex Reasoning Engine resource name/ID"
    )
    parser.add_argument("--project-id", help="GCP Project ID")
    parser.add_argument("--region", default="us-central1", help="GCP Region")
    parser.add_argument(
        "--service-name", default="sre-agent-gateway", help="Cloud Run service name"
    )

    args = parser.parse_args()
    project_id = args.project_id or get_project_id()

    if not project_id:
        print(
            "❌ Error: Project ID not found. Use --project-id or set GCP_PROJECT_ID env var."
        )
        sys.exit(1)

    print("🚀 Deploying SRE Gateway to Cloud Run...")
    print(f"   Project: {project_id}")
    print(f"   Region:  {args.region}")
    print(f"   Target:  {args.agent_id}")

    # Build and deploy command
    cmd = [
        "gcloud",
        "run",
        "deploy",
        args.service_name,
        "--source",
        ".",
        "--file",
        "deploy/Dockerfile.gateway",
        f"--region={args.region}",
        f"--project={project_id}",
        "--set-env-vars",
        f"REMOTE_AGENT_ID={args.agent_id}",
        "--allow-unauthenticated",  # Gateway for CopilotKit
        "--platform=managed",
    ]

    try:
        subprocess.run(cmd, check=True)
        # Get the URL of the deployed service
        url_cmd = [
            "gcloud",
            "run",
            "services",
            "describe",
            args.service_name,
            f"--region={args.region}",
            f"--project={project_id}",
            "--format=value(status.url)",
        ]
        url_result = subprocess.run(url_cmd, capture_output=True, text=True, check=True)
        gateway_url = url_result.stdout.strip()

        print("\n✅ Gateway deployed successfully!")
        print(f"🔗 Gateway URL: {gateway_url}")
        print(f"📡 CopilotKit Endpoint: {gateway_url}/copilotkit")

        # Return the URL for orchestration scripts
        print(f"EXPORT_GATEWAY_URL={gateway_url}")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Deployment failed with exit code {e.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
