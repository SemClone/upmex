"""ClearlyDefined API integration for license and metadata enrichment."""

import requests
from typing import Optional, Dict, Any
from ..core.models import PackageType, NO_ASSERTION


class ClearlyDefinedAPI:
    """Client for ClearlyDefined API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize ClearlyDefined API client.
        
        Args:
            api_key: Optional API key for authenticated requests
        """
        self.base_url = "https://api.clearlydefined.io/v1"
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'
    
    def get_definition(self, package_type: PackageType, namespace: Optional[str], name: str, version: str) -> Optional[Dict[str, Any]]:
        """Get package definition from ClearlyDefined.
        
        Args:
            package_type: Type of package
            namespace: Package namespace (e.g., npm scope, Maven groupId)
            name: Package name
            version: Package version
            
        Returns:
            Package definition or None
        """
        try:
            # Map package type to ClearlyDefined type
            cd_type = self._map_package_type(package_type)
            if not cd_type:
                return None
            
            # Construct coordinates
            if namespace:
                coordinates = f"{cd_type}/{namespace}/{name}/{version}"
            else:
                coordinates = f"{cd_type}/-/{name}/{version}"
            
            # Make API request
            url = f"{self.base_url}/definitions/{coordinates}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            
        except Exception as e:
            print(f"Error fetching from ClearlyDefined: {e}")
        
        return None
    
    def _map_package_type(self, package_type: PackageType) -> Optional[str]:
        """Map PackageType to ClearlyDefined type string.
        
        Args:
            package_type: Package type enum
            
        Returns:
            ClearlyDefined type string or None
        """
        mapping = {
            PackageType.PYTHON_WHEEL: "pypi",
            PackageType.PYTHON_SDIST: "pypi",
            PackageType.NPM: "npm",
            PackageType.MAVEN: "maven",
            PackageType.JAR: "maven",
            PackageType.GRADLE: "maven",  # Gradle projects often resolve from Maven repos
            PackageType.COCOAPODS: "pod",
            PackageType.CONDA: "conda",
            PackageType.RUBY_GEM: "gem",
            PackageType.RUST_CRATE: "crate",
            PackageType.GO_MODULE: "go",
            PackageType.NUGET: "nuget"
        }
        return mapping.get(package_type)
    
    def extract_license_info(self, definition: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract license information from ClearlyDefined definition.
        
        Args:
            definition: ClearlyDefined definition object
            
        Returns:
            License information or None
        """
        try:
            licensed = definition.get('licensed')
            if licensed:
                declared = licensed.get('declared')
                if declared:
                    return {
                        'spdx_id': declared,
                        'source': 'ClearlyDefined',
                        'confidence': 1.0
                    }
                
                # Check discovered licenses
                discovered = licensed.get('discovered')
                if discovered and discovered.get('expressions'):
                    return {
                        'spdx_id': discovered['expressions'][0],
                        'source': 'ClearlyDefined',
                        'confidence': 0.8
                    }
        except Exception as e:
            print(f"Error extracting license from ClearlyDefined: {e}")
        
        return None