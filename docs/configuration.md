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
  "license_detection": {
    "confidence_threshold": 0.9
  },
  "output": {
    "pretty_print": true
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
| `api.clearlydefined.base_url` | `https://api.clearlydefined.io/v1` | Service endpoint |
| `api.clearlydefined.timeout` | `30` | Seconds |
| `api.clearlydefined.api_key` | `null` | Optional key |
| `api.ecosystems.enabled` | `true` | Whether Ecosyste.ms may be used |
| `api.ecosystems.base_url` | `https://api.ecosyste.ms/v1` | Service endpoint |
| `api.ecosystems.timeout` | `30` | Seconds |
| `api.ecosystems.api_key` | `null` | Optional key |

### extraction

| Key | Default | Meaning |
|:--|:--|:--|
| `extraction.max_file_size` | `500000000` | Largest package to read, in bytes |
| `extraction.temp_dir` | system temp | Where archives are unpacked |
| `extraction.parallel_processing` | `false` | Reserved, not yet used |
| `extraction.cache_enabled` | `true` | Reserved, not yet used |
| `extraction.cache_dir` | `~/.cache/pme` | Reserved, not yet used |

The three cache settings are read into the configuration but nothing acts on them yet.
Registry lookups are cached in memory for the life of the process regardless, and
nothing is written to disk.

### license_detection

| Key | Default | Meaning |
|:--|:--|:--|
| `license_detection.methods` | `["regex", "dice_sorensen"]` | Detection methods, in order |
| `license_detection.confidence_threshold` | `0.85` | Minimum confidence to report |
| `license_detection.max_text_length` | `100000` | Largest text to analyse |
| `license_detection.enable_ml` | `false` | Requires the optional ml extra |

### output

| Key | Default | Meaning |
|:--|:--|:--|
| `output.format` | `json` | `json` or `text` |
| `output.pretty_print` | `true` | Indent JSON |
| `output.include_raw_metadata` | `false` | Include the unprocessed source |
| `output.schema_version` | `1.0.0` | Version stamped into the output |

The `-f` and `-p` flags on `extract` take precedence over the file for a single run.

### logging

| Key | Default | Meaning |
|:--|:--|:--|
| `logging.level` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `logging.format` | see below | Python logging format string |
| `logging.file` | `null` | Write logs to a file instead of the console |

The default format is `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.

Note that extractors currently report problems with plain writes to standard output
rather than through logging, so these settings do not yet control everything you see.
That is [issue #99](https://github.com/SemClone/upmex/issues/99).

## Environment variables

Every variable is prefixed `PME_` and overrides both the defaults and the config file.

| Variable | Sets |
|:--|:--|
| `PME_CLEARLYDEFINED_API_KEY` | `api.clearlydefined.api_key` |
| `PME_ECOSYSTEMS_API_KEY` | `api.ecosystems.api_key` |
| `PME_API_TIMEOUT` | the timeout of every API |
| `PME_MAX_FILE_SIZE` | `extraction.max_file_size` |
| `PME_TEMP_DIR` | `extraction.temp_dir` |
| `PME_CACHE_DIR` | `extraction.cache_dir` |
| `PME_CACHE_ENABLED` | `extraction.cache_enabled` |
| `PME_LICENSE_CONFIDENCE` | `license_detection.confidence_threshold` |
| `PME_LICENSE_METHODS` | `license_detection.methods` |
| `PME_ENABLE_ML` | `license_detection.enable_ml` |
| `PME_OUTPUT_FORMAT` | `output.format` |
| `PME_LOG_LEVEL` | `logging.level` |
| `PME_LOG_FILE` | `logging.file` |

```bash
export PME_LOG_LEVEL=DEBUG
export PME_LICENSE_CONFIDENCE=0.9
upmex extract package.whl
```

Values are converted by shape rather than by declared type. `true` and `false` become
booleans, digits become integers, and a value containing commas becomes a list. So
`PME_LICENSE_METHODS=regex,dice_sorensen` sets a two element list.

The prefix is `PME_` rather than `UPMEX_` for historical reasons: the project was called
`semantic-copycat-upmex` before it was renamed.

## Reading the configuration

```python
from upmex.config import Config

config = Config()
print(config.get("extraction.max_file_size"))     # 500000000
print(config.get("api.clearlydefined.timeout"))   # 30

config.set("license_detection.confidence_threshold", 0.9)
config.save("upmex.json")
```

`get()` takes a dot separated path and an optional default. A path that does not exist
returns the default rather than raising.
