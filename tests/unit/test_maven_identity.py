"""Tests for Maven identity fields: version, homepage, dependencies and PURL.

A POM nests <version> and <url> inside <parent>, <licenses>, <scm> and
<dependencies>, so a descendant search picks up values that belong to something
else. These tests pin each field to the project's own declaration.
"""

import zipfile

import pytest

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

    def test_name_without_a_group_id(self):
        metadata = PackageMetadata(
            name="standalone",
            version="1.0.0",
            package_type=PackageType.JAR,
        )

        assert PackageExtractor()._generate_purl(metadata) == "pkg:maven/standalone@1.0.0"

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
