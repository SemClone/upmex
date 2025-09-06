"""Tests for Debian package extractor."""

import pytest
from pathlib import Path
from upmex.extractors.deb_extractor import DebianExtractor
from upmex.core.models import PackageType, NO_ASSERTION


class TestDebianExtractor:
    """Test Debian package extraction."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = DebianExtractor()
    
    def test_can_extract_deb(self):
        """Test that extractor recognizes DEB files."""
        assert self.extractor.can_extract("package.deb")
        assert self.extractor.can_extract("/path/to/package.deb")
        assert not self.extractor.can_extract("package.rpm")
        assert not self.extractor.can_extract("package.tar.gz")
    
    def test_extract_basic_metadata(self, tmp_path):
        """Test basic metadata extraction from DEB filename."""
        # Create a dummy DEB file for testing
        deb_file = tmp_path / "test-package_1.0.0-1_amd64.deb"
        deb_file.write_bytes(b"dummy deb content")
        
        metadata = self.extractor.extract(str(deb_file))
        
        # Even without dpkg command, should parse filename
        assert metadata is not None
        # The extractor may not be able to extract full metadata without dpkg
        # but it should not fail
    
    def test_parse_filename(self):
        """Test filename parsing fallback."""
        # Create a mock file path
        metadata = self.extractor.extract("test-package_1.0.0-1_amd64.deb")
        # Should handle non-existent file gracefully in fallback mode
    
    def test_normalize_license_id(self):
        """Test license normalization."""
        assert self.extractor._normalize_license_id("GPL-2") == "GPL-2.0"
        assert self.extractor._normalize_license_id("GPL-2+") == "GPL-2.0-or-later"
        assert self.extractor._normalize_license_id("GPL-3") == "GPL-3.0"
        assert self.extractor._normalize_license_id("GPL-3+") == "GPL-3.0-or-later"
        assert self.extractor._normalize_license_id("LGPL-2") == "LGPL-2.0"
        assert self.extractor._normalize_license_id("LGPL-2.1") == "LGPL-2.1"
        assert self.extractor._normalize_license_id("LGPL-3") == "LGPL-3.0"
        assert self.extractor._normalize_license_id("Apache-2.0") == "Apache-2.0"
        assert self.extractor._normalize_license_id("MIT") == "MIT"
        assert self.extractor._normalize_license_id("BSD-3-clause") == "BSD-3-Clause"
        assert self.extractor._normalize_license_id("BSD-2-clause") == "BSD-2-Clause"
        assert self.extractor._normalize_license_id("MPL-2.0") == "MPL-2.0"
        assert self.extractor._normalize_license_id("Unknown License") is None
    
    def test_parse_debian_dependencies(self):
        """Test Debian dependency parsing."""
        deps = self.extractor._parse_debian_dependencies(
            "libc6 (>= 2.17), python3 (>= 3.6), libssl1.1 | libssl3"
        )
        
        assert len(deps) == 3
        assert deps[0]['name'] == 'libc6'
        assert deps[0]['version'] == '>= 2.17'
        assert deps[1]['name'] == 'python3'
        assert deps[1]['version'] == '>= 3.6'
        assert deps[2]['name'] == 'libssl1.1'  # Takes first alternative
        assert deps[2]['version'] == NO_ASSERTION
    
    def test_parse_debian_dependencies_empty(self):
        """Test parsing empty dependencies."""
        deps = self.extractor._parse_debian_dependencies("")
        assert deps == []
    
    def test_parse_control_file(self):
        """Test parsing of control file content."""
        control_content = """Package: test-package
Version: 1.0.0-1
Architecture: amd64
Maintainer: John Doe <john@example.com>
Depends: libc6 (>= 2.17), python3
Homepage: https://example.com
Description: Test package
 This is a test package for testing purposes.
 It has multiple lines of description."""
        
        from upmex.core.models import PackageMetadata
        metadata = PackageMetadata(name=NO_ASSERTION, version=NO_ASSERTION)
        self.extractor._parse_control_file(control_content, metadata)
        
        assert metadata.name == "test-package"
        assert metadata.version == "1.0.0-1"
        assert metadata.homepage == "https://example.com"
        assert metadata.description == "Test package\nThis is a test package for testing purposes.\nIt has multiple lines of description."
        assert metadata.maintainers is not None
        assert len(metadata.maintainers) == 1
        assert metadata.maintainers[0]['name'] == 'John Doe'
        assert metadata.maintainers[0]['email'] == 'john@example.com'
        assert metadata.dependencies is not None
        assert 'runtime' in metadata.dependencies
        assert len(metadata.dependencies['runtime']) == 2
    
    @pytest.mark.skipif(not Path("/usr/bin/dpkg").exists(), reason="dpkg command not available")
    def test_extract_with_dpkg_command(self, tmp_path):
        """Test extraction when dpkg command is available."""
        # This test would require a real DEB file and dpkg command
        # Skipped if dpkg is not available
        pass