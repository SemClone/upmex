"""Rust crate package extractor."""

import tarfile
import gzip
import toml
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .base import BaseExtractor
from ..core.models import NO_ASSERTION, PackageMetadata, PackageType

logger = logging.getLogger(__name__)


class RustExtractor(BaseExtractor):
    """Extract metadata from Rust crate packages."""

    # __init__ removed - using BaseExtractor

    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a Rust crate package.
        
        Rust crates are gzipped tar archives containing:
        - Cargo.toml: package manifest with metadata
        - Cargo.toml.orig: original manifest (sometimes present)
        - src/: source code
        - LICENSE files
        """
        package_path = Path(package_path)
        metadata = PackageMetadata(
            name=NO_ASSERTION,
            version=NO_ASSERTION,
            package_type=PackageType.RUST_CRATE,
            description=NO_ASSERTION,
            homepage=NO_ASSERTION,
            repository=NO_ASSERTION
        )
        metadata.dependencies = {'normal': [], 'dev': [], 'build': []}

        try:
            # Open the crate file (gzipped tar archive)
            with tarfile.open(package_path, 'r:gz') as crate_tar:
                cargo_toml = None
                cargo_toml_orig = None
                license_files = []
                
                # Find Cargo.toml and LICENSE files
                for member in crate_tar.getmembers():
                    if member.isfile():
                        # Look for Cargo.toml (usually in format: package-version/Cargo.toml)
                        if member.name.endswith('Cargo.toml.orig'):
                            cargo_toml_orig = member
                        elif member.name.endswith('Cargo.toml'):
                            cargo_toml = member
                        elif 'LICENSE' in member.name.upper() or 'LICENCE' in member.name.upper():
                            license_files.append(member)
                
                # Prefer Cargo.toml.orig if available (it's the unmodified original)
                manifest_member = cargo_toml_orig or cargo_toml
                
                if manifest_member:
                    # Extract and parse Cargo.toml
                    manifest_file = crate_tar.extractfile(manifest_member)
                    if manifest_file:
                        manifest_content = manifest_file.read().decode('utf-8')
                        cargo_data = toml.loads(manifest_content)
                        
                        # Extract package metadata
                        package = cargo_data.get('package', {})
                        
                        if package.get('name'):
                            metadata.name = package['name']
                        
                        if package.get('version'):
                            metadata.version = package['version']
                        
                        if package.get('description'):
                            metadata.description = package['description']
                        
                        if package.get('homepage'):
                            metadata.homepage = package['homepage']
                        
                        if package.get('repository'):
                            metadata.repository = package['repository']
                        
                        if package.get('documentation'):
                            metadata.raw_metadata['documentation'] = package['documentation']
                        
                        # Extract authors
                        if package.get('authors'):
                            authors = package['authors']
                            if isinstance(authors, list):
                                for author in authors:
                                    if isinstance(author, str):
                                        # Parse "Name <email>" format
                                        parsed = self.parse_author(author)
                                        if parsed:
                                            metadata.authors.append(parsed)
                                        else:
                                            metadata.authors.append({
                                                'name': author,
                                                'email': NO_ASSERTION
                                            })
                        
                        # Extract keywords
                        if package.get('keywords'):
                            keywords = package['keywords']
                            if isinstance(keywords, list):
                                metadata.keywords = keywords
                        
                        # Extract categories (Rust-specific classification)
                        if package.get('categories'):
                            categories = package['categories']
                            if isinstance(categories, list):
                                for category in categories:
                                    metadata.classifiers.append(f"Category :: {category}")
                        
                        # Extract edition (Rust version)
                        if package.get('edition'):
                            edition = package['edition']
                            metadata.classifiers.append(f"Rust Edition :: {edition}")
                        
                        # Extract license
                        if package.get('license'):
                            license_text = package['license']
                            # Format license text for better oslili detection
                            if len(license_text) < 20 and ':' not in license_text:
                                formatted_text = f"License: {license_text}"
                            else:
                                formatted_text = license_text
                            license_infos = self.detect_licenses_from_text(
                                formatted_text,
                                filename='Cargo.toml'
                            )
                            if license_infos:
                                metadata.licenses.extend(license_infos)
                        
                        # Extract dependencies
                        for dep_type in ['dependencies', 'dev-dependencies', 'build-dependencies']:
                            deps = cargo_data.get(dep_type, {})
                            if isinstance(deps, dict):
                                # Determine target list based on dependency type
                                if dep_type == 'dependencies':
                                    target_list = metadata.dependencies['normal']
                                elif dep_type == 'dev-dependencies':
                                    target_list = metadata.dependencies['dev']
                                else:  # build-dependencies
                                    target_list = metadata.dependencies['build']
                                
                                for dep_name, dep_spec in deps.items():
                                    if isinstance(dep_spec, str):
                                        # Simple version string
                                        target_list.append(f"{dep_name} {dep_spec}")
                                    elif isinstance(dep_spec, dict):
                                        # Complex dependency specification
                                        version = dep_spec.get('version', '*')
                                        features = dep_spec.get('features', [])
                                        if features:
                                            target_list.append(f"{dep_name} {version} (features: {', '.join(features)})")
                                        else:
                                            target_list.append(f"{dep_name} {version}")
                        
                        # Extract target-specific dependencies
                        for section_name, section_data in cargo_data.items():
                            if section_name.startswith('target.') and isinstance(section_data, dict):
                                # Extract target platform
                                target_platform = section_name.split('.', 1)[1]
                                
                                # Process dependencies for this target
                                for dep_type in ['dependencies', 'dev-dependencies', 'build-dependencies']:
                                    target_deps = section_data.get(dep_type, {})
                                    if target_deps:
                                        # Add platform classifier if not already present
                                        platform_classifier = f"Platform :: {target_platform}"
                                        if platform_classifier not in metadata.classifiers:
                                            metadata.classifiers.append(platform_classifier)
                                        
                                        # We'll add these to the main dependency lists with platform annotation
                                        if dep_type == 'dependencies':
                                            target_list = metadata.dependencies['normal']
                                        elif dep_type == 'dev-dependencies':
                                            target_list = metadata.dependencies['dev']
                                        else:
                                            target_list = metadata.dependencies['build']
                                        
                                        for dep_name, dep_spec in target_deps.items():
                                            if isinstance(dep_spec, str):
                                                target_list.append(f"{dep_name} {dep_spec} (target: {target_platform})")
                                            elif isinstance(dep_spec, dict):
                                                version = dep_spec.get('version', '*')
                                                target_list.append(f"{dep_name} {version} (target: {target_platform})")
                
                # Try to detect license from LICENSE files if not already found
                if not metadata.licenses and license_files:
                    for license_member in license_files:
                        license_file = crate_tar.extractfile(license_member)
                        if license_file:
                            license_content = license_file.read().decode('utf-8', errors='ignore')
                            # Only format if it's a short identifier (not full license text)
                            if len(license_content) < 20 and ':' not in license_content:
                                formatted_text = f"License: {license_content}"
                            else:
                                formatted_text = license_content
                            license_infos = self.detect_licenses_from_text(
                                formatted_text,
                                filename=license_member.name
                            )
                            if license_infos:
                                metadata.licenses.extend(license_infos)
                                break  # Use first detected license

        except Exception as e:
            logger.error(f"Error extracting Rust crate metadata: {e}")
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
        
        # Check for .crate extension
        if path.suffix == '.crate':
            return True
        
        # Check if it's a tar.gz that might be a crate
        if path.name.endswith('.tar.gz'):
            try:
                with tarfile.open(package_path, 'r:gz') as tar:
                    for member in tar.getmembers():
                        # Look for Cargo.toml which indicates a Rust crate
                        if 'Cargo.toml' in member.name:
                            return True
            except:
                pass
        
        return False

    def detect_package_type(self, package_path: Path) -> Optional[str]:
        """Detect if the package is a Rust crate."""
        if package_path.suffix == '.crate':
            return 'rust_crate'
        
        # Check if it's a tar.gz that contains Cargo.toml
        if package_path.name.endswith('.tar.gz'):
            try:
                with tarfile.open(str(package_path), 'r:gz') as tar:
                    for member in tar.getmembers():
                        if 'Cargo.toml' in member.name:
                            return 'rust_crate'
            except:
                pass
        
        return None