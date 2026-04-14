import re
import subprocess
from subprocess import CompletedProcess

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


def get_staged_diff() -> str:
    """Return a compact, changed-lines-only representation of staged changes."""
    result = subprocess.run(
        ["git", "diff", "--cached", "-U0"],
        capture_output=True,
        text=True,
    )
    return _parse_compact_diff(result.stdout)


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