"""License detection using regex patterns for common license identifiers."""

import re
from typing import Optional, List, Dict
from ..core.models import LicenseInfo
from ..utils.confidence import get_confidence_level
from ..utils.patterns import is_license_file
from .dice_sorensen import FuzzyLicenseMatcher


class LicenseDetector:
    """Regex-based license detection for metadata files and license identifiers."""
    
    # Common SPDX license identifiers and their variations
    SPDX_LICENSES = {
        'MIT': ['MIT', 'MIT License', 'The MIT License', 'MIT-style'],
        'Apache-2.0': ['Apache-2.0', 'Apache 2.0', 'Apache License 2.0', 'Apache License, Version 2.0', 'Apache Software License 2.0', 'ASL 2.0'],
        'Apache-1.1': ['Apache-1.1', 'Apache 1.1', 'Apache License 1.1', 'Apache License, Version 1.1'],
        'GPL-3.0': ['GPL-3.0', 'GPLv3', 'GPL v3', 'GNU GPL v3', 'GNU General Public License v3', 'GNU General Public License v3.0'],
        'GPL-3.0-or-later': ['GPL-3.0-or-later', 'GPL-3.0+', 'GPLv3+', 'GPL v3 or later'],
        'GPL-2.0': ['GPL-2.0', 'GPLv2', 'GPL v2', 'GNU GPL v2', 'GNU General Public License v2', 'GNU General Public License v2.0'],
        'GPL-2.0-or-later': ['GPL-2.0-or-later', 'GPL-2.0+', 'GPLv2+', 'GPL v2 or later'],
        'LGPL-3.0': ['LGPL-3.0', 'LGPLv3', 'LGPL v3', 'GNU LGPL v3', 'GNU Lesser General Public License v3'],
        'LGPL-2.1': ['LGPL-2.1', 'LGPLv2.1', 'LGPL v2.1', 'GNU LGPL v2.1', 'GNU Lesser General Public License v2.1'],
        'BSD-3-Clause': ['BSD-3-Clause', 'BSD 3-Clause', 'BSD License', '3-Clause BSD', 'New BSD', 'Modified BSD', 'BSD-3'],
        'BSD-2-Clause': ['BSD-2-Clause', 'BSD 2-Clause', '2-Clause BSD', 'Simplified BSD', 'FreeBSD', 'BSD-2'],
        'ISC': ['ISC', 'ISC License', 'Internet Systems Consortium License'],
        'MPL-2.0': ['MPL-2.0', 'MPL 2.0', 'Mozilla Public License 2.0', 'Mozilla Public License, Version 2.0'],
        'MPL-1.1': ['MPL-1.1', 'MPL 1.1', 'Mozilla Public License 1.1', 'Mozilla Public License, Version 1.1'],
        'CC0-1.0': ['CC0-1.0', 'CC0 1.0', 'Creative Commons Zero', 'Public Domain', 'CC0'],
        'Unlicense': ['Unlicense', 'The Unlicense', 'UNLICENSE'],
        'WTFPL': ['WTFPL', 'Do What The F*ck You Want To Public License', 'WTFPL-2.0'],
        'Zlib': ['Zlib', 'zlib License', 'zlib/libpng License'],
        'Python-2.0': ['Python-2.0', 'PSF', 'Python Software Foundation License', 'PSF License'],
        'Artistic-2.0': ['Artistic-2.0', 'Artistic License 2.0', 'Perl License'],
        'EPL-1.0': ['EPL-1.0', 'Eclipse Public License 1.0', 'EPL v1.0'],
        'EPL-2.0': ['EPL-2.0', 'Eclipse Public License 2.0', 'EPL v2.0'],
        'AGPL-3.0': ['AGPL-3.0', 'AGPLv3', 'GNU Affero General Public License v3', 'GNU AGPL v3'],
        'Proprietary': ['Proprietary', 'Commercial', 'All Rights Reserved', 'Closed Source'],
    }
    
    # Patterns for detecting license in various metadata formats
    LICENSE_FIELD_PATTERNS = [
        # Python setup.py/setup.cfg/pyproject.toml patterns
        (re.compile(r'license\s*[=:]\s*["\']([^"\']+)["\']', re.IGNORECASE), 1.0),
        (re.compile(r'License\s*::\s*([^\n]+)', re.IGNORECASE), 0.9),  # Classifier
        (re.compile(r'Classifier:\s*License\s*::\s*OSI Approved\s*::\s*([^\n]+)', re.IGNORECASE), 1.0),
        
        # package.json patterns
        (re.compile(r'"license"\s*:\s*"([^"]+)"', re.IGNORECASE), 1.0),
        (re.compile(r'"licenses"\s*:\s*\[\s*{\s*"type"\s*:\s*"([^"]+)"', re.IGNORECASE), 1.0),
        
        # Maven POM patterns
        (re.compile(r'<license>\s*<name>([^<]+)</name>', re.IGNORECASE), 1.0),
        (re.compile(r'<licenses>\s*<license>\s*<name>([^<]+)</name>', re.IGNORECASE), 1.0),
        
        # SPDX-License-Identifier pattern (common in source files)
        (re.compile(r'SPDX-License-Identifier:\s*([^\s\n]+)', re.IGNORECASE), 1.0),
        
        # Copyright header patterns
        (re.compile(r'Licensed under the\s+([^,\n]+)(?:\s+License)?', re.IGNORECASE), 0.8),
        (re.compile(r'This (?:software|project|code) is licensed under\s+([^,\n]+)', re.IGNORECASE), 0.8),
        
        # README patterns
        (re.compile(r'##?\s*License\s*\n+.*?(?:under|licensed|released under)\s+(?:the\s+)?([^\n,]+)', re.IGNORECASE | re.DOTALL), 0.7),
        (re.compile(r'##?\s*License\s*\n+([^\n]+)', re.IGNORECASE), 0.6),
    ]
    
    
    def __init__(self, enable_fuzzy: bool = True):
        """Initialize the license detector.
        
        Args:
            enable_fuzzy: Whether to enable Dice-Sørensen fuzzy matching
        """
        self._build_regex_cache()
        self.enable_fuzzy = enable_fuzzy
        if enable_fuzzy:
            self.fuzzy_matcher = FuzzyLicenseMatcher()
    
    def _build_regex_cache(self):
        """Build compiled regex patterns for all license variations."""
        self.license_patterns = {}
        for spdx_id, variations in self.SPDX_LICENSES.items():
            # Create pattern that matches any variation
            escaped_variations = [re.escape(v) for v in variations]
            pattern = re.compile(
                r'\b(?:' + '|'.join(escaped_variations) + r')\b',
                re.IGNORECASE
            )
            self.license_patterns[spdx_id] = pattern
    
    def detect_license_from_text(self, text: str, filename: Optional[str] = None) -> Optional[LicenseInfo]:
        """Detect license from text content using regex patterns.
        
        Args:
            text: Text content to analyze
            filename: Optional filename for context
            
        Returns:
            LicenseInfo if license detected, None otherwise
        """
        if not text:
            return None
        
        # First, try field-specific patterns (higher confidence)
        for pattern, confidence_boost in self.LICENSE_FIELD_PATTERNS:
            match = pattern.search(text)
            if match:
                license_text = match.group(1).strip()
                spdx_id = self._normalize_to_spdx(license_text)
                
                if spdx_id:
                    return LicenseInfo(
                        spdx_id=spdx_id,
                        name=license_text,
                        confidence=min(1.0, 0.9 * confidence_boost),
                        confidence_level=get_confidence_level(0.9),
                        detection_method='regex_field',
                        file_path=filename
                    )
        
        # Then try to match known license patterns in the text
        for spdx_id, pattern in self.license_patterns.items():
            if pattern.search(text):
                # Check context to determine confidence
                confidence = self._calculate_confidence(text, spdx_id, filename)
                
                return LicenseInfo(
                    spdx_id=spdx_id,
                    name=self.SPDX_LICENSES[spdx_id][0],
                    confidence=confidence,
                    confidence_level=self._get_confidence_level(confidence),
                    detection_method='regex_pattern',
                    file_path=filename
                )
        
        # If no regex match found and fuzzy matching is enabled, try Dice-Sørensen
        if self.enable_fuzzy and len(text) > 100:
            fuzzy_result = self.fuzzy_matcher.match(text, confidence_threshold=0.6)
            if fuzzy_result:
                license_id, confidence, method = fuzzy_result
                return LicenseInfo(
                    spdx_id=license_id,
                    name=self.SPDX_LICENSES.get(license_id, [license_id])[0],
                    confidence=confidence,
                    confidence_level=self._get_confidence_level(confidence),
                    detection_method=method,
                    file_path=filename
                )
        
        return None
    
    def detect_license_from_metadata(self, metadata: Dict) -> Optional[LicenseInfo]:
        """Detect license from structured metadata (dict).
        
        Args:
            metadata: Dictionary containing metadata fields
            
        Returns:
            LicenseInfo if license detected, None otherwise
        """
        # Check common license fields
        license_fields = ['license', 'licenses', 'licence', 'licences']
        
        for field in license_fields:
            if field in metadata:
                value = metadata[field]
                
                # Handle string value
                if isinstance(value, str):
                    spdx_id = self._normalize_to_spdx(value)
                    if spdx_id:
                        return LicenseInfo(
                            spdx_id=spdx_id,
                            name=value,
                            confidence=0.95,
                            confidence_level=get_confidence_level(0.9),
                            detection_method='regex_metadata'
                        )
                
                # Handle list of licenses
                elif isinstance(value, list) and value:
                    first_license = value[0]
                    if isinstance(first_license, str):
                        spdx_id = self._normalize_to_spdx(first_license)
                    elif isinstance(first_license, dict):
                        license_name = first_license.get('type') or first_license.get('name')
                        if license_name:
                            spdx_id = self._normalize_to_spdx(license_name)
                        else:
                            spdx_id = None
                    else:
                        spdx_id = None
                
                # Handle dict with type field
                elif isinstance(value, dict):
                    license_name = value.get('type') or value.get('name')
                    if license_name:
                        spdx_id = self._normalize_to_spdx(license_name)
                    else:
                        spdx_id = None
                else:
                    spdx_id = None
                
                if spdx_id:
                    return LicenseInfo(
                        spdx_id=spdx_id,
                        name=str(value) if not isinstance(value, list) else str(first_license),
                        confidence=0.95,
                        confidence_level=get_confidence_level(0.9),
                        detection_method='regex_metadata'
                    )
        
        # Check classifiers (Python packages)
        if 'classifiers' in metadata:
            for classifier in metadata.get('classifiers', []):
                if 'License ::' in classifier:
                    # Extract license from classifier
                    parts = classifier.split('::')
                    if len(parts) >= 3:
                        license_name = parts[-1].strip()
                        spdx_id = self._normalize_to_spdx(license_name)
                        if spdx_id:
                            return LicenseInfo(
                                spdx_id=spdx_id,
                                name=license_name,
                                confidence=0.9,
                                confidence_level=get_confidence_level(0.9),
                                detection_method='regex_classifier'
                            )
        
        return None
    
    def _normalize_to_spdx(self, license_text: str) -> Optional[str]:
        """Normalize a license string to SPDX identifier.
        
        Args:
            license_text: License text to normalize
            
        Returns:
            SPDX identifier if matched, None otherwise
        """
        if not license_text:
            return None
        
        # Clean the input
        license_text = license_text.strip()
        
        # Direct SPDX ID match (case-insensitive)
        for spdx_id in self.SPDX_LICENSES:
            if license_text.upper() == spdx_id.upper():
                return spdx_id
        
        # Check against all known variations
        for spdx_id, variations in self.SPDX_LICENSES.items():
            for variation in variations:
                if license_text.lower() == variation.lower():
                    return spdx_id
        
        # Partial match with known patterns
        for spdx_id, pattern in self.license_patterns.items():
            if pattern.search(license_text):
                return spdx_id
        
        return None
    
    def _calculate_confidence(self, text: str, spdx_id: str, filename: Optional[str]) -> float:
        """Calculate confidence score based on context.
        
        Args:
            text: Text where license was found
            spdx_id: Detected SPDX identifier
            filename: Optional filename for context
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence = 0.5  # Base confidence for pattern match
        
        # Boost if in a license file
        if filename:
            filename_lower = filename.lower()
            if 'license' in filename_lower or 'copying' in filename_lower:
                confidence += 0.3
            elif 'readme' in filename_lower:
                confidence += 0.1
            elif any(filename_lower.endswith(ext) for ext in ['.py', '.js', '.java', '.c', '.h']):
                confidence += 0.2  # Source file with SPDX identifier
        
        # Boost if SPDX-License-Identifier is present
        if 'SPDX-License-Identifier' in text:
            confidence += 0.2
        
        # Boost if copyright notice is present
        if re.search(r'Copyright|©|\(C\)', text, re.IGNORECASE):
            confidence += 0.1
        
        return min(1.0, max(0.6, confidence))  # Minimum 0.6 for any detection
    
    def _get_confidence_level(self, confidence: float):
        """Convert numeric confidence to confidence level.
        
        Args:
            confidence: Numeric confidence score
            
        Returns:
            LicenseConfidenceLevel enum value
        """
        return get_confidence_level(confidence)
    
    def is_license_file(self, filename: str) -> bool:
        """Check if a filename indicates a license file.
        
        Args:
            filename: Name of the file
            
        Returns:
            True if likely a license file
        """
        return is_license_file(filename)
    
    def detect_multiple_licenses(self, text: str) -> List[LicenseInfo]:
        """Detect multiple licenses in text (e.g., dual licensing).
        
        Args:
            text: Text to analyze
            
        Returns:
            List of detected licenses
        """
        licenses = []
        found_licenses = set()
        
        # Check for explicit dual/multi-licensing patterns
        dual_pattern = re.compile(
            r'dual[- ]licens|double[- ]licens|(?:either|choice of).*licens',
            re.IGNORECASE
        )
        is_dual = dual_pattern.search(text) is not None
        
        # Find all matching licenses
        for spdx_id, pattern in self.license_patterns.items():
            if pattern.search(text) and spdx_id not in found_licenses:
                confidence = 0.8 if is_dual else self._calculate_confidence(text, spdx_id, None)
                licenses.append(LicenseInfo(
                    spdx_id=spdx_id,
                    name=self.SPDX_LICENSES[spdx_id][0],
                    confidence=confidence,
                    confidence_level=self._get_confidence_level(confidence),
                    detection_method='regex_multi'
                ))
                found_licenses.add(spdx_id)
        
        # Also try fuzzy matching if enabled
        if self.enable_fuzzy and len(text) > 100:
            fuzzy_matches = self.fuzzy_matcher.match_multiple(text, max_results=3)
            for license_id, confidence, method in fuzzy_matches:
                if license_id not in found_licenses and confidence > 0.6:
                    licenses.append(LicenseInfo(
                        spdx_id=license_id,
                        name=self.SPDX_LICENSES.get(license_id, [license_id])[0],
                        confidence=confidence,
                        confidence_level=self._get_confidence_level(confidence),
                        detection_method=method
                    ))
                    found_licenses.add(license_id)
        
        return licenses
    
    def detect_with_dice_sorensen(self, text: str, threshold: float = 0.6) -> Optional[LicenseInfo]:
        """Detect license using only Dice-Sørensen coefficient.
        
        Args:
            text: Text to analyze
            threshold: Minimum similarity threshold
            
        Returns:
            LicenseInfo if detected, None otherwise
        """
        if not self.enable_fuzzy:
            return None
        
        result = self.fuzzy_matcher.match(text, confidence_threshold=threshold)
        if result:
            license_id, confidence, method = result
            return LicenseInfo(
                spdx_id=license_id,
                name=self.SPDX_LICENSES.get(license_id, [license_id])[0],
                confidence=confidence,
                confidence_level=self._get_confidence_level(confidence),
                detection_method=method
            )
        
        return None