"""Deployment script for SRE Agent"""

import os
import sys

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


flags.DEFINE_bool("list", False, "List all agents.")
flags.DEFINE_bool("create", False, "Creates a new agent.")
flags.DEFINE_bool("delete", False, "Deletes an existing agent.")
flags.mark_bool_flags_as_mutual_exclusive(["create", "delete"])


def get_requirements() -> list[str]:
    """Reads requirements from pyproject.toml."""
    pyproject_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "pyproject.toml"
    )
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    # Get dependencies from [project] section
    dependencies = pyproject.get("project", {}).get("dependencies", [])

    # Ensure crucial deployment dependencies are present
    # These are often needed even if not explicitly in pyproject.toml
    # for the Reasoning Engine runtime
    required_for_deploy = [
        "google-adk>=1.0.0",
        "google-cloud-aiplatform[adk,agent-engines]>=1.93.0",
        "numpy>=1.26.0",
    ]

    for req in required_for_deploy:
        if req not in dependencies:
            # Check if a different version of the same package is present
            package_name = req.split(">=")[0].split("[")[0]
            if not any(d.startswith(package_name) for d in dependencies):
                dependencies.append(req)

    return dependencies


def create(env_vars: dict[str, str] | None = None) -> None:
    """Creates an agent engine for SRE Agent."""
    if env_vars is None:
        env_vars = {}
    adk_app = AdkApp(agent=root_agent, enable_tracing=True)

    requirements = get_requirements()
    print(f"Deploying with requirements: {requirements}")

    remote_agent = agent_engines.create(
        adk_app,
        display_name=root_agent.name,
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
        env_vars = {}

        if project_id:
            env_vars["GOOGLE_CLOUD_PROJECT"] = project_id

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
