# UPMEX Refactoring Plan

## Overview
Code analysis reveals significant duplicate code across extractors that should be refactored for maintainability.

## Priority 1: Extract Common Utilities

### 1.1 Author Parsing Utility
**Location**: `src/upmex/utils/author_parser.py`
```python
def parse_author_string(author: str) -> Dict[str, str]:
    """Parse 'Name <email>' format into dict with name and email."""
    # Extract common author parsing logic
```

**Affected Files** (10+ extractors):
- npm_extractor.py (lines 48-67)
- python_extractor.py (lines 80-104)
- rust_extractor.py (lines 96-114)
- gradle_extractor.py (lines 221-260)
- All other extractors with similar logic

### 1.2 Archive Utilities
**Location**: `src/upmex/utils/archive_utils.py`
```python
def extract_from_tarball(path: str, target_files: List[str]) -> Dict[str, bytes]:
    """Extract specific files from tar archives."""
    
def extract_from_zip(path: str, target_files: List[str]) -> Dict[str, bytes]:
    """Extract specific files from zip archives."""
```

## Priority 2: Enhance BaseExtractor

### 2.1 Move Common Initialization
```python
class BaseExtractor(ABC):
    def __init__(self, online_mode: bool = False):
        self.online_mode = online_mode
        self.license_detector = LicenseDetector()
```

### 2.2 Add Common License Detection
```python
def detect_licenses_from_files(self, files: Dict[str, str]) -> List[LicenseInfo]:
    """Common license detection logic."""
```

### 2.3 Add Common Error Handling
```python
def safe_extract(self, package_path: str) -> PackageMetadata:
    """Wrapper with common error handling."""
```

## Priority 3: Consolidate Dependency Parsing

### 3.1 Common Dependency Structure
```python
def categorize_dependencies(self, deps: Dict, mapping: Dict[str, str]) -> Dict[str, List]:
    """Map package-specific dependency types to standard categories."""
```

## Files to Modify

### Phase 1: Create Utilities
1. Create `src/upmex/utils/author_parser.py`
2. Create `src/upmex/utils/archive_utils.py`
3. Update imports in all extractors

### Phase 2: Enhance BaseExtractor
1. Update `src/upmex/extractors/base.py`
2. Remove duplicate `__init__` from all extractors
3. Remove duplicate license detection code

### Phase 3: Update Extractors
Update each extractor to use common utilities:
- python_extractor.py
- npm_extractor.py
- java_extractor.py
- gradle_extractor.py
- ruby_extractor.py
- rust_extractor.py
- go_extractor.py
- nuget_extractor.py
- conda_extractor.py
- cocoapods_extractor.py

## Expected Benefits

1. **Code Reduction**: ~500+ lines of duplicate code removed
2. **Maintainability**: Single source of truth for common operations
3. **Consistency**: Uniform behavior across all extractors
4. **Testing**: Easier to test common functionality once
5. **Performance**: Potential for optimization in single location

## Implementation Order

1. **Week 1**: Create utility modules and test
2. **Week 2**: Update BaseExtractor
3. **Week 3**: Migrate extractors one by one
4. **Week 4**: Testing and validation

## Metrics

- Lines of code reduced: ~500-700
- Test coverage maintained: >95%
- Performance impact: Neutral or positive
- Extractors simplified: 10+