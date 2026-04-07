import click
from config import save_api_key, load_api_key
from git import get_staged_diff, get_staged_files

@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """Messy Git is a tool that analyzes your updated code and generates clean commit messages. Let's keep your "messy" messages in check!"""
    if ctx.invoked_subcommand is None:
        click.echo(f"Staged diff: {get_staged_diff()}")
        click.echo(f"Staged files: {get_staged_files()}")

@main.command('config')
@click.option('--key', type=str, help='Anthropic API key')
def config(key):
    """Configure your Anthropic API key."""
    click.echo(f"Configuring Messy Git with API key: {key}")
    save_api_key(key)
    click.echo("API key saved successfully")

@main.command('get-api-key')
def get_api_key():
    """Get your Anthropic API key."""
    key = load_api_key()
    click.echo(f"Your Anthropic API key is: {key}")

if __name__ == "__main__":
    main()
