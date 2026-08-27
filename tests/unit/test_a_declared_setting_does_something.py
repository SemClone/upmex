"""Every setting the configuration declares has to change something.

A setting that is declared, documented and mapped to an environment variable,
and that no code reads, is worse than an absent one: it reads as a supported
control, and someone sets it and believes it took effect. This is the third
time that has been found here, so the last test in this file is the one that
matters most - it fails when a new setting arrives with no reader.
"""

import json
import logging
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from upmex.cli import cli
from upmex.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "upmex"


def _run(tmp_path, config, *args):
    path = tmp_path / "upmex.json"
    path.write_text(json.dumps(config))
    return CliRunner().invoke(cli, ["--config", str(path), *args])


@pytest.fixture
def package(tmp_path):
    """A real npm package, so extract has something to report."""
    import tarfile

    source = tmp_path / "package"
    source.mkdir(exist_ok=True)
    (source / "package.json").write_text(
        json.dumps({"name": "express", "version": "4.18.2", "license": "MIT"})
    )
    archive = tmp_path / "express.tgz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source / "package.json", arcname="package/package.json")
    return str(archive)


class TestOutputFormat:
    def test_the_configured_format_is_used(self, tmp_path, package):
        result = _run(tmp_path, {"output": {"format": "text"}}, "extract", package)

        assert result.exit_code == 0, result.output
        assert result.stdout.startswith("Package:")

    def test_the_flag_still_wins(self, tmp_path, package):
        result = _run(tmp_path, {"output": {"format": "text"}},
                      "extract", package, "--format", "json")

        json.loads(result.stdout)

    def test_json_when_nothing_says_otherwise(self, tmp_path, package):
        result = _run(tmp_path, {}, "extract", package)

        json.loads(result.stdout)


class TestPrettyPrint:
    def test_compact_by_default(self, tmp_path, package):
        """What upmex has always emitted. The setting said True while nothing
        read it, so honouring it as shipped would reformat everyone's output."""
        result = _run(tmp_path, {}, "extract", package)

        assert len(result.stdout.strip().splitlines()) == 1

    def test_the_configured_value_is_used(self, tmp_path, package):
        result = _run(tmp_path, {"output": {"pretty_print": True}}, "extract", package)

        assert len(result.stdout.strip().splitlines()) > 10
        json.loads(result.stdout)

    def test_the_flag_still_wins(self, tmp_path, package):
        result = _run(tmp_path, {"output": {"pretty_print": True}},
                      "extract", package, "--no-pretty")

        assert len(result.stdout.strip().splitlines()) == 1


class TestIncludeRawMetadata:
    def test_absent_by_default(self, tmp_path, package):
        document = json.loads(_run(tmp_path, {}, "extract", package).stdout)

        assert "raw_metadata" not in document

    def test_present_when_asked_for(self, tmp_path, package):
        document = json.loads(
            _run(tmp_path, {"output": {"include_raw_metadata": True}},
                 "extract", package).stdout
        )

        assert document["raw_metadata"]["name"] == "express"

    def test_it_is_what_the_extractor_read(self, tmp_path, package):
        """Not a copy of the interpreted record under another name."""
        document = json.loads(
            _run(tmp_path, {"output": {"include_raw_metadata": True}},
                 "extract", package).stdout
        )

        assert document["raw_metadata"]["license"] == "MIT"
        assert "licensing" not in document["raw_metadata"]


class TestLogging:
    def _level_after(self, tmp_path, config, *args):
        logging.getLogger().setLevel(logging.NOTSET)
        _run(tmp_path, config, *args)
        return logging.getLevelName(logging.getLogger().level)

    def test_the_configured_level_is_applied(self, tmp_path, package):
        assert self._level_after(
            tmp_path, {"logging": {"level": "ERROR"}}, "extract", package
        ) == "ERROR"

    def test_verbose_still_wins(self, tmp_path, package):
        """Someone typing a flag is asking about this run, not every run."""
        assert self._level_after(
            tmp_path, {"logging": {"level": "ERROR"}}, "-v", "extract", package
        ) == "DEBUG"

    def test_quiet_still_wins(self, tmp_path, package):
        assert self._level_after(
            tmp_path, {"logging": {"level": "DEBUG"}}, "-q", "extract", package
        ) == "ERROR"

    def test_info_when_nothing_says_otherwise(self, tmp_path, package):
        assert self._level_after(tmp_path, {}, "extract", package) == "INFO"

    def test_a_level_that_is_not_one_does_not_stop_the_run(self, tmp_path, package):
        result = _run(tmp_path, {"logging": {"level": "LOUD"}}, "extract", package)

        assert result.exit_code == 0, result.output
        json.loads(result.stdout)

    def test_the_configured_format_is_applied(self, tmp_path, package):
        _run(tmp_path, {"logging": {"format": "SEEN %(levelname)s %(message)s"}},
             "extract", package)
        formats = [
            handler.formatter._fmt
            for handler in logging.getLogger().handlers
            if handler.formatter is not None
        ]

        assert "SEEN %(levelname)s %(message)s" in formats

    def test_the_configured_file_is_written(self, tmp_path, package):
        log = tmp_path / "upmex.log"
        broken = tmp_path / "broken.whl"
        broken.write_bytes(b"not a zip")

        _run(tmp_path, {"logging": {"level": "DEBUG", "file": str(log)}},
             "extract", str(broken))
        for handler in list(logging.getLogger().handlers):
            handler.close()

        assert log.exists() and log.read_text().strip()

    def test_a_log_file_that_cannot_be_opened_does_not_stop_the_run(
        self, tmp_path, package
    ):
        """Refusing to extract because a log file could not be opened would be
        the worse failure, and the record still has to reach stdout intact."""
        result = _run(
            tmp_path,
            {"logging": {"file": str(tmp_path / "no-such-dir" / "x.log")}},
            "extract", package,
        )

        assert result.exit_code == 0, result.output
        json.loads(result.stdout)


class TestSchemaVersionIsNotAPreference:
    """It describes the document, so the document owns it. As a setting it
    only let a caller make the output lie about its own shape."""

    def test_it_is_no_longer_declared(self):
        assert "schema_version" not in Config.DEFAULT_CONFIG["output"]

    def test_but_the_document_still_carries_one(self, tmp_path, package):
        document = json.loads(_run(tmp_path, {}, "extract", package).stdout)

        assert document["extraction_info"]["schema_version"]

    def test_and_setting_it_does_not_change_it(self, tmp_path, package):
        document = json.loads(
            _run(tmp_path, {"output": {"schema_version": "9.9.9"}},
                 "extract", package).stdout
        )

        assert document["extraction_info"]["schema_version"] != "9.9.9"


def _declared_keys(node, prefix=""):
    for key, value in node.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _declared_keys(value, f"{path}.")
        else:
            yield path


class TestEverySettingHasAReader:
    """The test that keeps this from happening a fourth time.

    Twice now a block of settings was declared, documented and mapped to
    environment variables while no code read any of it: the api.clearlydefined
    block, then output.* and logging.*. Both were found by a person noticing,
    which is not a mechanism.
    """

    def _source(self):
        """Everything except config.py, which is where the settings are
        declared. Including it made this test pass on its own declaration:
        DEFAULT_CONFIG holds the section name and the key together, which is
        exactly the shape a nested read has."""
        return "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in SRC.rglob("*.py")
            if path.name != "config.py"
        )

    def test_the_sweep_reads_the_package(self):
        """Without this the test below passes by reading nothing."""
        source = self._source()

        assert len(source) > 50_000, len(source)
        assert "setting(config," in source

    def test_the_sweep_excludes_the_declaration(self):
        """The whole point. If config.py were swept, a setting nothing reads
        would match its own DEFAULT_CONFIG entry."""
        assert "DEFAULT_CONFIG" not in self._source()

    @pytest.mark.parametrize("key", sorted(_declared_keys(Config.DEFAULT_CONFIG)))
    def test_it_is_read_somewhere(self, key):
        source = self._source()
        leaf = key.rsplit(".", 1)[-1]

        # Either the whole dotted path, as setting() and Config.get() take it,
        # or the section and the leaf named together the way a nested read
        # spells it.
        whole = re.search(rf"['\"]{re.escape(key)}['\"]", source)
        section = key.rsplit(".", 1)[0]
        nested = re.search(
            rf"['\"]{re.escape(section)}['\"].{{0,200}}['\"]{re.escape(leaf)}['\"]",
            source,
            re.DOTALL,
        )

        assert whole or nested, f"{key} is declared and nothing reads it"

    @pytest.mark.parametrize(
        "variable,key", sorted(Config.ENV_VAR_MAPPING.items())
    )
    def test_every_environment_variable_points_at_a_real_setting(self, variable, key):
        if "*" in key:
            pytest.skip(f"{variable} is a wildcard over a section")

        node = Config.DEFAULT_CONFIG
        for part in key.split("."):
            assert isinstance(node, dict) and part in node, (
                f"{variable} maps to {key}, which the defaults do not declare"
            )
            node = node[part]


class TestMaxFileSize:
    """Declared as a limit and consulted by nothing, so it protected nothing."""

    def test_a_package_over_the_limit_is_refused(self, tmp_path, package):
        result = _run(tmp_path, {"extraction": {"max_file_size": 10}},
                      "extract", package)

        assert result.exit_code == 1
        assert "over the" in result.output + str(result.stderr or "")

    def test_and_the_limit_is_named_in_the_message(self, tmp_path, package):
        result = _run(tmp_path, {"extraction": {"max_file_size": 10}},
                      "extract", package)

        assert "extraction.max_file_size" in result.output + str(result.stderr or "")

    def test_a_package_under_it_is_read(self, tmp_path, package):
        result = _run(tmp_path, {"extraction": {"max_file_size": 10_000_000}},
                      "extract", package)

        assert json.loads(result.stdout)["package"]["name"] == "express"

    def test_the_shipped_default_reads_everything_here(self, tmp_path, package):
        result = _run(tmp_path, {}, "extract", package)

        assert json.loads(result.stdout)["package"]["name"] == "express"

    def test_it_is_read_from_the_configuration_the_caller_passed(
        self, tmp_path, package
    ):
        """Not from a fresh Config(), which sees the defaults and the
        environment but not the file given with --config."""
        import os

        assert "PME_MAX_FILE_SIZE" not in os.environ
        result = _run(tmp_path, {"extraction": {"max_file_size": 10}},
                      "extract", package)

        assert result.exit_code == 1


class TestTempDir:
    """Fifteen extractors unpack into tempfile.TemporaryDirectory() and none
    of them knew about the setting."""

    def test_temporary_work_lands_in_the_configured_directory(self, tmp_path):
        import tempfile

        from upmex.cli import _configure_temp_dir

        elsewhere = tmp_path / "somewhere-else"
        elsewhere.mkdir()
        original = tempfile.tempdir
        try:
            _configure_temp_dir({"extraction": {"temp_dir": str(elsewhere)}})
            with tempfile.TemporaryDirectory() as created:
                assert Path(created).parent == elsewhere
        finally:
            tempfile.tempdir = original

    def test_nothing_changes_when_it_is_unset(self, tmp_path):
        import tempfile

        from upmex.cli import _configure_temp_dir

        original = tempfile.tempdir
        try:
            _configure_temp_dir({})
            assert tempfile.tempdir == original
        finally:
            tempfile.tempdir = original

    def test_a_directory_that_is_not_one_is_reported_and_ignored(self, tmp_path, package):
        """Refusing to run because a temp directory is wrong would be worse
        than using the system one, but saying nothing would be worse still."""
        result = _run(
            tmp_path,
            {"extraction": {"temp_dir": str(tmp_path / "no-such-place")}},
            "extract", package,
        )

        assert result.exit_code == 0, result.output
        json.loads(result.stdout)
