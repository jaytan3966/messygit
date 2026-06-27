"""Model-output evals for messygit.

Unlike the unit tests in `tests/` (which simulate the model and run offline),
evals call the REAL model and score its output. They cost tokens and need an
ANTHROPIC_API_KEY, so they are NOT part of the `pytest` run — launch them
explicitly with `python -m evals.commit_eval`.

`commit_eval` is the worked reference: a graded dataset, programmatic scorers,
an LLM-as-judge, and an aggregated scoreboard — the same shape you can reuse to
evaluate the agentic `suggest`/`changelog` commands.
"""
