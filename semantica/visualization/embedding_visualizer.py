"""
Embedding Visualizer Module

This module provides comprehensive visualization capabilities for vector
embeddings in the Semantica framework, including 2D/3D dimensionality
reduction projections, similarity heatmaps, clustering visualizations,
multi-modal comparisons, and quality metrics analysis.

Key Features:
    - 2D and 3D dimensionality reduction (UMAP, t-SNE, PCA)
    - Similarity heatmap visualization
    - Clustering visualization with color coding
    - Multi-modal embedding comparisons (text, image, audio)
    - Embedding quality metrics (norms, distributions)
    - Interactive and static output formats
    - Optional dependency handling (UMAP, sklearn)

Main Classes:
    - EmbeddingVisualizer: Main embedding visualizer coordinator

Example Usage:
    >>> from semantica.visualization import EmbeddingVisualizer
    >>> viz = EmbeddingVisualizer(color_scheme="vibrant")
    >>> fig = viz.visualize_2d_projection(embeddings, labels, method="umap")
    >>> viz.visualize_3d_projection(embeddings, method="tsne", file_path="3d.html")
    >>> viz.visualize_similarity_heatmap(embeddings, labels, output="interactive")
    >>> viz.visualize_clustering(embeddings, cluster_labels, method="umap")
    >>> viz.visualize_multimodal_comparison(text_emb, image_emb, audio_emb)

Author: Semantica Contributors
License: MIT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except (ImportError, OSError):
    px = None
    go = None
    make_subplots = None

try:
    from sklearn.decomposition import PCA
    from sklearn.manifold import TSNE
except (ImportError, OSError):
    PCA = None
    TSNE = None

try:
    import umap
except (ImportError, OSError):
    umap = None

from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .utils.color_schemes import ColorPalette, ColorScheme
from .utils.export_formats import export_plotly_figure


class EmbeddingVisualizer:
    """
    Embedding visualizer.

    Provides visualization methods for embeddings including:
    - 2D/3D dimensionality reduction projections
    - Similarity heatmaps
    - Clustering visualizations
    - Multi-modal embedding comparisons
    """

    def __init__(self, **config):
        """
        Initialize embedding visualizer.

        Args:
            **config: Configuration options:
                - color_scheme: Color scheme name
                - point_size: Point size for scatter plots
        """
        self.logger = get_logger("embedding_visualizer")
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
        self.point_size = config.get("point_size", 5)

    def _check_dependencies(self, require_sklearn: bool = False):
        """Check if dependencies are available."""
        if px is None or go is None:
            raise ProcessingError(
                "Plotly is required for embedding visualization. "
                "Install with: pip install 'semantica[viz]'"
            )
        if require_sklearn and (PCA is None or TSNE is None):
            raise ProcessingError(
                "scikit-learn is required for dimensionality reduction. "
                "Reinstall scikit-learn or install dependencies."
            )

    def visualize_2d_projection(
        self,
        embeddings: np.ndarray,
        labels: Optional[List[str]] = None,
        method: str = "umap",
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        color_by: Optional[List[Any]] = None,
        size_by: Optional[List[float]] = None,
        hover_data: Optional[List[Dict[str, Any]]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize embeddings in 2D using dimensionality reduction.

        Implements the 5-step visualization process:
        1. Problem setting: Dimensionality reduction choice
        2. Data analysis: Logs embedding statistics
        3. Layout: 2D Projection (UMAP/t-SNE/PCA)
        4. Styling: Configurable color and size mapping
        5. Interaction: Rich hover data

        Args:
            embeddings: Embedding matrix (n_samples, n_features)
            labels: Optional labels for points (used as default color_by if provided)
            method: Reduction method ("umap", "tsne", "pca")
            output: Output type ("interactive", "html", "png", "svg")
            file_path: Output file path
            color_by: List of values to map to color (overrides labels)
            size_by: List of values to map to point size
            hover_data: List of dictionaries containing metadata for each point
            **options: Additional options:
                - n_components: Number of components (default: 2)
                - perplexity: Perplexity for t-SNE
                - n_neighbors: Number of neighbors for UMAP

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        tracking_id = self.progress_tracker.start_tracking(
            module="visualization",
            submodule="EmbeddingVisualizer",
            message=f"Visualizing 2D projection using {method}",
        )

        try:
            self.logger.info(f"Visualizing 2D projection using {method}")

            # Step 2: Data Analysis
            n_samples, n_features = embeddings.shape
            self.logger.info(
                f"Embedding Analysis: {n_samples} samples, {n_features} dimensions"
            )

            if embeddings.shape[1] <= 2:
                # Already 2D or less, use directly
                self.progress_tracker.update_tracking(
                    tracking_id, message="Using embeddings directly (already 2D)..."
                )
                projected = embeddings[:, :2]
            else:
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Reducing dimensions using {method}..."
                )
                dim_options = dict(options)
                n_comp = dim_options.pop("n_components", 2)
                projected = self._reduce_dimensions(
                    embeddings, method=method, n_components=n_comp, **dim_options
                )

            self.progress_tracker.update_tracking(
                tracking_id, message="Generating visualization..."
            )
            result = self._visualize_2d_plotly(
                projected,
                labels,
                output,
                file_path,
                color_by=color_by,
                size_by=size_by,
                hover_data=hover_data,
                **options,
            )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=(
                    f"2D projection visualization generated: {len(projected)} points"
                ),
            )
            return result
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def visualize_3d_projection(
        self,
        embeddings: np.ndarray,
        labels: Optional[List[str]] = None,
        method: str = "umap",
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize embeddings in 3D using dimensionality reduction.

        Args:
            embeddings: Embedding matrix (n_samples, n_features)
            labels: Optional labels for coloring points
            method: Reduction method ("umap", "tsne", "pca")
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        tracking_id = self.progress_tracker.start_tracking(
            module="visualization",
            submodule="EmbeddingVisualizer",
            message=f"Visualizing 3D projection using {method}",
        )

        try:
            self.logger.info(f"Visualizing 3D projection using {method}")

            if embeddings.shape[1] <= 3:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Using embeddings directly (already 3D)..."
                )
                projected = embeddings[:, :3]
            else:
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Reducing dimensions using {method}..."
                )
                dim_options = dict(options)
                n_comp = dim_options.pop("n_components", 3)
                projected = self._reduce_dimensions(
                    embeddings, method=method, n_components=n_comp, **dim_options
                )

            self.progress_tracker.update_tracking(
                tracking_id, message="Generating visualization..."
            )
            result = self._visualize_3d_plotly(
                projected, labels, output, file_path, **options
            )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=(
                    f"3D projection visualization generated: {len(projected)} points"
                ),
            )
            return result
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def visualize_similarity_heatmap(
        self,
        embeddings: np.ndarray,
        labels: Optional[List[str]] = None,
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize similarity heatmap between embeddings.

        Args:
            embeddings: Embedding matrix
            labels: Optional labels for axis
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        tracking_id = self.progress_tracker.start_tracking(
            module="visualization",
            submodule="EmbeddingVisualizer",
            message="Visualizing similarity heatmap",
        )

        try:
            self.logger.info("Visualizing similarity heatmap")

            # Calculate cosine similarity
            self.progress_tracker.update_tracking(
                tracking_id, message="Calculating similarity matrix..."
            )
            # Normalize embeddings
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1  # Avoid division by zero
            normalized = embeddings / norms

            # Calculate similarity matrix
            similarity_matrix = np.dot(normalized, normalized.T)

            self.progress_tracker.update_tracking(
                tracking_id, message="Generating heatmap visualization..."
            )
            fig = go.Figure(
                data=go.Heatmap(
                    z=similarity_matrix,
                    colorscale="Viridis",
                    text=similarity_matrix,
                    texttemplate="%{text:.2f}",
                    textfont={"size": 8},
                )
            )

            if labels:
                fig.update_layout(
                    xaxis=dict(
                        tickmode="array",
                        tickvals=list(range(len(labels))),
                        ticktext=labels,
                    ),
                    yaxis=dict(
                        tickmode="array",
                        tickvals=list(range(len(labels))),
                        ticktext=labels,
                    ),
                )

            fig.update_layout(
                title="Embedding Similarity Heatmap",
                xaxis_title="Embedding Index",
                yaxis_title="Embedding Index",
                width=800,
                height=800,
            )

            if output == "interactive":
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=(
                        f"Similarity heatmap generated: "
                        f"{len(embeddings)}x{len(embeddings)} matrix"
                    ),
                )
                return fig
            elif file_path:
                export_plotly_figure(
                    fig, file_path, format=output if output != "interactive" else "html"
                )
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Similarity heatmap saved to {file_path}",
                )
                return None
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def visualize_clustering(
        self,
        embeddings: np.ndarray,
        cluster_labels: np.ndarray,
        method: str = "umap",
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize embeddings with cluster coloring.

        Args:
            embeddings: Embedding matrix
            cluster_labels: Cluster assignments for each embedding
            method: Reduction method for 2D projection
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        tracking_id = self.progress_tracker.start_tracking(
            module="visualization",
            submodule="EmbeddingVisualizer",
            message="Visualizing embedding clusters",
        )

        try:
            self.logger.info("Visualizing embedding clusters")

            # Project to 2D
            if embeddings.shape[1] <= 2:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Using embeddings directly (already 2D)..."
                )
                projected = embeddings[:, :2]
            else:
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Reducing dimensions using {method}..."
                )
                dim_options = dict(options)
                n_comp = dim_options.pop("n_components", 2)
                projected = self._reduce_dimensions(
                    embeddings, method=method, n_components=n_comp, **dim_options
                )

            num_clusters = len(set(cluster_labels))
            cluster_colors = ColorPalette.get_community_colors(
                num_clusters, self.color_scheme
            )

            colors = [cluster_colors[label % num_clusters] for label in cluster_labels]

            self.progress_tracker.update_tracking(
                tracking_id, message="Generating visualization..."
            )
            fig = go.Figure(
                data=go.Scatter(
                    x=projected[:, 0],
                    y=projected[:, 1],
                    mode="markers",
                    marker=dict(
                        size=self.point_size,
                        color=colors,
                        line=dict(width=1, color="black"),
                    ),
                    text=[f"Cluster {label}" for label in cluster_labels],
                    hovertemplate="%{text}<extra></extra>",
                )
            )

            fig.update_layout(
                title="Embedding Clusters",
                xaxis_title="Dimension 1",
                yaxis_title="Dimension 2",
                width=800,
                height=600,
            )

            if output == "interactive":
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=(
                        f"Clustering visualization generated: "
                        f"{num_clusters} clusters, {len(embeddings)} points"
                    ),
                )
                return fig
            elif file_path:
                export_plotly_figure(
                    fig, file_path, format=output if output != "interactive" else "html"
                )
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Clustering visualization saved to {file_path}",
                )
                return None
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def visualize_multimodal_comparison(
        self,
        text_embeddings: Optional[np.ndarray] = None,
        image_embeddings: Optional[np.ndarray] = None,
        audio_embeddings: Optional[np.ndarray] = None,
        method: str = "umap",
        output: str = "interactive",
        file_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> Optional[Any]:
        """
        Visualize multi-modal embeddings side by side.

        Args:
            text_embeddings: Text embeddings
            image_embeddings: Image embeddings
            audio_embeddings: Audio embeddings
            method: Reduction method
            output: Output type
            file_path: Output file path
            **options: Additional options

        Returns:
            Visualization figure or None
        """
        self._check_dependencies()
        tracking_id = self.progress_tracker.start_tracking(
            module="visualization",
            submodule="EmbeddingVisualizer",
            message="Visualizing multi-modal embedding comparison",
        )

        try:
            self.logger.info("Visualizing multi-modal embedding comparison")

            # Collect embeddings and labels
            self.progress_tracker.update_tracking(
                tracking_id, message="Collecting embeddings..."
            )
            all_embeddings = []
            all_labels = []
            all_types = []

            if text_embeddings is not None:
                all_embeddings.append(text_embeddings)
                all_labels.extend([f"Text {i}" for i in range(len(text_embeddings))])
                all_types.extend(["text"] * len(text_embeddings))

            if image_embeddings is not None:
                all_embeddings.append(image_embeddings)
                all_labels.extend([f"Image {i}" for i in range(len(image_embeddings))])
                all_types.extend(["image"] * len(image_embeddings))

            if audio_embeddings is not None:
                all_embeddings.append(audio_embeddings)
                all_labels.extend([f"Audio {i}" for i in range(len(audio_embeddings))])
                all_types.extend(["audio"] * len(audio_embeddings))

            if not all_embeddings:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message="No embeddings provided"
                )
                raise ProcessingError("No embeddings provided")

            # Concatenate embeddings
            combined_embeddings = np.vstack(all_embeddings)

            # Project to 2D
            if combined_embeddings.shape[1] <= 2:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Using embeddings directly (already 2D)..."
                )
                projected = combined_embeddings[:, :2]
            else:
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Reducing dimensions using {method}..."
                )
                dim_options = dict(options)
                n_comp = dim_options.pop("n_components", 2)
                projected = self._reduce_dimensions(
                    combined_embeddings,
                    method=method,
                    n_components=n_comp,
                    **dim_options,
                )

            # Color by type
            type_colors = {"text": "#1f77b4", "image": "#ff7f0e", "audio": "#2ca02c"}
            colors = [type_colors.get(t, "#888") for t in all_types]

            self.progress_tracker.update_tracking(
                tracking_id, message="Generating visualization..."
            )
            fig = go.Figure(
                data=go.Scatter(
                    x=projected[:, 0],
                    y=projected[:, 1],
                    mode="markers",
                    marker=dict(
                        size=self.point_size,
                        color=colors,
                        line=dict(width=1, color="black"),
                    ),
                    text=all_labels,
                    hovertemplate="%{text}<extra></extra>",
                )
            )

            fig.update_layout(
                title="Multi-Modal Embedding Comparison",
                xaxis_title="Dimension 1",
                yaxis_title="Dimension 2",
                width=800,
                height=600,
            )

            if output == "interactive":
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=(
                        f"Multi-modal comparison generated: "
                        f"{len(combined_embeddings)} embeddings"
                    ),
                )
                return fig
            elif file_path:
                export_plotly_figure(
                    fig, file_path, format=output if output != "interactive" else "html"
                )
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Multi-modal comparison saved to {file_path}",
                )
                return None
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _reduce_dimensions(
        self,
        embeddings: np.ndarray,
        method: str = "umap",
        n_components: int = 2,
        **options,
    ) -> np.ndarray:
        """Reduce embedding dimensions using specified method."""
        opts = dict(options)
        opts.pop("n_components", None)

        if method == "pca":
            if PCA is None:
                raise ProcessingError(
                    "scikit-learn is required for dimensionality reduction. "
                    "Reinstall scikit-learn or install dependencies."
                )
            pca = PCA(n_components=n_components, **opts)
            return pca.fit_transform(embeddings)

        elif method == "tsne":
            if TSNE is None:
                raise ProcessingError(
                    "scikit-learn is required for dimensionality reduction. "
                    "Reinstall scikit-learn or install dependencies."
                )
            perplexity = opts.pop("perplexity", min(30, len(embeddings) - 1))
            random_state = opts.pop("random_state", 42)
            tsne = TSNE(
                n_components=n_components,
                perplexity=perplexity,
                random_state=random_state,
                **opts,
            )
            return tsne.fit_transform(embeddings)

        elif method == "umap":
            if umap is not None:
                n_neighbors = opts.pop("n_neighbors", min(15, len(embeddings) - 1))
                reducer = umap.UMAP(
                    n_components=n_components, n_neighbors=n_neighbors, **opts
                )
                return reducer.fit_transform(embeddings)
            else:
                raise ProcessingError(
                    "UMAP is required for UMAP dimensionality reduction. "
                    "Install with: pip install 'semantica[viz]'"
                )

        else:
            if PCA is None:
                raise ProcessingError(
                    "scikit-learn is required for dimensionality reduction. "
                    "Reinstall scikit-learn or install dependencies."
                )
            # Fallback to PCA
            self.logger.warning(f"Method {method} not available, using PCA")
            pca = PCA(n_components=n_components, **opts)
            return pca.fit_transform(embeddings)

    def _visualize_2d_plotly(
        self,
        projected: np.ndarray,
        labels: Optional[List[str]],
        output: str,
        file_path: Optional[Path],
        **options,
    ) -> Optional[Any]:
        """Create 2D Plotly visualization."""
        if labels:
            fig = go.Figure(
                data=go.Scatter(
                    x=projected[:, 0],
                    y=projected[:, 1],
                    mode="markers+text",
                    text=labels,
                    textposition="top center",
                    marker=dict(
                        size=self.point_size,
                        color="lightblue",
                        line=dict(width=1, color="darkblue"),
                    ),
                )
            )
        else:
            fig = go.Figure(
                data=go.Scatter(
                    x=projected[:, 0],
                    y=projected[:, 1],
                    mode="markers",
                    marker=dict(
                        size=self.point_size,
                        color="lightblue",
                        line=dict(width=1, color="darkblue"),
                    ),
                )
            )

        fig.update_layout(
            title="Embedding 2D Projection",
            xaxis_title="Dimension 1",
            yaxis_title="Dimension 2",
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

    def _visualize_3d_plotly(
        self,
        projected: np.ndarray,
        labels: Optional[List[str]],
        output: str,
        file_path: Optional[Path],
        **options,
    ) -> Optional[Any]:
        """Create 3D Plotly visualization."""
        if labels:
            fig = go.Figure(
                data=go.Scatter3d(
                    x=projected[:, 0],
                    y=projected[:, 1],
                    z=projected[:, 2],
                    mode="markers+text",
                    text=labels,
                    textposition="top center",
                    marker=dict(
                        size=self.point_size,
                        color="lightblue",
                        line=dict(width=1, color="darkblue"),
                    ),
                )
            )
        else:
            fig = go.Figure(
                data=go.Scatter3d(
                    x=projected[:, 0],
                    y=projected[:, 1],
                    z=projected[:, 2],
                    mode="markers",
                    marker=dict(
                        size=self.point_size,
                        color="lightblue",
                        line=dict(width=1, color="darkblue"),
                    ),
                )
            )

        fig.update_layout(
            title="Embedding 3D Projection",
            scene=dict(
                xaxis_title="Dimension 1",
                yaxis_title="Dimension 2",
                zaxis_title="Dimension 3",
            ),
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
