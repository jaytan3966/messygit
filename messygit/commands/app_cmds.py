"""app group: todo, theme."""

import click
from rich.text import Text

from ..config import load_todo, save_todo, save_theme
from ..ui import theme
from ..ui.output import console, print_error, success, warn
from ..ui.theme import MUTED, THEMES

TODO_SEED = "# messygit todo\n\n- \n"


def handle_todo() -> None:
    """Open the persisted todo file in $EDITOR; save whatever comes back."""
    current = load_todo()
    seed = current if current.strip() else TODO_SEED
    edited = click.edit(seed)
    if edited is None:
        warn("Editor exited without saving; todo unchanged.")
        return
    save_todo(edited)
    open_items = sum(
        1 for line in edited.splitlines() if line.lstrip().startswith(("- ", "* "))
        and line.strip() not in ("-", "*")
    )
    success(f"Todo saved [{MUTED}]({open_items} item{'s' if open_items != 1 else ''})[/]")


def _swatch(rgb: tuple[int, int, int]) -> Text:
    r, g, b = rgb
    return Text("███", style=f"rgb({r},{g},{b})")


def _print_theme_list() -> None:
    console.print(
        f"[{MUTED}]Available themes — usage:[/] [bold]theme <name>[/]", highlight=False
    )
    for name, rgb in THEMES.items():
        current = name == theme.active_theme()
        line = Text()
        line.append("  ● " if current else "    ", style=theme.BRAND if current else MUTED)
        line.append_text(_swatch(rgb))
        line.append("  ")
        line.append(name, style="bold" if current else "default")
        if current:
            line.append("  (current)", style=MUTED)
        console.print(line)


def handle_theme(args: list[str]) -> None:
    if not args:
        _print_theme_list()
        return
    name = args[0].lower()
    if name not in THEMES:
        print_error(f"Unknown theme '{name}'. Run 'theme' to see the options.")
        return
    theme.apply_theme(name)
    save_theme(name)
    console.print(Text.assemble("Theme set to ", (name, theme.BRAND), "  ") + _swatch(THEMES[name]))
