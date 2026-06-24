"""The `trace` command: expand what the last agent run actually did.

Agent runs only show a spinner + final result by default. Each run's step trace
is stashed here silently; `trace` renders it on demand."""

from rich.panel import Panel
from rich.text import Text

from ..agent.agent import TraceStep
from ..ui import theme
from ..ui.output import console, warn
from ..ui.theme import ERROR, MUTED, SUCCESS

_RESULT_LIMIT = 400  # chars of tool output to show per step

# Last agent run: (human label, list[TraceStep]). None until something runs.
_last: tuple[str, list[TraceStep]] | None = None


def record_trace(label: str, steps: list[TraceStep]) -> None:
    """Stash the steps of the run that just finished (called by agent commands)."""
    global _last
    _last = (label, list(steps))


def _summarize_input(tool_input: dict) -> str:
    """Compact one-line view of a tool call's arguments."""
    parts = []
    for key, value in tool_input.items():
        if isinstance(value, list):
            shown = " ".join(str(v) for v in value)
        else:
            shown = str(value).replace("\n", "⏎")
        if len(shown) > 60:
            shown = shown[:57] + "…"
        parts.append(shown)
    return ", ".join(parts)


def _result_line(result: str) -> tuple[str, str]:
    """First line of a tool result (truncated) plus a dim '(+N more lines)' note.

    Returns plain strings — tool output is arbitrary text (diffs, logs) and must
    NOT be parsed as rich markup.
    """
    result = result.rstrip()
    if not result:
        return "(no output)", ""
    lines = result.splitlines()
    first = lines[0]
    if len(first) > _RESULT_LIMIT:
        first = first[:_RESULT_LIMIT].rstrip() + " …"
    extra = len(lines) - 1
    note = f"(+{extra} more line{'s' if extra != 1 else ''})" if extra > 0 else ""
    return first, note


def _format_text_step(step: TraceStep) -> Text:
    """The model's narration line."""
    return Text(step.text, style=MUTED)


def _format_tool_step(step: TraceStep, n: int) -> Text:
    """One numbered tool call: 'N. name  args' over a '└ result' line."""
    marker = ERROR if step.is_error else theme.BRAND
    out = Text()
    out.append(f"{n}. ", style=MUTED)
    out.append(step.name, style=f"bold {marker}")
    args = _summarize_input(step.tool_input)
    if args:
        out.append(f"  {args}", style="default")
    out.append("\n")
    main, note = _result_line(step.result)
    out.append("   └ ", style=MUTED)
    out.append(main, style=ERROR if step.is_error else SUCCESS)
    if note:
        out.append(f"  {note}", style=MUTED)
    return out


def live_reporter():
    """Return an on_step callback that prints each step as it happens.

    Used by verbose mode in place of the spinner: tool calls are numbered as
    they stream in.
    """
    counter = {"n": 0}

    def report(step: TraceStep) -> None:
        if step.kind == "text":
            console.print(_format_text_step(step))
        else:
            counter["n"] += 1
            console.print(_format_tool_step(step, counter["n"]))

    return report


def handle_trace() -> None:
    if not _last or not _last[1]:
        warn("No agent run to trace yet. Run 'suggest' or 'changelog' first.")
        return
    label, steps = _last
    blocks: list[Text] = []
    n = 0
    for step in steps:
        if step.kind == "text":
            blocks.append(_format_text_step(step))
        else:
            n += 1
            blocks.append(_format_tool_step(step, n))
    body = Text("\n\n").join(blocks)

    title = f"trace · {label} · {n} tool call{'s' if n != 1 else ''}"
    console.print(Panel(body, title=title, border_style=theme.BRAND, title_align="left"))
