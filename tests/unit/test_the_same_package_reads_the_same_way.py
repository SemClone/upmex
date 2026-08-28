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
        "licenses": sorted(lic.spdx_id for lic in (metadata.licenses or [])),
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
