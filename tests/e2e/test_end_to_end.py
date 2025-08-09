"""End-to-end tests for the complete extraction pipeline."""

import pytest
import json
import tempfile
import zipfile
import tarfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from upmex.cli import cli
from upmex.core.extractor import PackageExtractor
from upmex.core.models import PackageType, PackageMetadata


class TestCLIEndToEnd:
    """Test CLI commands end-to-end."""
    
    def test_extract_command_json_output(self, tmp_path):
        """Test extract command with JSON output."""
        # Create a mock package
        package_path = tmp_path / "test-1.0.0-py3-none-any.whl"
        
        with zipfile.ZipFile(package_path, 'w') as zf:
            metadata_content = """Metadata-Version: 2.1
Name: test-package
Version: 1.0.0
Summary: Test package for E2E
Author: Test Author
Author-email: test@example.com
License: MIT
"""
            zf.writestr("test-1.0.0.dist-info/METADATA", metadata_content)
        
        runner = CliRunner()
        result = runner.invoke(cli, ['extract', str(package_path), '--format', 'json'])
        
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["name"] == "test-package"
        assert output["version"] == "1.0.0"
        assert output["description"] == "Test package for E2E"
    
    def test_extract_command_text_output(self, tmp_path):
        """Test extract command with text output."""
        package_path = tmp_path / "test.jar"
        
        with zipfile.ZipFile(package_path, 'w') as zf:
            manifest = """Manifest-Version: 1.0
Implementation-Title: Test JAR
Implementation-Version: 1.0.0
"""
            zf.writestr("META-INF/MANIFEST.MF", manifest)
        
        runner = CliRunner()
        result = runner.invoke(cli, ['extract', str(package_path), '--format', 'text'])
        
        assert result.exit_code == 0
        assert "Test JAR" in result.output
        assert "1.0.0" in result.output
    
    def test_extract_command_with_output_file(self, tmp_path):
        """Test extract command with output file."""
        package_path = tmp_path / "package.tgz"
        output_path = tmp_path / "output.json"
        
        # Create mock npm package
        package_json = {
            "name": "test-npm",
            "version": "2.0.0",
            "description": "Test NPM package"
        }
        
        with tarfile.open(package_path, 'w:gz') as tf:
            info = tarfile.TarInfo(name="package/package.json")
            content = json.dumps(package_json).encode()
            info.size = len(content)
            
            # Create a proper file object for the content
            import io
            content_file = io.BytesIO(content)
            tf.addfile(info, fileobj=content_file)
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            'extract', str(package_path),
            '--output', str(output_path),
            '--format', 'json'
        ])
        
        assert result.exit_code == 0
        assert output_path.exists()
        
        with open(output_path) as f:
            data = json.load(f)
            assert data["name"] == "test-npm"
            assert data["version"] == "2.0.0"
    
    @patch('requests.get')
    def test_extract_with_online_mode(self, mock_get, tmp_path):
        """Test extraction with online mode enabled."""
        # Create Maven package with parent POM
        jar_path = tmp_path / "child.jar"
        
        child_pom = """<?xml version="1.0"?>
<project>
    <parent>
        <groupId>org.parent</groupId>
        <artifactId>parent-pom</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>child-artifact</artifactId>
</project>"""
        
        with zipfile.ZipFile(jar_path, 'w') as zf:
            zf.writestr("META-INF/maven/org.parent/child-artifact/pom.xml", child_pom)
        
        # Mock parent POM fetch
        parent_pom = """<?xml version="1.0"?>
<project>
    <groupId>org.parent</groupId>
    <artifactId>parent-pom</artifactId>
    <version>1.0.0</version>
    <description>Parent POM Description</description>
</project>"""
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = parent_pom
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            'extract', str(jar_path),
            '--online',
            '--format', 'json'
        ])
        
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "org.parent:child-artifact" in output["name"]
    
    def test_detect_command(self, tmp_path):
        """Test detect command."""
        # Create files with different extensions
        files = [
            ("package.whl", PackageType.PYTHON_WHEEL),
            ("package.tar.gz", PackageType.PYTHON_SDIST),
            ("package.tgz", PackageType.NPM),
            ("package.jar", PackageType.JAR)
        ]
        
        runner = CliRunner()
        
        for filename, expected_type in files:
            file_path = tmp_path / filename
            file_path.touch()
            
            result = runner.invoke(cli, ['detect', str(file_path)])
            assert result.exit_code == 0
            assert expected_type.value in result.output
    
    def test_detect_command_verbose(self, tmp_path):
        """Test detect command with verbose output."""
        file_path = tmp_path / "test.whl"
        file_path.write_text("test content")
        
        runner = CliRunner()
        result = runner.invoke(cli, ['detect', str(file_path), '--verbose'])
        
        assert result.exit_code == 0
        assert "File: test.whl" in result.output
        assert "Size:" in result.output
        assert "Type: python_wheel" in result.output
    
    def test_license_command(self, tmp_path):
        """Test license extraction command."""
        package_path = tmp_path / "licensed-1.0.0-py3-none-any.whl"
        
        with zipfile.ZipFile(package_path, 'w') as zf:
            metadata = """Metadata-Version: 2.1
Name: licensed-package
Version: 1.0.0
License: Apache-2.0
"""
            zf.writestr("licensed-1.0.0.dist-info/METADATA", metadata)
            
            # Add LICENSE file
            license_text = "Apache License Version 2.0"
            zf.writestr("licensed-1.0.0.dist-info/LICENSE", license_text)
        
        runner = CliRunner()
        result = runner.invoke(cli, ['license', str(package_path)])
        
        assert result.exit_code == 0
        # The output would show license info if properly extracted
        # For now, we're just checking the command runs
    
    def test_info_command(self):
        """Test info command."""
        runner = CliRunner()
        
        # Test default text output
        result = runner.invoke(cli, ['info'])
        assert result.exit_code == 0
        assert "UPMEX - Universal Package Metadata Extractor" in result.output
        assert "Supported Package Types:" in result.output
        assert "python_wheel" in result.output
        
        # Test JSON output
        result = runner.invoke(cli, ['info', '--json'])
        assert result.exit_code == 0
        info = json.loads(result.output)
        assert "version" in info
        assert "supported_packages" in info
        assert len(info["supported_packages"]) > 0


class TestFullPipeline:
    """Test complete extraction pipeline."""
    
    def test_python_wheel_full_extraction(self, tmp_path):
        """Test full extraction pipeline for Python wheel."""
        wheel_path = tmp_path / "complete-1.0.0-py3-none-any.whl"
        
        with zipfile.ZipFile(wheel_path, 'w') as zf:
            # Add comprehensive metadata
            metadata = """Metadata-Version: 2.1
Name: complete-package
Version: 1.0.0
Summary: A complete test package
Home-page: https://example.com
Author: John Doe
Author-email: john@example.com
License: MIT
Classifier: Development Status :: 5 - Production/Stable
Classifier: Programming Language :: Python :: 3
Classifier: License :: OSI Approved :: MIT License
Keywords: test complete example
Requires-Dist: requests>=2.0.0
Requires-Dist: click>=8.0.0
Provides-Extra: dev
Requires-Dist: pytest>=7.0.0; extra == "dev"
"""
            zf.writestr("complete-1.0.0.dist-info/METADATA", metadata)
            
            # Add LICENSE
            zf.writestr("complete-1.0.0.dist-info/LICENSE", "MIT License\n\nCopyright (c) 2024")
            
            # Add top_level.txt
            zf.writestr("complete-1.0.0.dist-info/top_level.txt", "complete")
        
        extractor = PackageExtractor()
        metadata = extractor.extract(str(wheel_path))
        
        assert metadata.name == "complete-package"
        assert metadata.version == "1.0.0"
        assert metadata.description == "A complete test package"
        assert metadata.homepage == "https://example.com"
        assert metadata.package_type == PackageType.PYTHON_WHEEL
        
        assert len(metadata.authors) > 0
        assert metadata.authors[0]["name"] == "John Doe"
        assert metadata.authors[0]["email"] == "john@example.com"
        
        assert "requests" in metadata.dependencies.get("runtime", [])
        assert "click" in metadata.dependencies.get("runtime", [])
        assert "pytest" in metadata.dependencies.get("dev", [])
        
        assert "test" in metadata.keywords
        assert "complete" in metadata.keywords
        
        assert len(metadata.classifiers) == 3
    
    @patch('requests.get')
    def test_maven_jar_with_online_enrichment(self, mock_get, tmp_path):
        """Test Maven JAR extraction with online enrichment."""
        jar_path = tmp_path / "maven-artifact-1.0.0.jar"
        
        # Create JAR with POM
        pom_xml = """<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>maven-artifact</artifactId>
    <version>1.0.0</version>
    <description>Maven test artifact</description>
    <url>https://example.com/maven</url>
    <developers>
        <developer>
            <id>dev1</id>
            <name>Developer One</name>
            <email>dev1@example.com</email>
        </developer>
    </developers>
    <licenses>
        <license>
            <name>Apache License, Version 2.0</name>
            <url>https://www.apache.org/licenses/LICENSE-2.0</url>
        </license>
    </licenses>
    <scm>
        <url>https://github.com/example/maven-artifact</url>
        <connection>scm:git:https://github.com/example/maven-artifact.git</connection>
    </scm>
    <dependencies>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>5.3.0</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>"""
        
        with zipfile.ZipFile(jar_path, 'w') as zf:
            zf.writestr("META-INF/maven/com.example/maven-artifact/pom.xml", pom_xml)
        
        # Mock ClearlyDefined response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "licensed": {
                "declared": "Apache-2.0"
            }
        }
        
        extractor = PackageExtractor({"online_mode": True})
        metadata = extractor.extract(str(jar_path))
        
        assert metadata.name == "com.example:maven-artifact"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Maven test artifact"
        assert metadata.homepage == "https://example.com/maven"
        assert metadata.repository == "https://github.com/example/maven-artifact.git"
        assert metadata.package_type == PackageType.MAVEN
        
        assert len(metadata.authors) > 0
        assert metadata.authors[0]["name"] == "Developer One"
        assert metadata.authors[0]["email"] == "dev1@example.com"
        
        assert "org.springframework:spring-core" in metadata.dependencies.get("runtime", [])
        assert "junit:junit" in metadata.dependencies.get("test", [])
    
    def test_npm_package_full_extraction(self, tmp_path):
        """Test full NPM package extraction."""
        tgz_path = tmp_path / "npm-package-1.0.0.tgz"
        
        package_json = {
            "name": "@scope/npm-package",
            "version": "1.0.0",
            "description": "Complete NPM package test",
            "main": "index.js",
            "scripts": {
                "test": "jest",
                "build": "webpack"
            },
            "repository": {
                "type": "git",
                "url": "git+https://github.com/scope/npm-package.git"
            },
            "keywords": ["npm", "test", "package"],
            "author": {
                "name": "NPM Author",
                "email": "npm@example.com",
                "url": "https://example.com"
            },
            "contributors": [
                {
                    "name": "Contributor One",
                    "email": "contrib1@example.com"
                }
            ],
            "license": "ISC",
            "bugs": {
                "url": "https://github.com/scope/npm-package/issues"
            },
            "homepage": "https://github.com/scope/npm-package#readme",
            "dependencies": {
                "express": "^4.18.0",
                "lodash": "^4.17.21"
            },
            "devDependencies": {
                "jest": "^29.0.0",
                "webpack": "^5.0.0"
            },
            "peerDependencies": {
                "react": "^18.0.0"
            }
        }
        
        # Create proper tgz structure
        import io
        with tarfile.open(tgz_path, 'w:gz') as tf:
            # Create package.json tarinfo
            info = tarfile.TarInfo(name="package/package.json")
            content = json.dumps(package_json, indent=2).encode()
            info.size = len(content)
            
            # Add to archive
            tf.addfile(info, fileobj=io.BytesIO(content))
            
            # Add README
            readme_info = tarfile.TarInfo(name="package/README.md")
            readme_content = b"# NPM Package\n\nTest package for E2E testing"
            readme_info.size = len(readme_content)
            tf.addfile(readme_info, fileobj=io.BytesIO(readme_content))
        
        extractor = PackageExtractor()
        metadata = extractor.extract(str(tgz_path))
        
        assert metadata.name == "@scope/npm-package"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Complete NPM package test"
        assert metadata.homepage == "https://github.com/scope/npm-package#readme"
        assert metadata.repository == "git+https://github.com/scope/npm-package.git"
        assert metadata.package_type == PackageType.NPM
        
        assert len(metadata.authors) > 0
        assert metadata.authors[0]["name"] == "NPM Author"
        assert metadata.authors[0]["email"] == "npm@example.com"
        
        assert "express" in metadata.dependencies.get("runtime", [])
        assert "lodash" in metadata.dependencies.get("runtime", [])
        assert "jest" in metadata.dependencies.get("dev", [])
        assert "webpack" in metadata.dependencies.get("dev", [])
        assert "react" in metadata.dependencies.get("peer", [])
        
        assert "npm" in metadata.keywords
        assert "test" in metadata.keywords
        assert "package" in metadata.keywords


class TestErrorHandling:
    """Test error handling throughout the pipeline."""
    
    def test_invalid_package_file(self, tmp_path):
        """Test handling of invalid package files."""
        invalid_file = tmp_path / "invalid.txt"
        invalid_file.write_text("This is not a package")
        
        runner = CliRunner()
        result = runner.invoke(cli, ['extract', str(invalid_file)])
        
        # Should handle gracefully, though exit code might be non-zero
        assert "Error" in result.output or result.exit_code != 0
    
    def test_corrupted_zip_file(self, tmp_path):
        """Test handling of corrupted archive files."""
        corrupted = tmp_path / "corrupted.whl"
        corrupted.write_bytes(b"This is not a valid zip file")
        
        extractor = PackageExtractor()
        metadata = extractor.extract(str(corrupted))
        
        # Should return basic metadata without crashing
        assert metadata.name == "unknown" or metadata.name == "corrupted"
        assert metadata.package_type in [PackageType.UNKNOWN, PackageType.PYTHON_WHEEL]
    
    def test_missing_metadata_files(self, tmp_path):
        """Test handling packages with missing metadata."""
        # Create wheel without METADATA file
        wheel_path = tmp_path / "empty-1.0.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, 'w') as zf:
            zf.writestr("empty/__init__.py", "# Empty package")
        
        extractor = PackageExtractor()
        metadata = extractor.extract(str(wheel_path))
        
        # Should handle missing metadata gracefully
        assert metadata.name == "unknown" or metadata.name == "empty"
        assert metadata.package_type == PackageType.PYTHON_WHEEL
    
    @patch('requests.get')
    def test_api_timeout_handling(self, mock_get, tmp_path):
        """Test handling of API timeouts."""
        import requests
        mock_get.side_effect = requests.Timeout("API timeout")
        
        package_path = tmp_path / "package.whl"
        package_path.touch()
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            'extract', str(package_path),
            '--online',
            '--api', 'clearlydefined'
        ])
        
        # Should complete without API data
        assert result.exit_code == 0 or "timeout" in result.output.lower()
    
    def test_nonexistent_file(self):
        """Test handling of non-existent files."""
        runner = CliRunner()
        result = runner.invoke(cli, ['extract', '/nonexistent/package.whl'])
        
        assert result.exit_code != 0
        assert "Error" in result.output or "not found" in result.output.lower()