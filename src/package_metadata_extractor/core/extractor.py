"""Main package extractor orchestrator."""

import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from .models import PackageMetadata, PackageType
from ..extractors.python_extractor import PythonExtractor
from ..extractors.npm_extractor import NpmExtractor
from ..extractors.java_extractor import JavaExtractor
from ..utils.package_detector import detect_package_type


class PackageExtractor:
    """Main class for extracting package metadata."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the package extractor.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.extractors = {
            PackageType.PYTHON_WHEEL: PythonExtractor(),
            PackageType.PYTHON_SDIST: PythonExtractor(),
            PackageType.NPM: NpmExtractor(),
            PackageType.MAVEN: JavaExtractor(),
            PackageType.JAR: JavaExtractor(),
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
        
        return metadata
    
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