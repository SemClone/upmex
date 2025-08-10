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
    GENERIC = "generic"
    UNKNOWN = "unknown"


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
class PackageMetadata:
    """Core package metadata structure."""
    name: str
    version: Optional[str] = None
    package_type: PackageType = PackageType.UNKNOWN
    description: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    authors: List[Dict[str, str]] = field(default_factory=list)
    maintainers: List[Dict[str, str]] = field(default_factory=list)
    licenses: List[LicenseInfo] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    keywords: List[str] = field(default_factory=list)
    classifiers: List[str] = field(default_factory=list)
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    extraction_timestamp: datetime = field(default_factory=datetime.utcnow)
    schema_version: str = "1.0.0"
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary format."""
        return {
            "name": self.name,
            "version": self.version,
            "package_type": self.package_type.value,
            "description": self.description,
            "homepage": self.homepage,
            "repository": self.repository,
            "authors": self.authors,
            "maintainers": self.maintainers,
            "licenses": [
                {
                    "spdx_id": lic.spdx_id,
                    "name": lic.name,
                    "confidence": lic.confidence,
                    "confidence_level": lic.confidence_level.value,
                    "detection_method": lic.detection_method,
                    "file_path": lic.file_path,
                } for lic in self.licenses
            ],
            "dependencies": self.dependencies,
            "keywords": self.keywords,
            "classifiers": self.classifiers,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "extraction_timestamp": self.extraction_timestamp.isoformat(),
            "schema_version": self.schema_version,
        }