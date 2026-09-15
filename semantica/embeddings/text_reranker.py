"""
Text Reranker Module

Cross-encoder reranking primitive for retrieval pipelines (e.g. BAAI
bge-reranker-v2-m3). Scores query-document pairs with a deep-interaction
cross encoder to produce a refined ordering of a candidate pool.

Key Features:
    - FlagEmbedding FlagReranker backend (first-party BAAI runtime, default)
    - sentence-transformers CrossEncoder backend (alternative runtime)
    - No silent fallback: if the requested backend is unavailable the rerank()
      call raises, and the caller decides how to degrade (e.g. keep the fused
      order) — a reranker that silently returns meaningless scores is worse
      than no reranker.

Example Usage:
    >>> from semantica.embeddings.text_reranker import TextReranker
    >>> reranker = TextReranker(model_name="BAAI/bge-reranker-v2-m3")
    >>> docs = ["Rivers overflow after heavy rain...", "Droughts reduce soil moisture..."]
    >>> scores = reranker.rerank("what causes seasonal flooding", docs)
    >>> order = sorted(range(len(docs)), key=lambda i: -scores[i])

Author: Semantica Contributors
License: MIT
"""

from typing import Any, Dict, List

from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger

try:
    from FlagEmbedding import FlagReranker

    FLAGRERANKER_AVAILABLE = True
except (ImportError, OSError):
    FLAGRERANKER_AVAILABLE = False
    FlagReranker = None

try:
    from sentence_transformers import CrossEncoder

    CROSSENCODER_AVAILABLE = True
except (ImportError, OSError):
    CROSSENCODER_AVAILABLE = False
    CrossEncoder = None


class TextReranker:
    """Cross-encoder reranker (bge-reranker-v2-m3 style, CPU-friendly)."""

    SUPPORTED_METHODS = ("flagembedding", "sentence_transformers")

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        method: str = "flagembedding",
        device: str = "cpu",
        **config,
    ):
        """
        Initialize text reranker.

        Args:
            model_name: Cross-encoder model name/path (weights load here;
                offline deployments mount the model directory and pass its path)
            method: Backend runtime — "flagembedding" (FlagReranker, first-party
                BAAI runtime, default) or "sentence_transformers" (CrossEncoder)
            device: "cpu" or "cuda" (default "cpu")
            **config: Backend options (e.g. use_fp16 for FlagReranker)
        """
        self.logger = get_logger("text_reranker")
        self.model_name = model_name
        self.method = method.lower()
        self.device = device
        self.config = config
        self.model = None
        self._load_error = ""
        if self.method not in self.SUPPORTED_METHODS:
            raise ProcessingError(
                f"Unknown reranker method: {method!r} (supported: {self.SUPPORTED_METHODS})"
            )
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Load the requested backend; no cross-backend fallback (caller degrades)."""
        self.model = None
        self._load_error = ""
        try:
            if self.method == "flagembedding":
                if not FLAGRERANKER_AVAILABLE:
                    raise ProcessingError(
                        "FlagEmbedding not available. Install with: pip install FlagEmbedding"
                    )
                self.model = FlagReranker(
                    self.model_name,
                    use_fp16=self.config.get("use_fp16", False),
                    devices=[self.device],
                )
            else:  # sentence_transformers
                if not CROSSENCODER_AVAILABLE:
                    raise ProcessingError(
                        "sentence-transformers not available. "
                        "Install with: pip install sentence-transformers"
                    )
                self.model = CrossEncoder(self.model_name, device=self.device)
            self.logger.info(
                f"Loaded reranker: {self.model_name} (method={self.method}, device={self.device})"
            )
        except Exception as e:
            self._load_error = str(e)
            self.model = None
            # 不换后端、不静默降级：调用方据 rerank() 的异常决定降级路径
            self.logger.warning(f"Failed to load reranker '{self.model_name}': {e}")

    def rerank(self, query: str, documents: List[str], **options) -> List[float]:
        """
        Score query-document pairs; scores aligned with documents (higher = more relevant).

        Args:
            query: Query text
            documents: Candidate documents (truncate long docs at the caller —
                e.g. ~256-token truncation keeps CPU cost bounded)
            **options: Backend options (e.g. batch_size)

        Returns:
            List[float]: One score per document, same order as input.
                flagembedding: sigmoid-normalized (0, 1) when normalize=True
                (default); sentence_transformers: raw logits.

        Raises:
            ProcessingError: If the model is not loaded (backend unavailable or
                load failed) or inputs are empty.
        """
        if self.model is None:
            raise ProcessingError(
                f"Reranker not available (method={self.method}, "
                f"model={self.model_name}): {self._load_error or 'not loaded'}"
            )
        if not query or not query.strip():
            raise ProcessingError("Query cannot be empty or whitespace-only")
        if not documents:
            return []

        pairs = [[query, doc] for doc in documents]
        try:
            if self.method == "flagembedding":
                scores = self.model.compute_score(
                    pairs,
                    normalize=self.config.get("normalize", True),
                    batch_size=options.get("batch_size", 16),
                )
                return [float(s) for s in scores]
            scores = self.model.predict(pairs)
            return [float(s) for s in scores]
        except Exception as e:
            raise ProcessingError(f"Reranker scoring failed: {e}") from e

    def get_method(self) -> str:
        """Active backend name, or "unavailable" when the model is not loaded."""
        return self.method if self.model is not None else "unavailable"

    def get_model_info(self) -> Dict[str, Any]:
        """Reranker status summary (no weight loading side effects)."""
        return {
            "method": self.method,
            "model_name": self.model_name,
            "model_loaded": self.model is not None,
            "device": self.device,
            "load_error": self._load_error or None,
        }
