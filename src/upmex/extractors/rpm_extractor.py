"""RPM package extractor."""

import os
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from .base import BaseExtractor
from ..core.models import PackageMetadata, LicenseInfo, NO_ASSERTION


class RpmExtractor(BaseExtractor):
    """Extractor for RPM packages."""
    
    def can_extract(self, package_path: str) -> bool:
        """Check if this is an RPM package."""
        return package_path.endswith('.rpm')
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from an RPM package.
        
        Args:
            package_path: Path to the RPM file
            
        Returns:
            PackageMetadata object with extracted information
        """
        metadata = PackageMetadata(
            name=NO_ASSERTION,
            version=NO_ASSERTION
        )
        
        # Try to extract metadata using rpm command
        if self._has_rpm_command():
            self._extract_with_rpm_command(package_path, metadata)
        else:
            # Fallback to extracting the archive and looking for spec file
            self._extract_from_archive(package_path, metadata)
        
        # Extract and detect licenses from package contents
        detected_licenses = self.find_and_detect_licenses(archive_path=package_path)
        if detected_licenses:
            metadata.licenses = detected_licenses
        
        return metadata
    
    def _has_rpm_command(self) -> bool:
        """Check if rpm command is available."""
        try:
            subprocess.run(['rpm', '--version'], capture_output=True, check=False)
            return True
        except FileNotFoundError:
            return False
    
    def _extract_with_rpm_command(self, package_path: str, metadata: PackageMetadata):
        """Extract metadata using rpm command."""
        try:
            # Query package information
            query_format = '%{NAME}\\n%{VERSION}\\n%{RELEASE}\\n%{SUMMARY}\\n%{LICENSE}\\n%{URL}\\n%{VENDOR}\\n%{PACKAGER}'
            result = subprocess.run(
                ['rpm', '-qp', '--queryformat', query_format, package_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 1 and lines[0] and lines[0] != '(none)':
                    metadata.name = lines[0]
                if len(lines) >= 2 and lines[1] and lines[1] != '(none)':
                    metadata.version = lines[1]
                if len(lines) >= 3 and lines[2] and lines[2] != '(none)':
                    # Combine version and release
                    if metadata.version != NO_ASSERTION:
                        metadata.version = f"{metadata.version}-{lines[2]}"
                if len(lines) >= 4 and lines[3] and lines[3] != '(none)':
                    metadata.description = lines[3]
                if len(lines) >= 5 and lines[4] and lines[4] != '(none)':
                    # Parse license
                    license_str = lines[4]
                    metadata.licenses = [
                        LicenseInfo(
                            name=license_str,
                            spdx_id=license_str,  # Pass raw license string - let OSLiLi normalize
                            detection_method="rpm_metadata"
                        )
                    ]
                if len(lines) >= 6 and lines[5] and lines[5] != '(none)':
                    metadata.homepage = lines[5]
                if len(lines) >= 7 and lines[6] and lines[6] != '(none)':
                    metadata.vendor = lines[6]
                if len(lines) >= 8 and lines[7] and lines[7] != '(none)':
                    # Parse packager as author
                    packager = lines[7]
                    author_info = self.parse_author(packager)
                    if author_info:
                        metadata.authors = [author_info]
            
            # Get dependencies
            self._extract_dependencies(package_path, metadata)
            
        except Exception as e:
            # Silently fall back to archive extraction
            pass
    
    def _extract_dependencies(self, package_path: str, metadata: PackageMetadata):
        """Extract dependencies using rpm command."""
        try:
            # Get requires (dependencies)
            result = subprocess.run(
                ['rpm', '-qp', '--requires', package_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                dependencies = []
                for line in result.stdout.strip().split('\n'):
                    if line and not line.startswith('rpmlib('):
                        # Parse dependency line (e.g., "python3 >= 3.6")
                        parts = line.split()
                        if parts:
                            dep_name = parts[0]
                            dep_version = ' '.join(parts[1:]) if len(parts) > 1 else None
                            dependencies.append({
                                'name': dep_name,
                                'version': dep_version or NO_ASSERTION
                            })
                
                if dependencies:
                    metadata.dependencies = {'runtime': dependencies}
            
        except Exception:
            pass
    
    def _extract_from_archive(self, package_path: str, metadata: PackageMetadata):
        """Extract metadata by unpacking the RPM archive."""
        try:
            # RPM files are cpio archives compressed with gzip or xz
            # Try to extract basic info from filename
            path = Path(package_path)
            filename = path.stem
            
            # Parse typical RPM naming: name-version-release.arch.rpm
            parts = filename.rsplit('-', 2)
            if len(parts) >= 2:
                metadata.name = parts[0]
                if len(parts) >= 3:
                    # Split version-release.arch
                    version_parts = parts[1].split('.')
                    metadata.version = version_parts[0]
                    if parts[2]:
                        metadata.version = f"{metadata.version}-{parts[2].split('.')[0]}"
            
            # For more detailed extraction, we would need to:
            # 1. Use rpm2cpio to convert to cpio
            # 2. Extract the cpio archive
            # 3. Look for spec files or metadata
            # This requires additional tools that may not be available
            
        except Exception:
            # Use filename as fallback
            path = Path(package_path)
            metadata.name = path.stem
    
