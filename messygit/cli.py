import os

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
from .git import get_staged_diff, git_commit
from .llm import generate_commit_message

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
                raise click.ClickException("git commit failed.")
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

        click.echo("Please answer Y (yes), n (no), or e (edit).")

@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """Messy Git is a tool that analyzes your updated code and generates clean commit messages. Let's keep your "messy" messages in check!"""
    if ctx.invoked_subcommand is None:
        diff = get_staged_diff()
        if not diff.strip():
            raise click.ClickException(
                "No staged changes found. Run 'git add' first."
            )
        try:
            message = generate_commit_message(diff)
        except MissingApiKeyError as e:
            raise click.ClickException(str(e)) from e
        except InvalidAnthropicCredentialsError as e:
            raise click.ClickException(str(e)) from e
        except AnthropicInsufficientBalanceError as e:
            raise click.ClickException(str(e)) from e
        _prompt_commit_action(message)

@main.command("config")
@click.option("--key", type=str, required=True, help="Anthropic API key")
def config_cmd(key):
    """Configure your Anthropic API key."""
    save_api_key(key)
    click.echo(f"API key saved successfully ({mask_api_key(key)})")

@main.command("show")
def show():
    """Display masked API key (env takes precedence over config file)."""
    env_key = (os.environ.get(ANTHROPIC_ENV_VAR) or "").strip()
    if env_key:
        click.echo(f"API key: {mask_api_key(env_key)} (from ANTHROPIC_API_KEY)")
        return
    file_key = load_api_key()
    if file_key and str(file_key).strip():
        click.echo(f"API key: {mask_api_key(file_key)} (from {CONFIG_FILE})")
        return
    click.echo("No API key found. Set ANTHROPIC_API_KEY or run messygit config --key.")

if __name__ == "__main__":
    main()
