# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Ruby Gem Support** (Issue #3)
  - Full `.gem` package extraction support
  - Custom YAML loader for Ruby-specific metadata format
  - Extraction from both metadata.gz and data.tar.gz
  - Dependency parsing for runtime and development dependencies
  - Author and email extraction from gemspec
  - License detection from gemspec and LICENSE files
  - Repository URL extraction from metadata URIs
  - Platform and Ruby version requirement extraction
- Ruby gem support in package detector
- API integration for Ruby gems:
  - ClearlyDefined support for gem packages
  - Ecosyste.ms support via rubygems.org registry
- Comprehensive unit tests for Ruby gem extraction
- Successfully tested with real packages (Rails 7.1.5)

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