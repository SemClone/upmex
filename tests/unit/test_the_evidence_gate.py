"""What upmex keeps out of osslili's evidence, and why.

osslili scores a match and also says what kind of evidence it is. Gating on
the score alone made the answer depend on the machine: the same MIT text was
scored 0.95 by one similarity backend and 0.6 by another, so a package came
back MIT locally and unlicensed in CI. These pin the rule to the evidence
rather than to the number.
"""

import json
from unittest.mock import patch

from upmex.licenses.osslili_subprocess import OssliliSubprocessDetector, is_reportable

MIT_TEXT = "MIT License\n\nPermission is hereby granted, free of charge"


def _result(evidence):
    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {"scan_results": [{"license_evidence": evidence, "copyright_evidence": []}]}
        )

    return Result()


# The two scorings of the same file, taken from a real run on each machine.
LOCAL_SCORING = [
    {"detected_license": "MIT", "confidence": 0.9, "detection_method": "keyword",
     "category": "detected", "match_type": "keyword"},
    {"detected_license": "MIT", "confidence": 0.95, "detection_method": "regex",
     "category": "declared", "match_type": "documentation"},
]
CI_SCORING = [
    {"detected_license": "MIT", "confidence": 0.9, "detection_method": "keyword",
     "category": "detected", "match_type": "keyword"},
    {"detected_license": "MIT", "confidence": 0.6, "detection_method": "regex",
     "category": "declared", "match_type": "documentation"},
]


class TestTheSameFileGivesTheSameAnswer:
    def test_the_high_scoring_machine_reports_mit(self):
        with patch("subprocess.run", return_value=_result(LOCAL_SCORING)):
            found = OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)
        assert "MIT" in [lic["spdx_id"] for lic in found]

    def test_the_low_scoring_machine_reports_mit_too(self):
        """This is the one that failed. 0.6 on a declared licence is still MIT."""
        with patch("subprocess.run", return_value=_result(CI_SCORING)):
            found = OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)
        assert "MIT" in [lic["spdx_id"] for lic in found]


class TestWhatStaysOut:
    def test_a_weak_detection_is_not_reported(self):
        """Nothing declared it, nothing matched exactly, the score is low."""
        assert not is_reportable(
            {"detected_license": "GPL-3.0", "confidence": 0.6,
             "detection_method": "keyword", "category": "detected"}
        )

    def test_a_referenced_licence_is_not_a_declared_one(self):
        """A file that mentions a licence has not declared it."""
        assert not is_reportable(
            {"detected_license": "MIT", "confidence": 0.7,
             "detection_method": "regex", "category": "referenced"}
        )

    def test_a_third_party_licence_is_not_a_declared_one(self):
        assert not is_reportable(
            {"detected_license": "MIT", "confidence": 0.7,
             "detection_method": "regex", "category": "third-party"}
        )

    def test_the_known_false_positive_stays_out_however_it_is_categorised(self):
        """Pixar is the standard Apache-2.0 confusion, and never right."""
        assert not is_reportable(
            {"detected_license": "Pixar", "confidence": 1.0,
             "detection_method": "tag", "category": "declared"}
        )

    def test_it_stays_out_of_a_real_scan_too(self):
        with patch("subprocess.run", return_value=_result([
            {"detected_license": "Pixar", "confidence": 1.0,
             "detection_method": "tag", "category": "declared"}
        ])):
            found = OssliliSubprocessDetector().detect_from_file("LICENSE", MIT_TEXT)
        assert found == []


class TestWhatStillGetsIn:
    def test_a_high_score_is_enough_on_its_own(self):
        assert is_reportable(
            {"detected_license": "MIT", "confidence": 0.97,
             "detection_method": "keyword", "category": "detected"}
        )

    def test_an_exact_identifier_is_enough_at_any_score(self):
        assert is_reportable(
            {"detected_license": "MIT", "confidence": 0.1,
             "detection_method": "spdx_identifier", "category": "detected"}
        )

    def test_a_tag_is_enough_at_any_score(self):
        assert is_reportable(
            {"detected_license": "MIT", "confidence": 0.1,
             "detection_method": "tag", "category": "detected"}
        )

    def test_declared_is_enough_at_any_score(self):
        assert is_reportable(
            {"detected_license": "MIT", "confidence": 0.1,
             "detection_method": "regex", "category": "declared"}
        )
