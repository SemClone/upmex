"""Shared utilities for confidence level conversion."""

from ..core.models import LicenseConfidenceLevel


def get_confidence_level(confidence: float) -> LicenseConfidenceLevel:
    """Convert numeric confidence to LicenseConfidenceLevel enum.
    
    Args:
        confidence: Numeric confidence score (0.0 to 1.0)
        
    Returns:
        LicenseConfidenceLevel enum value
    """
    if confidence >= 0.95:
        return LicenseConfidenceLevel.EXACT
    elif confidence >= 0.8:
        return LicenseConfidenceLevel.HIGH
    elif confidence >= 0.6:
        return LicenseConfidenceLevel.MEDIUM
    elif confidence >= 0.3:
        return LicenseConfidenceLevel.LOW
    else:
        return LicenseConfidenceLevel.NONE


def get_confidence_level_string(confidence: float) -> str:
    """Convert numeric confidence to string representation.
    
    Args:
        confidence: Numeric confidence score (0.0 to 1.0)
        
    Returns:
        String representation of confidence level
    """
    if confidence >= 0.95:
        return "exact"
    elif confidence >= 0.85:
        return "high"
    elif confidence >= 0.70:
        return "medium"
    else:
        return "low"