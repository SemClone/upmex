"""The text detector shells out to the osslili CLI.

Every other test of that detector patches subprocess.run, so the whole suite
can pass while the binary is missing, broken or too slow, and every real
detection silently returns nothing. These run the CLI for real, and say what
went wrong rather than leaving a bare `assert [] == ['MIT']` behind.
"""

import shutil
import subprocess

from upmex.licenses.osslili_subprocess import OssliliSubprocessDetector

MIT_TEXT = """MIT License

Copyright (c) 2024 Example

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT."""


def test_the_binary_is_on_path():
    found = shutil.which("osslili")
    assert found, (
        "the osslili CLI is not on PATH, so every text detection returns "
        "nothing and the failure surfaces as a missing licence"
    )


def test_the_binary_runs(tmp_path):
    target = tmp_path / "LICENSE"
    target.write_text(MIT_TEXT)

    result = subprocess.run(
        ["osslili", "-f", "evidence", str(target)],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"osslili exited {result.returncode}\n"
        f"stdout: {result.stdout[:2000]}\n"
        f"stderr: {result.stderr[:2000]}"
    )
    assert "MIT" in result.stdout, (
        f"osslili ran but found no MIT in its own output\n"
        f"stdout: {result.stdout[:2000]}\n"
        f"stderr: {result.stderr[:2000]}"
    )


def test_the_detector_reads_a_licence_file(tmp_path):
    """The path the NuGet, npm and Python extractors all take."""
    detector = OssliliSubprocessDetector()
    found = detector.detect_from_file("LICENSE", MIT_TEXT)

    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as t:
        t.write(MIT_TEXT)
        probe_path = t.name
    probe = subprocess.run(
        ["osslili", "-f", "evidence", probe_path],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert [lic["spdx_id"] for lic in found] == ["MIT"], (
        f"detector returned {found}\n"
        f"osslili on PATH: {shutil.which('osslili')}\n"
        f"probe returncode: {probe.returncode}\n"
        f"probe stdout: {probe.stdout[:3000]}\n"
        f"probe stderr: {probe.stderr[:1000]}"
    )
