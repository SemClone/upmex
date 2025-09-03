"""
License detection using oslili library.
"""

import tempfile
import os
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging

try:
    from semantic_copycat_oslili import LicenseCopyrightDetector, Config
    OSLILI_AVAILABLE = True
except ImportError:
    try:
        # Alternative import path
        from oslili import LicenseCopyrightDetector, Config
        OSLILI_AVAILABLE = True
    except ImportError:
        OSLILI_AVAILABLE = False
        LicenseCopyrightDetector = None
        Config = None

logger = logging.getLogger(__name__)


class OsliliLicenseDetector:
    """License detector using semantic-copycat-oslili library."""
    
    def __init__(self):
        """Initialize the oslili detector with optimized configuration."""
        if not OSLILI_AVAILABLE:
            raise ImportError("oslili library is not available. Install with: pip install semantic-copycat-oslili")
        
        config = Config(
            similarity_threshold=0.95,  # High confidence threshold
            max_recursion_depth=3,      # Limit depth for package scanning
            max_extraction_depth=1,     # Don't extract nested archives
            thread_count=1,             # Single thread for consistency
            verbose=False,
            debug=False,
            license_filename_patterns=[
                "LICENSE*",
                "LICENCE*",
                "COPYING*",
                "NOTICE*",
                "COPYRIGHT*",
            ],
            custom_aliases={
                "Apache 2": "Apache-2.0",
                "Apache 2.0": "Apache-2.0",
                "Apache License 2.0": "Apache-2.0",
                "MIT License": "MIT",
                "BSD License": "BSD-3-Clause",
                "The MIT License": "MIT",
            }
        )
        self.detector = LicenseCopyrightDetector(config)
    
    def detect_from_file(self, file_path: str, content: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Detect licenses from a file.
        
        Args:
            file_path: Path to the file (used for naming)
            content: Optional file content to analyze
            
        Returns:
            List of detected licenses with confidence scores
        """
        licenses = []
        
        if content is None:
            return licenses
            
        try:
            # Write content to temporary file for oslili to process
            with tempfile.NamedTemporaryFile(mode='w', suffix=Path(file_path).suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                # Process with oslili
                result = self.detector.process_local_path(tmp_path)
                
                # Convert oslili results to our format
                for detected in result.licenses:
                    license_info = {
                        "name": detected.name,
                        "spdx_id": detected.spdx_id,
                        "confidence": detected.confidence,
                        "confidence_level": self._get_confidence_level(detected.confidence),
                        "source": f"oslili_{detected.detection_method}",
                        "file": file_path,
                    }
                    
                    # Only include high-confidence matches
                    if detected.confidence >= 0.8:
                        licenses.append(license_info)
                        
            finally:
                # Clean up temp file
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.warning(f"Oslili detection failed for {file_path}: {e}")
            
        return licenses
    
    def detect_from_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """
        Detect licenses from a directory.
        
        Args:
            dir_path: Path to the directory
            
        Returns:
            List of detected licenses with confidence scores
        """
        licenses = []
        
        try:
            # Process directory with oslili
            result = self.detector.process_local_path(dir_path)
            
            # Convert oslili results to our format
            seen_licenses = set()
            for detected in result.licenses:
                # Create unique key to avoid duplicates
                key = (detected.spdx_id, detected.source_file)
                if key in seen_licenses:
                    continue
                seen_licenses.add(key)
                
                license_info = {
                    "name": detected.name,
                    "spdx_id": detected.spdx_id,
                    "confidence": detected.confidence,
                    "confidence_level": self._get_confidence_level(detected.confidence),
                    "source": f"oslili_{detected.detection_method}",
                    "file": detected.source_file or "unknown",
                }
                
                # Only include high-confidence matches
                if detected.confidence >= 0.8:
                    licenses.append(license_info)
                    
        except Exception as e:
            logger.warning(f"Oslili directory detection failed for {dir_path}: {e}")
            
        return licenses
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Convert numeric confidence to level string."""
        if confidence >= 0.95:
            return "exact"
        elif confidence >= 0.85:
            return "high"
        elif confidence >= 0.70:
            return "medium"
        else:
            return "low"


def detect_licenses(file_path: str, content: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Main entry point for license detection using oslili.
    
    Args:
        file_path: Path to the file
        content: Optional file content
        
    Returns:
        List of detected licenses
    """
    detector = OsliliLicenseDetector()
    return detector.detect_from_file(file_path, content)


def detect_licenses_from_directory(dir_path: str) -> List[Dict[str, Any]]:
    """
    Detect licenses from a directory using oslili.
    
    Args:
        dir_path: Path to the directory
        
    Returns:
        List of detected licenses
    """
    detector = OsliliLicenseDetector()
    return detector.detect_from_directory(dir_path)