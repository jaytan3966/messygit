# Evals

Evals measure the **quality of real model output** — distinct from the unit
tests in `tests/`, which simulate the model and run offline. Evals call the live
API, so they cost tokens and need an `ANTHROPIC_API_KEY`. They are intentionally
**not** collected by `pytest`.

## Run it

```bash
export ANTHROPIC_API_KEY=sk-ant-...     # or: messygit > config <key>
python -m evals.commit_eval
```

Each run writes a markdown report to `evals/results/<eval>/<timestamp>.md`
(one file per run, grouped by eval) — the terminal only prints the file path.
Exit code is `0` if the format-check pass rate ≥ `EVAL_PASS_BAR` (default `0.90`),
else `1` — so it can gate a CI job.

Env knobs:


| Var                | Default            | Meaning                                                                                                     |
| ------------------ | ------------------ | ----------------------------------------------------------------------------------------------------------- |
| `EVAL_JUDGE_MODEL` | `claude-haiku-4-5` | Model used for LLM-as-judge scoring (set a stronger one like `claude-sonnet-4-6` for more reliable grading) |
| `EVAL_PASS_BAR`    | `0.9`              | Fraction of applicable checks that must pass                                                                |


The model *under test* is whatever `model` is configured in messygit (default
Haiku) — switch it with `model <name>` to compare models on the same dataset.

## How it's built


| File             | Role                                                                                                                                                                    |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `core.py`        | The **generic harness**, shared by every eval: `run_eval`, `render`, the `ScoreResult`/`CaseResult` types, and `make_llm_judge`. Knows nothing about any specific eval. |
| `commit_eval.py` | **One self-contained eval**: the `CommitCase` dataset, the bespoke scorers, `generate()`, the judge rubric, and `main()`. The reference shape to copy.                  |


## Adding a new eval — just write one file

Create `evals/<name>_eval.py` with four things and let `core` do the rest:

```python
from .core import run_eval, write_report, make_llm_judge, ScoreResult, PASS_BAR

CASES = [...]                              # 1. objects with a `.name`
def generate(case) -> str: ...            # 2. run the thing under test
SCORERS = [my_scorer, ...]                # 3. (case, output) -> ScoreResult
judge = make_llm_judge(system, render_user)  # 4. optional

def main():
    results = run_eval(CASES, generate, SCORERS, judge=judge)
    rate = write_report(results, eval_name="<name>")   # writes results/<name>/<ts>.md
    return 0 if rate >= PASS_BAR else 1
```

The harness (running cases, catching generation errors, aggregating, the
scoreboard) is reused as-is. Only the dataset, `generate`, and scorers are
bespoke — which is inherent: each eval defines its own "what good looks like".

## Adapting this to the agentic evals (`suggest` / `changelog`)

Same one-file shape; only two things grow:

1. **Input/output.** Instead of a diff → subject line, an agentic case is a
  *repo state + task* → the agent's effect (final text, files written, and the
   `TraceStep` list the agent already records on `agent.steps`). Run the agent in
   a throwaway git repo (see how `tests/` build temp repos) so file writes are
   safe to inspect and discard.
2. **Scorers get richer.** Beyond output-quality scorers, evaluate the *process*
  using the trace:
  - did it call the expected tools (e.g. `changelog` should `git log` a tag
  range and `git show` at least one commit)?
  - did it stay within `max_iterations` / a tool-call budget?
  - did it avoid hallucinated numbers (assert no unverified figures appear) —
  the exact failure the changelog prompt guardrail targets?
  - did the written `CHANGELOG.md` parse, and prepend rather than clobber?

Keep deterministic scorers first (cheap, sharp), and reserve the LLM judge for  
the genuinely subjective properties. Make the judge return structured JSON and  
give it a rubric, as `scorers.llm_judge` does.

