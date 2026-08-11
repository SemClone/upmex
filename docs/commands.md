---
layout: default
title: Commands
nav_order: 2
description: The upmex command line interface, one section per command.
---

# Commands

upmex has four commands: `extract`, `license`, `detect` and `info`. Global options go
before the command name, command options after it.

```
upmex [--config FILE] [--verbose] [--quiet] COMMAND [OPTIONS]
```

| Global option | Effect |
|:--|:--|
| `-c, --config FILE` | Load settings from a JSON config file. See [Configuration]({{ site.baseurl }}/configuration/). |
| `-v, --verbose` | Print progress while working, including which lookups are being made. |
| `-q, --quiet` | Suppress everything except the result. |

## extract

Reads a package and prints its metadata.

```
upmex extract PACKAGE_PATH [OPTIONS]
```

| Option | Default | Effect |
|:--|:--|:--|
| `-o, --output PATH` | stdout | Write the result to a file. |
| `-f, --format [json\|text]` | `json` | Output format. |
| `-p, --pretty` | off | Indent and sort the JSON. |
| `--registry` | off | Allow lookups against the package's own registry. |
| `--api [clearlydefined\|ecosystems\|purldb\|vulnerablecode\|all\|none]` | `none` | Enrich from third party APIs. |

Both `--registry` and `--api` make network requests. Without them, `extract` only reads
the file.

```bash
upmex extract express-4.21.2.tgz
upmex extract --pretty --output metadata.json guava-33.4.0-jre.jar
upmex extract --format text serde-1.0.210.crate
upmex extract --registry commons-lang3-3.12.0.jar
```

### JSON output

The JSON has a fixed set of top level sections. They are always present, even when
empty, so a consumer can index into them without checking first.

| Section | Contents |
|:--|:--|
| `package` | `name`, `version`, `type`, `purl` |
| `metadata` | `description`, `homepage`, `repository`, `copyright`, `keywords`, `classifiers` |
| `people` | `authors`, `maintainers` |
| `licensing` | `declared_licenses` |
| `dependencies` | Lists keyed by scope, usually `runtime` and `dev` |
| `file_info` | `size` and the `sha1`, `md5` and `fuzzy` hashes |
| `extraction_info` | `timestamp` and `schema_version` |
| `provenance` | Which source supplied each field |
| `enrichment` | One record per external source that contributed |
| `vulnerabilities` | Populated by `--api vulnerablecode` |

`purl` is a [Package URL](https://github.com/package-url/purl-spec), the identifier most
other supply chain tools index on. It is `null` when the package cannot be identified
well enough to build a valid one, which happens for a jar with no coordinates.

Each entry in `declared_licenses` looks like this:

```json
{
  "spdx_id": "Apache-2.0",
  "name": "Apache-2.0",
  "confidence": 1.0,
  "confidence_level": "exact",
  "source": "osslili_tag",
  "file": "pom.xml"
}
```

`confidence_level` is one of `exact`, `high`, `medium`, `low` or `none`. `source` names
the detection method, and `file` names where in the package it was found. A `source` of
`declared` means the package stated a licence that could not be matched to an SPDX
identifier, and the stated text was kept rather than dropped.

### Text output

`--format text` prints a summary for reading rather than parsing.

```
$ upmex extract -f text gson-2.10.1.jar
Package: com.google.code.gson:gson
Version: 2.10.1
Type: maven
Repository: NO-ASSERTION
Licenses:
  - Apache-2.0 (confidence: 100.00%)
Dependencies:
  dev:
    - junit:junit
File Size: 283,367 bytes
SHA1: b3add478d4382b78ea20b1671390a858002feb6c
Schema Version: 1.0.0
```

`NO-ASSERTION` means the package did not declare that field. It is deliberately not an
empty string, so it cannot be confused with a value that was found and happened to be
blank.

## license

Prints only licence information. Useful when that is the one thing you need and you do
not want to parse the full record.

```
upmex license PACKAGE_PATH
```

```
$ upmex license gson-2.10.1.jar
License: Apache-2.0
  Confidence: 100.00%
  Level: exact
  Method: osslili_tag
  Source: pom.xml
```

## detect

Prints the package type without extracting anything. This is cheap, and useful for
routing files in a script.

```
upmex detect PACKAGE_PATH [-v]
```

```
$ upmex detect rails-7.1.5.gem
ruby_gem
```

Add `-v` to also print the file name and size:

```
$ upmex detect -v rails-7.1.5.gem
File: rails-7.1.5.gem
Size: 7,168 bytes
Type: ruby_gem
```

A file upmex does not recognise reports `unknown`. See
[Ecosystems]({{ site.baseurl }}/ecosystems/) for the detection rules.

## info

Prints what this build of upmex supports: package types, registry and API integrations,
and output formats. Add `--json` for a machine readable version.

```
upmex info
upmex info --json
```

This reflects the installed version rather than the documentation, so it is the
quickest way to check whether a feature you read about is present in your build.

## Exit codes and error output

`2` means the path you gave does not exist. That check happens before any work starts.

Everything else exits `0`, including cases you might expect to fail. An unrecognised
file type reports `unknown` and succeeds. A package that is read but declares almost
nothing succeeds, because an empty result is a legitimate answer for a package that
declares nothing.

A damaged archive also exits `0`. upmex reports the file level facts it could still
establish, such as size and hashes, with `NO-ASSERTION` for the rest:

```
$ upmex extract broken.whl; echo "exit=$?"
Error extracting wheel metadata: Failed to extract zip archive: File is not a zip file
{"package": {"name": "NO-ASSERTION", ...}}
exit=0
```

Note where that diagnostic goes. Errors of this kind are currently written to standard
output, ahead of the JSON, which means a pipe into `jq` or a JSON parser will fail to
read the stream rather than reporting the underlying problem. Until that is fixed
([issue #99](https://github.com/SemClone/upmex/issues/99)), a script that must survive
damaged input should write to a file with `--output` and parse that, since `--output`
sends only the record to the file:

```bash
upmex extract "$package" --output result.json
python -c "import json; json.load(open('result.json'))" || echo "could not read $package"
```
