import os
from .tool import Tool
from ..git import get_staged_diff, get_staged_files
import subprocess

ALLOWED_GIT_COMMANDS = ["log", "diff", "status", "show", "status", "shortlog", "blame", "tag"]


def _repo_root() -> str:
    """Absolute, symlink-resolved path to the git repository root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    root = result.stdout.strip() or os.getcwd()
    return os.path.realpath(root)


def run_git(args: list[str]) -> str:
    if not args or args[0] not in ALLOWED_GIT_COMMANDS:
        return "Invalid git command."
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    return result.stdout or result.stderr

run_git_tool = Tool(
    name="run_git",
    description=(
        "Run a read-only git command and return its output. The first element "
        "of `args` must be one of: "
        + ", ".join(sorted(set(ALLOWED_GIT_COMMANDS)))
        + ". Example: [\"log\", \"--oneline\", \"-n\", \"10\"]."
    ),
    function=run_git,
    parameters={
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "git subcommand and its arguments as separate strings, e.g. "
                "[\"diff\", \"--stat\"]. The subcommand (first item) must be allowed."
            ),
        },
    },
    required=["args"],
)

def read_file(path: str) -> str:
    root = _repo_root()
    target = os.path.realpath(os.path.join(root, path))
    if target != root and not target.startswith(root + os.sep):
        return f"Access denied: '{path}' is outside the repository root."
    try:
        with open(target, "r") as file:
            return file.read()
    except FileNotFoundError:
        return "File not found."
    except IsADirectoryError:
        return "Path is a directory, not a file."
    except PermissionError:
        return "Permission denied."
    except UnicodeDecodeError:
        return "File is not valid UTF-8 text and cannot be read."
    except Exception as e:
        return f"Error reading file: {e}"

read_file_tool = Tool(
    name="read_file",
    description=(
        "Read and return the UTF-8 text contents of a file inside the repository. "
        "Paths are resolved relative to the repository root; paths that escape the "
        "repository (e.g. via '..' or absolute paths) are rejected."
    ),
    function=read_file,
    parameters={
        "path": {
            "type": "string",
            "description": (
                "File path relative to the repository root, e.g. "
                "\"messygit/cli.py\"."
            ),
        },
    },
    required=["path"],
)

def list_directory(path: str) -> list[str]:
    root = _repo_root()
    target = os.path.realpath(os.path.join(root, path))
    if target != root and not target.startswith(root + os.sep):
        return f"Access denied: '{path}' is outside the repository root."
    try:
        return os.listdir(target)
    except FileNotFoundError:
        return "Directory not found."
    except NotADirectoryError:
        return "Path is a file, not a directory."
    except PermissionError:
        return "Permission denied."
    except Exception as e:
        return f"Error listing directory: {e}"

list_directory_tool = Tool(
    name="list_directory",
    description=(
        "List the names of entries (files and subdirectories) in a directory. "
        "Use \".\" for the current directory."
    ),
    function=list_directory,
    parameters={
        "path": {
            "type": "string",
            "description": "Directory path to list, e.g. \"messygit\" or \".\".",
        },
    },
    required=["path"],
)

def search_code(query: str) -> str:
    result = subprocess.run(["git", "grep", "-n", query], capture_output=True, text=True)
    return result.stdout or result.stderr

search_code_tool = Tool(
    name="search_code",
    description=(
        "Search tracked files in the repository for a string or regex using "
        "`git grep`. Returns matching lines prefixed with file path and line number."
    ),
    function=search_code,
    parameters={
        "query": {
            "type": "string",
            "description": "The text or basic regex pattern to search for.",
        },
    },
    required=["query"],
)

def write_file(path: str, content: str) -> str:
    root = _repo_root()
    target = os.path.realpath(os.path.join(root, path))
    if target != root and not target.startswith(root + os.sep):
        return f"Access denied: '{path}' is outside the repository root."
    try:
        with open(target, "w") as file:
            file.write(content)
        return "File written successfully."
    except FileNotFoundError:
        return "File not found."
    except IsADirectoryError:
        return "Path is a directory, not a file."
    except PermissionError:
        return "Permission denied."
    except Exception as e:
        return f"Error writing file: {e}"

write_file_tool = Tool(
    name="write_file",
    description=(
        "Write the given content to a file inside the repository. This OVERWRITES "
        "the entire file, so use it for creating a new file or fully replacing one. "
        "To change part of an existing file, prefer `edit_file`. "
        "Paths are resolved relative to the repository root; paths that escape the "
        "repository (e.g. via '..' or absolute paths) are rejected."
    ),
    function=write_file,
    parameters={
        "path": {
            "type": "string",
            "description": "File path relative to the repository root, e.g. \"messygit/cli.py\".",
        },
        "content": {
            "type": "string",
            "description": "The content to write to the file.",
        },
    },
    required=["path", "content"],
)

def edit_file(path: str, old_string: str, new_string: str) -> str:
    root = _repo_root()
    target = os.path.realpath(os.path.join(root, path))
    if target != root and not target.startswith(root + os.sep):
        return f"Access denied: '{path}' is outside the repository root."
    try:
        with open(target, "r") as file:
            content = file.read()
    except FileNotFoundError:
        return "File not found. Use write_file to create a new file."
    except IsADirectoryError:
        return "Path is a directory, not a file."
    except PermissionError:
        return "Permission denied."
    except UnicodeDecodeError:
        return "File is not valid UTF-8 text and cannot be edited."
    except Exception as e:
        return f"Error reading file: {e}"

    if old_string == new_string:
        return "No change: old_string and new_string are identical."
    count = content.count(old_string)
    if count == 0:
        return (
            "old_string not found in the file. It must match the existing text "
            "exactly (including whitespace and indentation)."
        )
    if count > 1:
        return (
            f"old_string is not unique ({count} matches). Include more surrounding "
            "context so it matches exactly one location."
        )

    try:
        with open(target, "w") as file:
            file.write(content.replace(old_string, new_string))
        return "File edited successfully."
    except Exception as e:
        return f"Error writing file: {e}"

edit_file_tool = Tool(
    name="edit_file",
    description=(
        "Replace an exact span of text in an existing file with new text, leaving "
        "the rest of the file untouched. `old_string` must appear EXACTLY ONCE in "
        "the file (include enough surrounding context to make it unique); if it "
        "appears zero times or more than once, the edit is rejected. To prepend "
        "text, set old_string to the current first line and put the new text before "
        "it in new_string. Use `write_file` to create a file that does not exist yet. "
        "Paths that escape the repository are rejected."
    ),
    function=edit_file,
    parameters={
        "path": {
            "type": "string",
            "description": "File path relative to the repository root, e.g. \"CHANGELOG.md\".",
        },
        "old_string": {
            "type": "string",
            "description": "The exact existing text to replace. Must match uniquely.",
        },
        "new_string": {
            "type": "string",
            "description": "The text to write in place of old_string.",
        },
    },
    required=["path", "old_string", "new_string"],
)