"""UPMEX - Universal Package Metadata Extractor."""

__version__ = "0.2.0"
__author__ = "Oscar Valenzuela B."
__email__ = "oscar.valenzuela.b@gmail.com"

# Suppress urllib3 SSL warning on macOS with LibreSSL
import warnings
try:
    import urllib3
    warnings.filterwarnings('ignore', category=urllib3.exceptions.NotOpenSSLWarning)
except (ImportError, AttributeError):
    # urllib3 not installed or doesn't have NotOpenSSLWarning
    pass

from .core.extractor import PackageExtractor
from .core.models import PackageMetadata, LicenseInfo

__all__ = [
    "PackageExtractor",
    "PackageMetadata", 
    "LicenseInfo",
    "__version__",
]