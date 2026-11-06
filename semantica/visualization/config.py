"""
Configuration Management Module for Visualization

This module provides centralized configuration management for visualization operations,
supporting multiple configuration sources including environment variables, config files,
and programmatic configuration.

Supported Configuration Sources:
    - Environment variables: VISUALIZATION_DEFAULT_LAYOUT, VISUALIZATION_COLOR_SCHEME, VISUALIZATION_OUTPUT_FORMAT, etc.
    - Config files: YAML, JSON, TOML formats
    - Programmatic: Python API for setting visualization configurations

Algorithms Used:
    - Environment Variable Parsing: OS-level environment variable access
    - YAML Parsing: YAML parser for configuration file loading
    - JSON Parsing: JSON parser for configuration file loading
    - TOML Parsing: TOML parser for configuration file loading
    - Fallback Chain: Priority-based configuration resolution
    - Dictionary Merging: Deep merge algorithms for configuration updates

Key Features:
    - Environment variable support for visualization parameters
    - Config file support (YAML, JSON, TOML formats)
    - Programmatic configuration via Python API
    - Method-specific configuration management
    - Automatic fallback chain (config file -> environment -> defaults)
    - Global config instance for easy access

Main Classes:
    - VisualizationConfig: Main configuration manager class for visualization module

Example Usage:
    >>> from semantica.visualization.config import visualization_config
    >>> default_layout = visualization_config.get("default_layout", default="force")
    >>> visualization_config.set("default_layout", "hierarchical")
    >>> method_config = visualization_config.get_method_config("visualize_kg")
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.logging import get_logger


class VisualizationConfig:
    """Configuration manager for visualization module - supports .env files, environment variables, and programmatic config."""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_file: Optional path to configuration file (YAML, JSON, or TOML)
        """
        self.logger = get_logger("visualization_config")
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
                    if config_data and "visualization" in config_data:
                        self._config.update(config_data["visualization"])
            elif file_path.suffix == ".json":
                import json

                with open(file_path, "r") as f:
                    config_data = json.load(f)
                    if config_data and "visualization" in config_data:
                        self._config.update(config_data["visualization"])
            elif file_path.suffix == ".toml":
                # stdlib since 3.11, the supported floor, so the old tomli -> tomllib
                # fallback is no longer needed.
                import tomllib

                with open(file_path, "rb") as f:
                    config_data = tomllib.load(f)
                    if config_data and "visualization" in config_data:
                        self._config.update(config_data["visualization"])
        except Exception as e:
            self.logger.error(f"Failed to load config file: {e}")

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        env_mappings = {
            "VISUALIZATION_DEFAULT_LAYOUT": "default_layout",
            "VISUALIZATION_COLOR_SCHEME": "color_scheme",
            "VISUALIZATION_OUTPUT_FORMAT": "output_format",
            "VISUALIZATION_NODE_SIZE": "node_size",
            "VISUALIZATION_EDGE_WIDTH": "edge_width",
            "VISUALIZATION_POINT_SIZE": "point_size",
            "VISUALIZATION_DIMENSION_REDUCTION_METHOD": "dimension_reduction_method",
            "VISUALIZATION_UMAP_N_NEIGHBORS": "umap_n_neighbors",
            "VISUALIZATION_TSNE_PERPLEXITY": "tsne_perplexity",
            "VISUALIZATION_PCA_N_COMPONENTS": "pca_n_components",
            "VISUALIZATION_FORCE_LAYOUT_K": "force_layout_k",
            "VISUALIZATION_FORCE_LAYOUT_ITERATIONS": "force_layout_iterations",
            "VISUALIZATION_HIERARCHICAL_VERTICAL_SPACING": "hierarchical_vertical_spacing",
            "VISUALIZATION_CIRCULAR_RADIUS": "circular_radius",
        }

        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string values to appropriate types
                if config_key in [
                    "node_size",
                    "edge_width",
                    "point_size",
                    "umap_n_neighbors",
                    "pca_n_components",
                    "force_layout_iterations",
                ]:
                    try:
                        self._config[config_key] = int(value)
                    except ValueError:
                        self.logger.warning(
                            f"Invalid integer value for {env_var}: {value}"
                        )
                elif config_key in [
                    "tsne_perplexity",
                    "force_layout_k",
                    "hierarchical_vertical_spacing",
                    "circular_radius",
                ]:
                    try:
                        self._config[config_key] = float(value)
                    except ValueError:
                        self.logger.warning(
                            f"Invalid float value for {env_var}: {value}"
                        )
                else:
                    self._config[config_key] = value

    def _set_defaults(self) -> None:
        """Set default configuration values."""
        defaults = {
            "default_layout": "force",
            "color_scheme": "default",
            "output_format": "interactive",
            "node_size": 10,
            "edge_width": 1,
            "point_size": 5,
            "dimension_reduction_method": "umap",
            "umap_n_neighbors": 15,
            "tsne_perplexity": 30.0,
            "pca_n_components": 2,
            "force_layout_k": 1.0,
            "force_layout_iterations": 50,
            "hierarchical_vertical_spacing": 2.0,
            "circular_radius": 1.5,
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
visualization_config = VisualizationConfig()
