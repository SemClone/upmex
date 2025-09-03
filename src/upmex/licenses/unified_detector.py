"""
Unified license detector that uses oslili as primary method with fallback to regex.
"""

import os
import tempfile
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging

try:
    from .oslili_detector import OsliliLicenseDetector
    OSLILI_IMPORT_AVAILABLE = True
except ImportError:
    OSLILI_IMPORT_AVAILABLE = False
    OsliliLicenseDetector = None

from .oslili_subprocess import OsliliSubprocessDetector
from ..utils.license_detector import LicenseDetector
from ..core.models import LicenseInfo

logger = logging.getLogger(__name__)


class UnifiedLicenseDetector:
    """Unified license detector using oslili with regex fallback."""
    
    def __init__(self):
        """Initialize both detectors."""
        # Always use subprocess version for copyright support
        # OsliliLicenseDetector doesn't extract copyrights
        self.oslili_detector = OsliliSubprocessDetector()
            
        self.regex_detector = LicenseDetector(enable_fuzzy=False)  # Disable fuzzy to avoid false positives
    
    def detect_licenses(self, file_path: str, content: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Detect licenses using oslili as primary method.
        
        Args:
            file_path: Path to the file
            content: Optional file content
            
        Returns:
            List of detected licenses
        """
        licenses = []
        seen_licenses = set()
        
        # Try oslili first
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
            logger.debug(f"Oslili detection failed, will try regex: {e}")
        
        # If no licenses found with oslili, try regex detection
        if not licenses and content:
            try:
                regex_result = self.regex_detector.detect_license_from_text(content, file_path)
                if regex_result:
                    license_info = {
                        "name": regex_result.name,
                        "spdx_id": regex_result.spdx_id,
                        "confidence": regex_result.confidence,
                        "confidence_level": regex_result.confidence_level.value,
                        "source": "regex_pattern",
                        "file": file_path,
                    }
                    key = (license_info.get('spdx_id'), license_info.get('file'))
                    if key not in seen_licenses:
                        licenses.append(license_info)
                        seen_licenses.add(key)
            except Exception as e:
                logger.debug(f"Regex detection failed: {e}")
        
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
        
        # Try oslili first
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
            logger.debug(f"Oslili directory detection failed: {e}")
        
        # If no licenses found, scan for LICENSE files with regex
        if not licenses:
            try:
                for root, _, files in os.walk(dir_path):
                    for file in files:
                        if self.regex_detector.is_license_file(file):
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                regex_result = self.regex_detector.detect_license_from_text(content, file)
                                if regex_result:
                                    license_info = {
                                        "name": regex_result.name,
                                        "spdx_id": regex_result.spdx_id,
                                        "confidence": regex_result.confidence,
                                        "confidence_level": regex_result.confidence_level.value,
                                        "source": "regex_pattern",
                                        "file": file,
                                    }
                                    key = (license_info.get('spdx_id'), license_info.get('file'))
                                    if key not in seen_licenses:
                                        licenses.append(license_info)
                                        seen_licenses.add(key)
                                        break  # Found license, stop searching
                            except Exception as e:
                                logger.debug(f"Failed to read {file_path}: {e}")
            except Exception as e:
                logger.debug(f"Directory scan failed: {e}")
        
        return {"licenses": licenses, "copyrights": copyrights}
    
    def detect_from_metadata(self, metadata: Dict) -> Optional[Dict[str, Any]]:
        """
        Detect license from metadata dictionary.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            License info if detected
        """
        # Use regex detector for metadata as it's optimized for this
        try:
            regex_result = self.regex_detector.detect_license_from_metadata(metadata)
            if regex_result:
                return {
                    "name": regex_result.name,
                    "spdx_id": regex_result.spdx_id,
                    "confidence": 0.6,  # Lower confidence for metadata-only detection
                    "confidence_level": "medium",
                    "source": "regex_pattern",
                    "file": "metadata",
                }
        except Exception as e:
            logger.debug(f"Metadata detection failed: {e}")
        
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