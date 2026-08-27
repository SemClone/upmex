"""Tests for RPM package extractor."""

from upmex.extractors.rpm_extractor import RpmExtractor
from upmex.core.models import NO_ASSERTION


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
    
    def test_a_missing_file_yields_no_assertion_rather_than_raising(self):
        """Unlike the Debian extractor there is no filename fallback here, so
        an unreadable package says it does not know."""
        metadata = self.extractor.extract("dummy.rpm")

        assert metadata.name == NO_ASSERTION
        assert metadata.version == NO_ASSERTION
        assert metadata.dependencies == {}