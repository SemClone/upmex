"""Debian package extractor."""

import os
import subprocess
import tempfile
import tarfile
import gzip
from pathlib import Path
from typing import Optional, List, Dict, Any
from .base import BaseExtractor
from ..core.models import PackageMetadata, LicenseInfo, NO_ASSERTION


class DebianExtractor(BaseExtractor):
    """Extractor for Debian packages."""
    
    def can_extract(self, package_path: str) -> bool:
        """Check if this is a Debian package."""
        return package_path.endswith('.deb')
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a Debian package.
        
        Args:
            package_path: Path to the DEB file
            
        Returns:
            PackageMetadata object with extracted information
        """
        metadata = PackageMetadata(
            name=NO_ASSERTION,
            version=NO_ASSERTION
        )
        
        # First try to parse filename as fallback
        self._parse_filename(package_path, metadata)
        
        # Try to extract metadata using dpkg command
        if self._has_dpkg_command():
            self._extract_with_dpkg_command(package_path, metadata)
        else:
            # Try to extract from the archive manually
            self._extract_from_archive(package_path, metadata)
        
        # Extract and detect licenses from package contents
        detected_licenses = self.find_and_detect_licenses(archive_path=package_path)
        if detected_licenses:
            # Only update if we didn't get licenses from metadata
            if not metadata.licenses:
                metadata.licenses = detected_licenses
        
        return metadata
    
    def _has_dpkg_command(self) -> bool:
        """Check if dpkg command is available."""
        try:
            subprocess.run(['dpkg', '--version'], capture_output=True, check=False)
            return True
        except FileNotFoundError:
            return False
    
    def _extract_with_dpkg_command(self, package_path: str, metadata: PackageMetadata):
        """Extract metadata using dpkg command."""
        try:
            # Get package information
            result = subprocess.run(
                ['dpkg', '--info', package_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                # Parse the control file output
                in_description = False
                description_lines = []
                
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    
                    if line.startswith('Package:'):
                        metadata.name = line.split(':', 1)[1].strip()
                    elif line.startswith('Version:'):
                        metadata.version = line.split(':', 1)[1].strip()
                    elif line.startswith('Homepage:'):
                        metadata.homepage = line.split(':', 1)[1].strip()
                    elif line.startswith('Maintainer:'):
                        maintainer = line.split(':', 1)[1].strip()
                        author_info = self.parse_author(maintainer)
                        if author_info:
                            metadata.maintainers = [author_info]
                    elif line.startswith('Description:'):
                        in_description = True
                        desc = line.split(':', 1)[1].strip()
                        if desc:
                            description_lines.append(desc)
                    elif in_description:
                        if line.startswith(' '):
                            # Continuation of description
                            description_lines.append(line)
                        else:
                            in_description = False
                    elif line.startswith('Section:'):
                        metadata.section = line.split(':', 1)[1].strip()
                    elif line.startswith('Priority:'):
                        metadata.priority = line.split(':', 1)[1].strip()
                    elif line.startswith('Architecture:'):
                        metadata.architecture = line.split(':', 1)[1].strip()
                
                if description_lines:
                    metadata.description = '\n'.join(description_lines)
            
            # Get dependencies
            self._extract_dependencies_from_dpkg(result.stdout, metadata)
            
            # Try to get copyright/license info
            self._extract_license_from_package(package_path, metadata)
            
        except Exception as e:
            # Silently fall back to archive extraction
            pass
    
    def _extract_dependencies_from_dpkg(self, dpkg_output: str, metadata: PackageMetadata):
        """Extract dependencies from dpkg output."""
        dependencies = []
        
        for line in dpkg_output.split('\n'):
            line = line.strip()
            if line.startswith('Depends:'):
                deps_str = line.split(':', 1)[1].strip()
                dependencies.extend(self._parse_debian_dependencies(deps_str))
        
        if dependencies:
            metadata.dependencies = {'runtime': dependencies}
    
    def _parse_debian_dependencies(self, deps_str: str) -> List[Dict[str, str]]:
        """Parse Debian dependency string."""
        dependencies = []
        
        # Split by comma
        for dep in deps_str.split(','):
            dep = dep.strip()
            if not dep:
                continue
            
            # Handle alternatives (|)
            if '|' in dep:
                # Take the first alternative
                dep = dep.split('|')[0].strip()
            
            # Parse version constraint if present
            if '(' in dep:
                name = dep.split('(')[0].strip()
                version = dep.split('(')[1].rstrip(')').strip()
            else:
                name = dep
                version = NO_ASSERTION
            
            dependencies.append({
                'name': name,
                'version': version
            })
        
        return dependencies
    
    def _extract_from_archive(self, package_path: str, metadata: PackageMetadata):
        """Extract metadata by unpacking the DEB archive."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # DEB files are ar archives containing:
                # - debian-binary (version)
                # - control.tar.gz or control.tar.xz (metadata)
                # - data.tar.gz or data.tar.xz (actual files)
                
                # Extract control.tar.gz
                result = subprocess.run(
                    ['ar', 'x', package_path, 'control.tar.gz'],
                    cwd=temp_dir,
                    capture_output=True,
                    check=False
                )
                
                control_tar = Path(temp_dir) / 'control.tar.gz'
                if not control_tar.exists():
                    # Try control.tar.xz
                    subprocess.run(
                        ['ar', 'x', package_path, 'control.tar.xz'],
                        cwd=temp_dir,
                        capture_output=True,
                        check=False
                    )
                    control_tar = Path(temp_dir) / 'control.tar.xz'
                
                if control_tar.exists():
                    # Extract control file
                    if str(control_tar).endswith('.gz'):
                        with tarfile.open(control_tar, 'r:gz') as tar:
                            tar.extractall(temp_dir)
                    else:
                        with tarfile.open(control_tar, 'r:xz') as tar:
                            tar.extractall(temp_dir)
                    
                    # Read control file
                    control_file = Path(temp_dir) / 'control'
                    if control_file.exists():
                        self._parse_control_file(control_file.read_text(), metadata)
        
        except Exception:
            # Fallback to parsing filename
            self._parse_filename(package_path, metadata)
    
    def _parse_control_file(self, content: str, metadata: PackageMetadata):
        """Parse Debian control file content."""
        in_description = False
        description_lines = []
        
        for line in content.split('\n'):
            if line.startswith('Package:'):
                metadata.name = line.split(':', 1)[1].strip()
            elif line.startswith('Version:'):
                metadata.version = line.split(':', 1)[1].strip()
            elif line.startswith('Homepage:'):
                metadata.homepage = line.split(':', 1)[1].strip()
            elif line.startswith('Maintainer:'):
                maintainer = line.split(':', 1)[1].strip()
                author_info = self.parse_author(maintainer)
                if author_info:
                    metadata.maintainers = [author_info]
            elif line.startswith('Description:'):
                in_description = True
                desc = line.split(':', 1)[1].strip()
                if desc:
                    description_lines.append(desc)
            elif in_description:
                if line.startswith(' '):
                    description_lines.append(line[1:])  # Remove leading space
                else:
                    in_description = False
            elif line.startswith('Depends:'):
                deps_str = line.split(':', 1)[1].strip()
                dependencies = self._parse_debian_dependencies(deps_str)
                if dependencies:
                    metadata.dependencies = {'runtime': dependencies}
        
        if description_lines:
            metadata.description = '\n'.join(description_lines)
    
    def _parse_filename(self, package_path: str, metadata: PackageMetadata):
        """Parse metadata from filename as last resort."""
        path = Path(package_path)
        filename = path.stem
        
        # Typical DEB naming: package_version_architecture
        parts = filename.split('_')
        if parts:
            metadata.name = parts[0]
            if len(parts) > 1:
                # Remove any architecture suffix from version
                version = parts[1]
                # Handle version-release format
                if '-' in version:
                    metadata.version = version
                else:
                    metadata.version = version
            if len(parts) > 2:
                metadata.architecture = parts[2]
    
    def _extract_license_from_package(self, package_path: str, metadata: PackageMetadata):
        """Try to extract license information from the package."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract data.tar.gz to look for copyright file
                subprocess.run(
                    ['ar', 'x', package_path, 'data.tar.gz'],
                    cwd=temp_dir,
                    capture_output=True,
                    check=False
                )
                
                data_tar = Path(temp_dir) / 'data.tar.gz'
                if not data_tar.exists():
                    # Try data.tar.xz
                    subprocess.run(
                        ['ar', 'x', package_path, 'data.tar.xz'],
                        cwd=temp_dir,
                        capture_output=True,
                        check=False
                    )
                    data_tar = Path(temp_dir) / 'data.tar.xz'
                
                if data_tar.exists():
                    # Extract and look for copyright file
                    if str(data_tar).endswith('.gz'):
                        with tarfile.open(data_tar, 'r:gz') as tar:
                            # Look for usr/share/doc/*/copyright
                            for member in tar.getmembers():
                                if 'copyright' in member.name.lower():
                                    file_obj = tar.extractfile(member)
                                    if file_obj:
                                        content = file_obj.read().decode('utf-8', errors='ignore')
                                        license_info = self._parse_copyright_file(content)
                                        if license_info:
                                            metadata.licenses = [license_info]
                                        break
        
        except Exception:
            pass
    
    def _parse_copyright_file(self, content: str) -> Optional[LicenseInfo]:
        """Parse Debian copyright file for license information."""
        license_name = None
        
        for line in content.split('\n'):
            if line.startswith('License:'):
                license_name = line.split(':', 1)[1].strip()
                break
        
        if license_name:
            return LicenseInfo(
                name=license_name,
                spdx_id=license_name,  # Pass raw license string - let OSLiLi normalize
                detection_method="debian_copyright"
            )
        
        return None
    
