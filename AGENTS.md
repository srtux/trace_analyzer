# SRE Agent

## Agent Rules

### Documentation Requirements
- **Keep Docs Up To Date**: When you make changes to the codebase, you MUST update `README.md` and `AGENTS.md` to reflect those changes.
- **Update Architecture Diagrams**: When adding/removing sub-agents, tools, or changing the architecture, update the mermaid diagrams in `README.md`:
  - System Architecture flowchart (shows agents, tools, GCP services)
  - Interaction Workflow sequence diagram (shows investigation phases)
- **Reference AGENTS.md**: Use this file as the source of truth for developer workflows.

### Deployment Script Requirements
- **Update deploy.py**: When adding new dependencies to `pyproject.toml`, also add them to `deploy/deploy.py` requirements list so Agent Engine deployments work correctly.
- **Keep imports in sync**: If agent module names change, update the import in `deploy/deploy.py`.

## Architecture Overview

The SRE Agent uses a **multi-stage analysis pipeline** with specialized sub-agents. See `README.md` for detailed architecture diagrams.

### Trace Analysis Pipeline

1. **Stage 0 (Aggregate)**: BigQuery-powered analysis using `aggregate_analyzer` sub-agent
   - Tools: `analyze_aggregate_metrics`, `find_exemplar_traces`, `compare_time_periods`, `detect_trend_changes`
   - Purpose: Analyze thousands of traces to identify patterns

2. **Stage 1 (Triage)**: Parallel trace comparison using 4 sub-agents
   - Agents: `latency_analyzer`, `error_analyzer`, `structure_analyzer`, `statistics_analyzer`
   - Purpose: Compare specific traces to identify WHAT is different

3. **Stage 2 (Deep Dive)**: Root cause analysis using 2 sub-agents
   - Agents: `causality_analyzer`, `service_impact_analyzer`
   - Purpose: Determine WHY differences occurred and assess blast radius

### Log Analysis Pipeline

- **log_pattern_extractor**: Uses Drain3 algorithm for log template extraction
  - Tools: `extract_log_patterns`, `compare_log_patterns`, `analyze_log_anomalies`
  - Purpose: Compress logs into patterns, detect anomalies by comparing time periods

## Dev Environment Tips

- Use `uv sync` to install dependencies and create the virtual environment.
- Use `uv run adk web sre_agent` to launch the agent's web interface.
- Use `uv run adk run sre_agent` to launch the interactive terminal interface.
- Environment variables are managed in `.env`. Copy `.env.example` to `.env`.
- Agent definitions are in `sre_agent/agent.py` and `sub_agents/`.
- Deployment scripts are in `deploy/` (`uv run python deploy/deploy.py --create`).

## Testing Instructions

- Run tests: `uv run pytest`
- Run with output: `uv run pytest -s`
- Tests are in `tests/` directory.

## Code Quality

- **Flake8**: `uv run flake8 .` (config in `.flake8`)
- **Max line length**: 127
- **Max complexity**: 10

## PR Instructions

- Ensure `uv.lock` is updated if dependencies change.
- Verify `uv run pytest` passes.
- If modifying architecture, update diagrams in `README.md`.
- If adding dependencies, update `deploy/deploy.py`.
- Title format: `[sre-agent] <Description>`
