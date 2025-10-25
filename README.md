# UPMEX - Universal Package Metadata Extractor

Extract metadata and license information from various package formats with a single tool.

## Features

### Core Capabilities
- **Universal Package Support**: Extract metadata from 15 package ecosystems
- **Multi-Format Detection**: Automatic package type identification
- **Standardized Output**: Consistent JSON structure across all formats
- **Native Extraction**: No dependency on external package managers
- **High Performance**: Process packages up to 500MB in under 10 seconds

#### Advanced Features
- **NO-ASSERTION Handling**: Clear indication for unavailable data
- **Dependency Mapping**: Full dependency tree with version constraints
- **Author Parsing**: Intelligent name/email extraction and normalization
- **Repository Detection**: Automatic VCS URL extraction
- **Platform Support**: Architecture and OS requirement detection
- **Package URL (PURL)**: Generate standard Package URLs for all packages
- **File Hashing**: SHA-1, MD5, and fuzzy hash (TLSH) for package files
- **JSON Organization**: Structured output with package, metadata, people, licensing, dependencies sections
- **Data Provenance**: Track source of each data field for attestation

#### Supported Ecosystems
- **Python**: wheel (.whl), sdist (.tar.gz, .zip)
- **NPM/Node.js**: .tgz, .tar.gz packages
- **Java/Maven**: .jar, .war, .ear with POM support
- **Gradle**: build.gradle, build.gradle.kts files
- **CocoaPods**: .podspec, .podspec.json files
- **Conda**: .conda (zip), .tar.bz2 packages
- **Perl/CPAN**: .tar.gz, .zip with META.json/yml
- **Conan C/C++**: conanfile.py, conanfile.txt, .tgz packages
- **Ruby Gems**: .gem packages
- **Rust Crates**: .crate packages
- **Go Modules**: .zip archives, go.mod files
- **NuGet/.NET**: .nupkg packages
- **Debian**: .deb packages
- **RPM**: .rpm packages

#### License Detection
- **Powered by OSLiLi**: Uses the external [semantic-copycat-oslili](https://github.com/oscarvalenzuelab/semantic-copycat-oslili) library (v1.5.0+) for license detection
- **Simplified Integration**: UPMEX extracts license-related files and delegates detection to OSLiLi
- **Detection Coverage**:
  - SPDX identifiers in package metadata
  - License files (LICENSE, COPYING, etc.)
  - Package manifest license fields

#### API Integrations & Enrichment
- **Registry Mode**: Fetches missing metadata from package registries (Maven Central, etc.)
- **API Enrichment**: External third-party API integrations for enhanced data
  - **ClearlyDefined**: License and compliance data enrichment
  - **Ecosyste.ms**: Package registry metadata and dependencies
  - **PurlDB**: Comprehensive package metadata from Package URL database
  - **VulnerableCode**: Security vulnerability scanning and assessment
- **Enrichment Tracking**: Full transparency on data sources and applied fields
- **Offline-First**: All core features work without internet connectivity

## Installation

```bash
# Install from source
git clone https://github.com/oscarvalenzuelab/semantic-copycat-upmex.git
cd semantic-copycat-upmex
pip install -e .

# Install with all dependencies
pip install -e .

# Install for development
pip install -e ".[dev]"

```

## Quick Start

```python
from upmex import PackageExtractor

# Create extractor
extractor = PackageExtractor()

# Extract metadata from a package
metadata = extractor.extract("path/to/package.whl")

# Access metadata
print(f"Package: {metadata.name} v{metadata.version}")
print(f"Type: {metadata.package_type.value}")
print(f"License: {metadata.licenses[0].spdx_id if metadata.licenses else 'Unknown'}")

# Convert to JSON
import json
print(json.dumps(metadata.to_dict(), indent=2))
```

## CLI Usage

```bash
# Basic extraction (offline mode - default)
upmex extract package.whl

# Registry mode - fetches missing metadata from package registries
upmex extract --registry package.jar

# API enrichment - query specific third-party APIs
upmex extract --api clearlydefined package.whl
upmex extract --api ecosystems package.jar
upmex extract --api purldb package.gem
upmex extract --api vulnerablecode package.jar
upmex extract --api all package.whl

# Combined registry and API enrichment
upmex extract --registry --api all package.jar

# With pretty JSON output
upmex extract --pretty package.whl

# Output to file
upmex extract package.whl -o metadata.json

# Text format output
upmex extract --format text package.tar.gz

# Detect package type
upmex detect package.jar

# Extract license information
upmex license package.tgz
```

## Configuration

Configuration can be done via JSON files or environment variables:

### Environment Variables

```bash
# API Keys
export PME_CLEARLYDEFINED_API_KEY=your-api-key
export PME_ECOSYSTEMS_API_KEY=your-api-key
export PME_PURLDB_API_KEY=your-api-key
export PME_VULNERABLECODE_API_KEY=your-api-key

# Settings
export PME_LOG_LEVEL=DEBUG
export PME_CACHE_DIR=/path/to/cache
export PME_OUTPUT_FORMAT=json

```

### Configuration File

Create a `config.json`:

```json
{
  "api": {
    "clearlydefined": {
      "enabled": true,
      "api_key": null
    }
  },
  "output": {
    "format": "json",
    "pretty_print": true
  }
}
```

## Supported Package Types

| Ecosystem | Formats | Detection | Metadata | Online Mode | Tested |
|-----------|---------|-----------|----------|-------------|--------|
| Python | .whl, .tar.gz, .zip | ✓ | ✓ | Registry & API | ✓ |
| NPM | .tgz, .tar.gz | ✓ | ✓ | Registry & API | ✓ |
| Java | .jar, .war, .ear | ✓ | ✓ | Registry & API | ✓ |
| Maven | .jar with POM | ✓ | ✓ | Registry & API | ✓ |
| Gradle | build.gradle(.kts) | ✓ | ✓ | Registry & API | ✓ |
| CocoaPods | .podspec(.json) | ✓ | ✓ | Registry & API | ✓ |
| Conda | .conda, .tar.bz2 | ✓ | ✓ | Registry & API | ✓ |
| Perl/CPAN | .tar.gz, .zip | ✓ | ✓ | Registry & API | ✓ |
| Conan | conanfile.py/.txt | ✓ | ✓ | Registry & API | ✓ |
| Ruby | .gem | ✓ | ✓ | Registry & API | ✓ |
| Rust | .crate | ✓ | ✓ | Registry & API | ✓ |
| Go | .zip, .mod, go.mod | ✓ | ✓ | Registry & API | ✓ |
| NuGet | .nupkg | ✓ | ✓ | Registry & API | ✓ |
| Debian | .deb | ✓ | ✓ | Registry & API | ✓ |
| RPM | .rpm | ✓ | ✓ | Registry & API | ✓ |


## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## License

MIT License - see LICENSE file for details.