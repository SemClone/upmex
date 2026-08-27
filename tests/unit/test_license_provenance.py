"""What a reported licence is, and where it came from.

Every licence upmex reported came back with `file_path` None and, if its
confidence was at least 0.95, `confidence_level` exact. Both were untrue in
ways a consumer could not detect.

A similarity score of 0.988 is a very good match against a licence text. It is
not a reading of a declaration, and calling it exact told a consumer the file
had named that licence. Separately, nine extractors resolved a declared name
by writing "License: {name}" to a file and handing it to the text detector,
which then reported an SPDX identifier at confidence 1.0 from a document we
had just written: packaging's classifier says "BSD License", and that produced
BSD-3-Clause as an exact finding for a project that uses the two-clause one.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from upmex.core.models import LicenseConfidenceLevel
from upmex.licenses.osslili_subprocess import OssliliSubprocessDetector


def evidence(**overrides):
    """One osslili evidence record, in the shape the CLI emits."""
    record = {
        "file": "/tmp/whatever/LICENSE",
        "detected_license": "Apache-2.0",
        "confidence": 1.0,
        "detection_method": "tag",
        "category": "declared",
        "match_type": "spdx_identifier",
        "description": "SPDX-License-Identifier: Apache-2.0 found",
    }
    record.update(overrides)
    return record


def run_with(records):
    """Run the detector against a canned osslili response."""
    payload = json.dumps({"scan_results": [{"license_evidence": records}]})

    class Result:
        returncode = 0
        stdout = payload
        stderr = ""

    with patch("subprocess.run", return_value=Result()):
        return OssliliSubprocessDetector().detect_from_file(
            "LICENSE.txt", content="anything"
        )


class TestExactMeansTheFileNamedIt:
    def test_a_tag_match_is_exact(self):
        found = run_with([evidence(detection_method="tag", confidence=1.0)])

        assert found[0]["confidence_level"] == "exact"

    def test_an_spdx_identifier_match_is_exact(self):
        found = run_with([
            evidence(detection_method="regex", match_type="spdx_identifier")
        ])

        assert found[0]["confidence_level"] == "exact"

    @pytest.mark.parametrize("confidence", [0.999, 0.989, 0.988, 0.95])
    def test_a_similarity_match_never_is(self, confidence):
        """However close, it is a match against a licence rather than a
        reading of one. 0.988 is where packaging's BSD-2-Clause lands."""
        found = run_with([
            evidence(
                detection_method="dice-sorensen",
                match_type="text_similarity",
                confidence=confidence,
            )
        ])

        assert found[0]["confidence_level"] == "high"

    @pytest.mark.parametrize(
        "confidence,level",
        [(0.96, "high"), (0.90, "medium"), (0.5, "low")],
    )
    def test_a_weaker_similarity_is_weaker_still(self, confidence, level):
        """Tested on the mapping directly: anything below 0.95 is filtered out
        before it reaches a result, so the lower rungs are not reachable end
        to end through this detector."""
        detector = OssliliSubprocessDetector()

        assert detector._get_confidence_level(
            confidence, "dice-sorensen", "text_similarity"
        ) == level

    def test_the_method_beats_the_number_in_both_directions(self):
        """A tag match at a low score is still a reading of a declaration."""
        detector = OssliliSubprocessDetector()

        assert detector._get_confidence_level(0.4, "tag", "") == "exact"
        assert detector._get_confidence_level(1.0, "dice-sorensen", "") == "high"


class TestTheClaimCanBeChecked:
    def test_the_category_is_carried(self):
        found = run_with([evidence(category="detected")])

        assert found[0]["category"] == "detected"

    def test_the_match_type_is_carried(self):
        found = run_with([evidence(match_type="text_similarity")])

        assert found[0]["match_type"] == "text_similarity"

    def test_the_file_asked_about_is_reported_not_the_temp_copy(self):
        """The content is written to a temp file for osslili, so the path it
        reports is that copy. The name the caller asked about is the real one,
        and reporting the temp path is how file_path came back useless."""
        found = run_with([evidence(file="/var/folders/xx/tmpabc123.txt")])

        assert found[0]["file"] == "LICENSE.txt"

    def test_a_directory_scan_reports_the_file_osslili_read(self):
        """There the path is real, and it is the only provenance there is."""
        payload = json.dumps({
            "scan_results": [{
                "license_evidence": [evidence(file="/repo/LICENSE.APACHE")],
                "copyright_evidence": [],
            }]
        })

        class Result:
            returncode = 0
            stdout = payload
            stderr = ""

        with patch("subprocess.run", return_value=Result()):
            found = OssliliSubprocessDetector().detect_from_directory("/repo")

        assert found["licenses"][0]["file"] == "/repo/LICENSE.APACHE"


class TestADeclaredNameIsResolvedNotRead:
    """Nine extractors wrote "License: {name}" to a file and asked the text
    detector what it said. Whatever came back was reported as a tag match at
    confidence 1.0 from a filename we invented."""

    def _resolve(self, declared, source_file="METADATA"):
        from upmex.extractors.python_extractor import PythonExtractor

        return PythonExtractor().detect_licenses_from_declared_name(
            declared, source_file
        )

    def test_a_family_name_resolves_but_is_not_exact(self):
        """BSD names four licences. Choosing one of them is an inference."""
        resolved = self._resolve("BSD License")

        assert resolved
        assert resolved[0].confidence_level == LicenseConfidenceLevel.HIGH

    def test_the_identifier_is_still_reported(self):
        """Downgrading the certainty must not throw the answer away."""
        resolved = self._resolve("BSD License")

        assert resolved[0].spdx_id == "BSD-3-Clause"

    def test_a_name_that_is_already_the_identifier_stays_exact(self):
        """Resolving "MIT" to MIT is identity, not interpretation."""
        resolved = self._resolve("MIT")

        assert resolved[0].spdx_id == "MIT"
        assert resolved[0].confidence_level == LicenseConfidenceLevel.EXACT

    def test_it_says_the_name_was_declared_rather_than_the_text_read(self):
        resolved = self._resolve("BSD License")

        assert resolved[0].detection_method == "declared_name"
        assert resolved[0].match_type == "declared_name"
        assert resolved[0].category == "declared"

    def test_it_points_at_the_file_that_declared_it(self):
        """Not at the temporary document that was written to ask the question."""
        resolved = self._resolve("BSD License", "METADATA")

        assert resolved[0].file_path == "METADATA"

    def test_nothing_declared_resolves_to_nothing(self):
        assert self._resolve("") == []


class TestItSurvivesIntoTheReportedLicence:
    """The detector carries the provenance; the extractor that builds the
    LicenseInfo has to keep it. It was dropped there, which is why every
    licence upmex reported had file_path None however well the detector knew.
    """

    def _detect(self, records):
        from upmex.extractors.python_extractor import PythonExtractor

        payload = json.dumps({"scan_results": [{"license_evidence": records}]})

        class Result:
            returncode = 0
            stdout = payload
            stderr = ""

        with patch("subprocess.run", return_value=Result()):
            return PythonExtractor().detect_licenses_from_text(
                "anything", "LICENSE.txt"
            )

    def test_the_file_reaches_the_licence(self):
        found = self._detect([evidence()])

        assert found[0].file_path == "LICENSE.txt"

    def test_the_category_reaches_the_licence(self):
        found = self._detect([evidence(category="detected")])

        assert found[0].category == "detected"

    def test_the_match_type_reaches_the_licence(self):
        found = self._detect([
            evidence(
                match_type="text_similarity",
                detection_method="dice-sorensen",
                confidence=0.99,
            )
        ])

        assert found[0].match_type == "text_similarity"

    def test_the_level_reaches_the_licence(self):
        found = self._detect([
            evidence(
                match_type="text_similarity",
                detection_method="dice-sorensen",
                confidence=0.99,
            )
        ])

        assert found[0].confidence_level == LicenseConfidenceLevel.HIGH


class TestADeclaredNameWithNoFileToPointAt:
    """Several extractors resolve a name they read from a structure rather
    than a named file. Naming a file there would be inventing one."""

    def test_no_source_file_means_no_file_path(self):
        from upmex.extractors.python_extractor import PythonExtractor

        resolved = PythonExtractor().detect_licenses_from_declared_name("MIT", None)

        assert resolved
        assert resolved[0].file_path is None

    def test_it_is_not_the_placeholder_the_detector_uses(self):
        """The text detector calls an unnamed document "content", and
        reporting that as the file it came from would be a fiction."""
        from upmex.extractors.python_extractor import PythonExtractor

        resolved = PythonExtractor().detect_licenses_from_declared_name("MIT", None)

        assert resolved[0].file_path != "content"


class TestACompoundExpressionIsAStatement:
    """"MIT OR Apache-2.0" is a choice the package offers. Reporting one arm
    says something the package did not: a consumer who may not use Apache-2.0
    needs to see MIT is on offer, and the other way round.
    """

    def _resolve(self, declared):
        from upmex.extractors.python_extractor import PythonExtractor

        return PythonExtractor().detect_licenses_from_declared_name(declared, "META")

    @pytest.mark.parametrize(
        "expression",
        [
            "MIT OR Apache-2.0",
            "Apache-2.0 AND MIT",
            "GPL-2.0-only WITH Classpath-exception-2.0",
            "MIT or Apache-2.0",
        ],
    )
    def test_it_is_kept_whole(self, expression):
        resolved = self._resolve(expression)

        assert len(resolved) == 1
        assert resolved[0].spdx_id == expression.strip()

    def test_it_is_exact_because_it_is_what_was_written(self):
        resolved = self._resolve("MIT OR Apache-2.0")

        assert resolved[0].confidence_level == LicenseConfidenceLevel.EXACT
        assert resolved[0].detection_method == "declared_expression"

    @pytest.mark.parametrize(
        "name",
        [
            "MIT",
            "Standard ML of New Jersey",       # St-AND-ard
            "Sun Industry Standards Source License",
            "Vim",
            "Nordic Widget Licence",
        ],
    )
    def test_a_name_containing_the_letters_is_not_an_expression(self, name):
        """The separator is a word on its own, not a substring.

        Matched as a substring, "Standard" makes every licence with it in its
        name read as a conjunction, and the whole name is then reported
        verbatim as though it were an SPDX expression.
        """
        from upmex.extractors.base import _COMPOUND_EXPRESSION

        assert _COMPOUND_EXPRESSION.search(name) is None, name

    def test_a_resolvable_name_is_still_a_name(self):
        resolved = self._resolve("MIT")

        assert resolved[0].detection_method == "declared_name"


class TestTheOutputCarriesItToo:
    """Provenance that stops at the dataclass is provenance a consumer of the
    JSON never sees."""

    def _document(self, **license_fields):
        from upmex.core.models import LicenseInfo, PackageMetadata, PackageType

        metadata = PackageMetadata(name="p", version="1", package_type=PackageType.NPM)
        metadata.licenses = [LicenseInfo(**license_fields)]
        return metadata.to_dict()

    def test_the_category_is_published(self):
        document = self._document(
            spdx_id="JSON", name="JSON", confidence=0.98,
            confidence_level=LicenseConfidenceLevel.HIGH,
            category="detected", match_type="text_similarity",
        )

        assert document["licensing"]["declared_licenses"][0]["category"] == "detected"

    def test_the_match_type_is_published(self):
        document = self._document(
            spdx_id="JSON", name="JSON", confidence=0.98,
            confidence_level=LicenseConfidenceLevel.HIGH,
            category="detected", match_type="text_similarity",
        )

        assert document["licensing"]["declared_licenses"][0]["match_type"] == (
            "text_similarity"
        )

    def test_a_declaration_and_a_recognition_are_distinguishable(self):
        """Which is the whole point: same identifier, different standing."""
        declared = self._document(
            spdx_id="MIT", name="MIT", confidence=1.0,
            confidence_level=LicenseConfidenceLevel.EXACT,
            category="declared", match_type="spdx_identifier",
        )["licensing"]["declared_licenses"][0]
        recognised = self._document(
            spdx_id="MIT", name="MIT", confidence=0.98,
            confidence_level=LicenseConfidenceLevel.HIGH,
            category="detected", match_type="text_similarity",
        )["licensing"]["declared_licenses"][0]

        assert declared["spdx_id"] == recognised["spdx_id"]
        assert declared["category"] != recognised["category"]
        assert declared["confidence_level"] != recognised["confidence_level"]


class TestEveryDeclaredNameGoesThroughOneGate:
    """Nine extractors had the same block copied into them. Converting five
    left npm, Ruby, Rust, Gradle, Maven and NuGet still reporting an inferred
    identifier as an exact tag match."""

    def test_no_extractor_synthesises_a_licence_document_any_more(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[2] / "src" / "upmex"
        offenders = []
        for path in root.rglob("*.py"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if 'formatted_text = f"License: ' in line:
                    offenders.append(f"{path.name}:{number}")

        # The ones that remain read the contents of a real licence file, where
        # a short file holding just an identifier is the file declaring it.
        for offender in offenders:
            assert offender.startswith(("go_extractor", "rust_extractor")), offender
