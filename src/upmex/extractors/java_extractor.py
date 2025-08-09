"""Java/Maven package extractor."""

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, Optional
from .base import BaseExtractor
from ..core.models import PackageMetadata, PackageType


class JavaExtractor(BaseExtractor):
    """Extractor for Java JAR and Maven packages."""
    
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
                    
                    # Extract basic info
                    group_id = root.findtext('.//maven:groupId', '', ns) or root.findtext('.//groupId', '')
                    artifact_id = root.findtext('.//maven:artifactId', '', ns) or root.findtext('.//artifactId', '')
                    
                    if group_id and artifact_id:
                        metadata.name = f"{group_id}:{artifact_id}"
                    elif artifact_id:
                        metadata.name = artifact_id
                    
                    metadata.version = root.findtext('.//maven:version', None, ns) or root.findtext('.//version')
                    metadata.description = root.findtext('.//maven:description', None, ns) or root.findtext('.//description')
                    metadata.homepage = root.findtext('.//maven:url', None, ns) or root.findtext('.//url')
                    
                    # Extract dependencies
                    dependencies = []
                    for dep in root.findall('.//maven:dependency', ns) or root.findall('.//dependency'):
                        dep_group = dep.findtext('maven:groupId', '', ns) or dep.findtext('groupId', '')
                        dep_artifact = dep.findtext('maven:artifactId', '', ns) or dep.findtext('artifactId', '')
                        if dep_group and dep_artifact:
                            dependencies.append(f"{dep_group}:{dep_artifact}")
                    
                    if dependencies:
                        metadata.dependencies['runtime'] = dependencies
                    
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