"""Tests for data models."""

import pytest
from datetime import datetime
from upmex.core.models import (
    PackageMetadata,
    LicenseInfo,
    PackageType,
    LicenseConfidenceLevel
)


class TestLicenseInfo:
    """Test LicenseInfo model."""
    
    def test_default_values(self):
        """Test default values for LicenseInfo."""
        license_info = LicenseInfo()
        
        assert license_info.spdx_id is None
        assert license_info.name is None
        assert license_info.confidence == 0.0
        assert license_info.confidence_level == LicenseConfidenceLevel.NONE
    
    def test_with_values(self):
        """Test LicenseInfo with values."""
        license_info = LicenseInfo(
            spdx_id="MIT",
            name="MIT License",
            confidence=0.95,
            confidence_level=LicenseConfidenceLevel.HIGH,
            detection_method="regex"
        )
        
        assert license_info.spdx_id == "MIT"
        assert license_info.name == "MIT License"
        assert license_info.confidence == 0.95
        assert license_info.confidence_level == LicenseConfidenceLevel.HIGH
        assert license_info.detection_method == "regex"


class TestPackageMetadata:
    """Test PackageMetadata model."""
    
    def test_required_fields(self):
        """Test creating metadata with required fields only."""
        metadata = PackageMetadata(name="test-package")
        
        assert metadata.name == "test-package"
        assert metadata.version is None
        assert metadata.package_type == PackageType.UNKNOWN
        assert metadata.licenses == []
        assert metadata.dependencies == {}
        assert metadata.schema_version == "1.0.0"
    
    def test_full_metadata(self):
        """Test creating metadata with all fields."""
        license_info = LicenseInfo(
            spdx_id="MIT",
            confidence=0.95,
            confidence_level=LicenseConfidenceLevel.HIGH
        )
        
        metadata = PackageMetadata(
            name="test-package",
            version="1.0.0",
            package_type=PackageType.PYTHON_WHEEL,
            description="Test package",
            homepage="https://example.com",
            repository="https://github.com/example/test",
            authors=[{"name": "Test Author", "email": "test@example.com"}],
            licenses=[license_info],
            dependencies={"runtime": ["requests", "pyyaml"]},
            keywords=["test", "package"],
            file_size=1024,
            file_hash="abc123"
        )
        
        assert metadata.name == "test-package"
        assert metadata.version == "1.0.0"
        assert metadata.package_type == PackageType.PYTHON_WHEEL
        assert metadata.description == "Test package"
        assert len(metadata.licenses) == 1
        assert metadata.licenses[0].spdx_id == "MIT"
        assert "runtime" in metadata.dependencies
        assert len(metadata.dependencies["runtime"]) == 2
    
    def test_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = PackageMetadata(
            name="test-package",
            version="1.0.0",
            package_type=PackageType.NPM,
            licenses=[
                LicenseInfo(
                    spdx_id="MIT",
                    confidence=0.9,
                    confidence_level=LicenseConfidenceLevel.HIGH
                )
            ]
        )
        
        data = metadata.to_dict()
        
        assert data["name"] == "test-package"
        assert data["version"] == "1.0.0"
        assert data["package_type"] == "npm"
        assert data["schema_version"] == "1.0.0"
        assert len(data["licenses"]) == 1
        assert data["licenses"][0]["spdx_id"] == "MIT"
        assert data["licenses"][0]["confidence"] == 0.9
        assert data["licenses"][0]["confidence_level"] == "high"
        assert "extraction_timestamp" in data
    
    def test_package_types(self):
        """Test all package type enums."""
        types = [
            PackageType.PYTHON_WHEEL,
            PackageType.PYTHON_SDIST,
            PackageType.NPM,
            PackageType.MAVEN,
            PackageType.JAR,
            PackageType.GENERIC,
            PackageType.UNKNOWN
        ]
        
        for package_type in types:
            metadata = PackageMetadata(name="test", package_type=package_type)
            assert metadata.package_type == package_type
            assert package_type.value in metadata.to_dict()["package_type"]