"""Shared console objects and the small print helpers used everywhere."""

from rich.console import Console
from rich.text import Text

from .theme import ERROR, SUCCESS, WARNING, MUTED

console = Console()
err_console = Console(stderr=True)


def print_error(msg: str) -> None:
    err_console.print(f"[{ERROR}]error:[/] {msg}", highlight=False)


def success(msg: str) -> None:
    console.print(f"[{SUCCESS}]✓[/] {msg}", highlight=False)


def warn(msg: str) -> None:
    console.print(f"[{WARNING}]![/] {msg}", highlight=False)


def field(label: str, value: Text | str) -> Text:
    """Build a 'label   value' line with a dim label and bright value."""
    line = Text()
    line.append(f"  {label:<9}", style=MUTED)
    line.append(value if isinstance(value, Text) else Text(value))
    return line
