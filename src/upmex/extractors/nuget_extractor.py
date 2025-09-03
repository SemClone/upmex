"""NuGet package extractor."""

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .base import BaseExtractor
from ..core.models import NO_ASSERTION, PackageMetadata, PackageType

logger = logging.getLogger(__name__)


class NuGetExtractor(BaseExtractor):
    """Extract metadata from NuGet packages."""

    # __init__ removed - using BaseExtractor

    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a NuGet package.
        
        NuGet packages (.nupkg) are ZIP archives containing:
        - .nuspec file with package metadata (XML format)
        - lib/ folder with compiled assemblies
        - content/ folder with content files
        - tools/ folder with PowerShell scripts
        """
        package_path = Path(package_path)
        metadata = PackageMetadata(
            name=NO_ASSERTION,
            version=NO_ASSERTION,
            package_type=PackageType.NUGET,
            description=NO_ASSERTION,
            homepage=NO_ASSERTION,
            repository=NO_ASSERTION
        )
        metadata.dependencies = {'runtime': [], 'development': []}

        try:
            with zipfile.ZipFile(package_path, 'r') as zip_file:
                nuspec_file = None
                license_files = []
                
                # Find .nuspec file and LICENSE files
                for file_info in zip_file.namelist():
                    if file_info.endswith('.nuspec'):
                        nuspec_file = file_info
                    elif 'LICENSE' in file_info.upper() or 'LICENCE' in file_info.upper():
                        license_files.append(file_info)
                
                if nuspec_file:
                    # Parse .nuspec XML file
                    nuspec_content = zip_file.read(nuspec_file)
                    self._parse_nuspec(nuspec_content, metadata)
                
                # Try to detect license from LICENSE files if not found in nuspec
                if not metadata.licenses and license_files:
                    for license_file in license_files:
                        license_content = zip_file.read(license_file).decode('utf-8', errors='ignore')
                        license_info = self.detect_licenses_from_text(
                            license_content,
                            filename=license_file
                        )
                        if license_info:
                            from ..core.models import LicenseInfo, LicenseConfidenceLevel
                            metadata.licenses.append(LicenseInfo(
                                spdx_id=license_info.spdx_id,
                                confidence=license_info.confidence,
                                confidence_level=LicenseConfidenceLevel(license_info.confidence_level),
                                detection_method=license_info.detection_method,
                                file_path=license_info.file_path
                            ))
                            break

        except Exception as e:
            logger.error(f"Error extracting NuGet metadata: {e}")
            raise

        return metadata

    def _parse_nuspec(self, nuspec_content: bytes, metadata: PackageMetadata) -> None:
        """Parse .nuspec XML content and populate metadata.
        
        Args:
            nuspec_content: XML content of .nuspec file
            metadata: PackageMetadata object to populate
        """
        try:
            root = ET.fromstring(nuspec_content)
            
            # Handle XML namespaces
            namespaces = {'ns': root.tag.split('}')[0][1:]} if '}' in root.tag else {}
            ns_prefix = 'ns:' if namespaces else ''
            
            # Find metadata element
            metadata_elem = root.find(f'{ns_prefix}metadata', namespaces)
            if metadata_elem is None:
                metadata_elem = root.find('metadata')
            
            if metadata_elem is not None:
                # Extract basic metadata
                self._extract_text(metadata_elem, 'id', metadata, 'name', namespaces)
                self._extract_text(metadata_elem, 'version', metadata, 'version', namespaces)
                self._extract_text(metadata_elem, 'description', metadata, 'description', namespaces)
                self._extract_text(metadata_elem, 'projectUrl', metadata, 'homepage', namespaces)
                
                # Extract repository information
                repository_elem = metadata_elem.find(f'{ns_prefix}repository', namespaces)
                if repository_elem is None:
                    repository_elem = metadata_elem.find('repository')
                
                if repository_elem is not None:
                    repo_url = repository_elem.get('url')
                    if repo_url:
                        metadata.repository = repo_url
                
                # If no repository element, try repositoryUrl
                if metadata.repository == NO_ASSERTION:
                    self._extract_text(metadata_elem, 'repositoryUrl', metadata, 'repository', namespaces)
                
                # Extract authors
                authors_text = self._get_text(metadata_elem, 'authors', namespaces)
                if authors_text:
                    # Authors are comma-separated
                    authors = [a.strip() for a in authors_text.split(',')]
                    for author in authors:
                        if author:
                            metadata.authors.append({
                                'name': author,
                                'email': NO_ASSERTION
                            })
                
                # Extract owners (similar to maintainers)
                owners_text = self._get_text(metadata_elem, 'owners', namespaces)
                if owners_text:
                    owners = [o.strip() for o in owners_text.split(',')]
                    for owner in owners:
                        if owner:
                            metadata.maintainers.append({
                                'name': owner,
                                'email': NO_ASSERTION
                            })
                
                # Extract tags (keywords)
                tags_text = self._get_text(metadata_elem, 'tags', namespaces)
                if tags_text:
                    metadata.keywords = [t.strip() for t in tags_text.split() if t.strip()]
                
                # Extract license information
                # Modern NuGet uses license element
                license_elem = metadata_elem.find(f'{ns_prefix}license', namespaces)
                if license_elem is None:
                    license_elem = metadata_elem.find('license')
                
                if license_elem is not None:
                    license_type = license_elem.get('type', 'expression')
                    if license_type == 'expression':
                        # SPDX expression
                        license_text = license_elem.text
                        if license_text:
                            # Format license text for better oslili detection
                            if len(license_text) < 20 and ':' not in license_text:
                                formatted_text = f"License: {license_text}"
                            else:
                                formatted_text = license_text
                            license_infos = self.detect_licenses_from_text(
                                formatted_text,
                                filename='.nuspec'
                            )
                            if license_infos:
                                metadata.licenses.extend(license_infos)
                    elif license_type == 'file':
                        # License is in a file
                        license_file = license_elem.text
                        if license_file:
                            metadata.raw_metadata['license_file'] = license_file
                
                # Fallback to licenseUrl for older packages
                if not metadata.licenses:
                    license_url = self._get_text(metadata_elem, 'licenseUrl', namespaces)
                    if license_url:
                        # Try to detect license from URL
                        if 'opensource.org/licenses/' in license_url.lower():
                            # Extract license ID from URL
                            parts = license_url.split('/')
                            if parts:
                                license_id = parts[-1].upper()
                                # Format license text for better oslili detection
                                if len(license_id) < 20 and ':' not in license_id:
                                    formatted_text = f"License: {license_id}"
                                else:
                                    formatted_text = license_id
                                license_info = self.detect_licenses_from_text(
                                    formatted_text,
                                    filename='licenseUrl'
                                )
                                if license_info:
                                    from ..core.models import LicenseInfo, LicenseConfidenceLevel
                                    metadata.licenses.append(LicenseInfo(
                                        spdx_id=license_info.spdx_id,
                                        confidence=license_info.confidence,
                                        confidence_level=LicenseConfidenceLevel(license_info.confidence_level),
                                        detection_method=license_info.detection_method,
                                        file_path='licenseUrl'
                                    ))
                        metadata.raw_metadata['license_url'] = license_url
                
                # Extract dependencies
                dependencies_elem = metadata_elem.find(f'{ns_prefix}dependencies', namespaces)
                if dependencies_elem is None:
                    dependencies_elem = metadata_elem.find('dependencies')
                
                if dependencies_elem is not None:
                    self._parse_dependencies(dependencies_elem, metadata, namespaces)
                
                # Extract framework assemblies
                framework_assemblies = metadata_elem.find(f'{ns_prefix}frameworkAssemblies', namespaces)
                if framework_assemblies is None:
                    framework_assemblies = metadata_elem.find('frameworkAssemblies')
                
                if framework_assemblies is not None:
                    for assembly in framework_assemblies:
                        assembly_name = assembly.get('assemblyName')
                        target_framework = assembly.get('targetFramework', 'any')
                        if assembly_name:
                            metadata.dependencies['runtime'].append(f"{assembly_name} (framework: {target_framework})")
                
                # Extract minimum client version
                min_client = self._get_text(metadata_elem, 'minClientVersion', namespaces)
                if min_client:
                    metadata.classifiers.append(f"NuGet Client :: >= {min_client}")
                
                # Extract release notes
                release_notes = self._get_text(metadata_elem, 'releaseNotes', namespaces)
                if release_notes:
                    metadata.raw_metadata['release_notes'] = release_notes
                
                # Extract icon URL
                icon_url = self._get_text(metadata_elem, 'iconUrl', namespaces)
                if icon_url:
                    metadata.raw_metadata['icon_url'] = icon_url
                
                # Extract copyright
                copyright_text = self._get_text(metadata_elem, 'copyright', namespaces)
                if copyright_text:
                    metadata.raw_metadata['copyright'] = copyright_text
                
                # Require license acceptance
                require_license = self._get_text(metadata_elem, 'requireLicenseAcceptance', namespaces)
                if require_license and require_license.lower() == 'true':
                    metadata.raw_metadata['require_license_acceptance'] = True
                
        except ET.ParseError as e:
            logger.error(f"Error parsing nuspec XML: {e}")
            raise

    def _parse_dependencies(self, dependencies_elem, metadata: PackageMetadata, namespaces: dict) -> None:
        """Parse dependencies from nuspec.
        
        Args:
            dependencies_elem: XML element containing dependencies
            metadata: PackageMetadata object to update
            namespaces: XML namespaces
        """
        ns_prefix = 'ns:' if namespaces else ''
        
        # Check for grouped dependencies (by target framework)
        groups = dependencies_elem.findall(f'{ns_prefix}group', namespaces)
        if not groups:
            groups = dependencies_elem.findall('group')
        
        if groups:
            # Dependencies grouped by target framework
            for group in groups:
                target_framework = group.get('targetFramework', 'any')
                
                deps = group.findall(f'{ns_prefix}dependency', namespaces)
                if not deps:
                    deps = group.findall('dependency')
                
                for dep in deps:
                    dep_id = dep.get('id')
                    dep_version = dep.get('version', '*')
                    dep_include = dep.get('include', 'All')
                    dep_exclude = dep.get('exclude', 'None')
                    
                    if dep_id:
                        dep_str = f"{dep_id} {dep_version}"
                        if target_framework != 'any':
                            dep_str += f" (framework: {target_framework})"
                        if dep_include != 'All':
                            dep_str += f" (include: {dep_include})"
                        if dep_exclude != 'None':
                            dep_str += f" (exclude: {dep_exclude})"
                        
                        # Determine if it's a development dependency
                        if dep_include in ['Build', 'Compile', 'Analyzers'] or 'Test' in dep_id:
                            metadata.dependencies['development'].append(dep_str)
                        else:
                            metadata.dependencies['runtime'].append(dep_str)
        else:
            # Flat list of dependencies (older format)
            deps = dependencies_elem.findall(f'{ns_prefix}dependency', namespaces)
            if not deps:
                deps = dependencies_elem.findall('dependency')
            
            for dep in deps:
                dep_id = dep.get('id')
                dep_version = dep.get('version', '*')
                
                if dep_id:
                    dep_str = f"{dep_id} {dep_version}"
                    # Simple heuristic for development dependencies
                    if 'Test' in dep_id or 'Mock' in dep_id or 'Analyzer' in dep_id:
                        metadata.dependencies['development'].append(dep_str)
                    else:
                        metadata.dependencies['runtime'].append(dep_str)

    def _extract_text(self, parent, tag: str, metadata: PackageMetadata, attr: str, namespaces: dict) -> None:
        """Extract text from XML element and set metadata attribute.
        
        Args:
            parent: Parent XML element
            tag: Tag name to find
            metadata: PackageMetadata object
            attr: Attribute name to set
            namespaces: XML namespaces
        """
        text = self._get_text(parent, tag, namespaces)
        if text:
            setattr(metadata, attr, text)

    def _get_text(self, parent, tag: str, namespaces: dict) -> Optional[str]:
        """Get text content from XML element.
        
        Args:
            parent: Parent XML element
            tag: Tag name to find
            namespaces: XML namespaces
            
        Returns:
            Text content or None
        """
        ns_prefix = 'ns:' if namespaces else ''
        elem = parent.find(f'{ns_prefix}{tag}', namespaces)
        if elem is None:
            elem = parent.find(tag)
        
        if elem is not None and elem.text:
            return elem.text.strip()
        return None

    def can_extract(self, package_path: str) -> bool:
        """Check if this extractor can handle the package."""
        path = Path(package_path)
        
        # Check for .nupkg extension
        if path.suffix == '.nupkg':
            return True
        
        # Check if it's a ZIP that contains a .nuspec file
        if path.suffix == '.zip':
            try:
                with zipfile.ZipFile(package_path, 'r') as zip_file:
                    for file_info in zip_file.namelist():
                        if file_info.endswith('.nuspec'):
                            return True
            except:
                pass
        
        return False

    def detect_package_type(self, package_path: Path) -> Optional[str]:
        """Detect if the package is a NuGet package."""
        if package_path.suffix == '.nupkg':
            return 'nuget'
        
        # Check if it's a ZIP with .nuspec
        if package_path.suffix == '.zip':
            try:
                with zipfile.ZipFile(str(package_path), 'r') as zip_file:
                    for file_info in zip_file.namelist():
                        if file_info.endswith('.nuspec'):
                            return 'nuget'
            except:
                pass
        
        return None