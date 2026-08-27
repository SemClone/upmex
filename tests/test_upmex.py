"""Tests about the package itself: it imports, it is where it says it is, and
it parses.

These used to pass without checking anything. The import test caught
ImportError and asserted True in both branches, so a package that could not be
imported still passed. The syntax check walked `<repo>/upmex`, which does not
exist because the code lives in `src/upmex`, so it parsed no files at all.
"""

import ast
import sys
from importlib import metadata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
PACKAGE_DIR = REPO_ROOT / "src" / "upmex"


def _distribution():
    """Read the installed metadata rather than parsing pyproject, so this
    works on every version the project claims to support. tomllib is 3.11+."""
    return metadata.metadata("upmex")


def test_the_package_imports():
    import upmex

    assert upmex.__version__


def test_the_version_matches_pyproject():
    """Two places state the version, and they have to agree."""
    import upmex

    assert upmex.__version__ == _distribution()["Version"]


def test_this_interpreter_is_one_the_project_claims_to_support():
    declared = _distribution()["Requires-Python"]
    assert declared.startswith(">="), f"unhandled specifier: {declared}"
    minimum = tuple(int(part) for part in declared[2:].strip().split("."))
    assert sys.version_info[: len(minimum)] >= minimum


class TestThePackageIsWhereItSaysItIs:
    def test_the_source_directory_exists(self):
        assert PACKAGE_DIR.is_dir(), f"{PACKAGE_DIR} is missing"

    def test_the_installed_package_is_that_directory(self):
        """An editable install, so a test can trust the tree it is reading."""
        import upmex

        assert Path(upmex.__file__).parent == PACKAGE_DIR

    def test_pyproject_exists(self):
        assert (REPO_ROOT / "pyproject.toml").exists()


@pytest.mark.parametrize("required_file", ["README.md", "LICENSE", "pyproject.toml"])
def test_required_files_exist(required_file):
    assert (REPO_ROOT / required_file).exists(), f"{required_file} not found"


def test_every_source_file_parses():
    checked = 0
    for path in PACKAGE_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        checked += 1
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as error:
            pytest.fail(f"Syntax error in {path}: {error}")

    # Without this the test passes when it has parsed nothing, which is how it
    # went unnoticed that it was pointed at a directory that does not exist.
    assert checked > 20, f"only {checked} files parsed, expected the whole package"
