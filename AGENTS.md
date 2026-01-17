# SRE Agent: Developer Guidelines

## 🚀 Core Workflows

We use **`uv`** for dependency management and **`poethepoet`** for task automation defined in `pyproject.toml`.

| Task | Command | Description |
|------|---------|-------------|
| **Sync** | `uv run poe sync` | Install dependencies and update `.venv` |
| **Run** | `uv run poe run` | Launch interactive terminal agent |
| **Lint** | `uv run poe lint` | Run **Ruff**, **MyPy**, **Codespell**, and **Deptry** |
| **Test** | `uv run poe test` | Run **Pytest** with coverage guards |
| **Deploy** | `uv run poe deploy` | Validate & Deploy to Agent Engine |
| **Pre-commit** | `uv run poe pre-commit` | Run quality guards (formatting, trailing whitespace) |

## 🛠️ Development Rules

### 1. Modern Python Stack
- **Dependencies**: Managed via `pyproject.toml` (NOT `requirements.txt`).
- **Lockfile**: Always commit `uv.lock`.
- **Python Version**: 3.10+ (Testing uses 3.10 & 3.11).
- **Import Style**: Use absolute imports (e.g., `sre_agent.tools...`) except for relative sibling/parent imports within modules.

### 2. Code Quality & Linting
- **Linter**: **Ruff** replaces Flake8/Black/Isort. Configuration is in `pyproject.toml`.
- **Type Checking**: **MyPy** is strict.
  - **Explicit Optional**: Use `name: str | None = None` instead of `name: str = None`.
  - **No Implicit Any**: Annotate empty containers: `items: list[dict[str, Any]] = []`.
  - **Float Initialization**: Use `val: float = 0.0` (not `0`) to satisfy strict typing.
- **Pydantic Schemas**: Use `model_config = ConfigDict(frozen=True, extra="forbid")` for all structured outputs.
  - **Why**: Ensures LLM hallucinations (extra fields) are caught immediately.
- **Dependency Freshness**: **Deptry** ensures no unused or missing dependencies are in `pyproject.toml`.
- **Error Envelopes**: All tools should follow the `BaseToolResponse` structure (status, result, error, metadata) to ensure the Orchestrator can handle failures gracefully.
- **Structured Logging**: Use `configure_logging()` from `sre_agent.tools.common.telemetry`. Set `LOG_FORMAT=JSON` in production for Cloud Logging compatibility.
- **Secret Scanning**: **detect-secrets** scans for leaked keys.
  - If you encounter a false positive, update the baseline: `uv run detect-secrets scan --baseline .secrets.baseline`.
- **Pre-commit**: You **MUST** run `uv run poe pre-commit` before pushing. It fixes formatting and spacing issues automatically.

### 3. Testing & Coverage
- **Framework**: `pytest` + `pytest-asyncio` + `pytest-cov`.
- **Coverage Guard**: A minimum of **70%** test coverage is enforced. `uv run poe test` will fail if coverage drops below this.
- **Structure**: Tests mirror source directory (e.g., `tests/sre_agent/tools/...` corresponds to `sre_agent/tools/...`).
- **Mocks**: Heavy use of `unittest.mock` to avoid hitting real GCP APIs during unit tests.

### 4. Deployment Protocol
- **Command**: Always use `uv run poe deploy`.
- **Validation-First**: The deploy script (`deploy/deploy.py`) verifies:
  1. Local imports work.
  2. `pyproject.toml` dependencies are extracted accurately.
  3. `uv` sync is fresh.
- **Agent Engine**: Used for hosting. `deploy.py` handles the creation and update of the Reasoning Engine resource.
### 5. Git Standards
- **Conventional Commits**: Use semantic prefixes to help agents and automation understand changes:
  - `feat`: New capability
  - `fix`: Bug fix
  - `docs`: Documentation only
  - `style`: Formatting, missing semi colons, etc; no code change
  - `refactor`: Refactoring production code
  - `perf`: Code change that improves performance
  - `test`: Adding missing tests, refactoring tests; no production code change
  - `chore`: Updating build tasks, package manager configs, etc; no production code change

## 📝 Documentation Rules

- **Readme Updates**: If you add a feature, update:
  - `README.md`: Architecture diagrams and Tool tables.
  - `AGENTS.md`: If workflows change.
- **Architecture Diagrams**: Maintain Mermaid charts in `README.md`:
  - **System Architecture**: Sub-agents, tools, and GCP services.
  - **Interaction Workflow**: Sequence of analysis phases.

## 📦 Sub-Agent Architecture

The project follows the "Council of Experts" pattern:

1.  **Orchestrator** (`sre_agent/agent.py`):
    - Receives user query.
    - Delegated to specialized sub-agents (`sre_agent/sub_agents/`).
2.  **Specialists**:
    - **Trace Squad**: Latency, Error, Structure, Stats.
    - **Log Squad**: Pattern Extractor.
    - **Metrics Squad**: Metrics Analyzer.
3.  **Tools**:
    - Located in `sre_agent/tools/`.
    - Divided into `mcp/` (Model Context Protocol) and `clients/` (Direct API).

## ✅ PR Checklist

1.  Sync dependencies: `uv run poe sync`
2.  Run pre-commit: `uv run poe pre-commit`
3.  Run lint checks: `uv run poe lint` (Must pass clean)
4.  Run tests: `uv run poe test` (Must pass all tests)
5.  Update docs: `README.md` if visible behavior changed.
