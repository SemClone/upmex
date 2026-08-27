---
layout: default
title: Configuration
nav_order: 6
description: The configuration file schema and the environment variables that override it.
---

# Configuration

upmex runs with sensible defaults and needs no configuration. When you do want to change
something, settings come from three places, each overriding the one before it:

1. built in defaults
2. a JSON file passed with `--config`
3. environment variables

## Using a config file

```bash
upmex --config upmex.json extract package.jar
```

The file is JSON. Only the keys you want to change need to be present; anything omitted
keeps its default.

```json
{
  "extraction": {
    "max_file_size": 1000000000
  },
  "output": {
    "pretty_print": true
  },
  "logging": {
    "level": "DEBUG",
    "file": "/var/log/upmex.log"
  }
}
```

From Python:

```python
from upmex.config import Config
from upmex import PackageExtractor

config = Config("upmex.json")
extractor = PackageExtractor(config.to_dict())
```

## Settings

### api

Third party services used by `--api`. See [Integration]({{ site.baseurl }}/integration/).

| Key | Default | Meaning |
|:--|:--|:--|
| `api.clearlydefined.enabled` | `true` | Whether ClearlyDefined may be used |
| `api.clearlydefined.base_url` | `https://api.clearlydefined.io` | Service endpoint. The bare host: the service serves `/definitions` directly and answers 404 for a `/v1` prefix |
| `api.clearlydefined.timeout` | `30` | Seconds |
| `api.clearlydefined.api_key` | `null` | Optional key |
| `api.ecosystems.enabled` | `true` | Whether Ecosyste.ms may be used |
| `api.ecosystems.base_url` | `https://packages.ecosyste.ms/api/v1` | Service endpoint |
| `api.ecosystems.timeout` | `30` | Seconds |
| `api.ecosystems.api_key` | `null` | Optional key |
| `api.purldb.enabled` | `true` | Whether PurlDB may be used |
| `api.purldb.base_url` | `https://public.purldb.io` | Service endpoint |
| `api.purldb.timeout` | `30` | Seconds |
| `api.purldb.api_key` | `null` | Optional key |
| `api.vulnerablecode.enabled` | `true` | Whether VulnerableCode may be used |
| `api.vulnerablecode.base_url` | `https://public.vulnerablecode.io` | Service endpoint |
| `api.vulnerablecode.timeout` | `30` | Seconds |
| `api.vulnerablecode.api_key` | `null` | Required for vulnerability lookups |

### extraction

| Key | Default | Meaning |
|:--|:--|:--|
| `extraction.max_file_size` | `500000000` | Largest package to read, in bytes. A larger one is refused rather than read |
| `extraction.temp_dir` | system temp | Where archives are unpacked. A package can be larger than the system temp directory allows |

There is no `license_detection` section. Which licences upmex reports is decided by the
evidence osslili returns rather than by a configurable threshold, and the reasoning is
in `src/upmex/licenses/osslili_subprocess.py`.

### output

| Key | Default | Meaning |
|:--|:--|:--|
| `output.format` | `json` | `json` or `text` |
| `output.pretty_print` | `false` | Indent JSON |
| `output.include_raw_metadata` | `false` | Also publish the source documents each field was read from. JSON output only; the text format is a summary |

The `-f` and `--pretty` / `--no-pretty` flags on `extract` take precedence over the file
for a single run. The version stamped into the output is not a setting: it describes the
document, so the document decides it.

### logging

| Key | Default | Meaning |
|:--|:--|:--|
| `logging.level` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `logging.format` | see below | Python logging format string |
| `logging.file` | `null` | Write logs to a file instead of the console |

The default format is `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.

`--verbose` and `--quiet` take precedence over `logging.level` for a single run. A log
file that cannot be opened is reported on standard error and the command carries on
logging to the console.

## Environment variables

Every variable is prefixed `PME_` and overrides both the defaults and the config file.

| Variable | Sets |
|:--|:--|
| `PME_CLEARLYDEFINED_API_KEY` | `api.clearlydefined.api_key` |
| `PME_ECOSYSTEMS_API_KEY` | `api.ecosystems.api_key` |
| `PME_PURLDB_API_KEY` | `api.purldb.api_key` |
| `PME_VULNERABLECODE_API_KEY` | `api.vulnerablecode.api_key` |
| `PME_API_TIMEOUT` | the timeout of every API |
| `PME_MAX_FILE_SIZE` | `extraction.max_file_size` |
| `PME_TEMP_DIR` | `extraction.temp_dir` |
| `PME_OUTPUT_FORMAT` | `output.format` |
| `PME_LOG_LEVEL` | `logging.level` |
| `PME_LOG_FILE` | `logging.file` |

```bash
export PME_LOG_LEVEL=DEBUG
export PME_LOG_FILE=/var/log/upmex.log
upmex extract package.whl
```

Values are converted by shape rather than by declared type. `true` and `false` become
booleans, digits become integers, and a value containing commas becomes a list.

The prefix is `PME_` rather than `UPMEX_` for historical reasons: the project was called
`semantic-copycat-upmex` before it was renamed.

## Reading the configuration

```python
from upmex.config import Config

config = Config()
print(config.get("extraction.max_file_size"))     # 500000000
print(config.get("api.clearlydefined.timeout"))   # 30

config.set("extraction.max_file_size", 1_000_000_000)
config.save("upmex.json")
```

`get()` takes a dot separated path and an optional default. A path that does not exist
returns the default rather than raising.
