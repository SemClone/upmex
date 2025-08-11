"""Enhanced license detector using SPDX license texts and multiple detection methods."""

import re
from typing import List, Optional, Dict, Tuple
from pathlib import Path
from difflib import SequenceMatcher

from ..core.models import LicenseInfo, LicenseConfidenceLevel
from ..utils.dice_sorensen import DiceSorensenMatcher
from .spdx_manager import SPDXLicenseManager


class EnhancedLicenseDetector:
    """Enhanced license detection using SPDX texts and multiple algorithms."""
    
    def __init__(self, enable_spdx: bool = True):
        """Initialize enhanced license detector.
        
        Args:
            enable_spdx: Whether to use full SPDX text matching
        """
        self.enable_spdx = enable_spdx
        
        # Initialize components
        self.dice_matcher = DiceSorensenMatcher(n_gram_size=3)  # Use trigrams for better accuracy
        
        if enable_spdx:
            self.spdx_manager = SPDXLicenseManager()
            self.spdx_manager.load_or_download()
            self.spdx_manager.load_texts()
            self.spdx_manager.load_hashes()
            
            # Add SPDX texts to Dice-Sørensen matcher
            self._populate_dice_matcher()
    
    def _populate_dice_matcher(self):
        """Populate Dice-Sørensen matcher with SPDX license texts."""
        for license_id, text in self.spdx_manager.license_texts.items():
            # Add normalized version for better matching
            normalized = self.spdx_manager.normalize_text(text)
            
            # Extract key phrases (first 500 chars and important sections)
            if len(normalized) > 500:
                # Take beginning and distinctive middle sections
                key_text = normalized[:500]
                
                # Look for key sections
                sections = ['permission', 'condition', 'limitation', 'warranty', 'liability']
                for section in sections:
                    idx = normalized.find(section)
                    if idx > 0:
                        snippet = normalized[max(0, idx-50):min(len(normalized), idx+200)]
                        self.dice_matcher.add_license_snippet(license_id, snippet)
            else:
                key_text = normalized
            
            self.dice_matcher.add_license_snippet(license_id, key_text)
    
    def detect_license(self, text: str, filename: Optional[str] = None) -> List[LicenseInfo]:
        """Detect licenses using multiple methods.
        
        Args:
            text: Text to analyze
            filename: Optional filename for context
            
        Returns:
            List of detected licenses with confidence scores
        """
        if not text or len(text) < 20:
            return []
        
        results = []
        detected_licenses = set()
        
        # Method 1: Exact SPDX identifier matching
        spdx_match = self._detect_spdx_identifier(text)
        if spdx_match:
            results.append(spdx_match)
            detected_licenses.add(spdx_match.spdx_id)
        
        # Method 2: Fuzzy hash matching (if SPDX enabled)
        if self.enable_spdx and len(text) > 100:
            fuzzy_matches = self.spdx_manager.find_license_by_fuzzy_hash(text, threshold=0.7)
            for license_id, similarity in fuzzy_matches[:2]:  # Top 2 matches
                if license_id not in detected_licenses:
                    results.append(LicenseInfo(
                        spdx_id=license_id,
                        name=self._get_license_name(license_id),
                        confidence=similarity,
                        confidence_level=self._get_confidence_level(similarity),
                        detection_method='fuzzy_hash_lsh',
                        file_path=filename
                    ))
                    detected_licenses.add(license_id)
        
        # Method 3: Dice-Sørensen coefficient matching
        dice_matches = self._detect_with_dice_sorensen(text, filename)
        for match in dice_matches:
            if match.spdx_id not in detected_licenses:
                results.append(match)
                detected_licenses.add(match.spdx_id)
        
        # Method 4: Full text similarity (if SPDX enabled and text is substantial)
        if self.enable_spdx and len(text) > 500:
            full_text_matches = self._detect_with_full_text_similarity(text, filename)
            for match in full_text_matches:
                if match.spdx_id not in detected_licenses:
                    results.append(match)
                    detected_licenses.add(match.spdx_id)
        
        # Sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        return results[:3]  # Return top 3 matches
    
    def _detect_spdx_identifier(self, text: str) -> Optional[LicenseInfo]:
        """Detect SPDX-License-Identifier in text.
        
        Args:
            text: Text to search
            
        Returns:
            LicenseInfo if found, None otherwise
        """
        # Look for SPDX-License-Identifier
        pattern = re.compile(r'SPDX-License-Identifier:\s*([^\s\n]+)', re.IGNORECASE)
        match = pattern.search(text)
        
        if match:
            license_id = match.group(1).strip()
            
            # Validate against known SPDX IDs
            if self.enable_spdx:
                if license_id in self.spdx_manager.licenses:
                    return LicenseInfo(
                        spdx_id=license_id,
                        name=self._get_license_name(license_id),
                        confidence=1.0,
                        confidence_level=LicenseConfidenceLevel.EXACT,
                        detection_method='spdx_identifier',
                        file_path=None
                    )
            else:
                # Basic validation
                return LicenseInfo(
                    spdx_id=license_id,
                    name=license_id,
                    confidence=0.95,
                    confidence_level=LicenseConfidenceLevel.HIGH,
                    detection_method='spdx_identifier',
                    file_path=None
                )
        
        return None
    
    def _detect_with_dice_sorensen(self, text: str, filename: Optional[str] = None) -> List[LicenseInfo]:
        """Detect licenses using Dice-Sørensen coefficient.
        
        Args:
            text: Text to analyze
            filename: Optional filename
            
        Returns:
            List of detected licenses
        """
        results = []
        
        # Normalize text for comparison
        normalized = self.spdx_manager.normalize_text(text) if self.enable_spdx else self._simple_normalize(text)
        
        # Get all matches above threshold
        matches = self.dice_matcher.match_all_licenses(normalized)
        
        for license_id, score in matches[:3]:  # Top 3
            if score > 0.6:  # Minimum threshold
                results.append(LicenseInfo(
                    spdx_id=license_id,
                    name=self._get_license_name(license_id),
                    confidence=score,
                    confidence_level=self._get_confidence_level(score),
                    detection_method='dice_sorensen',
                    file_path=filename
                ))
        
        return results
    
    def _detect_with_full_text_similarity(self, text: str, filename: Optional[str] = None) -> List[LicenseInfo]:
        """Detect licenses using full text similarity comparison.
        
        Args:
            text: Text to analyze
            filename: Optional filename
            
        Returns:
            List of detected licenses
        """
        if not self.enable_spdx:
            return []
        
        results = []
        normalized_input = self.spdx_manager.normalize_text(text)
        
        # Compare with each license text
        similarities = []
        for license_id, license_text in self.spdx_manager.license_texts.items():
            normalized_license = self.spdx_manager.normalize_text(license_text)
            
            # Use SequenceMatcher for similarity
            matcher = SequenceMatcher(None, normalized_input, normalized_license)
            ratio = matcher.ratio()
            
            if ratio > 0.7:  # Minimum threshold
                similarities.append((license_id, ratio))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Take top matches
        for license_id, ratio in similarities[:2]:
            results.append(LicenseInfo(
                spdx_id=license_id,
                name=self._get_license_name(license_id),
                confidence=ratio,
                confidence_level=self._get_confidence_level(ratio),
                detection_method='full_text_similarity',
                file_path=filename
            ))
        
        return results
    
    def _simple_normalize(self, text: str) -> str:
        """Simple text normalization when SPDX is not available.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = ' '.join(text.split())
        return text
    
    def _get_license_name(self, license_id: str) -> str:
        """Get human-readable license name.
        
        Args:
            license_id: SPDX license identifier
            
        Returns:
            License name
        """
        if self.enable_spdx:
            info = self.spdx_manager.get_license_info(license_id)
            if info:
                return info.get('name', license_id)
        return license_id
    
    def _get_confidence_level(self, confidence: float) -> LicenseConfidenceLevel:
        """Convert confidence score to level.
        
        Args:
            confidence: Numeric confidence
            
        Returns:
            Confidence level
        """
        if confidence >= 0.95:
            return LicenseConfidenceLevel.EXACT
        elif confidence >= 0.8:
            return LicenseConfidenceLevel.HIGH
        elif confidence >= 0.6:
            return LicenseConfidenceLevel.MEDIUM
        elif confidence >= 0.4:
            return LicenseConfidenceLevel.LOW
        else:
            return LicenseConfidenceLevel.NONE
    
    def extract_license_files(self, archive_path: str) -> List[Tuple[str, str]]:
        """Extract potential license files from an archive.
        
        Args:
            archive_path: Path to archive file
            
        Returns:
            List of (filename, content) tuples
        """
        license_patterns = [
            re.compile(r'LICENSE(?:\.\w+)?$', re.IGNORECASE),
            re.compile(r'LICENCE(?:\.\w+)?$', re.IGNORECASE),
            re.compile(r'COPYING(?:\.\w+)?$', re.IGNORECASE),
            re.compile(r'COPYRIGHT(?:\.\w+)?$', re.IGNORECASE),
            re.compile(r'NOTICE(?:\.\w+)?$', re.IGNORECASE),
            re.compile(r'LEGAL(?:\.\w+)?$', re.IGNORECASE),
            re.compile(r'PATENTS(?:\.\w+)?$', re.IGNORECASE),
        ]
        
        results = []
        path = Path(archive_path)
        
        if path.suffix in ['.whl', '.jar', '.zip']:
            import zipfile
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for name in zf.namelist():
                    basename = Path(name).name
                    if any(pattern.match(basename) for pattern in license_patterns):
                        try:
                            content = zf.read(name).decode('utf-8', errors='ignore')
                            results.append((name, content))
                        except:
                            pass
        
        elif path.suffix in ['.tar', '.gz', '.tgz', '.tar.gz']:
            import tarfile
            with tarfile.open(archive_path, 'r:*') as tf:
                for member in tf.getmembers():
                    if member.isfile():
                        basename = Path(member.name).name
                        if any(pattern.match(basename) for pattern in license_patterns):
                            try:
                                f = tf.extractfile(member)
                                if f:
                                    content = f.read().decode('utf-8', errors='ignore')
                                    results.append((member.name, content))
                            except:
                                pass
        
        return results
    
    def detect_from_package(self, package_path: str) -> List[LicenseInfo]:
        """Detect licenses from a package file.
        
        Args:
            package_path: Path to package file
            
        Returns:
            List of detected licenses
        """
        all_licenses = []
        detected_ids = set()
        
        # Extract and analyze license files
        license_files = self.extract_license_files(package_path)
        
        for filename, content in license_files:
            licenses = self.detect_license(content, filename)
            for lic in licenses:
                if lic.spdx_id not in detected_ids:
                    all_licenses.append(lic)
                    detected_ids.add(lic.spdx_id)
        
        # Sort by confidence
        all_licenses.sort(key=lambda x: x.confidence, reverse=True)
        
        return all_licenses