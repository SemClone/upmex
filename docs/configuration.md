# UPMEX Configuration Guide

This guide covers all configuration options for UPMEX, including configuration files, environment variables, and programmatic configuration.

## Configuration Overview

UPMEX can be configured through multiple methods (in order of precedence):

1. Command-line arguments (highest priority)
2. Environment variables
3. Configuration file
4. Default values (lowest priority)

## Configuration File

### Location

UPMEX looks for configuration files in the following order:

1. Path specified via `--config` CLI option
2. `$UPMEX_CONFIG_PATH` environment variable
3. `~/.upmex/config.json`
4. `/etc/upmex/config.json`

### Format

Configuration files use JSON format:

```json
{
  "api": {
    "clearlydefined": {
      "enabled": true,
      "api_key": null,
      "base_url": "https://api.clearlydefined.io",
      "timeout": 30,
      "retry_count": 3
    },
    "ecosystems": {
      "enabled": true,
      "api_key": null,
      "base_url": "https://ecosyste.ms/api/v1",
      "timeout": 30
    },
    "purldb": {
      "enabled": false,
      "api_key": null,
      "base_url": "https://purldb.com/api",
      "timeout": 30
    },
    "vulnerablecode": {
      "enabled": false,
      "api_key": null,
      "base_url": "https://vulnerablecode.io/api",
      "timeout": 30
    }
  },
  "cache": {
    "enabled": true,
    "directory": "~/.cache/upmex",
    "ttl": 86400,
    "max_size": 1073741824
  },
  "output": {
    "format": "json",
    "pretty_print": false,
    "include_files": false,
    "include_provenance": true
  },
  "processing": {
    "max_file_size": 524288000,
    "timeout": 60,
    "enable_registry": false,
    "parallel_workers": 4
  },
  "logging": {
    "level": "INFO",
    "file": null,
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  }
}
```

## Environment Variables

All configuration options can be set via environment variables using the prefix `PME_` (Package Metadata Extractor).

### API Configuration

```bash
# ClearlyDefined
export PME_CLEARLYDEFINED_ENABLED=true
export PME_CLEARLYDEFINED_API_KEY=your-api-key
export PME_CLEARLYDEFINED_BASE_URL=https://api.clearlydefined.io
export PME_CLEARLYDEFINED_TIMEOUT=30

# Ecosyste.ms
export PME_ECOSYSTEMS_ENABLED=true
export PME_ECOSYSTEMS_API_KEY=your-api-key
export PME_ECOSYSTEMS_BASE_URL=https://ecosyste.ms/api/v1

# PurlDB
export PME_PURLDB_ENABLED=false
export PME_PURLDB_API_KEY=your-api-key

# VulnerableCode
export PME_VULNERABLECODE_ENABLED=false
export PME_VULNERABLECODE_API_KEY=your-api-key
```

### Cache Configuration

```bash
export PME_CACHE_ENABLED=true
export PME_CACHE_DIR=~/.cache/upmex
export PME_CACHE_TTL=86400  # 24 hours in seconds
export PME_CACHE_MAX_SIZE=1073741824  # 1GB in bytes
```

### Output Configuration

```bash
export PME_OUTPUT_FORMAT=json  # or "text"
export PME_PRETTY_PRINT=true
export PME_INCLUDE_FILES=false
export PME_INCLUDE_PROVENANCE=true
```

### Processing Configuration

```bash
export PME_MAX_FILE_SIZE=524288000  # 500MB in bytes
export PME_PROCESSING_TIMEOUT=60  # seconds
export PME_ENABLE_REGISTRY=false
export PME_PARALLEL_WORKERS=4
```

### Logging Configuration

```bash
export PME_LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
export PME_LOG_FILE=/var/log/upmex.log
export PME_LOG_FORMAT="%(asctime)s - %(levelname)s - %(message)s"
```

## Configuration Options

### API Settings

#### ClearlyDefined

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable ClearlyDefined API enrichment |
| `api_key` | string | null | API key for authentication |
| `base_url` | string | https://api.clearlydefined.io | API base URL |
| `timeout` | integer | 30 | Request timeout in seconds |
| `retry_count` | integer | 3 | Number of retry attempts |

#### Ecosyste.ms

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable Ecosyste.ms API enrichment |
| `api_key` | string | null | API key for authentication |
| `base_url` | string | https://ecosyste.ms/api/v1 | API base URL |
| `timeout` | integer | 30 | Request timeout in seconds |

#### PurlDB

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable PurlDB API enrichment |
| `api_key` | string | null | API key for authentication |
| `base_url` | string | https://purldb.com/api | API base URL |
| `timeout` | integer | 30 | Request timeout in seconds |

#### VulnerableCode

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable VulnerableCode API |
| `api_key` | string | null | API key for authentication |
| `base_url` | string | https://vulnerablecode.io/api | API base URL |
| `timeout` | integer | 30 | Request timeout in seconds |

### Cache Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable response caching |
| `directory` | string | ~/.cache/upmex | Cache directory path |
| `ttl` | integer | 86400 | Cache time-to-live in seconds |
| `max_size` | integer | 1073741824 | Maximum cache size in bytes |

### Output Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `format` | string | json | Output format (json, text) |
| `pretty_print` | boolean | false | Pretty print JSON output |
| `include_files` | boolean | false | Include file listings in output |
| `include_provenance` | boolean | true | Include data provenance information |

### Processing Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_file_size` | integer | 524288000 | Maximum file size in bytes (500MB) |
| `timeout` | integer | 60 | Processing timeout in seconds |
| `enable_registry` | boolean | false | Enable package registry lookups |
| `parallel_workers` | integer | 4 | Number of parallel workers |

### Logging Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `level` | string | INFO | Log level (DEBUG, INFO, WARNING, ERROR) |
| `file` | string | null | Log file path (null for stdout) |
| `format` | string | %(asctime)s... | Log message format |

## Programmatic Configuration

### Using Config Class

```python
from upmex.config import Config

# Create config
config = Config()

# Modify settings
config.api.clearlydefined.enabled = True
config.api.clearlydefined.api_key = os.getenv('PME_CLEARLYDEFINED_API_KEY')
config.cache.directory = "/custom/cache"
config.output.pretty_print = True

# Use with extractor
from upmex import PackageExtractor
extractor = PackageExtractor(config=config)
```

### Loading from File

```python
from upmex.config import Config

# Load from file
config = Config()
config.load_from_file("~/.upmex/config.json")

# Modify and save
config.api.ecosystems.enabled = False
config.save("~/.upmex/config.json")
```

### Loading from Environment

```python
from upmex.config import Config

# Load from environment variables
config = Config()
config.load_from_env()

# Environment variables override file config
config.load_from_file("config.json")
config.load_from_env()  # Overrides file settings
```

## Configuration Profiles

### Minimal Configuration

For offline-only extraction:

```json
{
  "api": {
    "clearlydefined": {"enabled": false},
    "ecosystems": {"enabled": false},
    "purldb": {"enabled": false},
    "vulnerablecode": {"enabled": false}
  },
  "processing": {
    "enable_registry": false
  }
}
```

### Performance Configuration

For maximum performance:

```json
{
  "cache": {
    "enabled": true,
    "ttl": 604800,
    "max_size": 5368709120
  },
  "processing": {
    "parallel_workers": 8,
    "timeout": 120
  },
  "api": {
    "clearlydefined": {"timeout": 10, "retry_count": 1},
    "ecosystems": {"timeout": 10}
  }
}
```

### Security-Focused Configuration

For security scanning:

```json
{
  "api": {
    "vulnerablecode": {
      "enabled": true,
      "api_key": "your-key"
    },
    "clearlydefined": {
      "enabled": true,
      "api_key": "your-key"
    }
  },
  "output": {
    "include_provenance": true
  }
}
```

### CI/CD Configuration

For continuous integration:

```json
{
  "output": {
    "format": "json",
    "pretty_print": false,
    "include_provenance": false
  },
  "logging": {
    "level": "WARNING",
    "file": "/var/log/upmex-ci.log"
  },
  "processing": {
    "timeout": 30,
    "max_file_size": 104857600
  }
}
```

## Command-Line Override

Command-line arguments override all other configuration:

```bash
# Override output format
upmex extract --format text package.whl

# Override API settings
upmex extract --no-api package.jar

# Override cache
upmex extract --no-cache package.gem

# Use custom config file
upmex extract --config /path/to/config.json package.whl
```

## Configuration Validation

UPMEX validates configuration on startup:

```python
from upmex.config import Config, validate_config

config = Config()
errors = validate_config(config)

if errors:
    for error in errors:
        print(f"Configuration error: {error}")
```

## Best Practices

### Security

1. **Store API keys securely**: Use environment variables or secure vaults
   ```bash
   export PME_CLEARLYDEFINED_API_KEY=$(vault read secret/api-key)
   ```

2. **Restrict config file permissions**:
   ```bash
   chmod 600 ~/.upmex/config.json
   ```

3. **Don't commit secrets**:
   ```gitignore
   # .gitignore
   config.json
   *.key
   ```

### Performance

1. **Enable caching for repeated extractions**:
   ```json
   {
     "cache": {
       "enabled": true,
       "ttl": 604800
     }
   }
   ```

2. **Adjust parallel workers based on CPU**:
   ```python
   import multiprocessing
   config.processing.parallel_workers = multiprocessing.cpu_count()
   ```

3. **Set appropriate timeouts**:
   ```json
   {
     "processing": {
       "timeout": 60
     },
     "api": {
       "clearlydefined": {
         "timeout": 10
       }
     }
   }
   ```

### Reliability

1. **Configure retry logic**:
   ```json
   {
     "api": {
       "clearlydefined": {
         "retry_count": 3
       }
     }
   }
   ```

2. **Set file size limits**:
   ```json
   {
     "processing": {
       "max_file_size": 104857600
     }
   }
   ```

3. **Enable comprehensive logging**:
   ```json
   {
     "logging": {
       "level": "INFO",
       "file": "/var/log/upmex.log"
     }
   }
   ```

## Troubleshooting Configuration

### Debug Configuration Loading

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from upmex.config import Config
config = Config()
config.load_from_file("config.json")  # Will log loading details
```

### Verify Configuration

```bash
# Check effective configuration
upmex config show

# Validate configuration file
upmex config validate config.json

# Test API connectivity
upmex config test-api
```

### Common Issues

#### API Key Not Working

```bash
# Check if key is loaded
echo $PME_CLEARLYDEFINED_API_KEY

# Test API directly
curl -H "Authorization: Bearer $PME_CLEARLYDEFINED_API_KEY" \
     https://api.clearlydefined.io/definitions
```

#### Cache Not Working

```bash
# Check cache directory permissions
ls -la ~/.cache/upmex

# Clear corrupted cache
rm -rf ~/.cache/upmex/*
```

#### Config File Not Loading

```python
# Debug config file path
from upmex.config import Config
import os

config = Config()
print(f"Looking for config at: {config.get_config_path()}")
print(f"File exists: {os.path.exists(config.get_config_path())}")
```