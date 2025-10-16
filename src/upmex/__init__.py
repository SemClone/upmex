"""UPMEX - Universal Package Metadata Extractor."""

__version__ = "1.6.1"
__author__ = "Oscar Valenzuela B."
__email__ = "oscar.valenzuela.b@gmail.com"

# Suppress urllib3 SSL warning on macOS with LibreSSL
import warnings
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

from .core.extractor import PackageExtractor
from .core.models import PackageMetadata, LicenseInfo

__all__ = [
    "PackageExtractor",
    "PackageMetadata", 
    "LicenseInfo",
    "__version__",
]