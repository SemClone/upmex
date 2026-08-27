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

from upmex.licenses.osslili_subprocess import osslili_command

# Skip on what the detector actually runs, not on what PATH happens to offer.
# These tests are sensitive to the osslili version, and checking a different
# binary than the one under test is how the version confusion started.
pytestmark = pytest.mark.skipif(
    shutil.which(osslili_command()) is None,
    reason="the osslili CLI upmex depends on is not installed",
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

    @pytest.mark.parametrize("name", [
        "README.md", "README.markdown", "README.mdown", "README.text",
        "README.asciidoc", "README.textile", "README.org",
        "CHANGELOG.md", "docs.rst", "guide.adoc", "notes.txt",
        # No suffix at all, which the rule used to miss entirely. GNU-style
        # and many C and Go projects ship exactly these.
        "README", "INSTALL", "CHANGELOG", "NEWS", "TODO", "CONTRIBUTING",
    ])
    def test_in_every_kind_of_document(self, name):
        assert _found(name, CREDITS_A_DEPENDENCY) == []

    def test_the_package_is_not_relabelled_by_its_own_readme(self):
        """The whole point: an MIT package must not come back Apache-2.0."""
        found = _found("README.md", CREDITS_A_DEPENDENCY)
        assert "Apache-2.0" not in found


# The complete text, because a document only counts when it carries the
# licence, and osslili measures that by how closely the text matches.
FULL_MIT_TEXT = """MIT License

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
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


class TestADocumentThatCarriesTheLicence:
    """Naming a licence is what osslili cannot tell from declaring one, so
    the licence has to be present. Carrying the text is a different match
    type, and that is what counts here."""

    def test_a_readme_holding_the_licence_text_is_read(self):
        assert _found("README.md", "# mypkg\n\n## License\n\n" + FULL_MIT_TEXT) == ["MIT"]

    def test_in_a_markdown_variant_too(self):
        assert _found("README.markdown", "# mypkg\n\n## License\n\n" + FULL_MIT_TEXT) == ["MIT"]

    def test_a_bare_spdx_line_is_not_enough_on_its_own(self):
        """The cost of the rule, stated. osslili reports a real
        SPDX-License-Identifier line and the sentence "it bundles terser,
        license: BSD-2-Clause" as the same kind of evidence, so neither can
        be trusted inside a document. Package metadata carries this case."""
        assert _found("README.md", "SPDX-License-Identifier: MIT\n\nA parser.\n") == []

    def test_nor_is_a_license_line(self):
        assert _found("README.md", "License: MIT\n\nA parser.\n") == []


class TestTheProseThatLooksLikeAHeader:
    """osslili matches "License: X" anywhere in the first thirty lines,
    mid-sentence included, and reports it exactly as a real header."""

    @pytest.mark.parametrize("line", [
        "It bundles terser, license: BSD-2-Clause, for minification.\n",
        "| terser | License: BSD-2-Clause |\n",
        "- lodash, license: MIT\n",
        "Dependencies: react (License: MIT), terser (License: BSD-2-Clause)\n",
    ])
    def test_a_dependency_credit_is_not_the_package_licence(self, line):
        assert _found("README.md", line) == []


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


class TestLicenceFilesWithASuffixedName:
    """A dual-licensed project ships LICENSE-MIT.txt and LICENSE-APACHE.txt.
    Those are licence files with a document suffix, and reading them as
    documents would refuse the very files that hold the licence."""

    @pytest.mark.parametrize("name", [
        "LICENSE-MIT.txt", "LICENSE-APACHE.txt", "LICENCE-MIT.md",
        "license_apache.md", "licenses.txt", "COPYING.LESSER",
    ])
    def test_it_is_read(self, name):
        assert _found(name, "SPDX-License-Identifier: MIT\n") == ["MIT"], name

    @pytest.mark.parametrize("name", ["CHANGELOG.md", "CONTRIBUTING.md",
                                      "docs/install.rst", "notes.txt"])
    def test_but_a_document_is_still_a_document(self, name):
        assert _found(name, "SPDX-License-Identifier: MIT\n") == [], name



class TestWhatThisRuleGivesUp:
    """Stated as a test so it is a decision on the record rather than a
    surprise: a package whose only licence statement is prose in its README,
    with no licence file and nothing in its metadata."""

    def test_a_readme_carrying_the_licence_is_read_when_that_file_is_scanned(self):
        assert _found("README.md", "# mypkg\n\n## License\n\n" + FULL_MIT_TEXT) == ["MIT"]

    def test_but_not_when_the_directory_is_scanned(self):
        """Scanning a directory, osslili measures a short window around the
        word "license" rather than the whole file, and a bare mention scores
        the same as a document carrying the entire licence. Nothing separates
        them, so both are refused."""
        directory = tempfile.mkdtemp()
        try:
            with open(os.path.join(directory, "README.md"), "w") as handle:
                handle.write("# mypkg\n\n## License\n\n" + FULL_MIT_TEXT)
            found = OssliliSubprocessDetector().detect_from_directory(directory)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

        assert found["licenses"] == []

    def test_and_a_licence_file_alongside_it_is_still_read(self):
        """Which is why the loss is narrow: the shape needs no licence file
        anywhere, and almost every package has one."""
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


class TestALicenceFileNamedAfterItsLicence:
    """A dual-licensed project ships MIT.txt beside APACHE.txt. Neither name
    contains a licence word and both carry a document suffix, so the rule read
    them as prose and a directory scan came back with no licence at all."""

    @pytest.mark.parametrize("name", ["MIT.txt", "APACHE.txt", "BSD.txt",
                                      "OFL.txt", "GPL.md"])
    def test_a_directory_scan_reads_it(self, name):
        directory = tempfile.mkdtemp()
        try:
            with open(os.path.join(directory, name), "w") as handle:
                handle.write(FULL_MIT_TEXT)
            found = OssliliSubprocessDetector().detect_from_directory(directory)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

        assert [lic["spdx_id"] for lic in found["licenses"]] == ["MIT"], name

    @pytest.mark.parametrize("name", ["MIT.txt", "APACHE.txt", "GPL.md"])
    def test_and_so_does_a_file_scan(self, name):
        assert _found(name, FULL_MIT_TEXT) == ["MIT"], name
