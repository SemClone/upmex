"""Unit tests for NuGet package extractor."""

import pytest
from pathlib import Path
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from upmex.extractors.nuget_extractor import NuGetExtractor
from upmex.core.models import PackageType, NO_ASSERTION


class TestNuGetExtractor:
    """Test NuGet package extraction."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = NuGetExtractor()
    
    def test_detect_nuget_package_by_extension(self):
        """Test detecting NuGet package by .nupkg extension."""
        with tempfile.NamedTemporaryFile(suffix='.nupkg') as f:
            assert self.extractor.can_extract(f.name)
    
    def test_detect_nuget_package_type(self):
        """Test detecting NuGet package type."""
        with tempfile.NamedTemporaryFile(suffix='.nupkg') as f:
            path = Path(f.name)
            assert self.extractor.detect_package_type(path) == 'nuget'
    
    def test_extract_basic_nuget_metadata(self):
        """Test extracting basic metadata from a NuGet package."""
        # Create a test .nupkg file
        with tempfile.NamedTemporaryFile(suffix='.nupkg', delete=False) as f:
            # Create a minimal .nuspec XML
            nuspec_content = '''<?xml version="1.0"?>
            <package xmlns="http://schemas.microsoft.com/packaging/2010/07/nuspec.xsd">
                <metadata>
                    <id>TestPackage</id>
                    <version>1.0.0</version>
                    <authors>Test Author</authors>
                    <description>Test description</description>
                    <projectUrl>https://example.com</projectUrl>
                    <repositoryUrl>https://github.com/test/repo</repositoryUrl>
                    <tags>test sample</tags>
                </metadata>
            </package>'''
            
            # Create .nupkg (ZIP file)
            with zipfile.ZipFile(f.name, 'w') as zf:
                zf.writestr('TestPackage.nuspec', nuspec_content)
            
            # Extract metadata
            metadata = self.extractor.extract(f.name)
            
            # Verify basic metadata
            assert metadata.name == 'TestPackage'
            assert metadata.version == '1.0.0'
            assert metadata.description == 'Test description'
            assert metadata.homepage == 'https://example.com'
            assert metadata.repository == 'https://github.com/test/repo'
            assert metadata.package_type == PackageType.NUGET
            assert len(metadata.authors) == 1
            assert metadata.authors[0]['name'] == 'Test Author'
            assert metadata.keywords == ['test', 'sample']
            
            # Clean up
            Path(f.name).unlink()
    
    def test_extract_dependencies(self):
        """Test extracting dependencies from NuGet package."""
        # Create a test .nupkg file with dependencies
        with tempfile.NamedTemporaryFile(suffix='.nupkg', delete=False) as f:
            nuspec_content = '''<?xml version="1.0"?>
            <package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
                <metadata>
                    <id>TestPackage</id>
                    <version>1.0.0</version>
                    <description>Test</description>
                    <dependencies>
                        <group targetFramework=".NETStandard2.0">
                            <dependency id="Newtonsoft.Json" version="13.0.1" />
                            <dependency id="System.Text.Json" version="6.0.0" />
                        </group>
                        <group targetFramework=".NETFramework4.5">
                            <dependency id="EntityFramework" version="6.4.4" />
                        </group>
                    </dependencies>
                </metadata>
            </package>'''
            
            with zipfile.ZipFile(f.name, 'w') as zf:
                zf.writestr('TestPackage.nuspec', nuspec_content)
            
            metadata = self.extractor.extract(f.name)
            
            # Check dependencies
            assert 'runtime' in metadata.dependencies
            assert len(metadata.dependencies['runtime']) == 3
            assert any('Newtonsoft.Json 13.0.1' in dep for dep in metadata.dependencies['runtime'])
            assert any('.NETStandard2.0' in dep for dep in metadata.dependencies['runtime'])
            
            Path(f.name).unlink()
    
    def test_extract_license_expression(self):
        """Test extracting license from expression."""
        with tempfile.NamedTemporaryFile(suffix='.nupkg', delete=False) as f:
            nuspec_content = '''<?xml version="1.0"?>
            <package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
                <metadata>
                    <id>TestPackage</id>
                    <version>1.0.0</version>
                    <description>Test</description>
                    <license type="expression">MIT</license>
                </metadata>
            </package>'''
            
            with zipfile.ZipFile(f.name, 'w') as zf:
                zf.writestr('TestPackage.nuspec', nuspec_content)
            
            metadata = self.extractor.extract(f.name)
            
            # Check license detection
            assert len(metadata.licenses) == 1
            assert metadata.licenses[0].spdx_id == 'MIT'
            
            Path(f.name).unlink()