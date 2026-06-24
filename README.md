# messygit

**messygit** is an interactive CLI that turns messy git workflows into clean Conventional Commits — stage, commit, push, generate changelogs, and get AI-powered project suggestions, all from one interface powered by [Claude](https://www.anthropic.com/api).

## Why use it

- **Interactive REPL** — one command drops you into a persistent session where you can stage, commit, push, and more without leaving.
- **AI commit messages** — sends your staged diff to Claude and suggests a clean Conventional Commits subject line.
- **Project suggestions** — an AI agent inspects your repo and recommends concrete next steps.
- **Changelog generation** — an agent reads the commits between your two latest tags, drills into unclear ones, categorizes the changes, and writes/updates `CHANGELOG.md`.
- **See what the agent did** — runs are clean by default; type `trace` to expand the last run's tool calls, or flip `verbose` on to stream each step live.
- **Token usage & cost** — tracks the tokens each session uses and shows a rough cost estimate, with a one-command jump to billing.
- **Themed UI** — a colored startup animation and prompt you can recolor with the `theme` command.
- **Safe by default** — only the staged diff is sent for `commit`; agents use read-only git plus repo-scoped file tools that reject paths outside the repository. Your API key is never printed in full.

## Requirements

- **Python** 3.10 or newer
- **Git** (run inside a repository)
- An **Anthropic API key** with access to the Messages API

## Installation

```bash
pip install messygit
```

### Install from source

```bash
cd messygit
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## API key

messygit resolves the key in this order:

1. Environment variable **`ANTHROPIC_API_KEY`**
2. Config file **`~/.messygit/config.json`**

You can set the key from within the messygit interface:

```
messygit > config YOUR_ANTHROPIC_API_KEY
```

## Usage

```bash
messygit
```

This drops you into the interactive interface — an animated banner followed by a
status dashboard, then the prompt:

```
 mmm    mmmm  eeeeeee  sssssss  sssssss  yy   yy  ggggggg  ii  tttttttt
 mm mm mm mm  ee       ss       ss        yy yy   gg       ii     tt
 mm  mmm  mm  eeeee    sssssss  sssssss    yy     gg  ggg  ii     tt
 mm       mm  ee            ss       ss    yy     gg   gg  ii     tt
 mm       mm  eeeeeee  sssssss  sssssss    yy     ggggg    ii     tt

  repo     messygit  ⎇ main
  status   3 staged · 2 modified
  api key  sk-ant-a...x3f2 (config)
  model    Haiku 4.5  $1 in · $5 out / 1M
  tokens   0 used this session
  ────────────────────────────────────────────────────────────
  Type help for commands · quit to exit

messygit (main) ❯
```

### Commands

Commands are grouped on the `help` screen:

**git**

| Command | Description |
|---------|-------------|
| `add <file>` or `add .` | Stage files for commit |
| `commit` | Generate an AI commit message from staged changes, then commit / cancel / edit |
| `push` | Push commits to remote |
| `outbox` | Show commits made locally but not yet pushed to the upstream branch |

**messyagent**

| Command | Description |
|---------|-------------|
| `suggest` | Get AI-powered next-step suggestions for your project |
| `changelog` | Generate or update `CHANGELOG.md` from the commits between your two latest tags (requires at least one tag) |
| `trace` | Show what the last agent run actually did — its tool calls and results |

**account**

| Command | Description |
|---------|-------------|
| `config <key>` | Save your Anthropic API key to `~/.messygit/config.json` |
| `show` | Display a masked API key and its source |
| `model` or `model <name>` | Switch the Claude model (run `model` to list models and pricing) |
| `tokens` | Show this session's token usage and estimated cost, and open the billing console |

**app**

| Command | Description |
|---------|-------------|
| `todo` | Open your todo list in `$EDITOR` (saved to `~/.messygit/todo.md`) |
| `theme` or `theme <name>` | Change the UI color (run `theme` to list presets) |
| `verbose` or `verbose on\|off` | Toggle live streaming of agent steps (persists; off by default) |
| `help` | List available commands |
| `quit` / `exit` | Exit messygit |

### Typical flow

```
messygit > add .
Staged everything

messygit > commit
feat(cli): add interactive REPL with ASCII banner
Commit with this message? [y/n/e] y

messygit > push
```

> Tip: run `suggest` for AI next-step ideas, or `theme` to recolor the UI.

### Agent commands & transparency

`suggest` and `changelog` are backed by an agent that uses tools (read-only git,
file reads, and — for `changelog` — repo-scoped file writes) over several steps.

By default a run shows only a spinner and the final result. Two commands let you
see inside:

```
messygit > changelog          # generates/updates CHANGELOG.md
messygit > trace              # expand what that run just did

╭─ trace · changelog · 4 tool calls ─────────────╮
│ 1. run_git  tag --sort=-creatordate            │
│    └ v0.4.0  (+3 more lines)                    │
│ 2. run_git  log v0.3.2..v0.4.0                  │
│    └ commit a1b2c3 feat: …  (+12 more lines)    │
│ 3. read_file  CHANGELOG.md                      │
│    └ ## [v0.3.2] - 2026-06-20                    │
│ 4. edit_file  CHANGELOG.md                      │
│    └ File edited successfully.                   │
╰─────────────────────────────────────────────────╯
```

Prefer to watch it happen live? Turn on `verbose` — the same steps stream as the
agent works (no spinner). The setting persists in `~/.messygit/config.json`:

```
messygit > verbose on
Verbose on — agent runs will stream their steps live (no spinner)
```

`changelog` requires at least one git tag; it documents the range between your two
most recent tags (or the latest tag to `HEAD` when only one exists).

### Commit message style

The model follows **Conventional Commits**: `type(scope): description`

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`. Subjects are one line, imperative, lowercase, no trailing period.

### Token usage & cost

messygit tracks the tokens used by AI commands (`commit`, `suggest`, `changelog`) for the current session and shows a running total after each call. Run `tokens` for a breakdown and a one-key jump to the Anthropic billing console:

```
messygit > tokens
╭─ token usage ─────────────────────────────╮
│ used     8,420 tokens                     │
│          6,200 in · 2,220 out             │
│ requests 2                                │
│ est cost ≈ $0.02                          │
╰───────────────────────────────────────────╯
```

The cost is a **rough estimate** at the selected model's [pricing](https://www.anthropic.com/pricing). The Anthropic API does not expose remaining account credits, so usage and cost are measured per session only.

### Choosing a model

messygit defaults to **Claude Haiku 4.5** (fast and cheap). Use `model` to list the available models and their token pricing, or `model <name>` to switch (your choice persists in `~/.messygit/config.json`):

```
messygit > model
Available models — usage: model <name>
  ● haiku  Haiku 4.5   $1 in · $5 out / 1M  (current)
    sonnet Sonnet 4.6  $3 in · $15 out / 1M
    opus   Opus 4.8    $5 in · $25 out / 1M

messygit > model opus
! Opus 4.8 costs more than Haiku 4.5 ($5 in · $25 out / 1M vs $1 in · $5 out / 1M). Token usage will be billed at the higher rate.
Switch anyway? [y/N]:
```

Switching to a **more expensive** model prompts for confirmation first. The session cost estimate prices each request at the model used for it, so it stays accurate even if you switch mid-session.

## Development & testing

Install the package with its dev dependencies (pytest), then run the suite:

```bash
pip install -e ".[dev]"
pytest -q
```

The tests live in `tests/` and are pure unit tests — no network calls and no
API key required (the Anthropic client is simulated). They cover:

| File | What it covers |
|------|----------------|
| `tests/config_test.py` | API-key resolution order (env → file), key save/load, theme/model/todo persistence, malformed-config handling |
| `tests/git_test.py` | The diff parser — noise-file filtering and the compact changed-lines format |
| `tests/llm_test.py` | Insufficient-balance / billing-error detection and user messaging |
| `tests/tool_schema_test.py` | Agent tool schemas match the shape the Anthropic Messages API expects |
| `tests/agent_test.py` | The agent's tool-use loop, driven by a simulated Anthropic client with scripted responses |
| `tests/trace_test.py` | The `trace` renderer — step numbering, result truncation, empty state, and markup-safety of raw tool output |
| `tests/verbose_test.py` | The `verbose` setting, the toggle command, and `_drive` choosing live-stream vs. spinner |

### Continuous integration

`.github/workflows/test.yml` runs `pytest` on every push to `main` and on every
pull request, across Python 3.10–3.13. No secrets are required because the tests
mock the Anthropic client.

## Publishing to PyPI

This project uses GitHub Actions with [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/) — no API tokens needed in your repo.

### One-time setup

1. Go to your project on [pypi.org](https://pypi.org/manage/project/messygit/settings/publishing/)
2. Add a **Trusted Publisher**:
   - **Owner:** your GitHub username
   - **Repository:** `messygit`
   - **Workflow name:** `publish.yml`
   - **Environment:** leave blank

### To release a new version

1. Bump `version` in `pyproject.toml`
2. Commit and push
3. Create a GitHub release:

```bash
git tag v0.2.0
git push origin v0.2.0
```

4. Go to GitHub → Releases → Draft a new release → select the tag → Publish

The workflow at `.github/workflows/publish.yml` will automatically build and upload to PyPI.

### Manual publish (without CI)

```bash
rm -rf dist/
python -m build
twine upload dist/*
```

## License

MIT (see `pyproject.toml`).
