"""account group: config, show, model, tokens."""

import os
import webbrowser

import click
from rich.panel import Panel
from rich.text import Text

from ..config import (
    ANTHROPIC_ENV_VAR,
    CONFIG_FILE,
    load_api_key,
    mask_api_key,
    save_api_key,
    save_model,
)
from ..models import MODELS, current_model, resolve_model_key
from ..usage import SESSION_USAGE, BILLING_URL
from ..ui import theme
from ..ui.output import console, print_error, success, warn
from ..ui.theme import MUTED, SUCCESS
from .usage import fmt_cost, model_pricing


def handle_config(args: list[str]) -> None:
    if not args:
        print_error("Usage: config <api-key>")
        return
    key = args[0]
    try:
        save_api_key(key)
    except ValueError as e:
        print_error(str(e))
        return
    success(f"API key saved [{MUTED}]({mask_api_key(key.strip())})[/]")


def handle_show() -> None:
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
        warn(
            f"{ANTHROPIC_ENV_VAR} is set but empty or whitespace-only, and no usable key "
            f"is stored in {CONFIG_FILE}. Unset the variable or run: config <key>"
        )
        return
    warn("No API key found. Set ANTHROPIC_API_KEY or run: config <key>")


def _print_model_list() -> None:
    current = resolve_model_key()
    console.print(
        f"[{MUTED}]Available models — usage:[/] [bold]model <name>[/]", highlight=False
    )
    for key, m in MODELS.items():
        is_current = key == current
        line = Text()
        line.append("  ● " if is_current else "    ", style=theme.BRAND if is_current else MUTED)
        line.append(f"{key:<7}", style=("bold " + theme.BRAND) if is_current else "default")
        line.append(m.label, style=theme.BRAND if is_current else "default")
        line.append("  ")
        line.append(model_pricing(m), style=MUTED)
        if is_current:
            line.append("  (current)", style=MUTED)
        console.print(line)


def handle_model(args: list[str]) -> None:
    if not args:
        _print_model_list()
        return
    key = args[0].lower()
    if key not in MODELS:
        print_error(f"Unknown model '{key}'. Run 'model' to see the options.")
        return
    target = MODELS[key]
    current = current_model()
    if key == resolve_model_key():
        warn(f"Already using {target.label}.")
        return
    if target.input_per_mtok > current.input_per_mtok:
        warn(
            f"{target.label} costs more than {current.label} "
            f"({model_pricing(target)} vs {model_pricing(current)}). "
            "Token usage will be billed at the higher rate."
        )
        if not click.confirm(theme.brand_ansi("Switch anyway?", bold=False), default=False):
            warn("Model unchanged.")
            return
    save_model(key)
    console.print(
        Text.assemble(
            "Model set to ", (target.label, theme.BRAND), (f"  {model_pricing(target)}", MUTED)
        )
    )


def handle_tokens() -> None:
    u = SESSION_USAGE
    body = Text()
    body.append("used     ", style=MUTED)
    body.append(f"{u.total:,} tokens\n", style=SUCCESS if u.total else MUTED)
    body.append("         ", style=MUTED)
    body.append(f"{u.input:,} in · {u.output:,} out\n", style=MUTED)
    body.append("requests ", style=MUTED)
    body.append(f"{u.requests}\n", style="default")
    body.append("est cost ", style=MUTED)
    body.append(f"≈ {fmt_cost(u.estimated_cost)}\n\n", style=SUCCESS if u.total else MUTED)
    body.append(
        f"Note: cost is a rough estimate at {current_model().label} rates; the\n", style=MUTED
    )
    body.append("API can't report credits — usage is this session only.", style=MUTED)
    console.print(
        Panel(body, title="token usage", border_style=theme.BRAND, title_align="left")
    )
    console.print(f"[{MUTED}]Opening billing console:[/] {BILLING_URL}")
    try:
        webbrowser.open(BILLING_URL)
    except Exception:
        pass
