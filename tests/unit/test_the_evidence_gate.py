"""What upmex keeps out of osslili's evidence, and why.

osslili reports a score, a category (declared, detected, referenced,
third-party) and a match_type saying which rule fired. Gating on the score
alone made the answer depend on the machine: the same MIT text was scored 0.95
by one similarity backend and 0.6 by another, so a package came back MIT
locally and unlicensed in CI.

Gating on the category alone is not right either. osslili labels "declared"
any pattern match in a file ending .md, .rst, .txt or .adoc, so a README that
says "licensed under MIT" would count as a declaration. The match_type is what
separates the two.
"""

import json
import os
from unittest.mock import patch

import pytest

from upmex.licenses.osslili_subprocess import OssliliSubprocessDetector, is_reportable

MIT_TEXT = "MIT License\n\nPermission is hereby granted, free of charge"


def _result(evidence, key="scan_results"):
    payload = (
        {"scan_results": [{"license_evidence": evidence, "copyright_evidence": []}]}
        if key == "scan_results"
        else {"results": [{"licenses": evidence}]}
    )

    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps(payload)

    return Result()


def _spdx(found):
    return [lic["spdx_id"] for lic in found]


class TestOssliliSeesTheRealFilename:
    """The root of the CI failure. osslili decides what kind of evidence a
    match is partly from the file's name, and the content was being written to
    a random tmpXXXX.txt, so a package's own LICENSE was read as a passing
    mention in a text file."""

    def test_the_callers_name_reaches_osslili(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["path"] = cmd[-1]
            return _result([])

        with patch("subprocess.run", side_effect=fake_run):
            OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)

        assert os.path.basename(seen["path"]) == "LICENSE"

    def test_an_extension_is_kept_too(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["path"] = cmd[-1]
            return _result([])

        with patch("subprocess.run", side_effect=fake_run):
            OssliliSubprocessDetector().detect_from_file("LICENSE.md", MIT_TEXT)

        assert os.path.basename(seen["path"]) == "LICENSE.md"

    def test_nothing_is_left_behind(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["path"] = cmd[-1]
            return _result([])

        with patch("subprocess.run", side_effect=fake_run):
            OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)

        assert not os.path.exists(seen["path"])
        assert not os.path.exists(os.path.dirname(seen["path"]))


# What osslili really returns for a file named LICENSE holding MIT text. The
# score differs by machine; the match_type does not.
LICENCE_FILE_HIGH = [
    {"detected_license": "MIT", "confidence": 1.0, "detection_method": "regex",
     "category": "declared", "match_type": "license_file"},
    {"detected_license": "MIT", "confidence": 0.9, "detection_method": "keyword",
     "category": "detected", "match_type": "keyword"},
]
LICENCE_FILE_LOW = [
    {"detected_license": "MIT", "confidence": 0.6, "detection_method": "regex",
     "category": "declared", "match_type": "license_file"},
    {"detected_license": "MIT", "confidence": 0.9, "detection_method": "keyword",
     "category": "detected", "match_type": "keyword"},
]


class TestTheSameFileGivesTheSameAnswer:
    def test_the_high_scoring_machine_reports_mit(self):
        with patch("subprocess.run", return_value=_result(LICENCE_FILE_HIGH)):
            found = OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)
        assert _spdx(found) == ["MIT"]

    def test_the_low_scoring_machine_reports_mit_too(self):
        """This is the one that failed in CI. The score moved, the evidence
        did not, so the answer must not move either."""
        with patch("subprocess.run", return_value=_result(LICENCE_FILE_LOW)):
            found = OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)
        assert _spdx(found) == ["MIT"]

    def test_it_is_the_match_type_doing_the_work(self):
        """Same score, same category, only the match_type differs. If this
        passed on the score the two would agree, and they must not."""
        low_declaring = dict(LICENCE_FILE_LOW[0])
        low_mention = dict(low_declaring, match_type="documentation")

        assert is_reportable(low_declaring)
        assert not is_reportable(low_mention)


# What osslili really emits for a README sentence crediting a dependency,
# taken from a run of the binary. The tag record is the one that matters: the
# SPDX patterns match prose, so a mention is reported the same way a genuine
# identifier is, at confidence 1.0. An earlier version of this test invented a
# lone documentation record at 0.7, which the gate refused, so the test passed
# while production reported Apache-2.0 for an MIT package.
README_CREDITING_A_DEPENDENCY = [
    {"detected_license": "Apache-2.0", "confidence": 1.0, "detection_method": "tag",
     "category": "declared", "match_type": "spdx_identifier"},
    {"detected_license": "Apache-2.0", "confidence": 0.9, "detection_method": "keyword",
     "category": "detected", "match_type": "keyword"},
    {"detected_license": "Apache-2.0", "confidence": 0.867, "detection_method": "regex",
     "category": "declared", "match_type": "documentation"},
]


class TestAMentionIsNotADeclaration:
    """In a document, a licence named inside a sentence proves nothing."""

    def test_the_evidence_osslili_really_returns_for_a_mention(self):
        with patch("subprocess.run",
                   return_value=_result(README_CREDITING_A_DEPENDENCY)):
            found = OssliliSubprocessDetector().detect_from_file(
                "README.md", MIT_TEXT
            )
        assert found == []

    def test_the_exact_tag_clause_does_not_rescue_it(self):
        """confidence 1.0 and detection_method tag, and still not a licence,
        because of where it was found."""
        assert not is_reportable(
            README_CREDITING_A_DEPENDENCY[0], source_file="README.md"
        )

    def test_a_partial_pattern_match_is_not_one_either(self):
        assert not is_reportable(
            README_CREDITING_A_DEPENDENCY[2], source_file="README.md"
        )

    def test_a_header_shaped_line_is_not_rescued_either(self):
        """osslili reports a real SPDX-License-Identifier line and the
        sentence "it bundles terser, license: BSD-2-Clause" both as
        header_tag, so inside a document neither can be trusted."""
        assert not is_reportable(
            {"detected_license": "BSD-2-Clause", "confidence": 1.0,
             "detection_method": "tag", "category": "declared",
             "match_type": "header_tag"},
            source_file="README.md",
        )

    def test_a_match_type_the_rule_has_not_heard_of_stays_out(self):
        """The document branch names what it accepts. A blocklist would let
        every future match type in unexamined."""
        assert not is_reportable(
            {"detected_license": "MIT", "confidence": 1.0,
             "detection_method": "regex", "category": "declared",
             "match_type": "some_new_thing"},
            source_file="README.md",
        )

    @pytest.mark.parametrize("match_type", [
        "license_file", "license_header", "text_similarity", "exact_hash",
    ])
    def test_but_evidence_the_document_carries_it_does(self, match_type):
        assert is_reportable(
            {"detected_license": "MIT", "confidence": 0.98,
             "detection_method": "dice-sorensen", "category": "declared",
             "match_type": match_type},
            source_file="README.md",
        )

    def test_and_not_a_weak_text_match(self):
        """A partial match lands in a band osslili only reports when an
        optional backend is installed."""
        assert not is_reportable(
            {"detected_license": "MIT", "confidence": 0.55,
             "detection_method": "dice-sorensen", "category": "declared",
             "match_type": "text_similarity"},
            source_file="README.md",
        )

    def test_and_outside_a_document_the_same_evidence_counts(self):
        """The rule is about where the evidence was found, nothing else."""
        assert is_reportable(
            README_CREDITING_A_DEPENDENCY[0], source_file="package.json"
        )


class TestTheScoreBoundary:
    """osslili caps a documentation match at exactly 0.95, which is also the
    score this gate accepts on its own. Pinned so the comparison cannot drift
    from >= to > unnoticed."""

    def test_the_threshold_itself_is_enough(self):
        assert is_reportable(
            {"detected_license": "MIT", "confidence": 0.95,
             "detection_method": "keyword", "category": "detected",
             "match_type": "keyword"}
        )

    def test_just_under_is_not(self):
        assert not is_reportable(
            {"detected_license": "MIT", "confidence": 0.94,
             "detection_method": "keyword", "category": "detected",
             "match_type": "keyword"}
        )

    def test_and_in_a_document_the_score_does_not_open_the_door(self):
        """The cap and the threshold being equal would otherwise let every
        capped documentation match back in through the score."""
        assert not is_reportable(
            {"detected_license": "MIT", "confidence": 0.95,
             "detection_method": "regex", "category": "declared",
             "match_type": "documentation"},
            source_file="README.md",
        )


class TestSomeoneElsesLicenceStaysOut:
    """A referenced licence and a bundled third-party licence are not this
    package's licence, and no score makes them one."""

    @pytest.mark.parametrize("category", ["referenced", "third-party"])
    @pytest.mark.parametrize("confidence", [0.5, 0.95, 1.0])
    def test_at_any_score(self, category, confidence):
        assert not is_reportable(
            {"detected_license": "GPL-3.0", "confidence": confidence,
             "detection_method": "regex", "category": category,
             "match_type": "license_file"}
        )

    def test_even_with_an_exact_tag(self):
        assert not is_reportable(
            {"detected_license": "GPL-3.0", "confidence": 1.0,
             "detection_method": "tag", "category": "third-party",
             "match_type": "spdx_identifier"}
        )

    def test_through_a_real_scan(self):
        with patch("subprocess.run", return_value=_result([
            {"detected_license": "GPL-3.0", "confidence": 1.0,
             "detection_method": "regex", "category": "third-party",
             "match_type": "license_file"}
        ])):
            found = OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)
        assert found == []


class TestTheKnownFalsePositive:
    def test_pixar_stays_out_however_it_is_evidenced(self):
        assert not is_reportable(
            {"detected_license": "Pixar", "confidence": 1.0,
             "detection_method": "tag", "category": "declared",
             "match_type": "spdx_identifier"}
        )

    def test_through_a_real_scan(self):
        with patch("subprocess.run", return_value=_result([
            {"detected_license": "Pixar", "confidence": 1.0,
             "detection_method": "tag", "category": "declared",
             "match_type": "spdx_identifier"}
        ])):
            found = OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)
        assert found == []

    def test_the_old_output_format_filters_it_too(self):
        with patch("subprocess.run", return_value=_result([
            {"spdx_id": "Pixar", "confidence": 1.0, "detection_method": "tag"}
        ], key="results")):
            found = OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)
        assert found == []


class TestTheOldOutputFormat:
    """osslili's pre-evidence format carries no category, so only the score
    and the detection method can speak for it."""

    def test_an_exact_tag_gets_in(self):
        with patch("subprocess.run", return_value=_result([
            {"spdx_id": "MIT", "confidence": 0.2, "detection_method": "tag"}
        ], key="results")):
            found = OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)
        assert _spdx(found) == ["MIT"]

    def test_a_low_scoring_guess_does_not(self):
        with patch("subprocess.run", return_value=_result([
            {"spdx_id": "MIT", "confidence": 0.6, "detection_method": "keyword"}
        ], key="results")):
            found = OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)
        assert found == []


class TestTheOldFormatCarriesTheFileUnderAnotherName:
    """The pre-evidence format names the file source_file, not file. Reading
    only one key left the document rule silently off for that whole branch."""

    def test_a_mention_in_a_document_is_still_refused(self):
        with patch("subprocess.run", return_value=_result([
            {"spdx_id": "Apache-2.0", "confidence": 1.0,
             "detection_method": "tag", "category": "declared",
             "match_type": "spdx_identifier", "source_file": "README.md"}
        ], key="results")):
            found = OssliliSubprocessDetector().detect_from_directory("/repo")
        assert found["licenses"] == []

    def test_and_a_licence_file_is_still_read(self):
        with patch("subprocess.run", return_value=_result([
            {"spdx_id": "MIT", "confidence": 1.0,
             "detection_method": "tag", "category": "declared",
             "match_type": "spdx_identifier", "source_file": "LICENSE"}
        ], key="results")):
            found = OssliliSubprocessDetector().detect_from_directory("/repo")
        assert [lic["spdx_id"] for lic in found["licenses"]] == ["MIT"]


class TestADirectoryScanUsesTheSameRule:
    def _scan(self, evidence):
        with patch("subprocess.run", return_value=_result(evidence)):
            return OssliliSubprocessDetector().detect_from_directory("/repo")

    def test_a_declared_licence_is_reported(self):
        found = self._scan(LICENCE_FILE_LOW)
        assert [lic["spdx_id"] for lic in found["licenses"]] == ["MIT"]

    def test_a_third_party_licence_is_not(self):
        found = self._scan([
            {"detected_license": "GPL-3.0", "confidence": 1.0,
             "detection_method": "regex", "category": "third-party",
             "match_type": "license_file"}
        ])
        assert found["licenses"] == []

    def test_a_documentation_mention_is_not(self):
        found = self._scan([
            {"detected_license": "MIT", "confidence": 0.7,
             "detection_method": "regex", "category": "declared",
             "match_type": "documentation"}
        ])
        assert found["licenses"] == []


class TestWhatStillGetsIn:
    def test_a_high_score_is_enough_on_its_own(self):
        assert is_reportable(
            {"detected_license": "MIT", "confidence": 0.97,
             "detection_method": "keyword", "category": "detected",
             "match_type": "keyword"}
        )

    @pytest.mark.parametrize("method", ["tag", "spdx_identifier"])
    def test_an_exact_identifier_is_enough_at_any_score(self, method):
        assert is_reportable(
            {"detected_license": "MIT", "confidence": 0.1,
             "detection_method": method, "category": "detected",
             "match_type": "keyword"}
        )

    @pytest.mark.parametrize("match_type", [
        "license_file", "package_metadata", "spdx_identifier",
        "license_header", "text_similarity", "header_tag",
        "package_metadata_classifier", "package_metadata_file", "exact_hash",
    ])
    def test_every_way_osslili_says_a_file_declares_a_licence(self, match_type):
        assert is_reportable(
            {"detected_license": "MIT", "confidence": 0.1,
             "detection_method": "regex", "category": "declared",
             "match_type": match_type}
        )

    def test_a_pyproject_pointing_at_a_licence_file(self):
        """PEP 639. osslili reads the file pyproject.toml names, reports it
        against pyproject.toml as package_metadata_file, and caps it at 0.6.
        An allowlist that had not heard of that match type dropped it."""
        with patch("subprocess.run", return_value=_result([
            {"detected_license": "MIT", "confidence": 0.6,
             "detection_method": "regex", "category": "declared",
             "match_type": "package_metadata_file"}
        ])):
            found = OssliliSubprocessDetector().detect_from_file(
                "pyproject.toml", MIT_TEXT
            )
        assert _spdx(found) == ["MIT"]


class TestTheRuleKeepsUpWithOsslili:
    """The rule names the one match type it refuses. If osslili grows another
    weak one, this is what says so, rather than a licence quietly going
    missing months later."""

    def _declared_match_types_in_osslili(self):
        import pathlib
        import re

        import osslili

        source = pathlib.Path(osslili.__file__).parent
        found = set()
        for path in source.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            found.update(re.findall(r'DECLARED\.value,\s*"([a-z_]+)"', text))
            found.update(re.findall(r'match_type\s*=\s*"([a-z_]+)"', text))
        return found

    def test_osslili_still_emits_the_one_we_refuse(self):
        types = self._declared_match_types_in_osslili()
        assert types, "could not read osslili's match types"
        assert "documentation" in types, (
            "osslili no longer emits the match type this rule refuses; "
            "the exception may be stale"
        )

    def test_every_other_declared_type_is_accepted(self):
        for match_type in self._declared_match_types_in_osslili():
            if match_type == "documentation":
                continue
            assert is_reportable(
                {"detected_license": "MIT", "confidence": 0.1,
                 "detection_method": "regex", "category": "declared",
                 "match_type": match_type}
            ), f"{match_type} is dropped"
