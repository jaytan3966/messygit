# messygit

**messygit** is a command-line tool that reads your **staged** Git changes, asks **Claude** (via the [Anthropic API](https://www.anthropic.com/api)) to suggest a **Conventional Commits** subject line, and then lets you **commit**, **cancel**, or **edit** the message before running `git commit`.

## Why use it

- Keeps commit subjects consistent (`feat(scope): describe the change`) without thinking up wording from scratch.
- Only the **staged** diff is sent to the model—what you `git add` is what gets summarized.
- The API key is never printed in full; `show` uses a masked preview.
- Clear errors for missing keys, rejected keys, and billing or zero-balance situations.

## Requirements

- **Python** 3.10 or newer  
- **Git** (run inside a repository)  
- An **Anthropic API key** with access to the Messages API  

## Installation

```bash
pip install messygit
```

This installs the `messygit` command (see `[project.scripts]` in `pyproject.toml`).

### Install from source

From a checkout of this project:

```bash
cd messygit
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## API key

messygit resolves the key in this order:

1. Environment variable **`ANTHROPIC_API_KEY`**
2. Config file **`~/.messygit/config.json`** (written by `messygit config`)

If neither is set, the default command exits with a short message explaining how to fix it.

**Save a key to the config file:**

```bash
messygit config --key YOUR_ANTHROPIC_API_KEY
```

**Show a masked key** (which source is active, without revealing the secret):

```bash
messygit show
```

## Usage

Typical flow:

```bash
git add .
messygit
```

1. If there is nothing staged, messygit tells you to run `git add` first.  
2. Otherwise it sends the staged diff to Claude and prints a suggested one-line message.  
3. You are prompted: **commit** (default), **no** (cancel), or **edit** (open `$EDITOR` to change the message).  
4. On confirmation, it runs `git commit -m "..."` with your chosen text.

### Commands

| Command | Description |
|--------|-------------|
| `messygit` | Generate a message from `git diff --staged`, then prompt to commit / cancel / edit. |
| `messygit config --key KEY` | Store the Anthropic API key under `~/.messygit/config.json`. |
| `messygit show` | Print a masked API key and whether it comes from the environment or config file. |

### Commit message style

The model is instructed to follow **Conventional Commits**, for example:

`feat(auth): validate refresh tokens`

Allowed types include: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`. Subjects are one line, imperative, lowercase, no trailing period, and kept within a reasonable length (see your prompts in the package if you customize behavior).

## Development

Without installing the package, from the **repository root** (the directory that contains the `messygit` package folder):

```bash
.venv/bin/python -m messygit.cli
```

Subcommands:

```bash
python -m messygit.cli config --key YOUR_KEY
python -m messygit.cli show
```

## License

MIT (see `pyproject.toml`).
