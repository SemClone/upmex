"""Every setting the configuration declares has to change something.

A setting that is declared, documented and mapped to an environment variable,
and that no code reads, is worse than an absent one: it reads as a supported
control, and someone sets it and believes it took effect. This is the third
time that has been found here, so the last test in this file is the one that
matters most - it fails when a new setting arrives with no reader.
"""

import ast
import json
import logging
import sys
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


# Things that name a setting without reading it. Each one satisfied the older
# grep-based sweep, which is how a setting could arrive with a TODO instead of
# a reader and the suite stay green.
ATTACKS_THAT_ARE_NOT_READERS = [
    "# TODO: wire with setting(config, 'output.made_up', False)",
    '"""Docstring mentioning setting(config, \'output.made_up\')."""',
    "if False:\n    setting(config, 'output.made_up', None)",
    "import click\n@click.option('-x', help='[config: output.made_up]')\ndef f(x):\n    pass",
]

class _DropDeadBranches(ast.NodeTransformer):
    """Remove the body of `if False:` and keep the else.

    A call that cannot run is not a reader, and a call parked under a false
    condition is the shape a setting waiting to be wired takes.
    """

    def visit_If(self, node):
        self.generic_visit(node)
        test = node.test
        if isinstance(test, ast.Constant) and not test.value:
            return node.orelse or None
        return node


def _without_dead_branches(tree):
    return ast.fix_missing_locations(_DropDeadBranches().visit(tree))


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

    def _keys_actually_read(self):
        """Every configuration key the package really looks up.

        Parsed, not grepped. Grepping counted a comment, a docstring, dead
        code under `if False`, and the text of a --help entry as readers, so
        a plausible TODO naming the call it had not written yet satisfied the
        whole suite. The parser sees calls; it cannot see a comment at all.
        """
        found = set()

        def literal(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            return None

        for path in SRC.rglob("*.py"):
            if path.name == "config.py":
                # Where the settings are declared. A declaration is not a read.
                continue
            tree = _without_dead_branches(
                ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            )
            for node in ast.walk(tree):
                # setting(config, 'a.b.c', default) and config.get('a.b.c')
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "id", None) or getattr(
                        node.func, "attr", None)
                    if name in ("setting", "get"):
                        for argument in node.args:
                            text = literal(argument)
                            if text:
                                found.add(text)
                # config['a']['b']['c'], as a nested read spells it
                if isinstance(node, ast.Subscript):
                    parts = []
                    current = node
                    while isinstance(current, ast.Subscript):
                        text = literal(current.slice)
                        if text is None:
                            break
                        parts.append(text)
                        current = current.value
                    if len(parts) > 1:
                        found.add(".".join(reversed(parts)))

        return found

    def test_the_sweep_reads_the_package(self):
        """Without this the test below passes by reading nothing."""
        read = self._keys_actually_read()

        assert len(read) > 10, sorted(read)
        assert "api.clearlydefined.enabled" in read

    @pytest.mark.parametrize("key", sorted(_declared_keys(Config.DEFAULT_CONFIG)))
    def test_it_is_read_somewhere(self, key):
        assert key in self._keys_actually_read(), (
            f"{key} is declared and nothing reads it"
        )

    @pytest.mark.parametrize("attack", ATTACKS_THAT_ARE_NOT_READERS)
    def test_what_does_not_count_as_a_reader(self, attack, tmp_path, monkeypatch):
        """The fourth recurrence, attempted. A comment naming the call that
        was never written used to satisfy the whole suite."""
        (tmp_path / "pretend.py").write_text(attack)
        monkeypatch.setattr(
            sys.modules[__name__], "SRC", tmp_path
        )

        assert "output.made_up" not in self._keys_actually_read()

    def test_but_a_real_lookup_does(self, tmp_path, monkeypatch):
        """The other half, so the parser is not simply refusing everything."""
        (tmp_path / "pretend.py").write_text(
            "value = setting(config, 'output.made_up', None)\n"
        )
        monkeypatch.setattr(sys.modules[__name__], "SRC", tmp_path)

        assert "output.made_up" in self._keys_actually_read()

    @pytest.mark.parametrize(
        "variable,key", sorted(Config.ENV_VAR_MAPPING.items())
    )
    def test_every_environment_variable_points_at_a_real_setting(self, variable, key):
        if "*" in key:
            # A wildcard stands for every subsection, so check them all.
            # Skipping meant a typo in the leaf, api.*.timeot, would pass
            # while writing a setting nothing declares.
            before, leaf = key.split(".*.")
            section = Config.DEFAULT_CONFIG
            for part in before.split("."):
                assert part in section, f"{variable} maps to a section that does not exist"
                section = section[part]

            assert section, f"{variable} covers an empty section"
            for name, subsection in section.items():
                assert leaf in subsection, (
                    f"{variable} maps to {key}, and {before}.{name} has no {leaf}"
                )
            return

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

    def _where_the_extraction_unpacked(self, monkeypatch):
        """Record the parent of every temporary directory made during an
        extraction, which is the thing the setting is supposed to move.
        Checking tempfile.tempdir after construction instead would pass even
        if the extraction itself used the wrong directory."""
        import tempfile

        seen = []
        real = tempfile.TemporaryDirectory

        class Recording(real):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                seen.append(Path(self.name).parent)

        monkeypatch.setattr(tempfile, "TemporaryDirectory", Recording)
        return seen

    def test_the_extraction_unpacks_into_the_configured_directory(
        self, tmp_path, package, monkeypatch
    ):
        from upmex.core.extractor import PackageExtractor

        elsewhere = tmp_path / "somewhere-else"
        elsewhere.mkdir()
        seen = self._where_the_extraction_unpacked(monkeypatch)

        PackageExtractor({"extraction": {"temp_dir": str(elsewhere)}}).extract(package)

        assert seen, "the extraction made no temporary directory"
        assert all(parent == elsewhere for parent in seen), seen

    def test_a_library_caller_gets_it_too(self, tmp_path, package, monkeypatch):
        """It used to be applied by the command, so building the extractor
        directly, which is what the documentation shows, did nothing."""
        from upmex.config import Config
        from upmex.core.extractor import PackageExtractor

        elsewhere = tmp_path / "lib-temp"
        elsewhere.mkdir()
        config_file = tmp_path / "upmex.json"
        config_file.write_text(
            json.dumps({"extraction": {"temp_dir": str(elsewhere)}})
        )
        seen = self._where_the_extraction_unpacked(monkeypatch)

        PackageExtractor(Config(str(config_file)).to_dict()).extract(package)

        assert seen and all(parent == elsewhere for parent in seen), seen

    def test_one_extractor_does_not_decide_where_another_unpacks(
        self, tmp_path, package, monkeypatch
    ):
        """Applied once at construction, the second extractor built would set
        the process-wide value and the first would then unpack under it."""
        from upmex.core.extractor import PackageExtractor

        mine = tmp_path / "mine"
        mine.mkdir()
        theirs = tmp_path / "theirs"
        theirs.mkdir()

        first = PackageExtractor({"extraction": {"temp_dir": str(mine)}})
        PackageExtractor({"extraction": {"temp_dir": str(theirs)}})
        seen = self._where_the_extraction_unpacked(monkeypatch)

        first.extract(package)

        assert seen and all(parent == mine for parent in seen), seen

    def test_a_host_application_keeps_its_own_setting(self, tmp_path, package):
        """tempfile.tempdir belongs to the process, not to upmex."""
        import tempfile

        from upmex.core.extractor import PackageExtractor

        chosen = tmp_path / "the-host-chose-this"
        chosen.mkdir()
        original = tempfile.tempdir
        tempfile.tempdir = str(chosen)
        try:
            PackageExtractor({"extraction": {"temp_dir": str(tmp_path)}}).extract(package)

            assert tempfile.tempdir == str(chosen)
        finally:
            tempfile.tempdir = original

    def test_and_keeps_it_when_upmex_is_configured_with_nothing(
        self, tmp_path, package
    ):
        import tempfile

        from upmex.core.extractor import PackageExtractor

        chosen = tmp_path / "host-choice"
        chosen.mkdir()
        original = tempfile.tempdir
        tempfile.tempdir = str(chosen)
        try:
            PackageExtractor({}).extract(package)

            assert tempfile.tempdir == str(chosen)
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

    def test_and_the_extraction_uses_the_system_directory_instead(
        self, tmp_path, package, monkeypatch, caplog
    ):
        """Not the directory that does not exist. Pointing tempfile at a
        missing path makes every unpack raise, and those are caught, so the
        record comes back thin with nothing saying why."""
        import tempfile

        from upmex.core.extractor import PackageExtractor

        missing = tmp_path / "no-such-place"
        seen = self._where_the_extraction_unpacked(monkeypatch)

        with caplog.at_level(logging.WARNING):
            PackageExtractor(
                {"extraction": {"temp_dir": str(missing)}}
            ).extract(package)

        assert seen, "the extraction made no temporary directory"
        assert all(parent != missing for parent in seen), seen
        assert all(
            parent == Path(tempfile.gettempdir()) for parent in seen
        ), seen
        assert "is not a directory" in caplog.text


class TestTheLimitAppliesEverywhere:
    """Not only when the command is the caller, and not only when the number
    is one Python calls true."""

    def test_a_limit_of_zero_refuses_everything(self, tmp_path, package):
        """Zero is a limit, not an absence of one. Testing truthiness instead
        of presence made 0 mean unlimited."""
        result = _run(tmp_path, {"extraction": {"max_file_size": 0}},
                      "extract", package)

        assert result.exit_code == 1

    def test_a_library_caller_gets_the_default_limit(self, package):
        """A bare PackageExtractor() ran with no configuration at all, so the
        limit protected the command and nobody else."""
        from upmex.config import Config
        from upmex.core.extractor import PackageExtractor

        extractor = PackageExtractor()

        assert extractor.config["extraction"]["max_file_size"] == (
            Config.DEFAULT_CONFIG["extraction"]["max_file_size"]
        )

    def test_and_the_environment_reaches_a_library_caller(self, package, monkeypatch):
        from upmex.core.extractor import PackageExtractor

        monkeypatch.setenv("PME_MAX_FILE_SIZE", "10")

        with pytest.raises(ValueError, match="over the"):
            PackageExtractor().extract(package)

    def test_the_package_is_refused_before_anything_opens_it(
        self, tmp_path, package, monkeypatch
    ):
        """Detecting the type reads inside the archive, so checking the size
        afterwards read the package the limit exists to avoid reading."""
        from upmex.core import extractor as extractor_module

        opened = []
        real = extractor_module.detect_package_type
        monkeypatch.setattr(
            extractor_module, "detect_package_type",
            lambda path: opened.append(path) or real(path),
        )

        result = _run(tmp_path, {"extraction": {"max_file_size": 10}},
                      "extract", package)

        assert result.exit_code == 1
        assert opened == [], "the package was read before being refused"


class TestTheLogFileDoesNotOutliveItsRun:
    def test_a_second_run_without_one_stops_writing_to_the_first(
        self, tmp_path, package
    ):
        """The handler was added and never removed, so a run configured with
        no log file kept writing to the file of the run before it."""
        log = tmp_path / "first.log"

        _run(tmp_path, {"logging": {"level": "DEBUG", "file": str(log)}},
             "extract", package)
        for handler in logging.getLogger().handlers:
            handler.flush()
        after_first = log.read_text() if log.exists() else ""

        _run(tmp_path, {"logging": {"level": "DEBUG"}}, "extract", package)
        for handler in logging.getLogger().handlers:
            handler.flush()
        after_second = log.read_text() if log.exists() else ""

        assert after_second == after_first

    def test_and_a_different_file_does_not_write_to_both(self, tmp_path, package):
        first = tmp_path / "first.log"
        second = tmp_path / "second.log"
        broken = tmp_path / "broken.whl"
        broken.write_bytes(b"not a zip")

        _run(tmp_path, {"logging": {"level": "DEBUG", "file": str(first)}},
             "extract", str(broken))
        for handler in logging.getLogger().handlers:
            handler.flush()
        after_first = first.read_text() if first.exists() else ""

        _run(tmp_path, {"logging": {"level": "DEBUG", "file": str(second)}},
             "extract", str(broken))
        for handler in logging.getLogger().handlers:
            handler.flush()

        assert first.read_text() == after_first
        assert second.exists() and second.read_text().strip()


class TestTheLimitReachesEveryCommand:
    """Detecting a type opens the archive too, so a limit that only guarded
    extract left the largest packages being read by the smallest command."""

    def test_detect_refuses_an_oversized_package(self, tmp_path, package):
        result = _run(tmp_path, {"extraction": {"max_file_size": 10}},
                      "detect", package)

        assert result.exit_code == 1
        assert "over the" in result.output + str(result.stderr or "")

    def test_detect_still_works_under_the_limit(self, tmp_path, package):
        result = _run(tmp_path, {"extraction": {"max_file_size": 10_000_000}},
                      "detect", package)

        assert result.exit_code == 0
        assert result.stdout.strip() == "npm"

    def test_license_refuses_one_too(self, tmp_path, package):
        result = _run(tmp_path, {"extraction": {"max_file_size": 10}},
                      "license", package)

        assert result.exit_code == 1

    def test_a_limit_that_is_not_a_number_is_reported_and_ignored(
        self, tmp_path, package, caplog
    ):
        """PME_MAX_FILE_SIZE=500MB used to reach the comparison and fail
        there, once per package, with a message about int and str."""
        from upmex.core.extractor import refuse_if_too_large

        with caplog.at_level(logging.WARNING):
            refuse_if_too_large(package, {"extraction": {"max_file_size": "500MB"}})

        assert "not a number of bytes" in caplog.text

    def test_and_the_command_still_runs(self, tmp_path, package, monkeypatch):
        monkeypatch.setenv("PME_MAX_FILE_SIZE", "500MB")
        result = _run(tmp_path, {}, "extract", package)

        assert result.exit_code == 0, result.output
        json.loads(result.stdout)


class TestAFormatThatIsNotOne:
    def test_it_is_refused_before_the_work(self, tmp_path, package, monkeypatch):
        """Discovered after extraction and every API call had finished, a typo
        threw all of that away."""
        from upmex.core import extractor as extractor_module

        extracted = []
        real = extractor_module.PackageExtractor.extract
        monkeypatch.setattr(
            extractor_module.PackageExtractor, "extract",
            lambda self, path: extracted.append(path) or real(self, path),
        )

        result = _run(tmp_path, {"output": {"format": "xml"}}, "extract", package)

        assert result.exit_code == 1
        assert extracted == [], "the package was extracted before the format was checked"

    def test_and_the_message_names_the_value(self, tmp_path, package):
        result = _run(tmp_path, {"output": {"format": "xml"}}, "extract", package)

        assert "xml" in result.output + str(result.stderr or "")


class TestANumericLogLevel:
    def test_it_is_used_rather_than_silently_becoming_info(self, tmp_path, package):
        logging.getLogger().setLevel(logging.NOTSET)
        _run(tmp_path, {"logging": {"level": 10}}, "extract", package)

        assert logging.getLogger().level == 10

    def test_as_a_string_too(self, tmp_path, package):
        logging.getLogger().setLevel(logging.NOTSET)
        _run(tmp_path, {"logging": {"level": "30"}}, "extract", package)

        assert logging.getLogger().level == 30


class TestTheTemporaryScopeHoldsUnderPressure:
    def test_an_exception_inside_it_still_restores_the_previous_value(
        self, tmp_path, package
    ):
        """The limit raises from inside the scope, which is the shape that
        would leave the directory set for the rest of the process."""
        import tempfile

        from upmex.core.extractor import PackageExtractor

        elsewhere = tmp_path / "scoped"
        elsewhere.mkdir()
        original = tempfile.tempdir
        try:
            extractor = PackageExtractor({
                "extraction": {"temp_dir": str(elsewhere), "max_file_size": 10}
            })
            with pytest.raises(ValueError):
                extractor.extract(package)

            assert tempfile.tempdir == original
        finally:
            tempfile.tempdir = original

    def test_two_threads_do_not_take_each_others_directory(self, tmp_path, package):
        """tempfile.tempdir is one value for the whole process. Without a lock
        one thread unpacks under the other's directory, and the one that
        finishes second restores what the first had saved, leaving it set."""
        import tempfile
        import threading

        from upmex.core.extractor import PackageExtractor

        directories = {}
        for name in ("a", "b"):
            directory = tmp_path / name
            directory.mkdir()
            directories[name] = directory

        original = tempfile.tempdir
        seen = []
        real = tempfile.TemporaryDirectory

        class Recording(real):
            def __init__(self, *args, **kwargs):
                # What the extraction is about to unpack into, and who is
                # doing it. One recorder for both threads, because installing
                # one per thread is itself a race.
                seen.append(
                    (threading.current_thread().name, tempfile.tempdir)
                )
                super().__init__(*args, **kwargs)

        def run(name):
            PackageExtractor(
                {"extraction": {"temp_dir": str(directories[name])}}
            ).extract(package)

        tempfile.TemporaryDirectory = Recording
        try:
            threads = [
                threading.Thread(target=run, args=(name,), name=name)
                for name in ("a", "b")
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        finally:
            tempfile.TemporaryDirectory = real
            tempfile.tempdir = original

        assert seen, "no extraction unpacked anything"
        for name, used in seen:
            assert used == str(directories[name]), seen
        assert tempfile.tempdir == original
