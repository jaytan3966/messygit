import os
import random
import shlex
import threading
import time
import webbrowser

import click
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import (
    ANTHROPIC_ENV_VAR,
    CONFIG_FILE,
    AnthropicInsufficientBalanceError,
    InvalidAnthropicCredentialsError,
    MissingApiKeyError,
    load_api_key,
    load_theme,
    load_todo,
    mask_api_key,
    save_api_key,
    save_model,
    save_theme,
    save_todo,
)
from .git import (
    get_current_branch,
    get_repo_status,
    get_staged_diff,
    get_unpushed_commits,
    git_add,
    git_commit,
    git_push,
    is_git_repo,
)
from .llm import generate_commit_message
from .prompts import SUGGESTION_SYSTEM_PROMPT, CHANGELOG_SYSTEM_PROMPT
from .models import MODELS, current_model, resolve_model_key
from .usage import SESSION_USAGE, BILLING_URL
from .agent.tools import run_git_tool, read_file_tool, list_directory_tool, write_file_tool
from .agent.agent import Agent

# Once a session crosses this many tokens, surface a one-time heads-up with the
# billing link (the API can't report remaining credits, so this is usage-based).
HIGH_USAGE_TOKENS = 100_000
_high_usage_warned = False

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
# BRAND_RGB / BRAND / BANNER_COLOR are reassigned by _apply_theme().
_current_theme = DEFAULT_THEME
BRAND_RGB = THEMES[DEFAULT_THEME]
BRAND = f"rgb({BRAND_RGB[0]},{BRAND_RGB[1]},{BRAND_RGB[2]})"
SUCCESS = "green"
WARNING = "yellow"
ERROR = "red"
MUTED = "bright_black"


def _apply_theme(name: str) -> None:
    """Point the brand color (and banner) at the named preset."""
    global BRAND_RGB, BRAND, BANNER_COLOR, _current_theme
    rgb = THEMES[name]
    BRAND_RGB = rgb
    BRAND = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
    BANNER_COLOR = rgb
    _current_theme = name


def _brand_ansi(text: str, bold: bool = True) -> str:
    """Wrap text in a truecolor ANSI escape matching BRAND (for click prompts)."""
    r, g, b = BRAND_RGB
    prefix = ("\x1b[1m" if bold else "") + f"\x1b[38;2;{r};{g};{b}m"
    return f"{prefix}{text}\x1b[0m"

console = Console()
err_console = Console(stderr=True)

BANNER_ART = r"""
  mmm    mmmm  eeeeeee  sssssss  sssssss  yy   yy  ggggggg  ii  tttttttt
  mm mm mm mm  ee       ss       ss        yy yy   gg       ii     tt
  mm  mmm  mm  eeeee    sssssss  sssssss    yy     gg  ggg  ii     tt
  mm       mm  ee            ss       ss    yy     gg   gg  ii     tt
  mm       mm  eeeeeee  sssssss  sssssss    yy     ggggg    ii     tt
""".strip("\n")

# Banner fades from dim gray up to the brand ice-blue as the system "boots".
BANNER_COLOR = BRAND_RGB
BANNER_FADE_START = (70, 70, 70)

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
            (f"{self.phrase}  ", BRAND),
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


def _spinner(phrase: str | None = None) -> _CharSpinner:
    """Return the animated character spinner with a random witty phrase."""
    return _CharSpinner(phrase)


def _print_error(msg: str) -> None:
    err_console.print(f"[{ERROR}]error:[/] {msg}", highlight=False)


def _success(msg: str) -> None:
    console.print(f"[{SUCCESS}]✓[/] {msg}", highlight=False)


def _warn(msg: str) -> None:
    console.print(f"[{WARNING}]![/] {msg}", highlight=False)


def _field(label: str, value: Text | str) -> Text:
    """Build a 'label   value' line with a dim label and bright value."""
    line = Text()
    line.append(f"  {label:<9}", style=MUTED)
    line.append(value if isinstance(value, Text) else Text(value))
    return line


def _banner(rgb: tuple[int, int, int] | None = None) -> Text:
    """Render the whole banner in a single color."""
    r, g, b = rgb if rgb is not None else BANNER_COLOR
    return Text(BANNER_ART, style=f"bold rgb({r},{g},{b})")


_BANNER_WIDTH = max(len(line) for line in BANNER_ART.splitlines())


def _boot_frame(rgb: tuple[int, int, int], progress: float) -> Group:
    """Banner wrapped in a top/bottom progress bar that fills as it boots."""
    filled = round(_BANNER_WIDTH * progress)
    bar = Text()
    bar.append("=" * filled, style=f"bold {BRAND}")
    bar.append("=" * (_BANNER_WIDTH - filled), style=MUTED)
    return Group(Text("  ") + bar, _banner(rgb), Text("  ") + bar)


def _animate_banner() -> None:
    """Boot sequence: progress bars fill while the name fades in to ice-blue."""
    if not console.is_terminal:
        console.print(_boot_frame(BANNER_COLOR, 1.0))
        return
    steps = 24
    with Live(console=console, refresh_per_second=60, transient=False) as live:
        for i in range(steps + 1):
            t = i / steps
            rgb = tuple(
                round(a + (b - a) * t)
                for a, b in zip(BANNER_FADE_START, BANNER_COLOR)
            )
            live.update(_boot_frame(rgb, t))
            time.sleep(0.06)
        live.update(_boot_frame(BANNER_COLOR, 1.0))


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
    _animate_banner()
    console.print()

    if is_git_repo():
        status = get_repo_status()
        branch = Text.assemble(
            ("messygit", BRAND), ("  ⎇ ", MUTED), (status.branch or "detached", BRAND)
        )
        console.print(_field("repo", branch))
        console.print(_field("status", _status_summary(status)))
    else:
        console.print(_field("repo", Text("not a git repository", style=WARNING)))

    console.print(_field("api key", _api_key_status()))
    _m = current_model()
    console.print(
        _field("model", Text.assemble((_m.label, BRAND), (f"  {_model_pricing(_m)}", MUTED)))
    )
    console.print(_field("tokens", _usage_summary()))
    console.print(f"  {'─' * 60}", style=MUTED)
    console.print(
        f"  [{MUTED}]Type[/] [bold]help[/] [{MUTED}]for commands ·[/] "
        f"[bold]quit[/] [{MUTED}]to exit[/]"
    )
    console.print()


def _print_help() -> None:
    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column(style=f"bold {BRAND}", no_wrap=True)
    table.add_column(style="default")
    table.add_column(style=MUTED)
    for i, (group, commands) in enumerate(HELP_GROUPS):
        if i:
            table.add_row("", "", "")  # blank spacer between groups
        table.add_row(Text(group, style=f"bold {BRAND}"), "", "")
        for name, desc, usage in commands:
            table.add_row(f"  {name}", desc, usage)
    console.print(Panel(table, title="commands", border_style=MUTED, title_align="left"))


def _prompt_commit_action(message: str) -> None:
    """Ask [Y/n/e]: commit, cancel, or edit in $EDITOR."""
    current = message
    while True:
        console.print(
            Panel(current, title="proposed commit", border_style=BRAND, title_align="left")
        )
        choice = click.prompt(
            _brand_ansi("Commit with this message? [y/n/e]", bold=False),
            default="Y",
            show_default=False,
        ).strip().lower()

        if choice in ("", "y", "yes"):
            result = git_commit(current)
            if result.returncode != 0:
                if result.stderr:
                    err_console.print(result.stderr.strip())
                _print_error("git commit failed.")
                return
            summary = (result.stdout or "").strip().splitlines()
            _success("Committed" + (f" — {summary[0]}" if summary else ""))
            return

        if choice in ("n", "no"):
            _warn("Commit cancelled.")
            return

        if choice in ("e", "edit"):
            edited = click.edit(current)
            if edited is None:
                _warn("Editor exited without saving; message unchanged.")
                continue
            stripped = edited.strip()
            if not stripped:
                _warn("Empty message ignored; message unchanged.")
                continue
            current = stripped
            continue

        _warn("Please answer y (yes), n (no), or e (edit).")


def _handle_add(args: list[str]) -> None:
    if not args:
        _print_error("Usage: add <file> ... or add .")
        return
    result = git_add(args)
    if result.returncode != 0:
        _print_error(result.stderr.strip() if result.stderr else "git add failed.")
        return
    label = "everything" if args == ["."] else ", ".join(args)
    _success(f"Staged [{SUCCESS}]{label}[/]")


def _handle_push() -> None:
    with _spinner("pushing to remote"):
        result = git_push()
    if result.returncode != 0:
        _print_error(result.stderr.strip() if result.stderr else "git push failed.")
        return
    output = (result.stdout or result.stderr or "").strip()
    _success(output if output else "Pushed successfully.")


def _handle_outbox() -> None:
    if not is_git_repo():
        _print_error("Not a git repository.")
        return
    box = get_unpushed_commits()
    if box.upstream is None:
        _print_error(
            "No upstream branch set — push once with 'git push -u' to start tracking."
        )
        return
    if not box.commits:
        _success(f"Up to date with [{BRAND}]{box.upstream}[/] — nothing to push.")
        return

    n = len(box.commits)
    body = Text()
    body.append(
        f"{n} commit{'s' if n != 1 else ''} ahead of {box.upstream}\n\n", style=MUTED
    )
    for commit in box.commits:
        body.append(f"{commit.short_hash} ", style=BRAND)
        body.append(f"{commit.subject}\n", style="default")
    console.print(
        Panel(body, title="outbox", border_style=BRAND, title_align="left")
    )


def _handle_commit() -> None:
    diff = get_staged_diff()
    if not diff.strip():
        _warn("No staged changes found. Run 'add .' or 'add <file>' first.")
        return
    before = SESSION_USAGE.total
    try:
        with _spinner():
            message = generate_commit_message(diff)
    except (MissingApiKeyError, InvalidAnthropicCredentialsError, AnthropicInsufficientBalanceError) as e:
        _print_error(str(e))
        return
    _prompt_commit_action(message)
    _print_usage_delta(before)


def _handle_config(args: list[str]) -> None:
    if not args:
        _print_error("Usage: config <api-key>")
        return
    key = args[0]
    try:
        save_api_key(key)
    except ValueError as e:
        _print_error(str(e))
        return
    _success(f"API key saved [{MUTED}]({mask_api_key(key.strip())})[/]")


def _handle_show() -> None:
    env_set = ANTHROPIC_ENV_VAR in os.environ
    env_key = (os.environ.get(ANTHROPIC_ENV_VAR) or "").strip()
    if env_key:
        console.print(f"API key: [{SUCCESS}]{mask_api_key(env_key)}[/] [{MUTED}](from {ANTHROPIC_ENV_VAR})[/]")
        return
    file_key = load_api_key()
    if file_key:
        console.print(f"API key: [{SUCCESS}]{mask_api_key(file_key)}[/] [{MUTED}](from {CONFIG_FILE})[/]")
        return
    if env_set:
        _warn(
            f"{ANTHROPIC_ENV_VAR} is set but empty or whitespace-only, and no usable key "
            f"is stored in {CONFIG_FILE}. Unset the variable or run: config <key>"
        )
        return
    _warn("No API key found. Set ANTHROPIC_API_KEY or run: config <key>")


def _fmt_cost(amount: float) -> str:
    """Format a USD estimate: cents-precision normally, finer when tiny."""
    if amount > 0 and amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def _usage_summary() -> Text:
    """One-line session usage for the startup dashboard."""
    u = SESSION_USAGE
    if u.total == 0:
        return Text("0 used this session", style=MUTED)
    return Text.assemble(
        (f"{u.total:,}", SUCCESS),
        (" used this session  ", MUTED),
        (f"≈ {_fmt_cost(u.estimated_cost)}", MUTED),
    )


def _maybe_warn_high_usage() -> None:
    global _high_usage_warned
    if not _high_usage_warned and SESSION_USAGE.total >= HIGH_USAGE_TOKENS:
        _high_usage_warned = True
        _warn(
            f"High token usage this session ({SESSION_USAGE.total:,}). "
            f"Check or add credits: {BILLING_URL}"
        )


def _print_usage_delta(before_total: int) -> None:
    """After an API-using command, show how many tokens it cost."""
    delta = SESSION_USAGE.total - before_total
    if delta <= 0:
        return
    console.print(
        f"[{MUTED}]+{delta:,} tokens · {SESSION_USAGE.total:,} this session "
        f"· ≈ {_fmt_cost(SESSION_USAGE.estimated_cost)}[/]",
        highlight=False,
    )
    _maybe_warn_high_usage()


def _model_pricing(m) -> str:
    return f"${m.input_per_mtok:g} in · ${m.output_per_mtok:g} out / 1M"


def _print_model_list() -> None:
    current = resolve_model_key()
    console.print(
        f"[{MUTED}]Available models — usage:[/] [bold]model <name>[/]", highlight=False
    )
    for key, m in MODELS.items():
        is_current = key == current
        line = Text()
        line.append("  ● " if is_current else "    ", style=BRAND if is_current else MUTED)
        line.append(f"{key:<7}", style=("bold " + BRAND) if is_current else "default")
        line.append(m.label, style=BRAND if is_current else "default")
        line.append("  ")
        line.append(_model_pricing(m), style=MUTED)
        if is_current:
            line.append("  (current)", style=MUTED)
        console.print(line)


def _handle_model(args: list[str]) -> None:
    if not args:
        _print_model_list()
        return
    key = args[0].lower()
    if key not in MODELS:
        _print_error(f"Unknown model '{key}'. Run 'model' to see the options.")
        return
    target = MODELS[key]
    current = current_model()
    if key == resolve_model_key():
        _warn(f"Already using {target.label}.")
        return
    if target.input_per_mtok > current.input_per_mtok:
        _warn(
            f"{target.label} costs more than {current.label} "
            f"({_model_pricing(target)} vs {_model_pricing(current)}). "
            "Token usage will be billed at the higher rate."
        )
        if not click.confirm(_brand_ansi("Switch anyway?", bold=False), default=False):
            _warn("Model unchanged.")
            return
    save_model(key)
    console.print(
        Text.assemble(
            "Model set to ", (target.label, BRAND), (f"  {_model_pricing(target)}", MUTED)
        )
    )


def _handle_tokens() -> None:
    u = SESSION_USAGE
    body = Text()
    body.append("used     ", style=MUTED)
    body.append(f"{u.total:,} tokens\n", style=SUCCESS if u.total else MUTED)
    body.append("         ", style=MUTED)
    body.append(f"{u.input:,} in · {u.output:,} out\n", style=MUTED)
    body.append("requests ", style=MUTED)
    body.append(f"{u.requests}\n", style="default")
    body.append("est cost ", style=MUTED)
    body.append(f"≈ {_fmt_cost(u.estimated_cost)}\n\n", style=SUCCESS if u.total else MUTED)
    body.append(
        f"Note: cost is a rough estimate at {current_model().label} rates; the\n", style=MUTED
    )
    body.append("API can't report credits — usage is this session only.", style=MUTED)
    console.print(
        Panel(body, title="token usage", border_style=BRAND, title_align="left")
    )
    console.print(f"[{MUTED}]Opening billing console:[/] {BILLING_URL}")
    try:
        webbrowser.open(BILLING_URL)
    except Exception:
        pass


def _swatch(rgb: tuple[int, int, int]) -> Text:
    r, g, b = rgb
    return Text("███", style=f"rgb({r},{g},{b})")


def _print_theme_list() -> None:
    console.print(
        f"[{MUTED}]Available themes — usage:[/] [bold]theme <name>[/]", highlight=False
    )
    for name, rgb in THEMES.items():
        current = name == _current_theme
        line = Text()
        line.append("  ● " if current else "    ", style=BRAND if current else MUTED)
        line.append_text(_swatch(rgb))
        line.append("  ")
        line.append(name, style="bold" if current else "default")
        if current:
            line.append("  (current)", style=MUTED)
        console.print(line)


def _handle_theme(args: list[str]) -> None:
    if not args:
        _print_theme_list()
        return
    name = args[0].lower()
    if name not in THEMES:
        _print_error(f"Unknown theme '{name}'. Run 'theme' to see the options.")
        return
    _apply_theme(name)
    save_theme(name)
    console.print(Text.assemble("Theme set to ", (name, BRAND), "  ") + _swatch(THEMES[name]))


TODO_SEED = "# messygit todo\n\n- \n"


def _handle_todo() -> None:
    """Open the persisted todo file in $EDITOR; save whatever comes back."""
    current = load_todo()
    seed = current if current.strip() else TODO_SEED
    edited = click.edit(seed)
    if edited is None:
        _warn("Editor exited without saving; todo unchanged.")
        return
    save_todo(edited)
    open_items = sum(
        1 for line in edited.splitlines() if line.lstrip().startswith(("- ", "* "))
        and line.strip() not in ("-", "*")
    )
    _success(f"Todo saved [{MUTED}]({open_items} item{'s' if open_items != 1 else ''})[/]")


def _handle_suggestion() -> None:
    agent = Agent(
        name="suggestion_agent",
        system_prompt=SUGGESTION_SYSTEM_PROMPT,
        max_iterations=8,
        tools=[run_git_tool, read_file_tool, list_directory_tool],
    )
    before = SESSION_USAGE.total
    try:
        with _spinner():
            result = agent.run("What should the next steps for my project be? Let's limit it to 3-5 steps")
    except (MissingApiKeyError, InvalidAnthropicCredentialsError, AnthropicInsufficientBalanceError) as e:
        _print_error(str(e))
        return
    console.print(
        Panel(Markdown(result), title="suggested next steps", border_style=BRAND, title_align="left")
    )
    _print_usage_delta(before)

def _handle_changelog() -> None:
    if not run_git_tool.function(["tag"]).strip():
        _print_error(
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
        with _spinner():
            result = agent.run("What are the latest changes to my project? Add to or create the CHANGELOG.md markdown file.")
    except (MissingApiKeyError, InvalidAnthropicCredentialsError, AnthropicInsufficientBalanceError) as e:
        _print_error(str(e))
        return
    console.print(
        Panel(Markdown(result), title="changelog", border_style=BRAND, title_align="left")
    )
    _print_usage_delta(before)


COMMANDS = {
    "add": _handle_add,
    "commit": lambda args: _handle_commit(),
    "push": lambda args: _handle_push(),
    "outbox": lambda args: _handle_outbox(),
    "config": _handle_config,
    "show": lambda args: _handle_show(),
    "suggest": lambda args: _handle_suggestion(),
    "changelog": lambda args: _handle_changelog(),
    "tokens": lambda args: _handle_tokens(),
    "model": _handle_model,
    "todo": lambda args: _handle_todo(),
    "theme": _handle_theme,
    "help": lambda args: _print_help(),
}


def _load_saved_theme() -> None:
    name = load_theme()
    _apply_theme(name if name in THEMES else DEFAULT_THEME)


def _build_prompt() -> str:
    branch = get_current_branch() if is_git_repo() else None
    prompt = _brand_ansi("messygit")
    if branch:
        prompt += click.style(f" ({branch})", fg="bright_black")
    prompt += _brand_ansi(" ❯ ")
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
            console.print(f"[{BRAND}]Bye![/]")
            break

        if not raw:
            continue

        try:
            parts = shlex.split(raw)
        except ValueError:
            parts = raw.split()

        cmd, args = parts[0].lower(), parts[1:]

        if cmd in ("quit", "exit"):
            console.print(f"[{BRAND}]Bye![/]")
            break

        handler = COMMANDS.get(cmd)
        if handler is None:
            _print_error(f"Unknown command '{cmd}'. Type 'help' for a list of commands.")
            continue

        handler(args)
        console.print()


@click.command()
def main():
    """Messy Git — interactive CLI for clean commits from messy code."""
    _repl()


if __name__ == "__main__":
    main()
