"""Java/Maven package extractor."""

import zipfile
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from .base import BaseExtractor
from ..api.maven_central import MavenCentralAPI
from ..core.models import (
    LicenseConfidenceLevel,
    LicenseInfo,
    PackageMetadata,
    PackageType,
    NO_ASSERTION,
    split_namespace,
)


class JavaExtractor(BaseExtractor):
    """Extractor for Java JAR and Maven packages."""
    
    def __init__(self, registry_mode: bool = False):
        """Initialize the Java extractor."""
        super().__init__(registry_mode)
        self.maven_central_url = "https://repo1.maven.org/maven2"
        self._maven_central = MavenCentralAPI(base_url=self.maven_central_url)
    
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

                # An archive with no POM has no coordinates and no <parent> to
                # follow, so the file hash is the only handle on its identity.
                if pom_metadata is None and self.registry_mode:
                    try:
                        self._resolve_from_file_hash(package_path, metadata)
                    except Exception as e:
                        # Optional enrichment must not cost us the local metadata
                        print(f"Error resolving coordinates from file hash: {e}")

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
                    
                    # Extract basic info - check parent if not found directly.
                    # Every lookup here is deliberately a direct child of <project>:
                    # a descendant search reaches into <parent>, <licenses> and
                    # <dependencies>, whose values belong to something else.
                    parent = root.find('./maven:parent', ns) or root.find('./parent')

                    group_id = root.findtext('./maven:groupId', '', ns) or root.findtext('./groupId', '')
                    if not group_id and parent is not None:
                        # Inherited from the parent, which is legitimate Maven
                        group_id = parent.findtext('maven:groupId', '', ns) or parent.findtext('groupId', '')

                    artifact_id = root.findtext('./maven:artifactId', '', ns) or root.findtext('./artifactId', '')

                    if group_id and artifact_id:
                        metadata.name = f"{group_id}:{artifact_id}"
                    elif artifact_id:
                        metadata.name = artifact_id

                    metadata.version = root.findtext('./maven:version', None, ns) or root.findtext('./version')
                    if not metadata.version and parent is not None:
                        # Only a module that declares no version of its own inherits
                        metadata.version = (parent.findtext('maven:version', None, ns) or
                                            parent.findtext('version'))
                    metadata.description = root.findtext('./maven:description', None, ns) or root.findtext('./description')
                    metadata.homepage = root.findtext('./maven:url', None, ns) or root.findtext('./url')

                    # Extract SCM/repository information
                    scm = root.find('./maven:scm', ns) or root.find('./scm')
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
                    developers = (root.findall('./maven:developers/maven:developer', ns) or
                                  root.findall('./developers/developer'))
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
                    licenses_elem = root.find('./maven:licenses', ns) or root.find('./licenses')
                    if licenses_elem is not None:
                        metadata.licenses.extend(self._detect_pom_licenses(
                            licenses_elem,
                            ns,
                            detection_method=None,
                            file_path='pom.xml',
                            filename='pom.xml'
                        ))
                    
                    # Check if we have real data or just NO-ASSERTION placeholders
                    has_real_authors = metadata.authors and any(
                        author.get('name') != NO_ASSERTION or author.get('email') != NO_ASSERTION 
                        for author in metadata.authors
                    )
                    has_real_repository = metadata.repository and metadata.repository != NO_ASSERTION
                    
                    # If missing critical data and registry mode is enabled, fetch parent POM
                    if self.registry_mode and (not has_real_authors or not has_real_repository or not metadata.licenses):
                        self._apply_parent_pom(root, ns, metadata)

                    # ClearlyDefined fallback enrichment in registry mode
                    if self.registry_mode:
                        # Re-check if we still need more data after parent POM
                        has_real_authors_after_parent = metadata.authors and any(
                            author.get('name') != NO_ASSERTION or author.get('email') != NO_ASSERTION
                            for author in metadata.authors
                        )
                        has_sufficient_licenses = len(metadata.licenses) >= 1
                        has_real_repository_after_parent = metadata.repository and metadata.repository != NO_ASSERTION

                        if not has_real_authors_after_parent or not has_sufficient_licenses or not has_real_repository_after_parent:
                            self._enrich_with_clearlydefined(metadata)

                    # Extract dependencies
                    runtime_deps = []
                    dev_deps = []
                    # Direct children only: <dependencyManagement> holds version
                    # pins for modules to opt into, not dependencies of this artifact
                    for dep in (root.findall('./maven:dependencies/maven:dependency', ns) or
                                root.findall('./dependencies/dependency')):
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
                    # Don't add fake authors - leave empty if not found
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
    
    def _resolve_from_file_hash(self, package_path: str, metadata: PackageMetadata) -> None:
        """Resolve Maven coordinates from the artifact's SHA-1 and enrich from its POM.

        Used for archives that carry no POM: shaded, relocated and repackaged jars
        declare no coordinates locally, so there is nothing to look a POM up by.

        Args:
            package_path: Path to the archive
            metadata: Metadata to enrich in place
        """
        # Hashed here rather than reusing PackageExtractor's digest, which is not
        # assigned until after extract() returns. An extractor also has to work
        # when used directly, which is how consumers reach this path.
        sha1 = self.file_sha1(package_path)
        if not sha1:
            return

        coordinates = self._maven_central.find_by_sha1(sha1)
        if not coordinates:
            return

        group_id = coordinates['group_id']
        artifact_id = coordinates['artifact_id']
        version = coordinates['version']
        hash_source = f"maven_central_hash:{coordinates['search_url']}"

        # An exact file-hash match identifies the artifact more reliably than the
        # manifest strings the fallback path guessed from, and coordinates are what
        # make the PURL resolvable. The manifest is still kept in raw_metadata.
        metadata.name = f"{group_id}:{artifact_id}"
        metadata.provenance['name'] = hash_source
        metadata.version = version
        metadata.provenance['version'] = hash_source
        applied_fields = ['name', 'version']

        fetched = self._maven_central.fetch_pom(group_id, artifact_id, version)
        if fetched:
            root, pom_text, pom_url = fetched
            ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
            pom_data = self._parse_pom_metadata(
                root,
                pom_text,
                detection_method='maven_central_pom',
                license_file_path=f"maven_central:{artifact_id}-{version}.pom",
                license_filename='pom.xml'
            )
            applied_fields.extend(
                self._apply_pom_data(metadata, pom_data, f"maven_central_pom:{pom_url}")
            )

            # The resolved POM may inherit its licences, so fall through to the
            # existing parent hop when it declares none of its own.
            if not metadata.licenses:
                self._apply_parent_pom(root, ns, metadata)

        metadata.add_enrichment(
            source="maven_central",
            source_type="registry",
            data={
                'sha1': sha1,
                'group_id': group_id,
                'artifact_id': artifact_id,
                'version': version,
                'packaging': coordinates['packaging'],
                'match_count': coordinates['match_count'],
                'resolved_by': 'file_hash'
            },
            applied_fields=applied_fields
        )

    def _apply_parent_pom(self, root: Any, ns: Dict[str, str], metadata: PackageMetadata) -> List[str]:
        """Follow a POM's <parent> and fill missing fields from it.

        Args:
            root: Parsed POM root element
            ns: XML namespace map
            metadata: Metadata to enrich in place

        Returns:
            List of fields that were filled from the parent POM
        """
        try:
            return self._fetch_and_apply_parent_pom(root, ns, metadata)
        except Exception as e:
            # Enrichment is optional: a registry problem must never cost the
            # caller the metadata that was parsed out of the archive itself.
            print(f"Error applying parent POM: {e}")
            return []

    def _fetch_and_apply_parent_pom(self, root: Any, ns: Dict[str, str], metadata: PackageMetadata) -> List[str]:
        """Fetch the parent POM named by a POM and apply its data.

        Args:
            root: Parsed POM root element
            ns: XML namespace map
            metadata: Metadata to enrich in place

        Returns:
            List of fields that were filled from the parent POM
        """
        parent = root.find('./maven:parent', ns) or root.find('./parent')
        if parent is None:
            return []

        parent_group = parent.findtext('maven:groupId', '', ns) or parent.findtext('groupId', '')
        parent_artifact = parent.findtext('maven:artifactId', '', ns) or parent.findtext('artifactId', '')
        parent_version = parent.findtext('maven:version', '', ns) or parent.findtext('version', '')
        if not (parent_group and parent_artifact and parent_version):
            return []

        fetched = self._maven_central.fetch_pom(parent_group, parent_artifact, parent_version)
        if not fetched:
            return []

        parent_root, parent_text, parent_pom_url = fetched
        parent_metadata = self._parse_pom_metadata(
            parent_root,
            parent_text,
            detection_method='parent_pom_regex',
            license_file_path=f"parent:{parent_artifact}-{parent_version}.pom",
            license_filename='parent_pom.xml'
        )
        applied_fields = self._apply_pom_data(metadata, parent_metadata, f"parent_pom:{parent_pom_url}")

        # Track registry enrichment
        if applied_fields:
            metadata.add_enrichment(
                source="maven_central",
                source_type="registry",
                data=self._enrichment_payload(parent_metadata),
                applied_fields=applied_fields
            )

        return applied_fields

    def _apply_pom_data(self, metadata: PackageMetadata, pom_data: Dict[str, Any], source: str) -> List[str]:
        """Fill empty metadata fields from a remotely fetched POM.

        Locally declared data always wins: only fields that are missing or hold
        NO-ASSERTION are replaced.

        Args:
            metadata: Metadata to enrich in place
            pom_data: Parsed POM data
            source: Provenance string recorded for each field that is filled

        Returns:
            List of fields that were filled
        """
        has_real_authors = metadata.authors and any(
            author.get('name') != NO_ASSERTION or author.get('email') != NO_ASSERTION
            for author in metadata.authors
        )
        has_real_repository = metadata.repository and metadata.repository != NO_ASSERTION

        applied_fields = []

        if not metadata.description and pom_data.get('description'):
            metadata.description = pom_data['description']
            metadata.provenance['description'] = source
            applied_fields.append('description')
        if not has_real_authors and pom_data.get('authors'):
            metadata.authors = pom_data['authors']
            metadata.provenance['authors'] = source
            applied_fields.append('authors')
        if not metadata.maintainers and pom_data.get('maintainers'):
            metadata.maintainers = pom_data['maintainers']
            metadata.provenance['maintainers'] = source
            applied_fields.append('maintainers')
        if not has_real_repository and pom_data.get('repository'):
            metadata.repository = pom_data['repository']
            metadata.provenance['repository'] = source
            applied_fields.append('repository')
        if not metadata.homepage and pom_data.get('homepage'):
            metadata.homepage = pom_data['homepage']
            metadata.provenance['homepage'] = source
            applied_fields.append('homepage')
        if not metadata.licenses and pom_data.get('licenses'):
            metadata.licenses = pom_data['licenses']
            metadata.provenance['licenses'] = source
            applied_fields.append('licenses')

        return applied_fields

    def _enrichment_payload(self, pom_data: Dict[str, Any]) -> Dict[str, Any]:
        """Reduce parsed POM data to JSON-serializable values for the audit record.

        Args:
            pom_data: Parsed POM data, which may hold LicenseInfo objects

        Returns:
            Dictionary safe to serialize in the enrichment record
        """
        payload = {key: value for key, value in pom_data.items() if key != 'licenses'}
        if pom_data.get('licenses'):
            payload['licenses'] = [
                lic.spdx_id for lic in pom_data['licenses'] if lic.spdx_id
            ]
        return payload

    def _detect_pom_licenses(self,
                             licenses_elem: Any,
                             ns: Dict[str, str],
                             detection_method: Optional[str],
                             file_path: str,
                             filename: str) -> List[LicenseInfo]:
        """Detect the licenses declared in a POM's <licenses> block.

        A POM declares its license as prose rather than an SPDX id, and the common
        spellings ("The Apache Software License, Version 2.0") are not something
        osslili can classify. So the declared <url> is tried as a second signal,
        and a declaration osslili cannot classify at all is recorded verbatim
        rather than dropped — as the npm extractor does for its declared field.

        Args:
            licenses_elem: The POM's <licenses> element
            ns: XML namespace map
            detection_method: Overrides osslili's detection method when set
            file_path: Source path recorded on each detected license
            filename: Filename hint passed to license detection

        Returns:
            List of detected licenses
        """
        licenses = []
        license_elems = (licenses_elem.findall('./maven:license', ns) or
                         licenses_elem.findall('./license'))

        for license_elem in license_elems:
            license_name = license_elem.findtext('maven:name', '', ns) or license_elem.findtext('name', '')
            if not license_name:
                continue

            license_url = license_elem.findtext('maven:url', '', ns) or license_elem.findtext('url', '')
            try:
                detected = self.detect_licenses_from_text(
                    self._format_license_text(license_name),
                    filename=filename
                )
                if not detected and license_url:
                    detected = self.detect_licenses_from_text(
                        f"License: {license_url}",
                        filename=filename
                    )

                if detected:
                    for info in detected:
                        if detection_method:
                            info.detection_method = detection_method
                        info.file_path = file_path
                    licenses.extend(detected)
                else:
                    licenses.append(LicenseInfo(
                        spdx_id=license_name,
                        name=license_name,
                        confidence=1.0,
                        confidence_level=LicenseConfidenceLevel.HIGH,
                        detection_method='declared',
                        file_path=file_path
                    ))
            except Exception as lic_err:
                print(f"Error detecting license '{license_name}': {lic_err}")

        return licenses

    @staticmethod
    def _format_license_text(text: str) -> str:
        """Format a short license declaration for better osslili detection.

        Args:
            text: Declared license name or URL

        Returns:
            Text prefixed with a license tag when it is short enough to be an id
        """
        if len(text) < 20 and ':' not in text:
            return f"License: {text}"
        return text

    def _parse_pom_metadata(self,
                            root: Any,
                            pom_text: str,
                            detection_method: str,
                            license_file_path: str,
                            license_filename: str) -> Dict[str, Any]:
        """Extract metadata from a POM fetched from Maven Central.

        Args:
            root: Parsed POM root element
            pom_text: Raw POM XML, used for header comment parsing
            detection_method: Detection method recorded on detected licenses
            license_file_path: Source path recorded on detected licenses
            license_filename: Filename hint passed to license detection

        Returns:
            Dictionary with extracted POM metadata
        """
        try:
            ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}

            pom_data = {}

            # Extract SCM/repository. Direct children only: a descendant
            # search reaches into <licenses> and <dependencies>.
            scm = root.find('./maven:scm', ns) or root.find('./scm')
            if scm is not None:
                repo_url = (scm.findtext('maven:url', None, ns) or
                           scm.findtext('url') or
                           scm.findtext('maven:connection', None, ns) or
                           scm.findtext('connection'))
                if repo_url:
                    if repo_url.startswith('scm:'):
                        repo_url = repo_url.split(':', 2)[-1]
                    pom_data['repository'] = repo_url
            
            # Extract developers (as both authors and maintainers)
            developers = []
            maintainers = []
            for dev in (root.findall('./maven:developers/maven:developer', ns) or
                        root.findall('./developers/developer')):
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
                pom_data['authors'] = developers
            if maintainers:
                pom_data['maintainers'] = maintainers

            # Also extract contributors as additional maintainers
            for contrib in (root.findall('./maven:contributors/maven:contributor', ns) or
                            root.findall('./contributors/contributor')):
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
                    
                    if 'maintainers' not in pom_data:
                        pom_data['maintainers'] = []
                    pom_data['maintainers'].append(maintainer_info)

            # Extract description
            description = root.findtext('./maven:description', None, ns) or root.findtext('./description')
            if description:
                pom_data['description'] = description

            # Extract homepage
            homepage = root.findtext('./maven:url', None, ns) or root.findtext('./url')
            if homepage:
                pom_data['homepage'] = homepage

            # Extract licenses
            licenses_elem = root.find('./maven:licenses', ns) or root.find('./licenses')
            if licenses_elem is not None:
                licenses = self._detect_pom_licenses(
                    licenses_elem,
                    ns,
                    detection_method=detection_method,
                    file_path=license_file_path,
                    filename=license_filename
                )
                if licenses:
                    pom_data['licenses'] = licenses

            # Also check for license/author info in header comments
            header_data = self._parse_pom_header(pom_text)
            if header_data:
                if 'authors' in header_data and not pom_data.get('authors'):
                    pom_data['authors'] = header_data['authors']
                if 'license' in header_data and not pom_data.get('licenses'):
                    # Convert header license text to proper format
                    license_infos = self.detect_licenses_from_text(
                        self._format_license_text(header_data['license']),
                        filename=license_filename
                    )
                    if license_infos:
                        # Same source attribution as a declared <licenses> entry,
                        # so a consumer can tell which POM it came from
                        for info in license_infos:
                            info.detection_method = detection_method
                            info.file_path = license_file_path
                        pom_data['licenses'] = license_infos

        except Exception as e:
            print(f"Error parsing POM metadata: {e}")

        return pom_data
    
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

    def _enrich_with_clearlydefined(self, metadata: PackageMetadata) -> None:
        """Enrich metadata using ClearlyDefined API as fallback."""
        try:
            from ..api.clearlydefined import ClearlyDefinedAPI

            cd_api = ClearlyDefinedAPI()

            # Parse namespace from name for Maven packages
            namespace, name = split_namespace(metadata.package_type, metadata.name)

            cd_data = cd_api.get_definition(
                package_type=metadata.package_type,
                namespace=namespace,
                name=name,
                version=metadata.version
            )

            if cd_data:
                # Enrich licensing information if insufficient
                if len(metadata.licenses) < 2:  # Allow additional license sources
                    cd_license = cd_api.extract_license_info(cd_data)
                    if cd_license:
                        from ..core.models import LicenseInfo, LicenseConfidenceLevel
                        license_obj = LicenseInfo(
                            spdx_id=cd_license['spdx_id'],
                            confidence=cd_license['confidence'],
                            confidence_level=LicenseConfidenceLevel.EXACT if cd_license['confidence'] >= 0.95 else LicenseConfidenceLevel.HIGH,
                            detection_method='ClearlyDefined API (online)',
                            file_path='clearlydefined_api'
                        )
                        metadata.licenses.append(license_obj)
                        metadata.provenance['licenses_clearlydefined'] = f"clearlydefined:{cd_api.base_url}"

                # Enrich other metadata if missing
                if not metadata.homepage or metadata.homepage == NO_ASSERTION:
                    project_website = cd_data.get('described', {}).get('projectWebsite')
                    if project_website:
                        metadata.homepage = project_website
                        metadata.provenance['homepage'] = f"clearlydefined:{cd_api.base_url}"

                if not metadata.repository or metadata.repository == NO_ASSERTION:
                    source_location = cd_data.get('described', {}).get('sourceLocation', {})
                    if source_location and source_location.get('url'):
                        metadata.repository = source_location['url']
                        metadata.provenance['repository'] = f"clearlydefined:{cd_api.base_url}"

        except ImportError:
            # ClearlyDefined API not available
            pass
        except Exception as e:
            # Silently fail - ClearlyDefined enrichment is optional
            print(f"ClearlyDefined enrichment failed: {e}")
            pass