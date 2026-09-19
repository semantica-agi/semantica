"""
Graph Analytics Visualizer Module

This module provides comprehensive visualization capabilities for graph analytics in the
Semantica framework, including centrality rankings, community structures, connectivity
analysis, degree distributions, and comprehensive metrics dashboards.

Key Features:
    - Centrality ranking visualizations (degree, betweenness, closeness, eigenvector)
    - Community structure visualizations
    - Connectivity analysis with component visualization
    - Degree distribution histograms
    - Comprehensive metrics dashboards
    - Centrality comparison across multiple measures
    - Interactive and static output formats

Main Classes:
    - AnalyticsVisualizer: Main graph analytics visualizer coordinator

Example Usage:
    >>> from semantica.visualization import AnalyticsVisualizer
    >>> viz = AnalyticsVisualizer(color_scheme="default")
    >>> fig = viz.visualize_centrality_rankings(centrality, centrality_type="degree", top_n=20)
    >>> viz.visualize_community_structure(graph, communities, file_path="communities.html")
    >>> viz.visualize_connectivity(connectivity, output="interactive")
    >>> viz.visualize_degree_distribution(graph, file_path="degree_dist.png")
    >>> viz.visualize_metrics_dashboard(metrics, output="interactive")
    >>> viz.visualize_centrality_comparison(centrality_results, top_n=10)

Author: Semantica Contributors
License: MIT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import numpy as np
except (ImportError, OSError):
    np = None

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
from .utils.export_formats import export_plotly_figure


class AnalyticsVisualizer:
    """
    Graph analytics visualizer.

    Provides visualization methods for graph analytics including:
    - Centrality rankings
    - Community structures
    - Connectivity analysis
    - Graph metrics dashboards
    """

    def __init__(self, **config):
        """Initialize analytics visualizer."""
        self.logger = get_logger("analytics_visualizer")
        self.config = config
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True
        color_scheme_name = config.get("color_scheme", "default")
        try:
            self.color_scheme = ColorScheme[color_scheme_name.upper()]
        except (KeyError, AttributeError):
            self.color_scheme = ColorScheme.DEFAULT

    def _check_dependencies(self):
        """Check if dependencies are available."""
        if px is None or go is None:
            raise ProcessingError(
                "Plotly is required for analytics visualization. "
                "Install with: pip install 'semantica[viz]'"
            )
        if np is None:
            raise ProcessingError(
                "NumPy is required for analytics visualization. "
                "Install with: pip install numpy"
            )

    def visualize_centrality(self, *args, **kwargs):
        """Alias for visualize_centrality_rankings."""
        return self.visualize_centrality_rankings(*args, **kwargs)

    def visualize_centrality_rankings(
        self,
        centrality: Dict[str, Any],
        centrality_type: str = "degree",
        top_n: int = 20,
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize centrality rankings.

        Args:
            centrality: Centrality calculation results
            centrality_type: Type of centrality
            top_n: Number of top nodes to show
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        tracking_id = self.progress_tracker.start_tracking(
            module="visualization",
            submodule="AnalyticsVisualizer",
            message=f"Visualizing {centrality_type} centrality rankings",
        )

        try:
            self.logger.info(f"Visualizing {centrality_type} centrality rankings")

            # Get rankings
            self.progress_tracker.update_tracking(
                tracking_id, message="Processing centrality data..."
            )
            rankings = centrality.get("rankings", [])
            if not rankings:
                # Try to get from centrality scores
                centrality_scores = centrality.get("centrality", {})
                rankings = [
                    {"node": node, "score": score}
                    for node, score in centrality_scores.items()
                ]
                rankings.sort(key=lambda x: x["score"], reverse=True)

            # Get top N
            top_rankings = rankings[:top_n]

            nodes = [r["node"] for r in top_rankings]
            scores = [r["score"] for r in top_rankings]

            self.progress_tracker.update_tracking(
                tracking_id, message="Generating visualization..."
            )
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=nodes,
                        y=scores,
                        marker_color="lightblue",
                        text=[f"{s:.3f}" for s in scores],
                        textposition="auto",
                    )
                ]
            )

            fig.update_layout(
                title=f"Top {top_n} Nodes by {centrality_type.capitalize()} Centrality",
                xaxis_title="Node",
                yaxis_title="Centrality Score",
                xaxis={"tickangle": -45},
                width=1000,
                height=600,
            )

            if output == "interactive":
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Centrality rankings visualization generated: top {top_n} nodes",
                )
                return fig
            elif file_path:
                export_plotly_figure(
                    fig, file_path, format=output if output != "interactive" else "html"
                )
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Centrality rankings saved to {file_path}",
                )
                return None
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def visualize_community_structure(
        self,
        graph: Dict[str, Any],
        communities: Dict[str, Any],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize community structure in graph.

        Args:
            graph: Knowledge graph dictionary
            communities: Community detection results
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing community structure")

        # Use KG visualizer for community visualization
        from .kg_visualizer import KGVisualizer

        kg_viz = KGVisualizer(**self.config)
        return kg_viz.visualize_communities(
            graph, communities, output, file_path, **options
        )

    def visualize_connectivity(
        self,
        connectivity: Dict[str, Any],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize connectivity analysis results.

        Args:
            connectivity: Connectivity analysis results
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing connectivity analysis")

        # Extract metrics
        is_connected = connectivity.get("is_connected", False)
        num_components = connectivity.get("num_components", 1)
        component_sizes = connectivity.get("component_sizes", [])

        # Create visualization
        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=("Connectivity Status", "Component Sizes"),
            specs=[[{"type": "indicator"}, {"type": "bar"}]],
        )

        # Connectivity status
        status_text = "Connected" if is_connected else "Disconnected"
        status_color = "green" if is_connected else "red"

        fig.add_trace(
            go.Indicator(
                mode="number+delta",
                value=num_components,
                title={"text": f"Components<br>{status_text}"},
                delta={"reference": 1, "valueformat": ".0f"},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=1,
            col=1,
        )

        # Component sizes
        if component_sizes:
            fig.add_trace(
                go.Bar(
                    x=[f"Component {i+1}" for i in range(len(component_sizes))],
                    y=component_sizes,
                    marker_color="lightgreen",
                    text=component_sizes,
                    textposition="auto",
                ),
                row=1,
                col=2,
            )

        fig.update_layout(title="Connectivity Analysis")

        if output == "interactive":
            return fig
        elif file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )
            return None

    def visualize_degree_distribution(
        self,
        graph: Dict[str, Any],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize node degree distribution.

        Args:
            graph: Knowledge graph dictionary
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing degree distribution")

        # Calculate degrees
        relationships = graph.get("relationships", [])
        entities = graph.get("entities", [])

        degrees = {}
        for entity in entities:
            entity_id = entity.get("id") or entity.get("entity_id", "")
            degrees[entity_id] = 0

        for rel in relationships:
            source_id = rel.get("source") or rel.get("subject", "")
            target_id = rel.get("target") or rel.get("object", "")

            if source_id in degrees:
                degrees[source_id] += 1
            if target_id in degrees:
                degrees[target_id] += 1

        degree_values = list(degrees.values())

        fig = go.Figure(
            data=[
                go.Histogram(
                    x=degree_values,
                    nbinsx=30,
                    marker_color="lightblue",
                    marker_line_color="darkblue",
                    marker_line_width=1,
                )
            ]
        )

        fig.update_layout(
            title="Node Degree Distribution",
            xaxis_title="Degree",
            yaxis_title="Frequency",
            width=800,
            height=600,
        )

        if output == "interactive":
            return fig
        elif file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )
            return None

    def visualize_metrics_dashboard(
        self,
        metrics: Dict[str, Any],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize comprehensive graph metrics dashboard.

        Args:
            metrics: Graph metrics dictionary
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing graph metrics dashboard")

        # Extract key metrics
        num_nodes = metrics.get("num_nodes", metrics.get("total_nodes", 0))
        num_edges = metrics.get("num_edges", metrics.get("total_edges", 0))
        density = metrics.get("density", 0.0)
        avg_path_length = metrics.get(
            "avg_path_length", metrics.get("average_path_length", 0.0)
        )
        diameter = metrics.get("diameter", 0)

        # Create dashboard
        fig = make_subplots(
            rows=2,
            cols=3,
            subplot_titles=(
                "Nodes",
                "Edges",
                "Density",
                "Avg Path Length",
                "Diameter",
                "Summary",
            ),
            specs=[
                [{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}],
                [{"type": "indicator"}, {"type": "indicator"}, {"type": "bar"}],
            ],
        )

        # Nodes
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=num_nodes,
                title={"text": "Nodes"},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=1,
            col=1,
        )

        # Edges
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=num_edges,
                title={"text": "Edges"},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=1,
            col=2,
        )

        # Density
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=density * 100,
                title={"text": "Density (%)"},
                gauge={"axis": {"range": [None, 100]}, "bar": {"color": "darkblue"}},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=1,
            col=3,
        )

        # Avg path length
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=avg_path_length,
                title={"text": "Avg Path Length"},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=2,
            col=1,
        )

        # Diameter
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=diameter,
                title={"text": "Diameter"},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=2,
            col=2,
        )

        # Summary bar chart
        summary_metrics = {
            "Nodes": num_nodes,
            "Edges": num_edges,
            "Density": density * 100,
        }

        fig.add_trace(
            go.Bar(
                x=list(summary_metrics.keys()),
                y=list(summary_metrics.values()),
                marker_color="lightblue",
            ),
            row=2,
            col=3,
        )

        fig.update_layout(title="Graph Metrics Dashboard", height=800)

        if output == "interactive":
            return fig
        elif file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )
            return None

    def visualize_centrality_comparison(
        self,
        centrality_results: Dict[str, Dict[str, Any]],
        top_n: int = 10,
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize comparison of multiple centrality measures.

        Args:
            centrality_results: Dictionary of centrality type to results
            top_n: Number of top nodes to compare
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing centrality comparison")

        # Extract top nodes for each centrality type
        centrality_types = list(centrality_results.keys())
        all_top_nodes = set()

        for cent_type, results in centrality_results.items():
            rankings = results.get("rankings", [])
            top_nodes = [r["node"] for r in rankings[:top_n]]
            all_top_nodes.update(top_nodes)

        all_top_nodes = sorted(list(all_top_nodes))[:top_n]

        # Build comparison data
        comparison_data = {cent_type: [] for cent_type in centrality_types}

        for node in all_top_nodes:
            for cent_type, results in centrality_results.items():
                centrality_scores = results.get("centrality", {})
                score = centrality_scores.get(node, 0.0)

                # Try rankings if centrality dict not available
                if score == 0.0:
                    rankings = results.get("rankings", [])
                    for r in rankings:
                        if r.get("node") == node:
                            score = r.get("score", 0.0)
                            break

                comparison_data[cent_type].append(score)

        # Create grouped bar chart
        fig = go.Figure()

        colors = ColorPalette.get_colors(self.color_scheme, len(centrality_types))

        for i, cent_type in enumerate(centrality_types):
            fig.add_trace(
                go.Bar(
                    name=cent_type.capitalize(),
                    x=all_top_nodes,
                    y=comparison_data[cent_type],
                    marker_color=colors[i],
                )
            )

        fig.update_layout(
            title=f"Top {top_n} Nodes - Centrality Comparison",
            xaxis_title="Node",
            yaxis_title="Centrality Score",
            barmode="group",
            xaxis={"tickangle": -45},
            width=1200,
            height=600,
        )

        if output == "interactive":
            return fig
        elif file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )
            return None
