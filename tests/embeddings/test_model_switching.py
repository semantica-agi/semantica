import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import sys
import os

# Ensure the package is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from semantica.embeddings.text_embedder import TextEmbedder
from semantica.embeddings.embedding_generator import EmbeddingGenerator

class TestModelSwitching(unittest.TestCase):
    """Test suite for dynamic model switching in TextEmbedder and EmbeddingGenerator."""

    def setUp(self):
        # Mock dependencies
        self.mock_st_patcher = patch('semantica.embeddings.text_embedder.SentenceTransformer')
        self.mock_st_class = self.mock_st_patcher.start()
        
        self.mock_fe_patcher = patch('semantica.embeddings.text_embedder.TextEmbedding')
        self.mock_fe_class = self.mock_fe_patcher.start()
        
        # Patch availability flags
        self.st_avail_patcher = patch('semantica.embeddings.text_embedder.SENTENCE_TRANSFORMERS_AVAILABLE', True)
        self.st_avail_patcher.start()
        
        self.fe_avail_patcher = patch('semantica.embeddings.text_embedder.FASTEMBED_AVAILABLE', True)
        self.fe_avail_patcher.start()

    def tearDown(self):
        self.mock_st_patcher.stop()
        self.mock_fe_patcher.stop()
        self.st_avail_patcher.stop()
        self.fe_avail_patcher.stop()

    def test_text_embedder_dynamic_switching(self):
        """Test that TextEmbedder correctly switches between methods and clears state."""
        # 1. Start with fastembed
        embedder = TextEmbedder(method="fastembed", model_name="fast-model")
        self.assertEqual(embedder.get_method(), "fastembed")
        self.assertIsNotNone(embedder.fastembed_model)
        self.assertIsNone(embedder.model)
        
        # 2. Switch to sentence_transformers
        embedder.set_model(method="sentence_transformers", model_name="st-model")
        
        # Verify method and model state
        self.assertEqual(embedder.get_method(), "sentence_transformers")
        self.assertIsNone(embedder.fastembed_model, "fastembed_model should be cleared after switching")
        self.assertIsNotNone(embedder.model, "sentence_transformer model should be initialized")
        self.assertEqual(embedder.model_name, "st-model")
        
        # 3. Switch back to fastembed
        embedder.set_model(method="fastembed", model_name="fast-model-v2")
        
        self.assertEqual(embedder.get_method(), "fastembed")
        self.assertIsNotNone(embedder.fastembed_model, "fastembed_model should be re-initialized")
        self.assertIsNone(embedder.model, "sentence_transformer model should be cleared")
        self.assertEqual(embedder.model_name, "fast-model-v2")

    def test_embedding_generator_dynamic_switching(self):
        """Test that EmbeddingGenerator correctly propagates model switches to TextEmbedder."""
        gen = EmbeddingGenerator()
        
        # Default should be fastembed
        self.assertEqual(gen.get_text_method(), "fastembed")
        
        # Switch via EmbeddingGenerator
        gen.set_text_model(method="sentence_transformers", model_name="new-st-model")
        
        # Verify through Generator methods
        self.assertEqual(gen.get_text_method(), "sentence_transformers")
        
        info = gen.get_methods_info()
        self.assertEqual(info['text']['method'], "sentence_transformers")
        self.assertEqual(info['text']['model_name'], "new-st-model")
        self.assertTrue(info['text']['model_loaded'])

    def test_fallback_on_switch_failure(self):
        """Test that switching to an unavailable method falls back to 'fallback'."""
        embedder = TextEmbedder(method="sentence_transformers")
        
        # Mock availability to False for the next switch
        with patch('semantica.embeddings.text_embedder.FASTEMBED_AVAILABLE', False):
            embedder.set_model(method="fastembed", model_name="some-model")
            
            self.assertEqual(embedder.get_method(), "fallback")
            self.assertIsNone(embedder.fastembed_model)
            self.assertIsNone(embedder.model)

    def test_dimension_update_on_switch(self):
        """Test that embedding_dimension is correctly updated when switching models."""
        # 1. Setup mocks to return specific dimensions
        # FastEmbed mock
        mock_fe_instance = MagicMock()
        # FastEmbed doesn't have a direct dimension attribute in our implementation, 
        # it calls _embed_with_fastembed which calls self.fastembed_model.embed
        mock_fe_instance.embed.return_value = [np.zeros(384)] 
        self.mock_fe_class.return_value = mock_fe_instance
        
        # SentenceTransformer mock
        mock_st_instance = MagicMock()
        mock_st_instance.get_sentence_embedding_dimension.return_value = 768
        self.mock_st_class.return_value = mock_st_instance
        
        # 2. Start with FastEmbed (dim 384)
        embedder = TextEmbedder(method="fastembed", model_name="fast-model")
        self.assertEqual(embedder.get_embedding_dimension(), 384)
        
        # 3. Switch to SentenceTransformer (dim 768)
        embedder.set_model(method="sentence_transformers", model_name="st-model-large")
        self.assertEqual(embedder.get_embedding_dimension(), 768)
        
        # 4. Switch to another SentenceTransformer with different dimension
        mock_st_instance_small = MagicMock()
        mock_st_instance_small.get_sentence_embedding_dimension.return_value = 512
        self.mock_st_class.return_value = mock_st_instance_small
        
        embedder.set_model(method="sentence_transformers", model_name="st-model-small")
        self.assertEqual(embedder.get_embedding_dimension(), 512)


class TestFallbackReporting(unittest.TestCase):
    """get_model_info must not name a model that is not loaded.

    Model loading degrades to hash embedding without raising (documented on
    _initialize_model), so a caller's only signal is what get_model_info
    reports. Reporting the requested name while `method` is "fallback" made the
    two fields contradict each other, and the docstring promises model_name is
    the model "actually in use".
    """

    def test_fallback_does_not_report_the_requested_model_as_in_use(self):
        # Patch before constructing: the default method is "fastembed", so a
        # bare TextEmbedder() loads (and downloads) a real model wherever the
        # extra is installed, which is the case in CI.
        with patch(
            "semantica.embeddings.text_embedder.FASTEMBED_AVAILABLE", False
        ), patch(
            "semantica.embeddings.text_embedder.SENTENCE_TRANSFORMERS_AVAILABLE",
            False,
        ):
            embedder = TextEmbedder()
            embedder.set_model("fastembed", "BAAI/bge-small-en-v1.5")
            info = embedder.get_model_info()
        self.assertEqual(info["method"], "fallback")
        self.assertFalse(info["model_loaded"])
        self.assertNotEqual(
            info["model_name"],
            "BAAI/bge-small-en-v1.5",
            "model_name named a model that was never loaded",
        )
        self.assertEqual(info["requested_model_name"], "BAAI/bge-small-en-v1.5")

    def test_requested_name_is_preserved_for_diagnostics(self):
        with patch(
            "semantica.embeddings.text_embedder.FASTEMBED_AVAILABLE", False
        ), patch(
            "semantica.embeddings.text_embedder.SENTENCE_TRANSFORMERS_AVAILABLE",
            False,
        ):
            embedder = TextEmbedder()
            embedder.set_model("fastembed", "some/model")
            info = embedder.get_model_info()

        self.assertEqual(info["requested_model_name"], "some/model")

    def test_requested_name_follows_the_fastembed_config_override(self):
        """FastEmbed reads fastembed_model_name when that override is set.

        Reporting self.model_name would name a model the loader never tried.
        """
        with patch(
            "semantica.embeddings.text_embedder.FASTEMBED_AVAILABLE", False
        ), patch(
            "semantica.embeddings.text_embedder.SENTENCE_TRANSFORMERS_AVAILABLE",
            False,
        ):
            embedder = TextEmbedder(
                method="fastembed",
                model_name="declared/name",
                fastembed_model_name="override/name",
            )
            info = embedder.get_model_info()

        self.assertEqual(info["method"], "fallback")
        self.assertEqual(info["requested_model_name"], "override/name")


if __name__ == '__main__':
    unittest.main()
