"""NPM package extractor - REFACTORED."""

import json
from pathlib import Path
from typing import Dict, Any
from .base import BaseExtractor
from ..core.models import PackageMetadata, PackageType, NO_ASSERTION


class NpmExtractor(BaseExtractor):
    """Extractor for NPM packages."""
    
    # No __init__ needed - BaseExtractor handles it
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from NPM package."""
        metadata = self.create_metadata(package_type=PackageType.NPM)
        
        try:
            # Use base class archive extraction
            files = self.extract_archive_files(package_path, ['package.json'])

            # Prioritize root package.json (package/package.json)
            # First, try to find the root package.json
            root_package_json = None
            other_package_jsons = []

            for filename, content in files.items():
                if filename == 'package/package.json':
                    root_package_json = (filename, content)
                elif 'package.json' in filename:
                    other_package_jsons.append((filename, content))

            # Process root package.json first if found
            if root_package_json:
                self._process_package_json(metadata, root_package_json[1])
            elif other_package_jsons:
                # Fallback to the first package.json if no root found
                # This maintains backward compatibility
                self._process_package_json(metadata, other_package_jsons[0][1])
            
            # Try to find license files
            detected_licenses = self.find_and_detect_licenses(archive_path=package_path)
            if detected_licenses:
                metadata.licenses.extend(detected_licenses)
            
            # Extract copyright information by extracting full package
            import tempfile
            import tarfile
            import os
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract full package for copyright scanning
                try:
                    with tarfile.open(package_path, 'r:*') as tar:
                        # Extract with a limit on file count and size for safety
                        members = tar.getmembers()[:100]  # Limit to first 100 files
                        tar.extractall(temp_dir, members=members)
                    
                    # Find the package directory (usually 'package')
                    pkg_dir = temp_dir
                    if os.path.exists(os.path.join(temp_dir, 'package')):
                        pkg_dir = os.path.join(temp_dir, 'package')
                    
                    # Detect copyrights from the extracted directory and merge holders with authors
                    copyright_statement = self.find_and_detect_copyrights(
                        directory_path=pkg_dir,
                        merge_with_authors=True,
                        metadata=metadata
                    )
                    if copyright_statement:
                        metadata.copyright = copyright_statement
                except Exception as e:
                    print(f"Error extracting for copyright: {e}")
                
        except Exception as e:
            print(f"Error extracting NPM metadata: {e}")
        
        return metadata
    
    def can_extract(self, package_path: str) -> bool:
        """Check if this is an NPM package."""
        path = Path(package_path)
        return path.suffix in ['.tgz'] or path.name.endswith('.tar.gz')
    
    def _process_package_json(self, metadata: PackageMetadata, content: bytes):
        """Process package.json content."""
        try:
            # Handle empty content
            if not content or len(content.strip()) == 0:
                print("Warning: Empty package.json content, skipping")
                return

            data = json.loads(content)

            # Skip if data is empty or not a dict
            if not data or not isinstance(data, dict):
                print("Warning: Invalid package.json structure, skipping")
                return

            # Extract basic metadata
            metadata.name = data.get('name', NO_ASSERTION)
            metadata.version = data.get('version', NO_ASSERTION)
            metadata.description = data.get('description', NO_ASSERTION)
            metadata.homepage = data.get('homepage', NO_ASSERTION)
            
            # Extract repository
            repo = data.get('repository')
            if isinstance(repo, dict):
                metadata.repository = repo.get('url', NO_ASSERTION)
            elif isinstance(repo, str):
                metadata.repository = repo
            
            # Use base class author parsing
            author = data.get('author')
            if author:
                parsed = self.parse_author(author)
                if parsed:
                    metadata.authors.append(parsed)
            
            # Extract maintainers
            maintainers = data.get('maintainers', [])
            if isinstance(maintainers, list):
                for maintainer in maintainers:
                    parsed = self.parse_author(maintainer)
                    if parsed:
                        metadata.maintainers.append(parsed)
            
            # Extract dependencies
            if 'dependencies' in data:
                metadata.dependencies['runtime'] = list(data['dependencies'].keys())
            if 'devDependencies' in data:
                metadata.dependencies['dev'] = list(data['devDependencies'].keys())
            if 'peerDependencies' in data:
                metadata.dependencies['peer'] = list(data['peerDependencies'].keys())
            
            # Extract keywords
            metadata.keywords = data.get('keywords', [])
            
            # Extract license
            self._extract_license(metadata, data)
            
            # Store raw metadata
            metadata.raw_metadata = data
            
        except Exception as e:
            print(f"Error processing package.json: {e}")
    
    def _extract_license(self, metadata: PackageMetadata, data: Dict):
        """Extract license information from package.json."""
        license_data = data.get('license') or data.get('licenses')
        
        if not license_data:
            return
        
        if isinstance(license_data, str):
            # Simple string license
            # Format license text for better oslili detection
            if len(license_data) < 20 and ':' not in license_data:
                formatted_text = f"License: {license_data}"
            else:
                formatted_text = license_data
            detected = self.detect_licenses_from_text(formatted_text, 'package.json')
            if detected:
                metadata.licenses.extend(detected)
                
        elif isinstance(license_data, dict):
            # Dict with 'type' field
            license_type = license_data.get('type')
            if license_type:
                # Format license text for better oslili detection
                if len(license_type) < 20 and ':' not in license_type:
                    formatted_text = f"License: {license_type}"
                else:
                    formatted_text = license_type
                detected = self.detect_licenses_from_text(formatted_text, 'package.json')
                if detected:
                    metadata.licenses.extend(detected)
                    
        elif isinstance(license_data, list):
            # Multiple licenses
            for lic in license_data:
                license_text = None
                if isinstance(lic, str):
                    license_text = lic
                elif isinstance(lic, dict):
                    license_text = lic.get('type')
                
                if license_text:
                    # Format license text for better oslili detection
                    if len(license_text) < 20 and ':' not in license_text:
                        formatted_text = f"License: {license_text}"
                    else:
                        formatted_text = license_text
                    detected = self.detect_licenses_from_text(formatted_text, 'package.json')
                    if detected:
                        metadata.licenses.extend(detected)