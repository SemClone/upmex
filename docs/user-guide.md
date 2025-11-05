# UPMEX User Guide

This guide provides comprehensive documentation for using UPMEX to extract metadata from packages across various ecosystems.

## Table of Contents

1. [Installation](#installation)
2. [Getting Started](#getting-started)
3. [Command Line Interface](#command-line-interface)
4. [Python API](#python-api)
5. [Supported Packages](#supported-packages)
6. [API Enrichment](#api-enrichment)
7. [Configuration](#configuration)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## Installation

### From PyPI

```bash
pip install upmex
```

### From Source

```bash
git clone https://github.com/SemClone/upmex.git
cd upmex
pip install -e .
```

### Development Installation

```bash
pip install -e ".[dev]"
```

### Dependencies

UPMEX requires Python 3.8 or higher. Core dependencies are automatically installed, including:
- osslili for license detection
- Package-specific extractors
- API client libraries

## Getting Started

### Basic Usage

Extract metadata from any supported package:

```bash
upmex extract package.whl
```

This will output JSON metadata to stdout.

### Save to File

```bash
upmex extract package.jar -o metadata.json
```

### Pretty Print

```bash
upmex extract --pretty package.gem
```

## Command Line Interface

### Extract Command

The main command for extracting package metadata:

```bash
upmex extract [OPTIONS] PACKAGE_PATH
```

#### Options

- `-o, --output FILE`: Output file path (default: stdout)
- `--pretty`: Pretty print JSON output
- `--format {json,text}`: Output format (default: json)
- `--registry`: Enable registry lookups
- `--api {clearlydefined,ecosystems,purldb,vulnerablecode,all}`: Enable API enrichment
- `--no-cache`: Disable caching
- `--debug`: Enable debug logging

#### Examples

```bash
# Basic extraction
upmex extract numpy-1.24.0-py3-none-any.whl

# With registry lookup
upmex extract --registry commons-lang3-3.12.0.jar

# With specific API enrichment
upmex extract --api clearlydefined express-4.18.0.tgz

# All enrichments
upmex extract --registry --api all package.gem

# Text format output
upmex extract --format text package.crate
```

### Detect Command

Detect package type without full extraction:

```bash
upmex detect package.jar
# Output: maven
```

### License Command

Extract only license information:

```bash
upmex license package.whl
```

Output:
```json
{
  "licenses": [
    {
      "spdx_id": "MIT",
      "name": "MIT License",
      "file": "LICENSE"
    }
  ]
}
```

## Python API

### Basic Usage

```python
from upmex import PackageExtractor

# Create extractor
extractor = PackageExtractor()

# Extract metadata
metadata = extractor.extract("package.whl")

# Access fields
print(metadata.name)
print(metadata.version)
print(metadata.description)
```

### Advanced Usage

```python
from upmex import PackageExtractor
from upmex.config import Config

# Custom configuration
config = Config(
    enable_registry=True,
    enable_api_enrichment=True,
    api_providers=["clearlydefined", "ecosystems"]
)

# Create extractor with config
extractor = PackageExtractor(config=config)

# Extract with enrichment
metadata = extractor.extract("package.jar")

# Check provenance
print(metadata.provenance)
```

### Working with Results

```python
# Convert to dictionary
data = metadata.to_dict()

# Convert to JSON string
json_str = metadata.to_json(pretty=True)

# Access nested fields
for author in metadata.people.authors:
    print(f"{author.name} <{author.email}>")

for dep in metadata.dependencies.runtime:
    print(f"{dep.name} {dep.version_constraint}")
```

### Batch Processing

```python
from pathlib import Path
from upmex import PackageExtractor

extractor = PackageExtractor()

# Process multiple packages
packages_dir = Path("./packages")
for package_file in packages_dir.glob("*"):
    try:
        metadata = extractor.extract(str(package_file))
        print(f"Processed: {metadata.name}@{metadata.version}")
    except Exception as e:
        print(f"Error processing {package_file}: {e}")
```

## Supported Packages

### Python Packages

#### Wheel (.whl)
```bash
upmex extract numpy-1.24.0-py3-none-any.whl
```

#### Source Distribution (.tar.gz, .zip)
```bash
upmex extract requests-2.28.0.tar.gz
```

### Node.js Packages

#### NPM Tarball (.tgz)
```bash
upmex extract express-4.18.0.tgz
```

### Java Packages

#### JAR Files
```bash
upmex extract commons-lang3-3.12.0.jar
```

#### WAR/EAR Files
```bash
upmex extract webapp.war
```

### Ruby Gems

```bash
upmex extract rails-7.0.0.gem
```

### Rust Crates

```bash
upmex extract serde-1.0.0.crate
```

### Go Modules

```bash
upmex extract github.com-gin-gonic-gin-v1.8.0.zip
```

### .NET/NuGet Packages

```bash
upmex extract Newtonsoft.Json.13.0.1.nupkg
```

### System Packages

#### Debian (.deb)
```bash
upmex extract package.deb
```

#### RPM
```bash
upmex extract package.rpm
```

## API Enrichment

### ClearlyDefined

Provides license and compliance data:

```bash
upmex extract --api clearlydefined package.whl
```

Enhanced fields:
- License clarity score
- Attribution requirements
- Copyright holders
- Source location

### Ecosyste.ms

Package ecosystem data:

```bash
upmex extract --api ecosystems package.jar
```

Enhanced fields:
- Repository statistics
- Dependency tree
- Version history
- Maintainer information

### PurlDB

Comprehensive package database:

```bash
upmex extract --api purldb package.gem
```

Enhanced fields:
- Cross-ecosystem mappings
- Historical versions
- Alternative package names

### VulnerableCode

Security vulnerability data:

```bash
upmex extract --api vulnerablecode package.jar
```

Enhanced fields:
- CVE identifiers
- Vulnerability severity
- Affected version ranges
- Remediation advice

## Configuration

### Configuration File

Create `~/.upmex/config.json`:

```json
{
  "api": {
    "clearlydefined": {
      "enabled": true,
      "api_key": null,
      "base_url": "https://api.clearlydefined.io"
    },
    "ecosystems": {
      "enabled": true,
      "api_key": null,
      "base_url": "https://ecosyste.ms/api/v1"
    }
  },
  "cache": {
    "enabled": true,
    "directory": "~/.cache/upmex",
    "ttl": 86400
  },
  "output": {
    "format": "json",
    "pretty_print": false
  },
  "logging": {
    "level": "INFO",
    "file": null
  }
}
```

### Environment Variables

Override configuration with environment variables:

```bash
# API Keys
export PME_CLEARLYDEFINED_API_KEY=your-key
export PME_ECOSYSTEMS_API_KEY=your-key

# Cache settings
export PME_CACHE_DIR=/custom/cache/path
export PME_CACHE_TTL=3600

# Output settings
export PME_OUTPUT_FORMAT=text
export PME_PRETTY_PRINT=true

# Logging
export PME_LOG_LEVEL=DEBUG
export PME_LOG_FILE=/var/log/upmex.log
```

### Python Configuration

```python
from upmex.config import Config

config = Config()
config.api.clearlydefined.api_key = os.getenv('PME_CLEARLYDEFINED_API_KEY')
config.cache.directory = "/custom/cache"
config.output.pretty_print = True

extractor = PackageExtractor(config=config)
```

## Best Practices

### Performance Optimization

1. **Enable Caching**: Cache API responses to avoid redundant requests
   ```bash
   upmex extract --cache package.jar
   ```

2. **Batch Processing**: Process multiple packages efficiently
   ```python
   from concurrent.futures import ThreadPoolExecutor

   with ThreadPoolExecutor(max_workers=4) as executor:
       results = executor.map(extractor.extract, package_files)
   ```

3. **Selective Enrichment**: Only enable needed API providers
   ```bash
   upmex extract --api ecosystems package.whl
   ```

### Data Quality

1. **Use Registry Mode**: Get authoritative metadata from package registries
   ```bash
   upmex extract --registry package.jar
   ```

2. **Verify Licenses**: Cross-check with multiple sources
   ```bash
   upmex extract --api clearlydefined --api purldb package.gem
   ```

3. **Check Provenance**: Understand data sources
   ```python
   print(metadata.provenance)
   ```

### Error Handling

```python
from upmex import PackageExtractor
from upmex.exceptions import ExtractionError, UnsupportedPackageError

extractor = PackageExtractor()

try:
    metadata = extractor.extract("package.unknown")
except UnsupportedPackageError as e:
    print(f"Package type not supported: {e}")
except ExtractionError as e:
    print(f"Extraction failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Troubleshooting

### Common Issues

#### Package Type Not Detected

```bash
upmex detect package.unknown
# Error: Could not detect package type
```

Solution: Ensure file extension matches package type or specify type explicitly.

#### API Rate Limiting

```
Error: API rate limit exceeded for ecosystems
```

Solution: Use API keys or enable caching:
```bash
export PME_ECOSYSTEMS_API_KEY=your-key
upmex extract --cache package.jar
```

#### Missing Metadata

Some packages may have incomplete metadata. Use registry and API enrichment:
```bash
upmex extract --registry --api all package.jar
```

#### Large Package Processing

For packages over 100MB:
```python
config = Config()
config.processing.max_file_size = 1024 * 1024 * 500  # 500MB
extractor = PackageExtractor(config=config)
```

### Debug Mode

Enable detailed logging:

```bash
upmex extract --debug package.whl
```

Or in Python:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Getting Help

```bash
# Show help
upmex --help
upmex extract --help

# Show version
upmex --version
```

## Integration Examples

### With purl2notices

```bash
# Extract metadata
upmex extract library.jar -o metadata.json

# Generate notices
purl2notices -i metadata.json -o NOTICE.txt
```

### With CI/CD

```yaml
# GitHub Actions example
- name: Extract Package Metadata
  run: |
    pip install upmex
    upmex extract dist/*.whl -o metadata.json

- name: Check Licenses
  run: |
    python -c "
    import json
    with open('metadata.json') as f:
        data = json.load(f)
    licenses = [l['spdx_id'] for l in data['licensing']['licenses']]
    allowed = ['MIT', 'Apache-2.0', 'BSD-3-Clause']
    if not all(l in allowed for l in licenses):
        raise ValueError('Unapproved licenses found')
    "
```

### Custom Processing Pipeline

```python
from upmex import PackageExtractor
from pathlib import Path
import json

def process_package(package_path):
    """Custom package processing pipeline"""

    extractor = PackageExtractor()
    metadata = extractor.extract(package_path)

    # Custom validation
    if not metadata.licenses:
        raise ValueError("No license found")

    # Custom transformation
    result = {
        "purl": metadata.purl,
        "license": metadata.licenses[0].spdx_id if metadata.licenses else None,
        "dependencies": len(metadata.dependencies.runtime),
        "has_vulnerabilities": False  # Add security checks
    }

    return result

# Process all packages in directory
results = []
for package in Path("./packages").glob("*"):
    try:
        result = process_package(str(package))
        results.append(result)
    except Exception as e:
        print(f"Error: {package.name}: {e}")

# Save results
with open("analysis.json", "w") as f:
    json.dump(results, f, indent=2)
```