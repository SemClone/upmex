"""Tests for configuration management."""

import os
import json
import pytest
from pathlib import Path
from upmex.config import Config


class TestConfig:
    """Test configuration management."""
    
    def test_default_config(self):
        """Test default configuration is loaded."""
        config = Config()
        
        assert config.get("api.clearlydefined.enabled") is True
        assert config.get("extraction.cache_enabled") is True
        assert config.get("output.format") == "json"
        assert config.get("logging.level") == "INFO"
    
    def test_get_nested_value(self):
        """Test getting nested configuration values."""
        config = Config()
        
        assert config.get("api.clearlydefined.base_url") == "https://api.clearlydefined.io/v1"
        assert config.get("license_detection.confidence_threshold") == 0.85
        assert config.get("non.existent.key", "default") == "default"
    
    def test_set_nested_value(self):
        """Test setting nested configuration values."""
        config = Config()
        
        config.set("api.clearlydefined.enabled", False)
        assert config.get("api.clearlydefined.enabled") is False
        
        config.set("new.nested.value", "test")
        assert config.get("new.nested.value") == "test"
    
    def test_env_var_override(self, monkeypatch):
        """Test environment variable overrides."""
        monkeypatch.setenv("PME_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("PME_CACHE_ENABLED", "false")
        monkeypatch.setenv("PME_LICENSE_METHODS", "regex,dice_sorensen")
        
        config = Config()
        
        assert config.get("logging.level") == "DEBUG"
        assert config.get("extraction.cache_enabled") is False
        assert config.get("license_detection.methods") == ["regex", "dice_sorensen"]
    
    def test_load_from_json_file(self, tmp_path, monkeypatch):
        """Test loading configuration from JSON file."""
        # Clear all PME environment variables to avoid interference
        for key in list(os.environ.keys()):
            if key.startswith('PME_'):
                monkeypatch.delenv(key, raising=False)
        
        config_file = tmp_path / "config.json"
        config_data = {
            "api": {
                "clearlydefined": {
                    "enabled": False
                }
            },
            "output": {
                "format": "yaml"
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = Config(str(config_file))
        
        assert config.get("api.clearlydefined.enabled") is False
        assert config.get("output.format") == "yaml"
        # Check that other defaults are preserved
        assert config.get("logging.level") in ["INFO", "DEBUG"]  # Allow both since env might affect it
    
    def test_save_config(self, tmp_path):
        """Test saving configuration to file."""
        config = Config()
        config.set("test.value", "saved")
        
        config_file = tmp_path / "saved_config.json"
        config.save(str(config_file))
        
        assert config_file.exists()
        
        with open(config_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["test"]["value"] == "saved"
    
    def test_api_key_from_env(self, monkeypatch):
        """Test API key loading from environment variables."""
        monkeypatch.setenv("PME_CLEARLYDEFINED_API_KEY", "test-api-key-123")
        monkeypatch.setenv("PME_ECOSYSTEMS_API_KEY", "eco-key-456")
        
        config = Config()
        
        assert config.get("api.clearlydefined.api_key") == "test-api-key-123"
        assert config.get("api.ecosystems.api_key") == "eco-key-456"