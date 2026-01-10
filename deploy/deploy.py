"""Deployment script for SRE Agent"""

import os
import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import vertexai
from absl import app, flags
from dotenv import load_dotenv
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

from sre_agent.agent import root_agent

FLAGS = flags.FLAGS
flags.DEFINE_string("project_id", None, "GCP project ID.")
flags.DEFINE_string("location", None, "GCP location.")
flags.DEFINE_string("bucket", None, "GCP bucket.")
flags.DEFINE_string("resource_id", None, "ReasoningEngine resource ID.")
flags.DEFINE_string("display_name", None, "Display name for the agent.")
flags.DEFINE_string("description", None, "Description for the agent.")


flags.DEFINE_bool("list", False, "List all agents.")
flags.DEFINE_bool("create", False, "Creates a new agent.")
flags.DEFINE_bool("delete", False, "Deletes an existing agent.")
flags.DEFINE_bool("verify", True, "Verify agent import before creation.")
flags.mark_bool_flags_as_mutual_exclusive(["create", "delete"])


def get_requirements() -> list[str]:
    """Reads requirements from pyproject.toml with robust merging."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    # Get dependencies from [project] section
    dependencies = pyproject.get("project", {}).get("dependencies", [])

    # Ensure crucial deployment dependencies are present
    # These are required by the Reasoning Engine runtime itself
    required_for_deploy = [
        "google-adk>=1.0.0",
        "google-cloud-aiplatform[adk,agent-engines]>=1.93.0",
        "requests>=2.31.0",
    ]

    # Map of package name (lowercase) to full requirement string
    req_map = {}

    def add_req(req_str: str):
        # Extract package name for comparison (e.g., 'google-adk>=1.0' -> 'google-adk')
        import re

        name = re.split(r"[>=<~!\[]", req_str)[0].lower().strip()
        req_map[name] = req_str

    # Process existing dependencies first
    for d in dependencies:
        add_req(d)

    # Merge required deployment packages if not already present
    for r in required_for_deploy:
        name = re.split(r"[>=<~!\[]", r)[0].lower().strip()
        if name not in req_map:
            req_map[name] = r

    return list(req_map.values())


def verify_local_import():
    """Verify that the agent can be imported locally without error."""
    print("Checking if agent is importable locally...")
    try:
        from sre_agent.agent import root_agent

        print(f"✅ Successfully imported agent: {root_agent.name}")
        return True
    except ImportError as e:
        print(f"❌ ERROR: Failed to import agent locally: {e}")
        print("Please ensure all dependencies in pyproject.toml are installed.")
        return False
    except Exception as e:
        print(f"❌ ERROR: Unexpected error during agent import: {e}")
        return False


def create(env_vars: dict[str, str] | None = None) -> None:
    """Creates an agent engine for SRE Agent."""
    if env_vars is None:
        env_vars = {}
    adk_app = AdkApp(agent=root_agent, enable_tracing=True)

    requirements = get_requirements()
    print(f"Deploying with requirements: {requirements}")

    remote_agent = agent_engines.create(
        adk_app,  # type: ignore
        display_name=FLAGS.display_name if FLAGS.display_name else root_agent.name,
        description=FLAGS.description if FLAGS.description else root_agent.description,
        requirements=requirements,
        extra_packages=["./sre_agent"],
        env_vars={
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true",
            **env_vars,
        },
    )
    print(f"Created remote agent: {remote_agent.resource_name}")


def delete(resource_id: str) -> None:
    remote_agent = agent_engines.get(resource_id)
    remote_agent.delete(force=True)
    print(f"Deleted remote agent: {resource_id}")


def list_agents() -> None:
    remote_agents = agent_engines.list()
    if not remote_agents:
        print("No remote agents found.")
        return

    template = """
{agent.name} ("{agent.display_name}")
- Resource Name: {agent.resource_name}
- Create time: {agent.create_time}
- Update time: {agent.update_time}
"""
    remote_agents_string = "".join(
        template.format(agent=agent) for agent in remote_agents
    )
    print(f"All remote agents:\n{remote_agents_string}")


def main(argv: list[str]) -> None:
    del argv  # unused
    load_dotenv()

    project_id = (
        FLAGS.project_id if FLAGS.project_id else os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    location = FLAGS.location if FLAGS.location else os.getenv("GOOGLE_CLOUD_LOCATION")
    bucket = FLAGS.bucket if FLAGS.bucket else os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")

    print(f"PROJECT: {project_id}")
    print(f"LOCATION: {location}")
    print(f"BUCKET: {bucket}")

    if not project_id:
        print("Missing required environment variable: GOOGLE_CLOUD_PROJECT")
        return
    elif not location:
        print("Missing required environment variable: GOOGLE_CLOUD_LOCATION")
        return
    elif not bucket:
        print("Missing required environment variable: GOOGLE_CLOUD_STORAGE_BUCKET")
        return

    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=bucket if bucket.startswith("gs://") else f"gs://{bucket}",
    )

    if FLAGS.list:
        list_agents()
    elif FLAGS.create:
        env_vars: dict[str, str] = {}

        if FLAGS.verify:
            if not verify_local_import():
                print("Aborting deployment due to local import failure.")
                return

        create(env_vars=env_vars)
    elif FLAGS.delete:
        if not FLAGS.resource_id:
            print("resource_id is required for delete")
            return
        delete(FLAGS.resource_id)
    else:
        print("Unknown command")


if __name__ == "__main__":
    app.run(main)
