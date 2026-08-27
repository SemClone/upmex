"""upmex declares osslili as a dependency, so that is the one it must run.

Invoking it by bare name asked PATH instead, and PATH answered with whatever
copy came first. On the machine this was found, that was a system-wide 1.6.1
rather than the 1.7.5 in the environment, and the two disagree: the same
LICENSE file holding the MIT text is MIT to one and JSON to the other. Which
licence a package appears to have must not depend on PATH order.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from upmex.licenses.osslili_subprocess import (
    OssliliSubprocessDetector,
    osslili_command,
)


def test_it_is_the_one_installed_beside_the_interpreter():
    beside = Path(sys.executable).parent / "osslili"
    if not beside.exists():
        pytest.skip("no osslili installed beside this interpreter")
    assert osslili_command() == str(beside)


def test_it_is_not_a_bare_name():
    """A bare name is resolved by PATH at the moment of the call."""
    beside = Path(sys.executable).parent / "osslili"
    if not beside.exists():
        pytest.skip("no osslili installed beside this interpreter")
    assert os.path.isabs(osslili_command())


def test_the_detector_actually_runs_it():
    command = osslili_command()
    result = subprocess.run(
        [command, "--version"], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr

    scanned = []
    original = subprocess.run

    def record(cmd, **kwargs):
        scanned.append(cmd[0])
        return original(cmd, **kwargs)

    import upmex.licenses.osslili_subprocess as module

    module.subprocess.run = record
    try:
        module.OssliliSubprocessDetector().detect_from_file("LICENSE", "MIT License\n")
    finally:
        module.subprocess.run = original

    assert scanned == [command], scanned


def test_a_path_ahead_of_the_environment_does_not_win(tmp_path, monkeypatch):
    """The failure as it happened: another osslili earlier on PATH."""
    impostor = tmp_path / "osslili"
    impostor.write_text("#!/bin/sh\necho impostor\n")
    impostor.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    beside = Path(sys.executable).parent / "osslili"
    if not beside.exists():
        pytest.skip("no osslili installed beside this interpreter")

    assert osslili_command() != str(impostor)
    assert OssliliSubprocessDetector().detect_from_file(
        "LICENSE", "SPDX-License-Identifier: MIT\n"
    )


class TestSomethingUnrunnableBesideTheInterpreter:
    """Existing is not the same as runnable. Taking an unrunnable candidate
    means the subprocess raises, the broad except swallows it, and the package
    is reported as having no licence rather than falling back to PATH."""

    def _pretend_interpreter_lives_in(self, directory, monkeypatch):
        fake = directory / "python"
        fake.write_text("")
        monkeypatch.setattr(sys, "executable", str(fake))

    def test_a_directory_of_that_name_is_not_taken(self, tmp_path, monkeypatch):
        (tmp_path / "osslili").mkdir()
        self._pretend_interpreter_lives_in(tmp_path, monkeypatch)

        assert osslili_command() != str(tmp_path / "osslili")

    def test_nor_a_file_with_no_execute_bit(self, tmp_path, monkeypatch):
        candidate = tmp_path / "osslili"
        candidate.write_text("#!/bin/sh\nexit 0\n")
        candidate.chmod(0o644)
        self._pretend_interpreter_lives_in(tmp_path, monkeypatch)

        assert osslili_command() != str(candidate)

    def test_and_the_licence_is_still_found_through_the_fallback(
        self, tmp_path, monkeypatch
    ):
        (tmp_path / "osslili").mkdir()
        self._pretend_interpreter_lives_in(tmp_path, monkeypatch)
        real = Path(sys.executable).parent / "osslili"
        if not real.exists():
            pytest.skip("no osslili installed beside the real interpreter")
        monkeypatch.setenv("PATH", f"{real.parent}{os.pathsep}{os.environ['PATH']}")

        found = OssliliSubprocessDetector().detect_from_file(
            "LICENSE", "SPDX-License-Identifier: MIT\n"
        )
        assert [lic["spdx_id"] for lic in found] == ["MIT"]

    def test_a_runnable_one_is_taken(self, tmp_path, monkeypatch):
        candidate = tmp_path / "osslili"
        candidate.write_text("#!/bin/sh\nexit 0\n")
        candidate.chmod(0o755)
        self._pretend_interpreter_lives_in(tmp_path, monkeypatch)

        assert osslili_command() == str(candidate)
