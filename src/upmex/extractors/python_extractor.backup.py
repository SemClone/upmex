"""Python package extractor for wheel and sdist formats."""

import zipfile
import tarfile
import json
import email
from pathlib import Path
from typing import Dict, Any, Optional
from .base import BaseExtractor
from ..core.models import PackageMetadata, PackageType, NO_ASSERTION
from ..utils.license_detector import LicenseDetector


class PythonExtractor(BaseExtractor):
    """Extractor for Python packages (wheel and sdist)."""
    
    def __init__(self, online_mode: bool = False):
        """Initialize Python extractor."""
        super().__init__(online_mode)
        self.license_detector = LicenseDetector()
    
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
        metadata = PackageMetadata(
            name="unknown",
            package_type=PackageType.PYTHON_WHEEL
        )
        
        try:
            with zipfile.ZipFile(wheel_path, 'r') as zf:
                # Look for METADATA file
                for name in zf.namelist():
                    if name.endswith('/METADATA') or name.endswith('/metadata.json'):
                        content = zf.read(name)
                        
                        if name.endswith('.json'):
                            # Handle metadata.json format
                            data = json.loads(content)
                            metadata.name = data.get('name', 'unknown')
                            metadata.version = data.get('version')
                            metadata.description = data.get('summary')
                        else:
                            # Parse METADATA file (email format)
                            msg = email.message_from_string(content.decode('utf-8'))
                            metadata.name = msg.get('Name', 'unknown')
                            metadata.version = msg.get('Version')
                            metadata.description = msg.get('Summary')
                            metadata.homepage = msg.get('Home-page')
                            
                            # Extract repository from Project-URL
                            project_urls = msg.get_all('Project-URL') or []
                            for url in project_urls:
                                if 'repository' in url.lower() or 'source' in url.lower() or 'github' in url.lower():
                                    # Format: "Repository, https://github.com/..."
                                    if ', ' in url:
                                        _, repo_url = url.split(', ', 1)
                                        metadata.repository = repo_url
                                        break
                            
                            # Extract authors - parse the Author-email field properly
                            author = msg.get('Author')
                            author_email = msg.get('Author-email')
                            if author or author_email:
                                # Parse name and email if combined
                                if author_email and '<' in author_email and '>' in author_email:
                                    # Format: "Name <email>"
                                    parts = author_email.rsplit(' <', 1)
                                    if len(parts) == 2:
                                        parsed_name = parts[0].strip()
                                        parsed_email = parts[1].rstrip('>').strip()
                                        metadata.authors.append({
                                            'name': parsed_name,
                                            'email': parsed_email
                                        })
                                    else:
                                        metadata.authors.append({
                                            'name': author,
                                            'email': author_email
                                        })
                                else:
                                    metadata.authors.append({
                                        'name': author,
                                        'email': author_email
                                    })
                            
                            # Extract dependencies
                            requires = msg.get_all('Requires-Dist') or []
                            metadata.dependencies['runtime'] = requires
                            
                            # Extract classifiers
                            metadata.classifiers = msg.get_all('Classifier') or []
                            
                            # Extract license using regex detection
                            license_text = msg.get('License')
                            if license_text:
                                license_info = self.license_detector.detect_license_from_text(
                                    license_text, 
                                    filename='METADATA'
                                )
                                if license_info:
                                    metadata.licenses = [license_info]
                            
                            # Also check classifiers for license info
                            if not metadata.licenses and metadata.classifiers:
                                for classifier in metadata.classifiers:
                                    if 'License ::' in classifier:
                                        license_info = self.license_detector.detect_license_from_text(
                                            classifier,
                                            filename='METADATA'
                                        )
                                        if license_info:
                                            metadata.licenses = [license_info]
                                            break
                            
                            # Extract keywords
                            keywords = msg.get('Keywords')
                            if keywords:
                                # Split by comma or space and clean up
                                if ',' in keywords:
                                    metadata.keywords = [k.strip() for k in keywords.split(',') if k.strip()]
                                else:
                                    metadata.keywords = [k.strip() for k in keywords.split() if k.strip()]
                        
                        break
        except Exception as e:
            print(f"Error extracting wheel metadata: {e}")
        
        return metadata
    
    def _extract_sdist(self, sdist_path: str) -> PackageMetadata:
        """Extract metadata from a source distribution."""
        metadata = PackageMetadata(
            name="unknown",
            package_type=PackageType.PYTHON_SDIST
        )
        
        try:
            # Determine archive type and extract
            if sdist_path.endswith('.tar.gz') or sdist_path.endswith('.tgz'):
                with tarfile.open(sdist_path, 'r:gz') as tf:
                    metadata = self._extract_from_tarfile(tf, metadata)
            elif sdist_path.endswith('.zip'):
                with zipfile.ZipFile(sdist_path, 'r') as zf:
                    metadata = self._extract_from_zipfile(zf, metadata)
        except Exception as e:
            print(f"Error extracting sdist metadata: {e}")
        
        return metadata
    
    def _extract_from_tarfile(self, tf: tarfile.TarFile, metadata: PackageMetadata) -> PackageMetadata:
        """Extract metadata from tar archive."""
        for member in tf.getmembers():
            if 'PKG-INFO' in member.name or 'setup.cfg' in member.name:
                content = tf.extractfile(member).read().decode('utf-8')
                
                if 'PKG-INFO' in member.name:
                    msg = email.message_from_string(content)
                    metadata.name = msg.get('Name', metadata.name)
                    metadata.version = msg.get('Version')
                    metadata.description = msg.get('Summary')
                    metadata.homepage = msg.get('Home-page')
                
                if metadata.name != "unknown":
                    break
        
        return metadata
    
    def _extract_from_zipfile(self, zf: zipfile.ZipFile, metadata: PackageMetadata) -> PackageMetadata:
        """Extract metadata from zip archive."""
        for name in zf.namelist():
            if 'PKG-INFO' in name or 'setup.cfg' in name:
                content = zf.read(name).decode('utf-8')
                
                if 'PKG-INFO' in name:
                    msg = email.message_from_string(content)
                    metadata.name = msg.get('Name', metadata.name)
                    metadata.version = msg.get('Version')
                    metadata.description = msg.get('Summary')
                    metadata.homepage = msg.get('Home-page')
                
                if metadata.name != "unknown":
                    break
        
        return metadata