"""Tests for Maven identity fields: version, homepage, dependencies and PURL.

A POM nests <version> and <url> inside <parent>, <licenses>, <scm> and
<dependencies>, so a descendant search picks up values that belong to something
else. These tests pin each field to the project's own declaration.
"""

import xml.etree.ElementTree as ET
import zipfile

import pytest
import requests

from upmex.api.clearlydefined import ClearlyDefinedAPI
from upmex.api.purldb import PurlDBAPI
from upmex.api.vulnerablecode import VulnerableCodeAPI
from upmex.core.extractor import PackageExtractor
from upmex.core.models import PackageMetadata, PackageType
from upmex.extractors.java_extractor import JavaExtractor


def make_jar(path, pom, group='com.example', artifact='app'):
    """Build a jar carrying an embedded Maven POM."""
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr(f"META-INF/maven/{group}/{artifact}/pom.xml", pom)
    return str(path)


class TestVersion:
    """A module's own <version> outranks its parent's."""

    def test_parent_version_does_not_win(self, tmp_path):
        # commons-lang3 3.12.0 under commons-parent 52, the shape that made this
        # report version "52"
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <parent>
        <groupId>org.apache.commons</groupId>
        <artifactId>commons-parent</artifactId>
        <version>52</version>
    </parent>
    <groupId>org.apache.commons</groupId>
    <artifactId>commons-lang3</artifactId>
    <version>3.12.0</version>
</project>"""
        metadata = JavaExtractor().extract(
            make_jar(tmp_path / "commons-lang3.jar", pom, 'org.apache.commons', 'commons-lang3')
        )

        assert metadata.name == "org.apache.commons:commons-lang3"
        assert metadata.version == "3.12.0"

    def test_version_is_inherited_when_not_declared(self, tmp_path):
        """A module with no <version> of its own does inherit the parent's."""
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <parent>
        <groupId>com.example</groupId>
        <artifactId>example-parent</artifactId>
        <version>2.5.0</version>
    </parent>
    <artifactId>app</artifactId>
</project>"""
        metadata = JavaExtractor().extract(make_jar(tmp_path / "app.jar", pom))

        assert metadata.name == "com.example:app"
        assert metadata.version == "2.5.0"

    def test_dependency_version_is_not_mistaken_for_the_project_version(self, tmp_path):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <groupId>org.other</groupId>
            <artifactId>lib</artifactId>
            <version>9.9.9</version>
        </dependency>
    </dependencies>
</project>"""
        metadata = JavaExtractor().extract(make_jar(tmp_path / "app.jar", pom))

        assert metadata.version == "1.0.0"


class TestHomepage:
    """The homepage is the project's <url>, not a licence's or an SCM's."""

    def test_license_url_is_not_the_homepage(self, tmp_path):
        # The gson-2.10.1 shape: no project <url>, an Apache licence URL
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>1.0.0</version>
    <licenses>
        <license>
            <name>Apache-2.0</name>
            <url>https://www.apache.org/licenses/LICENSE-2.0.txt</url>
        </license>
    </licenses>
</project>"""
        metadata = JavaExtractor().extract(make_jar(tmp_path / "app.jar", pom))

        assert metadata.homepage is None
        # The licence itself is still detected
        assert [lic.spdx_id for lic in metadata.licenses] == ["Apache-2.0"]

    def test_project_url_is_the_homepage(self, tmp_path):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>1.0.0</version>
    <url>https://example.com/app</url>
    <licenses>
        <license>
            <name>Apache-2.0</name>
            <url>https://www.apache.org/licenses/LICENSE-2.0.txt</url>
        </license>
    </licenses>
    <scm><url>https://github.com/example/app</url></scm>
</project>"""
        metadata = JavaExtractor().extract(make_jar(tmp_path / "app.jar", pom))

        assert metadata.homepage == "https://example.com/app"
        assert metadata.repository == "https://github.com/example/app"


class TestDependencies:
    """<dependencyManagement> holds version pins, not dependencies."""

    def test_managed_pins_are_not_dependencies(self, tmp_path):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <groupId>org.real</groupId>
            <artifactId>actually-used</artifactId>
        </dependency>
        <dependency>
            <groupId>org.test</groupId>
            <artifactId>only-for-tests</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.pinned</groupId>
                <artifactId>version-pin-only</artifactId>
            </dependency>
        </dependencies>
    </dependencyManagement>
</project>"""
        metadata = JavaExtractor().extract(make_jar(tmp_path / "app.jar", pom))

        assert metadata.dependencies['runtime'] == ["org.real:actually-used"]
        assert metadata.dependencies['dev'] == ["org.test:only-for-tests"]

    def test_profile_dependencies_are_excluded(self, tmp_path):
        """Deliberate: whether a profile was active is unknowable from the archive.

        A profile's dependencies apply only when the profile was activated, which
        depends on build-time properties, the JDK and the OS. Reporting them
        unconditionally attributes components to an artifact that may never have
        shipped them, so they are left out rather than guessed at.
        """
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <groupId>org.real</groupId>
            <artifactId>actually-used</artifactId>
        </dependency>
    </dependencies>
    <profiles>
        <profile>
            <id>jdk8</id>
            <activation><jdk>1.8</jdk></activation>
            <dependencies>
                <dependency>
                    <groupId>org.conditional</groupId>
                    <artifactId>only-on-jdk8</artifactId>
                </dependency>
            </dependencies>
        </profile>
    </profiles>
</project>"""
        metadata = JavaExtractor().extract(make_jar(tmp_path / "app.jar", pom))

        assert metadata.dependencies['runtime'] == ["org.real:actually-used"]

    def test_build_plugin_dependencies_are_excluded(self, tmp_path):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <groupId>org.real</groupId>
            <artifactId>actually-used</artifactId>
        </dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin>
                <artifactId>maven-checkstyle-plugin</artifactId>
                <dependencies>
                    <dependency>
                        <groupId>com.puppycrawl.tools</groupId>
                        <artifactId>checkstyle</artifactId>
                    </dependency>
                </dependencies>
            </plugin>
        </plugins>
    </build>
</project>"""
        metadata = JavaExtractor().extract(make_jar(tmp_path / "app.jar", pom))

        assert metadata.dependencies['runtime'] == ["org.real:actually-used"]


class TestOtherIdentityFields:
    """description, scm, developers and contributors are project-scoped too."""

    def test_nested_values_are_not_picked_up(self, tmp_path):
        # Every nested element here would be reached by a descendant search
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <groupId>org.other</groupId>
            <artifactId>lib</artifactId>
            <version>9.9.9</version>
        </dependency>
    </dependencies>
    <profiles>
        <profile>
            <id>release</id>
            <description>Profile description, not the project's</description>
            <scm><url>https://example.invalid/wrong-scm</url></scm>
            <developers>
                <developer><name>Profile Person</name></developer>
            </developers>
        </profile>
    </profiles>
</project>"""
        metadata = JavaExtractor().extract(make_jar(tmp_path / "app.jar", pom))

        assert metadata.description is None
        assert metadata.repository == "NO-ASSERTION"
        assert metadata.authors == []

    def test_project_values_are_picked_up(self, tmp_path):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>1.0.0</version>
    <description>The project description</description>
    <scm><connection>scm:git:https://github.com/example/app.git</connection></scm>
    <developers>
        <developer><name>Real Person</name><email>real@example.com</email></developer>
    </developers>
</project>"""
        metadata = JavaExtractor().extract(make_jar(tmp_path / "app.jar", pom))

        assert metadata.description == "The project description"
        assert metadata.repository == "https://github.com/example/app.git"
        assert [a['name'] for a in metadata.authors] == ["Real Person"]


class TestFetchedPomParsing:
    """The remote-POM parser is scoped the same way as the embedded one."""

    def test_nested_values_are_not_picked_up(self, tmp_path):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>example-parent</artifactId>
    <version>1.0.0</version>
    <licenses>
        <license>
            <name>Apache-2.0</name>
            <url>https://www.apache.org/licenses/LICENSE-2.0.txt</url>
        </license>
    </licenses>
    <profiles>
        <profile>
            <id>release</id>
            <url>https://example.invalid/wrong-url</url>
            <description>Profile description</description>
        </profile>
    </profiles>
</project>"""
        root = ET.fromstring(pom)

        parsed = JavaExtractor()._parse_pom_metadata(
            root, pom,
            detection_method='parent_pom_regex',
            license_file_path='parent:example-parent-1.0.0.pom',
            license_filename='parent_pom.xml'
        )

        # No project <url> or <description>, so neither may be invented
        assert 'homepage' not in parsed
        assert 'description' not in parsed
        assert [lic.spdx_id for lic in parsed['licenses']] == ["Apache-2.0"]

    def test_nested_people_and_scm_are_not_picked_up(self, tmp_path):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>example-parent</artifactId>
    <version>1.0.0</version>
    <profiles>
        <profile>
            <id>release</id>
            <scm><url>https://example.invalid/wrong-scm</url></scm>
            <developers>
                <developer><name>Profile Person</name></developer>
            </developers>
            <contributors>
                <contributor><name>Profile Contributor</name></contributor>
            </contributors>
        </profile>
    </profiles>
</project>"""
        root = ET.fromstring(pom)

        parsed = JavaExtractor()._parse_pom_metadata(
            root, pom,
            detection_method='parent_pom_regex',
            license_file_path='parent:example-parent-1.0.0.pom',
            license_filename='parent_pom.xml'
        )

        assert 'repository' not in parsed
        assert 'authors' not in parsed
        assert 'maintainers' not in parsed

    def test_project_people_and_scm_are_picked_up(self, tmp_path):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>example-parent</artifactId>
    <version>1.0.0</version>
    <scm><url>https://github.com/example/parent</url></scm>
    <developers>
        <developer><name>Real Person</name></developer>
    </developers>
    <contributors>
        <contributor><name>Real Contributor</name></contributor>
    </contributors>
</project>"""
        root = ET.fromstring(pom)

        parsed = JavaExtractor()._parse_pom_metadata(
            root, pom,
            detection_method='parent_pom_regex',
            license_file_path='parent:example-parent-1.0.0.pom',
            license_filename='parent_pom.xml'
        )

        assert parsed['repository'] == "https://github.com/example/parent"
        assert [a['name'] for a in parsed['authors']] == ["Real Person"]
        assert {m['name'] for m in parsed['maintainers']} == {"Real Person", "Real Contributor"}


class TestNamespacelessLookups:
    """A maven coordinate is only unique with its groupId."""

    @pytest.fixture
    def refuse_requests(self, monkeypatch):
        """Any outbound request is a failure for these cases."""
        sent = []

        def spy(url, **kwargs):
            sent.append(url)
            raise AssertionError(f"a namespace-less maven lookup was sent to {url}")

        monkeypatch.setattr(requests, 'get', spy)
        return sent

    def test_purldb_refuses(self, refuse_requests):
        assert PurlDBAPI().get_package_info(PackageType.JAR, "standalone", "1.0.0") is None
        assert refuse_requests == []

    def test_vulnerablecode_refuses(self, refuse_requests):
        assert VulnerableCodeAPI().get_vulnerabilities(PackageType.GRADLE, "standalone", "1.0.0") is None
        assert refuse_requests == []

    def test_clearlydefined_refuses(self, refuse_requests):
        assert ClearlyDefinedAPI().get_definition(PackageType.JAR, None, "standalone", "1.0.0") is None
        assert refuse_requests == []

    def test_a_coordinate_with_a_group_id_is_still_queried(self, monkeypatch):
        sent = []

        def spy(url, **kwargs):
            sent.append((url, kwargs.get('params')))
            raise RuntimeError("stop here")

        monkeypatch.setattr(requests, 'get', spy)
        PurlDBAPI().get_package_info(PackageType.JAR, "com.example:app", "1.0.0")

        assert len(sent) == 1
        assert sent[0][1]['namespace'] == "com.example"
        assert sent[0][1]['name'] == "app"


class TestMavenPurl:
    """The groupId is the PURL namespace and keeps its dots."""

    @pytest.mark.parametrize('package_type', [
        PackageType.MAVEN,
        PackageType.JAR,
        PackageType.GRADLE,
    ])
    def test_group_id_keeps_its_dots(self, package_type):
        metadata = PackageMetadata(
            name="com.squareup.okhttp3:okhttp",
            version="4.11.0",
            package_type=package_type,
        )

        purl = PackageExtractor()._generate_purl(metadata)

        assert purl == "pkg:maven/com.squareup.okhttp3/okhttp@4.11.0"

    def test_no_purl_without_a_group_id(self):
        """A maven PURL requires its namespace, so there is no valid identifier."""
        metadata = PackageMetadata(
            name="standalone",
            version="1.0.0",
            package_type=PackageType.JAR,
        )

        assert PackageExtractor()._generate_purl(metadata) is None

    def test_unidentifiable_jar_has_no_purl(self, tmp_path):
        jar_path = tmp_path / "mystery.jar"
        with zipfile.ZipFile(jar_path, 'w') as zf:
            zf.writestr('META-INF/MANIFEST.MF', "Manifest-Version: 1.0\nImplementation-Title: Mystery\n")

        metadata = PackageExtractor().extract(str(jar_path))

        assert metadata.name == "Mystery"
        assert metadata.purl is None

    def test_npm_scope_is_still_a_namespace(self):
        metadata = PackageMetadata(
            name="@babel/core",
            version="7.0.0",
            package_type=PackageType.NPM,
        )

        assert PackageExtractor()._generate_purl(metadata) == "pkg:npm/babel/core@7.0.0"

    def test_purl_of_an_extracted_jar(self, tmp_path):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <parent>
        <groupId>org.apache.commons</groupId>
        <artifactId>commons-parent</artifactId>
        <version>52</version>
    </parent>
    <groupId>org.apache.commons</groupId>
    <artifactId>commons-lang3</artifactId>
    <version>3.12.0</version>
</project>"""
        jar = make_jar(tmp_path / "commons-lang3.jar", pom, 'org.apache.commons', 'commons-lang3')

        metadata = PackageExtractor().extract(jar)

        assert metadata.purl == "pkg:maven/org.apache.commons/commons-lang3@3.12.0"
