import os
import shlex
import sys
import threading
import time

import click

from .config import (
    ANTHROPIC_ENV_VAR,
    CONFIG_FILE,
    AnthropicInsufficientBalanceError,
    InvalidAnthropicCredentialsError,
    MissingApiKeyError,
    load_api_key,
    mask_api_key,
    save_api_key,
)
from .git import get_staged_diff, git_add, git_commit
from .llm import generate_commit_message
from .prompts import SUGGESTION_SYSTEM_PROMPT
from .agent.tools import run_git_tool, read_file_tool, list_directory_tool, search_code_tool
from .agent.agent import Agent

BANNER = r"""
=========================================================================
  mmm    mmmm  eeeeeee  sssssss  sssssss  yy   yy  ggggggg  ii  tttttttt
  mm mm mm mm  ee       ss       ss        yy yy   gg       ii     tt
  mm  mmm  mm  eeeee    sssssss  sssssss    yy     gg  ggg  ii     tt
  mm       mm  ee            ss       ss    yy     gg   gg  ii     tt
  mm       mm  eeeeeee  sssssss  sssssss    yy     ggggg    ii     tt
=========================================================================
"""

HELP_TEXT = """
commands:
  add          stage files (usage: add . or add <file> ...)
  commit       generate a commit message from staged changes
  config       set your Anthropic API key (usage: config <key>)
  show         display your masked API key
  suggestion   suggest next steps for your project
  help         show this help message
  quit/exit    exit messygit
""".strip()

SPINNER_PHRASES = [
    "brewing commit magic",
    "reading your diffs",
    "thinking real hard",
    "untangling your code",
    "consulting the git gods",
]


class Spinner:
    """Animated loading indicator that runs in a background thread."""

    def __init__(self, phrase: str | None = None):
        import random
        self._phrase = phrase or random.choice(SPINNER_PHRASES)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _animate(self) -> None:
        dots = ["   ", ".  ", ".. ", "..."]
        idx = 0
        while not self._stop.is_set():
            frame = f"\r  {self._phrase} {dots[idx % len(dots)]}"
            sys.stderr.write(frame)
            sys.stderr.flush()
            idx += 1
            self._stop.wait(0.4)
        sys.stderr.write("\r" + " " * (len(self._phrase) + 10) + "\r")
        sys.stderr.flush()

    def __enter__(self):
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join()


def _print_error(msg: str) -> None:
    click.secho(f"error: {msg}", fg="red", err=True)


def _prompt_commit_action(message: str) -> None:
    """Ask [Y/n/e]: commit, cancel, or edit in $EDITOR."""
    current = message
    while True:
        click.echo(current)
        choice = click.prompt(
            "Commit with this message? [y/n/e]",
            default="Y",
            show_default=False,
        ).strip().lower()

        if choice in ("", "y", "yes"):
            result = git_commit(current)
            if result.stdout:
                click.echo(result.stdout, nl=False)
            if result.stderr:
                click.echo(result.stderr, nl=False, err=True)
            if result.returncode != 0:
                _print_error("git commit failed.")
            return

        if choice in ("n", "no"):
            click.echo("Commit cancelled.")
            return

        if choice in ("e", "edit"):
            edited = click.edit(current)
            if edited is None:
                click.echo("Editor exited without saving; message unchanged.")
                continue
            stripped = edited.strip()
            if not stripped:
                click.echo("Empty message ignored; message unchanged.")
                continue
            current = stripped
            continue

        click.echo("Please answer y (yes), n (no), or e (edit).")


def _handle_add(args: list[str]) -> None:
    if not args:
        _print_error("Usage: add <file> ... or add .")
        return
    result = git_add(args)
    if result.returncode != 0:
        _print_error(result.stderr.strip() if result.stderr else "git add failed.")
        return
    label = "everything" if args == ["."] else ", ".join(args)
    click.echo(f"Staged {label}")


def _handle_commit() -> None:
    diff = get_staged_diff()
    if not diff.strip():
        _print_error("No staged changes found. Run 'add .' or 'add <file>' first.")
        return
    try:
        with Spinner():
            message = generate_commit_message(diff)
    except (MissingApiKeyError, InvalidAnthropicCredentialsError, AnthropicInsufficientBalanceError) as e:
        _print_error(str(e))
        return
    _prompt_commit_action(message)


def _handle_config(args: list[str]) -> None:
    if not args:
        _print_error("Usage: config <api-key>")
        return
    key = args[0]
    try:
        save_api_key(key)
    except ValueError as e:
        _print_error(str(e))
        return
    click.echo(f"API key saved successfully ({mask_api_key(key.strip())})")


def _handle_show() -> None:
    env_set = ANTHROPIC_ENV_VAR in os.environ
    env_key = (os.environ.get(ANTHROPIC_ENV_VAR) or "").strip()
    if env_key:
        click.echo(f"API key: {mask_api_key(env_key)} (from ANTHROPIC_API_KEY)")
        return
    file_key = load_api_key()
    if file_key:
        if env_set:
            click.echo(
                f"{ANTHROPIC_ENV_VAR} is set but empty; showing key from {CONFIG_FILE}."
            )
        click.echo(f"API key: {mask_api_key(file_key)} (from {CONFIG_FILE})")
        return
    if env_set:
        click.echo(
            f"{ANTHROPIC_ENV_VAR} is set but empty or whitespace-only, and no usable key "
            f"is stored in {CONFIG_FILE}. Unset the variable or run: config <key>"
        )
        return
    click.echo("No API key found. Set ANTHROPIC_API_KEY or run: config <key>")


def _handle_suggestion() -> None:
    agent = Agent(
        name="suggestion_agent",
        system_prompt=SUGGESTION_SYSTEM_PROMPT,
        max_iterations=15,
        tools=[run_git_tool, read_file_tool, list_directory_tool, search_code_tool],
    )
    try:
        with Spinner():
            result = agent.run("What should the next steps for my project be? Let's limit it to 3-5 steps")
    except (MissingApiKeyError, InvalidAnthropicCredentialsError, AnthropicInsufficientBalanceError) as e:
        _print_error(str(e))
        return
    click.echo(result)


COMMANDS = {
    "add": _handle_add,
    "commit": lambda args: _handle_commit(),
    "config": _handle_config,
    "show": lambda args: _handle_show(),
    "suggestion": lambda args: _handle_suggestion(),
    "help": lambda args: click.echo(HELP_TEXT),
}


def _repl() -> None:
    click.echo()
    click.secho(BANNER, fg="cyan", bold=True)
    click.echo()
    click.echo("Type 'help' for commands, 'quit' to exit.")
    click.echo()

    while True:
        try:
            raw = click.prompt(
                click.style("messygit", fg="cyan", bold=True) + click.style(" > ", bold=True),
                prompt_suffix="",
                default="",
                show_default=False,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            click.echo()
            click.secho("Bye!", fg="cyan")
            break

        if not raw:
            continue

        try:
            parts = shlex.split(raw)
        except ValueError:
            parts = raw.split()

        cmd, args = parts[0].lower(), parts[1:]

        if cmd in ("quit", "exit"):
            click.secho("Bye!", fg="cyan")
            break

        handler = COMMANDS.get(cmd)
        if handler is None:
            _print_error(f"Unknown command '{cmd}'. Type 'help' for a list of commands.")
            continue

        handler(args)
        click.echo()


@click.command()
def main():
    """Messy Git — interactive CLI for clean commits from messy code."""
    _repl()


if __name__ == "__main__":
    main()
