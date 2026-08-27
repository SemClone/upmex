"""What goes on stdout, and what the configuration is allowed to change.

Extractors reported problems with print(), which writes to standard output, so
a damaged archive put a diagnostic line ahead of the JSON record on the same
stream. `upmex extract broken.whl | jq .` then failed to parse, which is
exactly the artifact a compliance scan needs to survive rather than choke on.
Nothing was written to stderr at all.

Separately, the configuration declared enabled, base_url, timeout and api_key
for ClearlyDefined and the client read none of them. The base_url it held
carried a /v1 prefix that ClearlyDefined answers 404 for, so wiring it up as
written would have broken the integration rather than fixed it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from upmex.api.clearlydefined import ClearlyDefinedAPI
from upmex.config import Config
from upmex.core.models import PackageType


class TestStdoutCarriesOnlyTheRecord:
    def test_a_damaged_archive_still_yields_parseable_json(self, tmp_path):
        broken = tmp_path / "broken.whl"
        broken.write_bytes(b"not a zip")

        result = subprocess.run(
            [sys.executable, "-m", "upmex.cli", "extract", str(broken)],
            capture_output=True, text=True,
        )

        json.loads(result.stdout)  # raises if anything else got in the way

    def test_the_diagnostic_goes_to_stderr(self, tmp_path):
        broken = tmp_path / "broken.whl"
        broken.write_bytes(b"not a zip")

        result = subprocess.run(
            [sys.executable, "-m", "upmex.cli", "extract", str(broken)],
            capture_output=True, text=True,
        )

        assert "not a zip file" in result.stderr
        assert "not a zip file" not in result.stdout

    def test_the_record_is_still_complete(self, tmp_path):
        """Routing the noise away must not take the answer with it."""
        broken = tmp_path / "broken.whl"
        broken.write_bytes(b"not a zip")

        result = subprocess.run(
            [sys.executable, "-m", "upmex.cli", "extract", str(broken)],
            capture_output=True, text=True,
        )

        document = json.loads(result.stdout)
        assert document["package"]["type"] == "python_wheel"
        assert "file_info" in document

    def test_a_good_package_is_unaffected(self, tmp_path):
        """The ordinary path had no diagnostic on it and must stay quiet."""
        import zipfile

        wheel = tmp_path / "p-1.0.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(
                "p-1.0.0.dist-info/METADATA",
                "Metadata-Version: 2.1\nName: p\nVersion: 1.0.0\nLicense: MIT\n",
            )

        result = subprocess.run(
            [sys.executable, "-m", "upmex.cli", "extract", str(wheel)],
            capture_output=True, text=True,
        )

        document = json.loads(result.stdout)
        assert document["package"]["name"] == "p"


class TestNoDiagnosticIsLeftOnStdout:
    def test_nothing_outside_the_cli_prints(self):
        """The CLI writes the record. Everything else reports through
        logging, which goes to stderr, and which --quiet and --verbose reach.
        """
        root = Path(__file__).resolve().parents[2] / "src" / "upmex"
        offenders = []
        for path in root.rglob("*.py"):
            if path.name == "cli.py":
                continue
            for number, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if stripped.startswith("print(") or " print(" in stripped:
                    offenders.append(f"{path.name}:{number}: {stripped}")
        assert not offenders, offenders


class TestTheClearlyDefinedSettingsAreRead:
    def test_the_base_url_has_no_version_prefix(self):
        """/v1 is a 404. The service serves /definitions from the host."""
        assert Config().get("api.clearlydefined.base_url") == (
            "https://api.clearlydefined.io"
        )

    def test_the_shipped_config_file_agrees_with_the_defaults(self):
        """config/default.json is not what Config() reads, so the two can
        drift, and a reader following the file would configure the 404.

        Compared whole rather than section by section: checking one section
        let the file keep a package_types block with six settings nothing
        read, and an output.schema_version that no longer exists.
        """
        shipped = json.loads(
            (Path(__file__).resolve().parents[2] / "config" / "default.json")
            .read_text()
        )

        assert shipped == Config.DEFAULT_CONFIG

    def test_the_client_uses_the_configured_base_url(self):
        class Configured:
            def get(self, key, default=None):
                if key == "api.clearlydefined.base_url":
                    return "https://mirror.example.invalid/"
                return default

        client = ClearlyDefinedAPI(config=Configured())

        assert client.base_url == "https://mirror.example.invalid"

    def test_the_client_uses_the_configured_timeout(self):
        class Configured:
            def get(self, key, default=None):
                return 5 if key == "api.clearlydefined.timeout" else default

        assert ClearlyDefinedAPI(config=Configured()).timeout == 5

    def test_the_client_uses_the_configured_key(self):
        class Configured:
            def get(self, key, default=None):
                return "abc" if key == "api.clearlydefined.api_key" else default

        client = ClearlyDefinedAPI(config=Configured())

        assert client.api_key == "abc"
        assert client.headers["Authorization"] == "Bearer abc"

    def test_a_passed_key_wins_over_the_configured_one(self):
        class Configured:
            def get(self, key, default=None):
                return "from-config" if key.endswith("api_key") else default

        assert ClearlyDefinedAPI("passed", Configured()).api_key == "passed"

    def test_no_key_sends_no_authorization(self):
        class Configured:
            def get(self, key, default=None):
                return default

        assert ClearlyDefinedAPI(config=Configured()).headers == {}


class TestDisabledMeansDisabled:
    """Setting enabled to false disabled nothing, so a deployment that asked
    not to reach ClearlyDefined reached it anyway."""

    class Off:
        def get(self, key, default=None):
            return False if key.endswith("enabled") else default

    def test_no_request_is_made(self, monkeypatch):
        """Recorded rather than raised: get_definition catches everything, so
        an exception here would be swallowed and the test would pass whether
        the request happened or not."""
        import upmex.api.clearlydefined as module

        attempts = []

        def record(*args, **kwargs):
            attempts.append(args[0] if args else kwargs.get("url"))
            raise RuntimeError("no network in this test")

        monkeypatch.setattr(module.requests, "get", record)

        result = ClearlyDefinedAPI(config=self.Off()).get_definition(
            PackageType.NPM, None, "express", "4.18.2"
        )

        assert attempts == [], attempts
        assert result is None

    def test_enabled_does_make_the_request(self, monkeypatch):
        """The other half: the guard must not disable everything."""
        import upmex.api.clearlydefined as module

        attempts = []

        def record(*args, **kwargs):
            attempts.append(args[0] if args else kwargs.get("url"))
            raise RuntimeError("no network in this test")

        monkeypatch.setattr(module.requests, "get", record)

        class On:
            def get(self, key, default=None):
                return True if key.endswith("enabled") else default

        ClearlyDefinedAPI(config=On()).get_definition(
            PackageType.NPM, None, "express", "4.18.2"
        )

        assert attempts, "the request was never attempted"

    def test_enabled_by_default(self):
        class Silent:
            def get(self, key, default=None):
                return default

        assert ClearlyDefinedAPI(config=Silent()).enabled is True


class TestVerboseKeepsStdoutClean:
    """The record shares the stream with whatever -v prints, so a diagnostic
    there breaks the pipe exactly as the extractor's own did."""

    def _extract(self, tmp_path, *flags):
        broken = tmp_path / "broken.whl"
        broken.write_bytes(b"not a zip")
        return subprocess.run(
            [sys.executable, "-m", "upmex.cli", *flags, "extract", str(broken)],
            capture_output=True, text=True,
        )

    def test_verbose_output_still_parses(self, tmp_path):
        result = self._extract(tmp_path, "-v")

        json.loads(result.stdout)

    def test_the_verbose_lines_are_on_stderr(self, tmp_path):
        result = self._extract(tmp_path, "-v")

        assert "Extracting metadata from" in result.stderr
        assert "Extracting metadata from" not in result.stdout


class TestEnrichmentDoesNotDependOnVerbosity:
    """The whole ClearlyDefined block sat inside `if verbose:`, so asking for
    enrichment and not asking for chatter got no enrichment at all:

        upmex extract x --api clearlydefined       -> nothing fetched
        upmex extract x --api clearlydefined -v    -> fetched
    """

    def _wheel(self, tmp_path):
        import zipfile

        wheel = tmp_path / "p-1.0.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(
                "p-1.0.0.dist-info/METADATA",
                "Metadata-Version: 2.1\nName: p\nVersion: 1.0.0\n",
            )
        return wheel

    def _run(self, tmp_path, monkeypatch, *flags):
        from click.testing import CliRunner

        import upmex.api.clearlydefined as module
        from upmex.cli import cli

        built = []

        class Recorder:
            def __init__(self, api_key=None, config=None):
                built.append(("built", config))

            def get_definition(self, **kwargs):
                built.append(("queried", kwargs.get("name")))
                return None

        monkeypatch.setattr(module, "ClearlyDefinedAPI", Recorder)
        CliRunner().invoke(
            cli,
            [*flags, "extract", str(self._wheel(tmp_path)), "--api", "clearlydefined"],
        )
        return built

    def test_it_happens_without_verbose(self, tmp_path, monkeypatch):
        """Constructed and actually asked: building a client and never
        querying it would look the same from the outside."""
        events = self._run(tmp_path, monkeypatch)

        assert ("queried", "p") in events, events

    def test_it_still_happens_with_verbose(self, tmp_path, monkeypatch):
        events = self._run(tmp_path, monkeypatch, "-v")

        assert ("queried", "p") in events, events

    def test_the_command_config_is_what_reaches_it(self, tmp_path, monkeypatch):
        """The Config the command holds, not a fresh default one built inside
        the client. It is the dict form, because that is what --config
        produced and what the command passes on."""
        events = self._run(tmp_path, monkeypatch)

        built = [config for kind, config in events if kind == "built"]
        assert built, events
        assert built[0] is not None
        # Reaches the settings the command was configured with.
        from upmex.config import setting

        assert setting(built[0], "api.clearlydefined.base_url", None) == (
            "https://api.clearlydefined.io"
        )


class TestTheClientReadsEitherConfigShape:
    """The CLI holds a Config, whose get understands a dotted key. The
    extractors are handed what to_dict() produced, which is a plain nested
    dict and answers the same key with the default."""

    def test_a_plain_nested_dict_is_read(self):
        settings = {"api": {"clearlydefined": {"timeout": 7, "enabled": False}}}

        client = ClearlyDefinedAPI(config=settings)

        assert client.timeout == 7
        assert client.enabled is False

    def test_a_config_object_is_read(self):
        assert ClearlyDefinedAPI(config=Config()).timeout == 30

    def test_a_dict_missing_the_section_falls_back(self):
        client = ClearlyDefinedAPI(config={"api": {}})

        assert client.enabled is True
        assert client.base_url == "https://api.clearlydefined.io"

    def test_every_construction_site_passes_one(self):
        """Building the client with no config makes it read the defaults,
        whatever the caller asked for on the command line."""
        root = Path(__file__).resolve().parents[2] / "src" / "upmex"
        bare = []
        for path in root.rglob("*.py"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if "ClearlyDefinedAPI()" in line:
                    bare.append(f"{path.name}:{number}")
        assert not bare, bare


class TestOneConfigDoesNotChangeAnother:
    """DEFAULT_CONFIG was shared by reference, so set() wrote into it and
    every later Config, and every default-constructed client, saw the change
    for the life of the process."""

    def test_setting_one_leaves_the_next_alone(self):
        changed = Config()
        changed.set("api.clearlydefined.enabled", False)

        assert Config().get("api.clearlydefined.enabled") is True

    def test_and_leaves_the_class_default_alone(self):
        changed = Config()
        changed.set("api.clearlydefined.timeout", 999)

        assert Config.DEFAULT_CONFIG["api"]["clearlydefined"]["timeout"] != 999

    def test_the_change_still_applies_to_the_one_that_made_it(self):
        changed = Config()
        changed.set("api.clearlydefined.timeout", 999)

        assert changed.get("api.clearlydefined.timeout") == 999


class TestTheDebugLinesStillSayAnything:
    """The print-to-logger conversion dropped the f prefix on interpolated
    lines, so they logged the braces rather than the values."""

    def test_no_debug_line_logs_a_literal_brace(self):
        root = Path(__file__).resolve().parents[2] / "src" / "upmex"
        offenders = []
        for path in root.rglob("*.py"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.strip()
                if not stripped.startswith("logger."):
                    continue
                if '("' in stripped and "{" in stripped and 'f"' not in stripped:
                    offenders.append(f"{path.name}:{number}: {stripped}")
        assert not offenders, offenders


class TestEveryApiPathKeepsStdoutClean:
    """The record shares the stream with every diagnostic the command writes,
    so one line on the wrong stream breaks the pipe. -v without --api was the
    only case covered, and each --api branch had its own lines."""

    def _wheel(self, tmp_path):
        import zipfile

        wheel = tmp_path / "p-1.0.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(
                "p-1.0.0.dist-info/METADATA",
                "Metadata-Version: 2.1\nName: p\nVersion: 1.0.0\nLicense: MIT\n",
            )
        return wheel

    @pytest.mark.parametrize(
        "flags",
        [
            [],
            ["-v"],
            ["-v", "--registry"],
        ],
    )
    def test_stdout_is_parseable(self, tmp_path, flags):
        result = subprocess.run(
            [sys.executable, "-m", "upmex.cli", *[f for f in flags if f == "-v"],
             "extract", str(self._wheel(tmp_path)),
             *[f for f in flags if f != "-v"]],
            capture_output=True, text=True,
        )

        json.loads(result.stdout)

    def test_only_the_record_is_written_to_stdout(self):
        """Every other echo in the command goes to stderr. Checked on the
        source because reaching each branch needs the network.

        Parsed rather than scanned line by line. A call spread over several
        lines put its err=True on a line of its own, so the scanner read the
        opening line as a bare write to stdout, and the same blindness would
        have missed a real one.
        """
        import ast
        import inspect
        import textwrap

        from upmex import cli

        tree = ast.parse(textwrap.dedent(inspect.getsource(cli.extract.callback)))
        loose = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", None) != "echo":
                continue
            if any(keyword.arg == "err" for keyword in node.keywords):
                continue
            loose.append(ast.unparse(node.args[0]) if node.args else "<nothing>")

        assert loose == ["output_text"], loose

    def test_writing_to_a_file_says_so_on_stderr(self, tmp_path):
        out = tmp_path / "record.json"
        result = subprocess.run(
            [sys.executable, "-m", "upmex.cli", "extract",
             str(self._wheel(tmp_path)), "-o", str(out)],
            capture_output=True, text=True,
        )

        assert "Output written to" in result.stderr
        assert "Output written to" not in result.stdout
        json.loads(out.read_text())


class TestTheEcosystemsSettingsAreReadToo:
    """The same defect, in the sibling client: the configuration declared
    enabled, base_url, timeout and api_key and none of them was read. Its
    configured base_url does not resolve at all, so wiring it up as written
    would have broken the integration outright."""

    def test_the_base_url_resolves(self):
        """packages.ecosyste.ms/api/v1 answers; api.ecosyste.ms/v1 does not."""
        assert Config().get("api.ecosystems.base_url") == (
            "https://packages.ecosyste.ms/api/v1"
        )

    def test_the_client_reads_the_configured_settings(self):
        from upmex.api.ecosystems import EcosystemsAPI

        settings = {
            "api": {"ecosystems": {"timeout": 3, "api_key": "tok", "enabled": True}}
        }
        client = EcosystemsAPI(config=settings)

        assert client.timeout == 3
        assert client.headers["Authorization"] == "Bearer tok"

    def test_disabled_makes_no_request(self, monkeypatch):
        import upmex.api.ecosystems as module
        from upmex.api.ecosystems import EcosystemsAPI
        from upmex.core.models import PackageType

        attempts = []

        def record(*args, **kwargs):
            attempts.append(args[0] if args else kwargs.get("url"))
            raise RuntimeError("no network in this test")

        monkeypatch.setattr(module.requests, "get", record)
        off = {"api": {"ecosystems": {"enabled": False}}}

        assert EcosystemsAPI(config=off).get_package_info(
            PackageType.NPM, "express"
        ) is None
        assert attempts == []

    def test_every_construction_site_passes_a_config(self):
        root = Path(__file__).resolve().parents[2] / "src" / "upmex"
        bare = []
        for path in root.rglob("*.py"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if "EcosystemsAPI()" in line:
                    bare.append(f"{path.name}:{number}")
        assert not bare, bare

    def test_the_shipped_file_agrees_here_too(self):
        shipped = json.loads(
            (Path(__file__).resolve().parents[2] / "config" / "default.json")
            .read_text()
        )

        for name in ("base_url", "enabled", "timeout", "api_key"):
            assert shipped["api"]["ecosystems"][name] == Config().get(
                f"api.ecosystems.{name}"
            ), name


class TestDetectKeepsStdoutToTheType:
    """`upmex detect -v x` put File and Size on stdout alongside a "Type: ..."
    line, so the value a caller reads was wrapped in prose at one verbosity
    and bare at the other."""

    def _run(self, tmp_path, *flags):
        package = tmp_path / "p-1.0.0-py3-none-any.whl"
        package.write_bytes(b"anything")
        return subprocess.run(
            [sys.executable, "-m", "upmex.cli", "detect", *flags, str(package)],
            capture_output=True, text=True,
        )

    def test_the_type_is_the_same_at_either_verbosity(self, tmp_path):
        plain = self._run(tmp_path).stdout.strip()
        verbose = self._run(tmp_path, "-v").stdout.strip()

        assert plain == verbose
        assert plain

    def test_the_commentary_is_on_stderr(self, tmp_path):
        result = self._run(tmp_path, "-v")

        assert "File:" in result.stderr
        assert "File:" not in result.stdout
        assert "Size:" not in result.stdout


class TestTheDocumentedEnvironmentKeysReachSomething:
    """The README tells a user to export these. Neither was mapped, so
    exporting one set a key nothing ever read."""

    @pytest.mark.parametrize(
        "variable,key",
        [
            ("PME_CLEARLYDEFINED_API_KEY", "api.clearlydefined.api_key"),
            ("PME_ECOSYSTEMS_API_KEY", "api.ecosystems.api_key"),
            ("PME_PURLDB_API_KEY", "api.purldb.api_key"),
            ("PME_VULNERABLECODE_API_KEY", "api.vulnerablecode.api_key"),
        ],
    )
    def test_each_one_is_mapped(self, variable, key, monkeypatch):
        monkeypatch.setenv(variable, "a-token")

        assert Config().get(key) == "a-token"

    def test_every_key_the_readme_documents_is_mapped(self):
        """So a variable added to the documentation and not to the mapping is
        noticed rather than silently doing nothing."""
        import re

        readme = (Path(__file__).resolve().parents[2] / "README.md").read_text()
        documented = set(re.findall(r"\bPME_[A-Z_]+\b", readme))
        mapped = set(Config.ENV_VAR_MAPPING)

        assert documented <= mapped, sorted(documented - mapped)


class TestEveryDeclaredApiClientReadsItsSettings:
    """Adding a config section for a client that does not read it is the
    defect this whole change is about, so the rule is checked for all four
    rather than for the two the issue named."""

    CLIENTS = {
        "clearlydefined": "upmex.api.clearlydefined.ClearlyDefinedAPI",
        "ecosystems": "upmex.api.ecosystems.EcosystemsAPI",
        "purldb": "upmex.api.purldb.PurlDBAPI",
        "vulnerablecode": "upmex.api.vulnerablecode.VulnerableCodeAPI",
    }

    def _client(self, dotted, settings):
        import importlib

        module, name = dotted.rsplit(".", 1)
        return getattr(importlib.import_module(module), name)(config=settings)

    @pytest.mark.parametrize("section,dotted", sorted(CLIENTS.items()))
    def test_the_timeout_is_read(self, section, dotted):
        client = self._client(dotted, {"api": {section: {"timeout": 3}}})

        assert client.timeout == 3

    @pytest.mark.parametrize("section,dotted", sorted(CLIENTS.items()))
    def test_the_key_is_read(self, section, dotted):
        client = self._client(dotted, {"api": {section: {"api_key": "tok"}}})

        assert client.api_key == "tok"
        assert "tok" in str(client.headers)

    @pytest.mark.parametrize("section,dotted", sorted(CLIENTS.items()))
    def test_the_base_url_is_read(self, section, dotted):
        client = self._client(
            dotted, {"api": {section: {"base_url": "https://mirror.invalid/"}}}
        )

        assert client.base_url == "https://mirror.invalid"

    @pytest.mark.parametrize("section,dotted", sorted(CLIENTS.items()))
    def test_disabled_is_honoured(self, section, dotted):
        client = self._client(dotted, {"api": {section: {"enabled": False}}})

        assert client.enabled is False

    @pytest.mark.parametrize("section", sorted(CLIENTS))
    def test_the_default_url_is_the_one_the_client_builds_on(self, section):
        """The clients append their own /api/... path, so a setting carrying
        one produces /api/api/... . Checked against what the client uses when
        nothing is configured."""
        client = self._client(self.CLIENTS[section], {})

        assert Config().get(f"api.{section}.base_url") == client.base_url

    @pytest.mark.parametrize("section", sorted(CLIENTS))
    def test_the_shipped_file_carries_the_section(self, section):
        shipped = json.loads(
            (Path(__file__).resolve().parents[2] / "config" / "default.json")
            .read_text()
        )

        for name in ("base_url", "enabled", "timeout", "api_key"):
            assert shipped["api"][section][name] == Config().get(
                f"api.{section}.{name}"
            ), f"{section}.{name}"

    def test_no_client_is_built_without_a_config(self):
        """A bare construction reads the defaults whatever the caller asked."""
        root = Path(__file__).resolve().parents[2] / "src" / "upmex"
        bare = []
        for path in root.rglob("*.py"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                for name in ("ClearlyDefinedAPI", "EcosystemsAPI",
                             "PurlDBAPI", "VulnerableCodeAPI"):
                    if f"{name}()" in line:
                        bare.append(f"{path.name}:{number}")
        assert not bare, bare

    @pytest.mark.parametrize(
        "section,dotted,call",
        [
            ("clearlydefined", "upmex.api.clearlydefined.ClearlyDefinedAPI",
             lambda c: c.get_definition(
                 __import__("upmex.core.models", fromlist=["PackageType"])
                 .PackageType.NPM, None, "express", "4.18.2")),
            ("ecosystems", "upmex.api.ecosystems.EcosystemsAPI",
             lambda c: c.get_package_info(
                 __import__("upmex.core.models", fromlist=["PackageType"])
                 .PackageType.NPM, "express")),
            ("purldb", "upmex.api.purldb.PurlDBAPI",
             lambda c: c.get_package_by_purl("pkg:npm/express@4.18.2")),
            ("vulnerablecode", "upmex.api.vulnerablecode.VulnerableCodeAPI",
             lambda c: c.get_vulnerabilities_by_purl("pkg:npm/express@4.18.2")),
        ],
    )
    def test_disabled_makes_no_request_even_with_a_key(
        self, section, dotted, call, monkeypatch
    ):
        """With a key configured, nothing else short-circuits, so this is the
        case only the enabled guard can stop. Without one, VulnerableCode
        returns early anyway and the guard is untested."""
        import importlib

        module_name, name = dotted.rsplit(".", 1)
        module = importlib.import_module(module_name)
        attempts = []

        def record(*args, **kwargs):
            attempts.append(args[0] if args else kwargs.get("url"))
            raise RuntimeError("no network in this test")

        monkeypatch.setattr(module.requests, "get", record)
        client = getattr(module, name)(
            config={"api": {section: {"enabled": False, "api_key": "tok"}}}
        )

        assert call(client) is None
        assert attempts == [], attempts

    @pytest.mark.parametrize(
        "section,dotted,call",
        [
            ("purldb", "upmex.api.purldb.PurlDBAPI",
             lambda c: c.get_package_by_purl("pkg:npm/express@4.18.2")),
            ("vulnerablecode", "upmex.api.vulnerablecode.VulnerableCodeAPI",
             lambda c: c.get_vulnerabilities_by_purl("pkg:npm/express@4.18.2")),
        ],
    )
    def test_enabled_does_reach_the_network(
        self, section, dotted, call, monkeypatch
    ):
        """The other half: the guard must not disable everything."""
        import importlib

        module_name, name = dotted.rsplit(".", 1)
        module = importlib.import_module(module_name)
        attempts = []

        def record(*args, **kwargs):
            attempts.append(args[0] if args else kwargs.get("url"))
            raise RuntimeError("no network in this test")

        monkeypatch.setattr(module.requests, "get", record)
        client = getattr(module, name)(
            config={"api": {section: {"enabled": True, "api_key": "tok"}}}
        )
        call(client)

        assert attempts, "the request was never attempted"


def _npm_package(tmp_path):
    """A real .tgz on disk, so the CLI runs its normal extract path."""
    import tarfile

    src = tmp_path / "package"
    src.mkdir(exist_ok=True)
    (src / "package.json").write_text(
        json.dumps({"name": "express", "version": "4.18.2", "license": "MIT"})
    )
    pkg = tmp_path / "express.tgz"
    with tarfile.open(pkg, "w:gz") as tar:
        tar.add(src / "package.json", arcname="package/package.json")
    return pkg


class TestDisabledStopsTheRealEntryPoint:
    """The guard has to sit on the method the CLI calls, not on a sibling.

    An earlier version guarded PurlDB.get_package_by_purl while the CLI calls
    get_package_info, so `enabled: false` was ignored in production and the
    unit test still passed. These drive the CLI itself.
    """

    @pytest.mark.parametrize(
        "api,section",
        [
            ("clearlydefined", "clearlydefined"),
            ("ecosystems", "ecosystems"),
            ("purldb", "purldb"),
            ("vulnerablecode", "vulnerablecode"),
        ],
    )
    def test_cli_honours_disabled(self, api, section, tmp_path, monkeypatch):
        import json

        from click.testing import CliRunner

        from upmex import cli as cli_module
        from upmex.api import (
            clearlydefined as cd_mod,
            ecosystems as eco_mod,
            purldb as purldb_mod,
            vulnerablecode as vc_mod,
        )

        attempts = []

        def record(*args, **kwargs):
            attempts.append(args[0] if args else kwargs.get("url"))
            raise RuntimeError("no network in this test")

        for mod in (cd_mod, eco_mod, purldb_mod, vc_mod):
            monkeypatch.setattr(mod.requests, "get", record)

        cfg = tmp_path / "upmex.json"
        cfg.write_text(
            json.dumps({"api": {section: {"enabled": False, "api_key": "tok"}}})
        )
        pkg = _npm_package(tmp_path)

        result = CliRunner().invoke(
            cli_module.cli,
            ["--config", str(cfg), "extract", str(pkg), "--api", api],
        )

        assert result.exit_code == 0, result.output
        assert attempts == [], attempts

    @pytest.mark.parametrize(
        "api,section",
        [
            ("clearlydefined", "clearlydefined"),
            ("ecosystems", "ecosystems"),
            ("purldb", "purldb"),
            ("vulnerablecode", "vulnerablecode"),
        ],
    )
    def test_cli_enabled_still_reaches_the_network(
        self, api, section, tmp_path, monkeypatch
    ):
        """The other half: the guard must not disable everything."""
        import json

        from click.testing import CliRunner

        from upmex import cli as cli_module
        from upmex.api import (
            clearlydefined as cd_mod,
            ecosystems as eco_mod,
            purldb as purldb_mod,
            vulnerablecode as vc_mod,
        )

        attempts = []

        def record(*args, **kwargs):
            attempts.append(args[0] if args else kwargs.get("url"))
            raise RuntimeError("no network in this test")

        for mod in (cd_mod, eco_mod, purldb_mod, vc_mod):
            monkeypatch.setattr(mod.requests, "get", record)

        cfg = tmp_path / "upmex.json"
        cfg.write_text(
            json.dumps({"api": {section: {"enabled": True, "api_key": "tok"}}})
        )
        pkg = _npm_package(tmp_path)

        CliRunner().invoke(
            cli_module.cli,
            ["--config", str(cfg), "extract", str(pkg), "--api", api],
        )

        assert attempts, f"{api} never attempted a request"


class TestLegacyTopLevelApiKey:
    """A config file predating the api.* sections put the key at the top level.

    The CLI still reads it. It has to still reach the client, or upgrading
    upmex silently turns a working VulnerableCode setup off.
    """

    def test_top_level_vulnerablecode_key_still_authenticates(
        self, tmp_path, monkeypatch
    ):
        from click.testing import CliRunner

        from upmex import cli as cli_module
        from upmex.api import vulnerablecode as vc_mod

        seen = []

        def record(*args, **kwargs):
            seen.append(kwargs.get("headers") or {})
            raise RuntimeError("no network in this test")

        monkeypatch.setattr(vc_mod.requests, "get", record)

        cfg = tmp_path / "upmex.json"
        cfg.write_text(json.dumps({"vulnerablecode_api_key": "legacy-tok"}))
        pkg = _npm_package(tmp_path)

        CliRunner().invoke(
            cli_module.cli,
            ["--config", str(cfg), "extract", str(pkg), "--api", "vulnerablecode"],
        )

        assert seen, "no request attempted, so the key never took effect"
        assert seen[0].get("Authorization") == "Token legacy-tok", seen[0]

    def test_top_level_key_wins_over_the_nested_one(self, tmp_path, monkeypatch):
        """An explicit argument has always beaten configuration."""
        from click.testing import CliRunner

        from upmex import cli as cli_module
        from upmex.api import vulnerablecode as vc_mod

        seen = []

        def record(*args, **kwargs):
            seen.append(kwargs.get("headers") or {})
            raise RuntimeError("no network in this test")

        monkeypatch.setattr(vc_mod.requests, "get", record)

        cfg = tmp_path / "upmex.json"
        cfg.write_text(
            json.dumps(
                {
                    "vulnerablecode_api_key": "legacy-tok",
                    "api": {"vulnerablecode": {"api_key": "nested-tok"}},
                }
            )
        )
        pkg = _npm_package(tmp_path)

        CliRunner().invoke(
            cli_module.cli,
            ["--config", str(cfg), "extract", str(pkg), "--api", "vulnerablecode"],
        )

        assert seen, "no request attempted"
        assert seen[0].get("Authorization") == "Token legacy-tok", seen[0]
