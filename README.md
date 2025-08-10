# UPMEX - Universal Package Metadata Extractor

Extract metadata and license information from various package formats with a single tool.

## Features

- **Multi-Ecosystem Support**: Python (wheel, sdist), NPM, Java (JAR, Maven), Gradle, CocoaPods, Conda, Ruby Gems, Rust Crates, Go Modules, NuGet
- **License Detection**: 
  - Regex-based detection for 24+ SPDX identifiers
  - Dice-Sørensen coefficient for fuzzy matching
  - Confidence scoring and multi-license support
- **Offline/Online Modes**: Default offline mode with optional online enrichment
- **NO-ASSERTION Handling**: Clear indication when data cannot be determined
- **Parent POM Fetching**: Automatic retrieval of Maven parent metadata in online mode
- **API Integration**: ClearlyDefined and Ecosyste.ms support in online mode
- **Standardized Output**: Consistent JSON structure across all package types
- **Native Extraction**: No dependency on package managers
- **Comprehensive Testing**: 95+ tests with full coverage

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

## Current Status

UPMEX v0.2.0 is feature-complete with advanced license detection and comprehensive testing.

### Implemented Features
- Package type detection for all supported formats
- **License Detection System**:
  - ✅ Regex-based detection for 24+ SPDX identifiers (Issue #1)
  - ✅ Dice-Sørensen coefficient for fuzzy matching (Issue #2)
  - Confidence scoring and detection method tracking
  - Multi-license detection support
- Offline extraction mode (default) with NO-ASSERTION for missing data
- Online mode with:
  - Maven parent POM fetching from Maven Central
  - ClearlyDefined API integration for license data (Issue #6)
  - Ecosyste.ms API integration for metadata enrichment (Issue #7)
  - POM header comment parsing for license/author info
- Standardized output across all package types
- CLI interface with JSON and text output formats
- Configuration system with environment variables and JSON files
- **Comprehensive test suite with 95+ tests** (Issue #9)

### Tested Packages
- Python: requests-2.32.4 (wheel format) - full metadata extraction
- NPM: express-5.1.0 (tgz format) - complete package.json parsing
- Maven: guava-33.4.0-jre (JAR format) - POM extraction with parent fetching

### Completed Issues
- ✅ Issue #1: Regex-based license detection
- ✅ Issue #2: Dice-Sørensen coefficient
- ✅ Issue #6: ClearlyDefined API integration
- ✅ Issue #7: Ecosyste.ms API integration
- ✅ Issue #9: Comprehensive test suite

### Planned
- Fuzzy hash license detection (Issue #3)
- ML-based license classification (Issue #4)
- API integrations (ClearlyDefined, Ecosyste.ms)
- Performance optimizations for large packages
- GitHub Actions CI/CD pipeline

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

For major changes, please open an issue first to discuss what you would like to change. Please make sure to update tests as appropriate.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## License

MIT License - see LICENSE file for details.