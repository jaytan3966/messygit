"""The messygit ASCII banner and its boot animation."""

import time

from rich.console import Group
from rich.live import Live
from rich.text import Text

from . import theme
from .output import console
from .theme import MUTED

BANNER_ART = r"""
  mmm    mmmm  eeeeeee  sssssss  sssssss  yy   yy  ggggggg  ii  tttttttt
  mm mm mm mm  ee       ss       ss        yy yy   gg       ii     tt
  mm  mmm  mm  eeeee    sssssss  sssssss    yy     gg  ggg  ii     tt
  mm       mm  ee            ss       ss    yy     gg   gg  ii     tt
  mm       mm  eeeeeee  sssssss  sssssss    yy     ggggg    ii     tt
""".strip("\n")

_BANNER_WIDTH = max(len(line) for line in BANNER_ART.splitlines())


def banner(rgb: tuple[int, int, int] | None = None) -> Text:
    """Render the whole banner in a single color."""
    r, g, b = rgb if rgb is not None else theme.BANNER_COLOR
    return Text(BANNER_ART, style=f"bold rgb({r},{g},{b})")


def _boot_frame(rgb: tuple[int, int, int], progress: float) -> Group:
    """Banner wrapped in a top/bottom progress bar that fills as it boots."""
    filled = round(_BANNER_WIDTH * progress)
    bar = Text()
    bar.append("=" * filled, style=f"bold {theme.BRAND}")
    bar.append("=" * (_BANNER_WIDTH - filled), style=MUTED)
    return Group(Text("  ") + bar, banner(rgb), Text("  ") + bar)


def animate_banner() -> None:
    """Boot sequence: progress bars fill while the name fades in to the brand color."""
    if not console.is_terminal:
        console.print(_boot_frame(theme.BANNER_COLOR, 1.0))
        return
    steps = 24
    with Live(console=console, refresh_per_second=60, transient=False) as live:
        for i in range(steps + 1):
            t = i / steps
            rgb = tuple(
                round(a + (b - a) * t)
                for a, b in zip(theme.BANNER_FADE_START, theme.BANNER_COLOR)
            )
            live.update(_boot_frame(rgb, t))
            time.sleep(0.06)
        live.update(_boot_frame(theme.BANNER_COLOR, 1.0))
