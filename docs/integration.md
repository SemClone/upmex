---
layout: default
title: Integration
nav_order: 5
description: Registry lookups, enrichment APIs, and using upmex from scripts and CI.
---

# Integration

upmex reads a package and stops there. Two optional layers go further: registry mode
asks the package's own registry about it, and the API integrations ask third party
services. Both are off unless you turn them on, and both make network requests.

## Registry mode

`--registry` lets upmex fetch metadata the archive itself does not carry.

```bash
upmex extract --registry commons-lang3-3.12.0.jar
```

Today this is implemented for Maven Central only. Other ecosystems accept the flag and
ignore it. `upmex info` prints what your build supports.

It does two things for Java packages:

**Following an inherited POM.** A POM often declares almost nothing and inherits its
licence, developers and source location from a parent, which is a separate artifact and
therefore not in the jar. Registry mode fetches the parent and fills in what is missing.

**Resolving a jar with no POM.** Shaded, relocated and repackaged jars frequently ship
no POM at all, which leaves them with no coordinates and nothing to look up. Registry
mode hashes the file and asks the Maven Central index which artifact has that SHA-1,
then reads the published POM for it. `okhttp-4.11.0.jar` carries no POM and no licence,
and comes back as `com.squareup.okhttp3:okhttp` at `4.11.0` under Apache-2.0.

Locally declared data always wins. A registry value is only used where the package
itself said nothing, and `provenance` records which source supplied each field:

```json
"provenance": {
  "name": "maven_central_hash:https://search.maven.org/solrsearch/select",
  "licenses": "maven_central_pom:https://repo1.maven.org/maven2/com/squareup/okhttp3/okhttp/4.11.0/okhttp-4.11.0.pom"
}
```

Lookups are cached by hash for the life of the process, so scanning a directory that
contains the same artifact twice costs one request. The cache is not written to disk, so
a fresh invocation looks everything up again.

Maven Central rate limits its search index, and it does so quickly. A failed lookup is
not an error: upmex reports what it read from the file and moves on, and retries on the
next run rather than remembering the failure.

## API enrichment

`--api` queries third party services. They are independent of `--registry` and can be
combined with it.

| Value | Service | Adds |
|:--|:--|:--|
| `clearlydefined` | ClearlyDefined | curated licence and attribution data |
| `ecosystems` | Ecosyste.ms | registry metadata, maintainers, keywords |
| `purldb` | PurlDB | package records matched by coordinates |
| `vulnerablecode` | VulnerableCode | known vulnerabilities, into `vulnerabilities` |
| `all` | all of the above | |
| `none` | nothing, the default | |

```bash
upmex extract --api clearlydefined lodash-4.17.21.tgz
upmex extract --registry --api all package.jar --pretty
```

Every service that contributes leaves a record in `enrichment`, naming itself and
listing which fields it filled:

```json
"enrichment": [
  {
    "source": "clearlydefined",
    "source_type": "api",
    "timestamp": "2026-08-11T22:00:00",
    "applied_fields": ["licenses", "repository"],
    "data": { }
  }
]
```

`source_type` separates `registry`, meaning the package's own registry, from `api`,
meaning a third party. That distinction matters when you need to say where an assertion
came from.

A lookup needs enough identity to be unambiguous. Maven family packages are only
queried when the groupId is known, because a query by artifact name alone can match a
different project and attribute its licence to yours.

## Using the output

The JSON shape is stable and every section is always present, so you can index into it
without guarding. A few things are worth handling deliberately.

**`purl` can be null.** It is null when the package cannot be identified well enough to
build a valid Package URL. If you are keying records on the PURL, decide what to do with
those rather than letting `null` become a key.

**`repository` can be the string `NO-ASSERTION`.** That is not a URL and not an empty
string. It means the package did not declare one.

**A licence may not be an SPDX identifier.** When a package declares something the
detector cannot classify, the declaration is kept with `source` set to `declared` and
the stated text in `spdx_id`. Check `source` before treating the value as SPDX.

**Diagnostics currently go to standard output.** A damaged archive prints an error line
ahead of the JSON, which breaks a pipe into a parser. Until
[issue #99](https://github.com/SemClone/upmex/issues/99) is fixed, write to a file with
`--output` when the input might be bad.

## In a shell script

```bash
#!/usr/bin/env bash
set -euo pipefail

for package in lib/*; do
    upmex extract "$package" --output /tmp/upmex.json

    name=$(jq -r '.package.name' /tmp/upmex.json)
    licenses=$(jq -r '[.licensing.declared_licenses[].spdx_id] | unique | join(", ")' /tmp/upmex.json)

    if [ -z "$licenses" ]; then
        echo "$name: no licence declared"
    else
        echo "$name: $licenses"
    fi
done
```

## In CI

Failing a build on a licence that is not on an allowed list:

```yaml
name: Licence check

on: [push, pull_request]

jobs:
  licences:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - run: pip install upmex

      - name: Check licences
        run: |
          allowed="MIT Apache-2.0 BSD-2-Clause BSD-3-Clause ISC"
          failed=0

          for package in lib/*; do
            upmex extract "$package" --output result.json
            name=$(jq -r '.package.name' result.json)

            for spdx in $(jq -r '.licensing.declared_licenses[].spdx_id' result.json); do
              case " $allowed " in
                *" $spdx "*) ;;
                *) echo "$name: $spdx is not allowed"; failed=1 ;;
              esac
            done
          done

          exit $failed
```

Leave `--registry` and `--api` off in CI unless you need them. Without them the run is
offline, which makes it reproducible and immune to a registry being slow or rate
limiting you.

## Building an SBOM

upmex does not emit CycloneDX or SPDX directly, but its output carries what those
formats need. A minimal CycloneDX component per package:

```python
import json
from pathlib import Path

from upmex import PackageExtractor

extractor = PackageExtractor()
components = []

for path in sorted(Path("lib").iterdir()):
    if not path.is_file():
        continue

    metadata = extractor.extract(str(path))

    # A bom-ref has to be present and unique, and purl can be null
    ref = metadata.purl or f"{metadata.name}@{metadata.version}"

    components.append({
        "type": "library",
        "bom-ref": ref,
        "name": metadata.name,
        "version": metadata.version,
        "purl": metadata.purl,
        "hashes": [{"alg": "SHA-1", "content": metadata.file_hash}],
        "licenses": [
            {"license": {"id": lic.spdx_id}}
            for lic in metadata.licenses if lic.spdx_id
        ],
    })

sbom = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.5",
    "components": components,
}

print(json.dumps(sbom, indent=2))
```

Note the licence entry. CycloneDX distinguishes `license.id`, which must be a valid
SPDX identifier, from `license.name`, which is free text. A value upmex marked as
`declared` is not an SPDX identifier and belongs in `name`, so a stricter generator
should branch on `detection_method`.

## Other SEMCL.ONE tools

upmex is the metadata reader in a larger toolchain. It pairs with
[osslili](https://github.com/SemClone/osslili) for licence identification, which it uses
internally, and its PURLs are the join key for tools that work from package identity
rather than files.
