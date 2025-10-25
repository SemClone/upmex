"""VulnerableCode API integration for vulnerability information."""

import requests
from typing import Optional, Dict, Any, List
from ..core.models import PackageType


class VulnerableCodeAPI:
    """Client for VulnerableCode API."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://public.vulnerablecode.io"):
        """Initialize VulnerableCode API client.

        Args:
            api_key: API key for authenticated requests (required for VulnerableCode)
            base_url: Base URL for VulnerableCode instance
        """
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {'Content-Type': 'application/json'}
        if api_key:
            self.headers['Authorization'] = f'Token {api_key}'

    def get_vulnerabilities_by_purl(self, purl: str) -> Optional[Dict[str, Any]]:
        """Get vulnerability information by PURL.

        Args:
            purl: Package URL (PURL) string

        Returns:
            Vulnerability information or None
        """
        if not self.api_key:
            print("Warning: VulnerableCode API key not provided - skipping vulnerability check")
            return None

        try:
            url = f"{self.base_url}/api/packages"
            params = {'purl': purl}

            response = requests.get(url, params=params, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data
            elif response.status_code == 401:
                print("Warning: VulnerableCode API authentication failed - check API key")
                return None
            else:
                print(f"Warning: VulnerableCode API returned status {response.status_code}")
                return None

        except Exception as e:
            print(f"Error fetching from VulnerableCode: {e}")

        return None

    def get_vulnerabilities(self, package_type: PackageType, name: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get vulnerability information by package details.

        Args:
            package_type: Type of package
            name: Package name (can include namespace)
            version: Optional package version

        Returns:
            Vulnerability information or None
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

            # Construct PURL
            purl_parts = [f"pkg:{purl_type}"]
            if namespace:
                purl_parts.append(f"/{namespace}")
            purl_parts.append(f"/{package_name}")
            if version:
                purl_parts.append(f"@{version}")

            purl = "".join(purl_parts)
            return self.get_vulnerabilities_by_purl(purl)

        except Exception as e:
            print(f"Error constructing PURL for VulnerableCode: {e}")

        return None

    def _map_package_type(self, package_type: PackageType) -> Optional[str]:
        """Map PackageType to PURL type string.

        Args:
            package_type: Package type enum

        Returns:
            PURL type string or None
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

    def extract_vulnerabilities(self, vulnerability_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract vulnerability information from VulnerableCode response.

        Args:
            vulnerability_data: VulnerableCode API response

        Returns:
            Extracted vulnerability information
        """
        vulnerabilities = {
            'total_count': 0,
            'vulnerable_packages': [],
            'fixing_packages': [],
            'summary': {
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
                'unknown': 0
            }
        }

        try:
            if 'count' in vulnerability_data:
                vulnerabilities['total_count'] = vulnerability_data['count']

            results = vulnerability_data.get('results', [])

            for result in results:
                package_info = {
                    'purl': result.get('purl'),
                    'is_vulnerable': result.get('is_vulnerable', False),
                    'next_non_vulnerable_version': result.get('next_non_vulnerable_version'),
                    'affected_by_vulnerabilities': [],
                    'fixing_vulnerabilities': []
                }

                # Extract vulnerabilities affecting this package
                for vuln in result.get('affected_by_vulnerabilities', []):
                    vuln_info = {
                        'vulnerability_id': vuln.get('vulnerability_id'),
                        'summary': vuln.get('summary'),
                        'aliases': vuln.get('aliases', []),
                        'severity_scores': []
                    }

                    # Extract severity scores
                    for score in vuln.get('severities', []):
                        score_info = {
                            'system': score.get('scoring_system'),
                            'value': score.get('value'),
                            'scoring_elements': score.get('scoring_elements')
                        }
                        vuln_info['severity_scores'].append(score_info)

                        # Count severity levels for summary
                        if score.get('scoring_system') == 'cvssv3.1_base':
                            score_val = score.get('value', 0)
                            try:
                                score_float = float(score_val)
                                if score_float >= 9.0:
                                    vulnerabilities['summary']['critical'] += 1
                                elif score_float >= 7.0:
                                    vulnerabilities['summary']['high'] += 1
                                elif score_float >= 4.0:
                                    vulnerabilities['summary']['medium'] += 1
                                elif score_float > 0:
                                    vulnerabilities['summary']['low'] += 1
                                else:
                                    vulnerabilities['summary']['unknown'] += 1
                            except (ValueError, TypeError):
                                vulnerabilities['summary']['unknown'] += 1

                    package_info['affected_by_vulnerabilities'].append(vuln_info)

                # Extract vulnerabilities fixed by this package
                for vuln in result.get('fixing_vulnerabilities', []):
                    fix_info = {
                        'vulnerability_id': vuln.get('vulnerability_id'),
                        'summary': vuln.get('summary'),
                        'aliases': vuln.get('aliases', [])
                    }
                    package_info['fixing_vulnerabilities'].append(fix_info)

                if package_info['is_vulnerable']:
                    vulnerabilities['vulnerable_packages'].append(package_info)
                elif package_info['fixing_vulnerabilities']:
                    vulnerabilities['fixing_packages'].append(package_info)

        except Exception as e:
            print(f"Error extracting vulnerabilities from VulnerableCode: {e}")

        return vulnerabilities