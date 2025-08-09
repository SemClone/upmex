# Supported Package Formats

## ✅ Implemented (5 formats)

| Format | Extension | Ecosystem | Issue | Status |
|--------|-----------|-----------|-------|--------|
| Python Wheel | `.whl` | PyPI | - | ✅ Complete |
| Python Source | `.tar.gz` | PyPI | - | ✅ Complete |
| NPM | `.tgz` | npm | - | ✅ Complete |
| Maven/Java | `.jar` | Maven Central | - | ✅ Complete |
| Ruby Gem | `.gem` | RubyGems | #3 | ✅ Complete |
| Rust Crate | `.crate` | crates.io | #4 | ✅ Complete |

## 📋 Open Issues (10 formats)

| Format | Extension | Ecosystem | Issue | Priority |
|--------|-----------|-----------|-------|----------|
| NuGet | `.nupkg` | nuget.org | #16 | High |
| Go Module | `.mod`, `.zip` | proxy.golang.org | #17 | High |
| Debian | `.deb` | APT repos | #18 | Medium |
| RPM | `.rpm` | YUM/DNF repos | #19 | Medium |
| Gradle | `build.gradle` | Maven Central | #20 | Medium |
| Perl/CPAN | `.tar.gz` | CPAN | #21 | Low |
| Conan | `.tgz` | conan.io | #22 | Low |
| Conda | `.tar.bz2`, `.conda` | Anaconda | #23 | Medium |
| CocoaPods | `.podspec` | CocoaPods | #24 | Low |

## 🚫 Out of Scope

| Format | Reason | Issue |
|--------|--------|-------|
| Docker Images | Requires container runtime, complex layer system | #10 (Closed) |

## Package Format Details

### Implemented Formats

#### Python (PyPI)
- **Wheel (.whl)**: ZIP archive with METADATA file
- **Source (.tar.gz)**: Tarball with setup.py/pyproject.toml
- **Metadata**: PEP 566 compliant METADATA files

#### NPM (Node.js)
- **Format**: Gzipped tarball with package.json
- **Metadata**: JSON format with dependencies, scripts, etc.

#### Maven/Java
- **JAR**: ZIP archive with optional pom.xml
- **Metadata**: Maven POM (XML) with dependencies

#### Ruby Gems
- **Format**: TAR archive with metadata.gz and data.tar.gz
- **Metadata**: YAML format gemspec

#### Rust Crates
- **Format**: Gzipped tarball with Cargo.toml
- **Metadata**: TOML format with dependencies

### Planned Formats

#### NuGet (.NET/C#)
- **Format**: ZIP archive with .nuspec XML file
- **Priority**: High - Major ecosystem for enterprise

#### Go Modules
- **Format**: go.mod files or proxy.golang.org zips
- **Priority**: High - Growing ecosystem

#### Linux Packages
- **Debian**: ar archive with control.tar.gz
- **RPM**: CPIO archive with spec metadata
- **Priority**: Medium - Important for system packages

#### Build Systems
- **Gradle**: Groovy/Kotlin DSL for Java projects
- **Priority**: Medium - Common alternative to Maven

#### Language-Specific
- **Perl/CPAN**: TAR.GZ with META.json/yml
- **Priority**: Low - Mature but declining usage

#### C/C++
- **Conan**: Python-based package manager
- **Priority**: Low - Specialized use case

#### Scientific/Data Science
- **Conda**: TAR.BZ2 or .conda with info/index.json
- **Priority**: Medium - Important for data science

#### Apple Ecosystem
- **CocoaPods**: Ruby DSL podspec files
- **Priority**: Low - Platform-specific

## API Support Matrix

| Package Type | ClearlyDefined | Ecosyste.ms |
|--------------|----------------|-------------|
| Python | ✅ pypi | ✅ pypi.org |
| NPM | ✅ npm | ✅ npmjs.org |
| Maven | ✅ maven | ✅ repo.maven.apache.org |
| Ruby | ✅ gem | ✅ rubygems.org |
| Rust | ✅ crate | ✅ crates.io |
| NuGet | ✅ nuget | ✅ nuget.org |
| Go | ✅ go | ✅ proxy.golang.org |
| Debian | ✅ deb | ❓ |
| RPM | ✅ rpm | ❓ |
| Perl | ✅ cpan | ✅ cpan.org |
| Conan | ❓ | ✅ conan.io |
| Conda | ❓ | ✅ anaconda.org |
| CocoaPods | ✅ pod | ✅ trunk.cocoapods.org |