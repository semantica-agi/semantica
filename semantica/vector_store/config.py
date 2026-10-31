"""
Configuration Management Module for Vector Store

This module provides centralized configuration management for vector store operations,
supporting multiple configuration sources including environment variables, config files,
and programmatic configuration.

Supported Configuration Sources:
    - Environment variables: VECTOR_STORE_DEFAULT_BACKEND, VECTOR_STORE_DIMENSION, VECTOR_STORE_BATCH_SIZE, etc.
    - Config files: YAML, JSON, TOML formats
    - Programmatic: Python API for setting vector store configurations

Algorithms Used:
    - Environment Variable Parsing: OS-level environment variable access
    - YAML Parsing: YAML parser for configuration file loading
    - JSON Parsing: JSON parser for configuration file loading
    - TOML Parsing: TOML parser for configuration file loading
    - Fallback Chain: Priority-based configuration resolution
    - Dictionary Merging: Deep merge algorithms for configuration updates

Key Features:
    - Environment variable support for vector store parameters
    - Config file support (YAML, JSON, TOML formats)
    - Programmatic configuration via Python API
    - Method-specific configuration management
    - Automatic fallback chain (config file -> environment -> defaults)
    - Global config instance for easy access

Main Classes:
    - VectorStoreConfig: Main configuration manager class for vector store module

Example Usage:
    >>> from semantica.vector_store.config import vector_store_config
    >>> default_backend = vector_store_config.get("default_backend", default="faiss")
    >>> vector_store_config.set("default_backend", "faiss")
    >>> method_config = vector_store_config.get_method_config("store_vectors")
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.logging import get_logger


class VectorStoreConfig:
    """Configuration manager for vector store module - supports .env files, environment variables, and programmatic config."""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_file: Optional path to configuration file (YAML, JSON, or TOML)
        """
        self.logger = get_logger("vector_store_config")
        self.config_file = config_file
        self._config: Dict[str, Any] = {}
        self._method_configs: Dict[str, Dict[str, Any]] = {}

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file, environment variables, and defaults."""
        # Load from config file if provided
        if self.config_file:
            self._load_from_file(self.config_file)

        # Load from environment variables
        self._load_from_env()

        # Set defaults
        self._set_defaults()

    def _load_from_file(self, file_path: str) -> None:
        """Load configuration from file."""
        file_path = Path(file_path)
        if not file_path.exists():
            self.logger.warning(f"Config file not found: {file_path}")
            return

        try:
            if file_path.suffix in [".yaml", ".yml"]:
                import yaml

                with open(file_path, "r") as f:
                    config_data = yaml.safe_load(f)
                    if config_data and "vector_store" in config_data:
                        self._config.update(config_data["vector_store"])
            elif file_path.suffix == ".json":
                import json

                with open(file_path, "r") as f:
                    config_data = json.load(f)
                    if config_data and "vector_store" in config_data:
                        self._config.update(config_data["vector_store"])
            elif file_path.suffix == ".toml":
                # stdlib since 3.11, the supported floor. The tomli backport was
                # never a declared dependency, so .toml files were ignored on 3.11+.
                import tomllib

                with open(file_path, "rb") as f:
                    config_data = tomllib.load(f)
                    if config_data and "vector_store" in config_data:
                        self._config.update(config_data["vector_store"])
        except Exception as e:
            self.logger.error(f"Failed to load config file: {e}")

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        env_mappings = {
            "VECTOR_STORE_DEFAULT_BACKEND": "default_backend",
            "VECTOR_STORE_DIMENSION": "dimension",
            "VECTOR_STORE_BATCH_SIZE": "batch_size",
            "VECTOR_STORE_INDEX_TYPE": "index_type",
            "VECTOR_STORE_METRIC": "metric",
            "VECTOR_STORE_ENABLE_HYBRID_SEARCH": "enable_hybrid_search",
            "VECTOR_STORE_NAMESPACE": "default_namespace",
            "VECTOR_STORE_FAISS_INDEX_TYPE": "faiss_index_type",
            "VECTOR_STORE_WEAVIATE_URL": "weaviate_url",
            "VECTOR_STORE_QDRANT_URL": "qdrant_url",
            "VECTOR_STORE_MILVUS_HOST": "milvus_host",
            "VECTOR_STORE_MILVUS_PORT": "milvus_port",
            "VECTOR_STORE_SQLITE_PATH": "sqlite_path",
        }

        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string values to appropriate types
                if config_key in ["dimension", "batch_size", "milvus_port"]:
                    try:
                        self._config[config_key] = int(value)
                    except ValueError:
                        self.logger.warning(
                            f"Invalid integer value for {env_var}: {value}"
                        )
                elif config_key in ["enable_hybrid_search"]:
                    self._config[config_key] = value.lower() in [
                        "true",
                        "1",
                        "yes",
                        "on",
                    ]
                else:
                    self._config[config_key] = value

    def _set_defaults(self) -> None:
        """Set default configuration values."""
        defaults = {
            "default_backend": "faiss",
            "dimension": 768,
            "batch_size": 1000,
            "index_type": "flat",
            "metric": "cosine",
            "enable_hybrid_search": True,
            "default_namespace": "default",
            "faiss_index_type": "flat",
        }

        for key, default_value in defaults.items():
            if key not in self._config:
                self._config[key] = default_value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value

    def update(self, config: Dict[str, Any]) -> None:
        """
        Update configuration with dictionary.

        Args:
            config: Configuration dictionary
        """
        self._config.update(config)

    def get_method_config(self, method_name: str) -> Dict[str, Any]:
        """
        Get method-specific configuration.

        Args:
            method_name: Method name

        Returns:
            Method configuration dictionary
        """
        return self._method_configs.get(method_name, {}).copy()

    def set_method_config(self, method_name: str, config: Dict[str, Any]) -> None:
        """
        Set method-specific configuration.

        Args:
            method_name: Method name
            config: Method configuration dictionary
        """
        self._method_configs[method_name] = config.copy()

    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration.

        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()

    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._config.clear()
        self._method_configs.clear()
        self._set_defaults()


# Global configuration instance
vector_store_config = VectorStoreConfig()
