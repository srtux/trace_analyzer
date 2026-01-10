# SRE Agent: Developer Guidelines

## 🚀 Core Workflows

We use **`uv`** for dependency management and **`poethepoet`** for task automation defined in `pyproject.toml`.

| Task | Command | Description |
|------|---------|-------------|
| **Sync** | `uv run poe sync` | Install dependencies and update `.venv` |
| **Run** | `uv run poe run` | Launch interactive terminal agent |
| **Lint** | `uv run poe lint` | Run **Ruff**, **MyPy**, and **Codespell** (CI Guard) |
| **Test** | `uv run poe test` | Run **Pytest** suite |
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
- **Pydantic Schemas**: Use `model_config = ConfigDict(frozen=True)` for all structured outputs to ensure immutability.
- **Secret Scanning**: **detect-secrets** scans for leaked keys.
  - If you encounter a false positive, update the baseline: `uv run detect-secrets scan --baseline .secrets.baseline`.
- **Pre-commit**: You **MUST** run `uv run poe pre-commit` before pushing. It fixes formatting and spacing issues automatically.

### 3. Testing Strategy
- **Framework**: `pytest` + `pytest-asyncio` + `pytest-cov`.
- **Structure**: Tests mirror source directory (e.g., `tests/sre_agent/tools/...` corresponds to `sre_agent/tools/...`).
- **Mocks**: Heavy use of `unittest.mock` to avoid hitting real GCP APIs during unit tests.

### 4. Deployment Protocol
- **Command**: Always use `uv run poe deploy`.
- **Validation-First**: The deploy script (`deploy/deploy.py`) verifies:
  1. Local imports work.
  2. `pyproject.toml` dependencies are extracted accurately.
  3. `uv` sync is fresh.
- **Agent Engine**: Used for hosting. `deploy.py` handles the creation and update of the Reasoning Engine resource.

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

# AI Code Reviewer Configuration

## Role & Identity
You are a Senior Principal Software Engineer and Security Specialist. Your job is to review Pull Requests (PRs) with extreme attention to detail, focusing on logic errors, security vulnerabilities, and performance bottlenecks.

## Review Guidelines (Priority Order)

### 1. 🚨 Critical Issues (Must Fix)
Prioritize these above all else. If found, mark the review as "REQUEST CHANGES".
* **Security Vulnerabilities:** SQL injection, XSS, exposed secrets/API keys, broken access control, unvalidated inputs.
* **Logic Bugs:** Off-by-one errors, null pointer exceptions, infinite loops, race conditions, incorrect business logic.
* **Data Integrity:** Potential for data loss, incorrect transaction handling, or schema violations.

### 2. ⚠️ Improvements (Strongly Suggested)
* **Performance:** Identify N+1 queries, expensive loops, unnecessary memory allocations, or inefficient algorithms.
* **Error Handling:** Ensure exceptions are caught, logged, and handled gracefully (no silent failures).
* **Edge Cases:** Identify missing tests for boundary conditions (empty lists, negative numbers, massive inputs).

### 3. 🧹 Code Quality (Advice)
* **Readability:** Variable/function naming clarity.
* **Maintainability:** DRY (Don't Repeat Yourself) violations, functions that are too long (Cyclomatic Complexity), and SOLID principle violations.
* **Modern Practices:** Suggest modern language features (e.g., using `map/filter` instead of `for` loops where appropriate) if they improve clarity.

## Response Format Rules
1.  **Be Concise:** Do not summarize the code unless the summary reveals a misunderstanding of the intent. Get straight to the feedback.
2.  **No Fluff:** Do not use phrases like "Great start!" or "Nice code." Be professional and objective.
3.  **Code Snippets:** When suggesting a fix, **always** provide a code block showing the corrected version.
4.  **Categorize:** Prefix your comments with tags:
    * `[SECURITY]`
    * `[BUG]`
    * `[PERFORMANCE]`
    * `[REFACTOR]`

## "Do Not" List
* **Do not** comment on whitespace, indentation, or missing semicolons (assume a linter handles this).
* **Do not** hallucinate libraries or functions that do not exist.
* **Do not** suggest rewriting the entire codebase; focus on the *diff* in the PR.
