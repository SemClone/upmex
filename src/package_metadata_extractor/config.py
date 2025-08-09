"""Configuration management with environment variable support."""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Configuration manager with environment variable override support."""
    
    DEFAULT_CONFIG = {
        "api": {
            "clearlydefined": {
                "enabled": True,
                "base_url": "https://api.clearlydefined.io/v1",
                "timeout": 30,
                "api_key": None  # Set via PME_CLEARLYDEFINED_API_KEY env var
            },
            "ecosystems": {
                "enabled": True,
                "base_url": "https://api.ecosyste.ms/v1",
                "timeout": 30,
                "api_key": None  # Set via PME_ECOSYSTEMS_API_KEY env var
            }
        },
        "extraction": {
            "max_file_size": 500_000_000,  # 500MB
            "temp_dir": None,  # Uses system temp by default
            "parallel_processing": False,
            "cache_enabled": True,
            "cache_dir": None  # Set via PME_CACHE_DIR or ~/.cache/pme
        },
        "license_detection": {
            "methods": ["regex", "dice_sorensen"],  # Methods to use in order
            "confidence_threshold": 0.85,
            "max_text_length": 100_000,
            "enable_ml": False  # Requires ml extra dependencies
        },
        "output": {
            "format": "json",
            "pretty_print": True,
            "include_raw_metadata": False,
            "schema_version": "1.0.0"
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": None  # Set via PME_LOG_FILE env var
        }
    }
    
    ENV_VAR_MAPPING = {
        "PME_CLEARLYDEFINED_API_KEY": "api.clearlydefined.api_key",
        "PME_ECOSYSTEMS_API_KEY": "api.ecosystems.api_key",
        "PME_API_TIMEOUT": "api.*.timeout",
        "PME_MAX_FILE_SIZE": "extraction.max_file_size",
        "PME_TEMP_DIR": "extraction.temp_dir",
        "PME_CACHE_DIR": "extraction.cache_dir",
        "PME_CACHE_ENABLED": "extraction.cache_enabled",
        "PME_LICENSE_CONFIDENCE": "license_detection.confidence_threshold",
        "PME_LICENSE_METHODS": "license_detection.methods",
        "PME_ENABLE_ML": "license_detection.enable_ml",
        "PME_OUTPUT_FORMAT": "output.format",
        "PME_LOG_LEVEL": "logging.level",
        "PME_LOG_FILE": "logging.file"
    }
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration.
        
        Args:
            config_file: Optional path to configuration file
        """
        self.config = self.DEFAULT_CONFIG.copy()
        
        # Load from file if provided
        if config_file:
            self.load_from_file(config_file)
        
        # Override with environment variables
        self.load_from_env()
        
        # Set default directories if not configured
        self._set_default_dirs()
    
    def load_from_file(self, config_file: str):
        """Load configuration from JSON file.
        
        Args:
            config_file: Path to configuration file
        """
        path = Path(config_file)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        with open(path, 'r') as f:
            if path.suffix == '.json':
                file_config = json.load(f)
            else:
                raise ValueError(f"Unsupported config file format: {path.suffix}. Use .json files.")
        
        # Merge with default config
        self.config = self._deep_merge(self.config, file_config)
    
    def load_from_env(self):
        """Load configuration from environment variables."""
        for env_var, config_path in self.ENV_VAR_MAPPING.items():
            value = os.environ.get(env_var)
            if value is not None:
                self._set_nested(config_path, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key.
        
        Args:
            key: Dot-notation key (e.g., 'api.clearlydefined.enabled')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value by dot-notation key.
        
        Args:
            key: Dot-notation key
            value: Value to set
        """
        self._set_nested(key, value)
    
    def _set_nested(self, key: str, value: Any):
        """Set nested configuration value."""
        keys = key.split('.')
        
        # Handle wildcard paths
        if '*' in key:
            # Apply to all matching paths
            base_path = keys[0]
            if base_path in self.config:
                for sub_key in self.config[base_path]:
                    sub_path = f"{base_path}.{sub_key}.{'.'.join(keys[2:])}"
                    self._set_nested(sub_path, value)
            return
        
        # Regular path
        current = self.config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Convert value types
        if isinstance(value, str):
            if value.lower() in ['true', 'false']:
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif ',' in value:
                value = [v.strip() for v in value.split(',')]
        
        current[keys[-1]] = value
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _set_default_dirs(self):
        """Set default directories if not configured."""
        if not self.config['extraction']['cache_dir']:
            cache_dir = Path.home() / '.cache' / 'pme'
            self.config['extraction']['cache_dir'] = str(cache_dir)
        
        if not self.config['extraction']['temp_dir']:
            import tempfile
            self.config['extraction']['temp_dir'] = tempfile.gettempdir()
    
    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        return self.config.copy()
    
    def save(self, file_path: str):
        """Save configuration to file.
        
        Args:
            file_path: Path to save configuration
        """
        path = Path(file_path)
        
        with open(path, 'w') as f:
            json.dump(self.config, f, indent=2)