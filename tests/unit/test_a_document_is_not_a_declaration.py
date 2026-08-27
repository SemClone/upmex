"""A README talks about licences. That is not the same as having one.

These drive the real osslili binary rather than a mock, because the defect
they cover was invisible to mocks: the evidence hand-written into a test was
not the evidence osslili actually emits. osslili's SPDX patterns match prose,
so "the bundled minifier is licensed under the Apache License" arrives as
detection_method 'tag' at confidence 1.0, and an MIT package was reported as
Apache-2.0 on the strength of a sentence crediting a dependency.
"""

import os
import shutil
import tempfile

import pytest

from upmex.licenses.osslili_subprocess import OssliliSubprocessDetector

pytestmark = pytest.mark.skipif(
    shutil.which("osslili") is None, reason="the osslili CLI is not installed"
)

MIT_TEXT = """MIT License

Copyright (c) 2024 Example

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software."""

CREDITS_A_DEPENDENCY = (
    "Widget parser.\n\n"
    "The bundled minifier is licensed under the Apache License, Version 2.0.\n"
    "See http://www.apache.org/licenses/LICENSE-2.0.\n"
)


def _found(name, content):
    return [lic["spdx_id"] for lic in
            OssliliSubprocessDetector().detect_from_file(name, content)]


class TestAMentionIsNotADeclaration:
    def test_a_readme_crediting_a_dependency_reports_nothing(self):
        assert _found("README.md", CREDITS_A_DEPENDENCY) == []

    @pytest.mark.parametrize("name", ["README.md", "CHANGELOG.md", "docs.rst",
                                      "guide.adoc", "notes.txt"])
    def test_in_every_kind_of_document(self, name):
        assert _found(name, CREDITS_A_DEPENDENCY) == []

    def test_the_package_is_not_relabelled_by_its_own_readme(self):
        """The whole point: an MIT package must not come back Apache-2.0."""
        found = _found("README.md", CREDITS_A_DEPENDENCY)
        assert "Apache-2.0" not in found


class TestADocumentCanStillDeclare:
    """A line whose whole purpose is to state the licence is a declaration,
    wherever it sits."""

    def test_an_spdx_identifier_line(self):
        assert _found("README.md", "SPDX-License-Identifier: MIT\n\nA parser.\n") == ["MIT"]

    def test_a_license_line(self):
        assert _found("README.md", "License: MIT\n\nA parser.\n") == ["MIT"]


class TestALicenceFileIsNeverADocument:
    """LICENSE.txt and LICENCE.md carry a document suffix and are not
    documents. Dropping them would be the worse failure by far."""

    @pytest.mark.parametrize("name", [
        "LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCE", "LICENCE.txt",
        "COPYING", "COPYING.txt", "NOTICE", "UNLICENSE", "licenses.txt",
    ])
    def test_it_is_read(self, name):
        assert _found(name, MIT_TEXT) == ["MIT"], name


class TestADirectoryScan:
    def test_the_readme_does_not_add_a_licence_the_package_lacks(self):
        directory = tempfile.mkdtemp()
        try:
            with open(os.path.join(directory, "README.md"), "w") as handle:
                handle.write(CREDITS_A_DEPENDENCY)
            with open(os.path.join(directory, "LICENSE"), "w") as handle:
                handle.write(MIT_TEXT)

            found = OssliliSubprocessDetector().detect_from_directory(directory)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

        assert sorted({lic["spdx_id"] for lic in found["licenses"]}) == ["MIT"]


class TestTheContentIsWhatGetsScanned:
    """Every other test here mocks subprocess.run and so never checks that the
    content reaches the file osslili reads. An implementation that wrote
    nothing would pass those and find nothing in production."""

    def test_the_licence_is_read_from_the_content_not_the_name(self):
        assert _found("LICENSE", MIT_TEXT) == ["MIT"]

    def test_an_empty_licence_file_yields_nothing(self):
        assert _found("LICENSE", "") == []

    def test_the_name_alone_is_not_enough(self):
        assert _found("LICENSE", "This file intentionally left blank.\n") == []


class TestADegenerateFilename:
    """The content is written to a file named after the caller's path. Some
    paths have no usable basename, and writing to those raises an error the
    broad except turns into a silent empty result, so the licence disappears
    with no sign of why."""

    @pytest.mark.parametrize("name", ["", ".", "..", "/", "./", "../", "..."])
    def test_the_licence_is_still_found(self, name):
        assert _found(name, MIT_TEXT) == ["MIT"], name

    def test_a_path_with_directories_uses_only_the_last_part(self):
        assert _found("pkg/nested/LICENSE", MIT_TEXT) == ["MIT"]

    def test_an_absolute_path_too(self):
        assert _found("/opt/pkg/LICENSE", MIT_TEXT) == ["MIT"]

    def test_a_document_deep_in_a_tree_is_still_a_document(self):
        assert _found("docs/guide/README.md", CREDITS_A_DEPENDENCY) == []
