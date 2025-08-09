"""Tests for package type detection."""

import pytest
import zipfile
import tarfile
import json
from pathlib import Path
from upmex.utils.package_detector import detect_package_type
from upmex.core.models import PackageType


class TestPackageDetection:
    """Test package type detection."""
    
    def test_detect_python_wheel(self, temp_dir):
        """Test detecting Python wheel files."""
        wheel_file = temp_dir / "test_package-1.0.0-py3-none-any.whl"
        
        # Create a minimal wheel file
        with zipfile.ZipFile(wheel_file, 'w') as zf:
            zf.writestr("test_package/__init__.py", "")
            zf.writestr("test_package-1.0.0.dist-info/METADATA", "Name: test-package")
        
        detected_type = detect_package_type(str(wheel_file))
        assert detected_type == PackageType.PYTHON_WHEEL
    
    def test_detect_python_sdist_tar_gz(self, temp_dir):
        """Test detecting Python source distribution tar.gz."""
        sdist_file = temp_dir / "test_package-1.0.0.tar.gz"
        
        # Create a minimal sdist
        with tarfile.open(sdist_file, 'w:gz') as tf:
            # Create PKG-INFO content
            pkg_info = "Name: test-package\nVersion: 1.0.0\n"
            
            # Add PKG-INFO file
            import io
            info = tarfile.TarInfo(name="test_package-1.0.0/PKG-INFO")
            info.size = len(pkg_info)
            tf.addfile(info, io.BytesIO(pkg_info.encode()))
        
        detected_type = detect_package_type(str(sdist_file))
        assert detected_type == PackageType.PYTHON_SDIST
    
    def test_detect_npm_package(self, temp_dir):
        """Test detecting NPM package."""
        npm_file = temp_dir / "test-package-1.0.0.tgz"
        
        # Create a minimal NPM package
        with tarfile.open(npm_file, 'w:gz') as tf:
            package_json = json.dumps({
                "name": "test-package",
                "version": "1.0.0"
            })
            
            import io
            info = tarfile.TarInfo(name="package/package.json")
            info.size = len(package_json)
            tf.addfile(info, io.BytesIO(package_json.encode()))
        
        detected_type = detect_package_type(str(npm_file))
        assert detected_type == PackageType.NPM
    
    def test_detect_jar_file(self, temp_dir):
        """Test detecting JAR file."""
        jar_file = temp_dir / "test.jar"
        
        # Create a minimal JAR file
        with zipfile.ZipFile(jar_file, 'w') as zf:
            manifest = "Manifest-Version: 1.0\nMain-Class: com.example.Main\n"
            zf.writestr("META-INF/MANIFEST.MF", manifest)
        
        detected_type = detect_package_type(str(jar_file))
        assert detected_type == PackageType.JAR
    
    def test_detect_maven_jar(self, temp_dir):
        """Test detecting Maven JAR with POM."""
        jar_file = temp_dir / "maven-artifact.jar"
        
        # Create a Maven JAR with pom.xml
        with zipfile.ZipFile(jar_file, 'w') as zf:
            manifest = "Manifest-Version: 1.0\n"
            zf.writestr("META-INF/MANIFEST.MF", manifest)
            
            pom_xml = """<?xml version="1.0"?>
            <project>
                <groupId>com.example</groupId>
                <artifactId>test</artifactId>
                <version>1.0.0</version>
            </project>"""
            zf.writestr("META-INF/maven/com.example/test/pom.xml", pom_xml)
        
        detected_type = detect_package_type(str(jar_file))
        assert detected_type == PackageType.MAVEN
    
    def test_detect_unknown_file(self, temp_dir):
        """Test detecting unknown file type."""
        unknown_file = temp_dir / "unknown.xyz"
        unknown_file.write_text("Some random content")
        
        detected_type = detect_package_type(str(unknown_file))
        assert detected_type == PackageType.UNKNOWN
    
    def test_detect_by_extension_priority(self, temp_dir):
        """Test that extension detection has priority."""
        # Create a file with .whl extension but NPM content
        weird_file = temp_dir / "weird.whl"
        
        with zipfile.ZipFile(weird_file, 'w') as zf:
            # Add NPM-like content to a .whl file
            zf.writestr("package.json", '{"name": "test"}')
        
        # Should still detect as wheel due to extension
        detected_type = detect_package_type(str(weird_file))
        assert detected_type == PackageType.PYTHON_WHEEL