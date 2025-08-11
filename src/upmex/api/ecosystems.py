"""Ecosyste.ms API integration for package metadata enrichment."""

import requests
from typing import Optional, Dict, Any
from ..core.models import PackageType, NO_ASSERTION


class EcosystemsAPI:
    """Client for Ecosyste.ms API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Ecosyste.ms API client.
        
        Args:
            api_key: Optional API key for authenticated requests
        """
        self.base_url = "https://packages.ecosyste.ms/api/v1"
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'
    
    def get_package_info(self, package_type: PackageType, name: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get package information from Ecosyste.ms.
        
        Args:
            package_type: Type of package
            name: Package name (can include namespace)
            version: Optional package version
            
        Returns:
            Package information or None
        """
        try:
            # Map package type to Ecosyste.ms registry
            registry = self._map_package_type(package_type)
            if not registry:
                return None
            
            # Get package-level info first for maintainers
            package_url = f"{self.base_url}/registries/{registry}/packages/{name}"
            package_response = requests.get(package_url, headers=self.headers, timeout=10)
            
            if package_response.status_code == 200:
                package_data = package_response.json()
                
                # If version requested, get version-specific data and merge
                if version:
                    version_url = f"{package_url}/versions/{version}"
                    version_response = requests.get(version_url, headers=self.headers, timeout=10)
                    if version_response.status_code == 200:
                        version_data = version_response.json()
                        # Merge version data into package data, keeping maintainers from package level
                        version_data['maintainers'] = package_data.get('maintainers', [])
                        return version_data
                
                return package_data
            
        except Exception as e:
            print(f"Error fetching from Ecosyste.ms: {e}")
        
        return None
    
    def _map_package_type(self, package_type: PackageType) -> Optional[str]:
        """Map PackageType to Ecosyste.ms registry string.
        
        Args:
            package_type: Package type enum
            
        Returns:
            Ecosyste.ms registry string or None
        """
        mapping = {
            PackageType.PYTHON_WHEEL: "pypi.org",
            PackageType.PYTHON_SDIST: "pypi.org",
            PackageType.NPM: "npmjs.org",
            PackageType.MAVEN: "repo.maven.apache.org",
            PackageType.JAR: "repo.maven.apache.org",
            PackageType.GRADLE: "repo.maven.apache.org",  # Gradle projects resolve from Maven repos
            PackageType.COCOAPODS: "trunk.cocoapods.org",
            PackageType.CONDA: "anaconda.org",
            PackageType.RUBY_GEM: "rubygems.org",
            PackageType.RUST_CRATE: "crates.io",
            PackageType.GO_MODULE: "proxy.golang.org",
            PackageType.NUGET: "nuget.org"
        }
        return mapping.get(package_type)
    
    def extract_metadata(self, package_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from Ecosyste.ms package info.
        
        Args:
            package_info: Ecosyste.ms package information
            
        Returns:
            Extracted metadata
        """
        metadata = {}
        
        try:
            # Extract basic info
            if 'description' in package_info:
                metadata['description'] = package_info['description']
            
            if 'homepage' in package_info:
                metadata['homepage'] = package_info['homepage']
            
            if 'repository_url' in package_info:
                metadata['repository'] = package_info['repository_url']
            
            # Extract license
            if 'licenses' in package_info:
                metadata['licenses'] = package_info['licenses']
            elif 'license' in package_info:
                metadata['licenses'] = [package_info['license']]
            
            # Extract keywords
            if 'keywords' in package_info:
                metadata['keywords'] = package_info['keywords']
            
            # Extract maintainers
            if 'maintainers' in package_info:
                metadata['maintainers'] = package_info['maintainers']
            
        except Exception as e:
            print(f"Error extracting metadata from Ecosyste.ms: {e}")
        
        return metadata