"""EmbeddingGenerator(method=..., model_name=...) used to be ignored (#1808)."""

import unittest
from unittest.mock import patch

from semantica.embeddings.embedding_generator import EmbeddingGenerator


class TestGeneratorMethodKwargs(unittest.TestCase):

    def setUp(self):
        patchers = [
            patch("semantica.embeddings.text_embedder.SentenceTransformer"),
            patch("semantica.embeddings.text_embedder.TextEmbedding"),
            patch(
                "semantica.embeddings.text_embedder.SENTENCE_TRANSFORMERS_AVAILABLE",
                True,
            ),
            patch("semantica.embeddings.text_embedder.FASTEMBED_AVAILABLE", True),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_top_level_method_reaches_the_text_embedder(self):
        generator = EmbeddingGenerator(
            method="sentence_transformers", model_name="st-model"
        )
        self.assertEqual(generator.text_embedder.method, "sentence_transformers")
        self.assertEqual(generator.text_embedder.model_name, "st-model")
        self.assertEqual(generator.get_text_method(), "sentence_transformers")

    def test_top_level_method_via_config_dict(self):
        generator = EmbeddingGenerator(config={"method": "sentence_transformers"})
        self.assertEqual(generator.get_text_method(), "sentence_transformers")

    def test_text_config_still_wins(self):
        generator = EmbeddingGenerator(
            method="sentence_transformers",
            text={"method": "fastembed", "model_name": "fast-model"},
        )
        self.assertEqual(generator.text_embedder.method, "fastembed")
        self.assertEqual(generator.text_embedder.model_name, "fast-model")

    def test_default_is_unchanged(self):
        generator = EmbeddingGenerator()
        self.assertEqual(generator.text_embedder.method, "fastembed")

    def test_caller_config_is_not_mutated(self):
        text = {"model_name": "fast-model"}
        EmbeddingGenerator(method="sentence_transformers", text=text)
        self.assertEqual(text, {"model_name": "fast-model"})

    def test_caller_top_level_config_is_not_mutated(self):
        config = {"text": {"model_name": "fast-model"}}
        EmbeddingGenerator(config=config, method="sentence_transformers")
        self.assertEqual(config, {"text": {"model_name": "fast-model"}})


if __name__ == "__main__":
    unittest.main()
