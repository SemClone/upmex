"""Tests for Perl/CPAN package extractor."""

import os
import json
import tempfile
import tarfile
from unittest.mock import Mock, patch
from src.upmex.extractors.perl_extractor import PerlExtractor
from src.upmex.core.models import PackageType, NO_ASSERTION


class TestPerlExtractor:
    """Test Perl/CPAN package extraction."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = PerlExtractor()
    
    def test_extract_perl_metadata_json(self):
        """Test extracting metadata from Perl package with META.json."""
        # Create test META.json content
        meta_content = {
            "name": "Test-Module",
            "version": "1.23",
            "abstract": "A test Perl module",
            "author": ["John Doe <john@example.com>"],
            "license": ["perl_5"],
            "prereqs": {
                "runtime": {
                    "requires": {
                        "Moose": "2.0",
                        "JSON": "0"
                    }
                },
                "test": {
                    "requires": {
                        "Test::More": "0.96"
                    }
                }
            },
            "resources": {
                "homepage": "https://example.com",
                "repository": {
                    "url": "https://github.com/user/test-module"
                }
            },
            "keywords": ["testing", "module"]
        }
        
        # Create a temporary Perl package
        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            
            # Create tarball with META.json
            with tarfile.open(tmp_path, 'w:gz') as tar:
                # Create META.json
                meta_info = tarfile.TarInfo(name='Test-Module-1.23/META.json')
                meta_data = json.dumps(meta_content).encode('utf-8')
                meta_info.size = len(meta_data)
                tar.addfile(meta_info, fileobj=tempfile.SpooledTemporaryFile(max_size=len(meta_data)))
                tar.fileobj.write(meta_data)
        
        try:
            # Extract metadata
            metadata = self.extractor.extract(tmp_path)
            
            # Verify extraction
            assert metadata.name == "Test-Module"
            assert metadata.version == "1.23"
            assert metadata.package_type == PackageType.PERL
            assert metadata.description == "A test Perl module"
            assert metadata.homepage == "https://example.com"
            assert metadata.repository == "https://github.com/user/test-module"
            assert metadata.keywords == ["testing", "module"]
            
            # Check authors
            assert len(metadata.authors) == 1
            assert metadata.authors[0]['name'] == "John Doe"
            assert metadata.authors[0]['email'] == "john@example.com"
            
            # Check license
            assert len(metadata.licenses) == 1
            assert metadata.licenses[0].spdx_id == "Artistic-1.0 OR GPL-1.0-or-later"
            
            # Check dependencies
            deps = {d['name']: d['version'] for d in metadata.dependencies}
            assert 'Moose' in deps
            assert deps['Moose'] == '2.0'
            assert 'Test::More' in deps
            
        finally:
            os.unlink(tmp_path)
    
    def test_extract_perl_metadata_yml(self):
        """Test extracting metadata from Perl package with META.yml."""
        # Create a temporary Perl package with META.yml
        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            
            # Create tarball with META.yml
            with tarfile.open(tmp_path, 'w:gz') as tar:
                # Create META.yml (basic format)
                yml_content = """---
name: YAML-Module
version: 2.34
abstract: A YAML test module
author:
  - Jane Smith <jane@example.com>
license: mit
"""
                yml_info = tarfile.TarInfo(name='YAML-Module-2.34/META.yml')
                yml_data = yml_content.encode('utf-8')
                yml_info.size = len(yml_data)
                tar.addfile(yml_info, fileobj=tempfile.SpooledTemporaryFile(max_size=len(yml_data)))
                tar.fileobj.write(yml_data)
        
        try:
            # Extract metadata
            metadata = self.extractor.extract(tmp_path)
            
            # Verify extraction (basic parsing without PyYAML)
            assert metadata.package_type == PackageType.PERL
            # Basic parsing will extract limited fields
            
        finally:
            os.unlink(tmp_path)
    
    def test_parse_author(self):
        """Test author string parsing."""
        # Test various author formats
        assert self.extractor._parse_author("John Doe <john@example.com>") == {
            'name': 'John Doe',
            'email': 'john@example.com'
        }
        
        assert self.extractor._parse_author("Jane Smith") == {
            'name': 'Jane Smith'
        }
        
        assert self.extractor._parse_author("") is None
    
    def test_map_perl_license(self):
        """Test Perl license mapping to SPDX."""
        assert self.extractor._map_perl_license("perl_5") == "Artistic-1.0 OR GPL-1.0-or-later"
        assert self.extractor._map_perl_license("perl") == "Artistic-1.0 OR GPL-1.0-or-later"
        assert self.extractor._map_perl_license("mit") == "MIT"
        assert self.extractor._map_perl_license("apache_2_0") == "Apache-2.0"
        assert self.extractor._map_perl_license("gpl_3") == "GPL-3.0"
        assert self.extractor._map_perl_license("bsd") == "BSD-3-Clause"
        assert self.extractor._map_perl_license("unknown") is None
    
    def test_extract_dependencies(self):
        """Test dependency extraction from prereqs."""
        prereqs = {
            "runtime": {
                "requires": {
                    "Module::One": "1.0",
                    "Module::Two": "2.3"
                },
                "recommends": {
                    "Optional::Module": "0"
                }
            },
            "test": {
                "requires": {
                    "Test::Module": "0.98"
                }
            },
            "configure": {
                "requires": {
                    "ExtUtils::MakeMaker": "6.64"
                }
            }
        }
        
        deps = self.extractor._extract_dependencies(prereqs)
        dep_dict = {d['name']: d for d in deps}
        
        # Check runtime requires
        assert 'Module::One' in dep_dict
        assert dep_dict['Module::One']['version'] == '1.0'
        
        # Check test requires
        assert 'Test::Module' in dep_dict
        assert dep_dict['Test::Module']['phase'] == 'test'
        
        # Check recommends
        assert 'Optional::Module' in dep_dict
        assert dep_dict['Optional::Module']['relationship'] == 'recommends'
        
        # Check configure requires
        assert 'ExtUtils::MakeMaker' in dep_dict
        assert dep_dict['ExtUtils::MakeMaker']['phase'] == 'configure'
    
    def test_find_license_files(self):
        """Test finding license files in package directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create various license files
            license_files = ['LICENSE', 'COPYING', 'COPYRIGHT', 'ARTISTIC', 'GPL']
            for filename in license_files:
                with open(os.path.join(temp_dir, filename), 'w') as f:
                    f.write("License content")
            
            # Find license files
            found = self.extractor._find_license_files(temp_dir)
            found_names = [os.path.basename(f) for f in found]
            
            # Verify all license files were found
            for filename in license_files:
                assert filename in found_names