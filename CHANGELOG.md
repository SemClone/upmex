# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.5] - 2025-10-25

### Added
- **PurlDB API Integration**: New enrichment source for comprehensive package metadata
  - Query packages by PURL (Package URL) for enhanced metadata
  - Extract detailed licensing, authorship, and dependency information
  - Support for all package ecosystems with proper namespace handling
- **VulnerableCode API Integration**: Security vulnerability scanning and assessment
  - PURL-based vulnerability queries for comprehensive security analysis
  - CVSS v3.1 severity scoring with automatic categorization (Critical/High/Medium/Low)
  - Vulnerability aliases (CVE IDs) and fix version recommendations
  - Summary statistics by severity level for quick assessment
- **Enhanced CLI Flag Structure**: Improved separation of concerns
  - Renamed `--online` to `--registry` for clarity (fetches from package registries)
  - Separate `--api` flag for third-party API integrations (clearlydefined, ecosystems, purldb, vulnerablecode)
  - Support for combined usage: `--registry --api all` for comprehensive enrichment
- **Enrichment Tracking System**: Full transparency on data sources
  - Track all external data sources with timestamps and applied fields
  - Clear differentiation between package metadata and external API data
  - Enrichment provenance for compliance and attestation purposes
- **Vulnerability Information Display**: Comprehensive security reporting
  - Text format shows vulnerability counts, severity breakdown, and affected packages
  - JSON format includes detailed vulnerability metadata with CVSS scores
  - Support for both vulnerable and fixing package information

### Changed
- **CLI Structure Reorganization**: Improved flag naming and functionality
  - `--online` flag renamed to `--registry` for clarity
  - API enrichment separated from registry operations for better control
  - Updated help text and examples to reflect new flag structure
- **Info Command Accuracy**: Updated to reflect actual capabilities
  - Corrected registry support information (only Maven Central currently implemented)
  - Removed outdated license detection information (now handled by OSLiLi)
  - Added new API integrations to supported features list
- **Dependency Updates**: Bumped OSLiLi to v1.5.5 for improved license detection

### Enhanced
- **API Integration Coverage**: Expanded external data source support
  - ClearlyDefined: License and compliance data enrichment
  - Ecosystems: Package registry metadata and dependencies
  - PurlDB: Comprehensive package metadata from Package URL database
  - VulnerableCode: Security vulnerability scanning and assessment
- **Output Format Improvements**: Enhanced text and JSON output
  - Vulnerability section in text format with severity breakdown
  - Enrichment data section showing all external data sources
  - Improved formatting for vulnerability information display

### Technical
- Added `VulnerableCodeAPI` class for vulnerability scanning integration
- Added `PurlDBAPI` class for package metadata enrichment
- Enhanced `PackageMetadata` model with vulnerability tracking field
- Updated `OutputFormatter` to display vulnerability and enrichment information
- Improved error handling and API key validation for all integrations
- Maintained backward compatibility while adding new functionality

### Testing
- Comprehensive testing across all package types with new API integrations
- Verified vulnerability scanning functionality (requires API keys for full testing)
- Validated enrichment tracking and data source transparency
- Confirmed proper flag separation between registry and API operations

## [1.6.2] - 2025-10-16

### Added
- Enhanced online mode with intelligent package-type-specific enrichment strategies
- Unified `--online` flag that provides appropriate enrichment for each package type
- Package-type-aware namespace parsing for scoped packages (@scope/name, groupId:artifactId)
- ClearlyDefined API integration for NPM and Python packages in online mode
- Enhanced Maven online mode with Parent POM → ClearlyDefined API fallback chain
- Comprehensive provenance tracking for all enrichment data sources
- Improved error handling and graceful fallbacks for online enrichment

### Fixed
- NPM contributor parsing now correctly includes all contributors as authors
- NuGet copyright field assignment bug that prevented copyright extraction
- Enhanced copyright detection that prioritizes package metadata over file scanning
- Function name corrections in OSLiLi subprocess integration

### Changed
- Maven packages in online mode now use Parent POM fetching with ClearlyDefined fallback
- NPM and Python packages in online mode now use direct ClearlyDefined enrichment
- Online mode behavior is now package-type-specific and more intelligent
- CLI shows compatibility notes when both `--online` and `--api` flags are used together

### Technical
- Added `enrich_with_clearlydefined()` method to BaseExtractor class
- Enhanced Java extractor with ClearlyDefined fallback after Parent POM processing
- Updated CLI integration to unify enrichment under single `--online` flag
- Improved namespace parsing for Maven (groupId:artifactId) and NPM (@scope/name) formats
- Maintained backward compatibility with existing `--api` flag

### Testing
- Comprehensive parity testing shows correct enrichment across all package types
- NPM Express: 2→3 licenses with ClearlyDefined enrichment
- Maven GSON: 0→1 authors with Parent POM enrichment
- Python Requests: 2→3 licenses with ClearlyDefined enrichment
- Maven Guava: 0→1 authors with Parent POM + ClearlyDefined fallback
- Output format consistency maintained between offline and online modes
  - Resolved output formatter test failures

### Removed
- **Cleanup**
  - Removed incorrectly committed gin-test extraction output directory
  - Added gin-test/ to .gitignore to prevent future commits

## [1.6.0] - 2025-10-16

### Changed
- **Major code cleanup after OSLiLi integration**
  - Removed 38,000+ lines of obsolete license detection code
  - Removed entire src/upmex/licenses/data/ directory with 400+ SPDX license files
  - Removed obsolete oslili_detector.py and spdx_manager.py modules
  - Cleaned up unused imports across multiple extractors
  - Removed deprecated CLI flags (--all-methods, --no-cache, --confidence)
  - Removed obsolete docs folder

### Added
- **Comprehensive test package coverage**
  - Added test packages for all 15 supported ecosystems
  - Achieved 100% test success rate across all package types and CLI functions

- **Enhanced Conda support**
  - Added support for new Conda format v2 (.conda with zstandard compression)
  - Improved compatibility with modern conda-forge packages

### Fixed
- **Output formatter improvements**
  - Fixed output formatter to handle both dict and list dependency formats
  - Improved consistency across different package type outputs

## [1.5.9] - 2025-09-17

### Fixed
- **NPM extractor prioritizes root package.json** (#45)
  - Fixed issue where NPM packages with multiple package.json files would use the wrong one
  - Now prioritizes `package/package.json` (root) over nested package.json files
  - Added error handling for empty or corrupt package.json files
  - Resolves homepage field extraction issue for packages like yargs

## [1.5.8] - 2025-09-16

### Fixed
- **Missing toml dependency** (#43)
  - Added toml package as explicit dependency for Rust crate extraction
  - Fixes ImportError when extracting Rust packages in fresh installations

## [1.5.7] - 2025-09-06

### Added
- **RPM Package Support** (#19)
  - New RPM package extractor with filename parsing fallback
  - Optional rpm command integration for richer metadata extraction
  - License normalization from RPM format to SPDX identifiers
  - Dependency extraction when rpm command is available

- **Debian Package Support** (#18)
  - New Debian (.deb) package extractor with filename parsing fallback
  - Optional dpkg command integration for enhanced metadata
  - Control file parsing for package information
  - Copyright file extraction for license detection
  - Dependency parsing with version constraints

### Changed
- Added PackageType.RPM and PackageType.DEB enum values
- Updated package detector to recognize .rpm and .deb file extensions
- Registered new extractors in main PackageExtractor class

### Fixed
- Test format compatibility with new JSON output structure

## [1.5.6] - 2025-09-03

### Fixed
- **oslili License Detection for Short Identifiers**
  - Fixed oslili not detecting short license identifiers like "MIT" or "Apache-2.0"
  - All extractors now format short license text (< 20 chars) as "License: <identifier>" for better oslili tag detection
  - Updated oslili subprocess to handle both JSON formats (scan_results and results) for compatibility
  - Removed similarity threshold filtering to allow tag detection to work properly
  - Fixed EnhancedLicenseDetector minimum text length check from 20 to 2 characters
  - Ensures consistent license detection across all package formats using oslili tags

## [1.5.5] - 2025-09-03

### Added
- **Copyright Statement Extraction**
  - Extracts copyright statements from source files using oslili CLI
  - Adds new `copyright` field to metadata schema
  - Scans up to 100 files per package for copyright information
  - Supports all package formats (NPM, Python, Java, Ruby, Go, Rust, NuGet)

- **Author Unification with Copyright Holders**
  - Automatically merges copyright holders into the authors list
  - Copyright holders are tagged with `source: "copyright"` for provenance
  - Prevents duplicate entries when copyright holder already exists as author
  - Recognizes that copyright holders and authors are often the same people

### Changed
- **License Detection Migration to oslili**
  - Replaced custom license detection with oslili library integration
  - Uses oslili CLI via subprocess for maximum compatibility
  - Improved accuracy with 0.95 confidence threshold
  - Filters known false positives (e.g., Pixar license confusion)

### Fixed
- **oslili JSON Parsing**
  - Fixed parsing of oslili CLI output that includes non-JSON header lines
  - Properly handles both license and copyright detection results
  - Improved error handling for subprocess calls

## [1.5.1] - 2025-09-02

### Fixed
- **Java License Detection Enhancement**
  - Java extractor now scans for license files within JAR archives (e.g., META-INF/LICENSE)
  - Previously relied only on POM metadata for license detection
  - Improves license detection coverage for packages like Guava that include license files but don't declare them in POM
  - Merges detected licenses with existing POM-declared licenses while avoiding duplicates

## [1.5.0] - 2025-08-11

### Added
- **Enhanced License Detection with SPDX Support**
  - Full SPDX license database integration with 400+ official license texts
  - Fuzzy hash (LSH) matching against normalized license texts
  - Improved Dice-Sørensen similarity with trigram analysis
  - Full text similarity comparison using SequenceMatcher
  - License alias resolution (GPL-3.0, GPLv3, GPL v3 all map correctly)
  - Text normalization removing copyright notices, dates, and variables
  - Detection method tracking for provenance and attestation
  - Support for detecting dual/multiple licensing scenarios
  - Automatic extraction of LICENSE, COPYING, COPYRIGHT, NOTICE files from archives

- **File Hashing Improvements**
  - SHA-1 hash for package files (industry standard)
  - MD5 hash for legacy compatibility
  - TLSH/LSH fuzzy hash for similarity detection
  - All hashes included in file_info section

- **Package URL (PURL) Generation**
  - Standard Package URL generation for all supported package types
  - Follows PURL specification for cross-ecosystem compatibility

- **JSON Output Reorganization**
  - Structured sections: package, metadata, people, licensing, dependencies, file_info, extraction_info, provenance
  - Clear separation of concerns for better parsing
  - Provenance tracking showing data sources for each field

- **API Improvements**
  - Fixed ClearlyDefined API URL format (removed /v1, added provider)
  - Better online mode data enrichment without overwriting existing data
  - Improved maintainer extraction from Ecosyste.ms API

- **Developer Experience**
  - Templates directory removed (unused)
  - License manager for SPDX data caching and management
  - Enhanced detector with fallback chain for maximum detection rate

### Changed
- License detection now uses multiple methods in priority order:
  1. SPDX-License-Identifier exact matching
  2. Fuzzy hash matching against SPDX texts
  3. Dice-Sørensen similarity comparison
  4. Full text similarity matching
  5. Regex pattern matching (fallback)
- Description fields now normalized to remove extra whitespace
- Online mode only enriches missing data instead of overwriting
- Parent POM extraction includes description field
- Developer extraction handles id/organization when name/email missing

### Fixed
- ClearlyDefined API now working correctly with proper URL format
- JSON output provenance tracking for data attestation
- Author extraction from Maven POMs with only organization field
- Description extraction from parent POMs
- Maintainer information properly extracted from all sources

### Performance
- SPDX license texts cached locally for offline operation
- Pre-computed fuzzy hashes for all license texts
- Efficient fallback chain minimizes processing time

### Testing
- All 11 test packages now correctly detect licenses
- Enhanced detection achieves 100% success rate on test suite
- Multiple detection methods provide validation and higher confidence

## [1.1.3] - 2025-08-10

### Changed
- **Major Code Refactoring** - Eliminated significant code duplication across all extractors
  - Enhanced BaseExtractor with common functionality for license detection, author parsing, and archive extraction
  - Created reusable utility modules: author_parser.py for consistent author string parsing
  - Created archive_utils.py for common archive extraction operations
  - All 11 extractors now use consistent patterns and share common functionality
  - Reduced codebase size by approximately 30-40% while maintaining full functionality
  - Improved maintainability and consistency across all package format extractors

### Fixed
- Fixed indentation issues in Rust extractor that prevented proper parsing
- Updated all extractors to correctly handle list returns from detect_licenses_from_text method
- Fixed Java extractor missing maven_central_url attribute for online mode
- Corrected test assertions to match current version numbering

## [1.1.2] - 2025-08-10

### Added
- **Perl/CPAN Package Support** (Issue #21)
  - Full support for `.tar.gz` and `.zip` Perl packages
  - Parse `META.json` and `META.yml` metadata files
  - Support for `MYMETA.json` and `MYMETA.yml` (build-time metadata)
  - Extract dependencies with phase (runtime, test, configure) and relationship info
  - Map Perl license strings to SPDX identifiers
  - Author parsing with email extraction
  - License file detection (LICENSE, COPYING, ARTISTIC, GPL)
- **Conan C/C++ Package Support** (Issue #22)
  - Support for `conanfile.py` (Python-based recipes) and `conanfile.txt` (INI-style)
  - Parse `conaninfo.txt` for package metadata
  - Extract from `.tgz` package archives
  - AST-based and regex-based parsing for Python files
  - Dependencies with version constraints and tool_requires
  - Multi-license support with comma-separated values
  - Topics extraction as keywords
- **Conda Package Support** (Issue #23)
  - Full support for `.conda` (new zip-based format) and `.tar.bz2` (traditional format) packages
  - Parse `info/index.json` for core package metadata
  - Parse `info/recipe/meta.yaml` or `info/recipe.json` for detailed build information
  - Metadata extraction: name, version, build string, build number
  - Dependency parsing: runtime, build, host dependencies with version constraints
  - License detection from package metadata
  - Author/maintainer extraction from recipe maintainers
  - Platform and architecture information (subdir)
  - Channel and feature tracking
  - Homepage and repository URL extraction
  - Support for both conda-forge and Anaconda repository packages
- **CocoaPods Support** (Issue #24)
  - Full support for `.podspec` (Ruby DSL) and `.podspec.json` files
  - Support for both Ruby DSL and JSON podspec formats
  - Metadata extraction: name, version, summary, description
  - Platform requirements parsing (iOS, macOS, tvOS, watchOS, visionOS)
  - Dependency parsing with version requirements
  - License detection from podspec configuration and external files
  - Author and maintainer extraction from podspec metadata
  - Repository URL extraction from source configuration
  - Homepage URL extraction from podspec
  - Framework and library dependencies
  - Keywords extraction from platforms and frameworks
  - Compatible with all CocoaPods project types
- **Gradle Build File Support** (Issue #20)
  - Full support for `build.gradle` and `build.gradle.kts` files
  - Support for both Groovy DSL and Kotlin DSL syntax
  - Metadata extraction: name, version, group, description
  - Dependency parsing for implementation, api, runtime, and test scopes
  - License detection from publishing/pom configuration blocks
  - Author/developer extraction from publishing metadata
  - Repository URL extraction from SCM configuration
  - Homepage URL extraction from publishing configuration
  - Keywords extraction from project metadata
  - Compatible with Gradle projects and multi-module builds
- **Ruby Gem Support** (Issue #3)
  - Full `.gem` package extraction support
  - Custom YAML loader for Ruby-specific metadata format
  - Extraction from both metadata.gz and data.tar.gz
  - Dependency parsing for runtime and development dependencies
  - Author and email extraction from gemspec
  - License detection from gemspec and LICENSE files
  - Repository URL extraction from metadata URIs
  - Platform and Ruby version requirement extraction
- **Rust Crate Support** (Issue #4)
  - Full `.crate` package extraction support
  - Cargo.toml parsing with TOML library
  - Support for Cargo.toml.orig when available
  - Dependency extraction (normal, dev, build dependencies)
  - Target-specific dependency parsing with platform annotations
  - Author email parsing from "Name <email>" format
  - Keywords and categories extraction
  - Rust edition detection
  - License detection from Cargo.toml and LICENSE files
- **Go Module Support** (Issue #17)
  - Full Go module package extraction support
  - Support for .zip archives from proxy.golang.org
  - Parse go.mod files for module metadata
  - Extract require, indirect, and replace dependencies
  - Infer repository URLs from module paths (GitHub, GitLab, etc.)
  - Go version requirement extraction
  - License detection from LICENSE files in archives
  - Description extraction from README files
- **NuGet Package Support** (Issue #16)
  - Full `.nupkg` package extraction support
  - XML-based .nuspec metadata parsing with namespace handling
  - Dependency extraction with target framework annotations
  - Support for grouped and flat dependency formats
  - License extraction from expressions, files, and URLs
  - Framework assembly dependency tracking
  - Author and owner (maintainer) extraction
  - Tags (keywords) and release notes parsing
  - Repository URL extraction from multiple sources
  - Modern and legacy NuGet format compatibility
- Package detector enhancements:
  - Ruby gem detection by .gem extension and tar structure
  - Rust crate detection by .crate extension and Cargo.toml presence
  - Go module detection by .mod files and .zip archives with go.mod
  - NuGet package detection by .nupkg extension and .nuspec presence
- API integration for new package types:
  - ClearlyDefined support for gem, crate, go, and nuget packages
  - Ecosyste.ms support via rubygems.org, crates.io, proxy.golang.org, and nuget.org registries
- Successfully tested with real packages:
  - Perl: Moose 2.2207 (177 dependencies extracted)
  - Conan: zlib example with full metadata
  - Conda: numpy 1.21.5, pandas 1.5.3 (from Anaconda repository)
  - CocoaPods: Alamofire 5.10.2, SDWebImage 5.21.1, FirebaseCore 12.2.0
  - Ruby: Rails 7.1.5
  - Rust: serde 1.0.210, tokio 1.41.0
  - Go: gin v1.10.0, cobra v1.8.1
  - NuGet: Newtonsoft.Json 13.0.3, Serilog 3.1.1

### Fixed
- urllib3 LibreSSL warning suppression on macOS systems
  - Added warning filters at module initialization
  - Prevents NotOpenSSLWarning from appearing in CLI output
  - Ensures clean user experience on systems with LibreSSL

### Changed
- Version updated to 1.1.2
- Updated development status to stable

## [0.2.0] - 2025-08-09

### Added
- **License Detection System** (Issues #1, #2)
  - Regex-based license detection for 24+ SPDX identifiers
  - Dice-Sørensen coefficient for fuzzy license matching
  - Confidence scoring and detection method tracking
  - Multi-license detection support
  - Integration with all package extractors
- **License Detection Module** (`src/upmex/utils/license_detector.py`)
  - Pattern matching for metadata fields
  - SPDX normalization
  - License file detection
- **Dice-Sørensen Implementation** (`src/upmex/utils/dice_sorensen.py`)
  - N-gram based text similarity
  - Bigram and unigram matching strategies
  - Pre-computed license snippet database
- **Comprehensive Test Suite**
  - 95+ tests covering all functionality
  - Unit tests for license detection algorithms
  - Integration tests for package extraction
  - End-to-end tests for CLI commands
- Online mode (--online flag) for enhanced metadata extraction
  - Maven parent POM fetching from Maven Central
  - ClearlyDefined API integration for license information
  - Ecosyste.ms API integration for metadata enrichment
  - POM header comment parsing for license and author data
- NO-ASSERTION constant for fields where data cannot be determined
- Standardized metadata output across all package types
- Improved author parsing with consistent name/email separation
- Repository URL extraction for Python packages
- Developer extraction from Maven POMs

### Changed
- Standardized author format across all extractors (dict with name/email)
- Maven extractor now fetches parent POMs in online mode
- Python extractor now extracts repository from Project-URL metadata
- Default mode is offline (no external API calls)

### Fixed
- Maven package name extraction now uses parent groupId when needed
- Author email parsing for combined "Name <email>" format
- Repository URL extraction for all package types

### Removed
- YAML output format (was broken due to missing PyYAML dependency)

## [0.1.0] - 2025-08-09

### Added
- Initial project setup and structure
- Core package extraction framework
- Multi-ecosystem package support:
  - Python packages (wheel, sdist)
  - NPM packages (tgz)
  - Java/Maven packages (JAR)
- Package type auto-detection
- CLI interface with commands:
  - `extract`: Extract metadata from packages
  - `detect`: Detect package type
  - `license`: Extract license information
  - `info`: Show tool information
- Output format support (JSON, YAML, text)
- Configuration system with environment variable support
- Comprehensive test suite

### Tested
- Successfully tested extraction against real packages:
  - Python: requests-2.32.4 (wheel) - full metadata extraction
  - NPM: express-5.1.0 (tgz) - complete package.json parsing
  - Maven: guava-33.4.0-jre (JAR) - POM metadata extraction
- Verified all core metadata fields are properly extracted:
  - Package name, version, description
  - Authors, maintainers, homepage
  - Dependencies (runtime and dev)
  - Keywords, classifiers, repository info

### Changed
- Renamed project from `package-metadata-extractor` to `semantic-copycat-upmex`
- Renamed CLI command from `package-metadata-extractor` to `upmex`
- Simplified source structure from `package_metadata_extractor` to `upmex`
- Changed license from Apache 2.0 to MIT

### Removed
- Batch processing functionality (focus on single package extraction)
- CSV and JSONL output formats
- Batch command from CLI

### Security
- Path validation for safe extraction
- Resource limits for large packages

## [0.0.1] - 2025-08-09

### Added
- Initial repository creation
- Basic project structure
- README and LICENSE files