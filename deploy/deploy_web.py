import argparse
import os
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Deploy SRE Mission Control to Cloud Run"
    )
    parser.add_argument(
        "--agent-url", help="URL of the SRE Agent backend (e.g. from 'adk web')"
    )
    parser.add_argument(
        "--agent-id",
        help="Vertex Reasoning Engine resource ID (for future direct integration)",
    )
    parser.add_argument("--project-id", help="GCP Project ID")
    parser.add_argument(
        "--region", default="us-central1", help="GCP Region (default: us-central1)"
    )
    parser.add_argument(
        "--service-name", default="autosre", help="Cloud Run service name"
    )

    args, unknown = parser.parse_known_args()

    # Check if gcloud is installed
    if not subprocess.run(["which", "gcloud"], capture_output=True).returncode == 0:
        print("❌ Error: 'gcloud' CLI not found. Please install it.")
        sys.exit(1)

    # Resolve variables: CLI arg > Env Var > gcloud config
    project_id = (
        args.project_id
        or os.getenv("GCP_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    if not project_id:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"], capture_output=True, text=True
        )
        project_id = result.stdout.strip()

    if not project_id:
        print("❌ Error: Could not determine GCP Project ID.")
        sys.exit(1)

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    agent_url = (
        args.agent_url or os.getenv("SRE_AGENT_URL") or os.getenv("SRE_AGENT_API_URL")
    )
    agent_id = args.agent_id or os.getenv("SRE_AGENT_ID")

    if not gemini_key:
        print("❌ Error: GEMINI_API_KEY not found. Please set it in .env")
        sys.exit(1)

    # Prepare environment variables for Cloud Run
    env_vars = [
        f"GCP_PROJECT_ID={project_id}",
        f"GCP_REGION={args.region}",
        f"GOOGLE_CLOUD_LOCATION={args.region}",
    ]

    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    if google_client_id:
        env_vars.append(f"GOOGLE_CLIENT_ID={google_client_id}")

    if agent_url:
        env_vars.append(f"SRE_AGENT_URL={agent_url}")
        env_vars.append(f"SRE_AGENT_API_URL={agent_url}")

    if agent_id:
        env_vars.append(f"SRE_AGENT_ID={agent_id}")

    # Grant IAM Permissions automatically
    print("\n🔐 Verifying/Granting IAM Permissions...")
    subprocess.run(
        [sys.executable, "deploy/grant_permissions.py", "--project-id", project_id],
        check=False,  # Don't hard fail if user lacks admin rights, try deployment anyway
    )

    # Temporary: Copy Dockerfile.unified to Dockerfile in root
    import shutil

    shutil.copy("deploy/Dockerfile.unified", "Dockerfile")

    try:
        # Construct gcloud command
        cmd = [
            "gcloud",
            "run",
            "deploy",
            args.service_name,
            "--source",
            ".",  # Deploy from root context
            "--region",
            args.region,
            "--allow-unauthenticated",
            "--memory=1Gi",
            "--timeout=300",
            f"--set-env-vars={','.join(env_vars)}",
            # Mount the secret as both environment variables to be safe
            "--set-secrets=GOOGLE_API_KEY=gemini-api-key:latest,GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_GENERATIVE_AI_API_KEY=gemini-api-key:latest",
            f"--project={project_id}",
        ]

        # Append any unknown arguments (e.g. --cpu, --memory)
        cmd.extend(unknown)

        print(f"🚀 Deploying '{args.service_name}' to Cloud Run...")
        print(f"   Project: {project_id}")
        print(f"   Region:  {args.region}")
        if agent_url:
            print(f"   Agent URL: {agent_url}")
        if agent_id:
            print(f"   Agent ID Override: {agent_id}")

        subprocess.run(cmd, check=True)
        print("\n✅ Successfully deployed to Cloud Run!")
        print(
            f"🔗 View service details: https://console.cloud.google.com/run/detail/{args.region}/{args.service_name}/revisions?project={project_id}"
        )
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Deployment failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    finally:
        # Cleanup temporary Dockerfile
        if os.path.exists("Dockerfile"):
            os.remove("Dockerfile")


if __name__ == "__main__":
    main()
