"""Configuration management with environment variable support."""

import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
import copy


logger = logging.getLogger(__name__)


def path_setting(config, key, default=None):
    """A setting that has to name a path, or nothing.

    Environment values are converted by shape, so PME_TEMP_DIR=false arrives
    as the boolean False and PME_LOG_FILE=/tmp/a,b.log as a list. Both used to
    reach the code that opens them: one passed for nobody having asked, the
    other raised a TypeError the caller was not catching. Checked in one place
    because the same mistake was made separately for three settings.
    """
    value = setting(config, key, default)
    if value is None or value == '':
        return None
    if not isinstance(value, (str, os.PathLike)):
        logger.warning(
            "%s is %r, which is not a path; ignoring it", key, value
        )
        return None
    return str(value)


def int_setting(config, key, default=None):
    """A setting that has to be a whole number of something, or nothing.

    bool is a subclass of int, so PME_MAX_FILE_SIZE=true would otherwise pass
    for a limit of one byte and refuse everything.
    """
    value = setting(config, key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        logger.warning(
            "%s is %r, which is not a number; ignoring it", key, value
        )
        return None
    return value


def setting(config: Any, key: str, default: Any = None) -> Any:
    """Read a dotted setting from a Config or from a plain nested mapping.

    The CLI holds a Config, whose get understands the dotted key. The
    extractors are handed what Config.to_dict() produced, which is an ordinary
    nested dict and answers that key with the default. Reading both means a
    setting reaches whichever of them asks.
    """
    value = config.get(key, default) if hasattr(config, 'get') else default
    if value is not default:
        return value

    node = config
    for part in key.split('.'):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


class Config:
    """Configuration manager with environment variable override support."""
    
    DEFAULT_CONFIG = {
        "api": {
            "clearlydefined": {
                "enabled": True,
                "base_url": "https://api.clearlydefined.io",
                "timeout": 30,
                "api_key": None  # Set via PME_CLEARLYDEFINED_API_KEY env var
            },
            "purldb": {
                "enabled": True,
                "base_url": "https://public.purldb.io",
                "timeout": 30,
                "api_key": None  # Set via PME_PURLDB_API_KEY env var
            },
            "vulnerablecode": {
                "enabled": True,
                "base_url": "https://public.vulnerablecode.io",
                "timeout": 30,
                "api_key": None  # Set via PME_VULNERABLECODE_API_KEY env var
            },
            "ecosystems": {
                "enabled": True,
                "base_url": "https://packages.ecosyste.ms/api/v1",
                "timeout": 30,
                "api_key": None  # Set via PME_ECOSYSTEMS_API_KEY env var
            }
        },
        "extraction": {
            "max_file_size": 500_000_000,  # 500MB
            "temp_dir": None,  # Uses system temp by default
        },

        "output": {
            "format": "json",
            # Compact, which is what upmex has always emitted. The setting
            # said True while nothing read it, so turning it on now would
            # quietly reformat everyone's output.
            "pretty_print": False,
            "include_raw_metadata": False,
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
        # Documented in the README and mapped to nothing, so exporting either
        # of these set a key that never reached the client.
        "PME_PURLDB_API_KEY": "api.purldb.api_key",
        "PME_VULNERABLECODE_API_KEY": "api.vulnerablecode.api_key",
        "PME_API_TIMEOUT": "api.*.timeout",
        "PME_MAX_FILE_SIZE": "extraction.max_file_size",
        "PME_TEMP_DIR": "extraction.temp_dir",
        "PME_OUTPUT_FORMAT": "output.format",
        "PME_LOG_LEVEL": "logging.level",
        "PME_LOG_FILE": "logging.file"
    }
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration.
        
        Args:
            config_file: Optional path to configuration file
        """
        # Deep, because set() writes into the nested dicts: a shallow copy
        # shares them with DEFAULT_CONFIG, so one instance calling set()
        # changed what every later Config() and every default-constructed
        # client would read, for the life of the process.
        self.config = copy.deepcopy(self.DEFAULT_CONFIG)
        
        # Load from file if provided
        if config_file:
            self.load_from_file(config_file)
        
        # Override with environment variables
        self.load_from_env()
        
        # Set default directories if not configured
    
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