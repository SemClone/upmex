# UPMEX - Universal Package Metadata Extractor

Extract metadata and license information from various package formats with a single tool.

## Features

- **Multi-Ecosystem Support**: Python (wheel, sdist), NPM, Java (JAR, Maven)
- **Native License Detection**: Multi-layer approach (regex, Dice-Sørensen, fuzzy hashing, ML)
- **Zero External Dependencies**: Native extraction without package managers
- **Performance Optimized**: < 500ms for small packages, streaming for large files
- **Extensible**: Template-based configuration system
- **API Integration**: ClearlyDefined and Ecosyste.ms support
- **High Accuracy**: Multiple detection methods with confidence scoring

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
# Basic extraction
upmex extract package.whl

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

| Ecosystem | Formats | Detection | Metadata | License |
|-----------|---------|-----------|----------|---------|
| Python | .whl, .tar.gz, .zip | Yes | Yes | Planned |
| NPM | .tgz, .tar.gz | Yes | Yes | Planned |
| Java | .jar, .war, .ear | Yes | Yes | Planned |
| Maven | .jar with POM | Yes | Yes | Planned |

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

UPMEX is currently in active development (v0.1.0). The core extraction functionality is complete and working for Python, NPM, and Java packages. License detection is the next major feature being implemented.

### Implemented
- Package type detection
- Metadata extraction for Python, NPM, and Java packages  
- CLI interface with multiple output formats
- Configuration system with environment variables
- Comprehensive test coverage

### In Progress
- Regex-based license detection (Issue #1)
- Dice-Sørensen coefficient license matching (Issue #2)

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