"""Ruby gem package extractor."""

import tarfile
import gzip
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import re

from .base import BaseExtractor
from ..core.models import NO_ASSERTION, PackageMetadata, PackageType

logger = logging.getLogger(__name__)


# Custom YAML loader that ignores Ruby-specific tags
class RubyYAMLLoader(yaml.SafeLoader):
    """Custom YAML loader for Ruby gem metadata."""
    pass

# Register constructor for Ruby-specific tags
def ruby_object_constructor(loader, tag_suffix, node):
    """Constructor for Ruby objects in YAML."""
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_scalar(node)

# Add multi-constructor for all Ruby tags
RubyYAMLLoader.add_multi_constructor('!ruby/', ruby_object_constructor)


class RubyExtractor(BaseExtractor):
    """Extract metadata from Ruby gem packages."""

    # __init__ removed - using BaseExtractor

    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a Ruby gem package.
        
        Ruby gems are tar archives containing:
        - metadata.gz: YAML file with gem specification
        - data.tar.gz: actual gem files
        - checksums.yaml.gz: integrity checksums
        """
        package_path = Path(package_path)
        metadata = PackageMetadata(
            name=NO_ASSERTION,
            version=NO_ASSERTION,
            package_type=PackageType.RUBY_GEM,
            description=NO_ASSERTION,
            homepage=NO_ASSERTION,
            repository=NO_ASSERTION
        )
        metadata.dependencies = {'runtime': [], 'development': []}
        build_tools = []
        documentation_url = NO_ASSERTION

        try:
            # Open the gem file (tar archive)
            with tarfile.open(package_path, 'r') as gem_tar:
                # Extract metadata.gz
                metadata_member = None
                for member in gem_tar.getmembers():
                    if member.name == 'metadata.gz':
                        metadata_member = member
                        break
                
                if metadata_member:
                    # Extract and decompress metadata
                    metadata_file = gem_tar.extractfile(metadata_member)
                    if metadata_file:
                        metadata_content = gzip.decompress(metadata_file.read())
                        # Ruby gems use custom YAML tags, use our custom loader
                        gemspec = yaml.load(metadata_content.decode('utf-8'), Loader=RubyYAMLLoader)
                        
                        # Extract basic metadata
                        if gemspec.get('name'):
                            metadata.name = gemspec['name']
                        
                        if gemspec.get('version'):
                            version = gemspec['version']
                            if isinstance(version, dict) and 'version' in version:
                                metadata.version = str(version['version'])
                            elif hasattr(version, 'version'):
                                metadata.version = str(version.version)
                            else:
                                metadata.version = str(version)
                        
                        if gemspec.get('summary'):
                            metadata.description = gemspec['summary']
                        elif gemspec.get('description'):
                            metadata.description = gemspec['description']
                        
                        if gemspec.get('homepage'):
                            metadata.homepage = gemspec['homepage']
                        
                        # Try to extract repository from homepage or metadata
                        if gemspec.get('metadata'):
                            gem_metadata = gemspec['metadata']
                            if isinstance(gem_metadata, dict):
                                if gem_metadata.get('source_code_uri'):
                                    metadata.repository = gem_metadata['source_code_uri']
                                elif gem_metadata.get('homepage_uri'):
                                    repo_url = gem_metadata['homepage_uri']
                                    if 'github.com' in repo_url or 'gitlab.com' in repo_url:
                                        metadata.repository = repo_url
                                
                                if gem_metadata.get('documentation_uri'):
                                    documentation_url = gem_metadata['documentation_uri']
                        
                        if metadata.repository == NO_ASSERTION and metadata.homepage != NO_ASSERTION:
                            if 'github.com' in metadata.homepage or 'gitlab.com' in metadata.homepage:
                                metadata.repository = metadata.homepage
                        
                        # Extract authors
                        if gemspec.get('authors'):
                            authors = gemspec['authors']
                            if isinstance(authors, list):
                                for author in authors:
                                    if isinstance(author, str):
                                        metadata.authors.append({
                                            'name': author,
                                            'email': NO_ASSERTION
                                        })
                        elif gemspec.get('author'):
                            author = gemspec['author']
                            if isinstance(author, str):
                                metadata.authors.append({
                                    'name': author,
                                    'email': NO_ASSERTION
                                })
                        
                        # Extract email if available
                        if gemspec.get('email'):
                            emails = gemspec['email']
                            if isinstance(emails, list) and metadata.authors:
                                for i, email in enumerate(emails):
                                    if i < len(metadata.authors):
                                        metadata.authors[i]['email'] = email
                            elif isinstance(emails, str) and metadata.authors:
                                metadata.authors[0]['email'] = emails
                        
                        # Extract license
                        license_text = None
                        if gemspec.get('licenses'):
                            licenses = gemspec['licenses']
                            if isinstance(licenses, list) and licenses:
                                license_text = licenses[0]
                            elif isinstance(licenses, str):
                                license_text = licenses
                        elif gemspec.get('license'):
                            license_text = gemspec['license']
                        
                        if license_text:
                            # Format license text for better oslili detection
                            # If it's just a short license identifier, add "License:" prefix
                            if len(license_text) < 20 and not ':' in license_text:
                                formatted_text = f"License: {license_text}"
                            else:
                                formatted_text = license_text
                            
                            license_infos = self.detect_licenses_from_text(
                                formatted_text, 
                                filename='metadata.gz'
                            )
                            if license_infos:
                                metadata.licenses.extend(license_infos)
                        
                        # Extract dependencies
                        if gemspec.get('dependencies'):
                            deps = gemspec['dependencies']
                            if isinstance(deps, list):
                                for dep in deps:
                                    if hasattr(dep, 'name') and hasattr(dep, 'requirement'):
                                        # Handle Gem::Dependency objects from YAML
                                        dep_type = 'runtime' if hasattr(dep, 'type') and dep.type == ':runtime' else 'development'
                                        dep_str = f"{dep.name} {str(dep.requirement) if dep.requirement else '*'}"
                                        metadata.dependencies[dep_type].append(dep_str)
                                    elif isinstance(dep, dict):
                                        # Handle dictionary format
                                        dep_type = dep.get('type', 'runtime')
                                        dep_str = f"{dep.get('name', 'unknown')} {dep.get('version_requirements', '*')}"
                                        if dep_type not in metadata.dependencies:
                                            metadata.dependencies[dep_type] = []
                                        metadata.dependencies[dep_type].append(dep_str)
                        
                        # Extract requirements (alternative to dependencies)
                        if gemspec.get('requirements'):
                            requirements = gemspec['requirements']
                            if isinstance(requirements, list):
                                for req in requirements:
                                    if isinstance(req, str):
                                        build_tools.append(req)
                        
                        # Platform information
                        if gemspec.get('platform'):
                            platform = str(gemspec['platform'])
                            if platform and platform != 'ruby':
                                metadata.classifiers.append(f'Platform :: {platform}')
                        
                        # Ruby version requirement
                        if gemspec.get('required_ruby_version'):
                            ruby_version = str(gemspec['required_ruby_version'])
                            metadata.classifiers.append(f'Ruby :: {ruby_version}')
                        
                        # Rubygems version requirement
                        if gemspec.get('required_rubygems_version'):
                            rubygems_version = str(gemspec['required_rubygems_version'])
                            build_tools.append(f'rubygems {rubygems_version}')
                
                # Try to detect license from LICENSE file in data.tar.gz
                if not metadata.licenses:
                    data_member = None
                    for member in gem_tar.getmembers():
                        if member.name == 'data.tar.gz':
                            data_member = member
                            break
                    
                    if data_member:
                        data_file = gem_tar.extractfile(data_member)
                        if data_file:
                            # Open the nested tar.gz
                            with gzip.open(data_file, 'rb') as gz:
                                with tarfile.open(fileobj=gz, mode='r') as data_tar:
                                    for member in data_tar.getmembers():
                                        if member.isfile() and 'LICENSE' in member.name.upper():
                                            license_file = data_tar.extractfile(member)
                                            if license_file:
                                                license_content = license_file.read().decode('utf-8', errors='ignore')
                                                license_infos = self.detect_licenses_from_text(
                                                    license_content,
                                                    filename=member.name
                                                )
                                                if license_infos:
                                                    metadata.licenses.extend(license_infos)
                                                break

        except Exception as e:
            logger.error(f"Error extracting Ruby gem metadata: {e}")
            raise

        # Extract copyright information
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with tarfile.open(str(package_path), 'r:*') as tar:
                    # Extract limited files for copyright scanning
                    members = tar.getmembers()[:100]  # Limit to first 100 files
                    tar.extractall(temp_dir, members=members)
                
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

        # Query online APIs if enabled
        if self.online_mode and metadata.name != NO_ASSERTION:
            # This would be handled by the main extractor
            pass

        return metadata

    def can_extract(self, package_path: str) -> bool:
        """Check if this extractor can handle the package."""
        path = Path(package_path)
        if path.suffix == '.gem':
            return True
        
        # Check if it's a tar file that might be a gem
        if path.suffix in ['.tar', '.gz']:
            try:
                with tarfile.open(package_path, 'r') as tar:
                    members = tar.getnames()
                    # Ruby gems contain metadata.gz, data.tar.gz, and checksums.yaml.gz
                    if 'metadata.gz' in members and 'data.tar.gz' in members:
                        return True
            except:
                pass
        
        return False
    
    def detect_package_type(self, package_path: Path) -> Optional[str]:
        """Detect if the package is a Ruby gem."""
        if package_path.suffix == '.gem':
            return 'ruby_gem'
        
        # Check if it's a tar file that might be a gem
        if package_path.suffix in ['.tar', '.gz']:
            try:
                with tarfile.open(str(package_path), 'r') as tar:
                    members = tar.getnames()
                    # Ruby gems contain metadata.gz, data.tar.gz, and checksums.yaml.gz
                    if 'metadata.gz' in members and 'data.tar.gz' in members:
                        return 'ruby_gem'
            except:
                pass
        
        return None