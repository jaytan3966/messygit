"""Generic eval harness — shared by every eval, knows nothing about commits.

An eval supplies three things and calls `run_eval` + `write_report`:

    cases     : a list of case objects (each must have a `.name` attribute)
    generate  : (case) -> str            # run the system under test, return its output
    scorers   : list of (case, output) -> ScoreResult   # the bespoke criteria

Optionally a `judge` (use `make_llm_judge`) for properties best graded by a model.

The harness handles: running each case, collecting scores, catching generation
errors so one bad case doesn't sink the run, aggregating the pass rate, and
writing a markdown report. That's the part you reuse verbatim across evals.

Reports are written to `evals/results/<eval_name>/<timestamp>.md` — one file per
run, grouped by function type, so you can track iterations over time.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from anthropic import Anthropic
from rich.console import Console

from messygit.config import resolve_api_key
from messygit.models import current_model

console = Console()

# Run reports land here, one markdown file per run, in an eval-named subfolder.
RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Judge model. Defaults to Haiku (cheap); override with EVAL_JUDGE_MODEL — a
# stronger judge (e.g. claude-sonnet-4-6) gives more reliable semantic grading.
DEFAULT_JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "claude-haiku-4-5")
# Default bar: fraction of applicable checks that must pass for the suite to pass.
PASS_BAR = float(os.environ.get("EVAL_PASS_BAR", "0.9"))


@dataclass
class ScoreResult:
    scorer: str
    passed: bool | None        # None == not applicable to this case
    detail: str = ""
    score: float | None = None  # for graded scorers (e.g. a 1-5 judge); else None


@dataclass
class CaseResult:
    case: object               # any object with a `.name`
    output: str
    results: list[ScoreResult]

    @property
    def applicable(self) -> list[ScoreResult]:
        return [r for r in self.results if r.passed is not None]

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.applicable)


# Type aliases for the contract an eval implements.
Generate = Callable[[object], str]
Scorer = Callable[[object, str], ScoreResult]
Judge = Callable[[object, str, Anthropic, str], ScoreResult]


def run_eval(
    cases,
    generate: Generate,
    scorers: list[Scorer],
    judge: Judge | None = None,
    judge_model: str = DEFAULT_JUDGE_MODEL,
) -> list[CaseResult]:
    """Run every case through `generate` then all `scorers` (+ optional judge)."""
    client = Anthropic(api_key=resolve_api_key()) if judge is not None else None
    results: list[CaseResult] = []
    for case in cases:
        try:
            output = generate(case)
        except Exception as e:  # one failed generation shouldn't kill the run
            results.append(CaseResult(case, "", [ScoreResult("generation", False, str(e))]))
            continue
        scored = [s(case, output) for s in scorers]
        if judge is not None:
            scored.append(judge(case, output, client, judge_model))
        results.append(CaseResult(case, output, scored))
    return results


def make_llm_judge(
    system_prompt: str,
    render_user: Callable[[object, str], str],
    *,
    name: str = "llm_judge",
    threshold: float = 4,
) -> Judge:
    """Build a reusable LLM-as-judge scorer.

    `render_user(case, output)` formats the judge's user message; the judge must
    reply with JSON {"score": <number>, "reasoning": "..."}. Pass if score >=
    threshold. Errors return passed=None so a flaky judge never fails a case.
    """
    def judge(case, output, client: Anthropic, judge_model: str) -> ScoreResult:
        try:
            resp = client.messages.create(
                model=judge_model,
                max_tokens=256,
                system=system_prompt,
                messages=[{"role": "user", "content": render_user(case, output)}],
            )
            raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)
            score = float(data["score"])
            reasoning = str(data.get("reasoning", "")).strip()
            return ScoreResult(name, score >= threshold, reasoning, score=score)
        except Exception as e:
            return ScoreResult(name, None, f"judge error: {e}")

    return judge


def _one_line(text: str, limit: int = 60) -> str:
    text = " ".join(text.strip().splitlines())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _cell(text: str, limit: int = 80) -> str:
    """Sanitize a string for a markdown table cell (no pipes/newlines)."""
    return _one_line(text, limit).replace("|", "\\|")


def _inline(text: str) -> str:
    """Collapse whitespace/newlines so free text fits one markdown bullet (full
    length kept — only newlines are flattened)."""
    return " ".join(text.split())


def _markdown(
    case_results: list[CaseResult],
    *,
    eval_name: str,
    judge_model: str,
    pass_bar: float,
    judge_threshold: float,
    output_header: str,
    timestamp: str,
) -> tuple[str, float]:
    """Build the markdown report. Returns (markdown, format_pass_rate)."""
    fmt_total = fmt_passed = 0
    judge_scores: list[float] = []
    judge_met = 0
    rows: list[str] = []
    details: list[str] = []

    for cr in case_results:
        fails, judge_cell, case_detail = [], "—", []
        case_fmt_total = case_fmt_passed = 0
        for r in cr.results:
            if r.passed is None:
                continue
            if r.score is not None:                       # the judge
                judge_scores.append(r.score)
                judge_met += int(bool(r.passed))
                judge_cell = f"{r.score:.0f}/5 {'✓' if r.passed else '✗'}"
                if r.detail:
                    case_detail.append(f"- judge {r.score:.0f}/5: {_inline(r.detail)}")
                continue
            fmt_total += 1
            case_fmt_total += 1
            if r.passed:
                fmt_passed += 1
                case_fmt_passed += 1
            else:
                fails.append(r.scorer)
                case_detail.append(f"- ✗ **{r.scorer}**{f' — {_inline(r.detail)}' if r.detail else ''}")
        fmt_cell = (
            f"✓ {case_fmt_passed}/{case_fmt_total}"
            if not fails
            else f"✗ {case_fmt_passed}/{case_fmt_total} ({', '.join(fails)})"
        )
        rows.append(f"| {cr.case.name} | `{_cell(cr.output)}` | {fmt_cell} | {judge_cell} |")
        if case_detail:
            details.append(f"### {cr.case.name}\n" + "\n".join(case_detail))

    fmt_rate = fmt_passed / fmt_total if fmt_total else 0.0
    gate = "✅" if fmt_rate >= pass_bar else "❌"
    judge_line = ""
    if judge_scores:
        avg = sum(judge_scores) / len(judge_scores)
        judge_line = f"- **Judge:** avg {avg:.1f}/5 · {judge_met}/{len(judge_scores)} cases ≥ {judge_threshold:.0f}\n"

    md = (
        f"# {eval_name} eval — {timestamp}\n\n"
        f"- **Model under test:** {current_model().label}\n"
        f"- **Judge model:** {judge_model}\n"
        f"- **Format checks:** {fmt_passed}/{fmt_total} ({fmt_rate:.0%}) — bar {pass_bar:.0%} {gate}\n"
        f"{judge_line}"
        f"\n## Results\n\n"
        f"| Case | {output_header} | Format | Judge (≥{judge_threshold:.0f}) |\n"
        f"|------|{'-' * (len(output_header) + 2)}|--------|-------|\n"
        + "\n".join(rows) + "\n"
    )
    if details:
        md += "\n## Details\n\n" + "\n\n".join(details) + "\n"
    return md, fmt_rate


def write_report(
    case_results: list[CaseResult],
    *,
    eval_name: str,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    pass_bar: float = PASS_BAR,
    judge_threshold: float = 4,
    output_header: str = "output",
) -> float:
    """Write a markdown report for this run and return the format-check pass rate.

    The two axes are reported separately because they answer different questions:
    the deterministic checks are pass/fail ("is it well-formed?"), while the judge
    is a graded score ("is it semantically good?"). The returned value — and the
    exit gate — is the deterministic pass rate; the judge is reported beside it.

    One file is written per run to results/<eval_name>/<timestamp>.md.
    """
    now = datetime.now()
    md, fmt_rate = _markdown(
        case_results,
        eval_name=eval_name,
        judge_model=judge_model,
        pass_bar=pass_bar,
        judge_threshold=judge_threshold,
        output_header=output_header,
        timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
    )
    out_dir = RESULTS_DIR / eval_name
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{now.strftime('%Y-%m-%d_%H-%M-%S')}.md"
    path.write_text(md)
    console.print(f"[green]✓[/] results written to [bold]{path}[/]")
    return fmt_rate
