"""Unit tests for Ruby gem package extractor."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tarfile
import gzip
import yaml
import io
from pathlib import Path

from upmex.extractors.ruby_extractor import RubyExtractor


class TestRubyExtractor(unittest.TestCase):
    """Test Ruby gem metadata extraction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = RubyExtractor()
    
    def test_detect_ruby_gem_by_extension(self):
        """Test detection of Ruby gem by .gem extension."""
        package_path = Path("test-package.gem")
        result = self.extractor.detect_package_type(package_path)
        self.assertEqual(result, "ruby_gem")
    
    def test_detect_ruby_gem_in_tar(self):
        """Test detection of Ruby gem in tar archive."""
        # Mock tarfile to simulate gem structure
        with patch('tarfile.open') as mock_open:
            mock_tar = MagicMock()
            mock_member1 = MagicMock()
            mock_member1.name = 'metadata.gz'
            mock_member2 = MagicMock()
            mock_member2.name = 'data.tar.gz'
            mock_member3 = MagicMock()
            mock_member3.name = 'checksums.yaml.gz'
            mock_tar.getnames.return_value = ['metadata.gz', 'data.tar.gz', 'checksums.yaml.gz']
            mock_open.return_value.__enter__.return_value = mock_tar
            
            package_path = Path("test-package.tar")
            result = self.extractor.detect_package_type(package_path)
            self.assertEqual(result, "ruby_gem")
    
    @patch('tarfile.open')
    def test_extract_from_gemspec(self, mock_tarfile):
        """Test extracting metadata from gemspec."""
        # Create mock gemspec data
        gemspec_data = {
            'name': 'test-gem',
            'version': {'version': '1.2.3'},
            'summary': 'A test Ruby gem',
            'homepage': 'https://github.com/user/test-gem',
            'authors': ['John Doe', 'Jane Smith'],
            'email': ['john@example.com', 'jane@example.com'],
            'licenses': ['MIT'],
            'dependencies': [],
            'platform': 'ruby',
            'required_ruby_version': '>= 2.5.0'
        }
        
        # Create compressed YAML
        yaml_bytes = yaml.dump(gemspec_data).encode('utf-8')
        compressed_yaml = gzip.compress(yaml_bytes)
        
        # Mock tar file structure
        mock_tar = MagicMock()
        mock_metadata_member = MagicMock()
        mock_metadata_member.name = 'metadata.gz'
        
        mock_tar.getmembers.return_value = [mock_metadata_member]
        mock_tar.extractfile.return_value = io.BytesIO(compressed_yaml)
        
        mock_tarfile.return_value.__enter__.return_value = mock_tar
        
        # Extract metadata
        metadata = self.extractor.extract("test.gem")
        
        # Verify extracted data
        self.assertEqual(metadata.name, 'test-gem')
        self.assertEqual(metadata.version, '1.2.3')
        self.assertEqual(metadata.description, 'A test Ruby gem')
        self.assertEqual(metadata.homepage, 'https://github.com/user/test-gem')
        self.assertEqual(metadata.repository, 'https://github.com/user/test-gem')
        self.assertEqual(len(metadata.authors), 2)
        self.assertEqual(metadata.authors[0]['name'], 'John Doe')
        self.assertEqual(metadata.authors[0]['email'], 'john@example.com')
        self.assertIsNotNone(metadata.licenses)
        self.assertEqual(metadata.licenses[0].spdx_id, 'MIT')
    
    @patch('tarfile.open')
    def test_extract_with_gem_dependency(self, mock_tarfile):
        """Test extracting dependencies from gemspec."""
        # Create mock gemspec with dependencies
        # Create mock dependency objects
        rails_dep = Mock()
        rails_dep.name = 'rails'
        rails_dep.requirement = '>= 6.0'
        rails_dep.type = ':runtime'
        
        rspec_dep = Mock()
        rspec_dep.name = 'rspec'
        rspec_dep.requirement = '~> 3.0'
        rspec_dep.type = ':development'
        
        gemspec_data = {
            'name': 'test-gem',
            'version': '1.0.0',
            'dependencies': [rails_dep, rspec_dep]
        }
        
        # Prepare mock YAML
        yaml_bytes = yaml.dump(gemspec_data).encode('utf-8')
        compressed_yaml = gzip.compress(yaml_bytes)
        
        # Mock tar structure
        mock_tar = MagicMock()
        mock_metadata = MagicMock()
        mock_metadata.name = 'metadata.gz'
        mock_tar.getmembers.return_value = [mock_metadata]
        mock_tar.extractfile.return_value = io.BytesIO(compressed_yaml)
        
        mock_tarfile.return_value.__enter__.return_value = mock_tar
        
        # Extract and verify
        metadata = self.extractor.extract(Path("test.gem"))
        
        self.assertEqual(len(metadata.dependencies.get('runtime', [])) + len(metadata.dependencies.get('development', [])), 2)
        # Dependencies are now stored as strings in format 'name version'
        self.assertIn('rails >= 6.0', metadata.dependencies.get('runtime', []))
        self.assertIn('rspec ~> 3.0', metadata.dependencies.get('development', []))
    
    @patch('tarfile.open')
    def test_extract_license_from_data_tar(self, mock_tarfile):
        """Test extracting license from LICENSE file in data.tar.gz."""
        # Create gemspec without license
        gemspec_data = {
            'name': 'test-gem',
            'version': '1.0.0'
        }
        
        yaml_bytes = yaml.dump(gemspec_data).encode('utf-8')
        compressed_yaml = gzip.compress(yaml_bytes)
        
        # Create mock LICENSE file content
        license_content = b"MIT License\n\nCopyright (c) 2024"
        
        # Mock the nested tar structure
        mock_main_tar = MagicMock()
        mock_metadata = MagicMock()
        mock_metadata.name = 'metadata.gz'
        mock_data = MagicMock()
        mock_data.name = 'data.tar.gz'
        
        mock_main_tar.getmembers.return_value = [mock_metadata, mock_data]
        
        # Mock metadata.gz extraction
        def extract_file_side_effect(member):
            if member.name == 'metadata.gz':
                return io.BytesIO(compressed_yaml)
            elif member.name == 'data.tar.gz':
                # Create a mock data.tar.gz
                data_tar_bytes = io.BytesIO()
                with tarfile.open(fileobj=data_tar_bytes, mode='w:gz') as data_tar:
                    license_info = tarfile.TarInfo(name='LICENSE')
                    license_info.size = len(license_content)
                    data_tar.addfile(license_info, io.BytesIO(license_content))
                data_tar_bytes.seek(0)
                return data_tar_bytes
            return None
        
        mock_main_tar.extractfile.side_effect = extract_file_side_effect
        
        mock_tarfile.return_value.__enter__.return_value = mock_main_tar
        
        # Extract and verify
        metadata = self.extractor.extract(Path("test.gem"))
        
        self.assertIsNotNone(metadata.licenses)
        self.assertEqual(metadata.licenses[0].spdx_id, 'MIT')
        self.assertEqual(metadata.licenses[0].file_path, 'LICENSE')
    
    @patch('tarfile.open')
    def test_extract_with_metadata_uri(self, mock_tarfile):
        """Test extracting repository from metadata URIs."""
        gemspec_data = {
            'name': 'test-gem',
            'version': '1.0.0',
            'metadata': {
                'source_code_uri': 'https://github.com/user/test-gem',
                'documentation_uri': 'https://docs.example.com/test-gem'
            }
        }
        
        yaml_bytes = yaml.dump(gemspec_data).encode('utf-8')
        compressed_yaml = gzip.compress(yaml_bytes)
        
        mock_tar = MagicMock()
        mock_metadata = MagicMock()
        mock_metadata.name = 'metadata.gz'
        mock_tar.getmembers.return_value = [mock_metadata]
        mock_tar.extractfile.return_value = io.BytesIO(compressed_yaml)
        
        mock_tarfile.return_value.__enter__.return_value = mock_tar
        
        metadata = self.extractor.extract(Path("test.gem"))
        
        self.assertEqual(metadata.repository, 'https://github.com/user/test-gem')
        # documentation_url is not stored in PackageMetadata, it's part of raw_metadata


if __name__ == '__main__':
    unittest.main()