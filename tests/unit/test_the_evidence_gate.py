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


class TestAMentionIsNotADeclaration:
    """osslili labels a pattern match in any .md/.rst/.txt/.adoc file
    "declared" with match_type "documentation"."""

    def test_a_readme_mentioning_mit_is_not_reported(self):
        assert not is_reportable(
            {"detected_license": "MIT", "confidence": 0.7,
             "detection_method": "regex", "category": "declared",
             "match_type": "documentation"}
        )

    def test_not_through_a_real_scan_either(self):
        with patch("subprocess.run", return_value=_result([
            {"detected_license": "MIT", "confidence": 0.7,
             "detection_method": "regex", "category": "declared",
             "match_type": "documentation"}
        ])):
            found = OssliliSubprocessDetector().detect_from_file("README.md", MIT_TEXT)
        assert found == []

    def test_but_a_high_score_still_carries_it(self):
        """A near-exact text match is a licence however the file is named."""
        assert is_reportable(
            {"detected_license": "MIT", "confidence": 0.99,
             "detection_method": "regex", "category": "declared",
             "match_type": "documentation"}
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
