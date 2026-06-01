from .tool import Tool
from .git import get_staged_diff, get_staged_files
import subprocess

ALLOWED_GIT_COMMANDS = set[str]("log", "diff", "status", "show", "status", "shortlog", "blame")

def run_git(args: list[str]) -> str:
    if not args or args[0] not in ALLOWED_GIT_COMMANDS:
        return "Invalid git command."
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    return result.stdout or result.stderr

run_git_tool = Tool(
    name="run_git",
    description="Run a git command",
    function=run_git,
    parameters={
        "args": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
)

def read_file(path: str) -> str:
    try:
        with open(path, "r") as file:
            return file.read()
    except FileNotFoundError:
        return "File not found."
    except PermissionError:
        return "Permission denied."
    except Exception as e:
        return f"Error reading file: {e}"

read_file_tool = Tool(
    name="read_file",
    description="Read a file",
    function=read_file,
    parameters={
        "path": {
            "type": "string",
        },
    },
)

def list_directory(path: str) -> list[str]:
    try:
        return os.listdir(path)
    except FileNotFoundError:
        return "Directory not found."
    except PermissionError:
        return "Permission denied."
    except Exception as e:
        return f"Error listing directory: {e}"

list_directory_tool = Tool(
    name="list_directory", 
    description="List a directory",
    function=list_directory,
    parameters={
        "path": {
            "type": "string",
        },
    },
)

def search_code(query: str) -> str:
    result = subprocess.run(["git", "grep", "-n", query], capture_output=True, text=True)
    return result.stdout or result.stderr

search_code_tool = Tool(
    name="search_code",
    description="Search the codebase for a query",
    function=search_code,
    parameters={
        "query": {
            "type": "string",
        },
    },
)