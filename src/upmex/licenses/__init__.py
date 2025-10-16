"""License detection module with SPDX support."""

from .spdx_manager import SPDXLicenseManager, initialize_spdx_data

__all__ = [
    'SPDXLicenseManager',
    'initialize_spdx_data'
]