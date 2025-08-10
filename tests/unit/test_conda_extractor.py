"""Tests for Conda package extractor."""

import json
import tarfile
import zipfile
import tempfile
import os
import yaml
from pathlib import Path
from datetime import datetime

import pytest
from src.upmex.extractors.conda_extractor import CondaExtractor
from src.upmex.core.models import PackageType, NO_ASSERTION


class TestCondaExtractor:
    """Test Conda package extraction."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = CondaExtractor()
    
    def test_extract_conda_format_metadata(self):
        """Test extracting metadata from .conda format (zip-based)."""
        # Create index.json content
        index_json = {
            "name": "numpy",
            "version": "1.24.3",
            "build": "py39h1234567_0",
            "build_number": 0,
            "depends": [
                "python >=3.9,<3.10.0a0",
                "libopenblas >=0.3.20,<0.4.0a0"
            ],
            "license": "BSD-3-Clause",
            "subdir": "osx-64",
            "channel": "conda-forge"
        }
        
        # Create recipe meta.yaml content
        recipe_yaml = {
            "about": {
                "home": "https://numpy.org",
                "summary": "Fundamental package for array computing in Python",
                "license": "BSD-3-Clause",
                "dev_url": "https://github.com/numpy/numpy"
            },
            "requirements": {
                "build": ["cython"],
                "host": ["python", "pip"],
                "run": ["python", "libopenblas"]
            },
            "extra": {
                "recipe-maintainers": ["rgommers", "charris"]
            }
        }
        
        # Create a temporary .conda file
        with tempfile.NamedTemporaryFile(suffix='.conda', delete=False) as f:
            temp_path = f.name
        
        try:
            # Create the .conda package structure
            with zipfile.ZipFile(temp_path, 'w') as zf:
                zf.writestr('info/index.json', json.dumps(index_json))
                zf.writestr('info/recipe/meta.yaml', yaml.dump(recipe_yaml))
            
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "numpy"
            assert metadata.version == "1.24.3"
            assert metadata.package_type == PackageType.CONDA
            assert metadata.description == "Fundamental package for array computing in Python"
            assert metadata.homepage == "https://numpy.org"
            assert metadata.repository == "https://github.com/numpy/numpy"
            
            # Check dependencies (recipe takes precedence over index.json)
            assert "runtime" in metadata.dependencies
            assert "python" in metadata.dependencies["runtime"]
            assert "libopenblas" in metadata.dependencies["runtime"]
            
            # Check authors
            assert len(metadata.authors) == 2
            author_names = [author['name'] for author in metadata.authors]
            assert "rgommers" in author_names
            assert "charris" in author_names
            
            # Check keywords
            assert "conda-forge" in str(metadata.keywords)
            assert "osx-64" in metadata.keywords
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_tar_bz2_metadata(self):
        """Test extracting metadata from .tar.bz2 conda package."""
        # Create index.json content
        index_json = {
            "name": "pandas",
            "version": "2.0.3",
            "build": "py39h1234567_0",
            "build_number": 0,
            "depends": [
                "python >=3.9,<3.10.0a0",
                "numpy >=1.20.3,<2.0a0"
            ],
            "license": "BSD-3-Clause",
            "subdir": "linux-64"
        }
        
        # Create temporary .tar.bz2 file
        with tempfile.NamedTemporaryFile(suffix='.tar.bz2', delete=False) as f:
            temp_path = f.name
        
        try:
            # Create the .tar.bz2 package structure
            with tarfile.open(temp_path, 'w:bz2') as tar:
                # Add info/index.json
                info = tarfile.TarInfo('info/index.json')
                data = json.dumps(index_json).encode('utf-8')
                info.size = len(data)
                import io
                tar.addfile(info, io.BytesIO(data))
            
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "pandas"
            assert metadata.version == "2.0.3"
            assert metadata.package_type == PackageType.CONDA
            
            # Check dependencies
            assert "runtime" in metadata.dependencies
            deps = metadata.dependencies["runtime"]
            assert any("numpy" in dep for dep in deps)
            
            # Check license
            assert len(metadata.licenses) > 0
            assert metadata.licenses[0].spdx_id == "BSD-3-Clause"
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_with_recipe_json(self):
        """Test extracting metadata with recipe.json instead of meta.yaml."""
        index_json = {
            "name": "scipy",
            "version": "1.11.1",
            "build": "py39h1234567_0",
            "build_number": 1,
            "license": "BSD-3-Clause"
        }
        
        recipe_json = {
            "about": {
                "home": "https://scipy.org",
                "summary": "Scientific Library for Python",
                "author": "SciPy Developers"
            },
            "requirements": {
                "run": ["python", "numpy >=1.19.5"]
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.conda', delete=False) as f:
            temp_path = f.name
        
        try:
            with zipfile.ZipFile(temp_path, 'w') as zf:
                zf.writestr('info/index.json', json.dumps(index_json))
                zf.writestr('info/recipe.json', json.dumps(recipe_json))
            
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "scipy"
            assert metadata.version == "1.11.1"
            assert metadata.description == "Scientific Library for Python"
            assert metadata.homepage == "https://scipy.org"
            
            # Check author extraction
            assert len(metadata.authors) == 1
            assert metadata.authors[0]['name'] == "SciPy Developers"
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_minimal_metadata(self):
        """Test extracting minimal metadata from index.json only."""
        index_json = {
            "name": "minimal-package",
            "version": "0.1.0",
            "build": "0",
            "build_number": 0
        }
        
        with tempfile.NamedTemporaryFile(suffix='.conda', delete=False) as f:
            temp_path = f.name
        
        try:
            with zipfile.ZipFile(temp_path, 'w') as zf:
                zf.writestr('info/index.json', json.dumps(index_json))
            
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "minimal-package"
            assert metadata.version == "0.1.0"
            assert metadata.package_type == PackageType.CONDA
            assert metadata.description == NO_ASSERTION
            
            # Check raw metadata
            assert metadata.raw_metadata['build'] == "0"
            assert metadata.raw_metadata['build_number'] == 0
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_with_features(self):
        """Test extracting metadata with features and track_features."""
        index_json = {
            "name": "tensorflow",
            "version": "2.13.0",
            "build": "gpu_py39h1234567_0",
            "features": ["gpu"],
            "track_features": ["tensorflow-gpu"],
            "depends": [
                "python >=3.9,<3.10.0a0",
                "cudatoolkit >=11.2,<12.0a0"
            ]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.conda', delete=False) as f:
            temp_path = f.name
        
        try:
            with zipfile.ZipFile(temp_path, 'w') as zf:
                zf.writestr('info/index.json', json.dumps(index_json))
            
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "tensorflow"
            assert metadata.version == "2.13.0"
            
            # Check features in keywords
            assert "gpu" in metadata.keywords
            assert "tensorflow-gpu" in metadata.keywords
            
        finally:
            os.unlink(temp_path)
    
    def test_extract_with_detailed_requirements(self):
        """Test extracting metadata with detailed build/host/run requirements."""
        index_json = {
            "name": "scikit-learn",
            "version": "1.3.0",
            "build": "py39h1234567_0"
        }
        
        recipe_yaml = {
            "requirements": {
                "build": [
                    "cython >=0.29.33",
                    "compiler_c",
                    "compiler_cxx"
                ],
                "host": [
                    "python",
                    "pip",
                    "numpy >=1.17.3"
                ],
                "run": [
                    "python",
                    "numpy >=1.17.3",
                    "scipy >=1.5.0",
                    "joblib >=1.1.1",
                    "threadpoolctl >=2.0.0"
                ]
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.conda', delete=False) as f:
            temp_path = f.name
        
        try:
            with zipfile.ZipFile(temp_path, 'w') as zf:
                zf.writestr('info/index.json', json.dumps(index_json))
                zf.writestr('info/recipe/meta.yaml', yaml.dump(recipe_yaml))
            
            metadata = self.extractor.extract(temp_path)
            
            assert metadata.name == "scikit-learn"
            assert metadata.version == "1.3.0"
            
            # Check different dependency types
            assert "build" in metadata.dependencies
            assert "host" in metadata.dependencies
            assert "runtime" in metadata.dependencies
            
            # Check specific dependencies
            build_deps = metadata.dependencies["build"]
            assert any("cython" in dep for dep in build_deps)
            
            runtime_deps = metadata.dependencies["runtime"]
            assert any("scipy" in dep for dep in runtime_deps)
            assert any("joblib" in dep for dep in runtime_deps)
            
        finally:
            os.unlink(temp_path)
    
    def test_can_extract(self):
        """Test that can_extract correctly identifies Conda packages."""
        # Test .conda file
        with tempfile.NamedTemporaryFile(suffix='.conda', delete=False) as f:
            conda_path = f.name
        
        try:
            assert self.extractor.can_extract(conda_path) == True
        finally:
            os.unlink(conda_path)
        
        # Test .tar.bz2 with conda structure
        with tempfile.NamedTemporaryFile(suffix='.tar.bz2', delete=False) as f:
            tar_path = f.name
        
        try:
            # Create conda package structure
            with tarfile.open(tar_path, 'w:bz2') as tar:
                info = tarfile.TarInfo('info/index.json')
                data = b'{}'
                info.size = len(data)
                import io
                tar.addfile(info, io.BytesIO(data))
            
            assert self.extractor.can_extract(tar_path) == True
        finally:
            os.unlink(tar_path)
        
        # Test non-conda file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            zip_path = f.name
        
        try:
            assert self.extractor.can_extract(zip_path) == False
        finally:
            os.unlink(zip_path)
    
    def test_extract_invalid_package(self):
        """Test handling of invalid package files."""
        # Create an invalid .conda file
        with tempfile.NamedTemporaryFile(suffix='.conda', delete=False) as f:
            f.write(b'invalid zip content')
            temp_path = f.name
        
        try:
            metadata = self.extractor.extract(temp_path)
            
            # Should create minimal metadata with error
            assert metadata.package_type == PackageType.CONDA
            assert metadata.version == NO_ASSERTION
            assert "extraction_error" in metadata.raw_metadata
            
        finally:
            os.unlink(temp_path)
    
    def test_package_detection(self):
        """Test that package detection works correctly."""
        from src.upmex.utils.package_detector import detect_package_type
        
        # Test .conda file
        with tempfile.NamedTemporaryFile(suffix='.conda', delete=False) as f:
            temp_path = f.name
        
        try:
            assert detect_package_type(temp_path) == PackageType.CONDA
        finally:
            os.unlink(temp_path)
        
        # Test .tar.bz2 conda package
        with tempfile.NamedTemporaryFile(suffix='.tar.bz2', delete=False) as f:
            tar_path = f.name
        
        try:
            # Create conda package structure
            with tarfile.open(tar_path, 'w:bz2') as tar:
                info = tarfile.TarInfo('info/index.json')
                data = b'{}'
                info.size = len(data)
                import io
                tar.addfile(info, io.BytesIO(data))
            
            assert detect_package_type(tar_path) == PackageType.CONDA
        finally:
            os.unlink(tar_path)