# trace-analyzer

## Dev environment tips
- Use `uv sync` to install dependencies and create the virtual environment.
- Use `uv run adk web` to launch the agent's web interface (Streamlit-based).
- Use `uv run adk run .` to launch the interactive terminal interface.
- Environment variables are managed in `.env`. Copy `.env.example` to `.env` and set `GOOGLE_CLOUD_PROJECT`.
- The agent uses widespread `opentelemetry` instrumentation. Logs are visible in the console and Cloud Logging.
- Agent definitions are in `trace_analyzer/trace_analyzer/agent.py` and `sub_agents/`.
- `deployment/` contains scripts for deploying to Vertex AI Agent Engine (`uv run python deploy/deploy.py`).

## Testing instructions
- Run the full test suite with `uv run pytest`.
- Tests are located in the `tests/` directory.
- Use `uv run pytest -s` to see stdout/logging during tests.
- When modifying agents, add new tests to `tests/` to verify behavior.
- Run type checks with `uv run mypy .` (if configured in `optional-dependencies`).

## PR instructions
- Ensure `uv.lock` is updated if dependencies change.
- Verify that `uv run pytest` passes cleanly.
- If modifying prompts (`prompt.py`), verify agent behavior with `uv run adk run .` using a known trace ID.
- Title format: `[trace-analyzer] <Description of changes>`
