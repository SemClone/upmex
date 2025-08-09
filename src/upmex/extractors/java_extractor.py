"""Java/Maven package extractor."""

import zipfile
import xml.etree.ElementTree as ET
import re
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from .base import BaseExtractor
from ..core.models import PackageMetadata, PackageType, NO_ASSERTION
from ..utils.license_detector import LicenseDetector


class JavaExtractor(BaseExtractor):
    """Extractor for Java JAR and Maven packages."""
    
    def __init__(self, online_mode: bool = False):
        """Initialize Java extractor."""
        super().__init__(online_mode)
        self.maven_central_url = "https://repo1.maven.org/maven2"
        self.license_detector = LicenseDetector()
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from Java package."""
        metadata = PackageMetadata(
            name="unknown",
            package_type=PackageType.JAR
        )
        
        try:
            with zipfile.ZipFile(package_path, 'r') as zf:
                # Check for Maven POM
                pom_metadata = self._extract_maven_metadata(zf)
                if pom_metadata:
                    metadata = pom_metadata
                    metadata.package_type = PackageType.MAVEN
                else:
                    # Fallback to MANIFEST.MF
                    metadata = self._extract_manifest_metadata(zf)
                    metadata.package_type = PackageType.JAR
        except Exception as e:
            print(f"Error extracting Java metadata: {e}")
        
        return metadata
    
    def can_extract(self, package_path: str) -> bool:
        """Check if this is a Java package."""
        path = Path(package_path)
        return path.suffix in ['.jar', '.war', '.ear']
    
    def _extract_maven_metadata(self, zf: zipfile.ZipFile) -> Optional[PackageMetadata]:
        """Extract metadata from Maven POM file."""
        for name in zf.namelist():
            if name.startswith('META-INF/maven/') and name.endswith('/pom.xml'):
                try:
                    content = zf.read(name)
                    root = ET.fromstring(content)
                    
                    # Handle namespace
                    ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
                    
                    metadata = PackageMetadata(
                        name="unknown",
                        package_type=PackageType.MAVEN
                    )
                    
                    # Extract basic info - check parent if not found directly
                    group_id = root.findtext('./maven:groupId', '', ns) or root.findtext('./groupId', '')
                    if not group_id:
                        # Try parent groupId
                        parent = root.find('./maven:parent', ns) or root.find('./parent')
                        if parent is not None:
                            group_id = parent.findtext('maven:groupId', '', ns) or parent.findtext('groupId', '')
                    
                    artifact_id = root.findtext('./maven:artifactId', '', ns) or root.findtext('./artifactId', '')
                    
                    if group_id and artifact_id:
                        metadata.name = f"{group_id}:{artifact_id}"
                    elif artifact_id:
                        metadata.name = artifact_id
                    
                    metadata.version = root.findtext('.//maven:version', None, ns) or root.findtext('.//version')
                    metadata.description = root.findtext('.//maven:description', None, ns) or root.findtext('.//description')
                    metadata.homepage = root.findtext('.//maven:url', None, ns) or root.findtext('.//url')
                    
                    # Extract SCM/repository information
                    scm = root.find('.//maven:scm', ns) or root.find('.//scm')
                    if scm is not None:
                        # Try different SCM URLs in order of preference
                        repo_url = (scm.findtext('maven:url', None, ns) or 
                                   scm.findtext('url') or
                                   scm.findtext('maven:connection', None, ns) or 
                                   scm.findtext('connection') or
                                   scm.findtext('maven:developerConnection', None, ns) or
                                   scm.findtext('developerConnection'))
                        if repo_url:
                            # Clean up SCM URLs (remove scm:git: prefix)
                            if repo_url.startswith('scm:'):
                                repo_url = repo_url.split(':', 2)[-1]
                            metadata.repository = repo_url
                    
                    # Extract developers (authors)
                    developers = root.findall('.//maven:developer', ns) or root.findall('.//developer')
                    for dev in developers:
                        dev_name = dev.findtext('maven:name', None, ns) or dev.findtext('name')
                        dev_email = dev.findtext('maven:email', None, ns) or dev.findtext('email')
                        if dev_name or dev_email:
                            metadata.authors.append({
                                'name': dev_name,
                                'email': dev_email
                            })
                    
                    # If missing critical data and online mode is enabled, fetch parent POM
                    if self.online_mode and (not metadata.authors or not metadata.repository):
                        parent = root.find('./maven:parent', ns) or root.find('./parent')
                        if parent is not None:
                            parent_group = parent.findtext('maven:groupId', '', ns) or parent.findtext('groupId', '')
                            parent_artifact = parent.findtext('maven:artifactId', '', ns) or parent.findtext('artifactId', '')
                            parent_version = parent.findtext('maven:version', '', ns) or parent.findtext('version', '')
                            
                            if parent_group and parent_artifact and parent_version:
                                parent_metadata = self._fetch_parent_pom(parent_group, parent_artifact, parent_version)
                                if parent_metadata:
                                    # Merge missing data from parent
                                    if not metadata.authors and parent_metadata.get('authors'):
                                        metadata.authors = parent_metadata['authors']
                                    if not metadata.repository and parent_metadata.get('repository'):
                                        metadata.repository = parent_metadata['repository']
                                    if not metadata.homepage and parent_metadata.get('homepage'):
                                        metadata.homepage = parent_metadata['homepage']
                    
                    # Extract license using regex detection
                    licenses_elem = root.find('.//maven:licenses', ns) or root.find('.//licenses')
                    if licenses_elem is not None:
                        for license_elem in licenses_elem.findall('./maven:license', ns) or licenses_elem.findall('./license'):
                            license_name = license_elem.findtext('maven:name', '', ns) or license_elem.findtext('name', '')
                            if license_name:
                                license_info = self.license_detector.detect_license_from_text(
                                    license_name,
                                    filename='pom.xml'
                                )
                                if license_info:
                                    metadata.licenses.append(license_info)
                    
                    # Extract dependencies
                    runtime_deps = []
                    dev_deps = []
                    for dep in root.findall('.//maven:dependency', ns) or root.findall('.//dependency'):
                        dep_group = dep.findtext('maven:groupId', '', ns) or dep.findtext('groupId', '')
                        dep_artifact = dep.findtext('maven:artifactId', '', ns) or dep.findtext('artifactId', '')
                        dep_scope = dep.findtext('maven:scope', 'compile', ns) or dep.findtext('scope', 'compile')
                        
                        if dep_group and dep_artifact:
                            dep_name = f"{dep_group}:{dep_artifact}"
                            # Separate by scope
                            if dep_scope in ['test']:
                                dev_deps.append(dep_name)
                            else:
                                runtime_deps.append(dep_name)
                    
                    if runtime_deps:
                        metadata.dependencies['runtime'] = runtime_deps
                    if dev_deps:
                        metadata.dependencies['dev'] = dev_deps
                    
                    # Set NO-ASSERTION for missing critical fields
                    if not metadata.authors:
                        metadata.authors = [{'name': NO_ASSERTION, 'email': NO_ASSERTION}]
                    if not metadata.repository:
                        metadata.repository = NO_ASSERTION
                    
                    return metadata
                except Exception as e:
                    print(f"Error parsing POM file: {e}")
        
        return None
    
    def _extract_manifest_metadata(self, zf: zipfile.ZipFile) -> PackageMetadata:
        """Extract metadata from MANIFEST.MF file."""
        metadata = PackageMetadata(
            name="unknown",
            package_type=PackageType.JAR
        )
        
        try:
            if 'META-INF/MANIFEST.MF' in zf.namelist():
                content = zf.read('META-INF/MANIFEST.MF').decode('utf-8')
                
                # Parse manifest
                manifest = {}
                for line in content.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        manifest[key.strip()] = value.strip()
                
                # Extract metadata
                metadata.name = manifest.get('Implementation-Title', manifest.get('Bundle-Name', 'unknown'))
                metadata.version = manifest.get('Implementation-Version', manifest.get('Bundle-Version'))
                metadata.description = manifest.get('Bundle-Description')
                
                # Store raw manifest
                metadata.raw_metadata = manifest
        except Exception as e:
            print(f"Error parsing MANIFEST.MF: {e}")
        
        return metadata
    
    def _fetch_parent_pom(self, group_id: str, artifact_id: str, version: str) -> Optional[Dict[str, Any]]:
        """Fetch parent POM from Maven Central.
        
        Args:
            group_id: Maven group ID
            artifact_id: Maven artifact ID  
            version: Maven version
            
        Returns:
            Dictionary with extracted parent metadata or None
        """
        try:
            # Construct Maven Central URL
            group_path = group_id.replace('.', '/')
            pom_url = f"{self.maven_central_url}/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.pom"
            
            # Fetch POM
            response = requests.get(pom_url, timeout=10)
            if response.status_code == 200:
                # Parse POM content
                root = ET.fromstring(response.content)
                ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
                
                parent_data = {}
                
                # Extract SCM/repository
                scm = root.find('.//maven:scm', ns) or root.find('.//scm')
                if scm is not None:
                    repo_url = (scm.findtext('maven:url', None, ns) or 
                               scm.findtext('url') or
                               scm.findtext('maven:connection', None, ns) or 
                               scm.findtext('connection'))
                    if repo_url:
                        if repo_url.startswith('scm:'):
                            repo_url = repo_url.split(':', 2)[-1]
                        parent_data['repository'] = repo_url
                
                # Extract developers
                developers = []
                for dev in root.findall('.//maven:developer', ns) or root.findall('.//developer'):
                    dev_name = dev.findtext('maven:name', None, ns) or dev.findtext('name')
                    dev_email = dev.findtext('maven:email', None, ns) or dev.findtext('email')
                    if dev_name or dev_email:
                        developers.append({
                            'name': dev_name or NO_ASSERTION,
                            'email': dev_email or NO_ASSERTION
                        })
                if developers:
                    parent_data['authors'] = developers
                
                # Extract homepage
                homepage = root.findtext('.//maven:url', None, ns) or root.findtext('.//url')
                if homepage:
                    parent_data['homepage'] = homepage
                
                # Also check for license/author info in header comments
                header_data = self._parse_pom_header(response.text)
                if header_data:
                    if 'authors' in header_data and not parent_data.get('authors'):
                        parent_data['authors'] = header_data['authors']
                    if 'license' in header_data:
                        parent_data['license'] = header_data['license']
                
                return parent_data
                
        except Exception as e:
            print(f"Error fetching parent POM: {e}")
        
        return None
    
    def _parse_pom_header(self, pom_content: str) -> Optional[Dict[str, Any]]:
        """Parse license and author information from POM header comments.
        
        Args:
            pom_content: Raw POM XML content
            
        Returns:
            Dictionary with parsed header data or None
        """
        try:
            header_data = {}
            
            # Look for license in header comments (common in Apache projects)
            license_pattern = r'<!--.*?Licensed under the (.*?) License.*?-->'
            license_match = re.search(license_pattern, pom_content, re.DOTALL | re.IGNORECASE)
            if license_match:
                header_data['license'] = license_match.group(1).strip()
            
            # Look for copyright/author in comments
            copyright_pattern = r'<!--.*?Copyright.*?(\d{4}).*?(?:by\s+)?(.*?)(?:\n|-->)'
            copyright_match = re.search(copyright_pattern, pom_content, re.DOTALL | re.IGNORECASE)
            if copyright_match:
                author = copyright_match.group(2).strip()
                if author and not author.startswith('<!--'):
                    # Clean up common patterns
                    author = re.sub(r'\s*All rights reserved\.?\s*', '', author, flags=re.IGNORECASE)
                    author = author.strip()
                    if author:
                        header_data['authors'] = [{'name': author, 'email': None}]
            
            return header_data if header_data else None
            
        except Exception as e:
            print(f"Error parsing POM header: {e}")
        
        return None