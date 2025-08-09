"""Unit tests for license detection using regex patterns."""

import pytest
from upmex.utils.license_detector import LicenseDetector
from upmex.core.models import LicenseConfidenceLevel


class TestLicenseDetector:
    """Test license detection functionality."""
    
    @pytest.fixture
    def detector(self):
        """Create a license detector instance."""
        return LicenseDetector()
    
    def test_detect_mit_license(self, detector):
        """Test detection of MIT license."""
        texts = [
            "MIT",
            "MIT License",
            "The MIT License",
            "Licensed under the MIT License",
            "License: MIT"
        ]
        
        for text in texts:
            result = detector.detect_license_from_text(text)
            assert result is not None
            assert result.spdx_id == "MIT"
            assert result.confidence > 0.5
    
    def test_detect_apache_license(self, detector):
        """Test detection of Apache licenses."""
        texts = [
            "Apache-2.0",
            "Apache License 2.0",
            "Apache License, Version 2.0",
            "Licensed under the Apache License, Version 2.0",
            "Apache Software License 2.0"
        ]
        
        for text in texts:
            result = detector.detect_license_from_text(text)
            assert result is not None
            assert result.spdx_id == "Apache-2.0"
    
    def test_detect_gpl_licenses(self, detector):
        """Test detection of GPL licenses."""
        # GPL-3.0
        result = detector.detect_license_from_text("GPL-3.0")
        assert result.spdx_id == "GPL-3.0"
        
        result = detector.detect_license_from_text("GNU General Public License v3")
        assert result.spdx_id == "GPL-3.0"
        
        # GPL-2.0
        result = detector.detect_license_from_text("GPLv2")
        assert result.spdx_id == "GPL-2.0"
    
    def test_detect_bsd_licenses(self, detector):
        """Test detection of BSD licenses."""
        # BSD-3-Clause
        result = detector.detect_license_from_text("BSD-3-Clause")
        assert result.spdx_id == "BSD-3-Clause"
        
        result = detector.detect_license_from_text("New BSD License")
        assert result.spdx_id == "BSD-3-Clause"
        
        # BSD-2-Clause
        result = detector.detect_license_from_text("Simplified BSD")
        assert result.spdx_id == "BSD-2-Clause"
    
    def test_detect_from_spdx_identifier(self, detector):
        """Test detection from SPDX-License-Identifier."""
        text = """
        // SPDX-License-Identifier: Apache-2.0
        // Copyright 2024 Example Corp
        """
        result = detector.detect_license_from_text(text)
        assert result is not None
        assert result.spdx_id == "Apache-2.0"
        assert result.confidence >= 0.8
    
    def test_detect_from_package_json_format(self, detector):
        """Test detection from package.json license field."""
        text = '"license": "ISC"'
        result = detector.detect_license_from_text(text)
        assert result is not None
        assert result.spdx_id == "ISC"
    
    def test_detect_from_pom_xml_format(self, detector):
        """Test detection from Maven POM format."""
        text = """
        <license>
            <name>Eclipse Public License 2.0</name>
        </license>
        """
        result = detector.detect_license_from_text(text)
        assert result is not None
        assert result.spdx_id == "EPL-2.0"
    
    def test_detect_from_python_classifier(self, detector):
        """Test detection from Python classifier."""
        text = "License :: OSI Approved :: MIT License"
        result = detector.detect_license_from_text(text)
        assert result is not None
        assert result.spdx_id == "MIT"
    
    def test_detect_from_metadata_dict(self, detector):
        """Test detection from structured metadata."""
        # Simple string license
        metadata = {"license": "MIT"}
        result = detector.detect_license_from_metadata(metadata)
        assert result is not None
        assert result.spdx_id == "MIT"
        
        # License in list format
        metadata = {"licenses": ["Apache-2.0", "MIT"]}
        result = detector.detect_license_from_metadata(metadata)
        assert result is not None
        assert result.spdx_id == "Apache-2.0"  # First license
        
        # License as dict with type
        metadata = {"license": {"type": "ISC", "url": "https://example.com"}}
        result = detector.detect_license_from_metadata(metadata)
        assert result is not None
        assert result.spdx_id == "ISC"
    
    def test_normalize_to_spdx(self, detector):
        """Test normalization of license strings to SPDX IDs."""
        assert detector._normalize_to_spdx("MIT") == "MIT"
        assert detector._normalize_to_spdx("mit") == "MIT"
        assert detector._normalize_to_spdx("MIT License") == "MIT"
        assert detector._normalize_to_spdx("Apache 2.0") == "Apache-2.0"
        assert detector._normalize_to_spdx("GPLv3") == "GPL-3.0"
        assert detector._normalize_to_spdx("New BSD") == "BSD-3-Clause"
        assert detector._normalize_to_spdx("Unknown License") is None
    
    def test_confidence_levels(self, detector):
        """Test confidence level calculation."""
        # High confidence from license field
        text = 'license = "MIT"'
        result = detector.detect_license_from_text(text)
        assert result.confidence >= 0.9
        assert result.confidence_level == LicenseConfidenceLevel.HIGH
        
        # Lower confidence from general text
        text = "This software uses the MIT license somewhere"
        result = detector.detect_license_from_text(text)
        assert result is not None
        assert result.confidence < 0.9
    
    def test_is_license_file(self, detector):
        """Test license file detection."""
        assert detector.is_license_file("LICENSE")
        assert detector.is_license_file("LICENSE.txt")
        assert detector.is_license_file("LICENSE.md")
        assert detector.is_license_file("COPYING")
        assert detector.is_license_file("COPYRIGHT")
        assert detector.is_license_file("NOTICE")
        assert not detector.is_license_file("README.md")
        assert not detector.is_license_file("setup.py")
    
    def test_detect_multiple_licenses(self, detector):
        """Test detection of multiple licenses."""
        text = """
        This project is dual-licensed under MIT and Apache-2.0.
        You may choose either license for your use.
        """
        licenses = detector.detect_multiple_licenses(text)
        assert len(licenses) >= 2
        spdx_ids = [lic.spdx_id for lic in licenses]
        assert "MIT" in spdx_ids
        assert "Apache-2.0" in spdx_ids
    
    def test_no_license_detected(self, detector):
        """Test when no license is detected."""
        result = detector.detect_license_from_text("This is just some random text")
        assert result is None
        
        result = detector.detect_license_from_metadata({"name": "package"})
        assert result is None
    
    def test_proprietary_license(self, detector):
        """Test detection of proprietary/commercial licenses."""
        texts = [
            "Proprietary",
            "Commercial License",
            "All Rights Reserved",
            "Closed Source"
        ]
        
        for text in texts:
            result = detector.detect_license_from_text(text)
            assert result is not None
            assert result.spdx_id == "Proprietary"
    
    def test_public_domain(self, detector):
        """Test detection of public domain licenses."""
        texts = [
            "CC0-1.0",
            "Creative Commons Zero",
            "Public Domain",
            "Unlicense"
        ]
        
        for text in texts:
            result = detector.detect_license_from_text(text)
            assert result is not None
            assert result.spdx_id in ["CC0-1.0", "Unlicense"]
    
    def test_context_based_confidence(self, detector):
        """Test that context affects confidence scores."""
        # License in a LICENSE file should have higher confidence
        result1 = detector.detect_license_from_text("MIT", filename="LICENSE")
        result2 = detector.detect_license_from_text("MIT", filename="random.txt")
        
        assert result1.confidence > result2.confidence
        
        # SPDX identifier should boost confidence
        result3 = detector.detect_license_from_text("SPDX-License-Identifier: MIT")
        assert result3.confidence > result2.confidence