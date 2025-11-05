# UPMEX - Universal Package Metadata Extractor

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/upmex.svg)](https://pypi.org/project/upmex/)

Extract metadata and license information from packages across 15+ ecosystems with a single tool. Native extraction without external package managers, providing standardized JSON output with dependency mapping, license detection, and API enrichment capabilities.

## Features

- **Universal Package Support**: Extract metadata from 15+ package ecosystems
- **Standardized Output**: Consistent JSON structure across all formats
- **Native Extraction**: No dependency on external package managers
- **SEMCL.ONE Integration**: Works seamlessly with osslili, purl2notices, and ecosystem tools

## Installation

```bash
pip install upmex
```

For development:
```bash
git clone https://github.com/SemClone/upmex.git
cd upmex
pip install -e .
```

## Quick Start

```bash
# Extract metadata from any package
upmex extract package.whl

# With API enrichment
upmex extract --api all package.jar

# Output to file with pretty formatting
upmex extract --pretty package.gem -o metadata.json
```

## Usage

### CLI Usage

```bash
# Basic extraction (offline mode)
upmex extract package.whl

# Registry mode - fetch missing metadata
upmex extract --registry package.jar

# API enrichment modes
upmex extract --api clearlydefined package.whl
upmex extract --api ecosystems package.tgz
upmex extract --api purldb package.gem
upmex extract --api vulnerablecode package.jar

# Combined enrichment
upmex extract --registry --api all package.jar

# Detect package type
upmex detect package.jar

# Extract license information
upmex license package.tgz

# Text format output
upmex extract --format text package.tar.gz
```

### Python API

```python
from upmex import PackageExtractor

# Create extractor
extractor = PackageExtractor()

# Extract metadata
metadata = extractor.extract("path/to/package.whl")

# Access metadata
print(f"Package: {metadata.name} v{metadata.version}")
print(f"Type: {metadata.package_type.value}")
print(f"License: {metadata.licenses[0].spdx_id if metadata.licenses else 'Unknown'}")

# Convert to JSON
import json
print(json.dumps(metadata.to_dict(), indent=2))
```

## Supported Package Types

| Ecosystem | Formats | Registry | API Support |
|-----------|---------|----------|-------------|
| Python | .whl, .tar.gz, .zip | PyPI | ClearlyDefined, Ecosyste.ms |
| NPM/Node.js | .tgz, .tar.gz | NPM | ClearlyDefined, Ecosyste.ms |
| Java/Maven | .jar, .war, .ear | Maven Central | ClearlyDefined, PurlDB |
| Ruby | .gem | RubyGems | ClearlyDefined, Ecosyste.ms |
| Rust | .crate | crates.io | ClearlyDefined, Ecosyste.ms |
| Go | .zip, go.mod | Go Modules | ClearlyDefined, PurlDB |
| NuGet/.NET | .nupkg | NuGet | ClearlyDefined, Ecosyste.ms |
| Conda | .conda, .tar.bz2 | Anaconda | Ecosyste.ms |
| Perl/CPAN | .tar.gz, .zip | CPAN | Ecosyste.ms |
| CocoaPods | .podspec, .podspec.json | CocoaPods | Ecosyste.ms |
| Conan C/C++ | conanfile.py/.txt, .tgz | Conan Center | Limited |
| Gradle | build.gradle(.kts) | Maven/Gradle | Limited |
| Debian | .deb | Debian | Limited |
| RPM | .rpm | RPM repos | Limited |

## Advanced Features

### Metadata Extraction

- **Package Information**: Name, version, description, homepage
- **Author Parsing**: Intelligent name/email extraction and normalization
- **Repository Detection**: Automatic VCS URL extraction
- **Platform Support**: Architecture and OS requirement detection
- **Package URL (PURL)**: Generate standard Package URLs
- **File Hashing**: SHA-1, MD5, and fuzzy hash (TLSH)
- **Data Provenance**: Track source of each data field

### License Detection

Powered by [osslili](https://github.com/SemClone/osslili) v1.5.0+:

- SPDX identifier detection in metadata
- License file extraction (LICENSE, COPYING, etc.)
- Package manifest license field parsing
- Three-tier detection system with high accuracy

### Dependency Mapping

- Full dependency tree with version constraints
- Development vs. runtime dependency classification
- Optional dependency tracking
- Version range resolution

### API Enrichment

Enhance metadata with third-party APIs:

#### ClearlyDefined
```bash
upmex extract --api clearlydefined package.whl
```
- License and compliance data
- Attribution information
- Security assessments

#### Ecosyste.ms
```bash
upmex extract --api ecosystems package.jar
```
- Package registry metadata
- Dependency information
- Version history

#### PurlDB
```bash
upmex extract --api purldb package.gem
```
- Comprehensive package metadata
- Cross-ecosystem information
- Historical data

#### VulnerableCode
```bash
upmex extract --api vulnerablecode package.jar
```
- Security vulnerability scanning
- CVE mapping
- Risk assessment

## Configuration

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

Create `config.json`:

```json
{
  "api": {
    "clearlydefined": {
      "enabled": true,
      "api_key": null
    },
    "ecosystems": {
      "enabled": true,
      "api_key": null
    }
  },
  "output": {
    "format": "json",
    "pretty_print": true
  },
  "cache": {
    "enabled": true,
    "directory": "~/.cache/upmex"
  }
}
```

## Output Format

### Standard JSON Structure

```json
{
  "package": {
    "name": "example-package",
    "version": "1.2.3",
    "type": "pypi",
    "purl": "pkg:pypi/example-package@1.2.3",
    "description": "Package description"
  },
  "metadata": {
    "homepage": "https://example.com",
    "repository": "https://github.com/example/package",
    "documentation": "https://docs.example.com"
  },
  "people": {
    "authors": [
      {
        "name": "John Doe",
        "email": "john@example.com"
      }
    ],
    "maintainers": []
  },
  "licensing": {
    "licenses": [
      {
        "spdx_id": "MIT",
        "name": "MIT License",
        "text": "..."
      }
    ]
  },
  "dependencies": {
    "runtime": [
      {
        "name": "requests",
        "version_constraint": ">=2.0.0"
      }
    ],
    "development": []
  },
  "provenance": {
    "source": "package_metadata",
    "enrichment": ["clearlydefined", "ecosystems"]
  }
}
```

## Integration with SEMCL.ONE

UPMEX is a core component of the SEMCL.ONE ecosystem:

- Powers **purl2notices** for legal notice generation
- Uses **osslili** for enhanced license detection
- Supports **src2purl** for package identification
- Integrates with **ospac** for policy evaluation
- Works with **purl2src** for source retrieval

### Workflow Example

```bash
# 1. Extract metadata from package
upmex extract library.jar -o metadata.json

# 2. Generate legal notices
purl2notices -i metadata.json -o NOTICE.txt

# 3. Validate compliance
ospac evaluate NOTICE.txt --policy compliance.yaml
```

## Performance

- Process packages up to 500MB in under 10 seconds
- Efficient caching for API responses
- Parallel processing for batch operations
- Memory-efficient streaming for large files

## Documentation

- [User Guide](docs/user-guide.md) - Comprehensive usage documentation
- [API Reference](docs/api.md) - Python API documentation
- [Configuration Guide](docs/configuration.md) - Detailed configuration options
- [Examples](docs/examples.md) - Common use cases and workflows

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on:
- Code of conduct
- Development setup
- Submitting pull requests
- Reporting issues

## Support

For support and questions:
- [GitHub Issues](https://github.com/SemClone/upmex/issues) - Bug reports and feature requests
- [Documentation](https://github.com/SemClone/upmex) - Complete project documentation
- [SEMCL.ONE Community](https://semcl.one) - Ecosystem support and discussions

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.

## Authors

See [AUTHORS.md](AUTHORS.md) for a list of contributors.

---

*Part of the [SEMCL.ONE](https://semcl.one) ecosystem for comprehensive OSS compliance and code analysis.*