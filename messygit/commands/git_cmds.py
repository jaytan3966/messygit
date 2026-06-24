"""git group: add, commit, push, outbox."""

import click
from rich.panel import Panel
from rich.text import Text

from ..config import (
    AnthropicInsufficientBalanceError,
    InvalidAnthropicCredentialsError,
    MissingApiKeyError,
)
from ..git import (
    get_staged_diff,
    get_unpushed_commits,
    git_add,
    git_commit,
    git_push,
    is_git_repo,
)
from ..llm import generate_commit_message
from ..usage import SESSION_USAGE
from ..ui import theme
from ..ui.output import console, err_console, print_error, success, warn
from ..ui.spinner import spinner
from ..ui.theme import MUTED, SUCCESS
from .usage import print_usage_delta


def _prompt_commit_action(message: str) -> None:
    """Ask [Y/n/e]: commit, cancel, or edit in $EDITOR."""
    current = message
    while True:
        console.print(
            Panel(current, title="proposed commit", border_style=theme.BRAND, title_align="left")
        )
        choice = click.prompt(
            theme.brand_ansi("Commit with this message? [y/n/e]", bold=False),
            default="Y",
            show_default=False,
        ).strip().lower()

        if choice in ("", "y", "yes"):
            result = git_commit(current)
            if result.returncode != 0:
                if result.stderr:
                    err_console.print(result.stderr.strip())
                print_error("git commit failed.")
                return
            summary = (result.stdout or "").strip().splitlines()
            success("Committed" + (f" — {summary[0]}" if summary else ""))
            return

        if choice in ("n", "no"):
            warn("Commit cancelled.")
            return

        if choice in ("e", "edit"):
            edited = click.edit(current)
            if edited is None:
                warn("Editor exited without saving; message unchanged.")
                continue
            stripped = edited.strip()
            if not stripped:
                warn("Empty message ignored; message unchanged.")
                continue
            current = stripped
            continue

        warn("Please answer y (yes), n (no), or e (edit).")


def handle_add(args: list[str]) -> None:
    if not args:
        print_error("Usage: add <file> ... or add .")
        return
    result = git_add(args)
    if result.returncode != 0:
        print_error(result.stderr.strip() if result.stderr else "git add failed.")
        return
    label = "everything" if args == ["."] else ", ".join(args)
    success(f"Staged [{SUCCESS}]{label}[/]")


def handle_push() -> None:
    with spinner("pushing to remote"):
        result = git_push()
    if result.returncode != 0:
        print_error(result.stderr.strip() if result.stderr else "git push failed.")
        return
    output = (result.stdout or result.stderr or "").strip()
    success(output if output else "Pushed successfully.")


def handle_outbox() -> None:
    if not is_git_repo():
        print_error("Not a git repository.")
        return
    box = get_unpushed_commits()
    if box.upstream is None:
        print_error(
            "No upstream branch set — push once with 'git push -u' to start tracking."
        )
        return
    if not box.commits:
        success(f"Up to date with [{theme.BRAND}]{box.upstream}[/] — nothing to push.")
        return

    n = len(box.commits)
    body = Text()
    body.append(
        f"{n} commit{'s' if n != 1 else ''} ahead of {box.upstream}\n\n", style=MUTED
    )
    for commit in box.commits:
        body.append(f"{commit.short_hash} ", style=theme.BRAND)
        body.append(f"{commit.subject}\n", style="default")
    console.print(
        Panel(body, title="outbox", border_style=theme.BRAND, title_align="left")
    )


def handle_commit() -> None:
    diff = get_staged_diff()
    if not diff.strip():
        warn("No staged changes found. Run 'add .' or 'add <file>' first.")
        return
    before = SESSION_USAGE.total
    try:
        with spinner():
            message = generate_commit_message(diff)
    except (MissingApiKeyError, InvalidAnthropicCredentialsError, AnthropicInsufficientBalanceError) as e:
        print_error(str(e))
        return
    _prompt_commit_action(message)
    print_usage_delta(before)
