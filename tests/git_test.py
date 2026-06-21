import textwrap

import pytest

from messygit.git import (
    FileStat,
    _compact_diff_for_files,
    _is_noise_file,
    _parse_compact_diff,
)


def diff(text: str) -> str:
    """Dedent a triple-quoted diff fixture and strip the leading newline."""
    return textwrap.dedent(text).lstrip("\n")


# --- _is_noise_file -------------------------------------------------------

@pytest.mark.parametrize("path", [
    "package-lock.json",
    "frontend/yarn.lock",
    "go.sum",
    "app/bundle.min.js",
    "styles/site.min.css",
    "src/api.pb.go",
    "schema.generated.ts",
    "components/Button.snap",
    "nested/dir/.DS_Store",
])
def test_noise_files_are_detected(path):
    assert _is_noise_file(path) is True


@pytest.mark.parametrize("path", [
    "messygit/cli.py",
    "README.md",
    "src/index.js",
    "lockfile_reader.py",   # 'lock' in name but not an actual lockfile
    "minify.py",            # 'min' substring, not *.min.js
])
def test_real_source_files_are_not_noise(path):
    assert _is_noise_file(path) is False


# --- _parse_compact_diff --------------------------------------------------

def test_parse_single_file_keeps_only_changed_lines():
    raw = diff("""
        diff --git a/messygit/cli.py b/messygit/cli.py
        index 1111111..2222222 100644
        --- a/messygit/cli.py
        +++ b/messygit/cli.py
        @@ -10,1 +10,1 @@ def main():
        -    old_call()
        +    new_call()
    """)
    assert _parse_compact_diff(raw) == diff("""
        === messygit/cli.py ===
        -    old_call()
        +    new_call()
    """).rstrip()


def test_parse_drops_metadata_lines():
    """index, ---, +++ and @@ hunk headers must never appear in output."""
    raw = diff("""
        diff --git a/a.py b/a.py
        index 1111111..2222222 100644
        --- a/a.py
        +++ b/a.py
        @@ -1,0 +1,1 @@
        +added
    """)
    out = _parse_compact_diff(raw)
    assert "index" not in out
    assert "@@" not in out
    assert "---" not in out
    assert "+++" not in out
    assert out == "=== a.py ===\n+added"


def test_parse_multiple_files():
    raw = diff("""
        diff --git a/one.py b/one.py
        --- a/one.py
        +++ b/one.py
        @@ -1 +1 @@
        -a
        +b
        diff --git a/two.py b/two.py
        --- a/two.py
        +++ b/two.py
        @@ -1 +0,0 @@
        -gone
    """)
    # A blank line separates files: each header is emitted with a leading "\n",
    # and the very first one is removed by the trailing .strip().
    assert _parse_compact_diff(raw) == diff("""
        === one.py ===
        -a
        +b

        === two.py ===
        -gone
    """).rstrip()


def test_parse_skips_noise_file_entirely():
    """A noise file should not even get a === header, but real files still do."""
    raw = diff("""
        diff --git a/package-lock.json b/package-lock.json
        --- a/package-lock.json
        +++ b/package-lock.json
        @@ -1 +1 @@
        -  "version": "1.0.0"
        +  "version": "1.0.1"
        diff --git a/src/app.py b/src/app.py
        --- a/src/app.py
        +++ b/src/app.py
        @@ -1 +1 @@
        -x = 1
        +x = 2
    """)
    out = _parse_compact_diff(raw)
    assert "package-lock.json" not in out
    assert "version" not in out
    assert out == "=== src/app.py ===\n-x = 1\n+x = 2"


def test_parse_empty_diff_returns_empty_string():
    assert _parse_compact_diff("") == ""


def test_parse_new_file_only_additions():
    raw = diff("""
        diff --git a/new.py b/new.py
        new file mode 100644
        index 0000000..3333333
        --- /dev/null
        +++ b/new.py
        @@ -0,0 +1,2 @@
        +line one
        +line two
    """)
    assert _parse_compact_diff(raw) == diff("""
        === new.py ===
        +line one
        +line two
    """).rstrip()


# --- _compact_diff_for_files ---------------------------------------------

TWO_FILE_DIFF = diff("""
    diff --git a/keep.py b/keep.py
    --- a/keep.py
    +++ b/keep.py
    @@ -1 +1 @@
    -old
    +new
    diff --git a/drop.py b/drop.py
    --- a/drop.py
    +++ b/drop.py
    @@ -1 +1 @@
    -foo
    +bar
""")


def test_compact_for_files_includes_only_selected_paths():
    out = _compact_diff_for_files({"keep.py"}, TWO_FILE_DIFF)
    assert out == "=== keep.py ===\n-old\n+new"
    assert "drop.py" not in out
    assert "bar" not in out


def test_compact_for_files_selects_multiple():
    out = _compact_diff_for_files({"keep.py", "drop.py"}, TWO_FILE_DIFF)
    assert "=== keep.py ===" in out
    assert "=== drop.py ===" in out


def test_compact_for_files_empty_selection_returns_empty():
    assert _compact_diff_for_files(set(), TWO_FILE_DIFF) == ""


def test_compact_for_files_unknown_path_returns_empty():
    assert _compact_diff_for_files({"does/not/exist.py"}, TWO_FILE_DIFF) == ""


# --- FileStat -------------------------------------------------------------

def test_filestat_total_changed_sums_added_and_removed():
    assert FileStat(path="a.py", added=3, removed=2).total_changed == 5


def test_filestat_total_changed_zero():
    assert FileStat(path="a.py", added=0, removed=0).total_changed == 0
