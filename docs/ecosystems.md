---
layout: default
title: Ecosystems
nav_order: 3
description: Supported package formats, how each one is recognised, and what upmex reads from it.
---

# Ecosystems

upmex recognises sixteen package types across the ecosystems below. It reads the
archive directly, so the ecosystem's own toolchain does not need to be installed. You
do not need Maven to read a jar or Ruby to read a gem.

## Supported formats

| Type | Recognised by | Metadata read from |
|:--|:--|:--|
| `python_wheel` | `.whl` | `METADATA` |
| `python_sdist` | `.tar.gz` or `.zip` holding `PKG-INFO`, `setup.py` or `pyproject.toml` | `PKG-INFO`, `setup.py`, `pyproject.toml` |
| `npm` | `.tgz` holding `package/package.json` | `package.json` |
| `maven` | `.jar`, `.war` or `.ear` holding `META-INF/maven/**/pom.xml` | the embedded POM |
| `jar` | `.jar`, `.war` or `.ear` with no embedded POM | `META-INF/MANIFEST.MF` |
| `gradle` | a file named `build.gradle`, `build.gradle.kts`, `settings.gradle` or `settings.gradle.kts` | the build script |
| `ruby_gem` | `.gem`, or a tar holding `metadata.gz` | the gemspec |
| `rust_crate` | `.crate`, or a `.tar.gz` holding `Cargo.toml` | `Cargo.toml` |
| `go_module` | `.mod`, a file named `go.mod`, or a `.zip` holding one | `go.mod` |
| `nuget` | `.nupkg` | the `.nuspec` |
| `conda` | `.conda`, or a `.tar.bz2` holding `info/index.json` | `info/index.json`, `info/recipe.json`, `info/recipe/meta.yaml` |
| `conan` | a file named `conanfile.py` or `conanfile.txt`, or a `.tar.gz` holding one | `conanfile.py`, `conanfile.txt`, `conaninfo.txt` |
| `perl` | `.tar.gz` holding `META.json` or `META.yml` | `META.json`, `META.yml`, `MYMETA.json` |
| `cocoapods` | `.podspec` or `.podspec.json` | the podspec |
| `rpm` | `.rpm` | the `rpm` command, or the archive contents as a fallback |
| `deb` | `.deb` | the `dpkg` command, or `control` from the archive as a fallback |

## How detection works

Detection runs before extraction and does not depend on the file name being accurate
beyond its extension. `upmex detect` reports the result on its own.

Most types are decided by extension alone. Where one extension covers several
ecosystems, upmex looks inside the archive:

- **A `.jar` is `maven` or `jar`.** If the archive contains `META-INF/maven/**/pom.xml`
  it is `maven` and the POM is read. If not, it is `jar` and only the manifest is
  available. This distinction matters, because shaded, relocated and repackaged jars
  frequently ship no POM. See [Integration]({{ site.baseurl }}/integration/) for how
  registry mode recovers coordinates for those.
- **A `.tar.gz` is checked in order** for a Rust crate, a Ruby gem, a Perl
  distribution, a Conan package, a Python sdist and finally an npm package. The first
  match wins, so the check is by content rather than by naming convention.
- **A `.zip` is checked** for a Go module and then for a Python sdist.
- **A `.tar.bz2` is checked** for a Conda package before anything else.

Anything unrecognised is reported as `unknown`, and `extract` on it returns file level
facts such as size and hashes with no package metadata.

## Two ecosystems use external tools

RPM and Debian packages are read with `rpm` and `dpkg` when those commands are on the
path, because they handle the container formats properly. When the command is missing,
upmex falls back to reading the archive directly, which still works but recovers less.
This is the only place where results depend on what is installed on the machine, and it
is worth knowing if the same package produces different output on a developer laptop
and in a container. Every other ecosystem is read with Python alone.

## What you get per ecosystem

The output shape is the same for every type, but what a package actually declares
varies a lot. Some patterns worth knowing:

**Dependencies are grouped by scope.** Most ecosystems produce `runtime` and `dev`.
Maven maps `test` scope to `dev` and everything else to `runtime`. A package whose
dependencies are all test scoped shows an empty `runtime`, which is correct and not a
failure to read the file.

**Licence detection is text based.** upmex passes whatever the package declares to
[osslili](https://github.com/SemClone/osslili), and also scans licence files inside the
archive such as `LICENSE` and `COPYING`. A declaration it cannot match to an SPDX
identifier is kept as written, with `source` set to `declared`, rather than being
dropped.

**Maven names are coordinates.** A `maven` or `jar` package is named
`groupId:artifactId`, for example `com.google.code.gson:gson`. That splits into the
namespace and name of the PURL. Other ecosystems use their own name directly.

**Java packages can inherit.** A POM may declare almost nothing itself and inherit its
licence, developers and source location from a parent POM. Reading the archive alone
cannot follow that link, since the parent is a separate artifact. Registry mode can.

## Adding an ecosystem

Extractors live in `src/upmex/extractors/`, one module per ecosystem, each subclassing
`BaseExtractor` and implementing `extract()` and `can_extract()`. A new type needs an
entry in `PackageType`, a detection rule in `src/upmex/utils/package_detector.py` and
registration in `PackageExtractor`. `CONTRIBUTING.md` covers the workflow, and the
existing extractors are the best reference for the shape.
