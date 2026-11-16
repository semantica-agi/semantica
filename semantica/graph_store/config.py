"""
Configuration Management Module for Graph Store

This module provides centralized configuration management for graph store operations,
supporting multiple configuration sources including environment variables, config files,
and programmatic configuration.

Supported Configuration Sources:
    - Environment variables: GRAPH_STORE_DEFAULT_BACKEND,
      GRAPH_STORE_NEO4J_URI, GRAPH_STORE_FALKORDB_HOST, etc.
    - Config files: YAML, JSON, TOML formats
    - Programmatic: Python API for setting graph store configurations

Algorithms Used:
    - Environment Variable Parsing: OS-level environment variable access
    - YAML Parsing: YAML parser for configuration file loading
    - JSON Parsing: JSON parser for configuration file loading
    - TOML Parsing: TOML parser for configuration file loading
    - Fallback Chain: Priority-based configuration resolution
    - Dictionary Merging: Deep merge algorithms for configuration updates

Key Features:
    - Environment variable support for graph store parameters
    - Config file support (YAML, JSON, TOML formats)
    - Programmatic configuration via Python API
    - Method-specific configuration management
    - Automatic fallback chain (config file -> environment -> defaults)
    - Global config instance for easy access

Main Classes:
    - GraphStoreConfig: Main configuration manager class for graph store module

Example Usage:
    >>> from semantica.graph_store.config import graph_store_config
    >>> default_backend = graph_store_config.get("default_backend", default="neo4j")
    >>> graph_store_config.set("default_backend", "falkordb")
    >>> method_config = graph_store_config.get_method_config("create_node")
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.logging import get_logger


class GraphStoreConfig:
    """
    Configuration manager for graph store module.

    Supports .env files, environment variables, and programmatic config.
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_file: Optional path to configuration file (YAML, JSON, or TOML)
        """
        self.logger = get_logger("graph_store_config")
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
                    if config_data and "graph_store" in config_data:
                        self._config.update(config_data["graph_store"])
            elif file_path.suffix == ".json":
                import json

                with open(file_path, "r") as f:
                    config_data = json.load(f)
                    if config_data and "graph_store" in config_data:
                        self._config.update(config_data["graph_store"])
            elif file_path.suffix == ".toml":
                # stdlib since 3.11, the supported floor. The tomli backport was
                # never a declared dependency, so .toml files were ignored on 3.11+.
                import tomllib

                with open(file_path, "rb") as f:
                    config_data = tomllib.load(f)
                    if config_data and "graph_store" in config_data:
                        self._config.update(config_data["graph_store"])
        except Exception as e:
            self.logger.error(f"Failed to load config file: {e}")

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        env_mappings = {
            # General settings
            "GRAPH_STORE_DEFAULT_BACKEND": "default_backend",
            "GRAPH_STORE_BATCH_SIZE": "batch_size",
            "GRAPH_STORE_TIMEOUT": "timeout",
            "GRAPH_STORE_MAX_RETRIES": "max_retries",
            # Neo4j settings
            "GRAPH_STORE_NEO4J_URI": "neo4j_uri",
            "GRAPH_STORE_NEO4J_USER": "neo4j_user",
            "GRAPH_STORE_NEO4J_PASSWORD": "neo4j_password",
            "GRAPH_STORE_NEO4J_DATABASE": "neo4j_database",
            "GRAPH_STORE_NEO4J_ENCRYPTED": "neo4j_encrypted",
            # FalkorDB settings
            "GRAPH_STORE_FALKORDB_HOST": "falkordb_host",
            "GRAPH_STORE_FALKORDB_PORT": "falkordb_port",
            "GRAPH_STORE_FALKORDB_PASSWORD": "falkordb_password",
            "GRAPH_STORE_FALKORDB_GRAPH_NAME": "falkordb_graph_name",
            # Amazon Neptune settings
            "GRAPH_STORE_NEPTUNE_ENDPOINT": "neptune_endpoint",
            "GRAPH_STORE_NEPTUNE_PORT": "neptune_port",
            "GRAPH_STORE_NEPTUNE_REGION": "neptune_region",
            "GRAPH_STORE_NEPTUNE_IAM_AUTH": "neptune_iam_auth",
            "GRAPH_STORE_NEPTUNE_USE_SSL": "neptune_use_ssl",
            "AWS_ACCESS_KEY_ID": "neptune_access_key",
            "AWS_SECRET_ACCESS_KEY": "neptune_secret_key",
            "AWS_SESSION_TOKEN": "neptune_session_token",
            # Apache AGE settings
            "GRAPH_STORE_AGE_CONNECTION_STRING": "age_connection_string",
            "GRAPH_STORE_AGE_GRAPH_NAME": "age_graph_name",
        }

        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string values to appropriate types
                if config_key in [
                    "batch_size",
                    "timeout",
                    "max_retries",
                    "falkordb_port",
                    "neptune_port",
                ]:
                    try:
                        self._config[config_key] = int(value)
                    except ValueError:
                        self.logger.warning(
                            f"Invalid integer value for {env_var}: {value}"
                        )
                elif config_key in [
                    "neo4j_encrypted",
                    "neptune_iam_auth",
                    "neptune_use_ssl",
                ]:
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
            # General defaults
            "default_backend": "neo4j",
            "batch_size": 1000,
            "timeout": 30,
            "max_retries": 3,
            # Neo4j defaults
            "neo4j_uri": "bolt://localhost:7687",
            "neo4j_user": "neo4j",
            "neo4j_password": "password",
            "neo4j_database": "neo4j",
            "neo4j_encrypted": False,
            # FalkorDB defaults
            "falkordb_host": "localhost",
            "falkordb_port": 6379,
            "falkordb_password": None,
            "falkordb_graph_name": "default",
            # Amazon Neptune defaults
            "neptune_endpoint": None,
            "neptune_port": 8182,
            "neptune_region": None,
            "neptune_iam_auth": True,
            "neptune_use_ssl": True,
            "neptune_access_key": None,
            "neptune_secret_key": None,
            "neptune_session_token": None,
            # Apache AGE defaults
            "age_connection_string": "host=localhost dbname=agedb user=postgres password=postgres",
            "age_graph_name": "semantica",
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

    def get_neo4j_config(self) -> Dict[str, Any]:
        """
        Get Neo4j-specific configuration.

        Returns:
            Neo4j configuration dictionary
        """
        return {
            "uri": self._config.get("neo4j_uri"),
            "user": self._config.get("neo4j_user"),
            "password": self._config.get("neo4j_password"),
            "database": self._config.get("neo4j_database"),
            "encrypted": self._config.get("neo4j_encrypted"),
        }

    def get_falkordb_config(self) -> Dict[str, Any]:
        """
        Get FalkorDB-specific configuration.

        Returns:
            FalkorDB configuration dictionary
        """
        return {
            "host": self._config.get("falkordb_host"),
            "port": self._config.get("falkordb_port"),
            "password": self._config.get("falkordb_password"),
            "graph_name": self._config.get("falkordb_graph_name"),
        }

    def get_neptune_config(self) -> Dict[str, Any]:
        """
        Get Amazon Neptune-specific configuration.

        Returns:
            Neptune configuration dictionary
        """
        return {
            "endpoint": self._config.get("neptune_endpoint"),
            "port": self._config.get("neptune_port"),
            "region": self._config.get("neptune_region"),
            "iam_auth": self._config.get("neptune_iam_auth"),
            "use_ssl": self._config.get("neptune_use_ssl"),
            "access_key": self._config.get("neptune_access_key"),
            "secret_key": self._config.get("neptune_secret_key"),
            "session_token": self._config.get("neptune_session_token"),
        }

    def get_age_config(self) -> Dict[str, Any]:
        """
        Get Apache AGE-specific configuration.

        Returns:
            Apache AGE configuration dictionary
        """
        return {
            "connection_string": self._config.get("age_connection_string"),
            "graph_name": self._config.get("age_graph_name"),
        }

    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._config.clear()
        self._method_configs.clear()
        self._set_defaults()


# Global configuration instance
graph_store_config = GraphStoreConfig()
