# UPMEX API Reference

Complete API documentation for the UPMEX Python library.

## Core Classes

### `PackageExtractor`

Main class for extracting metadata from packages.

```python
class PackageExtractor(config: Optional[Config] = None)
```

#### Parameters

- **config** (Config, optional): Configuration object for customizing extraction behavior

#### Methods

##### `extract(package_path: str) -> PackageMetadata`

Extract metadata from a package file.

```python
extractor = PackageExtractor()
metadata = extractor.extract("package.whl")
```

**Parameters:**
- **package_path** (str): Path to the package file

**Returns:**
- **PackageMetadata**: Object containing extracted metadata

**Raises:**
- **UnsupportedPackageError**: If package type is not supported
- **ExtractionError**: If extraction fails
- **FileNotFoundError**: If package file does not exist

##### `detect_type(package_path: str) -> PackageType`

Detect the type of a package without full extraction.

```python
package_type = extractor.detect_type("package.jar")
print(package_type.value)  # "maven"
```

**Parameters:**
- **package_path** (str): Path to the package file

**Returns:**
- **PackageType**: Enum value representing the package type

## Data Models

### `PackageMetadata`

Container for all extracted package metadata.

```python
@dataclass
class PackageMetadata:
    name: str
    version: str
    package_type: PackageType
    purl: str
    description: Optional[str]
    homepage: Optional[str]
    repository: Optional[str]
    licenses: List[License]
    authors: List[Person]
    maintainers: List[Person]
    dependencies: Dependencies
    provenance: Provenance
    files: List[FileInfo]
    metadata: Dict[str, Any]
```

#### Methods

##### `to_dict() -> Dict[str, Any]`

Convert metadata to dictionary.

```python
data = metadata.to_dict()
```

##### `to_json(pretty: bool = False) -> str`

Convert metadata to JSON string.

```python
json_str = metadata.to_json(pretty=True)
```

##### `get_purl() -> PackageURL`

Get Package URL object.

```python
from packageurl import PackageURL
purl = metadata.get_purl()
print(purl.to_string())
```

### `License`

License information.

```python
@dataclass
class License:
    spdx_id: Optional[str]
    name: str
    text: Optional[str]
    file: Optional[str]
    url: Optional[str]
```

### `Person`

Author or maintainer information.

```python
@dataclass
class Person:
    name: str
    email: Optional[str]
    url: Optional[str]
```

### `Dependency`

Package dependency information.

```python
@dataclass
class Dependency:
    name: str
    version_constraint: Optional[str]
    purl: Optional[str]
    optional: bool = False
```

### `Dependencies`

Container for all dependency types.

```python
@dataclass
class Dependencies:
    runtime: List[Dependency]
    development: List[Dependency]
    optional: List[Dependency]
    build: List[Dependency]
```

### `FileInfo`

Information about files in the package.

```python
@dataclass
class FileInfo:
    path: str
    size: int
    sha1: Optional[str]
    md5: Optional[str]
    tlsh: Optional[str]
```

### `Provenance`

Data source tracking.

```python
@dataclass
class Provenance:
    source: str  # "package_metadata", "registry", "api"
    enrichment: List[str]  # API providers used
    timestamp: datetime
```

## Configuration

### `Config`

Configuration class for customizing UPMEX behavior.

```python
from upmex.config import Config

config = Config()
```

#### Attributes

##### `api`

API provider configuration.

```python
config.api.clearlydefined.enabled = True
config.api.clearlydefined.api_key = os.getenv('PME_CLEARLYDEFINED_API_KEY')
config.api.clearlydefined.base_url = "https://api.clearlydefined.io"

config.api.ecosystems.enabled = True
config.api.purldb.enabled = False
config.api.vulnerablecode.enabled = True
```

##### `cache`

Cache configuration.

```python
config.cache.enabled = True
config.cache.directory = "~/.cache/upmex"
config.cache.ttl = 86400  # seconds
```

##### `output`

Output formatting configuration.

```python
config.output.format = "json"  # or "text"
config.output.pretty_print = True
```

##### `processing`

Processing configuration.

```python
config.processing.max_file_size = 500 * 1024 * 1024  # 500MB
config.processing.timeout = 30  # seconds
config.processing.enable_registry = True
```

##### `logging`

Logging configuration.

```python
config.logging.level = "DEBUG"  # or "INFO", "WARNING", "ERROR"
config.logging.file = "/var/log/upmex.log"
```

#### Methods

##### `load_from_file(path: str)`

Load configuration from JSON file.

```python
config = Config()
config.load_from_file("~/.upmex/config.json")
```

##### `load_from_env()`

Load configuration from environment variables.

```python
config = Config()
config.load_from_env()
```

##### `save(path: str)`

Save configuration to JSON file.

```python
config.save("~/.upmex/config.json")
```

## Enumerations

### `PackageType`

Supported package types.

```python
from upmex.types import PackageType

class PackageType(Enum):
    PYTHON_WHEEL = "wheel"
    PYTHON_SDIST = "sdist"
    NPM = "npm"
    MAVEN = "maven"
    GRADLE = "gradle"
    RUBYGEM = "gem"
    RUST_CRATE = "crate"
    GO_MODULE = "go"
    NUGET = "nuget"
    DEBIAN = "deb"
    RPM = "rpm"
    CONDA = "conda"
    CPAN = "cpan"
    COCOAPODS = "pod"
    CONAN = "conan"
    UNKNOWN = "unknown"
```

### `OutputFormat`

Output format options.

```python
from upmex.types import OutputFormat

class OutputFormat(Enum):
    JSON = "json"
    TEXT = "text"
```

## Exceptions

### `UpmexException`

Base exception for all UPMEX errors.

```python
from upmex.exceptions import UpmexException
```

### `UnsupportedPackageError`

Raised when package type is not supported.

```python
from upmex.exceptions import UnsupportedPackageError

try:
    metadata = extractor.extract("unknown.xyz")
except UnsupportedPackageError as e:
    print(f"Unsupported: {e}")
```

### `ExtractionError`

Raised when extraction fails.

```python
from upmex.exceptions import ExtractionError

try:
    metadata = extractor.extract("corrupted.jar")
except ExtractionError as e:
    print(f"Extraction failed: {e}")
```

### `APIError`

Raised when API enrichment fails.

```python
from upmex.exceptions import APIError

try:
    metadata = extractor.extract_with_enrichment("package.whl")
except APIError as e:
    print(f"API error: {e}")
```

## Utility Functions

### `detect_package_type(file_path: str) -> PackageType`

Standalone function to detect package type.

```python
from upmex.utils import detect_package_type

package_type = detect_package_type("package.jar")
print(package_type.value)  # "maven"
```

### `generate_purl(metadata: PackageMetadata) -> str`

Generate Package URL from metadata.

```python
from upmex.utils import generate_purl

purl = generate_purl(metadata)
print(purl)  # "pkg:pypi/requests@2.28.0"
```

### `normalize_license(license_str: str) -> str`

Normalize license string to SPDX identifier.

```python
from upmex.utils import normalize_license

spdx_id = normalize_license("MIT License")
print(spdx_id)  # "MIT"
```

## API Enrichment

### `APIEnricher`

Base class for API enrichment providers.

```python
from upmex.enrichment import APIEnricher

class CustomEnricher(APIEnricher):
    def enrich(self, metadata: PackageMetadata) -> PackageMetadata:
        # Custom enrichment logic
        return metadata
```

### `ClearlyDefinedEnricher`

ClearlyDefined API enrichment.

```python
from upmex.enrichment import ClearlyDefinedEnricher

enricher = ClearlyDefinedEnricher(api_key=os.getenv('PME_CLEARLYDEFINED_API_KEY'))
enriched = enricher.enrich(metadata)
```

### `EcosystemsEnricher`

Ecosyste.ms API enrichment.

```python
from upmex.enrichment import EcosystemsEnricher

enricher = EcosystemsEnricher(api_key=os.getenv('PME_ECOSYSTEMS_API_KEY'))
enriched = enricher.enrich(metadata)
```

## Advanced Usage

### Custom Extractor

Create a custom package extractor:

```python
from upmex.extractors import BaseExtractor
from upmex import register_extractor

class CustomExtractor(BaseExtractor):
    """Custom package format extractor"""

    @classmethod
    def can_extract(cls, file_path: str) -> bool:
        """Check if this extractor can handle the file"""
        return file_path.endswith('.custom')

    def extract(self, file_path: str) -> PackageMetadata:
        """Extract metadata from custom package"""
        # Implementation here
        return PackageMetadata(
            name="custom-package",
            version="1.0.0",
            package_type=PackageType.UNKNOWN,
            purl="pkg:custom/custom-package@1.0.0"
        )

# Register the extractor
register_extractor(CustomExtractor)
```

### Custom Enrichment Provider

Create a custom API enrichment provider:

```python
from upmex.enrichment import APIEnricher
import requests

class MyAPIEnricher(APIEnricher):
    """Custom API enrichment provider"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://myapi.example.com"

    def enrich(self, metadata: PackageMetadata) -> PackageMetadata:
        """Enrich metadata with custom API"""

        # Query API
        response = requests.get(
            f"{self.base_url}/package/{metadata.purl}",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )

        if response.ok:
            data = response.json()

            # Add enriched data
            if 'vulnerabilities' in data:
                metadata.metadata['vulnerabilities'] = data['vulnerabilities']

            # Track enrichment
            metadata.provenance.enrichment.append('myapi')

        return metadata

# Use the enricher
enricher = MyAPIEnricher(api_key="your-key")
enriched = enricher.enrich(metadata)
```

### Batch Processing

Process multiple packages in parallel:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json

def process_package(file_path):
    """Process single package"""
    extractor = PackageExtractor()
    try:
        metadata = extractor.extract(str(file_path))
        return {
            'file': file_path.name,
            'success': True,
            'data': metadata.to_dict()
        }
    except Exception as e:
        return {
            'file': file_path.name,
            'success': False,
            'error': str(e)
        }

# Process packages in parallel
packages = list(Path('./packages').glob('*'))
results = []

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(process_package, p): p for p in packages}

    for future in as_completed(futures):
        result = future.result()
        results.append(result)

        if result['success']:
            print(f"✓ {result['file']}")
        else:
            print(f"✗ {result['file']}: {result['error']}")

# Save results
with open('batch_results.json', 'w') as f:
    json.dump(results, f, indent=2)
```

### Streaming Large Files

Process large packages with streaming:

```python
from upmex import PackageExtractor
from upmex.config import Config

# Configure for large files
config = Config()
config.processing.max_file_size = 1024 * 1024 * 1000  # 1GB
config.processing.streaming = True

extractor = PackageExtractor(config=config)

# Process large package
metadata = extractor.extract("large-package.jar")
```

### Custom Output Formatter

Create custom output formatter:

```python
from upmex.output import BaseFormatter

class MarkdownFormatter(BaseFormatter):
    """Format metadata as Markdown"""

    def format(self, metadata: PackageMetadata) -> str:
        lines = []
        lines.append(f"# {metadata.name} v{metadata.version}")
        lines.append("")

        if metadata.description:
            lines.append(f"{metadata.description}")
            lines.append("")

        lines.append("## License")
        for license in metadata.licenses:
            lines.append(f"- {license.name} ({license.spdx_id})")
        lines.append("")

        lines.append("## Dependencies")
        for dep in metadata.dependencies.runtime:
            lines.append(f"- {dep.name} {dep.version_constraint}")

        return "\n".join(lines)

# Use formatter
formatter = MarkdownFormatter()
markdown = formatter.format(metadata)
print(markdown)
```

## Testing

### Unit Testing

Test custom extractors:

```python
import unittest
from unittest.mock import Mock, patch
from upmex import PackageExtractor

class TestPackageExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = PackageExtractor()

    def test_extract_wheel(self):
        """Test wheel package extraction"""
        metadata = self.extractor.extract("test.whl")

        self.assertEqual(metadata.package_type.value, "wheel")
        self.assertIsNotNone(metadata.name)
        self.assertIsNotNone(metadata.version)

    @patch('upmex.api.requests.get')
    def test_api_enrichment(self, mock_get):
        """Test API enrichment"""
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {
            'licenses': ['MIT']
        }

        config = Config()
        config.api.clearlydefined.enabled = True

        extractor = PackageExtractor(config=config)
        metadata = extractor.extract("test.jar")

        self.assertIn('clearlydefined', metadata.provenance.enrichment)
```

### Integration Testing

Test full extraction pipeline:

```python
import tempfile
from pathlib import Path

def test_full_pipeline():
    """Test complete extraction pipeline"""

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test package
        test_package = Path(tmpdir) / "test.whl"
        # ... create test package ...

        # Extract
        extractor = PackageExtractor()
        metadata = extractor.extract(str(test_package))

        # Verify
        assert metadata.name == "expected-name"
        assert metadata.version == "1.0.0"
        assert len(metadata.licenses) > 0

        # Test JSON conversion
        json_str = metadata.to_json()
        assert json_str

        # Test dict conversion
        data = metadata.to_dict()
        assert data['package']['name'] == metadata.name
```

## Performance Considerations

### Caching

Implement caching for API calls:

```python
from functools import lru_cache
import hashlib

class CachedExtractor(PackageExtractor):
    @lru_cache(maxsize=128)
    def _get_api_data(self, purl: str) -> dict:
        """Cached API data retrieval"""
        # API call implementation
        return {}

    def extract(self, package_path: str) -> PackageMetadata:
        metadata = super().extract(package_path)

        # Use cached API data
        api_data = self._get_api_data(metadata.purl)
        # Apply enrichment

        return metadata
```

### Memory Management

For processing many packages:

```python
import gc

def process_packages_efficiently(package_files):
    """Process packages with memory management"""

    extractor = PackageExtractor()
    results = []

    for i, package_file in enumerate(package_files):
        metadata = extractor.extract(package_file)

        # Extract only needed data
        result = {
            'purl': metadata.purl,
            'license': metadata.licenses[0].spdx_id if metadata.licenses else None
        }
        results.append(result)

        # Periodic garbage collection
        if i % 100 == 0:
            gc.collect()

    return results
```