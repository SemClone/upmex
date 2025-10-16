"""CocoaPods extractor for .podspec and .podspec.json files."""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from .base import BaseExtractor
from ..core.models import PackageMetadata, PackageType, NO_ASSERTION


class CocoaPodsExtractor(BaseExtractor):
    """Extract metadata from CocoaPods .podspec or .podspec.json files."""
    
    # __init__ removed - using BaseExtractor
    
    def can_extract(self, package_path: str) -> bool:
        """Check if this extractor can handle the package.
        
        Args:
            package_path: Path to the package file
            
        Returns:
            True if this extractor can handle CocoaPods packages
        """
        path = Path(package_path)
        return path.suffix == '.podspec' or path.name.endswith('.podspec.json')
    
    def extract(self, file_path: str) -> PackageMetadata:
        """Extract metadata from a CocoaPods podspec file.
        
        Args:
            file_path: Path to .podspec or .podspec.json file
            
        Returns:
            PackageMetadata object
        """
        path = Path(file_path)
        
        try:
            if path.suffix == '.json':
                return self._extract_json_podspec(file_path)
            else:
                return self._extract_ruby_podspec(file_path)
        except Exception as e:
            return self._create_minimal_metadata(
                name=path.stem.replace('.podspec', '').replace('.json', ''),
                version=NO_ASSERTION,
                file_path=file_path,
                error=str(e)
            )
    
    def _extract_json_podspec(self, file_path: str) -> PackageMetadata:
        """Extract metadata from a .podspec.json file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                spec_data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return self._create_minimal_metadata(
                name=Path(file_path).stem.replace('.podspec', '').replace('.json', ''),
                version=NO_ASSERTION,
                file_path=file_path,
                error=f"JSON parsing error: {e}"
            )
        
        return self._extract_from_spec_data(spec_data, file_path)
    
    def _extract_ruby_podspec(self, file_path: str) -> PackageMetadata:
        """Extract metadata from a .podspec Ruby DSL file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError as e:
            return self._create_minimal_metadata(
                name=Path(file_path).stem.replace('.podspec', '').replace('.json', ''),
                version=NO_ASSERTION,
                file_path=file_path,
                error=f"File encoding error: {e}"
            )
        
        # Parse Ruby DSL using regex patterns
        spec_data = self._parse_ruby_dsl(content)
        return self._extract_from_spec_data(spec_data, file_path)
    
    def _parse_ruby_dsl(self, content: str) -> Dict[str, Any]:
        """Parse Ruby DSL podspec content using regex patterns."""
        spec_data = {}
        
        # Helper function to extract quoted strings and handle multi-line
        def extract_value(pattern: str, content: str, multiline: bool = False) -> Optional[str]:
            flags = re.DOTALL if multiline else 0
            match = re.search(pattern, content, flags)
            if match:
                value = match.group(1)
                # Clean up quotes and escape sequences
                value = re.sub(r'^["\']|["\']$', '', value.strip())
                value = value.replace('\\"', '"').replace("\\'", "'")
                return value
            return None
        
        # Extract basic metadata
        spec_data['name'] = extract_value(r's\.name\s*=\s*["\']([^"\']+)["\']', content)
        spec_data['version'] = extract_value(r's\.version\s*=\s*["\']([^"\']+)["\']', content)
        spec_data['summary'] = extract_value(r's\.summary\s*=\s*["\']([^"\']+)["\']', content)
        
        # Description can be multi-line, including heredoc format
        desc_heredoc = re.search(r's\.description\s*=\s*<<-?(\w+)(.*?)\n\s*\1', content, re.DOTALL)
        if desc_heredoc:
            desc_content = desc_heredoc.group(2).strip()
            # Clean up indentation
            lines = desc_content.split('\n')
            clean_lines = []
            for line in lines:
                clean_line = line.strip()
                if clean_line:
                    clean_lines.append(clean_line)
            spec_data['description'] = ' '.join(clean_lines)
        else:
            # Single-line description
            description = extract_value(r's\.description\s*=\s*["\']([^"\']*(?:\\.[^"\']*)*)["\']', content, True)
            if description:
                spec_data['description'] = description
        
        # Extract homepage
        homepage = extract_value(r's\.homepage\s*=\s*["\']([^"\']+)["\']', content)
        if homepage:
            spec_data['homepage'] = homepage
        
        # Extract license
        license_match = re.search(r's\.license\s*=\s*([^\\n]+)', content)
        if license_match:
            license_str = license_match.group(1).strip()
            if license_str.startswith('{') and license_str.endswith('}'):
                # Hash format: { :type => 'MIT', :file => 'LICENSE' }
                type_match = re.search(r':type\s*=>\s*["\']([^"\']+)["\']', license_str)
                file_match = re.search(r':file\s*=>\s*["\']([^"\']+)["\']', license_str)
                if type_match:
                    spec_data['license'] = {'type': type_match.group(1)}
                    if file_match:
                        spec_data['license']['file'] = file_match.group(1)
            else:
                # String format: 'MIT'
                license_clean = re.sub(r'^["\']|["\']$', '', license_str.strip())
                spec_data['license'] = license_clean
        
        # Extract authors (handle different formats)
        authors_hash = re.search(r's\.authors?\s*=\s*\{([^}]+)\}', content)
        if authors_hash:
            # Hash format: { 'Author Name' => 'email@example.com' }
            authors_str = authors_hash.group(1)
            authors = {}
            author_matches = re.findall(r'["\']([^"\']+)["\']\s*=>\s*["\']([^"\']+)["\']', authors_str)
            for name, email in author_matches:
                authors[name] = email
            spec_data['authors'] = authors
        else:
            # Try array format or simple string
            authors_simple = re.search(r's\.authors?\s*=\s*["\']([^"\']+)["\']', content)
            if authors_simple:
                spec_data['authors'] = authors_simple.group(1)
        
        # Extract source
        source_match = re.search(r's\.source\s*=\s*\{([^}]+)\}', content, re.DOTALL)
        if source_match:
            source_str = source_match.group(1)
            source = {}
            # Extract git URL
            git_match = re.search(r':git\s*=>\s*["\']([^"\']+)["\']', source_str)
            if git_match:
                source['git'] = git_match.group(1)
            # Extract tag
            tag_match = re.search(r':tag\s*=>\s*["\']([^"\']+)["\']', source_str)
            if tag_match:
                source['tag'] = tag_match.group(1)
            # Extract commit
            commit_match = re.search(r':commit\s*=>\s*["\']([^"\']+)["\']', source_str)
            if commit_match:
                source['commit'] = commit_match.group(1)
            # Extract http
            http_match = re.search(r':http\s*=>\s*["\']([^"\']+)["\']', source_str)
            if http_match:
                source['http'] = http_match.group(1)
            
            spec_data['source'] = source
        
        # Extract platform requirements
        platforms = {}
        
        # Check for s.platform = :ios, '9.0' format
        platform_matches = re.findall(r's\.platform\s*=\s*:(\w+)(?:,\s*["\']([^"\']+)["\'])?', content)
        for platform, version in platform_matches:
            platforms[platform] = version if version else None
        
        # Also check for deployment targets: s.ios.deployment_target = "9.0"
        deployment_targets = re.findall(r's\.(\w+)\.deployment_target\s*=\s*["\']([^"\']+)["\']', content)
        for platform, version in deployment_targets:
            platforms[platform] = version
        
        # Also check for legacy format: s.ios_deployment_target = "9.0"
        legacy_targets = re.findall(r's\.(\w+)_deployment_target\s*=\s*["\']([^"\']+)["\']', content)
        for target_key, version in legacy_targets:
            platform = target_key  # ios_deployment_target -> ios
            platforms[platform] = version
        
        if platforms:
            spec_data['platforms'] = platforms
        
        # Extract dependencies
        dependencies = {}
        
        # Runtime dependencies
        runtime_deps = re.findall(r's\.dependency\s+["\']([^"\']+)["\'](?:,\s*["\']([^"\']+)["\'])?', content)
        if runtime_deps:
            dependencies['runtime'] = []
            for dep_name, version_req in runtime_deps:
                if version_req:
                    dependencies['runtime'].append(f"{dep_name} {version_req}")
                else:
                    dependencies['runtime'].append(dep_name)
        
        if dependencies:
            spec_data['dependencies'] = dependencies
        
        # Extract frameworks (can be array or string)
        frameworks_array = re.search(r's\.frameworks?\s*=\s*\[([^\]]+)\]', content)
        if frameworks_array:
            frameworks_str = frameworks_array.group(1)
            frameworks = re.findall(r'["\']([^"\']+)["\']', frameworks_str)
            spec_data['frameworks'] = frameworks
        else:
            # Single framework
            framework = re.search(r's\.frameworks?\s*=\s*["\']([^"\']+)["\']', content)
            if framework:
                spec_data['frameworks'] = [framework.group(1)]
        
        # Extract libraries (can be array or string)
        libraries_array = re.search(r's\.libraries?\s*=\s*\[([^\]]+)\]', content)
        if libraries_array:
            libraries_str = libraries_array.group(1)
            libraries = re.findall(r'["\']([^"\']+)["\']', libraries_str)
            spec_data['libraries'] = libraries
        else:
            # Single library
            library = re.search(r's\.libraries?\s*=\s*["\']([^"\']+)["\']', content)
            if library:
                spec_data['libraries'] = [library.group(1)]
        
        return spec_data
    
    def _extract_from_spec_data(self, spec_data: Dict[str, Any], file_path: str) -> PackageMetadata:
        """Extract PackageMetadata from parsed spec data."""
        
        # Basic metadata
        name = spec_data.get('name', Path(file_path).stem.replace('.podspec', '').replace('.json', ''))
        version = spec_data.get('version', NO_ASSERTION)
        
        # Description (prefer description over summary)
        description = spec_data.get('description') or spec_data.get('summary', NO_ASSERTION)
        
        # Homepage
        homepage = spec_data.get('homepage', NO_ASSERTION)
        
        # Repository URL from source
        repository = NO_ASSERTION
        source = spec_data.get('source', {})
        if isinstance(source, dict):
            repository = source.get('git') or source.get('http', NO_ASSERTION)
        
        # Authors
        authors = []
        authors_data = spec_data.get('authors', spec_data.get('author'))
        if isinstance(authors_data, dict):
            # Hash format: { 'Name' => 'email' }
            for author_name, email in authors_data.items():
                authors.append({'name': author_name, 'email': email})
        elif isinstance(authors_data, list):
            # Array format
            for author in authors_data:
                if isinstance(author, str):
                    authors.append({'name': author, 'email': NO_ASSERTION})
        elif isinstance(authors_data, str):
            # String format
            authors.append({'name': authors_data, 'email': NO_ASSERTION})
        
        # Dependencies
        dependencies = {}
        deps_data = spec_data.get('dependencies', {})
        if isinstance(deps_data, dict):
            dependencies.update(deps_data)
        
        # Keywords from platforms and frameworks
        keywords = []
        if 'platforms' in spec_data:
            platforms = spec_data['platforms']
            if isinstance(platforms, dict):
                keywords.extend(platforms.keys())
        
        if 'frameworks' in spec_data:
            frameworks = spec_data['frameworks']
            if isinstance(frameworks, list):
                keywords.extend(frameworks)
            elif isinstance(frameworks, str):
                keywords.append(frameworks)
        
        # License detection
        licenses = []
        license_data = spec_data.get('license')
        if license_data:
            if isinstance(license_data, dict):
                license_type = license_data.get('type')
                license_file = license_data.get('file')
                if license_type:
                    # Format license text for better oslili detection
                    if len(license_type) < 20 and ':' not in license_type:
                        formatted_text = f"License: {license_type}"
                    else:
                        formatted_text = license_type
                    detected = self.detect_licenses_from_text(formatted_text)
                    if detected:
                        licenses.extend(detected)
                elif license_file:
                    # Try to read license file if it exists
                    license_file_path = Path(file_path).parent / license_file
                    if license_file_path.exists():
                        try:
                            with open(license_file_path, 'r', encoding='utf-8') as f:
                                license_content = f.read()
                                detected = self.detect_licenses_from_text(license_content)
                                if detected:
                                    licenses.extend(detected)
                        except Exception:
                            pass
            elif isinstance(license_data, str):
                # Format license text for better oslili detection
                if len(license_data) < 20 and ':' not in license_data:
                    formatted_text = f"License: {license_data}"
                else:
                    formatted_text = license_data
                detected = self.detect_licenses_from_text(formatted_text)
                if detected:
                    licenses.extend(detected)
        
        # If no license found, try to find LICENSE files
        if not licenses:
            license_files = ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'License', 'license']
            for license_file in license_files:
                license_path = Path(file_path).parent / license_file
                if license_path.exists():
                    try:
                        with open(license_path, 'r', encoding='utf-8') as f:
                            license_content = f.read()
                            detected = self.detect_licenses_from_text(license_content)
                            if detected:
                                licenses.extend(detected)
                                break
                    except Exception:
                        continue
        
        return PackageMetadata(
            name=name,
            version=version,
            package_type=PackageType.COCOAPODS,
            description=description,
            homepage=homepage,
            repository=repository,
            authors=authors,
            licenses=licenses,
            dependencies=dependencies,
            keywords=keywords,
            raw_metadata=spec_data
        )
    
    def _create_minimal_metadata(self, name: str, version: str, file_path: str, error: str = None) -> PackageMetadata:
        """Create minimal metadata when extraction fails."""
        return PackageMetadata(
            name=name,
            version=version,
            package_type=PackageType.COCOAPODS,
            description=NO_ASSERTION,
            homepage=NO_ASSERTION,
            repository=NO_ASSERTION,
            authors=[],
            licenses=[],
            dependencies={},
            keywords=[],
            raw_metadata={'extraction_error': error} if error else {}
        )