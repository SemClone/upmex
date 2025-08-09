"""Integration tests for API clients."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from upmex.api.clearlydefined import ClearlyDefinedAPI
from upmex.api.ecosystems import EcosystemsAPI
from upmex.core.models import PackageType


class TestClearlyDefinedAPI:
    """Test ClearlyDefined API integration."""
    
    def test_init_with_api_key(self):
        """Test initialization with API key."""
        api = ClearlyDefinedAPI(api_key="test-key")
        assert api.api_key == "test-key"
        assert api.headers["Authorization"] == "Bearer test-key"
    
    def test_init_without_api_key(self):
        """Test initialization without API key."""
        api = ClearlyDefinedAPI()
        assert api.api_key is None
        assert "Authorization" not in api.headers
    
    @patch('requests.get')
    def test_get_definition_success(self, mock_get):
        """Test successful package definition retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "coordinates": {
                "type": "pypi",
                "provider": "pypi",
                "name": "requests",
                "revision": "2.28.0"
            },
            "licensed": {
                "declared": "Apache-2.0"
            }
        }
        mock_get.return_value = mock_response
        
        api = ClearlyDefinedAPI()
        result = api.get_definition(
            PackageType.PYTHON_WHEEL,
            None,
            "requests",
            "2.28.0"
        )
        
        assert result is not None
        assert result["licensed"]["declared"] == "Apache-2.0"
        mock_get.assert_called_once()
        assert "pypi/-/requests/2.28.0" in mock_get.call_args[0][0]
    
    @patch('requests.get')
    def test_get_definition_with_namespace(self, mock_get):
        """Test package definition with namespace."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"licensed": {"declared": "MIT"}}
        mock_get.return_value = mock_response
        
        api = ClearlyDefinedAPI()
        result = api.get_definition(
            PackageType.NPM,
            "@angular",
            "core",
            "12.0.0"
        )
        
        assert result is not None
        assert "npm/@angular/core/12.0.0" in mock_get.call_args[0][0]
    
    @patch('requests.get')
    def test_get_definition_not_found(self, mock_get):
        """Test handling of 404 response."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        api = ClearlyDefinedAPI()
        result = api.get_definition(
            PackageType.PYTHON_WHEEL,
            None,
            "nonexistent",
            "1.0.0"
        )
        
        assert result is None
    
    @patch('requests.get')
    def test_get_definition_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = requests.RequestException("Network error")
        
        api = ClearlyDefinedAPI()
        result = api.get_definition(
            PackageType.PYTHON_WHEEL,
            None,
            "requests",
            "2.28.0"
        )
        
        assert result is None
    
    def test_map_package_type(self):
        """Test package type mapping."""
        api = ClearlyDefinedAPI()
        
        assert api._map_package_type(PackageType.PYTHON_WHEEL) == "pypi"
        assert api._map_package_type(PackageType.PYTHON_SDIST) == "pypi"
        assert api._map_package_type(PackageType.NPM) == "npm"
        assert api._map_package_type(PackageType.MAVEN) == "maven"
        assert api._map_package_type(PackageType.JAR) == "maven"
        assert api._map_package_type(PackageType.UNKNOWN) is None
    
    def test_extract_license_info_declared(self):
        """Test extracting declared license."""
        api = ClearlyDefinedAPI()
        definition = {
            "licensed": {
                "declared": "MIT"
            }
        }
        
        result = api.extract_license_info(definition)
        assert result is not None
        assert result["spdx_id"] == "MIT"
        assert result["source"] == "ClearlyDefined"
        assert result["confidence"] == 1.0
    
    def test_extract_license_info_discovered(self):
        """Test extracting discovered license."""
        api = ClearlyDefinedAPI()
        definition = {
            "licensed": {
                "discovered": {
                    "expressions": ["Apache-2.0", "MIT"]
                }
            }
        }
        
        result = api.extract_license_info(definition)
        assert result is not None
        assert result["spdx_id"] == "Apache-2.0"
        assert result["confidence"] == 0.8
    
    def test_extract_license_info_none(self):
        """Test when no license info available."""
        api = ClearlyDefinedAPI()
        
        result = api.extract_license_info({})
        assert result is None
        
        result = api.extract_license_info({"licensed": {}})
        assert result is None


class TestEcosystemsAPI:
    """Test Ecosyste.ms API integration."""
    
    def test_init_with_api_key(self):
        """Test initialization with API key."""
        api = EcosystemsAPI(api_key="test-key")
        assert api.api_key == "test-key"
        assert api.headers["Authorization"] == "Bearer test-key"
    
    def test_init_without_api_key(self):
        """Test initialization without API key."""
        api = EcosystemsAPI()
        assert api.api_key is None
        assert "Authorization" not in api.headers
    
    @patch('requests.get')
    def test_get_package_info_success(self, mock_get):
        """Test successful package info retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "requests",
            "description": "Python HTTP library",
            "homepage": "https://requests.readthedocs.io",
            "repository_url": "https://github.com/psf/requests",
            "licenses": ["Apache-2.0"],
            "keywords": ["http", "requests"]
        }
        mock_get.return_value = mock_response
        
        api = EcosystemsAPI()
        result = api.get_package_info(
            PackageType.PYTHON_WHEEL,
            "requests",
            "2.28.0"
        )
        
        assert result is not None
        assert result["name"] == "requests"
        assert result["repository_url"] == "https://github.com/psf/requests"
        mock_get.assert_called_once()
        assert "pypi.org/packages/requests/versions/2.28.0" in mock_get.call_args[0][0]
    
    @patch('requests.get')
    def test_get_package_info_without_version(self, mock_get):
        """Test package info retrieval without version."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "express"}
        mock_get.return_value = mock_response
        
        api = EcosystemsAPI()
        result = api.get_package_info(
            PackageType.NPM,
            "express"
        )
        
        assert result is not None
        assert "npmjs.org/packages/express" in mock_get.call_args[0][0]
        assert "/versions/" not in mock_get.call_args[0][0]
    
    @patch('requests.get')
    def test_get_package_info_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = requests.RequestException("Network error")
        
        api = EcosystemsAPI()
        result = api.get_package_info(
            PackageType.NPM,
            "express",
            "5.0.0"
        )
        
        assert result is None
    
    def test_map_package_type(self):
        """Test package type mapping to registry."""
        api = EcosystemsAPI()
        
        assert api._map_package_type(PackageType.PYTHON_WHEEL) == "pypi.org"
        assert api._map_package_type(PackageType.PYTHON_SDIST) == "pypi.org"
        assert api._map_package_type(PackageType.NPM) == "npmjs.org"
        assert api._map_package_type(PackageType.MAVEN) == "repo.maven.apache.org"
        assert api._map_package_type(PackageType.JAR) == "repo.maven.apache.org"
        assert api._map_package_type(PackageType.UNKNOWN) is None
    
    def test_extract_metadata_full(self):
        """Test metadata extraction with all fields."""
        api = EcosystemsAPI()
        package_info = {
            "description": "Test package",
            "homepage": "https://example.com",
            "repository_url": "https://github.com/test/repo",
            "licenses": ["MIT", "Apache-2.0"],
            "keywords": ["test", "example"],
            "maintainers": [
                {"name": "John Doe", "email": "john@example.com"}
            ]
        }
        
        metadata = api.extract_metadata(package_info)
        
        assert metadata["description"] == "Test package"
        assert metadata["homepage"] == "https://example.com"
        assert metadata["repository"] == "https://github.com/test/repo"
        assert metadata["licenses"] == ["MIT", "Apache-2.0"]
        assert metadata["keywords"] == ["test", "example"]
        assert metadata["maintainers"] == [{"name": "John Doe", "email": "john@example.com"}]
    
    def test_extract_metadata_single_license(self):
        """Test metadata extraction with single license field."""
        api = EcosystemsAPI()
        package_info = {
            "license": "MIT"
        }
        
        metadata = api.extract_metadata(package_info)
        assert metadata["licenses"] == ["MIT"]
    
    def test_extract_metadata_empty(self):
        """Test metadata extraction with empty input."""
        api = EcosystemsAPI()
        metadata = api.extract_metadata({})
        assert metadata == {}
    
    def test_extract_metadata_error_handling(self):
        """Test error handling in metadata extraction."""
        api = EcosystemsAPI()
        # Pass invalid data that would cause an exception
        metadata = api.extract_metadata(None)
        assert metadata == {}


class TestAPIIntegration:
    """Test integration between APIs and extractors."""
    
    @patch('requests.get')
    def test_clearlydefined_enrichment(self, mock_get):
        """Test enriching metadata with ClearlyDefined."""
        # Mock ClearlyDefined response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "licensed": {
                "declared": "Apache-2.0",
                "facets": {
                    "core": {
                        "discovered": {
                            "expressions": ["Apache-2.0"]
                        }
                    }
                }
            }
        }
        
        api = ClearlyDefinedAPI()
        definition = api.get_definition(
            PackageType.PYTHON_WHEEL,
            None,
            "requests",
            "2.28.0"
        )
        
        license_info = api.extract_license_info(definition)
        
        assert license_info is not None
        assert license_info["spdx_id"] == "Apache-2.0"
        assert license_info["source"] == "ClearlyDefined"
    
    @patch('requests.get')
    def test_ecosystems_enrichment(self, mock_get):
        """Test enriching metadata with Ecosyste.ms."""
        # Mock Ecosyste.ms response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "name": "express",
            "description": "Fast, unopinionated web framework",
            "repository_url": "https://github.com/expressjs/express",
            "licenses": ["MIT"],
            "keywords": ["express", "framework", "web"],
            "maintainers": [
                {"name": "Express Team"}
            ]
        }
        
        api = EcosystemsAPI()
        package_info = api.get_package_info(
            PackageType.NPM,
            "express",
            "4.18.0"
        )
        
        metadata = api.extract_metadata(package_info)
        
        assert metadata["description"] == "Fast, unopinionated web framework"
        assert metadata["repository"] == "https://github.com/expressjs/express"
        assert "express" in metadata["keywords"]
        assert len(metadata["maintainers"]) > 0