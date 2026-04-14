"""
Knowledge Graph Visualizer Module

This module provides comprehensive visualization capabilities for knowledge graphs in the
Semantica framework, including interactive network graphs, community visualizations,
centrality-based node sizing, entity/relationship distributions, and relationship matrices.

Key Features:
    - Interactive network graph visualizations
    - Community detection visualization with color coding
    - Centrality-based node sizing and coloring
    - Entity type distribution charts
    - Relationship frequency matrices
    - Multiple layout algorithms (force-directed, hierarchical, circular)
    - Customizable color schemes and node/edge styling

Main Classes:
    - KGVisualizer: Main knowledge graph visualizer coordinator

Example Usage:
    >>> from semantica.visualization import KGVisualizer
    >>> viz = KGVisualizer(layout="force", color_scheme="vibrant")
    >>> fig = viz.visualize_network(graph, output="interactive")
    >>> viz.visualize_communities(graph, communities, file_path="communities.html")
    >>> viz.visualize_centrality(graph, centrality, centrality_type="degree")
    >>> viz.visualize_entity_types(graph, file_path="entity_types.png")
    >>> viz.visualize_relationship_matrix(graph, output="interactive")

Author: Semantica Contributors
License: MIT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
except (ImportError, OSError):
    mpatches = None
    plt = None

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except (ImportError, OSError):
    px = None
    go = None
    make_subplots = None

from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .utils.color_schemes import ColorPalette, ColorScheme
from .utils.export_formats import (
    export_matplotlib_figure,
    export_plotly_figure,
    save_html,
)
from .utils.layout_algorithms import (
    CircularLayout,
    ForceDirectedLayout,
    HierarchicalLayout,
)


class KGVisualizer:
    """
    Knowledge graph visualizer.

    Provides various visualization methods for knowledge graphs including:
    - Interactive network graphs
    - Community visualizations
    - Centrality visualizations
    - Entity/relationship distribution charts
    """

    def __init__(self, **config):
        """
        Initialize knowledge graph visualizer.

        Args:
            **config: Configuration options:
                - layout: Layout algorithm ("force", "hierarchical", "circular")
                - color_scheme: Color scheme name
                - node_size: Base node size
                - edge_width: Edge width
        """
        self.logger = get_logger("kg_visualizer")
        self.config = config
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.layout_type = config.get("layout", "force")
        color_scheme_name = config.get("color_scheme", "default")
        try:
            self.color_scheme = ColorScheme[color_scheme_name.upper()]
        except (KeyError, AttributeError):
            self.color_scheme = ColorScheme.DEFAULT
        self.node_size = config.get("node_size", 10)
        self.edge_width = config.get("edge_width", 1)

        # Initialize layout algorithms
        self.force_layout = ForceDirectedLayout(**config)
        self.hierarchical_layout = HierarchicalLayout(**config)
        self.circular_layout = CircularLayout(**config)

    def _check_dependencies(self):
        """Check if dependencies are available."""
        if px is None or go is None:
            raise ProcessingError(
                "Plotly is required for KG visualization. "
                "Install with: pip install plotly"
            )

    def _normalize_graph(self, graph: Any) -> Dict[str, Any]:
        """
        Normalize graph input to the expected dict format.

        Accepts either:
        - A dict with "entities" and "relationships" keys (canonical format)
        - Any object that exposes .entities and .relationships attributes
          (e.g. a KnowledgeGraph dataclass returned by GraphBuilder.build())

        Returns:
            Dict with "entities", "relationships", and "metadata" keys.
        """
        if isinstance(graph, dict):
            return graph

        # Duck-type: accept any object with .entities / .relationships
        entities = getattr(graph, "entities", None)
        relationships = getattr(graph, "relationships", None)
        if entities is None and relationships is None:
            raise ProcessingError(
                f"Cannot visualize object of type '{type(graph).__name__}': "
                "expected a dict with 'entities'/'relationships' keys, or an object "
                "with .entities and .relationships attributes."
            )
        return {
            "entities": list(entities) if entities is not None else [],
            "relationships": list(relationships) if relationships is not None else [],
            "metadata": dict(getattr(graph, "metadata", None) or {}),
        }

    def visualize_network(
        self,
        graph: Union[Dict[str, Any], Any],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        node_color_by: str = "type",
        node_size_by: Optional[str] = None,
        hover_data: Optional[List[str]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize knowledge graph as interactive network.

        Implements the 5-step visualization process:
        1. Problem setting: implicit in graph selection
        2. Data analysis: logs graph statistics
        3. Layout: configurable via options
        4. Styling: configurable node color/size mappings
        5. Interaction: rich hover data and zoom capabilities

        Args:
            graph: Knowledge graph — either a dict with "entities"/"relationships"
                keys, or any object exposing .entities and .relationships attributes
                (e.g. the result of GraphBuilder.build())
            output: Output type ("interactive", "html", "png", "svg")
            file_path: Output file path (required for non-interactive)
            node_color_by: Property to map to node color (default: "type")
            node_size_by: Property to map to node size (default: fixed)
            hover_data: List of properties to show in hover tooltip
            **options: Additional visualization options

        Returns:
            Plotly figure (if interactive) or None
        """
        self._check_dependencies()
        graph = self._normalize_graph(graph)
        tracking_id = self.progress_tracker.start_tracking(
            module="visualization",
            submodule="KGVisualizer",
            message="Visualizing knowledge graph network",
        )

        try:
            self.logger.info("Visualizing knowledge graph network")

            # Extract entities and relationships
            self.progress_tracker.update_tracking(
                tracking_id, message="Extracting entities and relationships..."
            )
            entities = graph.get("entities", [])
            relationships = graph.get("relationships", [])

            if not entities:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message="No entities found in graph"
                )
                raise ProcessingError("No entities found in graph")

            # Step 2: Data Analysis - Understand data structure
            nodes = self._extract_nodes(entities)
            edges = self._extract_edges(relationships, entities)
            
            num_nodes = len(nodes)
            num_edges = len(edges)
            entity_types = set(n.get("type", "unknown") for n in nodes)
            
            self.logger.info(f"Graph Structure Analysis: {num_nodes} nodes, {num_edges} edges")
            self.logger.info(f"Entity Types: {', '.join(sorted(entity_types))}")

            # Build node and edge lists
            self.progress_tracker.update_tracking(
                tracking_id, message="Building node and edge lists..."
            )

            self.progress_tracker.update_tracking(
                tracking_id, message="Generating visualization..."
            )
            result = self._visualize_network_plotly(
                nodes, 
                edges, 
                output, 
                file_path, 
                node_color_by=node_color_by,
                node_size_by=node_size_by,
                hover_data=hover_data,
                **options
            )

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

    def visualize_communities(
        self,
        graph: Dict[str, Any],
        communities: Dict[str, Any],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize knowledge graph with community coloring.

        Args:
            graph: Knowledge graph dictionary
            communities: Community detection results with node_assignments
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        graph = self._normalize_graph(graph)
        self.logger.info("Visualizing knowledge graph communities")

        entities = graph.get("entities", [])
        relationships = graph.get("relationships", [])

        # Get community assignments
        node_assignments = communities.get("node_assignments", {})
        num_communities = communities.get(
            "num_communities", len(set(node_assignments.values()))
        )

        # Get colors for communities
        community_colors = ColorPalette.get_community_colors(
            num_communities, self.color_scheme
        )

        # Build nodes with community colors
        nodes = self._extract_nodes(entities)
        for node in nodes:
            entity_id = node.get("id", "")
            community_id = node_assignments.get(entity_id, 0)
            node["community"] = community_id
            node["color"] = community_colors[community_id % len(community_colors)]

        edges = self._extract_edges(relationships, entities)

        return self._visualize_network_plotly(
            nodes,
            edges,
            output,
            file_path,
            community_colors=community_colors,
            **options,
        )

    def visualize_centrality(
        self,
        graph: Dict[str, Any],
        centrality: Dict[str, Any],
        centrality_type: str = "degree",
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize knowledge graph with centrality-based node sizing/coloring.

        Args:
            graph: Knowledge graph dictionary
            centrality: Centrality calculation results
            centrality_type: Type of centrality ("degree", "betweenness", "closeness", "eigenvector")
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        graph = self._normalize_graph(graph)
        self.logger.info(
            f"Visualizing knowledge graph with {centrality_type} centrality"
        )

        entities = graph.get("entities", [])
        relationships = graph.get("relationships", [])

        # Get centrality scores
        centrality_scores = centrality.get("centrality", {})
        if not centrality_scores:
            # Try to get from rankings
            rankings = centrality.get("rankings", [])
            centrality_scores = {r["node"]: r["score"] for r in rankings}

        # Build nodes with centrality information
        nodes = self._extract_nodes(entities)
        max_centrality = max(centrality_scores.values()) if centrality_scores else 1.0

        for node in nodes:
            entity_id = node.get("id", "")
            score = centrality_scores.get(entity_id, 0.0)
            node["centrality"] = score
            node["size"] = (
                self.node_size * (1 + 5 * (score / max_centrality))
                if max_centrality > 0
                else self.node_size
            )

        edges = self._extract_edges(relationships, entities)

        return self._visualize_network_plotly(
            nodes, edges, output, file_path, size_by_centrality=True, **options
        )

    def visualize_entity_types(
        self,
        graph: Dict[str, Any],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize entity type distribution.

        Args:
            graph: Knowledge graph dictionary
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        graph = self._normalize_graph(graph)
        self.logger.info("Visualizing entity type distribution")

        entities = graph.get("entities", [])

        # Count entity types
        type_counts = {}
        for entity in entities:
            entity_type = entity.get("type") or entity.get("entity_type") or "Unknown"
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1

        fig = px.bar(
            x=list(type_counts.keys()),
            y=list(type_counts.values()),
            labels={"x": "Entity Type", "y": "Count"},
            title="Entity Type Distribution",
        )

        if file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )

        # Always return the figure to allow interactive preview in notebooks
        return fig

    def visualize_relationship_matrix(
        self,
        graph: Dict[str, Any],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize relationship frequency matrix between entity types.

        Args:
            graph: Knowledge graph dictionary
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        graph = self._normalize_graph(graph)
        self.logger.info("Visualizing relationship matrix")

        entities = graph.get("entities", [])
        relationships = graph.get("relationships", [])

        # Build entity type map
        entity_type_map = {}
        for entity in entities:
            entity_id = entity.get("id") or entity.get("entity_id", "")
            entity_type = entity.get("type") or entity.get("entity_type", "Unknown")
            entity_type_map[entity_id] = entity_type

        # Count relationships between types
        type_matrix = {}
        for rel in relationships:
            source_id = rel.get("source") or rel.get("subject", "")
            target_id = rel.get("target") or rel.get("object", "")

            source_type = entity_type_map.get(source_id, "Unknown")
            target_type = entity_type_map.get(target_id, "Unknown")

            key = (source_type, target_type)
            type_matrix[key] = type_matrix.get(key, 0) + 1

        # Convert to matrix format
        source_types = sorted(set(t[0] for t in type_matrix.keys()))
        target_types = sorted(set(t[1] for t in type_matrix.keys()))

        matrix = np.zeros((len(source_types), len(target_types)))
        for i, source_type in enumerate(source_types):
            for j, target_type in enumerate(target_types):
                matrix[i, j] = type_matrix.get((source_type, target_type), 0)

        fig = go.Figure(
            data=go.Heatmap(
                z=matrix,
                x=target_types,
                y=source_types,
                colorscale="Viridis",
                text=matrix,
                texttemplate="%{text}",
                textfont={"size": 10},
            )
        )
        fig.update_layout(
            title="Relationship Frequency Matrix",
            xaxis_title="Target Entity Type",
            yaxis_title="Source Entity Type",
        )

        if file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )

        # Always return the figure to allow interactive preview in notebooks
        return fig

    def _extract_nodes(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract nodes from entities."""
        nodes = []
        for entity in entities:
            node = {
                "id": entity.get("id") or entity.get("entity_id", ""),
                "label": entity.get("text")
                or entity.get("label")
                or entity.get("name", ""),
                "type": entity.get("type") or entity.get("entity_type", "entity"),
                "metadata": entity.get("metadata", {}),
            }
            nodes.append(node)
        return nodes

    def _extract_edges(
        self, relationships: List[Dict[str, Any]], entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract edges from relationships."""
        edges = []
        entity_map = {e.get("id") or e.get("entity_id", ""): e for e in entities}

        for rel in relationships:
            source_id = rel.get("source") or rel.get("subject", "")
            target_id = rel.get("target") or rel.get("object", "")

            if source_id in entity_map and target_id in entity_map:
                edge = {
                    "source": source_id,
                    "target": target_id,
                    "label": rel.get("type")
                    or rel.get("relationship_type")
                    or rel.get("predicate", ""),
                    "metadata": rel.get("metadata", {}),
                }
                edges.append(edge)

        return edges

    def _visualize_network_plotly(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        output: str,
        file_path: Optional[Path],
        node_color_by: str = "type",
        node_size_by: Optional[str] = None,
        hover_data: Optional[List[str]] = None,
        **options,
    ) -> Optional[Any]:
        """Create Plotly network visualization."""
        # Compute layout
        node_ids = [n["id"] for n in nodes]
        edge_tuples = [(e["source"], e["target"]) for e in edges]

        if self.layout_type == "hierarchical":
            pos = self.hierarchical_layout.compute_layout(
                node_ids, edge_tuples, **options
            )
        elif self.layout_type == "circular":
            pos = self.circular_layout.compute_layout(node_ids, edge_tuples, **options)
        else:
            pos = self.force_layout.compute_layout(node_ids, edge_tuples, **options)

        # Step 4: Styling - Node Colors
        # Priority 1: Explicit color set in node (e.g. from visualize_communities)
        # Priority 2: Mapped property via node_color_by
        
        node_colors = []
        if any("color" in n for n in nodes):
             node_colors = [n.get("color", "#888") for n in nodes if n["id"] in pos]
        else:
            if node_color_by == "type":
                entity_types = list(set(n.get("type", "entity") for n in nodes))
                type_colors = ColorPalette.get_entity_type_colors(
                    entity_types, self.color_scheme
                )
                node_colors = [
                    type_colors.get(n.get("type", "entity"), "#888")
                    for n in nodes
                    if n["id"] in pos
                ]
            else:
                # Custom property mapping
                values = []
                for n in nodes:
                    if n["id"] not in pos: continue
                    val = n.get(node_color_by) or n.get("metadata", {}).get(node_color_by, "Unknown")
                    values.append(str(val))
                
                unique_vals = sorted(list(set(values)))
                colors = ColorPalette.get_colors(self.color_scheme, len(unique_vals))
                val_map = dict(zip(unique_vals, colors))
                
                node_colors = []
                for n in nodes:
                    if n["id"] not in pos: continue
                    val = str(n.get(node_color_by) or n.get("metadata", {}).get(node_color_by, "Unknown"))
                    node_colors.append(val_map.get(val, "#888"))

        # Step 4: Styling - Node Sizes
        # Priority 1: Explicit size set in node (e.g. from visualize_centrality)
        # Priority 2: Mapped property via node_size_by
        
        node_sizes = []
        if any("size" in n for n in nodes) and not node_size_by:
             node_sizes = [n.get("size", self.node_size) for n in nodes if n["id"] in pos]
        elif node_size_by:
            raw_sizes = []
            valid_indices = []
            for i, n in enumerate(nodes):
                if n["id"] not in pos: continue
                val = n.get(node_size_by) or n.get("metadata", {}).get(node_size_by, 0)
                try:
                    s = float(val)
                except (ValueError, TypeError):
                    s = 0
                raw_sizes.append(s)
                valid_indices.append(i)
            
            # Normalize to range [10, 50]
            if raw_sizes and max(raw_sizes) > min(raw_sizes):
                min_s, max_s = min(raw_sizes), max(raw_sizes)
                node_sizes = [10 + 40 * ((s - min_s) / (max_s - min_s)) for s in raw_sizes]
            else:
                node_sizes = [self.node_size] * len(raw_sizes)
        else:
            node_sizes = [self.node_size for n in nodes if n["id"] in pos]

        # Step 5: Interaction - Rich Hover
        node_text = []
        for n in nodes:
            if n["id"] not in pos: continue
            
            # Basic info
            text = f"<b>{n['label']}</b><br>Type: {n.get('type', 'entity')}"
            
            # Additional hover data
            if hover_data:
                for field in hover_data:
                    val = n.get(field) or n.get("metadata", {}).get(field, "N/A")
                    text += f"<br>{field}: {val}"
            
            # Add dynamic styling info if relevant
            if node_size_by:
                val = n.get(node_size_by) or n.get("metadata", {}).get(node_size_by, "N/A")
                text += f"<br>{node_size_by}: {val}"
                
            node_text.append(text)

        # Prepare edge traces
        edge_x = []
        edge_y = []
        
        # Prepare edge label traces and annotations (for arrows)
        edge_label_x = []
        edge_label_y = []
        edge_label_text = []
        annotations = []
        
        # Limit detailed edge rendering for performance if graph is too large
        show_detailed_edges = len(edges) < 500
        
        for edge in edges:
            source_pos = pos.get(edge["source"])
            target_pos = pos.get(edge["target"])
            if source_pos and target_pos:
                x0, y0 = source_pos
                x1, y1 = target_pos
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])
                
                if show_detailed_edges:
                    # Calculate midpoint for label
                    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                    
                    if edge.get("label"):
                        edge_label_x.append(mx)
                        edge_label_y.append(my)
                        edge_label_text.append(edge["label"])
                    
                    # Add arrow annotation
                    # Adjust arrow to point slightly before the node to avoid overlap with node marker
                    # This is approximate; precise calculation requires node size
                    annotations.append(
                        dict(
                            ax=x0, ay=y0, axref='x', ayref='y',
                            x=x1, y=y1, xref='x', yref='y',
                            arrowhead=2, arrowsize=1, arrowwidth=1,
                            arrowcolor="#888", opacity=0.6,
                            standoff=15 # Distance from target node
                        )
                    )

        edge_trace = go.Scatter(
            x=edge_x,
            y=edge_y,
            line=dict(width=self.edge_width, color="#888"),
            hoverinfo="none",
            mode="lines",
            showlegend=False,
            opacity=0.5
        )
        
        traces = [edge_trace]
        
        if show_detailed_edges and edge_label_text:
            edge_label_trace = go.Scatter(
                x=edge_label_x,
                y=edge_label_y,
                mode="text",
                text=edge_label_text,
                textposition="middle center",
                hoverinfo="none",
                textfont=dict(size=8, color="#555"),
                showlegend=False
            )
            traces.append(edge_label_trace)

        # Prepare node traces
        node_x = [pos[n["id"]][0] for n in nodes if n["id"] in pos]
        node_y = [pos[n["id"]][1] for n in nodes if n["id"] in pos]
        node_labels = [n["label"] for n in nodes if n["id"] in pos]

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            hoverinfo="text",
            text=node_labels, # Show labels directly on graph
            hovertext=node_text, # Rich hover text
            textposition="top center",
            textfont=dict(size=10, color="#333"),
            marker=dict(
                size=node_sizes, 
                color=node_colors, 
                line=dict(width=2, color="white"),
                opacity=1.0
            ),
            showlegend=False
        )
        traces.append(node_trace)

        layout_args = dict(
            title="Knowledge Graph Network",
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="white"
        )
        
        if show_detailed_edges:
            layout_args["annotations"] = annotations

        fig = go.Figure(
            data=traces,
            layout=go.Layout(**layout_args),
        )

        if file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )

        # Always return the figure to allow interactive preview in notebooks
        return fig
