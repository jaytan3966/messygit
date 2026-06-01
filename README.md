# messygit

**messygit** is an interactive CLI that turns messy git workflows into clean Conventional Commits — stage, commit, push, and get AI-powered project suggestions, all from one interface powered by [Claude](https://www.anthropic.com/api).

## Why use it

- **Interactive REPL** — one command drops you into a persistent session where you can stage, commit, push, and more without leaving.
- **AI commit messages** — sends your staged diff to Claude and suggests a clean Conventional Commits subject line.
- **Project suggestions** — an AI agent inspects your repo and recommends concrete next steps.
- **Safe by default** — only the staged diff is sent to the model. Your API key is never printed in full.

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

This drops you into the interactive interface:

```
 mmm    mmm  eeeeeee  sssssss  sssssss  yy   yy  ggggggg  ii  tttttttt
 mm mm mm m  ee       ss       ss        yy yy   gg       ii     tt
 mm  mmm  m  eeeee    sssssss  sssssss    yyy    gg  ggg  ii     tt
 mm       m  ee            ss       ss    yy     gg   gg  ii     tt
 mm       m  eeeeeee  sssssss  sssssss   yy      ggggg   ii     tt

Type 'help' for commands, 'quit' to exit.

messygit >
```

### Commands

| Command | Description |
|---------|-------------|
| `add <file>` or `add .` | Stage files for commit |
| `commit` | Generate an AI commit message from staged changes, then commit / cancel / edit |
| `push` | Push commits to remote |
| `suggestion` | Get AI-powered next-step suggestions for your project |
| `config <key>` | Save your Anthropic API key to `~/.messygit/config.json` |
| `show` | Display a masked API key and its source |
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

### Commit message style

The model follows **Conventional Commits**: `type(scope): description`

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`. Subjects are one line, imperative, lowercase, no trailing period.

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
