# Architecture

This document describes the purpose of each file in the `messygit` project.

## Root

| File                              | Purpose                                                                                                                        |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `pyproject.toml`                  | Package metadata, dependencies (`anthropic`, `click`), build system (hatchling), and the `messygit` console script entrypoint. |
| `README.md`                       | User-facing documentation: install, usage, commands, and development instructions.                                             |
| `.gitignore`                      | Keeps `.venv/`, `__pycache__/`, `dist/`, and `*.egg-info/` out of version control.                                             |
| `.github/workflows/publish.yml`   | GitHub Actions workflow for publishing the package.                                                                             |

## `messygit/` (Python package)

| File          | Purpose                                                                                                                                                                                                                                                                 |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__.py` | Marks the directory as a Python package (empty).                                                                                                                                                                                                                        |
| `cli.py`      | Interactive REPL entrypoint. Displays an ASCII banner, runs a prompt loop, and dispatches commands: `add`, `commit`, `push`, `config`, `show`, `suggest`, `help`, `quit`/`exit`. Orchestrates all other modules. Includes a threaded `Spinner` for loading animations.   |
| `git.py`      | All subprocess calls to `git`. Reads staged diffs (`git diff --cached -U0`), parses them into a compact changed-lines format, filters noise files, handles the large-diff fallback (stat summary + top-N most-changed files), and runs `git add`, `git commit`, and `git push`. |
| `llm.py`      | Anthropic SDK integration. Creates the client with the resolved API key, calls `messages.create`, extracts the text response, and maps SDK exceptions (`AuthenticationError`, `PermissionDeniedError`, `BadRequestError`, billing 402) into user-friendly error classes. Also exposes helpers reused by `agent/agent.py`. |
| `config.py`   | API key storage and resolution. Reads/writes `~/.messygit/config.json`, checks the `ANTHROPIC_API_KEY` env var, validates keys are non-empty, masks keys for display, and defines all user-facing error messages and exception classes.                                 |
| `prompts.py`  | System prompts and user prompt builder. Contains the Conventional Commits instructions (`COMMIT_SYSTEM_PROMPT`), the suggestion agent instructions (`SUGGESTION_SYSTEM_PROMPT`), and `build_user_prompt` which wraps staged changes into the user message sent to Claude. |

## `messygit/agent/` (agentic tool-use subpackage)

| File       | Purpose                                                                                                                                                                                                                           |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tool.py`  | `Tool` dataclass wrapping a Python callable with a name, description, and parameter schema. Provides `run()` to invoke the function and `to_schema()` to emit an Anthropic-compatible tool definition.                            |
| `tools.py` | Concrete tool instances available to agents: `run_git_tool` (allowlisted read-only git commands), `read_file_tool`, `list_directory_tool`, and `search_code_tool` (`git grep`).                                                   |
| `agent.py` | Generic agentic loop. Sends messages to Claude with tool definitions, processes `tool_use` response blocks by dispatching to matching `Tool` instances, appends results, and iterates up to `max_iterations`. Handles API errors identically to `llm.py`. |

## Data flow

```
User runs `messygit` → interactive REPL
       │
       ├── "add <files>"  ──► git.py (git add)
       ├── "push"         ──► git.py (git push)
       ├── "config <key>" ──► config.py (save API key)
       ├── "show"         ──► config.py (display masked key)
       │
       ├── "commit" ──► git.py (read staged diff, apply token budget)
       │       │
       │       ▼
       │   llm.py (send context to Claude)
       │       │       │
       │       │       ├── config.py (resolve API key)
       │       │       └── prompts.py (COMMIT_SYSTEM_PROMPT + user prompt)
       │       ▼
       │   cli.py (display message, prompt Y/n/e)
       │       │
       │       ▼
       │   git.py (git commit -m "...")
       │
       └── "suggest" ──► agent/agent.py (agentic loop)
               │               │
               │               ├── config.py (resolve API key)
               │               ├── prompts.py (SUGGESTION_SYSTEM_PROMPT)
               │               └── agent/tools.py (run_git, read_file, list_directory)
               ▼
           cli.py (display suggestion)
```

