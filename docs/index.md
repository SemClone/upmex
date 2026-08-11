---
layout: default
title: Overview
nav_order: 1
description: What upmex does, how to install it, and how to run it for the first time.
permalink: /
---

# upmex

upmex reads a package file and tells you what is inside it: the name and version, the
licence, who wrote it, where the source lives, and what it depends on. It works on
package archives from many ecosystems without needing that ecosystem's toolchain
installed, so you can point it at a jar, a wheel, a gem or a crate and get the same
shape of answer back.

It is built for licence compliance and software supply chain work, where the question
is usually "what is this file, and what am I allowed to do with it". That focus shows
up in two places. Every value it reports can be traced to where it came from, and it
does not invent an answer when the package does not declare one.

## Installing

```bash
pip install upmex
```

upmex needs Python 3.8 or later. Licence detection uses
[osslili](https://github.com/SemClone/osslili), which is installed along with it.

To work on upmex itself, install it from a checkout in editable mode:

```bash
git clone https://github.com/SemClone/upmex.git
cd upmex
pip install -e .
```

## First run

Point `extract` at any package file:

```bash
upmex extract requests-2.32.3-py3-none-any.whl --pretty
```

The output is JSON grouped into sections. Trimmed to the parts most people want first:

```json
{
  "package": {
    "name": "requests",
    "version": "2.32.3",
    "type": "python_wheel",
    "purl": "pkg:pypi/requests@2.32.3"
  },
  "licensing": {
    "declared_licenses": [
      {
        "spdx_id": "Apache-2.0",
        "name": "Apache-2.0",
        "confidence": 1.0,
        "confidence_level": "exact",
        "source": "osslili_tag",
        "file": null
      }
    ]
  },
  "file_info": {
    "size": 64928,
    "hashes": {
      "sha1": "c7e25779bcff4f82f2f002cd0503ceabf433378f",
      "md5": "83d50f7980b330c48f3bfe86372adcca",
      "fuzzy": "tlsh:T14D53F1B3E3624111E91711F2FAB187D56E99F2323048F07CA468B48ECE83C95FA8B945"
    }
  }
}
```

If you only care about the licence, `license` prints just that:

```bash
$ upmex license gson-2.10.1.jar
License: Apache-2.0
  Confidence: 100.00%
  Level: exact
  Method: osslili_tag
  Source: pom.xml
```

## Two things worth knowing early

**upmex is offline by default.** A plain `extract` reads the file and nothing else. No
network request is made unless you ask for one with `--registry` or `--api`. That keeps
results reproducible and lets the tool run in a sealed build environment.

**Missing is not the same as unknown.** When a package does not declare a value, upmex
leaves the field empty or writes `NO-ASSERTION` rather than guessing. A field that is
present is a field the package actually declared, or one that a registry lookup
supplied and recorded in `provenance`.

## Where to go next

| Page | What it covers |
|:--|:--|
| [Commands]({{ site.baseurl }}/commands/) | Every CLI command and flag, with real output |
| [Ecosystems]({{ site.baseurl }}/ecosystems/) | Which formats are supported and what is read from each |
| [Python API]({{ site.baseurl }}/api/) | Using upmex as a library |
| [Integration]({{ site.baseurl }}/integration/) | Registry lookups, enrichment APIs, CI, SBOM output |
| [Configuration]({{ site.baseurl }}/configuration/) | Config file schema and environment variables |
