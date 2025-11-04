"""Integration tests for package extractors."""

import pytest
import tempfile
import zipfile
import tarfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from upmex.extractors.python_extractor import PythonExtractor
from upmex.extractors.npm_extractor import NpmExtractor
from upmex.extractors.java_extractor import JavaExtractor
from upmex.core.models import PackageType


class TestPythonExtractor:
    """Test Python package extraction."""
    
    def test_extract_wheel_metadata(self, tmp_path):
        """Test extracting metadata from a wheel file."""
        # Create a mock wheel file
        wheel_path = tmp_path / "test-1.0.0-py3-none-any.whl"
        
        with zipfile.ZipFile(wheel_path, 'w') as zf:
            # Add METADATA file
            metadata_content = """Metadata-Version: 2.1
Name: test-package
Version: 1.0.0
Summary: A test package
Author: Test Author
Author-email: test@example.com
License: MIT
Classifier: Programming Language :: Python :: 3
Requires-Dist: requests>=2.0.0
"""
            zf.writestr("test-1.0.0.dist-info/METADATA", metadata_content)
        
        extractor = PythonExtractor()
        metadata = extractor.extract(str(wheel_path))
        
        assert metadata.name == "test-package"
        assert metadata.version == "1.0.0"
        assert metadata.description == "A test package"
        assert metadata.package_type == PackageType.PYTHON_WHEEL
        assert len(metadata.authors) > 0
        assert metadata.authors[0]["name"] == "Test Author"
        assert metadata.authors[0]["email"] == "test@example.com"
        runtime_deps = metadata.dependencies.get("runtime", [])
        assert any("requests" in dep for dep in runtime_deps)
    
    def test_extract_sdist_metadata(self, tmp_path):
        """Test extracting metadata from sdist tar.gz."""
        import io
        sdist_path = tmp_path / "test-1.0.0.tar.gz"

        # Create PKG-INFO content
        pkg_info = """Metadata-Version: 2.1
Name: test-sdist
Version: 2.0.0
Summary: Test sdist package
Author: Sdist Author
License: Apache-2.0
"""

        with tarfile.open(sdist_path, 'w:gz') as tf:
            info = tarfile.TarInfo(name="test-1.0.0/PKG-INFO")
            info.size = len(pkg_info.encode())
            tf.addfile(info, fileobj=io.BytesIO(pkg_info.encode()))

        extractor = PythonExtractor()
        metadata = extractor.extract(str(sdist_path))

        assert metadata.name == "test-sdist"
        assert metadata.version == "2.0.0"
        assert metadata.package_type == PackageType.PYTHON_SDIST


class TestNpmExtractor:
    """Test NPM package extraction."""
    
    def test_extract_npm_metadata(self, tmp_path):
        """Test extracting metadata from npm tgz package."""
        npm_path = tmp_path / "test-1.0.0.tgz"
        
        # Create package.json content
        package_json = {
            "name": "@scope/test-package",
            "version": "1.0.0",
            "description": "Test npm package",
            "author": {
                "name": "NPM Author",
                "email": "npm@example.com"
            },
            "license": "ISC",
            "repository": {
                "type": "git",
                "url": "https://github.com/test/repo.git"
            },
            "dependencies": {
                "express": "^4.0.0"
            },
            "devDependencies": {
                "jest": "^27.0.0"
            },
            "keywords": ["test", "npm"]
        }
        
        # Create the tgz structure
        import io
        with tarfile.open(npm_path, 'w:gz') as tf:
            info = tarfile.TarInfo(name="package/package.json")
            content = json.dumps(package_json).encode()
            info.size = len(content)
            tf.addfile(info, fileobj=io.BytesIO(content))

        extractor = NpmExtractor()
        metadata = extractor.extract(str(npm_path))
        
        assert metadata.name == "@scope/test-package"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test npm package"
        assert metadata.package_type == PackageType.NPM
        assert metadata.repository == "https://github.com/test/repo.git"
        assert "express" in metadata.dependencies.get("runtime", [])
        assert "jest" in metadata.dependencies.get("dev", [])
        assert "test" in metadata.keywords


class TestJavaExtractor:
    """Test Java/Maven package extraction."""
    
    def test_extract_maven_metadata(self, tmp_path):
        """Test extracting metadata from Maven JAR."""
        jar_path = tmp_path / "test-1.0.0.jar"
        
        # Create POM XML content
        pom_xml = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>test-artifact</artifactId>
    <version>1.0.0</version>
    <description>Test Maven package</description>
    <url>https://example.com</url>
    <developers>
        <developer>
            <name>Maven Developer</name>
            <email>maven@example.com</email>
        </developer>
    </developers>
    <scm>
        <url>https://github.com/example/test.git</url>
    </scm>
    <dependencies>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.12</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>"""
        
        with zipfile.ZipFile(jar_path, 'w') as zf:
            zf.writestr("META-INF/maven/com.example/test-artifact/pom.xml", pom_xml)
        
        extractor = JavaExtractor()
        metadata = extractor.extract(str(jar_path))
        
        assert metadata.name == "com.example:test-artifact"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test Maven package"
        assert metadata.homepage == "https://example.com"
        assert metadata.package_type == PackageType.MAVEN
        assert metadata.repository == "https://github.com/example/test.git"
        assert len(metadata.authors) > 0
        assert metadata.authors[0]["name"] == "Maven Developer"
        assert metadata.authors[0]["email"] == "maven@example.com"
    
    def test_extract_jar_manifest(self, tmp_path):
        """Test extracting from JAR with only MANIFEST.MF."""
        jar_path = tmp_path / "simple.jar"
        
        manifest_content = """Manifest-Version: 1.0
Implementation-Title: Simple JAR
Implementation-Version: 2.0.0
Implementation-Vendor: Test Vendor
"""
        
        with zipfile.ZipFile(jar_path, 'w') as zf:
            zf.writestr("META-INF/MANIFEST.MF", manifest_content)
        
        extractor = JavaExtractor()
        metadata = extractor.extract(str(jar_path))
        
        assert metadata.name == "Simple JAR"
        assert metadata.version == "2.0.0"
        assert metadata.package_type == PackageType.JAR
        # Implementation-Vendor might not be extracted as author
        # Check raw metadata instead
        assert "Test Vendor" in str(metadata.raw_metadata)


class TestRegistryMode:
    """Test registry mode functionality."""
    
    @patch('requests.get')
    def test_maven_parent_pom_fetch(self, mock_get, tmp_path):
        """Test fetching parent POM from Maven Central."""
        jar_path = tmp_path / "child.jar"
        
        # Child POM with parent reference
        child_pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.5.0</version>
    </parent>
    <artifactId>my-app</artifactId>
</project>"""
        
        # Mock parent POM response
        parent_pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.5.0</version>
    <description>Parent POM for Spring Boot</description>
</project>"""
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = parent_pom
        
        with zipfile.ZipFile(jar_path, 'w') as zf:
            zf.writestr("META-INF/maven/org.springframework.boot/my-app/pom.xml", child_pom)
        
        extractor = JavaExtractor(registry_mode=True)
        metadata = extractor.extract(str(jar_path))
        
        assert metadata.name == "org.springframework.boot:my-app"
        assert mock_get.called


class TestExtractorAutoDetection:
    """Test automatic package type detection and extraction."""
    
    def test_detect_and_extract_wheel(self, tmp_path):
        """Test detection and extraction of wheel files."""
        wheel_path = tmp_path / "package-1.0.0-py3-none-any.whl"

        # Create a minimal valid wheel file
        import zipfile
        with zipfile.ZipFile(wheel_path, 'w') as zf:
            zf.writestr("package/__init__.py", "")
            zf.writestr("package-1.0.0.dist-info/METADATA", "Name: package\nVersion: 1.0.0\n")

        from upmex.core.extractor import PackageExtractor

        extractor = PackageExtractor()
        metadata = extractor.extract(str(wheel_path))
        assert metadata.package_type == PackageType.PYTHON_WHEEL