"""Tests for CocoaPods extractor."""

import json
import tempfile
import os
from pathlib import Path
from datetime import datetime

import pytest
from src.upmex.extractors.cocoapods_extractor import CocoaPodsExtractor
from src.upmex.core.models import PackageType, NO_ASSERTION


class TestCocoaPodsExtractor:
    """Test CocoaPods package extraction."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = CocoaPodsExtractor()
    
    def test_extract_json_podspec_metadata(self):
        """Test extracting metadata from .podspec.json file."""
        podspec_json = {
            "name": "Alamofire",
            "version": "5.6.4",
            "summary": "Elegant HTTP Networking in Swift",
            "description": "Alamofire is an HTTP networking library written in Swift.",
            "homepage": "https://github.com/Alamofire/Alamofire",
            "license": {
                "type": "MIT",
                "file": "LICENSE"
            },
            "authors": {
                "Alamofire Software Foundation": "info@alamofire.org"
            },
            "source": {
                "git": "https://github.com/Alamofire/Alamofire.git",
                "tag": "5.6.4"
            },
            "platforms": {
                "ios": "10.0",
                "osx": "10.12",
                "tvos": "10.0",
                "watchos": "3.0"
            },
            "dependencies": {
                "runtime": [
                    "SwiftyJSON ~> 5.0"
                ]
            },
            "frameworks": ["Foundation", "CFNetwork"]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.podspec.json', delete=False) as f:
            json.dump(podspec_json, f)
            temp_path = f.name
        
        try:
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "Alamofire"
            assert metadata.version == "5.6.4"
            assert metadata.package_type == PackageType.COCOAPODS
            assert metadata.description == "Alamofire is an HTTP networking library written in Swift."
            assert metadata.homepage == "https://github.com/Alamofire/Alamofire"
            assert metadata.repository == "https://github.com/Alamofire/Alamofire.git"
            
            # Check authors
            assert len(metadata.authors) == 1
            assert metadata.authors[0]['name'] == "Alamofire Software Foundation"
            assert metadata.authors[0]['email'] == "info@alamofire.org"
            
            # Check dependencies
            assert "runtime" in metadata.dependencies
            assert "SwiftyJSON ~> 5.0" in metadata.dependencies["runtime"]
            
            # Check keywords (from platforms and frameworks)
            assert "ios" in metadata.keywords
            assert "Foundation" in metadata.keywords
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_ruby_podspec_metadata(self):
        """Test extracting metadata from .podspec Ruby DSL file."""
        podspec_content = '''
Pod::Spec.new do |s|
  s.name         = "AFNetworking"
  s.version      = "4.0.1"
  s.summary      = "A delightful iOS and OS X networking framework"
  s.description  = <<-DESC
                   AFNetworking is a delightful iOS and OS X networking framework for networking.
                   It's built on top of the Foundation URL Loading System.
                   DESC
  s.homepage     = "https://github.com/AFNetworking/AFNetworking"
  s.license      = { :type => "MIT", :file => "LICENSE" }
  s.authors      = { "Matt Thompson" => "m@mattt.org", "Alamofire Software Foundation" => "info@alamofire.org" }
  
  s.ios.deployment_target = "9.0"
  s.osx.deployment_target = "10.10"
  
  s.source       = { :git => "https://github.com/AFNetworking/AFNetworking.git", :tag => "#{s.version}" }
  
  s.dependency "Reachability", "~> 3.2"
  s.dependency "Security"
  
  s.frameworks = ["Foundation", "CoreGraphics", "UIKit"]
  s.libraries = ["xml2"]
end
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.podspec', delete=False) as f:
            f.write(podspec_content)
            temp_path = f.name
        
        try:
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "AFNetworking"
            assert metadata.version == "4.0.1"
            assert metadata.package_type == PackageType.COCOAPODS
            assert "AFNetworking is a delightful iOS and OS X networking framework" in metadata.description
            assert metadata.homepage == "https://github.com/AFNetworking/AFNetworking"
            assert metadata.repository == "https://github.com/AFNetworking/AFNetworking.git"
            
            # Check authors
            assert len(metadata.authors) == 2
            author_names = [author['name'] for author in metadata.authors]
            assert "Matt Thompson" in author_names
            assert "Alamofire Software Foundation" in author_names
            
            # Check dependencies
            assert "runtime" in metadata.dependencies
            deps = metadata.dependencies["runtime"]
            assert any("Reachability" in dep for dep in deps)
            assert any("Security" in dep for dep in deps)
            
            # Check keywords from frameworks
            assert "Foundation" in metadata.keywords
            assert "UIKit" in metadata.keywords
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_minimal_podspec(self):
        """Test extracting metadata from minimal .podspec file."""
        podspec_content = '''
Pod::Spec.new do |s|
  s.name         = "SimpleLib"
  s.version      = "1.0.0"
  s.summary      = "A simple library"
  s.homepage     = "https://example.com"
  s.license      = "MIT"
  s.author       = "Developer"
  s.source       = { :git => "https://example.com/SimpleLib.git", :tag => "v1.0.0" }
end
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.podspec', delete=False) as f:
            f.write(podspec_content)
            temp_path = f.name
        
        try:
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "SimpleLib"
            assert metadata.version == "1.0.0"
            assert metadata.package_type == PackageType.COCOAPODS
            assert metadata.description == "A simple library"
            assert metadata.homepage == "https://example.com"
            assert metadata.repository == "https://example.com/SimpleLib.git"
            
            # Check single author (string format)
            assert len(metadata.authors) == 1
            assert metadata.authors[0]['name'] == "Developer"
            assert metadata.authors[0]['email'] == NO_ASSERTION
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_with_string_license(self):
        """Test extracting metadata with string license format."""
        podspec_json = {
            "name": "TestPod",
            "version": "2.0.0",
            "summary": "Test pod",
            "license": "Apache-2.0",
            "authors": ["Dev One", "Dev Two"],
            "source": {
                "git": "https://github.com/test/TestPod.git"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.podspec.json', delete=False) as f:
            json.dump(podspec_json, f)
            temp_path = f.name
        
        try:
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "TestPod"
            assert metadata.version == "2.0.0"
            
            # Check license detection
            assert len(metadata.licenses) > 0
            # Should detect Apache-2.0
            license_ids = [license.spdx_id for license in metadata.licenses]
            assert "Apache-2.0" in license_ids
            
            # Check authors array format
            assert len(metadata.authors) == 2
            author_names = [author['name'] for author in metadata.authors]
            assert "Dev One" in author_names
            assert "Dev Two" in author_names
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_with_http_source(self):
        """Test extracting metadata with HTTP source."""
        podspec_content = '''
Pod::Spec.new do |s|
  s.name = "HttpPod"
  s.version = "1.5.0"
  s.summary = "Pod from HTTP source"
  s.source = { :http => "https://example.com/download/HttpPod-1.5.0.tar.gz" }
end
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.podspec', delete=False) as f:
            f.write(podspec_content)
            temp_path = f.name
        
        try:
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "HttpPod"
            assert metadata.version == "1.5.0"
            assert metadata.repository == "https://example.com/download/HttpPod-1.5.0.tar.gz"
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_with_platform_requirements(self):
        """Test extracting metadata with platform requirements."""
        podspec_content = '''
Pod::Spec.new do |s|
  s.name = "PlatformPod"
  s.version = "3.0.0"
  s.summary = "Multi-platform pod"
  
  s.ios.deployment_target = "12.0"
  s.osx.deployment_target = "10.14"
  s.tvos.deployment_target = "12.0"
  s.watchos.deployment_target = "5.0"
end
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.podspec', delete=False) as f:
            f.write(podspec_content)
            temp_path = f.name
        
        try:
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "PlatformPod"
            assert metadata.version == "3.0.0"
            
            # Check that platform names are in keywords
            assert "ios" in metadata.keywords
            assert "osx" in metadata.keywords
            assert "tvos" in metadata.keywords
            assert "watchos" in metadata.keywords
            
            # Check raw metadata contains platform info
            assert "platforms" in metadata.raw_metadata
            platforms = metadata.raw_metadata["platforms"]
            assert platforms["ios"] == "12.0"
            assert platforms["osx"] == "10.14"
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_invalid_json(self):
        """Test handling of invalid JSON podspec."""
        invalid_json = '{"name": "Invalid", "version": "1.0.0"'  # Missing closing brace
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.podspec.json', delete=False) as f:
            f.write(invalid_json)
            temp_path = f.name
        
        try:
            metadata = self.extractor.extract(temp_path)
            
            # Should create minimal metadata with error
            # The name should be derived from the temp filename, not the invalid JSON
            assert metadata.version == NO_ASSERTION
            assert metadata.package_type == PackageType.COCOAPODS
            assert "extraction_error" in metadata.raw_metadata
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_nonexistent_file(self):
        """Test handling of nonexistent file."""
        metadata = self.extractor.extract("/nonexistent/file.podspec")
        
        assert metadata.name == "file"
        assert metadata.version == NO_ASSERTION
        assert metadata.package_type == PackageType.COCOAPODS
    
    def test_package_detection(self):
        """Test that package detection works correctly."""
        from src.upmex.utils.package_detector import detect_package_type
        
        # Test .podspec file
        with tempfile.NamedTemporaryFile(suffix='.podspec', delete=False) as f:
            temp_path = f.name
        
        try:
            assert detect_package_type(temp_path) == PackageType.COCOAPODS
        finally:
            os.unlink(temp_path)
        
        # Test .podspec.json file
        with tempfile.NamedTemporaryFile(suffix='.podspec.json', delete=False) as f:
            temp_path = f.name
        
        try:
            assert detect_package_type(temp_path) == PackageType.COCOAPODS
        finally:
            os.unlink(temp_path)