# Package Metadata Extractor

A comprehensive package metadata extraction tool supporting multiple ecosystems with native license detection capabilities.

## Features

- 🚀 **Multi-Ecosystem Support**: Python (wheel, sdist), NPM, Java (JAR, Maven)
- 🔍 **Native License Detection**: Multi-layer approach (regex, Dice-Sørensen, fuzzy hashing, ML)
- 📦 **Zero External Dependencies**: Native extraction without package managers
- ⚡ **Performance Optimized**: < 500ms for small packages, streaming for large files
- 🔧 **Extensible**: Template-based configuration system
- 🌐 **API Integration**: ClearlyDefined and Ecosyste.ms support
- 🎯 **High Accuracy**: Multiple detection methods with confidence scoring

## Installation

```bash
# Install from source
git clone https://github.com/oscarvalenzuelab/semantic-copycat-upex.git
cd semantic-copycat-upex
pip install -e .

# Install with all features
pip install -e ".[all]"

# Install for development
pip install -e ".[dev]"
```

## Quick Start

```python
from package_metadata_extractor import PackageExtractor

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

## CLI Usage (Coming Soon)

```bash
# Basic extraction
package-metadata-extractor extract package.whl

# With API enrichment
package-metadata-extractor extract --api clearlydefined package.whl

# Batch processing
package-metadata-extractor batch packages.txt --output results.json

# License detection only
package-metadata-extractor license package.tar.gz
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
| Python | .whl, .tar.gz, .zip | ✅ | ✅ | ✅ |
| NPM | .tgz, .tar.gz | ✅ | ✅ | ✅ |
| Java | .jar, .war, .ear | ✅ | ✅ | ✅ |
| Maven | .jar with POM | ✅ | ✅ | ✅ |

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
pytest tests/ --cov=package_metadata_extractor

# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

## Project Structure

```
semantic-copycat-upex/
├── src/package_metadata_extractor/
│   ├── core/           # Core models and orchestrator
│   ├── extractors/     # Package-specific extractors
│   ├── detectors/      # License detection engines
│   ├── api/           # External API integrations
│   └── utils/         # Utility functions
├── tests/             # Test suite
├── templates/         # Configuration templates
└── config/           # Default configurations
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Author

**Oscar Valenzuela B.**  
Email: oscar.valenzuela.b@gmail.com  
GitHub: [@oscarvalenzuelab](https://github.com/oscarvalenzuelab)