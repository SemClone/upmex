"""Base extractor class for all package types."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from ..core.models import PackageMetadata


class BaseExtractor(ABC):
    """Abstract base class for package extractors."""
    
    @abstractmethod
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a package.
        
        Args:
            package_path: Path to the package file
            
        Returns:
            PackageMetadata object with extracted information
        """
        pass
    
    @abstractmethod
    def can_extract(self, package_path: str) -> bool:
        """Check if this extractor can handle the package.
        
        Args:
            package_path: Path to the package file
            
        Returns:
            True if this extractor can handle the package
        """
        pass