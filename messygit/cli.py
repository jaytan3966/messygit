import os
import shlex

import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import (
    ANTHROPIC_ENV_VAR,
    load_api_key,
    load_theme,
    mask_api_key,
)
from .git import (
    get_current_branch,
    get_repo_status,
    is_git_repo,
)
from .models import current_model
from .ui import theme
from .ui.banner import animate_banner
from .ui.output import console, field, print_error
from .ui.theme import DEFAULT_THEME, MUTED, SUCCESS, THEMES, WARNING
from .commands.usage import model_pricing, usage_summary
from .commands import account_cmds, agent_cmds, app_cmds, git_cmds

# Commands grouped for the help screen: (group, [(name, description, usage), ...]).
HELP_GROUPS = [
    ("git", [
        ("add", "stage files", "add . or add <file> ..."),
        ("commit", "generate a commit message from staged changes", "commit"),
        ("push", "push commits to remote", "push"),
        ("outbox", "show committed but unpushed commits", "outbox"),
    ]),
    ("messyagent", [
        ("suggest", "suggest next steps for your project", "suggest"),
        ("changelog", "generate a changelog for your project", "changelog"),
    ]),
    ("account", [
        ("config", "set your Anthropic API key", "config <key>"),
        ("show", "display your masked API key", "show"),
        ("model", "change the AI model / see pricing", "model or model <name>"),
        ("tokens", "show session token usage / open billing", "tokens"),
    ]),
    ("app", [
        ("todo", "open your todo list in your editor", "todo"),
        ("theme", "change the UI color", "theme or theme <name>"),
        ("help", "show this help message", "help"),
        ("quit/exit", "exit messygit", "quit"),
    ]),
]


def _api_key_status() -> Text:
    """Return a colored summary of where (if anywhere) an API key is configured."""
    env_key = (os.environ.get(ANTHROPIC_ENV_VAR) or "").strip()
    if env_key:
        return Text.assemble((mask_api_key(env_key), SUCCESS), (" (env)", MUTED))
    file_key = load_api_key()
    if file_key:
        return Text.assemble((mask_api_key(file_key), SUCCESS), (" (config)", MUTED))
    return Text("not set — run: config <key>", style=WARNING)


def _status_summary(status) -> Text:
    """Render staged/modified/untracked counts with color and a dim separator."""
    if not (status.staged or status.modified or status.untracked):
        return Text("clean", style=SUCCESS)
    parts: list[Text] = []
    if status.staged:
        parts.append(Text(f"{status.staged} staged", style=SUCCESS))
    if status.modified:
        parts.append(Text(f"{status.modified} modified", style=WARNING))
    if status.untracked:
        parts.append(Text(f"{status.untracked} untracked", style=MUTED))
    out = Text()
    for i, part in enumerate(parts):
        if i:
            out.append(" · ", style=MUTED)
        out.append_text(part)
    return out


def _print_startup() -> None:
    if not console.is_terminal:
        # Piped/non-interactive: skip decoration entirely.
        console.print("messygit")
        return

    console.print()
    animate_banner()
    console.print()

    if is_git_repo():
        status = get_repo_status()
        branch = Text.assemble(
            ("messygit", theme.BRAND), ("  ⎇ ", MUTED), (status.branch or "detached", theme.BRAND)
        )
        console.print(field("repo", branch))
        console.print(field("status", _status_summary(status)))
    else:
        console.print(field("repo", Text("not a git repository", style=WARNING)))

    console.print(field("api key", _api_key_status()))
    _m = current_model()
    console.print(
        field("model", Text.assemble((_m.label, theme.BRAND), (f"  {model_pricing(_m)}", MUTED)))
    )
    console.print(field("tokens", usage_summary()))
    console.print(f"  {'─' * 60}", style=MUTED)
    console.print(
        f"  [{MUTED}]Type[/] [bold]help[/] [{MUTED}]for commands ·[/] "
        f"[bold]quit[/] [{MUTED}]to exit[/]"
    )
    console.print()


def _print_help() -> None:
    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column(style=f"bold {theme.BRAND}", no_wrap=True)
    table.add_column(style="default")
    table.add_column(style=MUTED)
    for i, (group, commands) in enumerate(HELP_GROUPS):
        if i:
            table.add_row("", "", "")  # blank spacer between groups
        table.add_row(Text(group, style=f"bold {theme.BRAND}"), "", "")
        for name, desc, usage in commands:
            table.add_row(f"  {name}", desc, usage)
    console.print(Panel(table, title="commands", border_style=MUTED, title_align="left"))


COMMANDS = {
    "add": git_cmds.handle_add,
    "commit": lambda args: git_cmds.handle_commit(),
    "push": lambda args: git_cmds.handle_push(),
    "outbox": lambda args: git_cmds.handle_outbox(),
    "config": account_cmds.handle_config,
    "show": lambda args: account_cmds.handle_show(),
    "suggest": lambda args: agent_cmds.handle_suggestion(),
    "changelog": lambda args: agent_cmds.handle_changelog(),
    "tokens": lambda args: account_cmds.handle_tokens(),
    "model": account_cmds.handle_model,
    "todo": lambda args: app_cmds.handle_todo(),
    "theme": app_cmds.handle_theme,
    "help": lambda args: _print_help(),
}


def _load_saved_theme() -> None:
    name = load_theme()
    theme.apply_theme(name if name in THEMES else DEFAULT_THEME)


def _build_prompt() -> str:
    branch = get_current_branch() if is_git_repo() else None
    prompt = theme.brand_ansi("messygit")
    if branch:
        prompt += click.style(f" ({branch})", fg="bright_black")
    prompt += theme.brand_ansi(" ❯ ")
    return prompt


def _repl() -> None:
    _load_saved_theme()
    _print_startup()

    while True:
        try:
            raw = click.prompt(
                _build_prompt(),
                prompt_suffix="",
                default="",
                show_default=False,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            console.print(f"[{theme.BRAND}]Bye![/]")
            break

        if not raw:
            continue

        try:
            parts = shlex.split(raw)
        except ValueError:
            parts = raw.split()

        cmd, args = parts[0].lower(), parts[1:]

        if cmd in ("quit", "exit"):
            console.print(f"[{theme.BRAND}]Bye![/]")
            break

        handler = COMMANDS.get(cmd)
        if handler is None:
            print_error(f"Unknown command '{cmd}'. Type 'help' for a list of commands.")
            continue

        handler(args)
        console.print()


@click.command()
def main():
    """Messy Git — interactive CLI for clean commits from messy code."""
    _repl()


if __name__ == "__main__":
    main()
