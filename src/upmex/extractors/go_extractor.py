"""Go module package extractor."""

import zipfile
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .base import BaseExtractor
from ..core.models import NO_ASSERTION, PackageMetadata, PackageType

logger = logging.getLogger(__name__)


class GoExtractor(BaseExtractor):
    """Extract metadata from Go module packages."""

    # __init__ removed - using BaseExtractor

    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a Go module package.
        
        Go modules can be:
        - .zip archives from proxy.golang.org
        - Directories with go.mod files
        - .mod files containing module definitions
        
        The .zip archives from proxy.golang.org have a specific structure:
        - module@version/ root directory
        - go.mod file with module definition
        - Source code files
        - LICENSE files
        """
        package_path = Path(package_path)
        metadata = PackageMetadata(
            name=NO_ASSERTION,
            version=NO_ASSERTION,
            package_type=PackageType.GO_MODULE,
            description=NO_ASSERTION,
            homepage=NO_ASSERTION,
            repository=NO_ASSERTION
        )
        metadata.dependencies = {'require': [], 'indirect': [], 'replace': []}

        try:
            if package_path.suffix == '.zip':
                # Handle zip archive from proxy.golang.org
                with zipfile.ZipFile(package_path, 'r') as zip_file:
                    go_mod_content = None
                    license_files = []
                    readme_content = None
                    
                    # Find go.mod and other files
                    for file_info in zip_file.namelist():
                        if file_info.endswith('go.mod'):
                            go_mod_content = zip_file.read(file_info).decode('utf-8')
                        elif 'LICENSE' in file_info.upper() or 'LICENCE' in file_info.upper():
                            license_files.append(file_info)
                        elif file_info.upper().endswith('README.MD') or file_info.upper().endswith('README'):
                            readme_content = zip_file.read(file_info).decode('utf-8', errors='ignore')
                    
                    if go_mod_content:
                        self._parse_go_mod(go_mod_content, metadata)
                    
                    # Extract description from README if available
                    if readme_content and metadata.description == NO_ASSERTION:
                        # Try to extract first paragraph or header description
                        lines = readme_content.split('\n')
                        for i, line in enumerate(lines):
                            if line.strip() and not line.startswith('#'):
                                metadata.description = line.strip()
                                break
                    
                    # Extract license information
                    if license_files:
                        for license_file in license_files:
                            license_content = zip_file.read(license_file).decode('utf-8', errors='ignore')
                            # Only format if it's a short identifier (not full license text)
                            if len(license_content) < 20 and ':' not in license_content:
                                formatted_text = f"License: {license_content}"
                            else:
                                formatted_text = license_content
                            license_infos = self.detect_licenses_from_text(
                                formatted_text,
                                filename=license_file
                            )
                            if license_infos:
                                metadata.licenses.extend(license_infos)
                                break
            
            elif package_path.suffix == '.mod' or package_path.name == 'go.mod':
                # Handle standalone go.mod file
                go_mod_content = package_path.read_text(encoding='utf-8')
                self._parse_go_mod(go_mod_content, metadata)
                
                # Check for LICENSE in same directory
                parent_dir = package_path.parent
                for license_name in ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'LICENCE']:
                    license_path = parent_dir / license_name
                    if license_path.exists():
                        license_content = license_path.read_text(encoding='utf-8', errors='ignore')
                        # Only format if it's a short identifier (not full license text)
                        if len(license_content) < 20 and ':' not in license_content:
                            formatted_text = f"License: {license_content}"
                        else:
                            formatted_text = license_content
                        license_infos = self.detect_licenses_from_text(
                            formatted_text,
                            filename=license_name
                        )
                        if license_infos:
                            metadata.licenses.extend(license_infos)
                        break

        except Exception as e:
            logger.error(f"Error extracting Go module metadata: {e}")
            raise
        
        # Extract copyright information
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with zipfile.ZipFile(str(package_path), 'r') as zf:
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

        return metadata

    def _parse_go_mod(self, content: str, metadata: PackageMetadata) -> None:
        """Parse go.mod file content and populate metadata.
        
        Args:
            content: go.mod file content
            metadata: PackageMetadata object to populate
        """
        lines = content.split('\n')
        in_require_block = False
        in_replace_block = False
        in_exclude_block = False
        
        for line in lines:
            line = line.strip()
            
            # Skip comments and empty lines
            if line.startswith('//') or not line:
                continue
            
            # Parse module declaration
            if line.startswith('module '):
                module_name = line[7:].strip()
                metadata.name = module_name
                # Infer repository URL from module name
                if metadata.repository == NO_ASSERTION:
                    metadata.repository = self._infer_repository_url(module_name)
                    if metadata.homepage == NO_ASSERTION:
                        metadata.homepage = metadata.repository
            
            # Parse go version
            elif line.startswith('go '):
                go_version = line[3:].strip()
                metadata.classifiers.append(f"Go :: {go_version}")
            
            # Handle require block
            elif line == 'require (':
                in_require_block = True
                in_replace_block = False
                in_exclude_block = False
            elif line == 'replace (':
                in_replace_block = True
                in_require_block = False
                in_exclude_block = False
            elif line == 'exclude (':
                in_exclude_block = True
                in_require_block = False
                in_replace_block = False
            elif line == ')':
                in_require_block = False
                in_replace_block = False
                in_exclude_block = False
            
            # Parse single-line require
            elif line.startswith('require ') and '(' not in line:
                dep_str = line[8:].strip()
                self._parse_dependency(dep_str, metadata, 'require')
            
            # Parse single-line replace
            elif line.startswith('replace ') and '(' not in line:
                dep_str = line[8:].strip()
                self._parse_replace(dep_str, metadata)
            
            # Parse dependencies in blocks
            elif in_require_block and line and not line.startswith('//'):
                self._parse_dependency(line, metadata, 'require')
            elif in_replace_block and line and not line.startswith('//'):
                self._parse_replace(line, metadata)
        
        # Extract version from module path if it includes version
        if metadata.name != NO_ASSERTION and '/v' in metadata.name:
            # Handle modules like github.com/user/project/v2
            parts = metadata.name.split('/')
            for part in parts:
                if part.startswith('v') and part[1:].replace('.', '').isdigit():
                    if metadata.version == NO_ASSERTION:
                        metadata.version = part

    def _parse_dependency(self, dep_line: str, metadata: PackageMetadata, dep_type: str) -> None:
        """Parse a dependency line from go.mod.
        
        Args:
            dep_line: Dependency line to parse
            metadata: PackageMetadata object to update
            dep_type: Type of dependency ('require')
        """
        # Remove inline comments
        if '//' in dep_line:
            comment_start = dep_line.index('//')
            comment = dep_line[comment_start+2:].strip()
            dep_line = dep_line[:comment_start].strip()
            
            # Check if it's an indirect dependency
            if comment == 'indirect':
                dep_type = 'indirect'
        
        # Parse module and version
        parts = dep_line.split()
        if len(parts) >= 2:
            module = parts[0]
            version = parts[1]
            
            if dep_type == 'indirect':
                metadata.dependencies['indirect'].append(f"{module} {version}")
            else:
                metadata.dependencies['require'].append(f"{module} {version}")

    def _parse_replace(self, replace_line: str, metadata: PackageMetadata) -> None:
        """Parse a replace directive from go.mod.
        
        Args:
            replace_line: Replace line to parse
            metadata: PackageMetadata object to update
        """
        # Remove inline comments
        if '//' in replace_line:
            replace_line = replace_line[:replace_line.index('//')].strip()
        
        # Parse replace directive (old => new)
        if '=>' in replace_line:
            parts = replace_line.split('=>')
            if len(parts) == 2:
                old_module = parts[0].strip()
                new_module = parts[1].strip()
                metadata.dependencies['replace'].append(f"{old_module} => {new_module}")

    def _infer_repository_url(self, module_name: str) -> str:
        """Infer repository URL from Go module name.
        
        Args:
            module_name: Go module name
            
        Returns:
            Inferred repository URL or NO_ASSERTION
        """
        # Remove version suffix if present
        if '/v' in module_name:
            # Find the last /vN pattern
            parts = module_name.split('/')
            cleaned_parts = []
            for part in parts:
                if part.startswith('v') and part[1:].replace('.', '').isdigit():
                    break
                cleaned_parts.append(part)
            module_name = '/'.join(cleaned_parts)
        
        # Common Git hosting platforms
        if module_name.startswith('github.com/'):
            return f"https://{module_name}"
        elif module_name.startswith('gitlab.com/'):
            return f"https://{module_name}"
        elif module_name.startswith('bitbucket.org/'):
            return f"https://{module_name}"
        elif module_name.startswith('gitea.com/'):
            return f"https://{module_name}"
        elif module_name.startswith('sr.ht/'):
            return f"https://{module_name}"
        elif module_name.startswith('gopkg.in/'):
            # gopkg.in URLs map to GitHub
            # e.g., gopkg.in/yaml.v2 -> github.com/go-yaml/yaml
            parts = module_name[9:].split('.')
            if parts:
                return f"https://github.com/go-{parts[0]}/{parts[0]}"
        elif '.' in module_name and '/' in module_name:
            # Custom domains might be Git repositories
            return f"https://{module_name}"
        
        return NO_ASSERTION

    def can_extract(self, package_path: str) -> bool:
        """Check if this extractor can handle the package."""
        path = Path(package_path)
        
        # Check for .mod files or go.mod
        if path.suffix == '.mod' or path.name == 'go.mod':
            return True
        
        # Check for .zip files that might be Go modules
        if path.suffix == '.zip':
            try:
                with zipfile.ZipFile(package_path, 'r') as zip_file:
                    for file_info in zip_file.namelist():
                        if file_info.endswith('go.mod'):
                            return True
            except:
                pass
        
        return False

    def detect_package_type(self, package_path: Path) -> Optional[str]:
        """Detect if the package is a Go module."""
        if package_path.suffix == '.mod' or package_path.name == 'go.mod':
            return 'go_module'
        
        # Check if it's a zip with go.mod
        if package_path.suffix == '.zip':
            try:
                with zipfile.ZipFile(str(package_path), 'r') as zip_file:
                    for file_info in zip_file.namelist():
                        if file_info.endswith('go.mod'):
                            return 'go_module'
            except:
                pass
        
        return None