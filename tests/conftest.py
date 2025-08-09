"""Pytest configuration and fixtures."""

import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_config():
    """Provide sample configuration for tests."""
    return {
        "api": {
            "clearlydefined": {
                "enabled": False,
                "base_url": "https://api.clearlydefined.io/v1",
                "timeout": 5
            }
        },
        "extraction": {
            "max_file_size": 100_000_000,
            "cache_enabled": False
        },
        "license_detection": {
            "methods": ["regex"],
            "confidence_threshold": 0.8
        },
        "output": {
            "format": "json",
            "pretty_print": False
        }
    }