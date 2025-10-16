"""Conda package extractor for .tar.bz2 and .conda formats."""

import json
import tarfile
import zipfile
import tempfile
import os
import io
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False
from .base import BaseExtractor
from ..core.models import PackageMetadata, PackageType, NO_ASSERTION


class CondaExtractor(BaseExtractor):
    """Extract metadata from Conda packages."""
    
    # __init__ removed - using BaseExtractor
    
    def can_extract(self, package_path: str) -> bool:
        """Check if this extractor can handle the package.
        
        Args:
            package_path: Path to the package file
            
        Returns:
            True if this extractor can handle Conda packages
        """
        path = Path(package_path)
        
        # .conda files (new format)
        if path.suffix == '.conda':
            return True
        
        # .tar.bz2 files that might be conda packages
        if path.name.endswith('.tar.bz2'):
            # Try to check if it's a conda package by looking for info/index.json
            try:
                if self._is_conda_tar_bz2(package_path):
                    return True
            except Exception:
                pass
        
        return False
    
    def _is_conda_tar_bz2(self, package_path: str) -> bool:
        """Check if a .tar.bz2 file is a conda package.
        
        Args:
            package_path: Path to the archive
            
        Returns:
            True if it contains conda package structure
        """
        try:
            with tarfile.open(package_path, 'r:bz2') as tar:
                # Look for info/index.json which is required in conda packages
                for member in tar.getmembers():
                    if member.name == 'info/index.json':
                        return True
        except Exception:
            pass
        return False
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a Conda package.
        
        Args:
            package_path: Path to the Conda package
            
        Returns:
            PackageMetadata object
        """
        path = Path(package_path)
        
        try:
            # Extract metadata based on package format
            if path.suffix == '.conda':
                return self._extract_from_conda_format(package_path)
            elif path.name.endswith('.tar.bz2'):
                return self._extract_from_tar_bz2(package_path)
            else:
                return self._create_minimal_metadata(
                    name=path.stem,
                    version=NO_ASSERTION,
                    error="Unsupported Conda package format"
                )
        except Exception as e:
            return self._create_minimal_metadata(
                name=path.stem,
                version=NO_ASSERTION,
                error=str(e)
            )
    
    def _extract_from_conda_format(self, package_path: str) -> PackageMetadata:
        """Extract metadata from .conda format (zip-based).

        Args:
            package_path: Path to .conda package

        Returns:
            PackageMetadata object
        """
        metadata_dict = {}
        recipe_dict = {}

        try:
            with zipfile.ZipFile(package_path, 'r') as zf:
                # Check for new conda format v2 with .tar.zst files
                info_files = [f for f in zf.namelist() if f.startswith('info-') and f.endswith('.tar.zst')]

                if info_files and HAS_ZSTD:
                    # New format with zstandard compression
                    for info_file in info_files:
                        with zf.open(info_file) as zst_file:
                            # Decompress zstd
                            dctx = zstd.ZstdDecompressor()
                            decompressed = dctx.decompress(zst_file.read())

                            # Extract tar content
                            tar_io = io.BytesIO(decompressed)
                            with tarfile.open(fileobj=tar_io, mode='r') as tar:
                                # Look for index.json
                                for member in tar.getmembers():
                                    if member.name == 'info/index.json':
                                        f = tar.extractfile(member)
                                        if f:
                                            metadata_dict = json.load(f)
                                            break

                                # Look for recipe files
                                for member in tar.getmembers():
                                    if member.name == 'info/recipe/meta.yaml':
                                        f = tar.extractfile(member)
                                        if f:
                                            recipe_dict = yaml.safe_load(f)
                                            break
                                    elif member.name == 'info/recipe.json':
                                        f = tar.extractfile(member)
                                        if f:
                                            recipe_dict = json.load(f)
                                            break

                # Old format: Extract info/index.json (if directly in zip)
                elif 'info/index.json' in zf.namelist():
                    with zf.open('info/index.json') as f:
                        metadata_dict = json.load(f)

                    # Extract info/recipe/meta.yaml (optional)
                    if 'info/recipe/meta.yaml' in zf.namelist():
                        with zf.open('info/recipe/meta.yaml') as f:
                            recipe_dict = yaml.safe_load(f)
                    elif 'info/recipe.json' in zf.namelist():
                        with zf.open('info/recipe.json') as f:
                            recipe_dict = json.load(f)
        except Exception as e:
            return self._create_minimal_metadata(
                name=Path(package_path).stem,
                version=NO_ASSERTION,
                error=f"Failed to extract .conda package: {e}"
            )

        return self._parse_conda_metadata(metadata_dict, recipe_dict)
    
    def _extract_from_tar_bz2(self, package_path: str) -> PackageMetadata:
        """Extract metadata from .tar.bz2 conda package.
        
        Args:
            package_path: Path to .tar.bz2 package
            
        Returns:
            PackageMetadata object
        """
        metadata_dict = {}
        recipe_dict = {}
        
        try:
            with tarfile.open(package_path, 'r:bz2') as tar:
                # Extract info/index.json (required)
                try:
                    index_member = tar.getmember('info/index.json')
                    index_file = tar.extractfile(index_member)
                    if index_file:
                        metadata_dict = json.load(index_file)
                except KeyError:
                    pass
                
                # Extract info/recipe/meta.yaml (optional)
                try:
                    recipe_member = tar.getmember('info/recipe/meta.yaml')
                    recipe_file = tar.extractfile(recipe_member)
                    if recipe_file:
                        recipe_dict = yaml.safe_load(recipe_file)
                except KeyError:
                    # Try JSON format
                    try:
                        recipe_member = tar.getmember('info/recipe.json')
                        recipe_file = tar.extractfile(recipe_member)
                        if recipe_file:
                            recipe_dict = json.load(recipe_file)
                    except KeyError:
                        pass
        except Exception as e:
            return self._create_minimal_metadata(
                name=Path(package_path).stem,
                version=NO_ASSERTION,
                error=f"Failed to extract .tar.bz2 package: {e}"
            )
        
        return self._parse_conda_metadata(metadata_dict, recipe_dict)
    
    def _parse_conda_metadata(self, index_json: Dict[str, Any], recipe: Dict[str, Any]) -> PackageMetadata:
        """Parse metadata from conda package files.
        
        Args:
            index_json: Contents of info/index.json
            recipe: Contents of info/recipe/meta.yaml or recipe.json
            
        Returns:
            PackageMetadata object
        """
        # Extract basic metadata from index.json
        name = index_json.get('name', NO_ASSERTION)
        version = index_json.get('version', NO_ASSERTION)
        build = index_json.get('build', NO_ASSERTION)
        build_number = index_json.get('build_number')
        
        # Get description from recipe if available, otherwise from index
        description = NO_ASSERTION
        if recipe:
            about = recipe.get('about', {})
            description = about.get('summary') or about.get('description', NO_ASSERTION)
        
        # Homepage and repository
        homepage = NO_ASSERTION
        repository = NO_ASSERTION
        if recipe:
            about = recipe.get('about', {})
            homepage = about.get('home', NO_ASSERTION)
            # Try to get repository from dev_url or home
            repository = about.get('dev_url') or about.get('home', NO_ASSERTION)
        
        # Extract dependencies
        dependencies = {}
        
        # From index.json
        if 'depends' in index_json:
            runtime_deps = []
            for dep in index_json.get('depends', []):
                runtime_deps.append(dep)
            if runtime_deps:
                dependencies['runtime'] = runtime_deps
        
        # From recipe (more detailed)
        if recipe:
            requirements = recipe.get('requirements', {})
            
            # Build dependencies
            build_deps = requirements.get('build', [])
            if build_deps:
                dependencies['build'] = build_deps
            
            # Host dependencies
            host_deps = requirements.get('host', [])
            if host_deps:
                dependencies['host'] = host_deps
            
            # Run dependencies (override if more detailed)
            run_deps = requirements.get('run', [])
            if run_deps:
                dependencies['runtime'] = run_deps
        
        # Extract license
        licenses = []
        license_info = index_json.get('license') or (recipe.get('about', {}).get('license') if recipe else None)
        if license_info:
            # Format license text for better oslili detection
            if len(license_info) < 20 and ':' not in license_info:
                formatted_text = f"License: {license_info}"
            else:
                formatted_text = license_info
            detected = self.detect_licenses_from_text(formatted_text)
            if detected:
                licenses.extend(detected)
        
        # Extract authors/maintainers
        authors = []
        if recipe:
            # Try to get from recipe maintainers
            extra = recipe.get('extra', {})
            maintainers = extra.get('recipe-maintainers', [])
            for maintainer in maintainers:
                if isinstance(maintainer, str):
                    authors.append({'name': maintainer, 'email': NO_ASSERTION})
            
            # Also check about section
            about = recipe.get('about', {})
            if not authors and 'author' in about:
                author = about['author']
                if isinstance(author, str):
                    authors.append({'name': author, 'email': NO_ASSERTION})
        
        # Keywords from features and other metadata
        keywords = []
        
        # Add channel if present
        channel = index_json.get('channel')
        if channel:
            keywords.append(f"channel:{channel}")
        
        # Add subdir/platform
        subdir = index_json.get('subdir')
        if subdir:
            keywords.append(subdir)
        
        # Add features
        features = index_json.get('features', [])
        keywords.extend(features)
        
        # Add track features
        track_features = index_json.get('track_features', [])
        keywords.extend(track_features)
        
        # Build complete raw metadata
        raw_metadata = {
            'index': index_json,
            'build': build,
            'build_number': build_number
        }
        if recipe:
            raw_metadata['recipe'] = recipe
        
        return PackageMetadata(
            name=name,
            version=version,
            package_type=PackageType.CONDA,
            description=description,
            homepage=homepage,
            repository=repository,
            authors=authors,
            licenses=licenses,
            dependencies=dependencies,
            keywords=keywords,
            raw_metadata=raw_metadata
        )
    
    def _create_minimal_metadata(self, name: str, version: str, error: str = None) -> PackageMetadata:
        """Create minimal metadata when extraction fails.
        
        Args:
            name: Package name
            version: Package version
            error: Optional error message
            
        Returns:
            PackageMetadata with minimal information
        """
        return PackageMetadata(
            name=name,
            version=version,
            package_type=PackageType.CONDA,
            description=NO_ASSERTION,
            homepage=NO_ASSERTION,
            repository=NO_ASSERTION,
            authors=[],
            licenses=[],
            dependencies={},
            keywords=[],
            raw_metadata={'extraction_error': error} if error else {}
        )