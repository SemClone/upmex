# UPMEX - Universal Package Metadata Extractor

Extract metadata and license information from various package formats with a single tool.

## Features

### Core Capabilities
- **Universal Package Support**: Extract metadata from 13 package ecosystems
- **Multi-Format Detection**: Automatic package type identification
- **Standardized Output**: Consistent JSON structure across all formats
- **Native Extraction**: No dependency on external package managers
- **High Performance**: Process packages up to 500MB in under 10 seconds

### Supported Ecosystems
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
- **Linux**: (Planned) Debian .deb, RPM .rpm

### License Detection Engine
- **Multi-Layer Detection**:
  - Regex-based pattern matching for 24+ SPDX identifiers
  - Dice-Sørensen coefficient for fuzzy text matching
  - Confidence scoring (0.0-1.0) for reliability assessment
  - Multi-license support with individual confidence scores
- **Smart File Discovery**: Automatic LICENSE/COPYING file detection
- **Metadata Parsing**: Extract from package manifests and configuration

### API Integrations
- **ClearlyDefined**: License and compliance data enrichment
- **Ecosyste.ms**: Package registry metadata and dependencies
- **Maven Central**: Parent POM resolution and inheritance
- **Offline-First**: All features work without internet connectivity

### Advanced Features
- **NO-ASSERTION Handling**: Clear indication for unavailable data
- **Parent POM Resolution**: Automatic Maven inheritance processing
- **Dependency Mapping**: Full dependency tree with version constraints
- **Author Parsing**: Intelligent name/email extraction and normalization
- **Repository Detection**: Automatic VCS URL extraction
- **Platform Support**: Architecture and OS requirement detection

## Installation

```bash
# Install from source
git clone https://github.com/oscarvalenzuelab/semantic-copycat-upmex.git
cd semantic-copycat-upmex
pip install -e .

# Install with all features
pip install -e ".[all]"

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

# Online mode - fetches parent POMs and queries APIs
upmex extract --online package.jar

# With pretty JSON output
upmex extract --pretty package.whl

# Output to file
upmex extract package.whl -o metadata.json

# Text format output
upmex extract --format text package.tar.gz

# Detect package type
upmex detect package.jar

# Extract license information with confidence scores
upmex license package.tgz --confidence
```

## Configuration

Configuration can be done via JSON files or environment variables:

### Environment Variables

```bash
# API Keys
export PME_CLEARLYDEFINED_API_KEY=your-api-key
export PME_ECOSYSTEMS_API_KEY=your-api-key

# Settings
export PME_LOG_LEVEL=DEBUG
export PME_CACHE_DIR=/path/to/cache
export PME_LICENSE_METHODS=regex,dice_sorensen
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
  "license_detection": {
    "methods": ["regex", "dice_sorensen"],
    "confidence_threshold": 0.85
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
| Python | .whl, .tar.gz, .zip | ✓ | ✓ | API enrichment | ✓ |
| NPM | .tgz, .tar.gz | ✓ | ✓ | API enrichment | ✓ |
| Java | .jar, .war, .ear | ✓ | ✓ | Parent POM fetch | ✓ |
| Maven | .jar with POM | ✓ | ✓ | Parent POM fetch | ✓ |
| Gradle | build.gradle(.kts) | ✓ | ✓ | API enrichment | ✓ |
| CocoaPods | .podspec(.json) | ✓ | ✓ | API enrichment | ✓ |
| Conda | .conda, .tar.bz2 | ✓ | ✓ | API enrichment | ✓ |
| Perl/CPAN | .tar.gz, .zip | ✓ | ✓ | API enrichment | ✓ |
| Conan | conanfile.py/.txt | ✓ | ✓ | - | ✓ |
| Ruby | .gem | ✓ | ✓ | API enrichment | ✓ |
| Rust | .crate | ✓ | ✓ | API enrichment | ✓ |
| Go | .zip, .mod, go.mod | ✓ | ✓ | API enrichment | ✓ |
| NuGet | .nupkg | ✓ | ✓ | API enrichment | ✓ |

## Performance

- **Small packages (< 1MB)**: < 500ms
- **Medium packages (1-50MB)**: < 2 seconds
- **Large packages (50-500MB)**: < 10 seconds
- **Memory usage**: < 100MB for packages under 100MB

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=upmex

# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

## Project Structure

```
semantic-copycat-upmex/
├── src/upmex/
│   ├── core/           # Core models and orchestrator
│   ├── extractors/     # Package-specific extractors
│   ├── detectors/      # License detection engines
│   ├── api/           # External API integrations
│   └── utils/         # Utility functions
├── tests/             # Test suite
├── templates/         # Configuration templates
└── config/           # Default configurations
```

## Release Status

**UPMEX v1.1.2** - Released 2025-08-10

### Supported Features
- **13 Package Ecosystems**: Python, NPM, Java/Maven, Gradle, CocoaPods, Conda, Perl/CPAN, Conan C/C++, Ruby, Rust, Go, NuGet
- **License Detection**: Regex patterns and Dice-Sørensen fuzzy matching with confidence scoring
- **API Integrations**: ClearlyDefined, Ecosyste.ms, Maven Central
- **Offline/Online Modes**: Full functionality without internet connection
- **Comprehensive Testing**: 95+ tests covering all extractors
- **Cross-Platform**: Linux, macOS, Windows support
- **Native Extraction**: No external package managers required
- **Performance**: Sub-second extraction for packages under 50MB

### Successfully Tested With Real Packages
- **Python**: requests, numpy, pandas, Django
- **NPM**: express, react, vue, angular
- **Java/Maven**: guava, spring-boot, jackson
- **Gradle**: Multiple Android and Spring projects
- **CocoaPods**: Alamofire, SDWebImage, FirebaseCore
- **Conda**: numpy, pandas, scikit-learn
- **Perl/CPAN**: Moose, DBI, Catalyst, Mojolicious
- **Conan C/C++**: zlib, boost, openssl, poco
- **Ruby**: rails, sinatra, rspec
- **Rust**: serde, tokio, actix-web
- **Go**: gin, cobra, gorilla/mux
- **NuGet**: Newtonsoft.Json, Serilog, Entity Framework

### Planned Features
- Linux package support (Debian .deb, RPM .rpm)
- Container image metadata extraction
- Performance improvements for large packages (>500MB)
- Batch processing capabilities

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

For major changes, please open an issue first to discuss what you would like to change. Please make sure to update tests as appropriate.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## License

MIT License - see LICENSE file for details.