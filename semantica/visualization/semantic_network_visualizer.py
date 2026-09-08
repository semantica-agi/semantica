"""
Semantic Network Visualizer Module

This module provides comprehensive visualization capabilities for semantic networks in the
Semantica framework, including network structure visualizations, node type distributions,
and edge type distributions with support for multiple input formats.

Key Features:
    - Semantic network structure visualizations
    - Node type distribution charts
    - Edge type distribution charts
    - Support for SemanticNetwork dataclass, dictionaries, and semantic models
    - Integration with KGVisualizer for network rendering
    - Interactive and static output formats

Main Classes:
    - SemanticNetworkVisualizer: Main semantic network visualizer coordinator

Example Usage:
    >>> from semantica.visualization import SemanticNetworkVisualizer
    >>> viz = SemanticNetworkVisualizer(color_scheme="vibrant")
    >>> fig = viz.visualize_network(semantic_network, output="interactive")
    >>> viz.visualize_node_types(semantic_network, file_path="node_types.png")
    >>> viz.visualize_edge_types(semantic_network, output="interactive")
    >>> 
    >>> # Works with SemanticNetwork objects, dicts, or semantic models
    >>> viz.visualize_network({"nodes": nodes, "edges": edges}, file_path="network.html")

Author: Semantica Contributors
License: MIT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import plotly.express as px
    import plotly.graph_objects as go
except (ImportError, OSError):
    px = None
    go = None

from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .utils.color_schemes import ColorPalette, ColorScheme
from .utils.export_formats import export_plotly_figure
from .utils.layout_algorithms import ForceDirectedLayout


class SemanticNetworkVisualizer:
    """
    Semantic network visualizer.

    Provides visualization methods for semantic networks.
    """

    def __init__(self, **config):
        """Initialize semantic network visualizer."""
        self.logger = get_logger("semantic_network_visualizer")
        self.config = config
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True
        color_scheme_name = config.get("color_scheme", "vibrant")
        try:
            self.color_scheme = ColorScheme[color_scheme_name.upper()]
        except (KeyError, AttributeError):
            self.color_scheme = ColorScheme.VIBRANT

    def _check_dependencies(self):
        """Check if dependencies are available."""
        if px is None or go is None:
            raise ProcessingError(
                "Plotly is required for semantic network visualization. "
                "Install with: pip install 'semantica[viz]'"
            )

    def visualize_network(
        self,
        semantic_network: Any,
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize semantic network.

        Supports multiple input formats:
        - SemanticNetwork dataclass object
        - Dictionary with 'nodes' and 'edges' keys
        - Semantic model from ontology generator
        - Entities and relationships lists

        Args:
            semantic_network: SemanticNetwork object, dict, or semantic model
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        tracking_id = self.progress_tracker.start_tracking(
            module="visualization",
            submodule="SemanticNetworkVisualizer",
            message="Visualizing semantic network",
        )

        try:
            self.logger.info("Visualizing semantic network")

            # Extract nodes and edges from semantic network
            self.progress_tracker.update_tracking(
                tracking_id, message="Extracting nodes and edges..."
            )
            nodes = []
            edges = []

            # Handle SemanticNetwork dataclass
            if hasattr(semantic_network, "nodes") and hasattr(
                semantic_network, "edges"
            ):
                for node in semantic_network.nodes:
                    nodes.append(
                        {
                            "id": getattr(node, "id", ""),
                            "label": getattr(node, "label", ""),
                            "type": getattr(node, "type", "entity"),
                            "metadata": getattr(node, "metadata", {}) or {},
                            "properties": getattr(node, "properties", {}) or {},
                        }
                    )

                for edge in semantic_network.edges:
                    edges.append(
                        {
                            "source": getattr(edge, "source", ""),
                            "target": getattr(edge, "target", ""),
                            "label": getattr(edge, "label", ""),
                            "type": getattr(edge, "label", ""),
                            "metadata": getattr(edge, "metadata", {}) or {},
                            "properties": getattr(edge, "properties", {}) or {},
                        }
                    )

            # Handle dictionary format
            elif isinstance(semantic_network, dict):
                # Check if it's a semantic model from ontology generator
                if "semantic_network" in semantic_network:
                    semantic_network = semantic_network["semantic_network"]

                # Extract nodes
                network_nodes = semantic_network.get("nodes", [])
                for node in network_nodes:
                    if isinstance(node, dict):
                        nodes.append(
                            {
                                "id": node.get("id", node.get("uri", "")),
                                "label": node.get("label", node.get("name", "")),
                                "type": node.get("type", node.get("class", "entity")),
                                "metadata": node.get("metadata", {}),
                                "properties": node.get("properties", {}),
                            }
                        )
                    elif hasattr(node, "id"):
                        nodes.append(
                            {
                                "id": getattr(node, "id", ""),
                                "label": getattr(node, "label", ""),
                                "type": getattr(node, "type", "entity"),
                                "metadata": getattr(node, "metadata", {}) or {},
                                "properties": getattr(node, "properties", {}) or {},
                            }
                        )

                # Extract edges
                network_edges = semantic_network.get(
                    "edges", semantic_network.get("relationships", [])
                )
                for edge in network_edges:
                    if isinstance(edge, dict):
                        edges.append(
                            {
                                "source": edge.get("source", edge.get("subject", "")),
                                "target": edge.get("target", edge.get("object", "")),
                                "label": edge.get(
                                    "label", edge.get("predicate", edge.get("type", ""))
                                ),
                                "type": edge.get("type", edge.get("predicate", "")),
                                "metadata": edge.get("metadata", {}),
                                "properties": edge.get("properties", {}),
                            }
                        )
                    elif hasattr(edge, "source"):
                        edges.append(
                            {
                                "source": getattr(edge, "source", ""),
                                "target": getattr(edge, "target", ""),
                                "label": getattr(edge, "label", ""),
                                "type": getattr(edge, "label", ""),
                                "metadata": getattr(edge, "metadata", {}) or {},
                                "properties": getattr(edge, "properties", {}) or {},
                            }
                        )

            # Handle entities/relationships format (for semantic models)
            elif isinstance(semantic_network, (list, tuple)):
                # Assume it's a list of entities/relationships
                for item in semantic_network:
                    if isinstance(item, dict):
                        if "source" in item or "subject" in item:
                            edges.append(
                                {
                                    "source": item.get(
                                        "source", item.get("subject", "")
                                    ),
                                    "target": item.get(
                                        "target", item.get("object", "")
                                    ),
                                    "label": item.get(
                                        "label",
                                        item.get("predicate", item.get("type", "")),
                                    ),
                                    "type": item.get("type", ""),
                                    "metadata": item.get("metadata", {}),
                                }
                            )
                        else:
                            nodes.append(
                                {
                                    "id": item.get("id", item.get("uri", "")),
                                    "label": item.get("label", item.get("name", "")),
                                    "type": item.get("type", "entity"),
                                    "metadata": item.get("metadata", {}),
                                }
                            )

            if not nodes and not edges:
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="failed",
                    message="Could not extract nodes and edges from semantic network",
                )
                raise ProcessingError(
                    "Could not extract nodes and edges from semantic network. "
                    "Please provide a SemanticNetwork object, dict with 'nodes'/'edges', or semantic model."
                )

            # Use KG visualizer for network visualization
            self.progress_tracker.update_tracking(
                tracking_id, message="Generating visualization..."
            )
            from .kg_visualizer import KGVisualizer

            graph = {"entities": nodes, "relationships": edges}
            kg_viz = KGVisualizer(**self.config)
            
            # Default to Kamada-Kawai layout if not specified as it often produces better results for semantic networks
            if "algorithm" not in options:
                options["algorithm"] = "kamada_kawai"
                
            result = kg_viz.visualize_network(graph, output, file_path, **options)

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Visualization generated: {len(nodes)} nodes, {len(edges)} edges",
            )
            return result
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def visualize_node_types(
        self,
        semantic_network: Any,
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize node type distribution.

        Args:
            semantic_network: SemanticNetwork object
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing semantic network node types")

        # Extract nodes
        nodes = []
        if hasattr(semantic_network, "nodes"):
            nodes = semantic_network.nodes
        elif isinstance(semantic_network, dict):
            nodes = semantic_network.get("nodes", [])

        # Count node types
        type_counts = {}
        for node in nodes:
            node_type = (
                node.type if hasattr(node, "type") else node.get("type", "Unknown")
            )
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

        fig = px.bar(
            x=list(type_counts.keys()),
            y=list(type_counts.values()),
            labels={"x": "Node Type", "y": "Count"},
            title="Semantic Network Node Type Distribution",
        )

        if file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )

        # Always return the figure to allow interactive preview in notebooks
        return fig

    def visualize_edge_types(
        self,
        semantic_network: Any,
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize edge type distribution.

        Args:
            semantic_network: SemanticNetwork object
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing semantic network edge types")

        # Extract edges
        edges = []
        if hasattr(semantic_network, "edges"):
            edges = semantic_network.edges
        elif isinstance(semantic_network, dict):
            edges = semantic_network.get("edges", [])

        # Count edge types
        type_counts = {}
        for edge in edges:
            edge_type = (
                edge.label if hasattr(edge, "label") else edge.get("label", "Unknown")
            )
            type_counts[edge_type] = type_counts.get(edge_type, 0) + 1

        fig = px.bar(
            x=list(type_counts.keys()),
            y=list(type_counts.values()),
            labels={"x": "Edge Type", "y": "Count"},
            title="Semantic Network Edge Type Distribution",
        )

        if file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )

        # Always return the figure to allow interactive preview in notebooks
        return fig
