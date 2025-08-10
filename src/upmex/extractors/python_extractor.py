"""Python package extractor for wheel and sdist formats - REFACTORED."""

import json
import email
from pathlib import Path
from typing import Dict, Any, Optional
from .base import BaseExtractor
from ..core.models import PackageMetadata, PackageType, NO_ASSERTION


class PythonExtractor(BaseExtractor):
    """Extractor for Python packages (wheel and sdist)."""
    
    # No need for __init__ anymore - BaseExtractor handles it
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from Python package."""
        path = Path(package_path)
        
        if path.suffix == '.whl':
            return self._extract_wheel(package_path)
        elif path.suffix in ['.gz', '.tar', '.zip']:
            return self._extract_sdist(package_path)
        else:
            raise ValueError(f"Unsupported Python package format: {path.suffix}")
    
    def can_extract(self, package_path: str) -> bool:
        """Check if this is a Python package."""
        path = Path(package_path)
        return (
            path.suffix == '.whl' or
            (path.suffix in ['.gz', '.tar', '.zip'] and 
             any(x in path.name for x in ['.tar.gz', '.tar.bz2', '.zip']))
        )
    
    def _extract_wheel(self, wheel_path: str) -> PackageMetadata:
        """Extract metadata from a wheel file."""
        metadata = self.create_metadata(package_type=PackageType.PYTHON_WHEEL)
        
        try:
            # Use base class archive extraction
            files = self.extract_archive_files(wheel_path, ['METADATA', 'metadata.json'])
            
            # Find and process metadata file
            for filename, content in files.items():
                if filename.endswith('/METADATA') or filename == 'METADATA':
                    self._process_metadata_file(metadata, content)
                    break
                elif filename.endswith('/metadata.json') or filename == 'metadata.json':
                    self._process_json_metadata(metadata, content)
                    break
            
            # Try to find license files
            detected_licenses = self.find_and_detect_licenses(archive_path=wheel_path)
            if detected_licenses:
                metadata.licenses.extend(detected_licenses)
                
        except Exception as e:
            print(f"Error extracting wheel metadata: {e}")
        
        return metadata
    
    def _extract_sdist(self, sdist_path: str) -> PackageMetadata:
        """Extract metadata from a source distribution."""
        metadata = self.create_metadata(package_type=PackageType.PYTHON_SDIST)
        
        try:
            # Use base class archive extraction
            files = self.extract_archive_files(sdist_path, ['PKG-INFO', 'setup.cfg', 'pyproject.toml'])
            
            # Process PKG-INFO if found
            for filename, content in files.items():
                if 'PKG-INFO' in filename:
                    self._process_metadata_file(metadata, content)
                    break
            
            # Try to find license files
            detected_licenses = self.find_and_detect_licenses(archive_path=sdist_path)
            if detected_licenses:
                metadata.licenses.extend(detected_licenses)
                
        except Exception as e:
            print(f"Error extracting sdist metadata: {e}")
        
        return metadata
    
    def _process_metadata_file(self, metadata: PackageMetadata, content: bytes):
        """Process METADATA or PKG-INFO file content."""
        try:
            # Parse email format
            msg = email.message_from_string(content.decode('utf-8'))
            
            metadata.name = msg.get('Name', NO_ASSERTION)
            metadata.version = msg.get('Version', NO_ASSERTION)
            metadata.description = msg.get('Summary', NO_ASSERTION)
            metadata.homepage = msg.get('Home-page', NO_ASSERTION)
            
            # Extract repository from Project-URL
            project_urls = msg.get_all('Project-URL') or []
            for url in project_urls:
                if any(term in url.lower() for term in ['repository', 'source', 'github']):
                    if ', ' in url:
                        _, repo_url = url.split(', ', 1)
                        metadata.repository = repo_url
                        break
            
            # Use base class author parsing
            author = msg.get('Author')
            author_email = msg.get('Author-email')
            
            if author_email and '<' in author_email:
                # "Name <email>" format
                parsed = self.parse_author(author_email)
                if parsed:
                    metadata.authors.append(parsed)
            elif author or author_email:
                # Separate fields
                author_dict = {}
                if author:
                    author_dict['name'] = author
                if author_email:
                    author_dict['email'] = author_email
                if author_dict:
                    metadata.authors.append(author_dict)
            
            # Extract dependencies
            requires = msg.get_all('Requires-Dist') or []
            if requires:
                metadata.dependencies['runtime'] = requires
            
            # Extract classifiers
            metadata.classifiers = msg.get_all('Classifier') or []
            
            # Detect license from text
            license_text = msg.get('License')
            if license_text:
                detected = self.detect_licenses_from_text(license_text, 'METADATA')
                if detected:
                    metadata.licenses.extend(detected)
            
            # Also check classifiers for license info
            if not metadata.licenses and metadata.classifiers:
                for classifier in metadata.classifiers:
                    if 'License ::' in classifier:
                        detected = self.detect_licenses_from_text(classifier, 'METADATA')
                        if detected:
                            metadata.licenses.extend(detected)
                            break
            
            # Extract keywords
            keywords = msg.get('Keywords')
            if keywords:
                if ',' in keywords:
                    metadata.keywords = [k.strip() for k in keywords.split(',') if k.strip()]
                else:
                    metadata.keywords = [k.strip() for k in keywords.split() if k.strip()]
                    
        except Exception as e:
            print(f"Error processing metadata file: {e}")
    
    def _process_json_metadata(self, metadata: PackageMetadata, content: bytes):
        """Process metadata.json format."""
        try:
            data = json.loads(content)
            metadata.name = data.get('name', NO_ASSERTION)
            metadata.version = data.get('version', NO_ASSERTION)
            metadata.description = data.get('summary', NO_ASSERTION)
            metadata.homepage = data.get('home_page', NO_ASSERTION)
            
            # Parse authors
            if 'author' in data:
                parsed = self.parse_author(data['author'])
                if parsed:
                    metadata.authors.append(parsed)
                    
        except Exception as e:
            print(f"Error processing JSON metadata: {e}")