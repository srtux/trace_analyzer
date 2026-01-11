import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None, env=None, interactive=False):
    """Runs a command and returns the output (or just runs it if interactive)."""
    print(f"Executing: {' '.join(cmd)}")

    if interactive:
        # Inherit TTY for authentication/interaction
        return subprocess.run(
            cmd, cwd=cwd, env={**os.environ, **(env or {})}, check=True
        )

    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    output = []
    if process.stdout:
        for line in process.stdout:
            print(line, end="")
            output.append(line)

    process.wait()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd, "".join(output))

    return "".join(output)


def main():
    """Orchestrates the deployment of the full stack."""
    root_dir = Path(__file__).parent.parent

    print("🚀 STARTING FULL STACK DEPLOYMENT")
    print("=================================")

    # --- STEP 1: Deploy Backend to Vertex AI ---
    print("\n🏗️  Step 1: Deploying Backend (Vertex Agent Engine)...")
    try:
        backend_cmd = [sys.executable, "deploy/deploy.py", "--create"]
        # We MUST capture output to get the resource ID, but this might
        # fail if re-auth is needed. We recommend the user run 'gcloud auth login'
        # beforehand if they have session expiration issues.
        output = run_command(backend_cmd, cwd=str(root_dir))

        # Parse the resource name from output
        resource_name = None
        for line in output.splitlines():
            if "Resource Name:" in line:
                resource_name = line.split("Resource Name:")[1].strip()
                break
            # Fallback if the print statement is different
            if (
                "projects/" in line
                and "/locations/" in line
                and "/reasoningEngines/" in line
            ):
                resource_name = line.strip()
                break

        if not resource_name:
            print("❌ Failed to find backend resource name in output.")
            sys.exit(1)

        print(f"\n✅ Backend deployed! Resource URI: agentengine://{resource_name}")

        # --- STEP 2: Deploy Gateway Proxy to Cloud Run ---
        # The frontend cannot talk to agentengine:// directly, so we need a proxy.
        print("\n🏗️  Step 2: Deploying Gateway Proxy to Cloud Run...")
        gateway_cmd = [
            sys.executable,
            "deploy/deploy_gateway.py",
            "--agent-id",
            resource_name,
        ]
        # Gateway deployment usually needs re-auth check too, so we'll enable interactive
        # but we also need the URL. We'll capture it from the tail of the output.
        gateway_output = run_command(gateway_cmd, cwd=str(root_dir))

        gateway_url = None
        for line in gateway_output.splitlines():
            if "EXPORT_GATEWAY_URL=" in line:
                gateway_url = line.split("=")[1].strip()
                break

        if not gateway_url:
            print("❌ Failed to capture Gateway URL from output.")
            sys.exit(1)

        # --- STEP 3: Deploy Frontend to Cloud Run ---
        print("\n🏗️  Step 3: Deploying Frontend to Cloud Run...")
        frontend_cmd = [
            sys.executable,
            "deploy/deploy_web.py",
            "--agent-url",
            gateway_url,
        ]
        # Frontend deployment is primarily the heavy lifting, definitely allow interactivity.
        run_command(frontend_cmd, cwd=str(root_dir), interactive=True)

        print("\n🚀 FULL STACK DEPLOYMENT COMPLETE!")
        print(f"Backend (Vertex):  {resource_name}")
        print(f"Gateway (Proxy):   {gateway_url}")
        print("Frontend (Next.js): Dashboard is ready!")

    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
