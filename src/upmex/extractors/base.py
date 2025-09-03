"""Base extractor class for all package types."""

import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union
from pathlib import Path

from ..core.models import PackageMetadata, LicenseInfo, LicenseConfidenceLevel, NO_ASSERTION
from ..utils.license_detector import LicenseDetector
from ..utils.patterns import LICENSE_FILE_NAMES
from ..licenses.enhanced_detector import EnhancedLicenseDetector
from ..utils.author_parser import parse_author_string, parse_author_list
from ..utils.archive_utils import find_file_in_archive, extract_from_tar, extract_from_zip


class BaseExtractor(ABC):
    """Abstract base class for package extractors."""
    
    # Common license file patterns (using shared patterns)
    LICENSE_FILE_PATTERNS = LICENSE_FILE_NAMES
    
    def __init__(self, online_mode: bool = False):
        """Initialize extractor.
        
        Args:
            online_mode: Whether to fetch additional data from online sources
        """
        self.online_mode = online_mode
        self.license_detector = LicenseDetector()
        
        # Try to use enhanced detector if available
        try:
            self.enhanced_detector = EnhancedLicenseDetector(enable_spdx=True)
            self.use_enhanced = True
        except:
            self.enhanced_detector = None
            self.use_enhanced = False
    
    @abstractmethod
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a package.
        
        Args:
            package_path: Path to the package file
            
        Returns:
            PackageMetadata object with extracted information
        """
        pass
    
    @abstractmethod
    def can_extract(self, package_path: str) -> bool:
        """Check if this extractor can handle the package.
        
        Args:
            package_path: Path to the package file
            
        Returns:
            True if this extractor can handle the package
        """
        pass
    
    def parse_author(self, author: Union[str, Dict]) -> Optional[Dict[str, str]]:
        """Parse author string using common utility.
        
        Args:
            author: Author string or dict
            
        Returns:
            Parsed author dictionary
        """
        return parse_author_string(author)
    
    def parse_authors(self, authors: Union[str, List, Dict]) -> List[Dict[str, str]]:
        """Parse multiple authors using common utility.
        
        Args:
            authors: Author(s) in various formats
            
        Returns:
            List of parsed author dictionaries
        """
        return parse_author_list(authors)
    
    def detect_licenses_from_text(self, 
                                 text: str, 
                                 filename: Optional[str] = None) -> List[LicenseInfo]:
        """Detect licenses from text content.
        
        Args:
            text: Text content to analyze
            filename: Optional filename for context
            
        Returns:
            List of detected licenses
        """
        licenses = []
        
        if not text:
            return licenses
        
        # Try enhanced detector first if available
        if self.use_enhanced and self.enhanced_detector:
            try:
                enhanced_results = self.enhanced_detector.detect_license(text, filename)
                if enhanced_results:
                    return enhanced_results
            except:
                pass
        
        # Fall back to standard detector
        detected = self.license_detector.detect_license_from_text(text, filename=filename)
        
        if detected:
            # detected is a single LicenseInfo object, not a list
            licenses.append(detected)
        
        return licenses
    
    def detect_licenses_from_file(self, file_path: str) -> List[LicenseInfo]:
        """Detect licenses from a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of detected licenses
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return self.detect_licenses_from_text(content, os.path.basename(file_path))
        except Exception:
            return []
    
    def find_and_detect_copyrights(self,
                                  directory_path: Optional[str] = None,
                                  merge_with_authors: bool = True,
                                  metadata: Optional[Any] = None) -> str:
        """Find and detect copyright statements from extracted directory.
        
        Args:
            directory_path: Path to directory to search
            merge_with_authors: Whether to merge copyright holders into authors list
            metadata: Optional metadata object to update with copyright holders as authors
            
        Returns:
            Combined copyright statement string
        """
        if not directory_path or not os.path.exists(directory_path):
            return ""
        
        try:
            # Import here to avoid circular dependency
            from ..licenses.unified_detector import detect_licenses_and_copyrights_from_directory
            
            result = detect_licenses_and_copyrights_from_directory(directory_path)
            if isinstance(result, dict) and 'copyrights' in result:
                copyrights = result['copyrights']
                
                # Combine unique copyright statements
                unique_statements = []
                seen_statements = set()
                seen_holders = set()
                
                for copyright_info in copyrights[:10]:  # Limit to first 10 to avoid huge strings
                    statement = copyright_info.get('statement', '')
                    holder = copyright_info.get('holder', '')
                    
                    if statement and statement not in seen_statements:
                        unique_statements.append(statement)
                        seen_statements.add(statement)
                    
                    # If merge_with_authors is enabled and we have metadata, add holders as authors
                    if merge_with_authors and metadata and holder and holder not in seen_holders:
                        seen_holders.add(holder)
                        # Check if holder is not already in authors
                        existing_names = {author.get('name', '').lower() for author in metadata.authors}
                        if holder.lower() not in existing_names:
                            # Add copyright holder as author
                            metadata.authors.append({
                                'name': holder,
                                'source': 'copyright'
                            })
                
                # Join statements with semicolons
                if unique_statements:
                    return '; '.join(unique_statements)
        except Exception as e:
            # Silently fail - copyright extraction is optional
            pass
        
        return ""
    
    def find_and_detect_licenses(self, 
                                archive_path: Optional[str] = None,
                                directory_path: Optional[str] = None) -> List[LicenseInfo]:
        """Find and detect licenses from common license files.
        
        Args:
            archive_path: Path to archive to search
            directory_path: Path to directory to search
            
        Returns:
            List of detected licenses
        """
        licenses = []
        
        # Search in archive
        if archive_path and os.path.exists(archive_path):
            license_files = find_file_in_archive(
                archive_path, 
                self.LICENSE_FILE_PATTERNS,
                return_first=False
            )
            
            if license_files:
                for filename, content in license_files.items():
                    try:
                        text = content.decode('utf-8', errors='ignore')
                        detected = self.detect_licenses_from_text(text, filename)
                        licenses.extend(detected)
                    except Exception:
                        continue
        
        # Search in directory
        if directory_path and os.path.exists(directory_path):
            for pattern in self.LICENSE_FILE_PATTERNS:
                file_path = os.path.join(directory_path, pattern)
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    detected = self.detect_licenses_from_file(file_path)
                    licenses.extend(detected)
        
        # Deduplicate licenses by SPDX ID
        unique_licenses = {}
        for license_info in licenses:
            if license_info.spdx_id:
                key = license_info.spdx_id
                if key not in unique_licenses or license_info.confidence > unique_licenses[key].confidence:
                    unique_licenses[key] = license_info
        
        return list(unique_licenses.values())
    
    def create_metadata(self, 
                       name: str = NO_ASSERTION,
                       version: str = NO_ASSERTION,
                       package_type: Any = None) -> PackageMetadata:
        """Create a PackageMetadata object with defaults.
        
        Args:
            name: Package name
            version: Package version  
            package_type: Package type enum
            
        Returns:
            PackageMetadata object
        """
        return PackageMetadata(
            name=name,
            version=version,
            package_type=package_type
        )
    
    def extract_archive_files(self, 
                            archive_path: str,
                            target_patterns: Optional[List[str]] = None) -> Dict[str, bytes]:
        """Extract files from an archive.
        
        Args:
            archive_path: Path to archive
            target_patterns: Optional patterns to filter files
            
        Returns:
            Dictionary of filename to content
        """
        path = Path(archive_path)
        
        # Determine archive type and extract
        if path.suffix in ['.gz', '.tgz', '.bz2', '.xz'] or '.tar' in path.name:
            return extract_from_tar(archive_path, target_patterns)
        elif path.suffix in ['.zip', '.whl', '.nupkg', '.jar']:
            return extract_from_zip(archive_path, target_patterns)
        else:
            # Try both
            try:
                return extract_from_tar(archive_path, target_patterns)
            except:
                return extract_from_zip(archive_path, target_patterns)