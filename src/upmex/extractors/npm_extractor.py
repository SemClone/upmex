"""NPM package extractor."""

import tarfile
import json
from pathlib import Path
from typing import Dict, Any
from .base import BaseExtractor
from ..core.models import PackageMetadata, PackageType, NO_ASSERTION


class NpmExtractor(BaseExtractor):
    """Extractor for NPM packages."""
    
    def __init__(self, online_mode: bool = False):
        """Initialize NPM extractor."""
        super().__init__(online_mode)
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from NPM package."""
        metadata = PackageMetadata(
            name="unknown",
            package_type=PackageType.NPM
        )
        
        try:
            with tarfile.open(package_path, 'r:gz') as tf:
                # Look for package.json
                for member in tf.getmembers():
                    if member.name.endswith('package.json'):
                        content = tf.extractfile(member).read()
                        data = json.loads(content)
                        
                        # Extract basic metadata
                        metadata.name = data.get('name', 'unknown')
                        metadata.version = data.get('version')
                        metadata.description = data.get('description')
                        metadata.homepage = data.get('homepage')
                        
                        # Extract repository
                        repo = data.get('repository')
                        if isinstance(repo, dict):
                            metadata.repository = repo.get('url')
                        elif isinstance(repo, str):
                            metadata.repository = repo
                        
                        # Extract author - standardize format
                        author = data.get('author')
                        if isinstance(author, dict):
                            # Already in dict format with name/email
                            metadata.authors.append(author)
                        elif isinstance(author, str):
                            # Parse string format "Name <email>"
                            if '<' in author and '>' in author:
                                parts = author.rsplit(' <', 1)
                                if len(parts) == 2:
                                    name = parts[0].strip()
                                    email = parts[1].rstrip('>').strip()
                                    metadata.authors.append({
                                        'name': name,
                                        'email': email
                                    })
                                else:
                                    metadata.authors.append({'name': author})
                            else:
                                metadata.authors.append({'name': author})
                        
                        # Extract maintainers
                        maintainers = data.get('maintainers', [])
                        if isinstance(maintainers, list):
                            metadata.maintainers.extend(maintainers)
                        
                        # Extract dependencies
                        if 'dependencies' in data:
                            metadata.dependencies['runtime'] = list(data['dependencies'].keys())
                        if 'devDependencies' in data:
                            metadata.dependencies['dev'] = list(data['devDependencies'].keys())
                        if 'peerDependencies' in data:
                            metadata.dependencies['peer'] = list(data['peerDependencies'].keys())
                        
                        # Extract keywords
                        metadata.keywords = data.get('keywords', [])
                        
                        # Store raw metadata
                        metadata.raw_metadata = data
                        
                        break
        except Exception as e:
            print(f"Error extracting NPM metadata: {e}")
        
        return metadata
    
    def can_extract(self, package_path: str) -> bool:
        """Check if this is an NPM package."""
        path = Path(package_path)
        return path.suffix in ['.tgz'] or path.name.endswith('.tar.gz')