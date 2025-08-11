"""License detection module with SPDX support."""

from .enhanced_detector import EnhancedLicenseDetector
from .spdx_manager import SPDXLicenseManager, initialize_spdx_data

__all__ = [
    'EnhancedLicenseDetector',
    'SPDXLicenseManager',
    'initialize_spdx_data'
]