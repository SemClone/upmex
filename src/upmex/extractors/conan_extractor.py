"""Conan C/C++ package extractor."""

import os
import re
import tarfile
import tempfile
import ast
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..core.models import PackageMetadata, PackageType, LicenseInfo, NO_ASSERTION


class ConanExtractor:
    """Extractor for Conan C/C++ packages."""
    
    def __init__(self):
        """Initialize the Conan extractor."""
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a Conan package.
        
        Args:
            package_path: Path to the Conan package file or conanfile.py
            
        Returns:
            PackageMetadata object with extracted information
        """
        package_path = str(package_path)
        
        # Check if it's a conanfile.py directly
        if package_path.endswith('conanfile.py'):
            return self._extract_from_conanfile_py(package_path)
        
        # Check if it's a conanfile.txt directly
        if package_path.endswith('conanfile.txt'):
            return self._extract_from_conanfile_txt(package_path)
        
        # Otherwise, it should be a package archive
        return self._extract_from_archive(package_path)
    
    def _extract_from_archive(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a Conan package archive.
        
        Args:
            package_path: Path to the .tgz package
            
        Returns:
            PackageMetadata object
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract the tarball
            with tarfile.open(package_path, 'r:gz') as tar:
                tar.extractall(temp_dir)
            
            # Look for conanfile.py first
            conanfile_py = os.path.join(temp_dir, 'conanfile.py')
            if os.path.exists(conanfile_py):
                return self._extract_from_conanfile_py(conanfile_py)
            
            # Look for conaninfo.txt
            conaninfo_txt = os.path.join(temp_dir, 'conaninfo.txt')
            if os.path.exists(conaninfo_txt):
                metadata = self._extract_from_conaninfo_txt(conaninfo_txt)
                
                # Also check for conanfile.txt for additional info
                conanfile_txt = os.path.join(temp_dir, 'conanfile.txt')
                if os.path.exists(conanfile_txt):
                    self._enrich_from_conanfile_txt(metadata, conanfile_txt)
                
                return metadata
            
            # Look for conanfile.txt
            conanfile_txt = os.path.join(temp_dir, 'conanfile.txt')
            if os.path.exists(conanfile_txt):
                return self._extract_from_conanfile_txt(conanfile_txt)
            
            # If no metadata files found, return minimal metadata
            return PackageMetadata(
                name=Path(package_path).stem,
                version=NO_ASSERTION,
                package_type=PackageType.CONAN
            )
    
    def _extract_from_conanfile_py(self, conanfile_path: str) -> PackageMetadata:
        """Extract metadata from conanfile.py.
        
        Args:
            conanfile_path: Path to conanfile.py
            
        Returns:
            PackageMetadata object
        """
        with open(conanfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the Python file
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # If parsing fails, try regex-based extraction
            return self._extract_from_conanfile_py_regex(content)
        
        # Extract metadata from AST
        metadata_dict = self._extract_from_ast(tree, content)
        
        # Create PackageMetadata object
        metadata = PackageMetadata(
            name=metadata_dict.get('name', NO_ASSERTION),
            version=metadata_dict.get('version', NO_ASSERTION),
            package_type=PackageType.CONAN
        )
        
        # Set description
        metadata.description = metadata_dict.get('description', NO_ASSERTION)
        
        # Set homepage and repository
        metadata.homepage = metadata_dict.get('homepage', metadata_dict.get('url', NO_ASSERTION))
        metadata.repository = metadata_dict.get('url', NO_ASSERTION)
        
        # Extract author
        author = metadata_dict.get('author')
        if author:
            metadata.authors = [self._parse_author(author)]
        
        # Extract license
        license_str = metadata_dict.get('license')
        if license_str:
            metadata.licenses = self._parse_licenses(license_str)
        
        # Extract topics as keywords
        topics = metadata_dict.get('topics', [])
        if isinstance(topics, (list, tuple)):
            metadata.keywords = list(topics)
        
        # Extract dependencies
        metadata.dependencies = self._extract_dependencies_from_dict(metadata_dict)
        
        return metadata
    
    def _extract_from_ast(self, tree: ast.AST, content: str) -> Dict[str, Any]:
        """Extract metadata from Python AST.
        
        Args:
            tree: Python AST tree
            content: Original file content
            
        Returns:
            Dictionary with metadata
        """
        metadata = {}
        
        # Find the ConanFile class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Look for class that inherits from ConanFile
                for attr in node.body:
                    if isinstance(attr, ast.Assign):
                        for target in attr.targets:
                            if isinstance(target, ast.Name):
                                name = target.id
                                value = self._extract_value(attr.value, content)
                                if name in ['name', 'version', 'license', 'author', 
                                          'url', 'homepage', 'description', 'topics',
                                          'requires', 'tool_requires', 'test_requires']:
                                    metadata[name] = value
        
        return metadata
    
    def _extract_value(self, node: ast.AST, content: str) -> Any:
        """Extract value from AST node.
        
        Args:
            node: AST node
            content: Original file content
            
        Returns:
            Extracted value
        """
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.List):
            return [self._extract_value(elt, content) for elt in node.elts]
        elif isinstance(node, ast.Tuple):
            return tuple(self._extract_value(elt, content) for elt in node.elts)
        elif isinstance(node, ast.Name):
            return node.id
        else:
            # For complex expressions, extract from source
            if hasattr(node, 'lineno') and hasattr(node, 'col_offset'):
                lines = content.split('\n')
                if node.lineno - 1 < len(lines):
                    line = lines[node.lineno - 1]
                    # Try to extract the value after '='
                    if '=' in line:
                        value_str = line.split('=', 1)[1].strip()
                        # Remove quotes and clean up
                        value_str = value_str.strip('"\'')
                        return value_str
        return None
    
    def _extract_from_conanfile_py_regex(self, content: str) -> PackageMetadata:
        """Extract metadata from conanfile.py using regex.
        
        Args:
            content: File content
            
        Returns:
            PackageMetadata object
        """
        metadata = PackageMetadata(
            name=NO_ASSERTION,
            version=NO_ASSERTION,
            package_type=PackageType.CONAN
        )
        
        # Extract name
        name_match = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if name_match:
            metadata.name = name_match.group(1)
        
        # Extract version
        version_match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if version_match:
            metadata.version = version_match.group(1)
        
        # Extract description
        desc_match = re.search(r'^\s*description\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if not desc_match:
            # Try multiline description
            desc_match = re.search(r'^\s*description\s*=\s*"""(.*?)"""', content, re.MULTILINE | re.DOTALL)
        if desc_match:
            metadata.description = desc_match.group(1).strip()
        
        # Extract license
        license_match = re.search(r'^\s*license\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if license_match:
            metadata.licenses = self._parse_licenses(license_match.group(1))
        
        # Extract author
        author_match = re.search(r'^\s*author\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if author_match:
            metadata.authors = [self._parse_author(author_match.group(1))]
        
        # Extract URL
        url_match = re.search(r'^\s*url\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if url_match:
            metadata.repository = url_match.group(1)
        
        # Extract homepage
        homepage_match = re.search(r'^\s*homepage\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if homepage_match:
            metadata.homepage = homepage_match.group(1)
        else:
            metadata.homepage = metadata.repository
        
        # Extract dependencies
        metadata.dependencies = self._extract_dependencies_from_content(content)
        
        return metadata
    
    def _extract_from_conaninfo_txt(self, conaninfo_path: str) -> PackageMetadata:
        """Extract metadata from conaninfo.txt.
        
        Args:
            conaninfo_path: Path to conaninfo.txt
            
        Returns:
            PackageMetadata object
        """
        with open(conaninfo_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse INI-style sections
        sections = self._parse_ini_sections(content)
        
        # Extract package name and version from requires
        name = NO_ASSERTION
        version = NO_ASSERTION
        
        # Try to extract from full_requires
        full_requires = sections.get('full_requires', [])
        if full_requires and full_requires[0]:
            # Format: package/version@user/channel: hash
            match = re.match(r'([^/]+)/([^@]+)', full_requires[0])
            if match:
                name = match.group(1)
                version = match.group(2)
        
        metadata = PackageMetadata(
            name=name,
            version=version,
            package_type=PackageType.CONAN
        )
        
        # Extract dependencies
        requires = sections.get('requires', [])
        metadata.dependencies = []
        for req in requires:
            if '/' in req:
                dep_name, dep_version = req.split('/', 1)
                dep_version = dep_version.split('@')[0] if '@' in dep_version else dep_version
                metadata.dependencies.append({
                    'name': dep_name,
                    'version': dep_version
                })
        
        # Extract settings as keywords
        settings = sections.get('settings', [])
        if settings:
            metadata.keywords = settings
        
        return metadata
    
    def _extract_from_conanfile_txt(self, conanfile_path: str) -> PackageMetadata:
        """Extract metadata from conanfile.txt.
        
        Args:
            conanfile_path: Path to conanfile.txt
            
        Returns:
            PackageMetadata object
        """
        with open(conanfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse INI-style sections
        sections = self._parse_ini_sections(content)
        
        # Extract name from filename or path
        name = Path(conanfile_path).parent.name
        if name in ['.', '']:
            name = NO_ASSERTION
        
        metadata = PackageMetadata(
            name=name,
            version=NO_ASSERTION,
            package_type=PackageType.CONAN
        )
        
        # Extract dependencies from requires section
        requires = sections.get('requires', [])
        metadata.dependencies = []
        for req in requires:
            if '/' in req:
                dep_name, dep_version = req.split('/', 1)
                dep_version = dep_version.split('@')[0] if '@' in dep_version else dep_version
                metadata.dependencies.append({
                    'name': dep_name,
                    'version': dep_version
                })
            else:
                metadata.dependencies.append({
                    'name': req,
                    'version': '*'
                })
        
        # Add tool_requires as build dependencies
        tool_requires = sections.get('tool_requires', [])
        for req in tool_requires:
            if '/' in req:
                dep_name, dep_version = req.split('/', 1)
                dep_version = dep_version.split('@')[0] if '@' in dep_version else dep_version
                metadata.dependencies.append({
                    'name': dep_name,
                    'version': dep_version,
                    'type': 'build'
                })
        
        return metadata
    
    def _enrich_from_conanfile_txt(self, metadata: PackageMetadata, conanfile_path: str):
        """Enrich metadata from conanfile.txt.
        
        Args:
            metadata: Existing metadata to enrich
            conanfile_path: Path to conanfile.txt
        """
        with open(conanfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        sections = self._parse_ini_sections(content)
        
        # Add any missing dependencies
        if not metadata.dependencies:
            metadata.dependencies = []
        
        existing_deps = {d['name'] for d in metadata.dependencies}
        
        requires = sections.get('requires', [])
        for req in requires:
            if '/' in req:
                dep_name, dep_version = req.split('/', 1)
                if dep_name not in existing_deps:
                    metadata.dependencies.append({
                        'name': dep_name,
                        'version': dep_version.split('@')[0] if '@' in dep_version else dep_version
                    })
    
    def _parse_ini_sections(self, content: str) -> Dict[str, List[str]]:
        """Parse INI-style sections from content.
        
        Args:
            content: File content
            
        Returns:
            Dictionary of section name to list of lines
        """
        sections = {}
        current_section = None
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Check for section header
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                sections[current_section] = []
            elif current_section is not None:
                sections[current_section].append(line)
        
        return sections
    
    def _parse_author(self, author_str: str) -> Dict[str, str]:
        """Parse author string.
        
        Args:
            author_str: Author string
            
        Returns:
            Dictionary with name and email
        """
        author_dict = {}
        
        # Parse "Name (email)" or "Name <email>" format
        email_match = re.search(r'[\(<]([^)>]+@[^)>]+)[\)>]', author_str)
        if email_match:
            email = email_match.group(1)
            name = author_str[:author_str.index(email_match.group(0))].strip()
            
            if name:
                author_dict['name'] = name
            if email:
                author_dict['email'] = email
        else:
            # Just a name
            author_dict['name'] = author_str.strip()
        
        return author_dict
    
    def _parse_licenses(self, license_str: str) -> List[LicenseInfo]:
        """Parse license string.
        
        Args:
            license_str: License string (may be comma-separated)
            
        Returns:
            List of LicenseInfo objects
        """
        licenses = []
        
        # Split by comma for multiple licenses
        license_parts = [l.strip() for l in license_str.split(',')]
        
        for license_part in license_parts:
            if license_part:
                license_info = LicenseInfo(
                    spdx_id=license_part,  # Pass raw license string - let OSLiLi normalize
                    name=license_part,
                    detection_method='metadata',
                    confidence=1.0
                )
                licenses.append(license_info)
        
        return licenses
    
    
    def _extract_dependencies_from_dict(self, metadata_dict: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract dependencies from metadata dictionary.
        
        Args:
            metadata_dict: Metadata dictionary
            
        Returns:
            List of dependency dictionaries
        """
        dependencies = []
        
        # Extract requires
        requires = metadata_dict.get('requires', [])
        if isinstance(requires, str):
            requires = [requires]
        
        for req in requires:
            if isinstance(req, str):
                if '/' in req:
                    dep_name, dep_version = req.split('/', 1)
                    dep_version = dep_version.split('@')[0] if '@' in dep_version else dep_version
                    dependencies.append({
                        'name': dep_name,
                        'version': dep_version
                    })
                else:
                    dependencies.append({
                        'name': req,
                        'version': '*'
                    })
        
        # Extract tool_requires
        tool_requires = metadata_dict.get('tool_requires', [])
        if isinstance(tool_requires, str):
            tool_requires = [tool_requires]
        
        for req in tool_requires:
            if isinstance(req, str):
                if '/' in req:
                    dep_name, dep_version = req.split('/', 1)
                    dep_version = dep_version.split('@')[0] if '@' in dep_version else dep_version
                    dependencies.append({
                        'name': dep_name,
                        'version': dep_version,
                        'type': 'build'
                    })
        
        return dependencies
    
    def _extract_dependencies_from_content(self, content: str) -> List[Dict[str, str]]:
        """Extract dependencies from file content using regex.
        
        Args:
            content: File content
            
        Returns:
            List of dependency dictionaries
        """
        dependencies = []
        
        # Find requires list or string
        requires_match = re.search(r'^\s*requires\s*=\s*\[(.*?)\]', content, re.MULTILINE | re.DOTALL)
        if requires_match:
            # Parse list of requirements
            req_str = requires_match.group(1)
            for req in re.findall(r'["\']([^"\']+)["\']', req_str):
                if '/' in req:
                    dep_name, dep_version = req.split('/', 1)
                    dep_version = dep_version.split('@')[0] if '@' in dep_version else dep_version
                    dependencies.append({
                        'name': dep_name,
                        'version': dep_version
                    })
                else:
                    dependencies.append({
                        'name': req,
                        'version': '*'
                    })
        else:
            # Try single string require
            requires_match = re.search(r'^\s*requires\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if requires_match:
                req = requires_match.group(1)
                if '/' in req:
                    dep_name, dep_version = req.split('/', 1)
                    dep_version = dep_version.split('@')[0] if '@' in dep_version else dep_version
                    dependencies.append({
                        'name': dep_name,
                        'version': dep_version
                    })
        
        return dependencies