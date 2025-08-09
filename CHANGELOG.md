# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- License detection implementation (in progress)
  - Regex-based pattern matching (Issue #1)
  - Dice-Sørensen coefficient matching (Issue #2)
  - Fuzzy hash detection (Issue #3)
  - ML-based classification (Issue #4)

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
- Added pre-commit hook to prevent commits with restricted words
- Path validation for safe extraction
- Resource limits for large packages

## [0.0.1] - 2025-08-09

### Added
- Initial repository creation
- Basic project structure
- README and LICENSE files