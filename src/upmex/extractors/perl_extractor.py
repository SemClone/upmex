"""Perl/CPAN package extractor."""

import json
import tarfile
import zipfile
import tempfile
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..core.models import PackageMetadata, PackageType, LicenseInfo, NO_ASSERTION, LicenseConfidenceLevel


class PerlExtractor:
    """Extractor for Perl/CPAN packages."""
    
    def __init__(self):
        """Initialize the Perl extractor."""
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a Perl package.
        
        Args:
            package_path: Path to the Perl package file
            
        Returns:
            PackageMetadata object with extracted information
        """
        package_path = str(package_path)
        
        # Determine package format and extract
        if package_path.endswith('.tar.gz'):
            return self._extract_from_tarball(package_path)
        elif package_path.endswith('.zip'):
            return self._extract_from_zip(package_path)
        else:
            # Try as tarball by default
            return self._extract_from_tarball(package_path)
    
    def _extract_from_tarball(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a tar.gz Perl package.
        
        Args:
            package_path: Path to the tar.gz package
            
        Returns:
            PackageMetadata object
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract the tarball
            with tarfile.open(package_path, 'r:gz') as tar:
                tar.extractall(temp_dir)
            
            # Find the extracted directory
            extracted_dirs = [d for d in os.listdir(temp_dir) 
                            if os.path.isdir(os.path.join(temp_dir, d))]
            
            if extracted_dirs:
                package_dir = os.path.join(temp_dir, extracted_dirs[0])
            else:
                package_dir = temp_dir
            
            return self._extract_from_directory(package_dir)
    
    def _extract_from_zip(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a zip Perl package.
        
        Args:
            package_path: Path to the zip package
            
        Returns:
            PackageMetadata object
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract the zip file
            with zipfile.ZipFile(package_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find the extracted directory
            extracted_dirs = [d for d in os.listdir(temp_dir) 
                            if os.path.isdir(os.path.join(temp_dir, d))]
            
            if extracted_dirs:
                package_dir = os.path.join(temp_dir, extracted_dirs[0])
            else:
                package_dir = temp_dir
            
            return self._extract_from_directory(package_dir)
    
    def _extract_from_directory(self, package_dir: str) -> PackageMetadata:
        """Extract metadata from an extracted Perl package directory.
        
        Args:
            package_dir: Path to the extracted package directory
            
        Returns:
            PackageMetadata object
        """
        metadata_dict = {}
        
        # Try to read META.json first (preferred)
        meta_json_path = os.path.join(package_dir, 'META.json')
        if os.path.exists(meta_json_path):
            with open(meta_json_path, 'r', encoding='utf-8') as f:
                metadata_dict = json.load(f)
        
        # Fall back to META.yml if META.json not found
        elif os.path.exists(os.path.join(package_dir, 'META.yml')):
            metadata_dict = self._parse_meta_yml(os.path.join(package_dir, 'META.yml'))
        
        # Also check for MYMETA files (generated during build)
        elif os.path.exists(os.path.join(package_dir, 'MYMETA.json')):
            with open(os.path.join(package_dir, 'MYMETA.json'), 'r', encoding='utf-8') as f:
                metadata_dict = json.load(f)
        elif os.path.exists(os.path.join(package_dir, 'MYMETA.yml')):
            metadata_dict = self._parse_meta_yml(os.path.join(package_dir, 'MYMETA.yml'))
        
        # Extract core metadata
        name = metadata_dict.get('name', NO_ASSERTION)
        version = str(metadata_dict.get('version', NO_ASSERTION))
        
        # Create PackageMetadata object
        metadata = PackageMetadata(
            name=name,
            version=version,
            package_type=PackageType.PERL
        )
        
        # Extract description
        metadata.description = metadata_dict.get('abstract', NO_ASSERTION)
        
        # Extract author information
        authors = metadata_dict.get('author', [])
        if isinstance(authors, str):
            authors = [authors]
        
        metadata.authors = []
        for author_str in authors:
            author_dict = self._parse_author(author_str)
            if author_dict:
                metadata.authors.append(author_dict)
        
        # Extract license information
        licenses = metadata_dict.get('license', [])
        if isinstance(licenses, str):
            licenses = [licenses]
        
        metadata.licenses = []
        for license_str in licenses:
            spdx_id = self._map_perl_license(license_str)
            if spdx_id:
                license_info = LicenseInfo(
                    spdx_id=spdx_id,
                    name=spdx_id,
                    detection_method='metadata',
                    confidence=1.0
                )
                metadata.licenses.append(license_info)
        
        # Also try to detect licenses from files
        license_files = self._find_license_files(package_dir)
        for license_file in license_files:
            try:
                with open(license_file, 'r', encoding='utf-8', errors='ignore') as f:
                    license_text = f.read()
                # Use unified detector which uses OSLiLi
                from ..licenses.unified_detector import detect_licenses
                detected_list = detect_licenses("LICENSE", license_text)

                detected_licenses = None
                if detected_list:
                    # Convert first detection to LicenseInfo
                    license_dict = detected_list[0]
                    detected_licenses = LicenseInfo(
                        name=license_dict.get('name', 'Unknown'),
                        spdx_id=license_dict.get('spdx_id', 'Unknown'),
                        confidence=license_dict.get('confidence', 0.0),
                        confidence_level=LicenseConfidenceLevel(
                            license_dict.get('confidence_level', 'low')
                        ),
                        detection_method=license_dict.get('source', 'oslili')
                    )
                for detected in detected_licenses:
                    if not any(l.spdx_id == detected.spdx_id for l in metadata.licenses):
                        metadata.licenses.append(detected)
            except Exception:
                pass
        
        # Extract dependencies
        metadata.dependencies = self._extract_dependencies(metadata_dict.get('prereqs', {}))
        
        # Extract keywords
        metadata.keywords = metadata_dict.get('keywords', [])
        
        # Extract URLs
        resources = metadata_dict.get('resources', {})
        metadata.homepage = resources.get('homepage', NO_ASSERTION)
        
        # Extract repository URL
        repository = resources.get('repository', {})
        if isinstance(repository, dict):
            metadata.repository = repository.get('web') or repository.get('url') or NO_ASSERTION
        elif isinstance(repository, str):
            metadata.repository = repository
        else:
            metadata.repository = NO_ASSERTION
        
        # Extract provides (packages provided by this distribution)
        provides = metadata_dict.get('provides', {})
        if provides:
            # Store provided packages as keywords
            if not metadata.keywords:
                metadata.keywords = []
            for package_name in provides.keys():
                if package_name not in metadata.keywords:
                    metadata.keywords.append(package_name)
        
        return metadata
    
    def _parse_meta_yml(self, yml_path: str) -> Dict[str, Any]:
        """Parse META.yml file.
        
        Args:
            yml_path: Path to META.yml file
            
        Returns:
            Dictionary with metadata
        """
        try:
            import yaml
            with open(yml_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except ImportError:
            # PyYAML not available, try basic parsing
            return self._parse_yml_basic(yml_path)
    
    def _parse_yml_basic(self, yml_path: str) -> Dict[str, Any]:
        """Basic YAML parsing without PyYAML.
        
        Args:
            yml_path: Path to META.yml file
            
        Returns:
            Dictionary with basic metadata
        """
        metadata = {}
        
        with open(yml_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                # Simple key-value parsing
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Store simple values
                    if key in ['name', 'version', 'abstract', 'license']:
                        metadata[key] = value
        
        return metadata
    
    def _parse_author(self, author_str: str) -> Optional[Dict[str, str]]:
        """Parse author string into name and email.
        
        Args:
            author_str: Author string like "Name <email@example.com>"
            
        Returns:
            Dictionary with name and email or None
        """
        if not author_str:
            return None
        
        author_dict = {}
        
        # Parse "Name <email>" format
        if '<' in author_str and '>' in author_str:
            name_part = author_str[:author_str.index('<')].strip()
            email_part = author_str[author_str.index('<')+1:author_str.index('>')].strip()
            
            if name_part:
                author_dict['name'] = name_part
            if email_part:
                author_dict['email'] = email_part
        else:
            # Just a name
            author_dict['name'] = author_str.strip()
        
        return author_dict if author_dict else None
    
    def _map_perl_license(self, perl_license: str) -> Optional[str]:
        """Map Perl license string to SPDX identifier.
        
        Args:
            perl_license: Perl license string
            
        Returns:
            SPDX license identifier or None
        """
        license_mapping = {
            'perl_5': 'Artistic-1.0 OR GPL-1.0-or-later',
            'perl': 'Artistic-1.0 OR GPL-1.0-or-later',
            'artistic_1': 'Artistic-1.0',
            'artistic_2': 'Artistic-2.0',
            'apache_2_0': 'Apache-2.0',
            'apache': 'Apache-2.0',
            'bsd': 'BSD-3-Clause',
            'freebsd': 'BSD-2-Clause-FreeBSD',
            'gpl_1': 'GPL-1.0',
            'gpl_2': 'GPL-2.0',
            'gpl_3': 'GPL-3.0',
            'lgpl_2_1': 'LGPL-2.1',
            'lgpl_3_0': 'LGPL-3.0',
            'mit': 'MIT',
            'mozilla_1_1': 'MPL-1.1',
            'mozilla_2_0': 'MPL-2.0',
            'open_source': 'OSI-Approved',
            'unrestricted': 'Unlicense',
            'unknown': None,
            'restricted': 'Proprietary'
        }
        
        return license_mapping.get(perl_license.lower(), perl_license)
    
    def _extract_dependencies(self, prereqs: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract dependencies from prereqs section.
        
        Args:
            prereqs: Prerequisites section from metadata
            
        Returns:
            List of dependency dictionaries
        """
        dependencies = []
        
        # Process each phase
        for phase, relationships in prereqs.items():
            if not isinstance(relationships, dict):
                continue
            
            # Process each relationship type
            for relationship, deps in relationships.items():
                if not isinstance(deps, dict):
                    continue
                
                for dep_name, dep_version in deps.items():
                    # Skip perl itself
                    if dep_name.lower() == 'perl':
                        continue
                    
                    dependency = {
                        'name': dep_name,
                        'version': str(dep_version) if dep_version else '*'
                    }
                    
                    # Add phase and relationship as extra info
                    if phase != 'runtime':
                        dependency['phase'] = phase
                    if relationship != 'requires':
                        dependency['relationship'] = relationship
                    
                    dependencies.append(dependency)
        
        return dependencies
    
    def _find_license_files(self, package_dir: str) -> List[str]:
        """Find license files in the package directory.
        
        Args:
            package_dir: Path to package directory
            
        Returns:
            List of paths to license files
        """
        license_files = []
        license_patterns = [
            'LICENSE', 'LICENSE.*', 'LICENCE', 'LICENCE.*',
            'COPYING', 'COPYING.*', 'COPYRIGHT',
            'ARTISTIC', 'GPL'
        ]
        
        for pattern in license_patterns:
            # Check exact match
            if '.' not in pattern:
                file_path = os.path.join(package_dir, pattern)
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    license_files.append(file_path)
            else:
                # Check pattern match
                base_pattern = pattern.replace('.*', '')
                for file_name in os.listdir(package_dir):
                    if file_name.startswith(base_pattern):
                        file_path = os.path.join(package_dir, file_name)
                        if os.path.isfile(file_path):
                            license_files.append(file_path)
        
        return license_files