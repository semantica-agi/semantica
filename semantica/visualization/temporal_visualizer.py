"""
Temporal Graph Visualizer Module

This module provides comprehensive visualization capabilities for temporal knowledge graphs
in the Semantica framework, including timeline views, temporal pattern visualizations,
snapshot comparisons, version history, and metrics evolution over time.

Key Features:
    - Timeline visualization of entity/relationship changes
    - Temporal pattern detection and visualization
    - Snapshot comparison across time points
    - Version history tree visualization
    - Metrics evolution over time
    - Multi-metric time series visualization
    - Interactive and static output formats

Main Classes:
    - TemporalVisualizer: Main temporal graph visualizer coordinator

Example Usage:
    >>> from semantica.visualization import TemporalVisualizer
    >>> viz = TemporalVisualizer(color_scheme="default")
    >>> fig = viz.visualize_timeline(temporal_data, output="interactive")
    >>> viz.visualize_temporal_patterns(patterns, file_path="patterns.html")
    >>> viz.visualize_snapshot_comparison(snapshots, output="interactive")
    >>> viz.visualize_version_history(version_history, file_path="versions.png")
    >>> viz.visualize_metrics_evolution(metrics_history, timestamps, output="interactive")

Author: Semantica Contributors
License: MIT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
from .utils.layout_algorithms import ForceDirectedLayout


class TemporalVisualizer:
    """
    Temporal graph visualizer.

    Provides visualization methods for temporal graphs including:
    - Timeline views of entity/relationship changes
    - Temporal pattern detection and visualization
    - Snapshot comparison across time points
    - Version history tree visualization
    - Metrics evolution over time
    - Comprehensive temporal dashboards
    - Interactive and static output formats
    """

    def __init__(self, **config):
        """Initialize temporal visualizer."""
        self.logger = get_logger("temporal_visualizer")
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
                "Plotly is required for temporal visualization. "
                "Install with: pip install 'semantica[viz]'"
            )

    def visualize_temporal_dashboard(
        self,
        temporal_kg: Dict[str, Any],
        metrics: Optional[Dict[str, Dict[str, List[Any]]]] = None,
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Create a comprehensive temporal dashboard combining lifelines, network activity, and metrics.

        Args:
            temporal_kg: Temporal knowledge graph data
            metrics: Optional metrics history
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing temporal dashboard")

        if make_subplots is None:
             raise ProcessingError("Plotly subplots required but not available")

        # 1. Prepare Data
        timestamps_map = temporal_kg.get("timestamps", {})
        entities = temporal_kg.get("entities", [])
        entity_map = {e.get("id"): e for e in entities}
        
        # Get all unique time points
        all_times = set()
        for times in timestamps_map.values():
            if isinstance(times, list):
                all_times.update(times)
        sorted_times = sorted(list(all_times))

        # 2. Create Subplots
        rows = 2 if not metrics else 3
        row_heights = [0.5, 0.5] if not metrics else [0.4, 0.3, 0.3]
        specs = [[{"type": "xy"}]] * rows

        fig = make_subplots(
            rows=rows, 
            cols=1, 
            row_heights=row_heights,
            specs=specs,
            subplot_titles=("Entity Lifecycles", "Network Activity" + (" & Metrics" if not metrics else ""), "Metrics Evolution")
        )

        # --- Panel 1: Entity Lifelines (Gantt-like) with Relationship Connections ---
        entity_ids = sorted(timestamps_map.keys())
        colors = ColorPalette.get_colors(self.color_scheme, len(entity_ids))
        
        # 1.1 Draw Entity Lines
        for i, eid in enumerate(entity_ids):
            times = timestamps_map.get(eid, [])
            if not times: continue
            
            # Draw a line for duration
            start, end = min(times), max(times)
            name = entity_map.get(eid, {}).get("name", eid)
            
            fig.add_trace(
                go.Scatter(
                    x=[start, end],
                    y=[name, name],
                    mode="lines+markers",
                    name=name,
                    line=dict(color=colors[i], width=5),
                    marker=dict(size=10),
                    showlegend=False
                ),
                row=1, col=1
            )
            
        # 1.2 Draw Relationship Connections
        # We draw vertical lines connecting entities when they have a relationship and overlap in time
        relationships = temporal_kg.get("relationships", [])
        if relationships:
            rel_x = []
            rel_y = []
            
            for rel in relationships:
                src = rel.get("source")
                tgt = rel.get("target")
                
                # Check if both entities exist in our timeline map
                if src in timestamps_map and tgt in timestamps_map:
                    # Find time overlap
                    src_times = set(timestamps_map[src])
                    tgt_times = set(timestamps_map[tgt])
                    overlap = sorted(list(src_times.intersection(tgt_times)))
                    
                    if overlap:
                        src_name = entity_map.get(src, {}).get("name", src)
                        tgt_name = entity_map.get(tgt, {}).get("name", tgt)
                        
                        for t in overlap:
                            # Add a vertical line segment
                            rel_x.extend([t, t, None])
                            rel_y.extend([src_name, tgt_name, None])
            
            if rel_x:
                fig.add_trace(
                    go.Scatter(
                        x=rel_x,
                        y=rel_y,
                        mode="lines",
                        name="Relationships",
                        line=dict(color="rgba(150, 150, 150, 0.5)", width=1, dash="dot"),
                        hoverinfo="none",
                        showlegend=True
                    ),
                    row=1, col=1
                )

        # --- Panel 2: Network Activity (Stacked Area or Line) ---
        # Calculate counts per timestamp
        entity_counts = []
        # Simple relationship count estimation (assuming rels exist if endpoints exist)
        # This is an approximation for visualization
        rel_counts = [] 
        
        for t in sorted_times:
            # Count active entities
            active_ents = [e for e, times in timestamps_map.items() if t in times]
            entity_counts.append(len(active_ents))
            
            # Count potentially active relationships
            # (If we had strict relationship timestamps, we'd use them. Here we use entity existence)
            active_rels = 0
            for rel in temporal_kg.get("relationships", []):
                src = rel.get("source")
                tgt = rel.get("target")
                # Check if both source and target are active at t
                if (src in timestamps_map and t in timestamps_map[src]) and \
                   (tgt in timestamps_map and t in timestamps_map[tgt]):
                    active_rels += 1
            rel_counts.append(active_rels)

        fig.add_trace(
            go.Scatter(
                x=sorted_times, y=entity_counts,
                mode="lines", name="Active Entities",
                fill='tozeroy', line=dict(color='blue')
            ),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=sorted_times, y=rel_counts,
                mode="lines", name="Active Relationships",
                fill='tonexty', line=dict(color='red')
            ),
            row=2, col=1
        )

        # --- Panel 3: Metrics (Optional) ---
        if metrics:
            # Metrics input: {"MetricName": [val1, val2...], "timestamps": [t1, t2...]} 
            # OR simple dict from previous example: {"MetricName": [values]} (assumes alignment)
            
            # Let's support the simple format from the user's example
            # We assume metrics align with sorted_times or are just passed as is if they have their own timestamps
            
            metric_colors = ColorPalette.get_colors(self.color_scheme, len(metrics))
            
            for i, (m_name, m_data) in enumerate(metrics.items()):
                # Check if m_data is complex or simple list
                if isinstance(m_data, dict) and "values" in m_data:
                    vals = m_data["values"]
                    ts = m_data.get("timestamps", sorted_times)
                else:
                    vals = m_data
                    ts = sorted_times[:len(vals)] # Best effort alignment

                fig.add_trace(
                    go.Scatter(
                        x=ts, y=vals,
                        mode="lines+markers", name=m_name,
                        line=dict(color=metric_colors[i])
                    ),
                    row=3, col=1
                )

        fig.update_layout(
            height=900 if metrics else 600,
            width=1200,
            title_text="Temporal Analysis Dashboard",
            showlegend=True
        )

        if output == "interactive":
            return fig
        elif file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )
            return None


    def visualize_network_evolution(
        self,
        temporal_kg: Dict[str, Any],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize the evolution of the network structure over time using animation.

        Args:
            temporal_kg: Temporal knowledge graph data
            output: Output type ("interactive", "html", etc.)
            file_path: Output file path
            **options: Additional options
                - title: Chart title
                - show_labels: Whether to show node labels

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing network evolution")

        # 1. Prepare Data
        timestamps_map = temporal_kg.get("timestamps", {})
        entities = temporal_kg.get("entities", [])
        relationships = temporal_kg.get("relationships", [])
        entity_map = {e.get("id"): e for e in entities}
        
        # Get all unique time points
        all_times = set()
        for times in timestamps_map.values():
            if isinstance(times, list):
                all_times.update(times)
        sorted_times = sorted(list(all_times))

        if not sorted_times:
            raise ProcessingError("No timestamps found for network evolution.")

        # 2. Compute Global Layout (Stable positions)
        all_node_ids = list(entity_map.keys())
        all_edges = [(r.get("source"), r.get("target")) for r in relationships]
        
        layout_algo = ForceDirectedLayout()
        pos = layout_algo.compute_layout(all_node_ids, all_edges)

        # 3. Create Frames
        frames = []
        max_x, min_x = -1, 1
        max_y, min_y = -1, 1

        if pos:
            xs = [p[0] for p in pos.values()]
            ys = [p[1] for p in pos.values()]
            if xs and ys:
                max_x, min_x = max(xs), min(xs)
                max_y, min_y = max(ys), min(ys)

        # Pad ranges
        range_x = [min_x - 0.1, max_x + 0.1]
        range_y = [min_y - 0.1, max_y + 0.1]

        for t in sorted_times:
            # Active entities
            active_node_ids = [eid for eid, times in timestamps_map.items() if t in times]
            
            # Active relationships (both endpoints must be active)
            active_edges = []
            for rel in relationships:
                src = rel.get("source")
                tgt = rel.get("target")
                if src in active_node_ids and tgt in active_node_ids:
                    # Ideally check relationship timestamps if available, else assume existence if nodes exist
                    active_edges.append(rel)

            # Node Trace
            node_x = []
            node_y = []
            node_text = []
            node_color = []
            
            for nid in active_node_ids:
                if nid in pos:
                    x, y = pos[nid]
                    node_x.append(x)
                    node_y.append(y)
                    ent = entity_map.get(nid, {})
                    node_text.append(ent.get("name", nid))
                    # Simple color by type
                    node_color.append(hash(ent.get("type", "Entity")) % 100)

            node_trace = go.Scatter(
                x=node_x, y=node_y,
                mode="markers+text" if options.get("show_labels", True) else "markers",
                text=node_text,
                textposition="top center",
                marker=dict(size=15, color=node_color, colorscale="Viridis", showscale=False),
                name="Entities"
            )

            # Edge Trace
            edge_x = []
            edge_y = []
            
            for rel in active_edges:
                src = rel.get("source")
                tgt = rel.get("target")
                if src in pos and tgt in pos:
                    x0, y0 = pos[src]
                    x1, y1 = pos[tgt]
                    edge_x.extend([x0, x1, None])
                    edge_y.extend([y0, y1, None])

            edge_trace = go.Scatter(
                x=edge_x, y=edge_y,
                mode="lines",
                line=dict(width=1, color="#888"),
                hoverinfo="none",
                name="Relationships"
            )

            frames.append(go.Frame(
                data=[edge_trace, node_trace],
                name=str(t)
            ))

        # 4. Create Initial Figure (First frame)
        if frames:
            initial_data = frames[0].data
        else:
            initial_data = []

        fig = go.Figure(
            data=initial_data,
            layout=go.Layout(
                title=options.get("title", "Network Evolution"),
                xaxis=dict(range=range_x, showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(range=range_y, showgrid=False, zeroline=False, showticklabels=False),
                width=options.get("width", 900),
                height=options.get("height", 700),
                updatemenus=[{
                    "type": "buttons",
                    "buttons": [
                        {
                            "label": "Play",
                            "method": "animate",
                            "args": [None, {"frame": {"duration": 1000, "redraw": True}, "fromcurrent": True}]
                        },
                        {
                            "label": "Pause",
                            "method": "animate",
                            "args": [[], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}]
                        }
                    ],
                    "showactive": False,
                    "y": 0,
                    "x": 0.1,
                    "xanchor": "right",
                    "yanchor": "top"
                }],
                sliders=[{
                    "currentvalue": {"prefix": "Time: "},
                    "pad": {"t": 50},
                    "steps": [
                        {
                            "method": "animate",
                            "label": str(t),
                            "args": [[str(t)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}]
                        }
                        for t in sorted_times
                    ]
                }]
            ),
            frames=frames
        )

        if output == "interactive":
            return fig
        elif file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )
            return None



    def visualize_timeline(
        self,
        temporal_data: Dict[str, Any],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize timeline of entity/relationship changes.

        Args:
            temporal_data: Temporal data dictionary with timestamps and changes
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        tracking_id = self.progress_tracker.start_tracking(
            module="visualization",
            submodule="TemporalVisualizer",
            message="Visualizing temporal timeline",
        )

        try:
            self.logger.info("Visualizing temporal timeline")

            # Extract timeline data
            self.progress_tracker.update_tracking(
                tracking_id, message="Extracting timeline data..."
            )
            events = temporal_data.get("events", [])
            timestamps = temporal_data.get("timestamps", [])

            # Handle case where timestamps is a dictionary mapping entities to time points
            if not events and isinstance(timestamps, dict):
                entities = temporal_data.get("entities", [])
                entity_map = {e.get("id"): e for e in entities} if entities else {}

                for entity_id, times in timestamps.items():
                    if not isinstance(times, list):
                        continue

                    entity_name = entity_id
                    if entity_id in entity_map:
                        entity_name = entity_map[entity_id].get("name", entity_id)

                    for t in times:
                        events.append({
                            "timestamp": t,
                            "type": "activity",
                            "label": entity_name,
                            "entity": entity_id
                        })

            if not events:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message="No temporal events found"
                )
                raise ProcessingError("No temporal events found")

            # Build timeline
            self.progress_tracker.update_tracking(
                tracking_id, message="Building timeline..."
            )
            event_types = []
            event_times = []
            event_labels = []

            for event in events:
                event_time = event.get("timestamp") or event.get("time", "")
                event_type = event.get("type") or event.get("event_type", "change")
                event_label = event.get("label") or event.get("entity", "")

                event_times.append(event_time)
                event_types.append(event_type)
                event_labels.append(event_label)

            # Create Gantt chart style timeline
            self.progress_tracker.update_tracking(
                tracking_id, message="Generating visualization..."
            )
            fig = go.Figure()

            # Group by type
            type_colors = {}
            unique_types = list(set(event_types))
            colors = ColorPalette.get_colors(self.color_scheme, len(unique_types))
            for i, t in enumerate(unique_types):
                type_colors[t] = colors[i]

            for event_type in unique_types:
                mask = [t == event_type for t in event_types]
                type_times = [
                    event_times[i] for i in range(len(event_times)) if mask[i]
                ]
                type_labels = [
                    event_labels[i] for i in range(len(event_labels)) if mask[i]
                ]

                fig.add_trace(
                    go.Scatter(
                        x=type_times,
                        y=[event_type] * len(type_times),
                        mode="markers",
                        name=event_type,
                        marker=dict(size=10, color=type_colors[event_type]),
                        text=type_labels,
                        hovertemplate="%{text}<br>Time: %{x}<extra></extra>",
                    )
                )

            fig.update_layout(
                title="Temporal Timeline",
                xaxis_title="Time",
                yaxis_title="Event Type",
                width=1200,
                height=600,
            )

            if output == "interactive":
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Timeline visualization generated: {len(events)} events",
                )
                return fig
            elif file_path:
                export_plotly_figure(
                    fig, file_path, format=output if output != "interactive" else "html"
                )
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Timeline saved to {file_path}",
                )
                return None
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def visualize_temporal_patterns(
        self,
        patterns: List[Dict[str, Any]],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize detected temporal patterns.

        Args:
            patterns: List of temporal patterns
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing temporal patterns")

        if not patterns:
            raise ProcessingError("No temporal patterns found")

        # Extract pattern data
        pattern_types = [p.get("pattern_type", "Unknown") for p in patterns]
        start_times = [p.get("start_time", "") for p in patterns]
        end_times = [p.get("end_time", "") for p in patterns]
        entities = [p.get("entities", []) for p in patterns]

        # Create timeline visualization
        fig = go.Figure()

        for i, pattern in enumerate(patterns):
            pattern_type = pattern.get("pattern_type", "Unknown")
            start_time = pattern.get("start_time", "")
            end_time = pattern.get("end_time", "")
            pattern_entities = pattern.get("entities", [])

            # Create a bar for the pattern duration
            fig.add_trace(
                go.Scatter(
                    x=[start_time, end_time],
                    y=[i, i],
                    mode="lines+markers",
                    name=pattern_type,
                    line=dict(
                        width=10,
                        color=ColorPalette.get_color_by_index(self.color_scheme, i),
                    ),
                    text=f"{pattern_type}: {len(pattern_entities)} entities",
                    hovertemplate="%{text}<br>Start: %{x}<extra></extra>",
                )
            )

        fig.update_layout(
            title="Temporal Patterns",
            xaxis_title="Time",
            yaxis_title="Pattern",
            width=1200,
            height=max(400, len(patterns) * 50),
        )

        if output == "interactive":
            return fig
        elif file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )
            return None

    def visualize_snapshot_comparison(
        self,
        snapshots: Dict[str, Dict[str, Any]],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize comparison of graph snapshots at different times.

        Args:
            snapshots: Dictionary mapping timestamps to graph snapshots
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing snapshot comparison")

        timestamps = sorted(snapshots.keys())

        # Extract metrics for each snapshot
        metrics_over_time = {"entities": [], "relationships": [], "density": []}

        for timestamp in timestamps:
            snapshot = snapshots[timestamp]
            entities = snapshot.get("entities", [])
            relationships = snapshot.get("relationships", [])

            metrics_over_time["entities"].append(len(entities))
            metrics_over_time["relationships"].append(len(relationships))

            # Calculate density
            num_nodes = len(entities)
            num_edges = len(relationships)
            max_edges = num_nodes * (num_nodes - 1) / 2 if num_nodes > 1 else 0
            density = num_edges / max_edges if max_edges > 0 else 0
            metrics_over_time["density"].append(density)

        # Create line chart
        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=metrics_over_time["entities"],
                mode="lines+markers",
                name="Entities",
                line=dict(color="blue", width=2),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=metrics_over_time["relationships"],
                mode="lines+markers",
                name="Relationships",
                line=dict(color="red", width=2),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=metrics_over_time["density"],
                mode="lines+markers",
                name="Density",
                line=dict(color="green", width=2),
                yaxis="y2",
            )
        )

        fig.update_layout(
            title="Graph Evolution Over Time",
            xaxis_title="Time",
            yaxis_title="Count",
            yaxis2=dict(title="Density", overlaying="y", side="right"),
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

    def visualize_version_history(
        self,
        version_history: List[Dict[str, Any]],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize version history tree.

        Args:
            version_history: List of version information
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing version history")

        # Build tree structure
        versions = sorted(version_history, key=lambda v: v.get("version", ""))

        # Create timeline
        version_names = [v.get("version", f"v{i}") for i, v in enumerate(versions)]
        version_dates = [v.get("date", v.get("timestamp", "")) for v in versions]
        version_changes = [v.get("changes", v.get("description", "")) for v in versions]

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=version_dates,
                y=[i for i in range(len(versions))],
                mode="lines+markers+text",
                text=version_names,
                textposition="middle right",
                line=dict(color="blue", width=2),
                marker=dict(size=10, color="red"),
                hovertemplate="Version: %{text}<br>Date: %{x}<extra></extra>",
            )
        )

        fig.update_layout(
            title="Version History",
            xaxis_title="Date",
            yaxis_title="Version",
            yaxis=dict(
                tickmode="array",
                tickvals=list(range(len(versions))),
                ticktext=version_names,
            ),
            width=1200,
            height=max(400, len(versions) * 50),
        )

        if output == "interactive":
            return fig
        elif file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )
            return None

    def visualize_metrics_evolution(
        self,
        metrics_history: Dict[str, List[float]],
        timestamps: List[str],
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize metrics evolution over time.

        Args:
            metrics_history: Dictionary mapping metric names to time series
            timestamps: List of timestamps
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        self.logger.info("Visualizing metrics evolution")

        fig = go.Figure()

        colors = ColorPalette.get_colors(self.color_scheme, len(metrics_history))

        for i, (metric_name, values) in enumerate(metrics_history.items()):
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=values,
                    mode="lines+markers",
                    name=metric_name,
                    line=dict(color=colors[i], width=2),
                    marker=dict(size=6),
                )
            )

        fig.update_layout(
            title="Metrics Evolution Over Time",
            xaxis_title="Time",
            yaxis_title="Metric Value",
            width=1200,
            height=600,
            hovermode="x unified",
        )

        if output == "interactive":
            return fig
        elif file_path:
            export_plotly_figure(
                fig, file_path, format=output if output != "interactive" else "html"
            )
            return None
