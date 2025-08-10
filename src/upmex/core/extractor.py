"""Main package extractor orchestrator."""

import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from .models import PackageMetadata, PackageType, NO_ASSERTION
from ..extractors.python_extractor import PythonExtractor
from ..extractors.npm_extractor import NpmExtractor
from ..extractors.java_extractor import JavaExtractor
from ..extractors.gradle_extractor import GradleExtractor
from ..extractors.cocoapods_extractor import CocoaPodsExtractor
from ..extractors.conda_extractor import CondaExtractor
from ..extractors.ruby_extractor import RubyExtractor
from ..extractors.rust_extractor import RustExtractor
from ..extractors.go_extractor import GoExtractor
from ..extractors.nuget_extractor import NuGetExtractor
from ..utils.package_detector import detect_package_type
from ..api.clearlydefined import ClearlyDefinedAPI
from ..api.ecosystems import EcosystemsAPI


class PackageExtractor:
    """Main class for extracting package metadata."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the package extractor.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.online_mode = self.config.get('online_mode', False)
        
        # Initialize extractors with online mode
        self.extractors = {
            PackageType.PYTHON_WHEEL: PythonExtractor(online_mode=self.online_mode),
            PackageType.PYTHON_SDIST: PythonExtractor(online_mode=self.online_mode),
            PackageType.NPM: NpmExtractor(online_mode=self.online_mode),
            PackageType.MAVEN: JavaExtractor(online_mode=self.online_mode),
            PackageType.JAR: JavaExtractor(online_mode=self.online_mode),
            PackageType.GRADLE: GradleExtractor(online_mode=self.online_mode),
            PackageType.COCOAPODS: CocoaPodsExtractor(online_mode=self.online_mode),
            PackageType.CONDA: CondaExtractor(online_mode=self.online_mode),
            PackageType.RUBY_GEM: RubyExtractor(online_mode=self.online_mode),
            PackageType.RUST_CRATE: RustExtractor(online_mode=self.online_mode),
            PackageType.GO_MODULE: GoExtractor(online_mode=self.online_mode),
            PackageType.NUGET: NuGetExtractor(online_mode=self.online_mode),
        }
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a package file.
        
        Args:
            package_path: Path to the package file
            
        Returns:
            PackageMetadata object containing extracted information
        """
        path = Path(package_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Package file not found: {package_path}")
        
        # Detect package type
        package_type = detect_package_type(package_path)
        
        # Get file metadata
        file_size = path.stat().st_size
        file_hash = self._calculate_hash(package_path)
        
        # Extract metadata using appropriate extractor
        if package_type in self.extractors:
            extractor = self.extractors[package_type]
            metadata = extractor.extract(package_path)
        else:
            # Fallback to basic metadata
            metadata = PackageMetadata(
                name=path.stem,
                package_type=package_type
            )
        
        # Add file metadata
        metadata.file_size = file_size
        metadata.file_hash = file_hash
        metadata.package_type = package_type
        
        # Enrich with APIs if online mode is enabled
        if self.online_mode:
            self._enrich_with_apis(metadata)
        
        return metadata
    
    def _enrich_with_apis(self, metadata: PackageMetadata) -> None:
        """Enrich metadata using external APIs.
        
        Args:
            metadata: Package metadata to enrich
        """
        try:
            # Extract namespace and name for API calls
            namespace = None
            name = metadata.name
            
            # Handle namespaced packages
            if metadata.package_type in [PackageType.MAVEN, PackageType.JAR]:
                # Maven format: groupId:artifactId
                if ':' in name:
                    parts = name.split(':', 1)
                    namespace = parts[0]
                    name = parts[1]
            elif metadata.package_type == PackageType.NPM:
                # NPM scoped packages: @scope/package
                if name.startswith('@') and '/' in name:
                    parts = name.split('/', 1)
                    namespace = parts[0][1:]  # Remove @
                    name = parts[1]
            
            # Try ClearlyDefined
            cd_api = ClearlyDefinedAPI(api_key=self.config.get('clearlydefined_api_key'))
            cd_def = cd_api.get_definition(metadata.package_type, namespace, name, metadata.version)
            if cd_def:
                # Extract license info
                license_info = cd_api.extract_license_info(cd_def)
                if license_info and not metadata.licenses:
                    from .models import LicenseInfo
                    metadata.licenses.append(LicenseInfo(
                        spdx_id=license_info['spdx_id'],
                        confidence=license_info['confidence'],
                        detection_method='ClearlyDefined API'
                    ))
            
            # Try Ecosyste.ms
            eco_api = EcosystemsAPI(api_key=self.config.get('ecosystems_api_key'))
            eco_info = eco_api.get_package_info(metadata.package_type, metadata.name, metadata.version)
            if eco_info:
                eco_metadata = eco_api.extract_metadata(eco_info)
                
                # Fill in missing fields
                if not metadata.description and eco_metadata.get('description'):
                    metadata.description = eco_metadata['description']
                
                if metadata.repository == NO_ASSERTION and eco_metadata.get('repository'):
                    metadata.repository = eco_metadata['repository']
                
                if not metadata.keywords and eco_metadata.get('keywords'):
                    metadata.keywords = eco_metadata['keywords']
                
        except Exception as e:
            print(f"Error enriching with APIs: {e}")
    
    def _calculate_hash(self, file_path: str, algorithm: str = "sha256") -> str:
        """Calculate file hash.
        
        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use
            
        Returns:
            Hex digest of the file hash
        """
        hash_func = hashlib.new(algorithm)
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
        return hash_func.hexdigest()