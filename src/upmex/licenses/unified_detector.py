"""
Unified license detector that uses OSLiLi for all license detection.
"""

import os
import tempfile
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging

# OSLiLi detection is now handled via subprocess only

from .oslili_subprocess import OsliliSubprocessDetector

logger = logging.getLogger(__name__)


class UnifiedLicenseDetector:
    """Unified license detector using OSLiLi."""

    def __init__(self):
        """Initialize the detector."""
        # Use subprocess version for copyright support
        self.oslili_detector = OsliliSubprocessDetector()

    def detect_licenses(self, file_path: str, content: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Detect licenses using OSLiLi.

        Args:
            file_path: Path to the file
            content: Optional file content

        Returns:
            List of detected licenses
        """
        licenses = []
        seen_licenses = set()

        # Use OSLiLi for all detection
        try:
            oslili_licenses = self.oslili_detector.detect_from_file(file_path, content)
            for license_info in oslili_licenses:
                # Filter known false positives
                if license_info.get('spdx_id') == 'Pixar':
                    continue
                key = (license_info.get('spdx_id'), license_info.get('file'))
                if key not in seen_licenses:
                    licenses.append(license_info)
                    seen_licenses.add(key)
        except Exception as e:
            logger.debug(f"OSLiLi detection failed: {e}")

        return licenses

    def detect_licenses_from_directory(self, dir_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect licenses and copyrights from a directory.

        Args:
            dir_path: Path to the directory

        Returns:
            Dictionary with 'licenses' and 'copyrights' lists
        """
        licenses = []
        copyrights = []
        seen_licenses = set()

        # Use OSLiLi for directory scanning
        try:
            oslili_result = self.oslili_detector.detect_from_directory(dir_path)

            # Handle new format with separate licenses and copyrights
            if isinstance(oslili_result, dict):
                # Handle licenses
                if 'licenses' in oslili_result:
                    for license_info in oslili_result['licenses']:
                        # Filter known false positives
                        if license_info.get('spdx_id') == 'Pixar':
                            continue
                        key = (license_info.get('spdx_id'), license_info.get('file'))
                        if key not in seen_licenses:
                            licenses.append(license_info)
                            seen_licenses.add(key)

                # Handle copyrights
                if 'copyrights' in oslili_result:
                    copyrights = oslili_result['copyrights']
            elif isinstance(oslili_result, list):
                # Backward compatibility - old format
                for license_info in oslili_result:
                    if license_info.get('spdx_id') == 'Pixar':
                        continue
                    key = (license_info.get('spdx_id'), license_info.get('file'))
                    if key not in seen_licenses:
                        licenses.append(license_info)
                        seen_licenses.add(key)
        except Exception as e:
            logger.debug(f"OSLiLi directory detection failed: {e}")

        return {"licenses": licenses, "copyrights": copyrights}

    def detect_from_metadata(self, metadata: Dict, file_path: str = "metadata") -> Optional[Dict[str, Any]]:
        """
        Detect license from metadata dictionary.
        OSLiLi now handles metadata extraction internally.

        Args:
            metadata: Metadata dictionary
            file_path: Optional file path for context

        Returns:
            License info if detected
        """
        # Create a temporary file with the metadata content to let OSLiLi handle it
        if 'license' in metadata:
            license_value = metadata['license']
            if isinstance(license_value, str) and license_value:
                # Create a simple package.json-like content for OSLiLi to parse
                content = f'{{"license": "{license_value}"}}'
                try:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name

                    try:
                        licenses = self.oslili_detector.detect_from_file(file_path, content)
                        if licenses:
                            return licenses[0]  # Return first detected license
                    finally:
                        os.unlink(tmp_path)
                except Exception as e:
                    logger.debug(f"Metadata detection via OSLiLi failed: {e}")

        return None


# Global instance for backward compatibility
_detector = None


def get_detector() -> UnifiedLicenseDetector:
    """Get or create the global detector instance."""
    global _detector
    if _detector is None:
        _detector = UnifiedLicenseDetector()
    return _detector


def detect_licenses(file_path: str, content: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Detect licenses from a file.

    Args:
        file_path: Path to the file
        content: Optional file content

    Returns:
        List of detected licenses
    """
    detector = get_detector()
    return detector.detect_licenses(file_path, content)


def detect_licenses_from_directory(dir_path: str) -> List[Dict[str, Any]]:
    """
    Detect licenses from a directory.

    Args:
        dir_path: Path to the directory

    Returns:
        List of detected licenses (for backward compatibility)
    """
    detector = get_detector()
    result = detector.detect_licenses_from_directory(dir_path)
    # For backward compatibility, return just licenses
    if isinstance(result, dict) and 'licenses' in result:
        return result['licenses']
    return result


def detect_licenses_and_copyrights_from_directory(dir_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Detect licenses and copyrights from a directory.

    Args:
        dir_path: Path to the directory

    Returns:
        Dictionary with 'licenses' and 'copyrights' lists
    """
    detector = get_detector()
    return detector.detect_licenses_from_directory(dir_path)


def find_and_detect_licenses(extract_dir: str) -> List[Dict[str, Any]]:
    """
    Find and detect licenses in extracted directory.

    Args:
        extract_dir: Directory to scan

    Returns:
        List of detected licenses
    """
    return detect_licenses_from_directory(extract_dir)