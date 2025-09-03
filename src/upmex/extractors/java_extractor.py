"""Java/Maven package extractor."""

import zipfile
import xml.etree.ElementTree as ET
import re
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from .base import BaseExtractor
from ..core.models import PackageMetadata, PackageType, NO_ASSERTION


class JavaExtractor(BaseExtractor):
    """Extractor for Java JAR and Maven packages."""
    
    def __init__(self, online_mode: bool = False):
        """Initialize the Java extractor."""
        super().__init__(online_mode)
        self.maven_central_url = "https://repo1.maven.org/maven2"
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from Java package."""
        metadata = self.create_metadata(package_type=PackageType.JAR)
        
        try:
            with zipfile.ZipFile(package_path, 'r') as zf:
                # Check for Maven POM
                pom_metadata = self._extract_maven_metadata(zf)
                if pom_metadata:
                    metadata = pom_metadata
                else:
                    # Fallback to MANIFEST.MF
                    metadata = self._extract_manifest_metadata(zf)
                    metadata.package_type = PackageType.JAR
                
                # Detect licenses from files in the archive (e.g., META-INF/LICENSE)
                detected_licenses = self.find_and_detect_licenses(archive_path=package_path)
                if detected_licenses and not metadata.licenses:
                    metadata.licenses = detected_licenses
                elif detected_licenses:
                    # Merge with existing licenses, avoiding duplicates
                    existing_spdx_ids = {lic.spdx_id for lic in metadata.licenses if lic.spdx_id}
                    for lic in detected_licenses:
                        if lic.spdx_id not in existing_spdx_ids:
                            metadata.licenses.append(lic)
                            existing_spdx_ids.add(lic.spdx_id)
                
                # Extract copyright information
                import tempfile
                import os
                with tempfile.TemporaryDirectory() as temp_dir:
                    try:
                        # Extract limited files for copyright scanning
                        members = zf.namelist()[:100]  # Limit to first 100 files
                        for member in members:
                            zf.extract(member, temp_dir)
                        
                        # Detect copyrights and merge holders with authors
                        copyright_statement = self.find_and_detect_copyrights(
                            directory_path=temp_dir,
                            merge_with_authors=True,
                            metadata=metadata
                        )
                        if copyright_statement:
                            metadata.copyright = copyright_statement
                    except Exception as e:
                        print(f"Error extracting for copyright: {e}")
                            
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
                    
                    metadata = self.create_metadata(package_type=PackageType.MAVEN)
                    
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
                        dev_id = dev.findtext('maven:id', None, ns) or dev.findtext('id')
                        dev_org = dev.findtext('maven:organization', None, ns) or dev.findtext('organization')
                        
                        # Use id or organization as fallback for name
                        if not dev_name:
                            if dev_org:
                                dev_name = dev_org
                            elif dev_id:
                                dev_name = dev_id
                        
                        if dev_name or dev_email:
                            metadata.authors.append({
                                'name': dev_name or NO_ASSERTION,
                                'email': dev_email or NO_ASSERTION
                            })
                    
                    # Extract license from embedded POM first
                    licenses_elem = root.find('.//maven:licenses', ns) or root.find('.//licenses')
                    if licenses_elem is not None:
                        license_elems = licenses_elem.findall('./maven:license', ns) or licenses_elem.findall('./license')
                        for license_elem in license_elems:
                            license_name = license_elem.findtext('maven:name', '', ns) or license_elem.findtext('name', '')
                            if license_name:
                                # Format license text for better oslili detection
                                if len(license_name) < 20 and ':' not in license_name:
                                    formatted_text = f"License: {license_name}"
                                else:
                                    formatted_text = license_name
                                license_infos = self.detect_licenses_from_text(
                                    formatted_text,
                                    filename='pom.xml'
                                )
                                if license_infos:
                                    metadata.licenses.extend(license_infos)
                    
                    # Check if we have real data or just NO-ASSERTION placeholders
                    has_real_authors = metadata.authors and any(
                        author.get('name') != NO_ASSERTION or author.get('email') != NO_ASSERTION 
                        for author in metadata.authors
                    )
                    has_real_repository = metadata.repository and metadata.repository != NO_ASSERTION
                    
                    # If missing critical data and online mode is enabled, fetch parent POM
                    if self.online_mode and (not has_real_authors or not has_real_repository or not metadata.licenses):
                        parent = root.find('./maven:parent', ns) or root.find('./parent')
                        if parent is not None:
                            parent_group = parent.findtext('maven:groupId', '', ns) or parent.findtext('groupId', '')
                            parent_artifact = parent.findtext('maven:artifactId', '', ns) or parent.findtext('artifactId', '')
                            parent_version = parent.findtext('maven:version', '', ns) or parent.findtext('version', '')
                            
                            if parent_group and parent_artifact and parent_version:
                                parent_metadata = self._fetch_parent_pom(parent_group, parent_artifact, parent_version)
                                if parent_metadata:
                                    parent_pom_url = f"https://repo1.maven.org/maven2/{parent_group.replace('.', '/')}/{parent_artifact}/{parent_version}/{parent_artifact}-{parent_version}.pom"
                                    
                                    # Only replace NO-ASSERTION values, don't overwrite real data
                                    if not metadata.description and parent_metadata.get('description'):
                                        metadata.description = parent_metadata['description']
                                        metadata.provenance['description'] = f"parent_pom:{parent_pom_url}"
                                    if not has_real_authors and parent_metadata.get('authors'):
                                        metadata.authors = parent_metadata['authors']
                                        metadata.provenance['authors'] = f"parent_pom:{parent_pom_url}"
                                    if not metadata.maintainers and parent_metadata.get('maintainers'):
                                        metadata.maintainers = parent_metadata['maintainers']
                                        metadata.provenance['maintainers'] = f"parent_pom:{parent_pom_url}"
                                    if not has_real_repository and parent_metadata.get('repository'):
                                        metadata.repository = parent_metadata['repository']
                                        metadata.provenance['repository'] = f"parent_pom:{parent_pom_url}"
                                    if not metadata.homepage and parent_metadata.get('homepage'):
                                        metadata.homepage = parent_metadata['homepage']
                                        metadata.provenance['homepage'] = f"parent_pom:{parent_pom_url}"
                                    if not metadata.licenses and parent_metadata.get('licenses'):
                                        metadata.licenses = parent_metadata['licenses']
                                        metadata.provenance['licenses'] = f"parent_pom:{parent_pom_url}"
                    
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
        metadata = self.create_metadata(package_type=PackageType.JAR)
        
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
                
                # Extract developers (as both authors and maintainers)
                developers = []
                maintainers = []
                for dev in root.findall('.//maven:developer', ns) or root.findall('.//developer'):
                    dev_name = dev.findtext('maven:name', None, ns) or dev.findtext('name')
                    dev_email = dev.findtext('maven:email', None, ns) or dev.findtext('email')
                    dev_id = dev.findtext('maven:id', None, ns) or dev.findtext('id')
                    dev_org = dev.findtext('maven:organization', None, ns) or dev.findtext('organization')
                    dev_role = dev.find('maven:roles/maven:role', ns) or dev.find('roles/role')
                    role_text = dev_role.text if dev_role is not None else None
                    
                    # Use id or organization as fallback for name
                    if not dev_name:
                        if dev_org:
                            dev_name = dev_org
                        elif dev_id:
                            dev_name = dev_id
                    
                    if dev_name or dev_email:
                        dev_info = {
                            'name': dev_name or NO_ASSERTION,
                            'email': dev_email or NO_ASSERTION
                        }
                        developers.append(dev_info)
                        
                        # Also add as maintainer with organization info
                        maintainer_info = dev_info.copy()
                        if dev_org:
                            maintainer_info['organization'] = dev_org
                        if role_text:
                            maintainer_info['role'] = role_text
                        maintainers.append(maintainer_info)
                
                if developers:
                    parent_data['authors'] = developers
                if maintainers:
                    parent_data['maintainers'] = maintainers
                
                # Also extract contributors as additional maintainers
                for contrib in root.findall('.//maven:contributor', ns) or root.findall('.//contributor'):
                    contrib_name = contrib.findtext('maven:name', None, ns) or contrib.findtext('name')
                    contrib_email = contrib.findtext('maven:email', None, ns) or contrib.findtext('email')
                    contrib_org = contrib.findtext('maven:organization', None, ns) or contrib.findtext('organization')
                    
                    if contrib_name or contrib_email:
                        maintainer_info = {
                            'name': contrib_name or NO_ASSERTION,
                            'email': contrib_email or NO_ASSERTION
                        }
                        if contrib_org:
                            maintainer_info['organization'] = contrib_org
                        maintainer_info['role'] = 'contributor'
                        
                        if 'maintainers' not in parent_data:
                            parent_data['maintainers'] = []
                        parent_data['maintainers'].append(maintainer_info)
                
                # Extract description
                description = root.findtext('.//maven:description', None, ns) or root.findtext('.//description')
                if description:
                    parent_data['description'] = description
                
                # Extract homepage
                homepage = root.findtext('.//maven:url', None, ns) or root.findtext('.//url')
                if homepage:
                    parent_data['homepage'] = homepage
                
                # Extract licenses
                licenses = []
                licenses_elem = root.find('.//maven:licenses', ns) or root.find('.//licenses')
                if licenses_elem is not None:
                    license_elems = licenses_elem.findall('maven:license', ns)  # Remove ./ prefix
                    if not license_elems:
                        license_elems = licenses_elem.findall('license')  # Try without namespace
                    
                    for license_elem in license_elems:
                        license_name = license_elem.findtext('maven:name', '', ns) or license_elem.findtext('name', '')
                        if license_name:
                            # Use the same license detection as in main extraction
                            try:
                                # Format license text for better oslili detection
                                if len(license_name) < 20 and ':' not in license_name:
                                    formatted_text = f"License: {license_name}"
                                else:
                                    formatted_text = license_name
                                license_infos = self.detect_licenses_from_text(
                                    formatted_text,
                                    filename='parent_pom.xml'
                                )
                                if license_infos:
                                    # Update detection method to clarify source
                                    for info in license_infos:
                                        info.detection_method = 'parent_pom_regex'
                                        info.file_path = f"parent:{artifact_id}-{version}.pom"
                                    licenses.extend(license_infos)
                            except Exception as lic_err:
                                print(f"Error detecting license '{license_name}': {lic_err}")
                
                if licenses:
                    parent_data['licenses'] = licenses
                
                # Also check for license/author info in header comments
                header_data = self._parse_pom_header(response.text)
                if header_data:
                    if 'authors' in header_data and not parent_data.get('authors'):
                        parent_data['authors'] = header_data['authors']
                    if 'license' in header_data and not parent_data.get('licenses'):
                        # Convert header license text to proper format
                        license_text = header_data['license']
                        # Format license text for better oslili detection
                        if len(license_text) < 20 and ':' not in license_text:
                            formatted_text = f"License: {license_text}"
                        else:
                            formatted_text = license_text
                        license_infos = self.detect_licenses_from_text(
                            formatted_text,
                            filename='pom.xml'
                        )
                        if license_infos:
                            parent_data['licenses'] = license_infos
                
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