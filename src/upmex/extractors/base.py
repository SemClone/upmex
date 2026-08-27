"""Base extractor class for all package types."""

import hashlib
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
import re

# An SPDX expression joining licences. Resolving one of these to a single
# identifier reports one arm as though it were the whole statement.
_COMPOUND_EXPRESSION = re.compile(r"\s(?:OR|AND|WITH)\s", re.IGNORECASE)

from ..core.models import (
    PackageMetadata,
    LicenseInfo,
    LicenseConfidenceLevel,
    NO_ASSERTION,
    split_namespace,
)
from ..utils.patterns import LICENSE_FILE_NAMES
from ..utils.author_parser import parse_author_string, parse_author_list
from ..utils.archive_utils import find_file_in_archive, extract_from_tar, extract_from_zip


class BaseExtractor(ABC):
    """Abstract base class for package extractors."""
    
    # Common license file patterns (using shared patterns)
    LICENSE_FILE_PATTERNS = LICENSE_FILE_NAMES
    
    def __init__(self, registry_mode: bool = False, config: Any = None):
        """Initialize extractor.

        Args:
            registry_mode: Whether to fetch additional data from package registries
        """
        self.registry_mode = registry_mode
        # The configuration the caller was given, so an API client built in
        # here honours --config rather than reading the defaults. None means
        # nothing was threaded through and the defaults apply.
        self.config = config
    
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
    
    def file_sha1(self, file_path: str) -> Optional[str]:
        """Calculate the SHA-1 of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hex digest, or None if the file could not be read
        """
        try:
            digest = hashlib.sha1()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    digest.update(chunk)
            return digest.hexdigest()
        except Exception:
            return None

    def detect_licenses_from_declared_name(
        self,
        declared: str,
        source_file: Optional[str] = None,
    ) -> List[LicenseInfo]:
        """Resolve a licence name a package declares into SPDX identifiers.

        Packages declare a name, not a licence text: "BSD License" in a PyPI
        classifier, "MIT" in a package.json. Resolving that to an identifier
        is worth doing, and it is an inference rather than a reading.

        This existed as the same block copied into nine extractors: wrap the
        name in "License: ..." and hand the result to the text detector. The
        detector then reported an SPDX identifier at confidence 1.0, level
        exact, method tag, from a file that does not exist, because the
        document it read was one we had just written. For packaging, whose
        classifier says "BSD License", that produced BSD-3-Clause as an exact
        finding when BSD names four licences and the project uses the
        two-clause one.

        So the answer is kept and labelled for what it is. Where the declared
        name is already the identifier, resolving it is identity and stays
        exact; where it is a family or a prose name, the identifier is the
        detector's best reading of it and says so.
        """
        if not declared:
            return []

        # A compound expression names a relationship between licences, and
        # resolving it would report one arm as though it were the whole:
        # "MIT OR Apache-2.0" is a choice, and "MIT" alone is a different
        # statement. Kept verbatim, which is what the SPDX expression already
        # is.
        if _COMPOUND_EXPRESSION.search(declared):
            return [
                LicenseInfo(
                    name=declared.strip(),
                    spdx_id=declared.strip(),
                    confidence=1.0,
                    confidence_level=LicenseConfidenceLevel.EXACT,
                    detection_method="declared_expression",
                    match_type="declared_expression",
                    category="declared",
                    file_path=source_file,
                )
            ]

        # osslili reads a licence declaration more reliably with the prefix,
        # unless the value already looks like a document or a expression.
        if len(declared) < 20 and ':' not in declared:
            text = f"License: {declared}"
        else:
            text = declared

        resolved = self.detect_licenses_from_text(text, source_file)
        for license_info in resolved:
            identifier = (license_info.spdx_id or "").strip().lower()
            verbatim = declared.strip().lower()
            license_info.detection_method = "declared_name"
            license_info.match_type = "declared_name"
            license_info.category = "declared"
            license_info.file_path = source_file
            if identifier != verbatim:
                # The name was interpreted. Exact would say the file named
                # this identifier, and it named something else.
                license_info.confidence_level = LicenseConfidenceLevel.HIGH
        return resolved

    def detect_licenses_from_text(self,
                                 text: str,
                                 filename: Optional[str] = None) -> List[LicenseInfo]:
        """Detect licenses from text content using OSLiLi.

        Args:
            text: Text content to analyze
            filename: Optional filename for context

        Returns:
            List of detected licenses
        """
        if not text:
            return []

        # Use unified detector which now uses OSLiLi
        from ..licenses.unified_detector import detect_licenses

        licenses = []
        detected_list = detect_licenses(filename or "content", text)

        for license_dict in detected_list:
            license_info = LicenseInfo(
                name=license_dict.get('name', 'Unknown'),
                spdx_id=license_dict.get('spdx_id', 'Unknown'),
                confidence=license_dict.get('confidence', 0.0),
                confidence_level=LicenseConfidenceLevel(
                    license_dict.get('confidence_level', 'low')
                ),
                detection_method=license_dict.get('source', 'osslili'),
                # Carried so a consumer can check the claim against the file
                # that made it. It was dropped here, which is why every
                # licence upmex reported came back with file_path None.
                file_path=license_dict.get('file'),
                category=license_dict.get('category'),
                match_type=license_dict.get('match_type'),
            )
            licenses.append(license_info)

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
        """Find and detect copyright statements, prioritizing package metadata.

        Priority order:
        1. Use existing authors from package metadata to construct copyright
        2. Fall back to OSLiLi scanning if no authors in metadata

        Args:
            directory_path: Path to directory to search
            merge_with_authors: Whether to merge copyright holders into authors list
            metadata: Optional metadata object to update with copyright holders as authors

        Returns:
            Combined copyright statement string
        """
        # First, try to construct copyright from existing authors in metadata
        if metadata and hasattr(metadata, 'authors') and metadata.authors:
            # Filter authors that came from package metadata (not from previous copyright scans)
            metadata_authors = [
                author for author in metadata.authors
                if author.get('source') != 'copyright'
            ]

            if metadata_authors:
                # Construct copyright statement from metadata authors
                copyright_statements = []
                for author in metadata_authors:
                    name = author.get('name', '').strip()
                    if name:
                        # Simple copyright statement format
                        copyright_statements.append(f"Copyright {name}")

                if copyright_statements:
                    return '; '.join(copyright_statements)

        # Fall back to OSLiLi scanning if no metadata authors or directory not available
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

    def enrich_with_clearlydefined(self, metadata: 'PackageMetadata') -> None:
        """Enrich metadata using ClearlyDefined API for registry mode."""
        if not self.registry_mode:
            return

        try:
            from ..api.clearlydefined import ClearlyDefinedAPI

            cd_api = ClearlyDefinedAPI(config=self.config)

            # Parse namespace based on package type
            namespace, name = split_namespace(metadata.package_type, metadata.name)

            cd_data = cd_api.get_definition(
                package_type=metadata.package_type,
                namespace=namespace,
                name=name,
                version=metadata.version
            )

            if cd_data:
                applied_fields = []

                # Enrich licensing information
                cd_license = cd_api.extract_license_info(cd_data)
                if cd_license:
                    from ..core.models import LicenseInfo, LicenseConfidenceLevel
                    license_obj = LicenseInfo(
                        spdx_id=cd_license['spdx_id'],
                        confidence=cd_license['confidence'],
                        confidence_level=LicenseConfidenceLevel.EXACT if cd_license['confidence'] >= 0.95 else LicenseConfidenceLevel.HIGH,
                        detection_method='ClearlyDefined API (registry)',
                        file_path='clearlydefined_api'
                    )
                    metadata.licenses.append(license_obj)
                    metadata.provenance['licenses_clearlydefined'] = f"clearlydefined:{cd_api.base_url}"
                    applied_fields.append('licenses')

                # Enrich other metadata if missing
                from ..core.models import NO_ASSERTION
                if not metadata.homepage or metadata.homepage == NO_ASSERTION:
                    project_website = cd_data.get('described', {}).get('projectWebsite')
                    if project_website:
                        metadata.homepage = project_website
                        metadata.provenance['homepage'] = f"clearlydefined:{cd_api.base_url}"
                        applied_fields.append('homepage')

                if not metadata.repository or metadata.repository == NO_ASSERTION:
                    source_location = cd_data.get('described', {}).get('sourceLocation', {})
                    if source_location and source_location.get('url'):
                        metadata.repository = source_location['url']
                        metadata.provenance['repository'] = f"clearlydefined:{cd_api.base_url}"
                        applied_fields.append('repository')

                # Track enrichment data
                if applied_fields:
                    metadata.add_enrichment(
                        source="clearlydefined",
                        source_type="api",  # ClearlyDefined is a third-party API
                        data=cd_data,
                        applied_fields=applied_fields
                    )

        except ImportError:
            # ClearlyDefined API not available
            pass
        except Exception as e:
            # Silently fail - ClearlyDefined enrichment is optional
            pass