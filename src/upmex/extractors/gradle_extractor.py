"""Gradle build file extractor."""

import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from .base import BaseExtractor
from ..core.models import PackageMetadata, PackageType, NO_ASSERTION


class GradleExtractor(BaseExtractor):
    """Extractor for Gradle build files."""
    
    # __init__ removed - using BaseExtractor
    
    def extract(self, file_path: str) -> PackageMetadata:
        """Extract metadata from Gradle build file."""
        metadata = self.create_metadata(package_type=PackageType.GRADLE)
        
        try:
            path = Path(file_path)
            content = path.read_text(encoding='utf-8')
            
            # Determine if it's Kotlin DSL or Groovy DSL
            is_kotlin_dsl = path.suffix == '.kts'
            
            # Extract basic metadata
            # First try rootProject.name for settings.gradle
            project_name = self._extract_field(content, 'rootProject.name', 'rootProject.name', is_kotlin_dsl)
            
            # If not found, use the file stem (without .gradle extension)
            if not project_name:
                project_name = path.stem
                if project_name.endswith('.gradle'):
                    project_name = project_name[:-7]
            
            metadata.name = project_name
            metadata.version = self._extract_field(content, 'version', 'version', is_kotlin_dsl)
            metadata.description = self._extract_field(content, 'description', 'description', is_kotlin_dsl)
            
            # Extract group (organization)
            group = self._extract_field(content, 'group', 'group', is_kotlin_dsl)
            if group and metadata.name != "unknown":
                # Format similar to Maven: group:artifact
                metadata.name = f"{group}:{metadata.name}"
            
            # Extract repository URL
            metadata.repository = self._extract_repository(content, is_kotlin_dsl)
            
            # Extract homepage URL
            metadata.homepage = self._extract_url(content, is_kotlin_dsl)
            
            # Extract dependencies
            metadata.dependencies = self._extract_dependencies(content, is_kotlin_dsl)
            
            # Extract author information from publishing block
            metadata.authors = self._extract_authors(content, is_kotlin_dsl)
            
            # Extract license
            license_info = self._extract_license(content, is_kotlin_dsl)
            if license_info:
                    metadata.licenses.extend(license_info)
            
            # Extract keywords/tags from labels or tags
            metadata.keywords = self._extract_keywords(content, is_kotlin_dsl)
            
        except Exception as e:
            print(f"Error extracting Gradle metadata: {e}")
        
        return metadata
    
    def can_extract(self, file_path: str) -> bool:
        """Check if this is a Gradle build file."""
        path = Path(file_path)
        return path.name in ['build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts']
    
    def _extract_field(self, content: str, field: str, alt_field: str, is_kotlin: bool) -> Optional[str]:
        """Extract a field value from Gradle script."""
        patterns = []
        
        if is_kotlin:
            # Kotlin DSL patterns
            patterns = [
                rf'{field}\s*=\s*"([^"]+)"',
                rf'{field}\s*=\s*\'([^\']+)\'',
                rf'{alt_field}\s*=\s*"([^"]+)"',
                rf'{alt_field}\s*=\s*\'([^\']+)\'',
                rf'{field}\s*\(\s*"([^"]+)"\s*\)',
                rf'{field}\s*\(\s*\'([^\']+)\'\s*\)',
            ]
        else:
            # Groovy DSL patterns
            patterns = [
                rf'{field}\s*=\s*["\']([^"\']+)["\']',
                rf'{field}\s+["\']([^"\']+)["\']',
                rf'{alt_field}\s*=\s*["\']([^"\']+)["\']',
                rf'{alt_field}\s+["\']([^"\']+)["\']',
            ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_repository(self, content: str, is_kotlin: bool) -> Optional[str]:
        """Extract repository URL from Gradle script."""
        # Look for vcs/scm URL
        patterns = [
            r'url\s*=\s*["\']([^"\']+github[^"\']+)["\']',
            r'url\s*=\s*["\']([^"\']+gitlab[^"\']+)["\']',
            r'url\s*=\s*["\']([^"\']+bitbucket[^"\']+)["\']',
            r'scm\s*\{[^}]*url\s*=\s*["\']([^"\']+)["\']',
            r'vcs\s*\{[^}]*url\s*=\s*["\']([^"\']+)["\']',
        ]
        
        if is_kotlin:
            patterns.extend([
                r'url\.set\(["\']([^"\']+)["\']',
                r'vcs\s*\{[^}]*url\.set\(["\']([^"\']+)["\']',
            ])
        
        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                url = match.group(1)
                # Clean up URL
                if url.startswith('git://'):
                    url = url.replace('git://', 'https://')
                elif url.startswith('scm:git:'):
                    url = url.replace('scm:git:', '')
                return url
        
        return None
    
    def _extract_url(self, content: str, is_kotlin: bool) -> Optional[str]:
        """Extract homepage URL from Gradle script."""
        patterns = [
            r'url\s*=\s*["\']([^"\']+)["\']',
            r'website\s*=\s*["\']([^"\']+)["\']',
            r'homepage\s*=\s*["\']([^"\']+)["\']',
        ]
        
        if is_kotlin:
            patterns.extend([
                r'url\.set\(["\']([^"\']+)["\']',
                r'website\.set\(["\']([^"\']+)["\']',
            ])
        
        # Look in publishing or pom configuration
        publishing_match = re.search(
            r'publishing\s*\{[^}]*pom\s*\{([^}]+)\}',
            content,
            re.MULTILINE | re.DOTALL
        )
        
        if publishing_match:
            pom_content = publishing_match.group(1)
            for pattern in patterns:
                match = re.search(pattern, pom_content)
                if match:
                    url = match.group(1)
                    if url.startswith('http'):
                        return url
        
        return None
    
    def _extract_dependencies(self, content: str, is_kotlin: bool) -> Dict[str, List[str]]:
        """Extract dependencies from Gradle script."""
        dependencies = {
            'runtime': [],
            'compile': [],
            'implementation': [],
            'test': [],
            'api': []
        }
        
        # Find dependencies block
        dep_pattern = r'dependencies\s*\{([^}]+(?:\{[^}]+\}[^}]+)*)\}'
        dep_match = re.search(dep_pattern, content, re.MULTILINE | re.DOTALL)
        
        if dep_match:
            dep_block = dep_match.group(1)
            
            # Patterns for different dependency configurations
            patterns = {
                'implementation': r'implementation\s*\(?["\']([^"\']+)["\']\)?',
                'compile': r'compile\s*\(?["\']([^"\']+)["\']\)?',
                'runtime': r'runtime\s*\(?["\']([^"\']+)["\']\)?',
                'runtimeOnly': r'runtimeOnly\s*\(?["\']([^"\']+)["\']\)?',
                'api': r'api\s*\(?["\']([^"\']+)["\']\)?',
                'testImplementation': r'testImplementation\s*\(?["\']([^"\']+)["\']\)?',
                'testCompile': r'testCompile\s*\(?["\']([^"\']+)["\']\)?',
                'testRuntime': r'testRuntime\s*\(?["\']([^"\']+)["\']\)?',
            }
            
            for config, pattern in patterns.items():
                matches = re.findall(pattern, dep_block)
                for dep in matches:
                    # Categorize dependencies
                    if 'test' in config.lower():
                        dependencies['test'].append(dep)
                    elif config in ['implementation', 'compile']:
                        dependencies['implementation'].append(dep)
                    elif config == 'api':
                        dependencies['api'].append(dep)
                    elif 'runtime' in config.lower():
                        dependencies['runtime'].append(dep)
        
        # Clean up empty categories
        return {k: v for k, v in dependencies.items() if v}
    
    def _extract_authors(self, content: str, is_kotlin: bool) -> List[Dict[str, str]]:
        """Extract author information from Gradle script."""
        authors = []
        
        # Look in publishing/pom section
        patterns = [
            r'developer\s*\{[^}]*name\s*=\s*["\']([^"\']+)["\'][^}]*email\s*=\s*["\']([^"\']+)["\']',
            r'author\s*=\s*["\']([^"\']+)["\']',
            r'developers\s*\{[^}]*developer\s*\{[^}]*name\s*=\s*["\']([^"\']+)["\']',
        ]
        
        # Add Kotlin-specific patterns
        if is_kotlin:
            patterns.extend([
                r'developer\s*\{[^}]*name\.set\(["\']([^"\']+)["\']\)[^}]*email\.set\(["\']([^"\']+)["\']\)',
                r'name\.set\(["\']([^"\']+)["\']\)[^}]*email\.set\(["\']([^"\']+)["\']\)',
            ])
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                if isinstance(match, tuple) and len(match) == 2:
                    authors.append({
                        'name': match[0],
                        'email': match[1]
                    })
                elif isinstance(match, str):
                    # Parse "Name <email>" format
                    if '<' in match and '>' in match:
                        name, email = match.rsplit(' <', 1)
                        authors.append({
                            'name': name.strip(),
                            'email': email.rstrip('>').strip()
                        })
                    else:
                        authors.append({
                            'name': match,
                            'email': None
                        })
        
        return authors if authors else []
    
    def _extract_license(self, content: str, is_kotlin: bool):
        """Extract license information from Gradle script."""
        # Look for license in publishing/pom section
        patterns = [
            r'license\s*\{[^}]*name\s*=\s*["\']([^"\']+)["\']',
            r'licenses\s*\{[^}]*license\s*\{[^}]*name\s*=\s*["\']([^"\']+)["\']',
            r'license\s*=\s*["\']([^"\']+)["\']',
        ]
        
        # Add Kotlin-specific patterns
        if is_kotlin:
            patterns.extend([
                r'license\s*\{[^}]*name\.set\(["\']([^"\']+)["\']\)',
                r'name\.set\(["\']([^"\']+)["\']\)',
            ])
        
        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                license_text = match.group(1)
                # Format license text for better oslili detection
                if len(license_text) < 20 and ':' not in license_text:
                    formatted_text = f"License: {license_text}"
                else:
                    formatted_text = license_text
                return self.detect_licenses_from_text(
                    formatted_text,
                    filename='build.gradle'
                )
        
        return None
    
    def _extract_keywords(self, content: str, is_kotlin: bool) -> List[str]:
        """Extract keywords/tags from Gradle script."""
        keywords = []
        
        patterns = [
            r'tags\s*=\s*\[([^\]]+)\]',
            r'labels\s*=\s*\[([^\]]+)\]',
            r'keywords\s*=\s*\[([^\]]+)\]',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                tags_str = match.group(1)
                # Parse the list of tags
                tags = re.findall(r'["\']([^"\']+)["\']', tags_str)
                keywords.extend(tags)
        
        return list(set(keywords)) if keywords else []