"""Tests for resolving Maven coordinates from a file hash."""

import zipfile

import pytest
import requests

from upmex.api import maven_central
from upmex.extractors.java_extractor import JavaExtractor

MANIFEST_WITHOUT_COORDINATES = (
    "Manifest-Version: 1.0\n"
    "Automatic-Module-Name: okhttp3\n"
)

OKHTTP_POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.squareup.okhttp3</groupId>
    <artifactId>okhttp</artifactId>
    <version>4.11.0</version>
    <name>okhttp</name>
    <description>Square’s meticulous HTTP client for Java and Kotlin.</description>
    <url>https://square.github.io/okhttp/</url>
    <licenses>
        <license>
            <name>The Apache Software License, Version 2.0</name>
            <url>http://www.apache.org/licenses/LICENSE-2.0.txt</url>
        </license>
    </licenses>
    <developers>
        <developer>
            <name>Square, Inc.</name>
        </developer>
    </developers>
    <scm>
        <url>https://github.com/square/okhttp</url>
    </scm>
</project>"""

POM_WITH_PARENT = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <parent>
        <groupId>com.example</groupId>
        <artifactId>example-parent</artifactId>
        <version>1.0.0</version>
    </parent>
    <groupId>com.example</groupId>
    <artifactId>shaded-lib</artifactId>
    <version>2.3.4</version>
</project>"""

PARENT_POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>example-parent</artifactId>
    <version>1.0.0</version>
    <licenses>
        <license>
            <name>MIT</name>
        </license>
    </licenses>
</project>"""


class FakeResponse:
    """Minimal stand-in for a requests response."""

    def __init__(self, status_code=200, text='', payload=None):
        self.status_code = status_code
        self.content = text.encode('utf-8')
        # Maven Central serves POMs with no charset, so requests falls back to
        # ISO-8859-1 for .text. Mirroring that keeps a decoding regression visible.
        self.text = self.content.decode('iso-8859-1')
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("response is not JSON")
        return self._payload


class FakeMavenCentral:
    """Routes requests.get calls to canned search index and POM responses."""

    def __init__(self, docs=None, num_found=None, poms=None, error=None):
        self.docs = docs if docs is not None else []
        self.num_found = num_found if num_found is not None else len(self.docs)
        self.poms = poms or {}
        self.error = error
        self.search_calls = []
        self.pom_calls = []

    def __call__(self, url, params=None, timeout=None, headers=None):
        if 'solrsearch' in url:
            self.search_calls.append(params)
            if self.error:
                raise self.error
            return FakeResponse(payload={
                'response': {'numFound': self.num_found, 'docs': self.docs}
            })

        self.pom_calls.append(url)
        for suffix, text in self.poms.items():
            if url.endswith(suffix):
                return FakeResponse(text=text)
        return FakeResponse(status_code=404)


def make_jar(path, manifest=MANIFEST_WITHOUT_COORDINATES, extra_files=None):
    """Build a jar with no POM, optionally with extra archive members."""
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('META-INF/MANIFEST.MF', manifest)
        zf.writestr('okhttp3/OkHttpClient.class', b'\xca\xfe\xba\xbe')
        for name, content in (extra_files or {}).items():
            zf.writestr(name, content)
    return str(path)


def okhttp_registry(**kwargs):
    """A registry that resolves the okhttp jar hash and serves its POM."""
    defaults = {
        'docs': [{
            'id': 'com.squareup.okhttp3:okhttp:4.11.0',
            'g': 'com.squareup.okhttp3',
            'a': 'okhttp',
            'v': '4.11.0',
            'p': 'jar',
        }],
        'poms': {'okhttp-4.11.0.pom': OKHTTP_POM},
    }
    defaults.update(kwargs)
    return FakeMavenCentral(**defaults)


@pytest.fixture(autouse=True)
def clear_lookup_caches():
    """Keep the process-wide lookup caches from leaking between tests."""
    maven_central.clear_caches()
    yield
    maven_central.clear_caches()


class TestHashResolutionGating:
    """Coordinate resolution must not disturb the offline path."""

    def test_no_lookup_without_registry_mode(self, tmp_path, monkeypatch):
        registry = okhttp_registry()
        monkeypatch.setattr(requests, 'get', registry)

        metadata = JavaExtractor().extract(make_jar(tmp_path / "okhttp.jar"))

        assert registry.search_calls == []
        assert registry.pom_calls == []
        assert metadata.name == "unknown"

    def test_no_lookup_when_pom_is_present(self, tmp_path, monkeypatch):
        registry = okhttp_registry()
        monkeypatch.setattr(requests, 'get', registry)

        jar_path = tmp_path / "with-pom.jar"
        with zipfile.ZipFile(jar_path, 'w') as zf:
            zf.writestr("META-INF/maven/com.squareup.okhttp3/okhttp/pom.xml", OKHTTP_POM)

        metadata = JavaExtractor(registry_mode=True).extract(str(jar_path))

        assert registry.search_calls == []
        assert metadata.name == "com.squareup.okhttp3:okhttp"


class TestHashResolution:
    """Resolving coordinates and licences for an archive with no POM."""

    def test_resolves_coordinates_and_license(self, tmp_path, monkeypatch):
        registry = okhttp_registry()
        monkeypatch.setattr(requests, 'get', registry)

        metadata = JavaExtractor(registry_mode=True).extract(make_jar(tmp_path / "okhttp.jar"))

        assert metadata.name == "com.squareup.okhttp3:okhttp"
        assert metadata.version == "4.11.0"
        assert metadata.repository == "https://github.com/square/okhttp"
        assert [lic.spdx_id for lic in metadata.licenses] == ["Apache-2.0"]
        assert [author['name'] for author in metadata.authors] == ["Square, Inc."]

    def test_pom_is_decoded_by_its_xml_declaration(self, tmp_path, monkeypatch):
        registry = okhttp_registry()
        monkeypatch.setattr(requests, 'get', registry)

        metadata = JavaExtractor(registry_mode=True).extract(make_jar(tmp_path / "okhttp.jar"))

        assert metadata.description == "Square’s meticulous HTTP client for Java and Kotlin."

    def test_searches_by_the_artifact_sha1(self, tmp_path, monkeypatch):
        registry = okhttp_registry()
        monkeypatch.setattr(requests, 'get', registry)

        extractor = JavaExtractor(registry_mode=True)
        jar_path = make_jar(tmp_path / "okhttp.jar")
        extractor.extract(jar_path)

        assert registry.search_calls == [{
            'q': f'1:"{extractor.file_sha1(jar_path)}"',
            'rows': maven_central.SEARCH_ROWS,
            'wt': 'json',
        }]

    def test_records_resolution_source(self, tmp_path, monkeypatch):
        registry = okhttp_registry(num_found=2)
        monkeypatch.setattr(requests, 'get', registry)

        extractor = JavaExtractor(registry_mode=True)
        jar_path = make_jar(tmp_path / "okhttp.jar")
        metadata = extractor.extract(jar_path)

        assert metadata.provenance['name'].startswith('maven_central_hash:')
        assert metadata.provenance['version'].startswith('maven_central_hash:')
        assert metadata.provenance['licenses'] == (
            "maven_central_pom:https://repo1.maven.org/maven2/com/squareup/okhttp3"
            "/okhttp/4.11.0/okhttp-4.11.0.pom"
        )

        enrichment = metadata.enrichment[0]
        assert enrichment.source == "maven_central"
        assert enrichment.source_type == "registry"
        assert enrichment.data['resolved_by'] == 'file_hash'
        assert enrichment.data['sha1'] == extractor.file_sha1(jar_path)
        # Ambiguous matches stay visible to a consumer
        assert enrichment.data['match_count'] == 2
        assert 'name' in enrichment.applied_fields
        assert 'licenses' in enrichment.applied_fields

    def test_prefers_a_jar_among_ambiguous_matches(self, tmp_path, monkeypatch):
        registry = okhttp_registry(docs=[
            {'g': 'com.example', 'a': 'relocated', 'v': '1.0.0', 'p': 'bundle'},
            {'g': 'com.squareup.okhttp3', 'a': 'okhttp', 'v': '4.11.0', 'p': 'jar'},
        ])
        monkeypatch.setattr(requests, 'get', registry)

        metadata = JavaExtractor(registry_mode=True).extract(make_jar(tmp_path / "okhttp.jar"))

        assert metadata.name == "com.squareup.okhttp3:okhttp"

    def test_falls_through_to_the_parent_pom(self, tmp_path, monkeypatch):
        registry = FakeMavenCentral(
            docs=[{'g': 'com.example', 'a': 'shaded-lib', 'v': '2.3.4', 'p': 'jar'}],
            poms={
                'shaded-lib-2.3.4.pom': POM_WITH_PARENT,
                'example-parent-1.0.0.pom': PARENT_POM,
            }
        )
        monkeypatch.setattr(requests, 'get', registry)

        metadata = JavaExtractor(registry_mode=True).extract(make_jar(tmp_path / "shaded.jar"))

        assert metadata.name == "com.example:shaded-lib"
        assert [lic.spdx_id for lic in metadata.licenses] == ["MIT"]
        assert metadata.provenance['licenses'].startswith('parent_pom:')
        assert len(registry.pom_calls) == 2

    def test_local_license_file_is_not_overwritten(self, tmp_path, monkeypatch):
        registry = okhttp_registry()
        monkeypatch.setattr(requests, 'get', registry)

        jar_path = make_jar(
            tmp_path / "okhttp.jar",
            extra_files={'META-INF/LICENSE': 'License: MIT\n'}
        )
        metadata = JavaExtractor(registry_mode=True).extract(jar_path)

        # Coordinates still resolve, but the locally declared licence wins
        assert metadata.name == "com.squareup.okhttp3:okhttp"
        assert [lic.spdx_id for lic in metadata.licenses] == ["MIT"]
        assert 'licenses' not in metadata.provenance

    def test_caches_lookups_across_extractions(self, tmp_path, monkeypatch):
        registry = okhttp_registry()
        monkeypatch.setattr(requests, 'get', registry)

        jar_path = make_jar(tmp_path / "okhttp.jar")
        JavaExtractor(registry_mode=True).extract(jar_path)
        JavaExtractor(registry_mode=True).extract(jar_path)

        assert len(registry.search_calls) == 1
        assert len(registry.pom_calls) == 1


class TestHashResolutionFailures:
    """Every lookup failure leaves the local metadata untouched."""

    def test_unknown_hash(self, tmp_path, monkeypatch):
        registry = FakeMavenCentral(docs=[])
        monkeypatch.setattr(requests, 'get', registry)

        metadata = JavaExtractor(registry_mode=True).extract(make_jar(tmp_path / "private.jar"))

        assert metadata.name == "unknown"
        assert metadata.licenses == []
        assert len(registry.search_calls) == 1
        assert registry.pom_calls == []

    def test_search_timeout(self, tmp_path, monkeypatch):
        registry = okhttp_registry(error=requests.Timeout("rate limited"))
        monkeypatch.setattr(requests, 'get', registry)

        metadata = JavaExtractor(registry_mode=True).extract(make_jar(tmp_path / "okhttp.jar"))

        assert metadata.name == "unknown"
        assert metadata.enrichment == []

    def test_unknown_hash_is_cached_but_a_failure_is_not(self, tmp_path, monkeypatch):
        """A rate limit says nothing about the artifact, so it must not stick."""
        jar_path = make_jar(tmp_path / "okhttp.jar")

        failing = okhttp_registry(error=requests.Timeout("rate limited"))
        monkeypatch.setattr(requests, 'get', failing)
        assert JavaExtractor(registry_mode=True).extract(jar_path).name == "unknown"

        # The same hash resolves once the rate limit lifts
        recovered = okhttp_registry()
        monkeypatch.setattr(requests, 'get', recovered)
        metadata = JavaExtractor(registry_mode=True).extract(jar_path)

        assert metadata.name == "com.squareup.okhttp3:okhttp"
        assert len(recovered.search_calls) == 1

    def test_definitive_miss_is_not_retried(self, tmp_path, monkeypatch):
        registry = FakeMavenCentral(docs=[])
        monkeypatch.setattr(requests, 'get', registry)

        jar_path = make_jar(tmp_path / "private.jar")
        JavaExtractor(registry_mode=True).extract(jar_path)
        JavaExtractor(registry_mode=True).extract(jar_path)

        assert len(registry.search_calls) == 1

    def test_unreadable_search_body_is_not_a_miss(self, tmp_path, monkeypatch):
        """A garbled 200 says nothing about the hash, so it must not be cached."""
        jar_path = make_jar(tmp_path / "okhttp.jar")

        garbled = FakeMavenCentral(docs=["not a document"])
        monkeypatch.setattr(requests, 'get', garbled)
        assert JavaExtractor(registry_mode=True).extract(jar_path).name == "unknown"

        recovered = okhttp_registry()
        monkeypatch.setattr(requests, 'get', recovered)
        metadata = JavaExtractor(registry_mode=True).extract(jar_path)

        assert metadata.name == "com.squareup.okhttp3:okhttp"
        assert len(recovered.search_calls) == 1

    def test_incomplete_coordinates_are_skipped(self, tmp_path, monkeypatch):
        registry = okhttp_registry(docs=[
            {'a': 'missing-group', 'v': '1.0.0', 'p': 'jar'},
            {'g': 'com.squareup.okhttp3', 'a': 'okhttp', 'v': '4.11.0', 'p': 'jar'},
        ])
        monkeypatch.setattr(requests, 'get', registry)

        metadata = JavaExtractor(registry_mode=True).extract(make_jar(tmp_path / "okhttp.jar"))

        assert metadata.name == "com.squareup.okhttp3:okhttp"

    def test_unreadable_pom_body_is_not_cached(self, tmp_path, monkeypatch):
        """A 200 carrying an error page must not stick as the POM for a version."""
        jar_path = make_jar(tmp_path / "okhttp.jar")

        broken = okhttp_registry(poms={'okhttp-4.11.0.pom': '<html>503 from a proxy</html>'})
        monkeypatch.setattr(requests, 'get', broken)
        first = JavaExtractor(registry_mode=True).extract(jar_path)
        # Coordinates still resolve; only the POM was unusable
        assert first.name == "com.squareup.okhttp3:okhttp"
        assert first.licenses == []

        recovered = okhttp_registry()
        monkeypatch.setattr(requests, 'get', recovered)
        metadata = JavaExtractor(registry_mode=True).extract(jar_path)

        assert [lic.spdx_id for lic in metadata.licenses] == ["Apache-2.0"]

    def test_missing_pom_still_yields_coordinates(self, tmp_path, monkeypatch):
        registry = okhttp_registry(poms={})
        monkeypatch.setattr(requests, 'get', registry)

        metadata = JavaExtractor(registry_mode=True).extract(make_jar(tmp_path / "okhttp.jar"))

        assert metadata.name == "com.squareup.okhttp3:okhttp"
        assert metadata.version == "4.11.0"
        assert metadata.licenses == []
        assert metadata.enrichment[0].applied_fields == ['name', 'version']


class TestDeclaredPomLicenses:
    """A POM declares its licence as prose, which osslili cannot always classify."""

    def test_license_url_resolves_a_prose_name(self, tmp_path):
        jar_path = tmp_path / "with-pom.jar"
        with zipfile.ZipFile(jar_path, 'w') as zf:
            zf.writestr("META-INF/maven/com.squareup.okhttp3/okhttp/pom.xml", OKHTTP_POM)

        metadata = JavaExtractor().extract(str(jar_path))

        # "The Apache Software License, Version 2.0" is unclassifiable on its own;
        # the declared URL identifies it.
        assert [lic.spdx_id for lic in metadata.licenses] == ["Apache-2.0"]

    def test_unclassifiable_declaration_is_kept(self, tmp_path):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>vendor-lib</artifactId>
    <version>1.0.0</version>
    <licenses>
        <license>
            <name>Example Corp Commercial License</name>
        </license>
    </licenses>
</project>"""
        jar_path = tmp_path / "vendor.jar"
        with zipfile.ZipFile(jar_path, 'w') as zf:
            zf.writestr("META-INF/maven/com.example/vendor-lib/pom.xml", pom)

        metadata = JavaExtractor().extract(str(jar_path))

        assert len(metadata.licenses) == 1
        declared = metadata.licenses[0]
        assert declared.name == "Example Corp Commercial License"
        assert declared.detection_method == "declared"
        assert declared.file_path == "pom.xml"
