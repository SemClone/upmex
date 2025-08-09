"""UPMEX - Universal Package Metadata Extractor."""

__version__ = "0.1.0"
__author__ = "Oscar Valenzuela B."
__email__ = "oscar.valenzuela.b@gmail.com"

from .core.extractor import PackageExtractor
from .core.models import PackageMetadata, LicenseInfo

__all__ = [
    "PackageExtractor",
    "PackageMetadata", 
    "LicenseInfo",
    "__version__",
]