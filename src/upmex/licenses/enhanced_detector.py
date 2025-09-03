"""Enhanced license detector - now using oslili for improved accuracy."""

# Re-export unified detector functions for backward compatibility
from .unified_detector import (
    detect_licenses,
    detect_licenses_from_directory,
    find_and_detect_licenses,
    UnifiedLicenseDetector,
)

from typing import List, Optional
from ..core.models import LicenseInfo
from ..utils.confidence import get_confidence_level


class EnhancedLicenseDetector:
    """Enhanced license detection - now powered by oslili."""
    
    def __init__(self, enable_spdx: bool = True):
        """Initialize enhanced license detector.
        
        Args:
            enable_spdx: Whether to use full SPDX text matching (kept for compatibility)
        """
        self.enable_spdx = enable_spdx
        # Use unified detector internally
        self.unified_detector = UnifiedLicenseDetector()
    
    def detect_license(self, text: str, filename: Optional[str] = None) -> List[LicenseInfo]:
        """Detect licenses using oslili.
        
        Args:
            text: Text to analyze
            filename: Optional filename for context
            
        Returns:
            List of detected licenses with confidence scores
        """
        if not text or len(text.strip()) < 2:  # Allow short license identifiers
            return []
        
        # Use unified detector
        licenses = self.unified_detector.detect_licenses(filename or "unknown", text)
        
        # Convert to LicenseInfo objects for compatibility
        results = []
        for lic in licenses[:3]:  # Return top 3 matches
            results.append(LicenseInfo(
                spdx_id=lic.get('spdx_id', 'Unknown'),
                name=lic.get('name', 'Unknown'),
                confidence=lic.get('confidence', 0.0),
                confidence_level=get_confidence_level(lic.get('confidence', 0.0)),
                detection_method=lic.get('source', 'oslili'),
                file_path=filename
            ))
        
        return results