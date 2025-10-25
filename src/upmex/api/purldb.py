"""PurlDB API integration for package metadata enrichment."""

import requests
from typing import Optional, Dict, Any, List
from ..core.models import PackageType, NO_ASSERTION


class PurlDBAPI:
    """Client for PurlDB API."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://public.purldb.io"):
        """Initialize PurlDB API client.

        Args:
            api_key: Optional API key for authenticated requests
            base_url: Base URL for PurlDB instance
        """
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {'Content-Type': 'application/json'}
        if api_key:
            self.headers['Authorization'] = f'Token {api_key}'

    def get_package_by_purl(self, purl: str) -> Optional[Dict[str, Any]]:
        """Get package information by PURL.

        Args:
            purl: Package URL (PURL) string

        Returns:
            Package information or None
        """
        try:
            # Use the packages endpoint with PURL query
            url = f"{self.base_url}/api/packages/"
            params = {'purl': purl}

            response = requests.get(url, params=params, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # Return first result if any packages found
                if data.get('results') and len(data['results']) > 0:
                    return data['results'][0]

        except Exception as e:
            print(f"Error fetching from PurlDB: {e}")

        return None

    def get_package_info(self, package_type: PackageType, name: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get package information by type, name, and version.

        Args:
            package_type: Type of package
            name: Package name (can include namespace)
            version: Optional package version

        Returns:
            Package information or None
        """
        try:
            # Map package type to PURL type
            purl_type = self._map_package_type(package_type)
            if not purl_type:
                return None

            # Parse namespace from name for certain package types
            namespace = None
            package_name = name

            if package_type == PackageType.MAVEN and ':' in name:
                # Maven format: groupId:artifactId
                parts = name.split(':')
                if len(parts) >= 2:
                    namespace = parts[0]
                    package_name = parts[1]
            elif package_type == PackageType.NPM and name.startswith('@'):
                # NPM scoped packages: @scope/name
                parts = name[1:].split('/', 1)
                if len(parts) == 2:
                    namespace = parts[0]
                    package_name = parts[1]

            # Query packages endpoint with filters
            url = f"{self.base_url}/api/packages/"
            params = {
                'type': purl_type,
                'name': package_name
            }

            if namespace:
                params['namespace'] = namespace
            if version:
                params['version'] = version

            response = requests.get(url, params=params, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # Return first result if any packages found
                if data.get('results') and len(data['results']) > 0:
                    return data['results'][0]

        except Exception as e:
            print(f"Error fetching from PurlDB: {e}")

        return None

    def _map_package_type(self, package_type: PackageType) -> Optional[str]:
        """Map PackageType to PurlDB package type string.

        Args:
            package_type: Package type enum

        Returns:
            PurlDB package type string or None
        """
        mapping = {
            PackageType.PYTHON_WHEEL: "pypi",
            PackageType.PYTHON_SDIST: "pypi",
            PackageType.NPM: "npm",
            PackageType.MAVEN: "maven",
            PackageType.JAR: "maven",
            PackageType.GRADLE: "maven",
            PackageType.RUBY_GEM: "gem",
            PackageType.RUST_CRATE: "cargo",
            PackageType.GO_MODULE: "golang",
            PackageType.NUGET: "nuget",
            PackageType.CONDA: "conda",
            PackageType.DEB: "deb",
            PackageType.RPM: "rpm",
        }
        return mapping.get(package_type)

    def extract_metadata(self, package_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from PurlDB package info.

        Args:
            package_info: PurlDB package information

        Returns:
            Extracted metadata
        """
        metadata = {}

        try:
            # Extract basic info
            if 'description' in package_info:
                metadata['description'] = package_info['description']

            if 'homepage_url' in package_info:
                metadata['homepage'] = package_info['homepage_url']
            elif 'project_url' in package_info:
                metadata['homepage'] = package_info['project_url']

            if 'repository_homepage_url' in package_info:
                metadata['repository'] = package_info['repository_homepage_url']
            elif 'vcs_url' in package_info:
                metadata['repository'] = package_info['vcs_url']

            # Extract licensing information
            if 'license_expression' in package_info:
                metadata['license_expression'] = package_info['license_expression']
            elif 'declared_license' in package_info:
                metadata['licenses'] = package_info['declared_license']

            # Extract keywords
            if 'keywords' in package_info:
                metadata['keywords'] = package_info['keywords']

            # Extract parties (authors/maintainers)
            if 'parties' in package_info:
                authors = []
                maintainers = []

                for party in package_info['parties']:
                    party_data = {
                        'name': party.get('name', NO_ASSERTION),
                        'email': party.get('email', NO_ASSERTION)
                    }

                    # Add role-specific information
                    role = party.get('role', '').lower()
                    if 'author' in role:
                        authors.append(party_data)
                    elif 'maintainer' in role:
                        maintainers.append(party_data)
                    else:
                        # Default to author if no specific role
                        authors.append(party_data)

                if authors:
                    metadata['authors'] = authors
                if maintainers:
                    metadata['maintainers'] = maintainers

            # Extract download information
            if 'download_url' in package_info:
                metadata['download_url'] = package_info['download_url']

            # Extract file information
            if 'size' in package_info:
                metadata['size'] = package_info['size']

            if 'release_date' in package_info:
                metadata['release_date'] = package_info['release_date']

            # Extract dependencies
            if 'dependencies' in package_info:
                metadata['dependencies'] = package_info['dependencies']

        except Exception as e:
            print(f"Error extracting metadata from PurlDB: {e}")

        return metadata