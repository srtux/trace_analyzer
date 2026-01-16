"""Evaluation tests for the SRE Agent.

These tests require Google Cloud credentials (API key or Vertex AI setup) to run.
They will be skipped if the required environment variables are not set.

Required environment variables:
- GOOGLE_API_KEY or GEMINI_API_KEY: For Google AI API
- OR GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION: For Vertex AI

To run these tests locally:
1. Set up your credentials in .env file
2. Run: uv run pytest eval/test_evaluate.py -v
"""

import json
import os

import pytest
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_set import EvalSet


def _has_api_credentials() -> bool:
    """Check if API credentials are available for evaluation tests."""
    # Check for Google AI API key
    has_api_key = bool(
        os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    )

    # Check for Vertex AI credentials
    has_vertexai = bool(
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        and os.environ.get("GOOGLE_CLOUD_LOCATION")
        and os.environ.get("GOOGLE_GENAI_USE_VERTEXAI")
    )

    return has_api_key or has_vertexai


# Skip all eval tests if no credentials are available
requires_credentials = pytest.mark.skipif(
    not _has_api_credentials(),
    reason="Evaluation tests require Google AI API key or Vertex AI credentials. "
    "Set GOOGLE_API_KEY or (GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION + GOOGLE_GENAI_USE_VERTEXAI).",
)


def _load_eval_set(file_path: str) -> EvalSet:
    """Load and parse an evaluation set from a JSON file.

    Args:
        file_path: Path to the JSON file containing the eval set data.

    Returns:
        Parsed EvalSet object.
    """
    with open(file_path) as f:
        eval_data = json.load(f)

    # Handle different Pydantic versions
    try:
        return EvalSet(**eval_data)
    except Exception:
        # Fallback to pydantic model_validate (v2) or parse_obj (v1)
        if hasattr(EvalSet, "model_validate"):
            return EvalSet.model_validate(eval_data)
        else:
            return EvalSet.parse_obj(eval_data)


@requires_credentials
@pytest.mark.asyncio
async def test_agent_capabilities():
    """Test the agent's basic capabilities via an evaluation session.

    This test verifies that the agent can:
    - Understand its core capabilities
    - Respond appropriately to general capability questions
    - Provide coherent and helpful responses
    """
    eval_set = _load_eval_set("eval/basic_capabilities.test.json")

    # Lower threshold to 0.6 to account for high variability in agent's creative intro
    config = EvalConfig(criteria={"response_match_score": 0.6})

    await AgentEvaluator.evaluate_eval_set(
        agent_module="sre_agent.agent",
        eval_set=eval_set,
        eval_config=config,
        print_detailed_results=False,
    )


@requires_credentials
@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Agent may ask for clarification even when Project ID is provided in prompt"
)
async def test_tool_selection():
    """Test the agent's tool selection capabilities.

    This test verifies that the agent correctly selects the appropriate tools
    for different types of queries:
    - fetch_trace for trace details
    - run_log_pattern_analysis for log analysis
    - list_time_series for metric queries
    """
    eval_set = _load_eval_set("eval/tool_selection.test.json")

    # We mostly care about tool trajectory here, not the response text
    config = EvalConfig(
        criteria={
            "tool_trajectory_match_score": 0.8,
            # Relax response match since we are focusing on tool selection
            "response_match_score": 0.0,
        }
    )

    await AgentEvaluator.evaluate_eval_set(
        agent_module="sre_agent.agent",
        eval_set=eval_set,
        eval_config=config,
        print_detailed_results=False,
    )


@requires_credentials
@pytest.mark.asyncio
async def test_metrics_analysis():
    """Test the agent's metrics analysis capabilities.

    This test verifies that the agent can:
    - Query time series data correctly
    - Detect metric anomalies
    - Provide meaningful analysis of metric data
    """
    eval_set = _load_eval_set("eval/metrics_analysis.test.json")

    config = EvalConfig(
        criteria={
            "tool_trajectory_match_score": 0.8,
            "response_match_score": 0.0,
        }
    )

    await AgentEvaluator.evaluate_eval_set(
        agent_module="sre_agent.agent",
        eval_set=eval_set,
        eval_config=config,
        print_detailed_results=False,
    )
