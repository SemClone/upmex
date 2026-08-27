"""Pytest configuration for upmex."""

import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def separated_runner():
    """A CliRunner that keeps stderr out of stdout.

    Click separated the two by default from 8.2 onward. Before that it had to
    be asked, and asking a newer Click raises, so a test written against one
    version fails on the other. Tests that prove the two streams stay apart
    need a runner that actually keeps them apart, on every version the project
    supports.
    """
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()
