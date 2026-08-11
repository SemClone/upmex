"""Data models for package metadata."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from enum import Enum

# Special constant for fields where data cannot be determined
NO_ASSERTION = "NO-ASSERTION"


class PackageType(Enum):
    """Supported package types."""
    PYTHON_WHEEL = "python_wheel"
    PYTHON_SDIST = "python_sdist"
    NPM = "npm"
    MAVEN = "maven"
    JAR = "jar"
    GRADLE = "gradle"
    COCOAPODS = "cocoapods"
    CONDA = "conda"
    CONAN = "conan"
    PERL = "perl"
    RUBY_GEM = "ruby_gem"
    RUST_CRATE = "rust_crate"
    GO_MODULE = "go_module"
    NUGET = "nuget"
    RPM = "rpm"
    DEB = "deb"
    GENERIC = "generic"
    UNKNOWN = "unknown"


# A Gradle or plain JAR artifact is identified by Maven coordinates just as much
# as a MAVEN one, so anything splitting a coordinate must treat all three alike
MAVEN_PACKAGE_TYPES = (PackageType.MAVEN, PackageType.JAR, PackageType.GRADLE)


def split_namespace(package_type: 'PackageType', name: str) -> tuple:
    """Split a package name into its namespace and name.

    Maven-family names carry the groupId as ``groupId:artifactId`` and npm scoped
    names carry the scope as ``@scope/name``. PURL construction and every registry
    lookup needs the two parts separately.

    Args:
        package_type: Type of package the name belongs to
        name: Package name, possibly carrying a namespace

    Returns:
        Tuple of (namespace, name); namespace is None when the name carries none
    """
    if not name:
        return (None, name)

    if package_type in MAVEN_PACKAGE_TYPES and ':' in name:
        namespace, _, artifact = name.partition(':')
        if namespace and artifact:
            return (namespace, artifact)
    elif package_type == PackageType.NPM and name.startswith('@') and '/' in name:
        scope, _, package = name[1:].partition('/')
        if scope and package:
            return (scope, package)

    return (None, name)


class LicenseConfidenceLevel(Enum):
    """Confidence levels for license detection."""
    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class LicenseInfo:
    """License information with confidence scoring."""
    spdx_id: Optional[str] = None
    name: Optional[str] = None
    text: Optional[str] = None
    confidence: float = 0.0
    confidence_level: LicenseConfidenceLevel = LicenseConfidenceLevel.NONE
    detection_method: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class EnrichmentData:
    """Data collected from external sources (registries and APIs)."""
    source: str  # e.g., "maven_central", "clearlydefined", "ecosystems"
    source_type: str  # "registry" or "api"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    applied_fields: List[str] = field(default_factory=list)  # Which fields were updated


@dataclass
class PackageMetadata:
    """Core package metadata structure."""
    name: str
    version: Optional[str] = None
    package_type: PackageType = PackageType.UNKNOWN
    purl: Optional[str] = None
    description: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    copyright: Optional[str] = None  # Copyright statements
    authors: List[Dict[str, str]] = field(default_factory=list)
    maintainers: List[Dict[str, str]] = field(default_factory=list)
    licenses: List[LicenseInfo] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    keywords: List[str] = field(default_factory=list)
    classifiers: List[str] = field(default_factory=list)
    file_size: Optional[int] = None
    file_hash: Optional[str] = None  # SHA-1
    file_hash_md5: Optional[str] = None  # MD5
    fuzzy_hash: Optional[str] = None  # TLSH or LSH
    extraction_timestamp: datetime = field(default_factory=datetime.utcnow)
    schema_version: str = "1.0.0"
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, str] = field(default_factory=dict)  # Track data sources
    enrichment: List[EnrichmentData] = field(default_factory=list)  # External enrichment data
    vulnerabilities: Dict[str, Any] = field(default_factory=dict)  # Vulnerability information
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary format with organized structure."""
        return {
            # Package identification
            "package": {
                "name": self.name,
                "version": self.version,
                "type": self.package_type.value,
                "purl": self.purl,
            },
            
            # Package metadata
            "metadata": {
                "description": self.description,
                "homepage": self.homepage,
                "repository": self.repository,
                "copyright": self.copyright,
                "keywords": self.keywords,
                "classifiers": self.classifiers,
            },
            
            # People
            "people": {
                "authors": self.authors,
                "maintainers": self.maintainers,
            },
            
            # Licensing
            "licensing": {
                "declared_licenses": [
                    {
                        "spdx_id": lic.spdx_id,
                        "name": lic.name,
                        "confidence": lic.confidence,
                        "confidence_level": lic.confidence_level.value,
                        "source": lic.detection_method,
                        "file": lic.file_path,
                    } for lic in self.licenses
                ],
            },
            
            # Dependencies
            "dependencies": self.dependencies,
            
            # File information
            "file_info": {
                "size": self.file_size,
                "hashes": {
                    "sha1": self.file_hash,
                    "md5": self.file_hash_md5,
                    "fuzzy": self.fuzzy_hash,
                }
            },
            
            # Extraction metadata
            "extraction_info": {
                "timestamp": self.extraction_timestamp.isoformat(),
                "schema_version": self.schema_version,
            },
            
            # Data provenance for attestation
            "provenance": self.provenance,

            # External enrichment data
            "enrichment": [
                {
                    "source": enrichment.source,
                    "source_type": enrichment.source_type,
                    "timestamp": enrichment.timestamp.isoformat(),
                    "applied_fields": enrichment.applied_fields,
                    "data": enrichment.data
                } for enrichment in self.enrichment
            ],

            # Vulnerability information
            "vulnerabilities": self.vulnerabilities
        }

    def add_enrichment(self, source: str, source_type: str, data: Dict[str, Any], applied_fields: List[str] = None) -> None:
        """Add enrichment data from external sources.

        Args:
            source: Name of the source (e.g., "maven_central", "clearlydefined")
            source_type: Type of source ("registry" or "api")
            data: Raw data received from the source
            applied_fields: List of metadata fields that were updated with this data
        """
        enrichment = EnrichmentData(
            source=source,
            source_type=source_type,
            data=data,
            applied_fields=applied_fields or []
        )
        self.enrichment.append(enrichment)