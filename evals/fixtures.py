"""Throwaway git repos for the agentic evals (`suggest`, `changelog`).

The commit eval feeds the model a diff string and reads back one line. The
agentic commands are different: they take a *repo state + task* and act on it
with tools (`run_git`, `read_file`, `write_file`, …), all of which operate on
the current working directory's git repo. So to evaluate them we hand the agent
a real — but disposable — repo and run it there.

`build_repo` materializes a repo from a list of `Commit`s (deterministic author
dates so changelog dates are stable), and `run_agent_in_repo` chdirs into it,
runs the agent, and restores the cwd. Everything lives under a tempdir the
caller removes when done.
"""

import os
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from messygit.agent.agent import Agent


@dataclass
class Commit:
    """One commit to lay down in a fixture repo, in order."""
    message: str
    files: dict[str, str]           # path (repo-relative) -> file content at this commit
    tag: str | None = None          # annotated? no — a lightweight tag on this commit
    date: str = "2026-01-01T12:00:00"  # author+committer date (stable changelog dates)
    deletes: list[str] = field(default_factory=list)  # paths to `git rm` in this commit


def _run(args: list[str], cwd: Path, env: dict | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_repo(commits: list[Commit]) -> Path:
    """Create a temp git repo, apply `commits` in order, return its path.

    Caller owns the directory and must `shutil.rmtree` it. Git identity and
    dates are pinned so tag dates in changelog output are reproducible.
    """
    root = Path(tempfile.mkdtemp(prefix="messygit_eval_"))
    _run(["git", "init", "-q", "-b", "main"], root)
    _run(["git", "config", "user.name", "Eval Bot"], root)
    _run(["git", "config", "user.email", "eval@example.com"], root)
    _run(["git", "config", "commit.gpgsign", "false"], root)

    for c in commits:
        for path in c.deletes:
            _run(["git", "rm", "-q", path], root)
        for rel, content in c.files.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            _run(["git", "add", rel], root)
        env = {**os.environ, "GIT_AUTHOR_DATE": c.date, "GIT_COMMITTER_DATE": c.date}
        _run(["git", "commit", "-q", "-m", c.message], root, env=env)
        if c.tag:
            _run(["git", "tag", c.tag], root, env=env)
    return root


@contextmanager
def in_dir(path: Path):
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def run_agent_in_repo(repo: Path, agent: Agent, prompt: str) -> str:
    """Run `agent` with its cwd set to `repo`; leave `agent.steps` populated."""
    with in_dir(repo):
        return agent.run(prompt)


def hit_iteration_limit(output: str) -> bool:
    """The Agent prefixes a ⚠️ warning when it stops before finishing."""
    return output.lstrip().startswith("⚠️")


def used_git(steps, *, subcommand: str) -> bool:
    """True if any recorded step called run_git with args[0] == subcommand."""
    for s in steps:
        if s.kind == "tool" and s.name == "run_git":
            args = s.tool_input.get("args") or []
            if args and args[0] == subcommand:
                return True
    return False


def used_tool(steps, name: str) -> bool:
    return any(s.kind == "tool" and s.name == name for s in steps)
