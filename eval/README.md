# SRE Agent Evaluations

This directory contains the evaluation framework for benchmarking the SRE Agent's performance, accuracy, and tool selection capabilities.

## 🚀 Running Evaluations

To run the full evaluation suite:

```bash
uv run poe eval
```

Or run the script directly:

```bash
uv run python deploy/run_eval.py
```

## 📂 Evaluation Datasets

The evaluation cases are defined in JSON files within this directory. Each file represents a category of tests:

*   **`basic_capabilities.test.json`**: Basic "sanity checks" (e.g., getting time, listing projects).
*   **`metrics_analysis.test.json`**: Tests focused on PromQL querying and metric anomaly detection.
*   **`tool_selection.test.json`**: Tests specifically checking if the agent picks the correct tool for a given prompt (e.g., choosing `trace_analyzer` for latency issues).

## 📝 Test Case Schema

Each test file contains a list of test cases following this schema:

```json
[
  {
    "id": "unique-test-id",
    "prompt": "The user query to simulate",
    "expected_tools": ["tool_name_1", "tool_name_2"],
    "forbidden_tools": ["tool_that_should_not_be_used"],
    "expected_strings": ["phrase to look for in response"],
    "description": "Brief description of what this tests"
  }
]
```

### Fields:

*   **`id`**: (Required) Unique identifier for the test case.
*   **`prompt`**: (Required) The input text sent to the agent.
*   **`expected_tools`**: (Optional) List of tool names that *must* be called during execution.
*   **`forbidden_tools`**: (Optional) List of tool names that must *not* be called.
*   **`expected_strings`**: (Optional) Substrings that must appear in the agent's final text response.

## 📊 Scoring

The `run_eval.py` script calculates a pass/fail status for each test based on:
1.  **Tool Selection Accuracy**: Did it call all expected tools? Did it avoid forbidden tools?
2.  **Response Validation**: Did the final answer contain the expected keywords?
3.  **Execution Success**: Did the agent crash or error out?

A summary report is printed to the console at the end of the run.
