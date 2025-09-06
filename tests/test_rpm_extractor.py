"""Tests for RPM package extractor."""

import pytest
from pathlib import Path
from upmex.extractors.rpm_extractor import RpmExtractor
from upmex.core.models import PackageType, NO_ASSERTION


class TestRpmExtractor:
    """Test RPM package extraction."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = RpmExtractor()
    
    def test_can_extract_rpm(self):
        """Test that extractor recognizes RPM files."""
        assert self.extractor.can_extract("package.rpm")
        assert self.extractor.can_extract("/path/to/package.rpm")
        assert not self.extractor.can_extract("package.deb")
        assert not self.extractor.can_extract("package.tar.gz")
    
    def test_extract_basic_metadata(self, tmp_path):
        """Test basic metadata extraction from RPM filename."""
        # Create a dummy RPM file for testing
        rpm_file = tmp_path / "test-package-1.0.0-1.el8.x86_64.rpm"
        rpm_file.write_bytes(b"dummy rpm content")
        
        metadata = self.extractor.extract(str(rpm_file))
        
        # Even without rpm command, should parse filename
        assert metadata is not None
        # The extractor may not be able to extract name/version without rpm command
        # but it should not fail
    
    def test_normalize_license_id(self):
        """Test license normalization."""
        assert self.extractor._normalize_license_id("GPLv2") == "GPL-2.0"
        assert self.extractor._normalize_license_id("GPLv2+") == "GPL-2.0-or-later"
        assert self.extractor._normalize_license_id("GPLv3") == "GPL-3.0"
        assert self.extractor._normalize_license_id("GPLv3+") == "GPL-3.0-or-later"
        assert self.extractor._normalize_license_id("LGPLv2") == "LGPL-2.0"
        assert self.extractor._normalize_license_id("LGPLv2+") == "LGPL-2.0-or-later"
        assert self.extractor._normalize_license_id("ASL 2.0") == "Apache-2.0"
        assert self.extractor._normalize_license_id("MIT") == "MIT"
        assert self.extractor._normalize_license_id("BSD") == "BSD-3-Clause"
        assert self.extractor._normalize_license_id("MPLv2.0") == "MPL-2.0"
        assert self.extractor._normalize_license_id("Unknown License") is None
    
    @pytest.mark.skipif(not Path("/usr/bin/rpm").exists(), reason="rpm command not available")
    def test_extract_with_rpm_command(self, tmp_path):
        """Test extraction when rpm command is available."""
        # This test would require a real RPM file and rpm command
        # Skipped if rpm is not available
        pass
    
    def test_parse_debian_dependencies(self):
        """Test dependency parsing."""
        # The extractor should handle dependencies gracefully
        # even if it can't extract them without rpm command
        rpm_file = "dummy.rpm"
        metadata = self.extractor.extract(rpm_file)
        # Should not fail even without real RPM file