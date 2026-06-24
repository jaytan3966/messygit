"""Animated loading indicator shown while blocking on API calls."""

import random
import threading

from rich.live import Live
from rich.text import Text

from . import theme
from .output import console
from .theme import WARNING

SPINNER_PHRASES = [
    "brewing commit magic",
    "reading your diffs",
    "thinking real hard",
    "untangling your code",
    "consulting the git gods",
]


# Spinner themes — a little character that travels along a track. Each theme
# gives a two-frame animation per direction (so it shimmers/chomps as it moves)
# and the character used to draw the track it runs along.
SPINNER_THEMES = [
    # pac-man chomping through dots
    {"right": ("ᗧ", "●"), "left": ("ᗤ", "●"), "track": "·"},
    # spaceship blasting through stars
    {"right": ("🚀", "🛸"), "left": ("🚀", "🛸"), "track": "·"},
    # runner on the track
    {"right": ("🏃", "🏃‍♂️"), "left": ("🏃", "🏃‍♂️"), "track": "."},
    # car on the road
    {"right": ("🚗", "🚙"), "left": ("🚗", "🚙"), "track": "—"},
    # fish swimming through waves
    {"right": ("🐟", "🐠"), "left": ("🐟", "🐠"), "track": "~"},
    # comet streaking across the sky
    {"right": ("☄", "✦"), "left": ("☄", "✦"), "track": "·"},
]


class _CharSpinner:
    """Loading indicator: a little character travels back and forth along a track.

    A theme is chosen at random per use, so consecutive runs show different
    characters (pac-man, spaceship, runner, ...). Renders with rich.Live on a
    background thread so it keeps animating while the main thread is blocked on
    a (synchronous) API call.
    """

    def __init__(self, phrase: str | None = None, width: int = 18):
        self.phrase = phrase or random.choice(SPINNER_PHRASES)
        self.theme = random.choice(SPINNER_THEMES)
        self.width = width
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _frame(self, pos: int, direction: int, tick: bool) -> Text:
        frames = self.theme["right"] if direction > 0 else self.theme["left"]
        char = frames[0] if tick else frames[1]
        fill = self.theme["track"]
        track = fill * pos + char + fill * (self.width - pos - 1)
        return Text.assemble(
            ("  ", ""),
            (f"{self.phrase}  ", theme.BRAND),
            (track, WARNING),
        )

    def _run(self) -> None:
        if not console.is_terminal:
            return
        pos, direction, mouth_open = 0, 1, True
        with Live(console=console, refresh_per_second=30, transient=True) as live:
            while not self._stop.is_set():
                live.update(self._frame(pos, direction, mouth_open))
                mouth_open = not mouth_open
                pos += direction
                if pos >= self.width - 1 or pos <= 0:
                    direction *= -1
                self._stop.wait(0.07)

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join()


def spinner(phrase: str | None = None) -> _CharSpinner:
    """Return the animated character spinner with a random witty phrase."""
    return _CharSpinner(phrase)
