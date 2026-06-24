"""Theme + color palette.

IMPORTANT: BRAND, BRAND_RGB and BANNER_COLOR are reassigned at runtime by
`apply_theme()`. Always read them through the module (e.g. `theme.BRAND`) so you
see the current value — never `from .theme import BRAND`, which would freeze the
value at import time and break the `theme` command. The fixed palette
(SUCCESS/WARNING/ERROR/MUTED) never changes, so importing those by name is fine.
"""

# Preset brand colors selectable via the `theme` command. The chosen color
# drives the banner AND all accent text (prompt, panels, spinner) so the whole
# UI matches. Tuned to stay readable on a dark terminal.
THEMES: dict[str, tuple[int, int, int]] = {
    "ice": (150, 200, 255),
    "aqua": (60, 210, 220),
    "mint": (90, 225, 160),
    "gold": (255, 205, 70),
    "amber": (255, 176, 0),
    "coral": (255, 120, 90),
    "rose": (255, 110, 160),
    "violet": (180, 140, 255),
}
DEFAULT_THEME = "ice"

# Semantic palette — labels are dim, values are bright; one role per color.
# BRAND_RGB / BRAND / BANNER_COLOR are reassigned by apply_theme().
_current_theme = DEFAULT_THEME
BRAND_RGB = THEMES[DEFAULT_THEME]
BRAND = f"rgb({BRAND_RGB[0]},{BRAND_RGB[1]},{BRAND_RGB[2]})"
SUCCESS = "green"
WARNING = "yellow"
ERROR = "red"
MUTED = "bright_black"

# Banner fades from dim gray up to the brand color as the system "boots".
BANNER_COLOR = BRAND_RGB
BANNER_FADE_START = (70, 70, 70)


def apply_theme(name: str) -> None:
    """Point the brand color (and banner) at the named preset."""
    global BRAND_RGB, BRAND, BANNER_COLOR, _current_theme
    rgb = THEMES[name]
    BRAND_RGB = rgb
    BRAND = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
    BANNER_COLOR = rgb
    _current_theme = name


def active_theme() -> str:
    """Name of the currently applied theme."""
    return _current_theme


def brand_ansi(text: str, bold: bool = True) -> str:
    """Wrap text in a truecolor ANSI escape matching BRAND (for click prompts)."""
    r, g, b = BRAND_RGB
    prefix = ("\x1b[1m" if bold else "") + f"\x1b[38;2;{r};{g};{b}m"
    return f"{prefix}{text}\x1b[0m"
