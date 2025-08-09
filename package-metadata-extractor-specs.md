## Performance Requirements and Optimization

### Single Package Processing Targets
- **Small packages (< 1MB)**: < 500ms total processing time
- **Medium packages (1-50MB)**: < 2 seconds total processing time  
- **Large packages (50-500MB)**: < 10 seconds total processing time
- **Memory usage**: < 100MB RAM for packages under 100MB
- **License detection**: < 100ms per file using regex, < 500ms using Dice-Sørensen

### Optimization Strategies
```python
class PerformanceOptimizer:
    """Optimize processing for single-package speed"""
    
    def __init__(self):
        self.file_size_cache = {}
        self.license_detection_cache = {}
        self.metadata_cache = {}
    
    def optimize_extraction(self, package_path: str) -> ExtractionStrategy:
        """Choose optimal extraction strategy based on package characteristics"""
        file_size = os.path.getsize(package_path)
        
        if file_size < 1_000_000:  # < 1MB - extract everything
            return FullExtractionStrategy()
        elif file_size < 50_000_000:  # < 50MB - selective extraction
            return SelectiveExtractionStrategy()
        else:  # > 50MB - streaming extraction
            return StreamingExtractionStrategy()
    
    def should_use_ml_detection(self, text_length: int, confidence_so_far: float) -> bool:
        """Decide whether to use expensive ML detection"""
        # Skip ML if we already have high confidence or text is very long
        if confidence_so_far > 0.95:
            return False
        if text_length > 100_000:  # Very long files - skip ML
            return False
        return True

class StreamingExtractionStrategy:
    """Extract large packages without loading everything into memory"""
    
    def extract_metadata_files_only(self, archive_path: str) -> Dict[str, bytes]:
        """Extract only metadata files from large archives"""
        metadata_files = {}
        
        with self._open_archive(archive_path) as archive:
            for member in archive:
                if self._is_metadata_file(member.name):
                    # Only extract files likely to contain metadata
                    if member.size < 10_000_000:  # Skip very large "metadata" files
                        metadata_files[member.name] = archive.read(member)
                
                # Stop after finding key files to save time
                if len(metadata_files) > 20:  # Reasonable limit
                    break
        
        return metadata_files
```

## Testing Strategy

### Test Package Repository Structure
```
tests/
├── fixtures/
│   ├── packages/
│   │   ├── python/
│   │   │   ├── simple_wheel.whl          # Basic wheel with clear metadata
│   │   │   ├── complex_wheel.whl         # Wheel with multiple licenses
│   │   │   ├── malformed_wheel.whl       # Corrupted/incomplete wheel
│   │   │   └── source_dist.tar.gz        # Source distribution
│   │   ├── javascript/
│   │   │   ├── simple_npm.tgz            # Basic npm package
│   │   │   ├── scoped_package.tgz        # @scope/package
│   │   │   ├── no_license.tgz            # Package without license info
│   │   │   └── dual_license.tgz          # Package with dual licensing
│   │   ├── java/
│   │   │   ├── simple_jar.jar            # Basic JAR with manifest
│   │   │   ├── maven_jar.jar             # JAR with Maven metadata
│   │   │   └── unsigned_jar.jar          # JAR without signatures
│   │   └── generic/
│   │       ├── unknown_archive.tar.gz    # Archive with mixed content
│   │       ├── empty_archive.zip         # Empty archive
│   │       └── corrupted_archive.zip     # Corrupted archive
│   ├── license_texts/
│   │   ├── mit_license.txt               # Standard MIT license
│   │   ├── apache_2_license.txt          # Apache 2.0 license
│   │   ├── modified_mit.txt              # MIT with modifications
│   │   └── custom_license.txt            # Non-standard license
│   └── expected_results/
│       ├── simple_wheel_expected.json    # Expected output for each test package
│       ├── complex_wheel_expected.json
│       └── ...
├── unit/
│   ├── test_license_detection.py         # License detection algorithm tests
│   ├── test_package_detection.py         # Package type detection tests
│   ├── test_extractors.py                # Individual extractor tests
│   └── test_performance.py               # Performance benchmark tests
├── integration/
│   ├── test_end_to_end.py                # Full pipeline tests
│   ├── test_api_integration.py           # External API integration tests
│   └── test_cli.py                       # CLI interface tests
└── performance/
    ├── test_processing_speed.py          # Speed benchmarks
    ├── test_memory_usage.py              # Memory usage tests
    └── test_large_packages.py            # Large package handling
```

### Key Test Categories
```python
class TestLicenseDetection:
    """Test multi-layer license detection system"""
    
    def test_regex_detection_speed(self):
        """Regex detection should complete in < 10ms for typical license files"""
        with open('tests/fixtures/license_texts/mit_license.txt') as f:
            text = f.read()
        
        start_time = time.time()
        result = RegexLicenseDetector().detect_license(text)
        duration = time.time() - start_time
        
        assert duration < 0.01  # < 10ms
        assert result[0].spdx_id == 'MIT'
        assert result[0].confidence > 0.9
    
    def test_dice_sorensen_accuracy(self):
        """Dice-Sørensen should detect modified licenses accurately"""
        # Test with slightly modified MIT license
        with open('tests/fixtures/license_texts/modified_mit.txt') as f:
            modified_text = f.read()
        
        result = DiceSorensenLicenseDetector().detect_license(modified_text)
        
        assert result[0].spdx_id == 'MIT'
        assert result[0].confidence > 0.8
        assert result[0].method == 'dice_sorensen'
    
    def test_detection_method_ordering(self):
        """Test that detection methods are tried in correct order"""
        detector = LicenseDetectionEngine(LicenseConfig())
        
        # Mock each detector to track call order
        with patch.object(detector.regex_detector, 'detect_license') as mock_regex:
            with patch.object(detector.dice_detector, 'detect_license') as mock_dice:
                mock_regex.return_value = [LicenseMatch('MIT', 0.95, 'regex')]
                
                result = detector.detect_licenses("MIT License text")
                
                # Should call regex first
                mock_regex.assert_called_once()
                # Should not call dice due to high confidence
                mock_dice.assert_not_called()

class TestPackageExtraction:
    """Test native package extraction"""
    
    def test_wheel_extraction_speed(self):
        """Wheel extraction should be fast for small packages"""
        wheel_path = 'tests/fixtures/packages/python/simple_wheel.whl'
        
        start_time = time.time()
        result = NativePythonExtractor().extract_wheel(wheel_path)
        duration = time.time() - start_time
        
        assert duration < 0.5  # < 500ms
        assert result.name is not None
        assert result.version is not None
    
    def test_npm_package_extraction(self):
        """Test NPM package extraction without npm command"""
        npm_path = 'tests/fixtures/packages/javascript/simple_npm.tgz'
        
        result = NativeNpmExtractor().extract_npm_package(npm_path)
        
        assert result.name is not None
        assert result.version is not None
        assert result.package_type == 'npm'
    
    def test_jar_extraction(self):
        """Test JAR extraction with manifest parsing"""
        jar_path = 'tests/fixtures/packages/java/simple_jar.jar'
        
        result = NativeJavaExtractor().extract_jar(jar_path)
        
        assert result.name is not None
        # Should extract from MANIFEST.MF
        assert result.package_type == 'jar'

class TestPerformance:
    """Performance and memory usage tests"""
    
    @pytest.mark.performance
    def test_memory_usage_large_package(self):
        """Memory usage should stay reasonable for large packages"""
        large_package = 'tests/fixtures/packages/large_package.tar.gz'  # 100MB package
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        result = PackageProcessor().process(large_package)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Should not use more than 100MB additional memory
        assert memory_increase < 100 * 1024 * 1024
    
    @pytest.mark.performance 
    def test_processing_speed_targets(self):
        """Test processing speed targets for different package sizes"""
        test_cases = [
            ('tests/fixtures/packages/small_package.whl', 0.5),    # < 500ms
            ('tests/fixtures/packages/medium_package.tgz', 2.0),   # < 2s
            ('tests/fixtures/packages/large_package.tar.gz', 10.0) # < 10s
        ]
        
        for package_path, target_time in test_cases:
            start_time = time.time()
            result = PackageProcessor().process(package_path)
            duration = time.time() - start_time
            
            assert duration < target_time, f"Processing took {duration}s, target was {target_time}s"
            assert result.package_type != 'unknown'

class TestCLI:
    """CLI interface tests"""
    
    def test_basic_extraction_command(self):
        """Test basic upex command"""
        result = subprocess.run([
            'upex', 'tests/fixtures/packages/python/simple_wheel.whl'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert 'components' in output  # CycloneDX format
    
    def test_detect_only_mode(self):
        """Test --detect-only flag"""
        result = subprocess.run([
            'upex', '--detect-only', 'tests/fixtures/packages/javascript/simple_npm.tgz'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output['package_type'] == 'npm'
        assert output['confidence'] > 0.8
```

### Continuous Integration Test Matrix
```yaml
# .github/workflows/test.yml
test_matrix:
  python_version: [3.8, 3.9, 3.10, 3.11, 3.12]
  os: [ubuntu-latest, windows-latest, macos-latest]
  test_type: 
    - unit
    - integration  
    - performance
  package_ecosystem: [python, javascript, java, rust, generic]

performance_benchmarks:
  - name: "Small package processing"
    target: "< 500ms"
    packages: ["simple_wheel.whl", "simple_npm.tgz"]
  
  - name: "License detection speed"
    target: "< 100ms regex, < 500ms dice-sorensen"
    files: ["mit_license.txt", "apache_license.txt"]
  
  - name: "Memory usage"
    target: "< 100MB for packages under 100MB"
    packages: ["medium_package.tar.gz"]
```

### 5. Generic Archive Detection Edge Cases

#### Unknown Package Types
```python
class GenericArchiveHandler:
    """Handle archives that don't match known package signatures"""
    
    def analyze_unknown_archive(self, archive_path: str) -> DetectionResult:
        """Comprehensive analysis of unknown archive types"""
        
        # Extract sample files for analysis
        sample_files = self._extract_sample_files(archive_path, max_files=50)
        
        # Analyze file patterns
        patterns = self._analyze_file_patterns(sample_files)
        
        # Look for build system indicators
        build_systems = self._detect_build_systems(sample_files)
        
        # Analyze directory structure
        structure = self._analyze_directory_structure(sample_files)
        
        # Check for programming language indicators
        languages = self._detect_programming_languages(sample_files)
        
        # Generate confidence-scored hypothesis
        hypothesis = self._generate_package_hypothesis(
            patterns, build_systems, structure, languages
        )
        
        return DetectionResult(
            package_type=hypothesis.package_type or "generic",
            ecosystem=hypothesis.ecosystem or "unknown",
            confidence=hypothesis.confidence,
            detection_methods=["heuristic_analysis", "pattern_matching"],
            fallback_used=True,
            analysis_details=hypothesis.details
        )
    
    def _detect_build_systems(self, files: Dict[str, bytes]) -> List[BuildSystemHint]:
        """Detect build systems from file contents and names"""
        hints = []
        
        build_file_patterns = {
            'maven': ['pom.xml', 'maven.xml'],
            'gradle': ['build.gradle', 'build.gradle.kts', 'settings.gradle'],
            'npm': ['package.json', 'package-lock.json', 'yarn.lock'],
            'cargo': ['Cargo.toml', 'Cargo.lock'],
            'cmake': ['CMakeLists.txt', 'cmake'],
            'make': ['Makefile', 'makefile', 'GNUmakefile'],
            'python': ['setup.py', 'pyproject.toml', 'requirements.txt'],
            'composer': ['composer.json', 'composer.lock'],
            'go': ['go.mod', 'go.sum']
        }
        
        for build_system, patterns in build_file_patterns.items():
            for pattern in patterns:
                if any(pattern.lower() in filename.lower() for filename in files.keys()):
                    content_confidence = self._analyze_build_file_content(
                        files, pattern, build_system
                    )
                    hints.append(BuildSystemHint(
                        build_system=build_system,
                        confidence=content_confidence,
                        evidence_files=[pattern]
                    ))
        
        return sorted(hints, key=lambda x: x.confidence, reverse=True)

    def _detect_programming_languages(self, files: Dict[str, bytes]) -> List[LanguageHint]:
        """Detect programming languages from file extensions and content"""
        language_patterns = {
            'javascript': ['.js', '.mjs', '.jsx', '.ts', '.tsx'],
            'python': ['.py', '.pyw', '.pyc', '.pyo'],
            'java': ['.java', '.class', '.jar'],
            'rust': ['.rs'],
            'go': ['.go'],
            'php': ['.php', '.phtml'],
            'ruby': ['.rb', '.gem'],
            'csharp': ['.cs', '.dll', '.exe'],
            'cpp': ['.cpp', '.cxx', '.cc', '.c', '.h', '.hpp']
        }
        
        language_scores = {}
        
        for filename in files.keys():
            for language, extensions in language_patterns.items():
                if any(filename.lower().endswith(ext) for ext in extensions):
                    language_scores[language] = language_scores.get(language, 0) + 1
        
        # Convert to hints with confidence based on file count
        total_files = len(files)
        hints = []
        
        for language, count in language_scores.items():
            confidence = min(count / max(total_files * 0.1, 1), 1.0)
            hints.append(LanguageHint(
                language=language,
                confidence=confidence,
                file_count=count
            ))
        
        return sorted(hints, key=lambda x: x.confidence, reverse=True)
```

#### Corrupted or Malformed Packages
```python
class CorruptedPackageHandler:
    """Handle packages with corruption or malformed structure"""
    
    def analyze_corrupted_package(self, package_path: str) -> ProcessingResult:
        """Attempt to extract what information is available from corrupted packages"""
        
        errors = []
        warnings = []
        partial_metadata = PackageMetadata()
        
        try:
            # Attempt partial extraction
            extractable_files = self._attempt_partial_extraction(package_path)
            
            if extractable_files:
                # Try to parse whatever files we can extract
                for file_path, content in extractable_files.items():
                    try:
                        self._parse_individual_file(file_path, content, partial_metadata)
                    except Exception as e:
                        warnings.append(f"Failed to parse {file_path}: {str(e)}")
            
            # Generate PURL if we have minimum required info
            purl = None
            if partial_metadata.name and partial_metadata.version:
                purl = self._generate_purl_from_partial_metadata(partial_metadata)
            
            return ProcessingResult(
                package_type="unknown",
                ecosystem="unknown", 
                confidence=0.3,
                detection_methods=["partial_extraction"],
                metadata=partial_metadata,
                licenses=[],
                purl=purl,
                build_info=None,
                enriched_data=None,
                processing_time=0,
                template_used="generic",
                fallback_used=True,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            errors.append(f"Critical extraction failure: {str(e)}")
            return self._create_minimal_error_result(package_path, errors)
```

### 6. Local Package Manager Integration Details

#### Package Manager Verification System
```python
class PackageManagerVerifier:
    """Verify package detection using local package managers"""
    
    def verify_detection(self, package_path: str, 
                        detected_type: str) -> VerificationResult:
        """Verify detected package type using appropriate package manager"""
        
        manager = self._get_package_manager(detected_type)
        if not manager or not manager.is_available():
            return VerificationResult(verified=False, reason="manager_unavailable")
        
        try:
            # Use package manager to analyze the package
            pm_result = manager.analyze_package(package_path)
            
            if pm_result:
                # Compare with our detection
                consistency = self._check_consistency(detected_type, pm_result)
                
                return VerificationResult(
                    verified=True,
                    confidence=consistency.confidence,
                    package_manager_data=pm_result,
                    consistency_score=consistency.score,
                    discrepancies=consistency.discrepancies
                )
            else:
                return VerificationResult(verified=False, reason="analysis_failed")
                
        except subprocess.TimeoutExpired:
            return VerificationResult(verified=False, reason="timeout")
        except Exception as e:
            return VerificationResult(verified=False, reason=f"error: {str(e)}")

class EnhancedPipManager(PackageManager):
    """Enhanced pip manager with detailed package analysis"""
    
    def analyze_package(self, file_path: str) -> Optional[Dict]:
        """Comprehensive pip-based analysis"""
        
        # First try pip show if it's an installed package name
        if not os.path.exists(file_path):
            return self._analyze_by_name(file_path)
        
        # For wheel files, use wheel inspect
        if file_path.endswith('.whl'):
            return self._analyze_wheel_file(file_path)
        
        # For source distributions, try pip install --dry-run
        if file_path.endswith(('.tar.gz', '.zip')):
            return self._analyze_source_distribution(file_path)
        
        return None
    
    def _analyze_wheel_file(self, wheel_path: str) -> Optional[Dict]:
        """Analyze wheel file using wheel command"""
        try:
            # Use wheel unpack to examine contents
            with tempfile.TemporaryDirectory() as temp_dir:
                result = subprocess.run([
                    'wheel', 'unpack', wheel_path, '--dest', temp_dir
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    # Look for METADATA file
                    metadata_files = glob.glob(f"{temp_dir}/**/*METADATA", recursive=True)
                    if metadata_files:
                        return self._parse_wheel_metadata(metadata_files[0])
                        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Fallback to pip install --dry-run
        return self._analyze_with_pip_install(wheel_path)
    
    def _analyze_source_distribution(self, sdist_path: str) -> Optional[Dict]:
        """Analyze source distribution"""
        try:
            # Try pip install --dry-run --no-deps
            result = subprocess.run([
                'pip', 'install', '--dry-run', '--no-deps', '--quiet', sdist_path
            ], capture_output=True, text=True, timeout=45)
            
            if result.returncode == 0:
                # Parse the dry-run output
                return self._parse_pip_dry_run_output(result.stdout)
                
        except subprocess.TimeoutExpired:
            pass
        
        return None

class EnhancedNpmManager(PackageManager):
    """Enhanced npm manager with comprehensive analysis"""
    
    def analyze_package(self, file_path: str) -> Optional[Dict]:
        """Comprehensive npm-based analysis"""
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract package to temporary directory
                if file_path.endswith('.tgz'):
                    self._extract_tgz(file_path, temp_dir)
                else:
                    # Try to handle it as a directory or other format
                    shutil.copytree(file_path, os.path.join(temp_dir, 'package'))
                
                # Run npm commands in the extracted directory
                package_dir = os.path.join(temp_dir, 'package')
                
                # Get basic package info
                package_json_path = os.path.join(package_dir, 'package.json')
                if os.path.exists(package_json_path):
                    with open(package_json_path) as f:
                        package_data = json.load(f)
                
                # Run npm list to get dependency tree
                npm_list_result = subprocess.run([
                    'npm', 'list', '--json', '--depth=1'
                ], cwd=package_dir, capture_output=True, text=True, timeout=30)
                
                dependency_data = {}
                if npm_list_result.returncode == 0:
                    dependency_data = json.loads(npm_list_result.stdout)
                
                # Combine package.json and npm list data
                return {
                    'package_json': package_data,
                    'dependencies': dependency_data,
                    'npm_version': self._get_npm_version(),
                    'verification_method': 'npm_analysis'
                }
                
        except Exception as e:
            logger.warning(f"NPM analysis failed: {e}")
            return None
```

### 7. Template Extensibility Features

#### Custom Template Creation
```python
class TemplateGenerator:
    """Generate new templates from detected packages"""
    
    def generate_template_from_package(self, package_path: str, 
                                     output_path: str) -> bool:
        """Analyze a package and generate a reusable template"""
        
        # Perform deep analysis of the package
        analysis = self._deep_analyze_package(package_path)
        
        # Extract patterns and create template
        template = PackageTypeTemplate(
            name=analysis.inferred_type,
            ecosystem=analysis.inferred_ecosystem,
            provider=analysis.inferred_provider,
            description=f"Auto-generated template for {analysis.inferred_type}",
            detection=self._create_detection_config(analysis),
            metadata_extraction=self._create_metadata_config(analysis),
            build_analysis=self._create_build_config(analysis),
            license_detection=self._create_license_config(analysis),
            local_package_manager=self._create_pm_config(analysis),
            purl_template=self._create_purl_template(analysis)
        )
        
        # Save template to YAML file
        return self._save_template(template, output_path)
    
    def _deep_analyze_package(self, package_path: str) -> DeepAnalysis:
        """Perform comprehensive analysis to understand package structure"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract package
            extracted_path = self._extract_package(package_path, temp_dir)
            
            # Analyze file structure
            file_structure = self._analyze_file_structure(extracted_path)
            
            # Find metadata files
            metadata_files = self._find_metadata_files(extracted_path)
            
            # Analyze content patterns
            content_patterns = self._analyze_content_patterns(extracted_path)
            
            # Infer package type and ecosystem
            inference = self._infer_package_characteristics(
                file_structure, metadata_files, content_patterns
            )
            
            return DeepAnalysis(
                file_structure=file_structure,
                metadata_files=metadata_files,
                content_patterns=content_patterns,
                inferred_type=inference.package_type,
                inferred_ecosystem=inference.ecosystem,
                inferred_provider=inference.provider,
                confidence=inference.confidence
            )
```

### 8. Advanced Detection Scenarios

#### Multi-Language Projects
```python
class MultiLanguageDetector:
    """Handle projects with multiple programming languages/ecosystems"""
    
    def detect_multi_language_project(self, extracted_path: str) -> List[DetectionResult]:
        """Detect multiple package types within a single archive"""
        
        results = []
        
        # Analyze each subdirectory independently
        for root, dirs, files in os.walk(extracted_path):
            if self._is_potential_package_root(root, dirs, files):
                subpackage_result = self._analyze_subpackage(root)
                if subpackage_result.confidence > 0.6:
                    results.append(subpackage_result)
        
        # Also check for monorepo patterns
        monorepo_result = self._detect_monorepo_structure(extracted_path)
        if monorepo_result:
            results.extend(monorepo_result)
        
        return self._rank_and_filter_results(results)
    
    def _detect_monorepo_structure(self, root_path: str) -> List[DetectionResult]:
        """Detect monorepo structures like Lerna, Nx, etc."""
        
        monorepo_indicators = {
            'lerna': ['lerna.json', 'packages/'],
            'nx': ['nx.json', 'workspace.json', 'apps/', 'libs/'],
            'yarn_workspaces': ['package.json'],  # with workspaces field
            'rush': ['rush.json', 'common/']
        }
        
        detected_structures = []
        
        for structure_type, indicators in monorepo_indicators.items():
            if self._check_monorepo_indicators(root_path, indicators, structure_type):
                # Analyze individual packages within the monorepo
                packages = self._find_monorepo_packages(root_path, structure_type)
                
                for package_path in packages:
                    result = self._analyze_subpackage(package_path)
                    result.monorepo_type = structure_type
                    detected_structures.append(result)
        
        return detected_structures
```

This completes the enhanced specification with comprehensive package type detection, extensible template system, local package manager fallbacks, and advanced edge case handling. The specification now provides:

1. **Intelligent Package Detection**: Multi-layer detection with file extension analysis, content inspection, and package manager verification
2. **Extensible Template System**: YAML-based configuration templates for easy addition of new package types and ecosystems
3. **Local Package Manager Integration**: Fallback verification using pip, npm, maven, cargo, and other local tools
4. **Enhanced API Integration**: Proper integration with ClearlyDefined and Ecosyste.ms APIs with rate limiting and caching
5. **Advanced Edge Case Handling**: Support for corrupted packages, multi-language projects, monorepos, and unknown archive types
6. **Comprehensive Output Format**: Enhanced JSON schema with detection details, confidence scores, and metadata enrichment
7. **Robust CLI Interface**: Extended command-line options for all new features
8. **Flexible Configuration**: Detailed YAML configuration covering all aspects of the system

The specification is now production-ready and provides a solid foundation for building a comprehensive universal package metadata extraction tool that can handle the complexities of modern software ecosystems.# Universal Package Metadata Extractor - Technical Specifications

## Project Overview

**Package Name**: `semantic-copycat-upex` (PyPI)
**CLI Command**: `upex`
**Version**: 1.0.0
**License**: Apache-2.0 OR MIT
**Python Version**: 3.8+

A native Python library and CLI tool for extracting, parsing, and normalizing metadata from packages across multiple ecosystems. Uses pure Python implementations for package parsing, multi-layered license detection (regex → Dice-Sørensen → fuzzy hashing → ML), and falls back to package managers only as a last resort. Optimized for single-package processing with fast extraction and SPDX compliance.

## Core Features

### 1. Multi-Ecosystem Package Support

#### Supported Package Types
- **Python**: wheel (.whl), source distributions (.tar.gz), eggs
- **JavaScript/Node.js**: npm packages (.tgz), yarn packages
- **Java**: JAR files (.jar), WAR files (.war), Maven artifacts
- **C/C++**: Conan packages, vcpkg packages
- **Rust**: Cargo packages (.crate)
- **Go**: Go modules
- **C#/.NET**: NuGet packages (.nupkg)
- **Ruby**: Gems (.gem)
- **PHP**: Composer packages
- **Docker**: Container images (via manifest analysis)
- **Generic**: Archive formats (zip, tar, tar.gz, tar.bz2, tar.xz)

### 1. Native Package Extraction (No External Dependencies)

The tool implements native Python extractors for each package format, avoiding dependencies on external package managers:

#### Python Package Extractor (Native Implementation)
```python
class NativePythonExtractor:
    """Native Python package extraction without pip dependency"""
    
    def extract_wheel(self, wheel_path: str) -> PackageInfo:
        """Extract .whl files using native zipfile"""
        with zipfile.ZipFile(wheel_path, 'r') as zf:
            # Find METADATA or PKG-INFO file
            metadata_file = self._find_metadata_file(zf.namelist())
            
            if metadata_file:
                metadata_content = zf.read(metadata_file).decode('utf-8')
                metadata = self._parse_wheel_metadata(metadata_content)
            else:
                metadata = PackageInfo()
            
            # Extract license files
            license_files = self._extract_license_files(zf)
            
            # Scan source files for license information if metadata incomplete
            if not metadata.license:
                source_files = self._extract_source_files(zf)
                license_info = self._scan_files_for_licenses(source_files)
                metadata.license_from_source = license_info
            
            return self._build_package_info(metadata, license_files)
    
    def extract_source_dist(self, sdist_path: str) -> PackageInfo:
        """Extract source distributions (.tar.gz)"""
        with tarfile.open(sdist_path, 'r:gz') as tf:
            # Look for setup.py, pyproject.toml, setup.cfg
            setup_files = self._find_setup_files(tf.getnames())
            
            metadata = PackageInfo()
            for setup_file in setup_files:
                setup_content = tf.extractfile(setup_file).read().decode('utf-8')
                partial_metadata = self._parse_setup_file(setup_file, setup_content)
                metadata = self._merge_metadata(metadata, partial_metadata)
            
            # Extract and analyze license files
            license_files = self._extract_license_files_tar(tf)
            
            return self._build_package_info(metadata, license_files)
    
    def _parse_wheel_metadata(self, content: str) -> PackageInfo:
        """Parse METADATA file from wheel"""
        metadata = PackageInfo()
        
        for line in content.split('\n'):
            if line.startswith('Name: '):
                metadata.name = line[6:].strip()
            elif line.startswith('Version: '):
                metadata.version = line[9:].strip()
            elif line.startswith('License: '):
                metadata.license = line[9:].strip()
            elif line.startswith('Author: '):
                metadata.author = line[8:].strip()
            elif line.startswith('Home-page: '):
                metadata.homepage = line[11:].strip()
            elif line.startswith('Classifier: License'):
                # Extract license from classifier
                license_classifier = line.split(' :: ')[-1]
                if not metadata.license:
                    metadata.license = license_classifier
        
        return metadata
    
    def _parse_setup_file(self, filename: str, content: str) -> PackageInfo:
        """Parse setup.py, pyproject.toml, or setup.cfg"""
        metadata = PackageInfo()
        
        if filename.endswith('setup.py'):
            metadata = self._parse_setup_py(content)
        elif filename.endswith('pyproject.toml'):
            metadata = self._parse_pyproject_toml(content)
        elif filename.endswith('setup.cfg'):
            metadata = self._parse_setup_cfg(content)
        
        return metadata
    
    def _parse_setup_py(self, content: str) -> PackageInfo:
        """Extract metadata from setup.py using AST parsing"""
        try:
            tree = ast.parse(content)
            setup_call = self._find_setup_call(tree)
            
            if setup_call:
                return self._extract_setup_kwargs(setup_call)
        except SyntaxError:
            # Fallback to regex for malformed Python
            return self._parse_setup_py_regex(content)
        
        return PackageInfo()
```

#### NPM Package Extractor (Native Implementation)
```python
class NativeNpmExtractor:
    """Native NPM package extraction without npm dependency"""
    
    def extract_npm_package(self, package_path: str) -> PackageInfo:
        """Extract .tgz NPM packages using native tarfile"""
        with tarfile.open(package_path, 'r:gz') as tf:
            # Find package.json
            package_json_path = self._find_package_json(tf.getnames())
            
            if package_json_path:
                package_json_content = tf.extractfile(package_json_path).read().decode('utf-8')
                metadata = self._parse_package_json(package_json_content)
            else:
                metadata = PackageInfo()
            
            # Extract license files
            license_files = self._extract_license_files_tar(tf)
            
            # Scan JavaScript files for license headers if needed
            if not metadata.license:
                js_files = self._extract_js_files(tf)
                license_info = self._scan_js_files_for_licenses(js_files)
                metadata.license_from_source = license_info
            
            return self._build_package_info(metadata, license_files)
    
    def _parse_package_json(self, content: str) -> PackageInfo:
        """Parse package.json file"""
        try:
            data = json.loads(content)
            metadata = PackageInfo()
            
            metadata.name = data.get('name')
            metadata.version = data.get('version')
            metadata.license = data.get('license')
            metadata.description = data.get('description')
            metadata.homepage = data.get('homepage')
            metadata.repository = data.get('repository', {}).get('url')
            
            # Handle author (can be string or object)
            author = data.get('author')
            if isinstance(author, dict):
                metadata.author = author.get('name')
                metadata.author_email = author.get('email')
            elif isinstance(author, str):
                metadata.author = author
            
            # Extract dependencies
            metadata.dependencies = list(data.get('dependencies', {}).keys())
            metadata.dev_dependencies = list(data.get('devDependencies', {}).keys())
            
            return metadata
        except json.JSONDecodeError:
            return PackageInfo()
```

#### Java Package Extractor (Native Implementation)
```python
class NativeJavaExtractor:
    """Native Java package extraction without Maven/Gradle dependency"""
    
    def extract_jar(self, jar_path: str) -> PackageInfo:
        """Extract JAR files using native zipfile"""
        with zipfile.ZipFile(jar_path, 'r') as zf:
            # Look for META-INF/MANIFEST.MF
            manifest_content = self._read_manifest(zf)
            metadata = self._parse_manifest(manifest_content)
            
            # Look for Maven pom.properties and pom.xml
            pom_info = self._extract_pom_info(zf)
            metadata = self._merge_metadata(metadata, pom_info)
            
            # Extract license files
            license_files = self._extract_license_files_zip(zf)
            
            # Scan Java files for license headers if needed
            if not metadata.license:
                java_files = self._extract_java_files(zf)
                license_info = self._scan_java_files_for_licenses(java_files)
                metadata.license_from_source = license_info
            
            return self._build_package_info(metadata, license_files)
    
    def _parse_manifest(self, content: str) -> PackageInfo:
        """Parse JAR MANIFEST.MF file"""
        metadata = PackageInfo()
        
        for line in content.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if key == 'Implementation-Title':
                    metadata.name = value
                elif key == 'Implementation-Version':
                    metadata.version = value
                elif key == 'Implementation-Vendor':
                    metadata.author = value
        
        return metadata
    
    def _extract_pom_info(self, zipfile_obj) -> PackageInfo:
        """Extract Maven POM information from JAR"""
        metadata = PackageInfo()
        
        # Look for META-INF/maven/*/*/pom.xml
        for filename in zipfile_obj.namelist():
            if filename.endswith('/pom.xml') and 'META-INF/maven' in filename:
                pom_content = zipfile_obj.read(filename).decode('utf-8')
                pom_metadata = self._parse_pom_xml(pom_content)
                metadata = self._merge_metadata(metadata, pom_metadata)
                break
        
        return metadata
```

#### Package Manager Fallback (Last Resort Only)
```python
class PackageManagerFallback:
    """Use package managers only as absolute last resort"""
    
    def __init__(self):
        self.available_managers = self._detect_available_managers()
    
    def fallback_extract(self, package_path: str, detected_type: str) -> Optional[PackageInfo]:
        """Use package manager only if native extraction completely fails"""
        
        if detected_type not in self.available_managers:
            return None
        
        try:
            manager = self.available_managers[detected_type]
            return manager.extract_metadata(package_path)
        except Exception as e:
            logger.warning(f"Package manager fallback failed: {e}")
            return None
    
    def _detect_available_managers(self) -> Dict[str, PackageManager]:
        """Detect which package managers are available on system"""
        managers = {}
        
        # Only add if actually available and working
        if self._is_command_available('pip'):
            managers['python'] = PipFallbackManager()
        
        if self._is_command_available('npm'):
            managers['npm'] = NpmFallbackManager()
        
        return managers
    
    def _is_command_available(self, command: str) -> bool:
        """Check if command is available in PATH"""
        try:
            subprocess.run([command, '--version'], 
                         capture_output=True, timeout=5)
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
```

##### Package Signature System
```python
@dataclass
class PackageSignature:
    name: str
    package_type: str
    ecosystem: str
    required_files: List[str]
    optional_files: List[str] 
    file_patterns: List[Pattern]
    content_patterns: Dict[str, List[str]]  # filename -> content patterns
    exclusion_patterns: List[str]
    confidence: float
    priority: int

# Example signatures for generic archive detection
PACKAGE_SIGNATURES = [
    PackageSignature(
        name="npm_package",
        package_type="npm",
        ecosystem="javascript",
        required_files=["package.json"],
        optional_files=["package-lock.json", "yarn.lock", "node_modules/"],
        file_patterns=[re.compile(r".*\.js$"), re.compile(r".*\.ts$")],
        content_patterns={
            "package.json": ['"name":', '"version":', '"dependencies":']
        },
        exclusion_patterns=["requirements.txt", "pom.xml"],
        confidence=0.95,
        priority=1
    ),
    PackageSignature(
        name="python_source",
        package_type="python",
        ecosystem="python",
        required_files=["setup.py", "pyproject.toml", "requirements.txt"],
        optional_files=["MANIFEST.in", "tox.ini", "setup.cfg"],
        file_patterns=[re.compile(r".*\.py$")],
        content_patterns={
            "setup.py": ["from setuptools import", "setup("],
            "pyproject.toml": ["[build-system]", "[tool.setuptools]"]
        },
        confidence=0.90,
        priority=2
    ),
    PackageSignature(
        name="maven_project", 
        package_type="maven",
        ecosystem="java",
        required_files=["pom.xml"],
        optional_files=["src/", "target/", "build.gradle"],
        file_patterns=[re.compile(r".*\.java$"), re.compile(r".*\.class$")],
        content_patterns={
            "pom.xml": ["<modelVersion>", "<groupId>", "<artifactId>"]
        },
        confidence=0.92,
        priority=1
    ),
    PackageSignature(
        name="cargo_project",
        package_type="cargo", 
        ecosystem="rust",
        required_files=["Cargo.toml"],
        optional_files=["Cargo.lock", "src/", "target/"],
        file_patterns=[re.compile(r".*\.rs$")],
        content_patterns={
            "Cargo.toml": ["[package]", "name =", "version ="]
        },
        confidence=0.93,
        priority=1
    )
]
```

##### Local Package Manager Fallback System
```python
class LocalPackageManagerClient:
    """Interface with local package managers for verification and enrichment"""
    
    def query_package_managers(self, file_path: str) -> Dict[str, Any]:
        """Query multiple local package managers for package information"""
        results = {}
        
        # Try different package managers based on file type
        managers = self._get_applicable_managers(file_path)
        
        for manager in managers:
            try:
                result = manager.analyze_package(file_path)
                if result:
                    results[manager.name] = result
            except Exception as e:
                self.logger.warning(f"Package manager {manager.name} failed: {e}")
        
        return results
    
    def _get_applicable_managers(self, file_path: str) -> List[PackageManager]:
        """Get list of package managers that might handle this file type"""
        managers = []
        
        if file_path.endswith(('.whl', '.tar.gz')):
            managers.extend([PipManager(), CondaManager()])
        elif file_path.endswith('.jar'):
            managers.extend([MavenManager(), GradleManager()])
        elif file_path.endswith('.tgz'):
            managers.extend([NpmManager(), YarnManager()])
        elif file_path.endswith('.gem'):
            managers.append(GemManager())
        elif file_path.endswith('.nupkg'):
            managers.append(NuGetManager())
        
        return managers

class PipManager(PackageManager):
    def analyze_package(self, file_path: str) -> Optional[Dict]:
        """Use pip to analyze Python packages"""
        try:
            result = subprocess.run([
                'pip', 'show', '--verbose', file_path
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return self._parse_pip_output(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

class NpmManager(PackageManager): 
    def analyze_package(self, file_path: str) -> Optional[Dict]:
        """Use npm to analyze JavaScript packages"""
        try:
            # Extract to temp directory first
            with tempfile.TemporaryDirectory() as temp_dir:
                self._extract_package(file_path, temp_dir)
                
                result = subprocess.run([
                    'npm', 'list', '--json', '--depth=0'
                ], cwd=temp_dir, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    return json.loads(result.stdout)
        except Exception:
            pass
        return None
```

### 2. Native License Detection Engine (Multi-Layer Approach)

The license detection system uses a hierarchical approach with increasing computational cost:

#### Layer 1: Regex Pattern Matching (Fastest)
```python
class RegexLicenseDetector:
    """Fast regex-based license detection for common patterns"""
    
    LICENSE_PATTERNS = {
        'MIT': [
            r'MIT\s+License',
            r'Permission\s+is\s+hereby\s+granted.*free\s+of\s+charge',
            r'THE\s+SOFTWARE\s+IS\s+PROVIDED\s+"AS\s+IS"'
        ],
        'Apache-2.0': [
            r'Apache\s+License.*Version\s+2\.0',
            r'Licensed\s+under\s+the\s+Apache\s+License',
            r'www\.apache\.org/licenses/LICENSE-2\.0'
        ],
        'GPL-3.0': [
            r'GNU\s+GENERAL\s+PUBLIC\s+LICENSE.*Version\s+3',
            r'This\s+program\s+is\s+free\s+software.*GNU\s+General\s+Public\s+License',
            r'www\.gnu\.org/licenses/gpl-3\.0'
        ],
        'BSD-3-Clause': [
            r'BSD\s+3-Clause\s+License',
            r'Redistribution\s+and\s+use\s+in\s+source\s+and\s+binary\s+forms',
            r'Neither\s+the\s+name\s+of.*nor\s+the\s+names\s+of\s+its\s+contributors'
        ]
    }
    
    def detect_license(self, text: str) -> List[LicenseMatch]:
        """Fast regex-based detection"""
        normalized_text = self._normalize_text(text)
        matches = []
        
        for license_id, patterns in self.LICENSE_PATTERNS.items():
            confidence = self._calculate_pattern_confidence(normalized_text, patterns)
            if confidence > 0.7:
                matches.append(LicenseMatch(
                    spdx_id=license_id,
                    confidence=confidence,
                    method="regex_pattern",
                    matched_patterns=self._get_matched_patterns(normalized_text, patterns)
                ))
        
        return sorted(matches, key=lambda x: x.confidence, reverse=True)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent pattern matching"""
        # Remove extra whitespace, normalize case
        normalized = re.sub(r'\s+', ' ', text.strip())
        # Remove common formatting
        normalized = re.sub(r'[^\w\s\.\-]', ' ', normalized)
        return normalized.lower()
```

#### Layer 2: Dice-Sørensen Coefficient (Medium Speed)
```python
class DiceSorensenLicenseDetector:
    """Dice-Sørensen coefficient for text similarity matching"""
    
    def __init__(self):
        self.reference_texts = self._load_reference_license_texts()
        self.bigram_cache = {}
    
    def detect_license(self, text: str) -> List[LicenseMatch]:
        """Detect license using Dice-Sørensen similarity"""
        normalized_text = self._normalize_text_advanced(text)
        text_bigrams = self._get_bigrams(normalized_text)
        
        matches = []
        for license_id, reference_text in self.reference_texts.items():
            similarity = self._calculate_dice_sorensen(text_bigrams, reference_text)
            if similarity > 0.8:  # High threshold for Dice-Sørensen
                matches.append(LicenseMatch(
                    spdx_id=license_id,
                    confidence=similarity,
                    method="dice_sorensen",
                    similarity_score=similarity
                ))
        
        return sorted(matches, key=lambda x: x.confidence, reverse=True)
    
    def _calculate_dice_sorensen(self, text_bigrams: Set[str], 
                               reference_text: str) -> float:
        """Calculate Dice-Sørensen coefficient"""
        ref_bigrams = self._get_cached_bigrams(reference_text)
        
        intersection = len(text_bigrams & ref_bigrams)
        union_size = len(text_bigrams) + len(ref_bigrams)
        
        if union_size == 0:
            return 0.0
        
        return 2.0 * intersection / union_size
    
    def _get_bigrams(self, text: str) -> Set[str]:
        """Generate character bigrams from text"""
        text = text.replace(' ', '_')  # Preserve word boundaries
        return {text[i:i+2] for i in range(len(text) - 1)}
    
    def _normalize_text_advanced(self, text: str) -> str:
        """Advanced normalization for Dice-Sørensen comparison"""
        # Remove copyright years, names, URLs
        text = re.sub(r'\d{4}(?:-\d{4})?', 'YEAR', text)
        text = re.sub(r'https?://[^\s]+', 'URL', text)
        text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
        text = re.sub(r'\s+', ' ', text.strip().lower())
        return text
```

#### Layer 3: Fuzzy Hashing with LSH (Medium-High Cost)
```python
class FuzzyHashLicenseDetector:
    """Locality-Sensitive Hashing for fuzzy license matching"""
    
    def __init__(self):
        self.lsh_index = self._build_lsh_index()
        self.reference_hashes = self._load_reference_hashes()
    
    def detect_license(self, text: str) -> List[LicenseMatch]:
        """Detect license using fuzzy hashing with LSH"""
        normalized_text = self._normalize_text_for_hashing(text)
        text_hash = self._generate_fuzzy_hash(normalized_text)
        
        # Find similar hashes using LSH
        candidates = self.lsh_index.query(text_hash, num_results=10)
        
        matches = []
        for candidate_id, similarity in candidates:
            if similarity > 0.85:  # High threshold for fuzzy matching
                license_id = self._get_license_id_from_hash(candidate_id)
                matches.append(LicenseMatch(
                    spdx_id=license_id,
                    confidence=similarity,
                    method="fuzzy_hash_lsh",
                    hash_similarity=similarity,
                    hash_type="minhash"
                ))
        
        return sorted(matches, key=lambda x: x.confidence, reverse=True)
    
    def _generate_fuzzy_hash(self, text: str) -> MinHash:
        """Generate MinHash for fuzzy comparison"""
        minhash = MinHash(num_perm=128)
        
        # Use overlapping shingles for better fuzzy matching
        shingles = self._generate_shingles(text, k=3)
        for shingle in shingles:
            minhash.update(shingle.encode('utf-8'))
        
        return minhash
    
    def _generate_shingles(self, text: str, k: int = 3) -> Set[str]:
        """Generate k-shingles from text"""
        words = text.split()
        shingles = set()
        
        for i in range(len(words) - k + 1):
            shingle = ' '.join(words[i:i+k])
            shingles.add(shingle)
        
        return shingles
```

#### Layer 4: ML Classification (Highest Cost, Best Accuracy)
```python
class MLLicenseDetector:
    """Machine Learning-based license classification"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=10000,
            ngram_range=(1, 3),
            stop_words='english'
        )
        self.classifier = None
        self.model_loaded = False
    
    def detect_license(self, text: str) -> List[LicenseMatch]:
        """ML-based license detection using scikit-learn"""
        if not self._ensure_model_loaded():
            return []  # Fallback gracefully if model unavailable
        
        normalized_text = self._normalize_text_for_ml(text)
        features = self.vectorizer.transform([normalized_text])
        
        # Get probabilities for all classes
        probabilities = self.classifier.predict_proba(features)[0]
        classes = self.classifier.classes_
        
        matches = []
        for prob, license_id in zip(probabilities, classes):
            if prob > 0.6:  # Confidence threshold for ML
                matches.append(LicenseMatch(
                    spdx_id=license_id,
                    confidence=prob,
                    method="ml_classification",
                    model_type="tfidf_svm",
                    probability=prob
                ))
        
        return sorted(matches, key=lambda x: x.confidence, reverse=True)
    
    def _ensure_model_loaded(self) -> bool:
        """Lazy load ML model"""
        if self.model_loaded:
            return True
        
        try:
            # Try to load pre-trained model or train simple one
            model_path = self._get_model_path()
            if os.path.exists(model_path):
                self.classifier = joblib.load(model_path)
            else:
                self.classifier = self._train_simple_model()
            
            self.model_loaded = True
            return True
        except Exception as e:
            logger.warning(f"Failed to load ML model: {e}")
            return False
    
    def _train_simple_model(self):
        """Train a simple model with basic license texts"""
        from sklearn.svm import SVC
        
        # Use reference license texts as training data
        training_texts, training_labels = self._get_training_data()
        
        if len(training_texts) < 10:  # Not enough data
            return None
        
        X = self.vectorizer.fit_transform(training_texts)
        classifier = SVC(probability=True, kernel='linear')
        classifier.fit(X, training_labels)
        
        return classifier
```

#### Unified License Detection Controller
```python
class LicenseDetectionEngine:
    """Orchestrates multi-layer license detection"""
    
    def __init__(self, config: LicenseConfig):
        self.config = config
        self.regex_detector = RegexLicenseDetector()
        self.dice_detector = DiceSorensenLicenseDetector()
        self.fuzzy_detector = FuzzyHashLicenseDetector()
        self.ml_detector = MLLicenseDetector()
    
    def detect_licenses(self, text: str, max_methods: int = 4) -> List[LicenseMatch]:
        """Run detection methods in order of speed until confident match found"""
        
        all_matches = []
        
        # Layer 1: Regex (fastest)
        regex_matches = self.regex_detector.detect_license(text)
        all_matches.extend(regex_matches)
        
        # Return early if high-confidence regex match
        if regex_matches and regex_matches[0].confidence > 0.9:
            return self._deduplicate_matches(all_matches)
        
        # Layer 2: Dice-Sørensen
        if max_methods >= 2:
            dice_matches = self.dice_detector.detect_license(text)
            all_matches.extend(dice_matches)
            
            # Return early if high-confidence similarity match
            if dice_matches and dice_matches[0].confidence > 0.95:
                return self._deduplicate_matches(all_matches)
        
        # Layer 3: Fuzzy Hashing
        if max_methods >= 3:
            fuzzy_matches = self.fuzzy_detector.detect_license(text)
            all_matches.extend(fuzzy_matches)
        
        # Layer 4: ML (most expensive)
        if max_methods >= 4 and self.config.enable_ml:
            ml_matches = self.ml_detector.detect_license(text)
            all_matches.extend(ml_matches)
        
        return self._deduplicate_matches(all_matches)
    
    def _deduplicate_matches(self, matches: List[LicenseMatch]) -> List[LicenseMatch]:
        """Combine matches for same license, keeping highest confidence"""
        license_map = {}
        
        for match in matches:
            if match.spdx_id not in license_map:
                license_map[match.spdx_id] = match
            else:
                # Keep match with higher confidence
                if match.confidence > license_map[match.spdx_id].confidence:
                    # Combine detection methods
                    combined_methods = license_map[match.spdx_id].methods + [match.method]
                    match.methods = combined_methods
                    license_map[match.spdx_id] = match
        
        return sorted(license_map.values(), key=lambda x: x.confidence, reverse=True)
```

@dataclass
class LicenseMatch:
    spdx_id: str
    confidence: float
    method: str
    methods: List[str] = field(default_factory=list)
    matched_patterns: List[str] = field(default_factory=list)
    similarity_score: Optional[float] = None
    hash_similarity: Optional[float] = None
    probability: Optional[float] = None
    hash_type: Optional[str] = None
    model_type: Optional[str] = None

### 3. Package Metadata Extraction

#### Core Metadata Fields
```python
@dataclass
class PackageMetadata:
    name: str
    version: str
    purl: str  # Package URL
    ecosystem: str
    namespace: Optional[str]
    description: Optional[str]
    homepage: Optional[str]
    download_url: Optional[str]
    authors: List[Author]
    maintainers: List[Maintainer]
    dependencies: List[Dependency]
    dev_dependencies: List[Dependency]
    build_dependencies: List[Dependency]
    creation_date: Optional[datetime]
    modification_date: Optional[datetime]
    file_hashes: Dict[str, str]  # sha1, md5, sha256
    size: int
    build_config: Optional[BuildConfiguration]
```

#### Build Configuration Analysis
```python
@dataclass
class BuildConfiguration:
    build_system: str  # maven, gradle, npm, cargo, etc.
    build_files: List[str]  # pom.xml, package.json, Cargo.toml
    compilation_targets: List[str]
    build_flags: List[str]
    project_structure: ProjectStructure
    dependency_graph: DependencyGraph
```

### 4. External API Integration

#### Supported APIs
- **ClearlyDefined**: License and copyright information via REST API with coordinate-based lookup
- **Ecosyste.ms**: Package ecosystem data with comprehensive metadata and dependency information
- **OSV.dev**: Vulnerability information
- **Libraries.io**: Package metadata and statistics
- **SPDX License List API**: License validation

#### ClearlyDefined API Integration
```python
class ClearlyDefinedClient:
    """Client for ClearlyDefined API with proper coordinate handling"""
    
    BASE_URL = "https://api.clearlydefined.io"
    RATE_LIMIT = 2000  # requests per minute for general endpoints
    
    def __init__(self, api_key: Optional[str] = None):
        self.session = requests.Session()
        self.rate_limiter = RateLimiter(self.RATE_LIMIT, 60)
        
    def get_definition(self, purl: str) -> Optional[ClearlyDefinedData]:
        """Get component definition using ClearlyDefined coordinates"""
        coordinates = self._convert_purl_to_coordinates(purl)
        
        url = f"{self.BASE_URL}/definitions/{coordinates}"
        
        with self.rate_limiter:
            response = self.session.get(url, headers={"accept": "*/*"})
            
            if response.status_code == 200:
                return ClearlyDefinedData.from_dict(response.json())
            elif response.status_code == 429:
                # Handle rate limiting
                retry_after = int(response.headers.get('Retry-After', 60))
                time.sleep(retry_after)
                return self.get_definition(purl)
        
        return None
    
    def _convert_purl_to_coordinates(self, purl: str) -> str:
        """Convert Package URL to ClearlyDefined coordinates"""
        # Parse PURL: pkg:npm/namespace/name@version
        parsed = PackageURL.from_string(purl)
        
        # Map to ClearlyDefined format: type/provider/namespace/name/revision
        type_mapping = {
            'npm': 'npm/npmjs',
            'pypi': 'pypi/pypi', 
            'maven': 'maven/mavencentral',
            'cargo': 'crate/cratesio',
            'nuget': 'nuget/nuget',
            'gem': 'gem/rubygems'
        }
        
        provider = type_mapping.get(parsed.type, f"{parsed.type}/{parsed.type}")
        namespace = parsed.namespace or '-'
        
        # Handle special encoding for namespaces with slashes (Go packages)
        if '/' in namespace and parsed.type == 'golang':
            namespace = namespace.replace('/', '%2F')
        
        coordinates = f"{provider}/{namespace}/{parsed.name}/{parsed.version}"
        return coordinates
    
    def harvest_component(self, purl: str) -> bool:
        """Queue component for harvest if not already processed"""
        coordinates = self._convert_purl_to_coordinates(purl)
        
        payload = [{
            "tool": "package",
            "coordinates": coordinates
        }]
        
        url = f"{self.BASE_URL}/harvest"
        response = self.session.post(
            url, 
            json=payload,
            headers={"Content-Type": "application/json", "accept": "*/*"}
        )
        
        return response.status_code == 200

@dataclass
class ClearlyDefinedData:
    coordinates: str
    described: Optional[Dict]
    licensed: Optional[Dict]
    files: Optional[List[Dict]]
    score: Optional[Dict]
    
    def get_license_expression(self) -> Optional[str]:
        """Extract SPDX license expression from definition"""
        if self.licensed and 'declared' in self.licensed:
            return self.licensed['declared']
        return None
    
    def get_source_location(self) -> Optional[Dict]:
        """Get source repository information"""
        if self.described and 'sourceLocation' in self.described:
            return self.described['sourceLocation']
        return None
```

#### Ecosyste.ms API Integration
```python
class EcosystemsClient:
    """Client for Ecosyste.ms Package API"""
    
    BASE_URL = "https://packages.ecosyste.ms/api/v1"
    
    def lookup_package(self, purl: str = None, name: str = None, 
                      ecosystem: str = None) -> List[EcosystemsPackage]:
        """Lookup package using various identifiers"""
        params = {}
        
        if purl:
            params['purl'] = purl
        elif name and ecosystem:
            params['name'] = name
            params['ecosystem'] = ecosystem
        else:
            raise ValueError("Must provide either PURL or name+ecosystem")
        
        url = f"{self.BASE_URL}/packages/lookup"
        response = self.session.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return [EcosystemsPackage.from_dict(pkg) for pkg in data]
        
        return []
    
    def get_package_versions(self, registry: str, name: str) -> List[EcosystemsVersion]:
        """Get all versions for a specific package"""
        url = f"{self.BASE_URL}/registries/{registry}/packages/{name}/versions"
        response = self.session.get(url)
        
        if response.status_code == 200:
            data = response.json()
            return [EcosystemsVersion.from_dict(ver) for ver in data]
        
        return []
    
    def get_package_dependencies(self, registry: str, name: str, 
                               version: str) -> List[EcosystemsDependency]:
        """Get dependencies for a specific package version"""
        url = f"{self.BASE_URL}/registries/{registry}/packages/{name}/versions/{version}"
        response = self.session.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if 'dependencies' in data:
                return [EcosystemsDependency.from_dict(dep) for dep in data['dependencies']]
        
        return []

@dataclass 
class EcosystemsPackage:
    name: str
    ecosystem: str
    description: Optional[str]
    homepage: Optional[str]
    licenses: Optional[str]
    normalized_licenses: List[str]
    repository_url: Optional[str]
    purl: str
    latest_release_number: Optional[str]
    dependent_packages_count: int
    maintainers: List[Dict]
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'EcosystemsPackage':
        return cls(
            name=data['name'],
            ecosystem=data['ecosystem'],
            description=data.get('description'),
            homepage=data.get('homepage'),
            licenses=data.get('licenses'),
            normalized_licenses=data.get('normalized_licenses', []),
            repository_url=data.get('repository_url'),
            purl=data['purl'],
            latest_release_number=data.get('latest_release_number'),
            dependent_packages_count=data.get('dependent_packages_count', 0),
            maintainers=data.get('maintainers', [])
        )
```

#### Unified API Client with Intelligent Routing
```python
class ExternalAPIClient:
    """Unified client that intelligently routes requests to appropriate APIs"""
    
    def __init__(self, config: APIConfig):
        self.clearly_defined = ClearlyDefinedClient(config.clearly_defined_key)
        self.ecosystems = EcosystemsClient()
        self.config = config
        
    def enrich_metadata(self, metadata: PackageMetadata) -> EnrichedMetadata:
        """Combine local extraction with external API data"""
        enriched = EnrichedMetadata.from_metadata(metadata)
        
        # Try ClearlyDefined first for license information
        if self.config.use_clearly_defined:
            cd_data = self.clearly_defined.get_definition(metadata.purl)
            if cd_data:
                enriched = self._merge_clearly_defined_data(enriched, cd_data)
        
        # Use Ecosyste.ms for additional package metadata
        if self.config.use_ecosystems:
            eco_data = self.ecosystems.lookup_package(purl=metadata.purl)
            if eco_data:
                enriched = self._merge_ecosystems_data(enriched, eco_data[0])
        
        return enriched
    
    def _merge_clearly_defined_data(self, enriched: EnrichedMetadata, 
                                  cd_data: ClearlyDefinedData) -> EnrichedMetadata:
        """Merge ClearlyDefined data with existing metadata"""
        # Priority: ClearlyDefined curated data > local extraction
        if cd_data.get_license_expression():
            enriched.add_license_source("clearly_defined", cd_data.get_license_expression())
        
        if cd_data.get_source_location():
            enriched.source_repository = cd_data.get_source_location()
        
        enriched.confidence_scores['clearly_defined'] = cd_data.score
        enriched.api_sources.append('clearly_defined')
        
        return enriched
```

### 5. Output Format

#### Enhanced Standard JSON Schema with Package Type Detection
```json
{
  "$schema": "https://schemas.example.com/package-metadata/v1.1.0",
  "extraction_metadata": {
    "extractor_version": "1.0.0",
    "extraction_date": "2025-01-15T10:30:00Z",
    "package_type": "npm",
    "ecosystem": "javascript",
    "confidence_score": 0.95,
    "detection_methods": ["file_extension", "content_analysis"],
    "template_used": "npm_standard",
    "fallback_used": false,
    "package_manager_verified": true,
    "processing_time_ms": 1250,
    "api_sources": ["clearly_defined", "ecosystems"]
  },
  "package": {
    "name": "example-package",
    "version": "1.2.3",
    "purl": "pkg:npm/example-package@1.2.3",
    "ecosystem": "javascript",
    "package_type": "npm",
    "namespace": null,
    "description": "An example package",
    "homepage": "https://example.com",
    "repository": {
      "type": "git",
      "url": "https://github.com/example/example-package"
    },
    "authors": [
      {
        "name": "John Doe",
        "email": "john@example.com"
      }
    ],
    "maintainers": [
      {
        "name": "Jane Smith", 
        "email": "jane@example.com"
      }
    ],
    "dependencies": [
      {
        "name": "lodash",
        "version": "^4.17.21",
        "type": "runtime",
        "purl": "pkg:npm/lodash@4.17.21",
        "scope": "dependencies"
      }
    ],
    "dev_dependencies": [
      {
        "name": "jest",
        "version": "^27.0.0", 
        "type": "development",
        "purl": "pkg:npm/jest@27.0.0",
        "scope": "devDependencies"
      }
    ],
    "keywords": ["example", "package", "demo"],
    "creation_date": "2023-01-15T08:00:00Z",
    "modification_date": "2024-12-01T15:30:00Z",
    "file_hashes": {
      "sha1": "abc123...",
      "md5": "def456...", 
      "sha256": "ghi789..."
    },
    "size": 1048576
  },
  "licenses": [
    {
      "spdx_id": "MIT",
      "confidence": 0.98,
      "expression": "MIT", 
      "sources": ["metadata", "LICENSE.txt"],
      "detection_methods": ["spdx_match", "text_analysis"],
      "files": [
        {
          "path": "LICENSE.txt",
          "type": "license",
          "content_hash": {
            "sha1": "abc123...",
            "md5": "def456...",
            "fuzzy_hash": "ssdeep:123..."
          },
          "size": 1024,
          "detected_licenses": ["MIT"],
          "confidence": 0.98
        }
      ]
    }
  ],
  "legal_files": [
    {
      "path": "NOTICE.txt",
      "type": "notice",
      "content_hash": {
        "sha1": "xyz789...",
        "md5": "uvw012...",
        "fuzzy_hash": "ssdeep:456..."
      },
      "size": 512,
      "purpose": "attribution"
    },
    {
      "path": "COPYRIGHT",
      "type": "copyright",
      "content_hash": {
        "sha1": "mno345...",
        "md5": "pqr678...",
        "fuzzy_hash": "ssdeep:789..."
      },
      "size": 256,
      "purpose": "copyright_notice"
    }
  ],
  "build_config": {
    "build_system": "npm",
    "build_files": ["package.json", "package-lock.json"],
    "scripts": {
      "build": "webpack --mode production",
      "test": "jest",
      "lint": "eslint src/"
    },
    "project_structure": {
      "source_directories": ["src/", "lib/"],
      "test_directories": ["test/", "__tests__/"],
      "documentation": ["README.md", "docs/"],
      "entry_points": ["index.js", "src/main.js"]
    },
    "dependency_graph": {
      "total_dependencies": 45,
      "direct_dependencies": 8,
      "dev_dependencies": 12,
      "peer_dependencies": 2
    },
    "compilation_targets": ["es2018", "node14"],
    "build_flags": ["--optimize", "--minify"]
  },
  "detection_details": {
    "file_signatures_matched": [
      {
        "signature_name": "npm_package", 
        "confidence": 0.95,
        "matched_files": ["package.json"],
        "matched_patterns": ['"name":', '"version":']
      }
    ],
    "package_manager_verification": {
      "manager": "npm",
      "command_used": "npm view example-package --json",
      "verification_successful": true,
      "metadata_matches": true
    },
    "content_analysis": {
      "javascript_files": 15,
      "typescript_files": 0,
      "config_files": 3,
      "package_indicators": ["package.json", "node_modules/"]
    }
  },
  "api_enrichment": {
    "clearly_defined": {
      "available": true,
      "license_curated": true,
      "source_location_verified": true,
      "score": {
        "effective": 85,
        "tool": 75
      }
    },
    "ecosystems": {
      "available": true,
      "registry": "npmjs",
      "download_count": 150000,
      "dependent_packages": 25,
      "last_updated": "2024-12-01T15:30:00Z"
    }
  },
  "warnings": [
    "Some development dependencies may have security advisories"
  ],
  "errors": []
}
```

## Architecture Design

### 1. Core Components

```
semantic-copycat-upex/
├── extractors/
│   ├── base.py                    # Base extractor interface
│   ├── templates/                 # Package type templates and configurations  
│   │   ├── python.yaml            # Python ecosystem configuration
│   │   ├── javascript.yaml        # JavaScript/Node.js configuration
│   │   ├── java.yaml              # Java/Maven configuration
│   │   ├── rust.yaml              # Rust/Cargo configuration
│   │   └── generic.yaml           # Generic archive configuration
│   ├── python/                    # Python package extractors
│   │   ├── wheel_extractor.py     # .whl file extractor
│   │   ├── sdist_extractor.py     # Source distribution extractor
│   │   └── egg_extractor.py       # Legacy egg format
│   ├── javascript/                # NPM/Yarn extractors
│   │   ├── npm_extractor.py       # NPM package extractor
│   │   └── yarn_extractor.py      # Yarn package extractor
│   ├── java/                      # Maven/Gradle extractors
│   │   ├── jar_extractor.py       # JAR file extractor
│   │   ├── maven_extractor.py     # Maven POM extractor
│   │   └── gradle_extractor.py    # Gradle build extractor
│   ├── rust/                      # Cargo extractors
│   │   └── cargo_extractor.py     # Cargo package extractor
│   └── generic/                   # Generic archive extractors
│       ├── tar_extractor.py       # TAR archive extractor
│       ├── zip_extractor.py       # ZIP archive extractor
│       └── content_analyzer.py    # Content-based detection
├── detection/
│   ├── signatures.py              # Package signature definitions
│   ├── detector.py                # Main detection engine
│   ├── package_managers/          # Local package manager interfaces
│   │   ├── pip_manager.py         # pip interface
│   │   ├── npm_manager.py         # npm interface
│   │   ├── maven_manager.py       # maven interface
│   │   └── base_manager.py        # Base package manager interface
│   └── fallback_detector.py       # Fallback detection strategies
├── license/
│   ├── detector.py                # License detection engine
│   ├── spdx_normalizer.py         # SPDX normalization
│   ├── ml_models/                 # Pre-trained license detection models
│   └── license_patterns.py        # License file patterns
├── api_clients/
│   ├── clearly_defined.py         # ClearlyDefined API client
│   ├── ecosystems.py              # Ecosyste.ms API client  
│   ├── osv.py                     # OSV.dev API client
│   └── base_client.py             # Base API client
├── templates/                     # Extensible configuration templates
│   ├── package_types/             # Package type definitions
│   │   ├── npm.yaml               # NPM package configuration
│   │   ├── pypi.yaml              # PyPI package configuration
│   │   ├── maven.yaml             # Maven package configuration
│   │   └── cargo.yaml             # Cargo package configuration
│   ├── ecosystems/                # Ecosystem-specific configurations
│   │   ├── javascript.yaml        # JavaScript ecosystem
│   │   ├── python.yaml            # Python ecosystem
│   │   └── java.yaml              # Java ecosystem
│   └── schemas/                   # JSON schemas for validation
│       ├── package_metadata.json  # Package metadata schema
│       ├── license_info.json      # License information schema
│       └── output_format.json     # Output format schema
├── utils/
│   ├── file_hash.py               # File hashing utilities
│   ├── purl_generator.py          # PURL generation
│   ├── archive_handler.py         # Archive extraction
│   ├── template_loader.py         # Configuration template loader
│   └── confidence_calculator.py   # Confidence scoring
├── cli/
│   └── main.py                    # Command-line interface
└── core/
    ├── models.py                  # Data models
    ├── processor.py               # Main processing engine
    ├── config.py                  # Configuration management
    └── template_manager.py        # Template and configuration management
```

### 2. Extensible Template System

#### Package Type Templates
```yaml
# templates/package_types/npm.yaml
name: "npm"
ecosystem: "javascript"
provider: "npmjs"
description: "Node.js package manager packages"

detection:
  file_extensions: [".tgz", ".tar.gz"]
  required_files: ["package.json"]
  optional_files: ["package-lock.json", "yarn.lock", "node_modules/"]
  content_patterns:
    "package.json":
      - '"name":'
      - '"version":'
      - '"dependencies":'
  exclusion_patterns: ["requirements.txt", "pom.xml", "Cargo.toml"]
  confidence_base: 0.95

metadata_extraction:
  primary_manifest: "package.json"
  secondary_manifests: ["package-lock.json", "yarn.lock"]
  
  fields:
    name: "$.name"
    version: "$.version" 
    description: "$.description"
    license: "$.license"
    homepage: "$.homepage"
    repository: "$.repository.url"
    author: "$.author"
    maintainers: "$.maintainers"
    dependencies: "$.dependencies"
    dev_dependencies: "$.devDependencies"
    keywords: "$.keywords"

build_analysis:
  build_files: ["package.json", "webpack.config.js", "tsconfig.json"]
  script_fields: ["$.scripts"]
  build_commands: ["npm run build", "npm run compile"]

license_detection:
  metadata_fields: ["license", "licenses"]
  license_files: 
    patterns: ["LICENSE*", "COPYING*", "README*"]
    directories: ["./", "docs/", "legal/"]

local_package_manager:
  commands:
    info: ["npm", "view", "{package_name}", "--json"]
    analyze: ["npm", "list", "--json", "--depth=0"]
  verification:
    command: ["npm", "pack", "--dry-run"]
    timeout: 30

purl_template: "pkg:npm/{namespace}/{name}@{version}"
```

```yaml
# templates/package_types/pypi.yaml  
name: "pypi"
ecosystem: "python"
provider: "pypi"
description: "Python Package Index packages"

detection:
  file_extensions: [".whl", ".tar.gz", ".egg"]
  required_files: ["setup.py", "pyproject.toml", "PKG-INFO", "METADATA"]
  optional_files: ["requirements.txt", "setup.cfg", "MANIFEST.in"]
  content_patterns:
    "setup.py":
      - "from setuptools import"
      - "setup("
    "pyproject.toml":
      - "[build-system]"
      - "[tool.setuptools]"
  confidence_base: 0.90

metadata_extraction:
  primary_manifest: "PKG-INFO"  # for wheels
  secondary_manifests: ["METADATA", "setup.py", "pyproject.toml"]
  
  fields:
    name: "Name"
    version: "Version"
    description: "Summary"
    license: "License"
    homepage: "Home-page"
    author: "Author"
    author_email: "Author-email"
    maintainer: "Maintainer"
    classifier: "Classifier"

build_analysis:
  build_files: ["setup.py", "pyproject.toml", "setup.cfg"]
  build_commands: ["python setup.py build", "pip install -e ."]

local_package_manager:
  commands:
    info: ["pip", "show", "{package_name}"]
    analyze: ["pip", "inspect", "{package_file}"]
  verification:
    command: ["pip", "install", "--dry-run", "{package_file}"]
    timeout: 45

purl_template: "pkg:pypi/{name}@{version}"
```

#### Ecosystem Configuration Templates
```yaml
# templates/ecosystems/javascript.yaml
name: "javascript"
description: "JavaScript/Node.js ecosystem"

package_types:
  - npm
  - yarn

registries:
  - name: "npmjs"
    url: "https://registry.npmjs.org"
    purl_provider: "npmjs"
    api_endpoints:
      package_info: "/{name}"
      version_info: "/{name}/{version}"

build_systems:
  - name: "npm"
    config_files: ["package.json"]
    lock_files: ["package-lock.json"]
  - name: "yarn"  
    config_files: ["package.json"]
    lock_files: ["yarn.lock"]
  - name: "webpack"
    config_files: ["webpack.config.js"]

common_patterns:
  source_directories: ["src/", "lib/", "index.js"]
  test_directories: ["test/", "tests/", "__tests__/"]
  documentation: ["README.md", "docs/"]
  
license_conventions:
  metadata_fields: ["license", "licenses"]
  common_licenses: ["MIT", "Apache-2.0", "ISC", "BSD-3-Clause"]
  dual_license_patterns: ["MIT OR Apache-2.0"]

dependency_types:
  runtime: ["dependencies"]
  development: ["devDependencies"] 
  peer: ["peerDependencies"]
  optional: ["optionalDependencies"]
```

#### Template Management System
```python
class TemplateManager:
    """Manages package type and ecosystem templates for extensibility"""
    
    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)
        self.package_templates = {}
        self.ecosystem_templates = {}
        self.loaded = False
    
    def load_templates(self):
        """Load all configuration templates"""
        self._load_package_type_templates()
        self._load_ecosystem_templates()
        self._validate_templates()
        self.loaded = True
    
    def get_package_template(self, package_type: str) -> PackageTypeTemplate:
        """Get configuration template for a specific package type"""
        if not self.loaded:
            self.load_templates()
            
        if package_type not in self.package_templates:
            raise TemplateNotFoundError(f"No template found for package type: {package_type}")
            
        return self.package_templates[package_type]
    
    def get_ecosystem_template(self, ecosystem: str) -> EcosystemTemplate:
        """Get configuration template for a specific ecosystem"""
        if not self.loaded:
            self.load_templates()
            
        return self.ecosystem_templates.get(ecosystem)
    
    def register_custom_template(self, template_path: str):
        """Register a custom user-defined template"""
        template = self._load_template_file(template_path)
        
        if template.template_type == "package_type":
            self.package_templates[template.name] = template
        elif template.template_type == "ecosystem":
            self.ecosystem_templates[template.name] = template
    
    def get_detection_signatures(self) -> List[PackageSignature]:
        """Generate package signatures from all loaded templates"""
        signatures = []
        
        for template in self.package_templates.values():
            signature = PackageSignature(
                name=f"{template.name}_signature",
                package_type=template.name,
                ecosystem=template.ecosystem,
                required_files=template.detection.required_files,
                optional_files=template.detection.optional_files,
                file_patterns=[re.compile(p) for p in template.detection.file_patterns],
                content_patterns=template.detection.content_patterns,
                exclusion_patterns=template.detection.exclusion_patterns,
                confidence=template.detection.confidence_base,
                priority=template.detection.get('priority', 5)
            )
            signatures.append(signature)
        
        return sorted(signatures, key=lambda x: x.priority)

@dataclass
class PackageTypeTemplate:
    name: str
    ecosystem: str
    provider: str
    description: str
    detection: DetectionConfig
    metadata_extraction: MetadataConfig
    build_analysis: BuildConfig
    license_detection: LicenseConfig
    local_package_manager: PackageManagerConfig
    purl_template: str
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'PackageTypeTemplate':
        """Load template from YAML file"""
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)
```

### 2. Enhanced Processing Pipeline with Package Type Detection

```python
class PackageProcessor:
    def __init__(self, template_manager: TemplateManager, 
                 config: ProcessingConfig):
        self.template_manager = template_manager
        self.detector = PackageDetector(template_manager)
        self.extractor_factory = ExtractorFactory(template_manager)
        self.license_detector = LicenseDetector()
        self.api_client = ExternalAPIClient(config.api_config)
        self.config = config
    
    def process(self, package_path: str, options: ProcessingOptions) -> ProcessingResult:
        """Enhanced processing pipeline with intelligent package detection"""
        
        # Phase 1: Package Type Detection
        detection_result = self.detector.detect_package_type(package_path)
        
        if detection_result.confidence < self.config.min_confidence_threshold:
            if options.strict_mode:
                raise PackageDetectionError(
                    f"Could not reliably detect package type. "
                    f"Confidence: {detection_result.confidence}"
                )
            else:
                # Fall back to generic handling
                detection_result.package_type = "generic"
        
        # Phase 2: Get Template and Extractor
        template = self.template_manager.get_package_template(detection_result.package_type)
        extractor = self.extractor_factory.create_extractor(detection_result.package_type)
        
        # Phase 3: Extract Package Contents
        extraction_result = extractor.extract(package_path)
        
        # Phase 4: Parse Metadata Using Template
        metadata_parser = MetadataParser(template)
        metadata = metadata_parser.parse(extraction_result.extracted_path)
        
        # Phase 5: Detect Licenses
        license_detector = LicenseDetector(template.license_detection)
        licenses = license_detector.detect_all(
            extraction_result.extracted_path, 
            metadata
        )
        
        # Phase 6: Generate PURL
        purl_generator = PURLGenerator(template)
        purl = purl_generator.generate(metadata)
        
        # Phase 7: Build Analysis (if enabled)
        build_info = None
        if options.analyze_build_system:
            build_analyzer = BuildAnalyzer(template.build_analysis)
            build_info = build_analyzer.analyze(extraction_result.extracted_path)
        
        # Phase 8: External API Enrichment (if enabled)
        enriched_data = None
        if options.use_external_apis:
            enriched_data = self.api_client.enrich_metadata(metadata, purl)
        
        # Phase 9: Generate Final Output
        return ProcessingResult(
            package_type=detection_result.package_type,
            ecosystem=template.ecosystem,
            confidence=detection_result.confidence,
            detection_methods=detection_result.detection_methods,
            metadata=metadata,
            licenses=licenses,
            purl=purl,
            build_info=build_info,
            enriched_data=enriched_data,
            processing_time=time.time() - start_time,
            template_used=template.name,
            fallback_used=detection_result.fallback_used
        )
    
    def process_batch(self, package_paths: List[str], 
                     options: ProcessingOptions) -> List[ProcessingResult]:
        """Process multiple packages with optional parallelization"""
        if options.parallel and len(package_paths) > 1:
            return self._process_parallel(package_paths, options)
        else:
            return [self.process(path, options) for path in package_paths]
    
    def _process_parallel(self, package_paths: List[str], 
                         options: ProcessingOptions) -> List[ProcessingResult]:
        """Process packages in parallel using worker threads"""
        with ThreadPoolExecutor(max_workers=options.max_workers) as executor:
            futures = [
                executor.submit(self.process, path, options) 
                for path in package_paths
            ]
            return [future.result() for future in as_completed(futures)]

@dataclass
class ProcessingResult:
    package_type: str
    ecosystem: str
    confidence: float
    detection_methods: List[str]
    metadata: PackageMetadata
    licenses: List[LicenseInfo]
    purl: str
    build_info: Optional[BuildInformation]
    enriched_data: Optional[EnrichedMetadata]
    processing_time: float
    template_used: str
    fallback_used: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization"""
        return {
            "extraction_metadata": {
                "package_type": self.package_type,
                "ecosystem": self.ecosystem,
                "confidence": self.confidence,
                "detection_methods": self.detection_methods,
                "template_used": self.template_used,
                "fallback_used": self.fallback_used,
                "processing_time": self.processing_time,
                "extractor_version": "1.0.0",
                "extraction_date": datetime.utcnow().isoformat() + "Z"
            },
            "package": self.metadata.to_dict(),
            "licenses": [license.to_dict() for license in self.licenses],
            "build_info": self.build_info.to_dict() if self.build_info else None,
            "enriched_data": self.enriched_data.to_dict() if self.enriched_data else None,
            "errors": self.errors,
            "warnings": self.warnings
        }

class MetadataParser:
    """Parse package metadata using template-driven field extraction"""
    
    def __init__(self, template: PackageTypeTemplate):
        self.template = template
        self.field_extractors = self._build_field_extractors()
    
    def parse(self, extracted_path: str) -> PackageMetadata:
        """Parse metadata from extracted package using template configuration"""
        metadata = PackageMetadata()
        
        # Find and parse primary manifest
        primary_manifest = self._find_manifest_file(
            extracted_path, 
            self.template.metadata_extraction.primary_manifest
        )
        
        if primary_manifest:
            primary_data = self._parse_manifest_file(primary_manifest)
            metadata = self._extract_fields_from_data(primary_data, metadata)
        
        # Parse secondary manifests for additional information
        for secondary_manifest in self.template.metadata_extraction.secondary_manifests:
            manifest_file = self._find_manifest_file(extracted_path, secondary_manifest)
            if manifest_file:
                secondary_data = self._parse_manifest_file(manifest_file)
                metadata = self._merge_secondary_data(metadata, secondary_data)
        
        # Set ecosystem-specific fields
        metadata.ecosystem = self.template.ecosystem
        metadata.package_type = self.template.name
        
        return metadata
    
    def _extract_fields_from_data(self, data: Dict, metadata: PackageMetadata) -> PackageMetadata:
        """Extract fields using JSONPath expressions from template"""
        for field_name, json_path in self.template.metadata_extraction.fields.items():
            try:
                value = self._extract_json_path_value(data, json_path)
                if value:
                    setattr(metadata, field_name, value)
            except Exception as e:
                logger.warning(f"Failed to extract field {field_name}: {e}")
        
        return metadata
```

## CLI Interface

### Command Structure
```bash
# Basic extraction
upex package.whl

# Extract with API enrichment
upex package.jar --use-apis clearly_defined,ecosystems

# Extract multiple packages
upex *.whl --output-dir results/

# Extract with custom output format
upex package.gem --format json --output package-info.json

# Batch processing
upex --batch package-list.txt --workers 4

# License-only extraction
upex package.tgz --licenses-only

# Verbose mode with confidence scores
upex package.nupkg --verbose --show-confidence
```

### CLI Options
```bash
Options:
  --format [json|yaml|xml]        Output format (default: json)
  --output, -o TEXT              Output file path
  --output-dir TEXT              Output directory for batch processing
  --use-apis TEXT                Comma-separated list of APIs to use
  --batch TEXT                   Process packages from file list
  --workers INTEGER              Number of parallel workers (default: 1)
  --licenses-only                Extract only license information
  --verbose, -v                  Verbose output with debug information
  --show-confidence              Include confidence scores in output
  --min-confidence FLOAT         Minimum confidence threshold (default: 0.7)
  --recursive                    Extract nested packages
  --timeout INTEGER              API request timeout in seconds
  --cache-dir TEXT               Directory for API response caching
  --no-cache                     Disable API response caching
  --config TEXT                  Configuration file path
  --template-dir TEXT            Custom template directory
  --strict-mode                  Fail on low confidence detection
  --analyze-build-system         Include build system analysis
  --detect-only                  Only perform package type detection
  --force-type TEXT              Force specific package type detection
  --fallback-pm                  Use package manager fallback detection
  --export-template TEXT         Export detected package template to file
```

### Enhanced CLI Usage Examples
```bash
# Basic extraction with package type detection
upex unknown-package.tar.gz

# Force specific package type
upex generic-archive.tar.gz --force-type npm

# Detection only mode
upex suspicious-file.bin --detect-only --show-confidence

# Export detected configuration as template
upex new-package-type.tar.gz --export-template new-type.yaml

# Strict mode with high confidence requirement
upex package.tgz --strict-mode --min-confidence 0.9

# Use local package manager fallback
upex package.whl --fallback-pm --verbose

# Custom template directory
upex package.jar --template-dir ./custom-templates/

# Build system analysis
upex package.tgz --analyze-build-system --verbose

# Batch processing with package type detection
upex --batch mixed-packages.txt --workers 4 --show-confidence
```

## Special Cases and Edge Case Handling

### 1. Multiple Licenses
- Support for license expressions (MIT OR Apache-2.0)
- Dual licensing detection from metadata and files
- Conflicting license resolution with confidence scoring
- License compatibility analysis

### 2. Nested Packages
- Recursive extraction of packages within packages
- Dependency package analysis
- Vendor directory handling
- Embedded library detection

### 3. Incomplete Metadata
- Fallback to file-based detection when metadata is missing
- Heuristic-based package type detection
- External API supplementation of missing data
- Confidence scoring for uncertain extractions

### 4. Large Packages
- Streaming extraction for large archives
- Selective file processing for performance
- Memory-efficient processing of multi-GB packages
- Progress reporting for long-running extractions

## Performance and Scalability

### 1. Optimization Strategies
- Lazy loading of extraction modules
- Parallel processing for batch operations
- Caching of API responses and license detection results
- Incremental processing for large package sets

### 2. Memory Management
- Streaming file processing
- Temporary file cleanup
- Configurable memory limits
- Efficient data structures for large datasets

### 3. Caching Strategy
```python
class CacheManager:
    def cache_api_response(self, purl: str, api_name: str, response: Dict):
        """Cache API responses to reduce external calls"""
        pass
    
    def cache_license_detection(self, file_hash: str, license_info: LicenseInfo):
        """Cache license detection results for identical files"""
        pass
    
    def get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Retrieve cached results"""
        pass
```

## Configuration Management

### Configuration File Format (YAML)
```yaml
# config.yaml
general:
  temp_dir: "/tmp/universal-extractor"
  max_extraction_size: "1GB"
  timeout: 30
  min_confidence_threshold: 0.7
  strict_mode: false

# Package detection configuration
detection:
  use_file_extensions: true
  use_content_analysis: true
  use_package_manager_fallback: true
  cache_detection_results: true
  
  # Confidence thresholds for different detection methods
  confidence_thresholds:
    file_extension: 0.6
    content_analysis: 0.8
    package_manager: 0.9
    signature_match: 0.85

# Template system configuration  
templates:
  default_template_dir: "./templates"
  custom_template_dirs: 
    - "./custom-templates"
    - "/usr/local/share/universal-extractor/templates"
  auto_reload: false
  cache_templates: true

# External API configuration
apis:
  clearly_defined:
    enabled: true
    api_key: null
    base_url: "https://api.clearlydefined.io"
    rate_limit: 2000  # requests per minute
    timeout: 30
    retry_attempts: 3
    cache_responses: true
    harvest_missing: false  # Auto-harvest missing components
  
  ecosystems:
    enabled: true
    base_url: "https://packages.ecosyste.ms/api/v1"
    rate_limit: 500  # requests per 5 minutes  
    timeout: 30
    retry_attempts: 3
    cache_responses: true

  osv:
    enabled: false
    base_url: "https://api.osv.dev"
    
  libraries_io:
    enabled: false
    api_key: null
    base_url: "https://libraries.io/api"

# Package manager fallback configuration
package_managers:
  pip:
    enabled: true
    command: "pip"
    timeout: 45
    verify_installation: true
    
  npm:
    enabled: true
    command: "npm"  
    timeout: 30
    verify_installation: true
    
  maven:
    enabled: true
    command: "mvn"
    timeout: 60
    verify_installation: true
    
  cargo:
    enabled: true
    command: "cargo"
    timeout: 45
    verify_installation: true

# License detection configuration
license_detection:
  confidence_threshold: 0.7
  use_ml_models: true
  spdx_strict_mode: false
  fuzzy_matching: true
  detect_dual_licenses: true
  detect_license_expressions: true
  
  # File patterns for license detection
  license_file_patterns:
    - "LICEN[SC]E*"
    - "COPYING*"
    - "COPYRIGHT*"
    - "NOTICE*"
    - "PATENTS*"
    - "README*"
    
  license_file_extensions:
    - ""
    - ".txt"
    - ".md"
    - ".rst"
    - ".license"

# Build system analysis
build_analysis:
  enabled: true
  analyze_dependencies: true
  analyze_build_scripts: true
  analyze_project_structure: true
  detect_build_tools: true
  
  # Build system specific configuration
  build_systems:
    npm:
      analyze_scripts: true
      analyze_dependencies: true
      check_lock_files: true
    maven:
      analyze_pom: true
      analyze_dependencies: true
      check_profiles: true
    gradle:
      analyze_build_gradle: true
      analyze_dependencies: true

# Output configuration
output:
  include_confidence_scores: false
  include_file_hashes: true
  include_detection_details: false
  include_api_enrichment: false
  hash_algorithms: ["sha1", "md5", "sha256"]
  fuzzy_hash_algorithm: "ssdeep"
  
  # Schema validation
  validate_output: true
  schema_version: "1.1.0"

# Extraction configuration
extraction:
  max_recursion_depth: 3
  extract_nested_packages: true
  skip_test_files: false
  skip_documentation: false
  file_size_limit: "100MB"
  preserve_permissions: false
  
  # Archive extraction limits
  max_archive_size: "1GB"
  max_files_per_archive: 50000
  extraction_timeout: 300  # seconds

# Caching configuration
cache:
  enabled: true
  cache_dir: "./cache"
  max_cache_size: "1GB"
  cache_ttl: 86400  # 24 hours
  
  # What to cache
  cache_api_responses: true
  cache_license_detection: true
  cache_package_detection: true
  cache_file_hashes: true

# Logging configuration
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: null  # Log to stdout if null
  max_file_size: "10MB"
  backup_count: 5

# Performance tuning
performance:
  max_workers: 4
  memory_limit: "2GB"
  enable_parallel_processing: true
  batch_size: 100
  
  # I/O optimization
  use_memory_mapping: true
  buffer_size: 65536
```

## Security Considerations

### 1. Safe Extraction
- Zip bomb protection
- Path traversal prevention
- File size limits
- Malware scanning integration points

### 2. External API Security
- API key management
- Rate limiting
- SSL/TLS verification
- Request timeout handling

### 3. Temporary File Management
- Secure temporary directory creation
- Automatic cleanup on exit
- Permission restrictions on extracted files

## Testing Strategy

### 1. Test Package Repository
- Curated test packages for each ecosystem
- Edge cases and malformed packages
- Known license detection test cases
- Performance benchmark packages

### 2. Test Categories
- Unit tests for individual components
- Integration tests for end-to-end workflows
- Performance tests for large packages
- API integration tests with mocking
- License detection accuracy tests

### 3. Continuous Integration
```yaml
# .github/workflows/test.yml
test_matrix:
  python_version: [3.8, 3.9, 3.10, 3.11, 3.12]
  package_ecosystem: [python, javascript, java, rust, generic]
  test_type: [unit, integration, performance]
```

## Deployment and Distribution

### 1. PyPI Package Structure
```
semantic-copycat-upex/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── src/upex/               # Main package code
├── tests/
├── docs/
└── examples/
```

### 2. Installation Options
```bash
# Standard installation
pip install semantic-copycat-upex

# With all optional dependencies
pip install semantic-copycat-upex[all]

# ML license detection support
pip install semantic-copycat-upex[ml]

# Development installation
pip install semantic-copycat-upex[dev]
```

### 3. Usage
```bash
# CLI usage after installation
upex package.whl
upex --help

# Python library usage
python -c "from upex import PackageProcessor; print('Library imported successfully')"
```

## Documentation Plan

### 1. User Documentation
- Quick start guide
- CLI reference
- API documentation
- Configuration guide
- License detection guide

### 2. Developer Documentation
- Architecture overview
- Adding new extractors
- Custom license detection
- API integration guide
- Contributing guidelines

### 3. Examples and Tutorials
- Common use cases
- Integration with CI/CD pipelines
- Custom processing workflows
- Enterprise deployment scenarios

## Future Enhancements

### Phase 2 Features
- GUI interface for non-technical users
- Plugin system for custom extractors
- Real-time package monitoring
- License compliance reporting
- SBOM (Software Bill of Materials) generation
- Integration with vulnerability databases
- Machine learning improvements for license detection
- Support for additional package ecosystems

### Enterprise Features
- High-availability deployment
- Database backend for large-scale processing
- Advanced reporting and analytics
- Role-based access control
- Audit logging and compliance tracking

This specification provides a comprehensive foundation for building a robust, scalable universal package metadata extraction library that meets enterprise requirements while remaining accessible to individual developers.
