"""messyagent group: suggest, changelog."""

from rich.markdown import Markdown
from rich.panel import Panel

from ..agent.agent import Agent
from ..agent.tools import (
    list_directory_tool,
    read_file_tool,
    run_git_tool,
    write_file_tool,
)
from ..config import (
    AnthropicInsufficientBalanceError,
    InvalidAnthropicCredentialsError,
    MissingApiKeyError,
)
from ..prompts import SUGGESTION_SYSTEM_PROMPT, CHANGELOG_SYSTEM_PROMPT
from ..usage import SESSION_USAGE
from ..ui import theme
from ..ui.output import console, print_error
from ..ui.spinner import spinner
from .usage import print_usage_delta


def handle_suggestion() -> None:
    agent = Agent(
        name="suggestion_agent",
        system_prompt=SUGGESTION_SYSTEM_PROMPT,
        max_iterations=8,
        tools=[run_git_tool, read_file_tool, list_directory_tool],
    )
    before = SESSION_USAGE.total
    try:
        with spinner():
            result = agent.run("What should the next steps for my project be? Let's limit it to 3-5 steps")
    except (MissingApiKeyError, InvalidAnthropicCredentialsError, AnthropicInsufficientBalanceError) as e:
        print_error(str(e))
        return
    console.print(
        Panel(Markdown(result), title="suggested next steps", border_style=theme.BRAND, title_align="left")
    )
    print_usage_delta(before)


def handle_changelog() -> None:
    if not run_git_tool.function(["tag"]).strip():
        print_error(
            "No tags found. Create a tag to mark a release "
            "(e.g. `git tag v0.1.0`) before running changelog."
        )
        return
    agent = Agent(
        name="changelog_agent",
        system_prompt=CHANGELOG_SYSTEM_PROMPT,
        max_iterations=12,
        tools=[run_git_tool, read_file_tool, list_directory_tool, write_file_tool],
    )
    before = SESSION_USAGE.total
    try:
        with spinner():
            result = agent.run("What are the latest changes to my project? Add to or create the CHANGELOG.md markdown file.")
    except (MissingApiKeyError, InvalidAnthropicCredentialsError, AnthropicInsufficientBalanceError) as e:
        print_error(str(e))
        return
    console.print(
        Panel(Markdown(result), title="changelog", border_style=theme.BRAND, title_align="left")
    )
    print_usage_delta(before)
