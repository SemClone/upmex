"""The same package has to produce the same record.

upmex reported a different author for the same file from one run to the next,
and a different set of copyright statements. A record whose content depends on
the run cannot be compared with itself, diffed in CI, or attested to.

The cause was osslili extracting copyright statements concurrently: the order
it returns them in changes every time. That order decided which statements
survived a cap of ten and which holder was listed first.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest

from upmex.core.extractor import PackageExtractor
from upmex.core.models import PackageMetadata, PackageType
from upmex.extractors.base import _in_a_settled_order

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGES = REPO_ROOT / "test-packages"


def _record(package):
    metadata = PackageExtractor().extract(str(package))
    return json.dumps({
        "copyright": metadata.copyright,
        "authors": [author.get("name") for author in (metadata.authors or [])],
        # Not sorted. The order licences come out in is part of the record,
        # so sorting here would hide exactly the kind of change this is for.
        "licenses": [lic.spdx_id for lic in (metadata.licenses or [])],
        "keywords": metadata.keywords,
    })


def _statements(*holders):
    """Records shaped like osslili's, with the file deliberately varied.

    osslili reports each distinct statement once and attaches whichever file
    reached it first, so the same statement comes back against one file on one
    run and another on the next. Anything that sorts on the file inherits that.
    """
    return [
        {"statement": f"Copyright {year} {holder}",
         "holder": holder,
         "years": [year],
         "file": f"/tmp/{index}/some_test.go"}
        for index, (holder, year) in enumerate(holders)
    ]


class TestTheOrderDoesNotDependOnTheRun:
    def test_the_same_records_in_any_order_settle_the_same_way(self):
        records = _statements(
            ("Gin Core Team", 2018), ("Gin Core Team", 2019),
            ("Manu Martinez-Almeida", 2014), ("The Go Authors", 2009),
        )
        shuffled = [records[2], records[0], records[3], records[1]]

        assert (
            [r["statement"] for r in _in_a_settled_order(records)]
            == [r["statement"] for r in _in_a_settled_order(shuffled)]
        )

    def test_and_reversing_them_changes_nothing(self):
        records = _statements(
            ("A Person", 2001), ("B Person", 2002), ("A Person", 2003),
        )

        assert (
            _in_a_settled_order(records)
            == _in_a_settled_order(list(reversed(records)))
        )

    def test_the_file_is_not_what_decides(self):
        """It cannot be: the same statement arrives against a different file
        each run, so an order built on it moves with the run."""
        records = _statements(("A Person", 2001), ("B Person", 2002))
        moved = [dict(record, file="/tmp/somewhere/else.go") for record in records]

        assert (
            [r["statement"] for r in _in_a_settled_order(records)]
            == [r["statement"] for r in _in_a_settled_order(moved)]
        )


class TestTheHolderWhoCoversMostComesFirst:
    """Whoever is named across the most files is the one whose package this
    is. Ordering on the statement alone is stable but puts a vendored
    "Copyright 2009 The Go Authors" ahead of the people who wrote it."""

    def test_the_dominant_holder_leads(self):
        """The names are chosen so that coverage and the alphabet disagree.
        With names where they agree, an ordering that ignores coverage
        entirely still passes."""
        records = _statements(
            ("Alpha Authors", 2009),
            ("Zed Core Team", 2018),
            ("Zed Core Team", 2019),
            ("Zed Core Team", 2020),
        )

        assert _in_a_settled_order(records)[0]["holder"] == "Zed Core Team"

    def test_however_the_records_arrive(self):
        records = _statements(
            ("Zed Core Team", 2018),
            ("Alpha Authors", 2009),
            ("Zed Core Team", 2019),
        )

        assert _in_a_settled_order(list(reversed(records)))[0]["holder"] == (
            "Zed Core Team"
        )

    def test_and_the_one_named_once_comes_last(self):
        records = _statements(
            ("Alpha Authors", 2009),
            ("Zed Core Team", 2018),
            ("Zed Core Team", 2019),
        )

        assert _in_a_settled_order(records)[-1]["holder"] == "Alpha Authors"

    def test_a_tie_is_broken_by_name_then_statement(self):
        records = _statements(("B Person", 2002), ("A Person", 2001))

        settled = _in_a_settled_order(records)

        assert [r["holder"] for r in settled] == ["A Person", "B Person"]


class TestEveryPackageReadsTheSameWayTwice:
    @pytest.mark.parametrize("package", sorted(
        path.name for path in PACKAGES.iterdir()
        if path.is_file() and path.suffix not in (".sh", ".txt", ".json")
    ))
    def test_it_does(self, package):
        first = _record(PACKAGES / package)
        second = _record(PACKAGES / package)

        assert hashlib.md5(first.encode()).hexdigest() == (
            hashlib.md5(second.encode()).hexdigest()
        ), package


class TestNothingIsLostToTheCap:
    """The cap was applied to the records before they were deduplicated or
    ordered, so a package with eleven statements dropped a different one each
    run, and the list of authors was cut short with them."""

    def test_every_holder_is_reported_however_many_there_are(self, tmp_path):
        source = tmp_path / "pkg"
        source.mkdir()
        for index in range(15):
            (source / f"file_{index:02d}.go").write_text(
                f"// Copyright 20{index:02d} Person {index:02d}\npackage main\n"
            )

        metadata = PackageMetadata(name="x", package_type=PackageType.GO_MODULE)
        from upmex.extractors.npm_extractor import NpmExtractor

        NpmExtractor().find_and_detect_copyrights(
            directory_path=str(source), merge_with_authors=True, metadata=metadata
        )

        assert len(metadata.authors) > 10, [a["name"] for a in metadata.authors]

    def test_the_summary_is_still_bounded(self, tmp_path):
        """It is a summary, so it may be cut. It just has to cut the same
        statements every time."""
        from upmex.extractors.base import MAX_COPYRIGHT_STATEMENTS
        from upmex.extractors.npm_extractor import NpmExtractor

        source = tmp_path / "pkg"
        source.mkdir()
        for index in range(15):
            (source / f"file_{index:02d}.go").write_text(
                f"// Copyright 20{index:02d} Person {index:02d}\npackage main\n"
            )

        summaries = set()
        for _ in range(3):
            metadata = PackageMetadata(name="x", package_type=PackageType.GO_MODULE)
            summaries.add(NpmExtractor().find_and_detect_copyrights(
                directory_path=str(source), merge_with_authors=True,
                metadata=metadata,
            ))

        assert len(summaries) == 1, summaries
        only = summaries.pop()
        assert len(only.split(";")) <= MAX_COPYRIGHT_STATEMENTS


class TestTheOrderIsTotal:
    """Two records that tie on every key would otherwise hold whatever order
    they arrived in, which is the order this exists to replace."""

    def test_identical_claims_collapse_to_one(self):
        same = {"statement": "Copyright 2024 Same", "holder": "Same"}
        records = [dict(same, file="/tmp/a.go"), dict(same, file="/tmp/b.go")]

        settled = _in_a_settled_order(records)

        assert len(settled) == 1

    def test_so_reversing_the_input_changes_nothing(self):
        same = {"statement": "Copyright 2024 Same", "holder": "Same"}
        records = [dict(same, file="/tmp/a.go"), dict(same, file="/tmp/b.go")]

        assert (
            [r["statement"] for r in _in_a_settled_order(records)]
            == [r["statement"] for r in _in_a_settled_order(list(reversed(records)))]
        )

    def test_a_holder_with_two_statements_still_keeps_both(self):
        records = _statements(("Same", 2023), ("Same", 2024))

        assert len(_in_a_settled_order(records)) == 2


class TestWhatTheOrderingSignalActuallyIs:
    """Named plainly because it is a heuristic, not a measurement. osslili
    reports each statement once however many files carry it, so the number of
    files a holder appears in is not in the record."""

    def test_it_counts_distinct_statements_not_files(self):
        records = [
            {"statement": "Copyright 2024 One Liner", "holder": "One Liner",
             "file": "/tmp/a.go"},
            {"statement": "Copyright 2009 Many Years", "holder": "Many Years",
             "file": "/tmp/b.go"},
            {"statement": "Copyright 2010 Many Years", "holder": "Many Years",
             "file": "/tmp/c.go"},
        ]

        assert _in_a_settled_order(records)[0]["holder"] == "Many Years"

    def test_and_every_holder_is_reported_whatever_the_order(self):
        records = [
            {"statement": "Copyright 2024 One Liner", "holder": "One Liner",
             "file": "/tmp/a.go"},
            {"statement": "Copyright 2009 Many Years", "holder": "Many Years",
             "file": "/tmp/b.go"},
            {"statement": "Copyright 2010 Many Years", "holder": "Many Years",
             "file": "/tmp/c.go"},
        ]

        holders = {r["holder"] for r in _in_a_settled_order(records)}

        assert holders == {"One Liner", "Many Years"}


class TestKeywordsComeOutInAnOrder:
    """A set's order depends on the hash seed, and this list is published."""

    def test_the_same_build_file_gives_the_same_order(self):
        """Run in separate processes with different hash seeds, because a
        set's order is fixed within one process and only moves between them.
        Comparing three calls in the same process cannot see this at all."""
        import subprocess
        import sys

        script = (
            "import sys; sys.path.insert(0, 'src');"
            "from upmex.extractors.gradle_extractor import GradleExtractor;"
            "print(GradleExtractor()._extract_keywords("
            "'tags = [\"web\", \"api\", \"cli\", \"server\", \"json\", \"tool\"]', False))"
        )

        orders = set()
        for seed in ("0", "1", "42", "12345"):
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=REPO_ROOT, capture_output=True, text=True,
                env={**os.environ, "PYTHONHASHSEED": seed},
            )
            assert result.returncode == 0, result.stderr
            orders.add(result.stdout.strip())

        assert len(orders) == 1, orders

    def test_and_it_is_sorted(self, tmp_path):
        from upmex.extractors.gradle_extractor import GradleExtractor

        keywords = GradleExtractor()._extract_keywords(
            'tags = ["web", "api", "cli"]\n', False
        )

        assert keywords == sorted(keywords)


class TestADirectoryScanPublishesLicencesInAnOrder:
    """The list goes straight into a Debian package's record. osslili scans
    concurrently and sorts its evidence by confidence, so two licences of
    equal confidence keep whatever order the threads finished in."""

    def _scan(self, evidence):
        from unittest.mock import patch

        from upmex.licenses.osslili_subprocess import OssliliSubprocessDetector

        payload = json.dumps({
            "scan_results": [{"license_evidence": evidence, "copyright_evidence": []}]
        })

        class Result:
            returncode = 0
            stderr = ""
            stdout = payload

        with patch("subprocess.run", return_value=Result()):
            found = OssliliSubprocessDetector().detect_from_directory("/repo")
        return [lic["spdx_id"] for lic in found["licenses"]]

    def _scan_whole(self, evidence, copyrights=()):
        """Every published field, not the identifier alone. Comparing only
        the identifier missed that the source and match_type came from
        whichever equally confident record arrived first."""
        from unittest.mock import patch

        from upmex.licenses.osslili_subprocess import OssliliSubprocessDetector

        payload = json.dumps({
            "scan_results": [{
                "license_evidence": evidence,
                "copyright_evidence": list(copyrights),
            }]
        })

        class Result:
            returncode = 0
            stderr = ""
            stdout = payload

        with patch("subprocess.run", return_value=Result()):
            return OssliliSubprocessDetector().detect_from_directory("/repo")

    def _evidence(self, *pairs):
        return [
            {"detected_license": spdx, "confidence": confidence,
             "detection_method": "tag", "category": "declared",
             "match_type": "spdx_identifier", "file": f"/repo/LICENSE-{spdx}"}
            for spdx, confidence in pairs
        ]

    def test_two_licences_of_equal_confidence_come_out_the_same_way(self):
        evidence = self._evidence(("MIT", 1.0), ("Apache-2.0", 1.0))

        assert self._scan(evidence) == self._scan(list(reversed(evidence)))

    def test_and_the_better_evidenced_one_leads(self):
        evidence = self._evidence(("Zlib", 0.96), ("Apache-2.0", 1.0))

        assert self._scan(evidence)[0] == "Apache-2.0"

    def test_however_it_arrives(self):
        evidence = self._evidence(("Apache-2.0", 1.0), ("Zlib", 0.96))

        assert self._scan(evidence)[0] == "Apache-2.0"

    def test_the_whole_record_settles_not_only_the_identifier(self):
        """Two equally confident records for one licence in one file. The
        identifier never moved; the source and match_type published alongside
        it did, because the dedupe kept whichever arrived first."""
        evidence = [
            {"detected_license": "MIT", "confidence": 1.0,
             "detection_method": "tag", "category": "declared",
             "match_type": "license_file", "file": "/repo/LICENSE"},
            {"detected_license": "MIT", "confidence": 1.0,
             "detection_method": "spdx_identifier", "category": "declared",
             "match_type": "spdx_identifier", "file": "/repo/LICENSE"},
        ]

        assert (
            self._scan_whole(evidence)["licenses"]
            == self._scan_whole(list(reversed(evidence)))["licenses"]
        )

    def test_and_the_copyrights_a_direct_caller_gets_settle_too(self):
        """Package extraction reorders them again, so only someone calling
        this function sees this order. They should still see one order."""
        copyrights = [
            {"statement": "Copyright 2024 Same", "holder": "Same",
             "years": [2024], "file": "/repo/a.go"},
            {"statement": "Copyright 2024 Same", "holder": "Same",
             "years": [2024], "file": "/repo/b.go"},
            {"statement": "Copyright 2009 Other", "holder": "Other",
             "years": [2009], "file": "/repo/c.go"},
        ]

        assert (
            self._scan_whole([], copyrights)["copyrights"]
            == self._scan_whole([], list(reversed(copyrights)))["copyrights"]
        )

    def _scan_results(self, results):
        """osslili returns a list of scan results. Sorting the evidence
        inside each one settles that one; the order of the list itself is a
        second place the arrival order can show through."""
        from unittest.mock import patch

        from upmex.licenses.osslili_subprocess import OssliliSubprocessDetector

        class Result:
            returncode = 0
            stderr = ""
            stdout = json.dumps({"scan_results": list(results)})

        with patch("subprocess.run", return_value=Result()):
            return OssliliSubprocessDetector().detect_from_directory("/repo")

    def test_the_order_of_the_scan_results_themselves_does_not_show(self):
        first = {
            "license_evidence": [
                {"detected_license": "MIT", "confidence": 1.0,
                 "detection_method": "tag", "category": "declared",
                 "match_type": "spdx_identifier", "file": "/repo/a/LICENSE"},
            ],
            "copyright_evidence": [
                {"statement": "Copyright 2024 A", "holder": "A",
                 "years": [2024], "file": "/repo/a/x.go"},
            ],
        }
        second = {
            "license_evidence": [
                {"detected_license": "Apache-2.0", "confidence": 1.0,
                 "detection_method": "tag", "category": "declared",
                 "match_type": "spdx_identifier", "file": "/repo/b/LICENSE"},
            ],
            "copyright_evidence": [
                {"statement": "Copyright 2009 B", "holder": "B",
                 "years": [2009], "file": "/repo/b/y.go"},
            ],
        }

        one = self._scan_results([first, second])
        other = self._scan_results([second, first])

        assert one["licenses"] == other["licenses"]
        assert one["copyrights"] == other["copyrights"]

    def test_the_same_licence_in_two_scan_results_settles(self):
        """The deduplication is global but the ordering was per result, so
        two records for one licence arriving in different scan results still
        let the arrival order pick which one was published."""
        mit = {"detected_license": "MIT", "confidence": 1.0,
               "category": "declared", "file": "/repo/LICENSE"}
        first = {"license_evidence": [
            dict(mit, detection_method="tag", match_type="license_file")]}
        second = {"license_evidence": [
            dict(mit, detection_method="spdx_identifier",
                 match_type="spdx_identifier")]}

        assert (
            self._scan_results([first, second])["licenses"]
            == self._scan_results([second, first])["licenses"]
        )

    def test_the_same_statement_in_two_scan_results_settles_too(self):
        same = {"statement": "Copyright 2024 Same", "holder": "Same",
                "years": [2024]}
        first = {"copyright_evidence": [dict(same, file="/repo/a.go")]}
        second = {"copyright_evidence": [dict(same, file="/repo/b.go")]}

        assert (
            self._scan_results([first, second])["copyrights"]
            == self._scan_results([second, first])["copyrights"]
        )

    def test_and_the_file_published_with_it_is_the_same_one(self):
        """The identifier never moved. What moved was the record around it."""
        same = {"statement": "Copyright 2024 Same", "holder": "Same",
                "years": [2024]}
        first = {"copyright_evidence": [dict(same, file="/repo/a.go")]}
        second = {"copyright_evidence": [dict(same, file="/repo/b.go")]}

        one = self._scan_results([first, second])["copyrights"]
        other = self._scan_results([second, first])["copyrights"]

        assert [c["file"] for c in one] == [c["file"] for c in other]


class TestTheRecordDoesNotMoveWithTheHashSeed:
    """The test above extracts twice inside one pytest process, which shares
    one hash seed, so anything ordered by a set looks settled to it.

    Replacing the author merge with a loop over a set of holders passed all
    700 tests and still gave gin four different author orders across four
    seeds. That is the bug this file is named for, green suite and all.
    """

    def _record_under(self, seed, package):
        import subprocess
        import sys

        script = (
            "import sys, json, warnings, logging;"
            "warnings.filterwarnings('ignore'); logging.disable(logging.CRITICAL);"
            "sys.path.insert(0, 'src');"
            "from upmex.core.extractor import PackageExtractor;"
            f"m = PackageExtractor().extract({str(package)!r});"
            "print(json.dumps({"
            "'copyright': m.copyright,"
            "'authors': [a.get('name') for a in (m.authors or [])],"
            "'licenses': [l.spdx_id for l in (m.licenses or [])],"
            "'keywords': m.keywords}))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT, capture_output=True, text=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    @pytest.mark.parametrize("package", [
        # The one that was unstable, and one with several copyright holders.
        "gin-v1.10.0.zip",
        "cobra-v1.8.1.zip",
    ])
    def test_four_seeds_give_one_record(self, package):
        path = PACKAGES / package
        records = {self._record_under(seed, path) for seed in (0, 1, 5, 7)}

        assert len(records) == 1, records


class TestTheHolderWithTheLongestClaimLeads:
    """Counting statements ranked a project writing one line covering eleven
    years below a third-party file carrying two. osslili expands a range, so
    the years are there to count."""

    def test_a_range_outweighs_two_separate_claims(self):
        records = [
            {"statement": "Copyright 2013-2023 The Project",
             "holder": "The Project", "years": list(range(2013, 2024))},
            {"statement": "Copyright 2009 Third Party",
             "holder": "Third Party", "years": [2009]},
            {"statement": "Copyright 2010 Third Party",
             "holder": "Third Party", "years": [2010]},
        ]

        assert _in_a_settled_order(records)[0]["holder"] == "The Project"

    def test_however_the_records_arrive(self):
        records = [
            {"statement": "Copyright 2009 Third Party",
             "holder": "Third Party", "years": [2009]},
            {"statement": "Copyright 2010 Third Party",
             "holder": "Third Party", "years": [2010]},
            {"statement": "Copyright 2013-2023 The Project",
             "holder": "The Project", "years": list(range(2013, 2024))},
        ]

        assert _in_a_settled_order(records)[0]["holder"] == "The Project"

    def test_a_holder_claiming_more_years_leads(self):
        records = [
            {"statement": "Copyright 2009 Brief", "holder": "Brief",
             "years": [2009]},
            {"statement": "Copyright 2018 Long", "holder": "Long",
             "years": [2018]},
            {"statement": "Copyright 2019 Long", "holder": "Long",
             "years": [2019]},
        ]

        assert _in_a_settled_order(records)[0]["holder"] == "Long"

    def test_records_with_no_years_fall_back_to_counting_claims(self):
        """Named so that the alphabet disagrees with the claim count. With
        names where they agree, dropping the fallback entirely still passes."""
        records = [
            {"statement": "Copyright Alpha", "holder": "Alpha"},
            {"statement": "Copyright A Zed", "holder": "Zed"},
            {"statement": "Copyright B Zed", "holder": "Zed"},
        ]

        assert _in_a_settled_order(records)[0]["holder"] == "Zed"

    def test_and_a_holder_with_years_still_beats_one_with_more_claims(self):
        """The years come first, so one dated claim outranks two undated
        ones however many there are."""
        records = [
            {"statement": "Copyright 2009 Dated", "holder": "Dated",
             "years": [2009]},
            {"statement": "Copyright A Undated", "holder": "Undated"},
            {"statement": "Copyright B Undated", "holder": "Undated"},
        ]

        assert _in_a_settled_order(records)[0]["holder"] == "Dated"

    def test_and_a_real_package_reads_the_way_it_should(self):
        """cobra states one range and nothing else, so counting statements
        gave it no weight at all."""
        metadata = PackageExtractor().extract(str(PACKAGES / "cobra-v1.8.1.zip"))

        assert metadata.authors
        assert metadata.authors[0]["name"] == "The Cobra Authors"


class TestTheOlderOutputFormatSettlesToo:
    """Reachable only with an osslili old enough to emit it, and wrong in the
    same way without ordering."""

    def _scan(self, licences):
        from unittest.mock import patch

        from upmex.licenses.osslili_subprocess import OssliliSubprocessDetector

        class Result:
            returncode = 0
            stderr = ""
            stdout = json.dumps({"results": [{"licenses": list(licences)}]})

        with patch("subprocess.run", return_value=Result()):
            return OssliliSubprocessDetector().detect_from_directory("/repo")

    def test_equal_evidence_comes_out_the_same_way(self):
        licences = [
            {"spdx_id": "MIT", "confidence": 1.0, "detection_method": "tag",
             "source_file": "/repo/LICENSE"},
            {"spdx_id": "MIT", "confidence": 1.0,
             "detection_method": "spdx_identifier", "source_file": "/repo/LICENSE"},
        ]

        assert self._scan(licences) == self._scan(list(reversed(licences)))


class TestADirectoryIsWalkedInAnOrder:
    """os.listdir returns whatever the filesystem gives, which is stable on
    one machine and not guaranteed between them."""

    def test_the_perl_extractor_does_not_walk_unordered(self):
        source = (REPO_ROOT / "src" / "upmex" / "extractors"
                  / "perl_extractor.py").read_text()

        assert "sorted(os.listdir(" in source
        assert source.count("os.listdir(") == source.count("sorted(os.listdir(")
