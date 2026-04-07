import subprocess

def get_staged_diff():
    result = subprocess.run(
        ["git", "diff", "--staged"],
        capture_output=True,
        text=True
    )
    return result.stdout

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