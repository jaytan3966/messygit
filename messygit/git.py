import subprocess
from subprocess import CompletedProcess


def get_staged_diff():
    result = subprocess.run(
        ["git", "diff", "--staged"],
        capture_output=True,
        text=True
    )
    return result.stdout
##I LOVE PENIS
def get_staged_files():
    result = subprocess.run(
        ["git", "diff", "--staged", "--name-only"],
        capture_output=True,
        text=True
    )
    files = result.stdout.strip()
    if not files:
        return []
    return files.split("\n")


def git_commit(message: str) -> CompletedProcess[str]:
    """Create a commit with the given message (subject; body supported if message contains newlines)."""
    return subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
    )