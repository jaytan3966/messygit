# Architecture

This document describes the purpose of each file in the `messygit` project.

The package is organized in layers. `ui/` is the shared presentation foundation
(console, theme, spinner, banner). `commands/` holds the command handlers grouped
the same way the `help` screen groups them. `agent/` is a self-contained tool-use
loop. `cli.py` is a thin shell that wires everything together. Dependencies flow
one way — `ui/` knows nothing about `commands/`, and `commands/` knows nothing
about `cli` — so there are no import cycles.

## Root

| File                            | Purpose                                                                                                                        |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `pyproject.toml`                | Package metadata, dependencies (`anthropic`, `click`, `rich`), build system (hatchling), and the `messygit` console script.    |
| `README.md`                     | User-facing documentation: install, usage, commands, and development instructions.                                             |
| `ARCHITECTURE.md`               | This file — a per-module map of the codebase.                                                                                   |
| `CHANGELOG.md`                  | Release notes, generated/updated by the `changelog` command.                                                                   |
| `.gitignore`                    | Keeps `.venv/`, `__pycache__/`, `dist/`, and `*.egg-info/` out of version control.                                             |
| `.github/workflows/test.yml`    | Runs `pytest` on every push/PR across Python 3.10–3.13.                                                                         |
| `.github/workflows/publish.yml` | Builds and publishes to PyPI via trusted publishing on release.                                                                |

## `messygit/` (core package)

| File          | Purpose                                                                                                                                                                                                                                                |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `__init__.py` | Marks the directory as a Python package.                                                                                                                                                                                                              |
| `cli.py`      | The REPL shell: prints the startup dashboard, runs the prompt loop, owns the `COMMANDS` dispatch table and the `help` screen, and applies the saved theme on launch. Delegates all real work to `commands/`.                                          |
| `git.py`      | All subprocess calls to `git`. Reads staged diffs (`git diff --cached -U0`), parses them into a compact changed-lines format, filters noise files, handles the large-diff fallback (stat summary + top-N changed files), and runs `add`/`commit`/`push`. |
| `llm.py`      | Anthropic SDK integration for the (non-agentic) `commit` path. Creates the client, calls `messages.create`, extracts text, and maps SDK exceptions (auth, permission, billing/402) into user-friendly error classes. Exposes helpers reused by `agent/agent.py`. |
| `config.py`   | Reads/writes `~/.messygit/config.json`: API key (plus `ANTHROPIC_API_KEY` env resolution), theme, model, todo, and the `verbose` flag. Masks keys for display and defines user-facing error messages and exception classes.                            |
| `models.py`   | The selectable Claude models, their labels, and approximate per-million-token pricing; resolves the active model from config.                                                                                                                        |
| `usage.py`    | Session-local token-usage tracker (`SESSION_USAGE`) and the billing URL. The API exposes no balance endpoint, so usage/cost are accumulated per session.                                                                                              |
| `prompts.py`  | The three system prompts — `COMMIT_SYSTEM_PROMPT`, `SUGGESTION_SYSTEM_PROMPT`, `CHANGELOG_SYSTEM_PROMPT` — plus `build_user_prompt`. Each prompt includes anti-hallucination and untrusted-input guardrails.                                          |

## `messygit/ui/` (shared presentation)

| File         | Purpose                                                                                                                                                                  |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `theme.py`   | Color palette and theme state. `BRAND`/`BRAND_RGB`/`BANNER_COLOR` are reassigned at runtime by `apply_theme()`, so other modules read them as `theme.BRAND` (never import the name directly). Also `brand_ansi()` and `active_theme()`. |
| `output.py`  | The shared `console`/`err_console` objects and the small print helpers (`print_error`, `success`, `warn`, `field`).                                                     |
| `spinner.py` | The threaded `_CharSpinner` loading animation and the `spinner()` factory.                                                                                              |
| `banner.py`  | The ASCII banner art and its boot animation (`animate_banner`).                                                                                                         |

## `messygit/commands/` (command handlers)

| File              | Purpose                                                                                                                                                  |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `git_cmds.py`     | The git group: `add`, `commit` (AI message + Y/n/e prompt), `push`, `outbox`.                                                                           |
| `agent_cmds.py`   | The agent group: `suggest` and `changelog`. `_drive()` runs an agent either under a spinner or streaming live (verbose), and records the run's trace.    |
| `account_cmds.py` | The account group: `config`, `show`, `model`, `tokens`.                                                                                                 |
| `app_cmds.py`     | The app group: `todo`, `theme`, `verbose`.                                                                                                              |
| `usage.py`        | Token-usage/cost *display* helpers (`usage_summary`, `print_usage_delta`, `model_pricing`, the high-usage warning). Distinct from the root `usage.py` tracker. |
| `trace.py`        | The `trace` command. Stores the last agent run's steps and renders them as a panel; also provides `live_reporter()`, the per-step formatter that verbose mode streams. |

## `messygit/agent/` (agentic tool-use subpackage)

| File       | Purpose                                                                                                                                                                                                                            |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tool.py`  | `Tool` dataclass wrapping a Python callable with a name, description, and parameter schema. `run()` invokes the function; `to_schema()` emits an Anthropic-compatible tool definition.                                            |
| `tools.py` | Concrete tools: `run_git_tool` (allowlisted read-only git, including tag ranges), `read_file_tool`, `list_directory_tool`, `search_code_tool` (`git grep`), `write_file_tool` (full overwrite), and `edit_file_tool` (unique-match string replace). All file tools reject paths outside the repo root. |
| `agent.py` | The agentic loop. Sends messages to Claude with tool definitions, dispatches `tool_use` blocks to matching `Tool`s, feeds results back, and iterates up to `max_iterations`. Records each step as a `TraceStep` (optionally streamed via an `on_step` callback) and warns when the iteration cap is hit before finishing. |

## Data flow

```
User runs `messygit` → cli.py REPL (dispatch table)
       │
       ├── "add <files>" / "push" ─────► commands/git_cmds.py ─► git.py
       ├── "config" / "show" / "model" / "tokens" ─► commands/account_cmds.py ─► config.py / usage.py
       ├── "todo" / "theme" / "verbose" ─────► commands/app_cmds.py ─► config.py
       ├── "trace" ─────────────────────► commands/trace.py (render last run)
       │
       ├── "commit" ──► commands/git_cmds.py
       │       │            ├── git.py (staged diff + token budget)
       │       │            └── llm.py ─► prompts.COMMIT_SYSTEM_PROMPT, config.py (key)
       │       ▼
       │   Y/n/e prompt ─► git.py (git commit)
       │
       └── "suggest" / "changelog" ──► commands/agent_cmds.py
               │            └── agent/agent.py (tool-use loop)
               │                    ├── config.py (key) + models.py
               │                    ├── prompts.{SUGGESTION,CHANGELOG}_SYSTEM_PROMPT
               │                    └── agent/tools.py (run_git, read_file, list_directory,
               │                                        write_file, edit_file)
               ▼
           spinner OR live step stream (verbose); steps saved for `trace`
```
