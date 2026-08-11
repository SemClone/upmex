---
layout: default
title: Python API
nav_order: 4
description: Using upmex as a library, with the classes and fields it actually exposes.
---

# Python API

The library entry point is `PackageExtractor`. It detects the package type, picks the
right extractor and returns a `PackageMetadata` object.

```python
from upmex import PackageExtractor

extractor = PackageExtractor()
metadata = extractor.extract("requests-2.32.3-py3-none-any.whl")

print(metadata.name)                        # requests
print(metadata.version)                     # 2.32.3
print(metadata.package_type.value)          # python_wheel
print(metadata.purl)                        # pkg:pypi/requests@2.32.3
print([lic.spdx_id for lic in metadata.licenses])   # ['Apache-2.0']
```

`upmex` exports `PackageExtractor`, `PackageMetadata` and `LicenseInfo` at the top
level. Everything else is imported from its module.

## PackageExtractor

```python
PackageExtractor(config: Optional[dict] = None)
```

`config` is a plain dictionary. The key upmex reads directly is `registry_mode`:

```python
extractor = PackageExtractor({"registry_mode": True})
```

Building a `Config` object and passing `config.to_dict()` is the usual way to get the
file and environment settings in as well. See
[Configuration]({{ site.baseurl }}/configuration/).

### extract

```python
extract(package_path: str) -> PackageMetadata
```

Reads the package and returns its metadata. Raises `FileNotFoundError` if the path does
not exist. A file whose type is not recognised does not raise; it comes back with
`package_type` set to `PackageType.UNKNOWN` and only file level fields populated.

Problems encountered while reading a package are reported on standard output rather
than raised, so a damaged archive returns a mostly empty record instead of failing.
Check `metadata.name` against `NO_ASSERTION` if you need to tell that case apart.

## PackageMetadata

A dataclass. Only `name` is required; everything else has a default, so a field being
empty means the package did not declare it.

| Field | Type | Notes |
|:--|:--|:--|
| `name` | `str` | For Maven and jar packages this is `groupId:artifactId` |
| `version` | `str \| None` | |
| `package_type` | `PackageType` | An enum, use `.value` for the string |
| `purl` | `str \| None` | `None` when no valid Package URL can be built |
| `description` | `str \| None` | |
| `homepage` | `str \| None` | |
| `repository` | `str \| None` | May be the string `NO-ASSERTION` |
| `copyright` | `str \| None` | Copyright statements, joined with `; ` |
| `authors` | `list[dict[str, str]]` | Each has `name` and usually `email` |
| `maintainers` | `list[dict[str, str]]` | May also carry `organization` and `role` |
| `licenses` | `list[LicenseInfo]` | |
| `dependencies` | `dict[str, list[str]]` | Keyed by scope, usually `runtime` and `dev` |
| `keywords` | `list[str]` | |
| `classifiers` | `list[str]` | |
| `file_size` | `int \| None` | Bytes |
| `file_hash` | `str \| None` | SHA-1 of the package file |
| `file_hash_md5` | `str \| None` | MD5 of the package file |
| `fuzzy_hash` | `str \| None` | TLSH, ssdeep or a simple fallback, prefixed with the scheme |
| `extraction_timestamp` | `datetime` | When extraction ran |
| `schema_version` | `str` | Version of the output shape |
| `raw_metadata` | `dict` | The unprocessed source, for example a parsed manifest |
| `provenance` | `dict[str, str]` | Field name to the source that supplied it |
| `enrichment` | `list[EnrichmentData]` | One record per external source used |
| `vulnerabilities` | `dict` | Populated by the VulnerableCode integration |

### to_dict

```python
to_dict() -> dict
```

Returns the grouped structure the CLI prints, with sections `package`, `metadata`,
`people`, `licensing`, `dependencies`, `file_info`, `extraction_info`, `provenance`,
`enrichment` and `vulnerabilities`. Use this rather than reading the dataclass fields
if you want the same shape as the JSON output.

Note that `to_dict()` returns the `LicenseInfo` values already flattened, but
`enrichment[].data` holds whatever the source returned. If you serialise the result,
serialise it with a `default=` handler or check that section first.

## LicenseInfo

```python
from upmex.core.models import LicenseInfo
```

| Field | Type | Notes |
|:--|:--|:--|
| `spdx_id` | `str \| None` | The SPDX identifier, or the declared text when it could not be matched |
| `name` | `str \| None` | |
| `text` | `str \| None` | Full licence text when it was captured |
| `confidence` | `float` | `0.0` to `1.0` |
| `confidence_level` | `LicenseConfidenceLevel` | `exact`, `high`, `medium`, `low` or `none` |
| `detection_method` | `str \| None` | How it was found, for example `osslili_tag` or `declared` |
| `file_path` | `str \| None` | Where in the package it was found |

A `detection_method` of `declared` means the package stated a licence that could not be
matched to an SPDX identifier. The stated value is kept in `spdx_id` and `name` so it is
not lost, but it is not a valid SPDX identifier and should not be treated as one.

## EnrichmentData

```python
from upmex.core.models import EnrichmentData
```

Records that an external source contributed to the result. One per source, in
`metadata.enrichment`.

| Field | Type | Notes |
|:--|:--|:--|
| `source` | `str` | For example `maven_central` or `clearlydefined` |
| `source_type` | `str` | `registry` for the package's own registry, `api` for a third party |
| `timestamp` | `datetime` | |
| `data` | `dict` | What the source returned |
| `applied_fields` | `list[str]` | Which fields were filled from it |

## PackageType

```python
from upmex.core.models import PackageType
```

The values are `python_wheel`, `python_sdist`, `npm`, `maven`, `jar`, `gradle`,
`cocoapods`, `conda`, `conan`, `perl`, `ruby_gem`, `rust_crate`, `go_module`, `nuget`,
`rpm`, `deb`, `generic` and `unknown`.

Note that `maven` and `jar` are separate. A jar carrying an embedded POM is `maven`; one
without is `jar`. Both map to the `maven` Package URL type.

## Detecting without extracting

```python
from upmex.utils.package_detector import detect_package_type

package_type = detect_package_type("rails-7.1.5.gem")
print(package_type.value)   # ruby_gem
```

This only inspects enough of the file to classify it, so it is much cheaper than a full
extraction when you are routing files.

## A worked example

Reading a directory of packages and reporting anything without a recognised licence:

```python
from pathlib import Path
from upmex import PackageExtractor
from upmex.core.models import NO_ASSERTION

extractor = PackageExtractor()

for path in sorted(Path("lib").iterdir()):
    if not path.is_file():
        continue

    metadata = extractor.extract(str(path))

    if metadata.name == NO_ASSERTION:
        print(f"{path.name}: could not be read")
        continue

    spdx_ids = [lic.spdx_id for lic in metadata.licenses if lic.spdx_id]
    if spdx_ids:
        print(f"{path.name}: {', '.join(sorted(set(spdx_ids)))}")
    else:
        print(f"{path.name}: no licence declared")
```

Reuse one `PackageExtractor` across files rather than constructing one per file. It
holds the extractor instances, and in registry mode it also benefits from the lookup
cache that lives for the life of the process.
