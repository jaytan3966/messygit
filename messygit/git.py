from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from subprocess import CompletedProcess

TOKEN_CHAR_ESTIMATE = 4
MAX_CONTEXT_TOKENS = 60_000
MAX_CONTEXT_CHARS = MAX_CONTEXT_TOKENS * TOKEN_CHAR_ESTIMATE

NOISE_PATTERNS: tuple[str, ...] = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Pipfile.lock",
    "poetry.lock",
    "Cargo.lock",
    "composer.lock",
    "Gemfile.lock",
    "go.sum",
    ".DS_Store",
    "Thumbs.db",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.bundle.js",
    "*.chunk.js",
    "*.pb.go",
    "*.generated.*",
    "*.snap",
)

_DIFF_FILE_HEADER = re.compile(r"^diff --git a/.+ b/(.+)$")
_HUNK_HEADER = re.compile(r"^@@\s")


def _is_noise_file(path: str) -> bool:
    """Return True if path matches a common build/generated pattern we always skip."""
    from fnmatch import fnmatch

    name = path.rsplit("/", 1)[-1]
    for pattern in NOISE_PATTERNS:
        if fnmatch(name, pattern) or fnmatch(path, pattern):
            return True
    return False


def _parse_compact_diff(raw_diff: str) -> str:
    """Parse a -U0 unified diff into a compact per-file changed-lines format.

    Output looks like:

        === path/to/file.py ===
        + added line
        - removed line
        === another/file.ts ===
        + another addition
    """
    lines = raw_diff.splitlines()
    out: list[str] = []
    current_file: str | None = None
    skip_file = False

    for line in lines:
        header_match = _DIFF_FILE_HEADER.match(line)
        if header_match:
            current_file = header_match.group(1)
            skip_file = _is_noise_file(current_file)
            if not skip_file:
                out.append(f"\n=== {current_file} ===")
            continue

        if skip_file:
            continue

        if _HUNK_HEADER.match(line):
            continue

        if line.startswith("+") and not line.startswith("+++"):
            out.append(line)
        elif line.startswith("-") and not line.startswith("---"):
            out.append(line)

    return "\n".join(out).strip()


@dataclass
class FileStat:
    path: str
    added: int
    removed: int

    @property
    def total_changed(self) -> int:
        return self.added + self.removed


_STAT_LINE_RE = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+(.+)$"
)


def _get_raw_staged_diff() -> str:
    result = subprocess.run(
        ["git", "diff", "--cached", "-U0"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def _get_staged_numstat() -> list[FileStat]:
    """Run git diff --cached --numstat and parse per-file added/removed counts."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--numstat"],
        capture_output=True,
        text=True,
    )
    stats: list[FileStat] = []
    for line in result.stdout.strip().splitlines():
        match = _STAT_LINE_RE.match(line)
        if not match:
            continue
        added_str, removed_str, path = match.groups()
        if added_str == "-" or removed_str == "-":
            continue
        path = path.strip()
        if _is_noise_file(path):
            continue
        stats.append(FileStat(path=path, added=int(added_str), removed=int(removed_str)))
    return stats


def _get_stat_summary() -> str:
    """Run git diff --cached --stat and return the summary string."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--stat"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _compact_diff_for_files(paths: set[str], raw_diff: str) -> str:
    """Extract compact changed lines only for the given file paths."""
    raw_lines = raw_diff.splitlines()
    collected: list[str] = []
    active_path: str | None = None
    include = False

    for raw_line in raw_lines:
        file_match = _DIFF_FILE_HEADER.match(raw_line)
        if file_match:
            active_path = file_match.group(1)
            include = active_path in paths
            if include:
                collected.append(f"\n=== {active_path} ===")
            continue

        if not include:
            continue

        if _HUNK_HEADER.match(raw_line):
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            collected.append(raw_line)
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            collected.append(raw_line)

    return "\n".join(collected).strip()


def build_staged_context() -> str:
    """Build the context string sent to the LLM.

    If the full compact diff fits within the token budget, return it as-is.
    Otherwise, fall back to:
      - The full --stat summary (file list with bar chart)
      - Full compact diff of only the most-changed files that fit the budget
    """
    raw_diff = _get_raw_staged_diff()
    full_compact = _parse_compact_diff(raw_diff)

    if len(full_compact) <= MAX_CONTEXT_CHARS:
        return full_compact

    stat_summary = _get_stat_summary()
    file_stats = _get_staged_numstat()
    file_stats.sort(key=lambda fs: fs.total_changed, reverse=True)

    header = (
        "This diff was too large to include in full. "
        "Below is the complete --stat summary followed by the full changed lines "
        "of the most-changed files.\n\n"
        f"--- stat summary ---\n{stat_summary}\n\n"
        "--- most-changed files (full changed lines) ---\n"
    )

    budget = MAX_CONTEXT_CHARS - len(header)
    selected_paths: set[str] = set()
    for fs in file_stats:
        file_diff = _compact_diff_for_files({fs.path}, raw_diff)
        if len(file_diff) > budget:
            continue
        selected_paths.add(fs.path)
        budget -= len(file_diff)

    if not selected_paths:
        return header.strip()

    top_files_diff = _compact_diff_for_files(selected_paths, raw_diff)
    return f"{header}{top_files_diff}"


def get_staged_diff() -> str:
    """Return a compact, changed-lines-only representation of staged changes."""
    return build_staged_context()


def get_staged_files() -> list[str]:
    """Return list of staged file paths, excluding noise files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    files = result.stdout.strip()
    if not files:
        return []
    return [f for f in files.split("\n") if not _is_noise_file(f)]


def git_commit(message: str) -> CompletedProcess[str]:
    return subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
    )