"""Token-usage and cost display helpers (the SESSION_USAGE *tracker* lives in
``messygit.usage``; this module is just the rendering of it)."""

from rich.text import Text

from ..models import current_model
from ..usage import SESSION_USAGE, BILLING_URL
from ..ui.output import console, warn
from ..ui.theme import MUTED, SUCCESS

# Once a session crosses this many tokens, surface a one-time heads-up with the
# billing link (the API can't report remaining credits, so this is usage-based).
HIGH_USAGE_TOKENS = 100_000
_high_usage_warned = False


def fmt_cost(amount: float) -> str:
    """Format a USD estimate: cents-precision normally, finer when tiny."""
    if amount > 0 and amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def model_pricing(m) -> str:
    return f"${m.input_per_mtok:g} in · ${m.output_per_mtok:g} out / 1M"


def usage_summary() -> Text:
    """One-line session usage for the startup dashboard."""
    u = SESSION_USAGE
    if u.total == 0:
        return Text("0 used this session", style=MUTED)
    return Text.assemble(
        (f"{u.total:,}", SUCCESS),
        (" used this session  ", MUTED),
        (f"≈ {fmt_cost(u.estimated_cost)}", MUTED),
    )


def maybe_warn_high_usage() -> None:
    global _high_usage_warned
    if not _high_usage_warned and SESSION_USAGE.total >= HIGH_USAGE_TOKENS:
        _high_usage_warned = True
        warn(
            f"High token usage this session ({SESSION_USAGE.total:,}). "
            f"Check or add credits: {BILLING_URL}"
        )


def print_usage_delta(before_total: int) -> None:
    """After an API-using command, show how many tokens it cost."""
    delta = SESSION_USAGE.total - before_total
    if delta <= 0:
        return
    console.print(
        f"[{MUTED}]+{delta:,} tokens · {SESSION_USAGE.total:,} this session "
        f"· ≈ {fmt_cost(SESSION_USAGE.estimated_cost)}[/]",
        highlight=False,
    )
    maybe_warn_high_usage()
