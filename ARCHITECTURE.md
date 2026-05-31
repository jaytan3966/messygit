# Architecture

This document describes the purpose of each file in the `messygit` project.

## Root


| File             | Purpose                                                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `pyproject.toml` | Package metadata, dependencies (`anthropic`, `click`), build system (hatchling), and the `messygit` console script entrypoint. |
| `README.md`      | User-facing documentation: install, usage, commands, and development instructions.                                             |
| `.gitignore`     | Keeps `.venv/`, `__pycache__/`, `dist/`, and `*.egg-info/` out of version control.                                             |


## `messygit/` (Python package)


| File          | Purpose                                                                                                                                                                                                                                                                  |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `__init__.py` | Marks the directory as a Python package (empty).                                                                                                                                                                                                                         |
| `cli.py`      | Click CLI entrypoint. Defines the command group (`main`), the default commit flow (generate → prompt Y/n/e → commit), and subcommands (`config`, `show`). Orchestrates all other modules.                                                                                |
| `git.py`      | All subprocess calls to `git`. Reads staged diffs (`git diff --cached -U0`), parses them into a compact changed-lines format, filters noise files, handles the large-diff fallback (stat summary + top-N most-changed files), and runs `git commit -m`.                  |
| `llm.py`      | Anthropic SDK integration. Creates the client with the resolved API key, calls `messages.create`, extracts the text response, and maps SDK exceptions (`AuthenticationError`, `PermissionDeniedError`, `BadRequestError`, billing 402) into user-friendly error classes. |
| `config.py`   | API key storage and resolution. Reads/writes `~/.messygit/config.json`, checks the `ANTHROPIC_API_KEY` env var, validates keys are non-empty, masks keys for display, and defines all user-facing error messages and exception classes.                                  |
| `prompts.py`  | System prompt and user prompt builder. Contains the full Conventional Commits instructions, input format descriptions (full and truncated), security rules, and the function that wraps staged changes into the user message sent to Claude.                             |


## Data flow

```
User runs `messygit`
       │
       ▼
   cli.py ──► git.py (read staged diff, apply token budget)
       │
       ▼
   cli.py ──► llm.py (send context to Claude)
       │           │
       │           ├── config.py (resolve API key)
       │           └── prompts.py (system + user prompt)
       │
       ▼
   cli.py (display message, prompt Y/n/e)
       │
       ▼
   cli.py ──► git.py (git commit -m "...")
```

