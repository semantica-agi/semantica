
import sys
import os
import unittest
import pytest
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from semantica.embeddings import TextEmbedder, EmbeddingGenerator

class TestModelSelection(unittest.TestCase):
    def test_dynamic_switching(self):
        # Needs the optional embeddings-local extra; skip rather than fail on a
        # core install. Both packages: the test switches to fastembed and
        # asserts the switch took, and set_model() falls back silently instead
        # of raising, so the surrounding `except ImportError` would not catch a
        # missing fastembed.
        pytest.importorskip("sentence_transformers")
        pytest.importorskip("fastembed")
        print("\nTesting Dynamic Model Switching...")
        embedder = TextEmbedder(method="sentence_transformers")
        info = embedder.get_model_info()
        self.assertEqual(info["method"], "sentence_transformers")
        
        # Switch to FastEmbed
        try:
            print("Switching to FastEmbed...")
            embedder.set_model("fastembed", "BAAI/bge-small-en-v1.5")
            info = embedder.get_model_info()
            self.assertEqual(info["method"], "fastembed")
            self.assertEqual(info["model_name"], "BAAI/bge-small-en-v1.5")
            
            emb = embedder.embed_text("Test")
            self.assertEqual(len(emb), 384)
            print("Switch successful.")
        except ImportError:
            print("FastEmbed not available for switching test")

    def test_generator_switching(self):
        # Needs the optional embeddings-local extra; skip rather than fail on a
        # core install. Both packages: the test switches to fastembed and
        # asserts the switch took, and set_model() falls back silently instead
        # of raising, so the surrounding `except ImportError` would not catch a
        # missing fastembed.
        pytest.importorskip("sentence_transformers")
        pytest.importorskip("fastembed")
        print("\nTesting EmbeddingGenerator Switching...")
        # Initialize with explicit method to ensure consistent starting state for test
        generator = EmbeddingGenerator(text={"method": "sentence_transformers"})
        
        # Default check
        self.assertEqual(generator.get_text_method(), "sentence_transformers")
        
        # Switch via generator
        try:
            generator.set_text_model("fastembed", "BAAI/bge-small-en-v1.5")
            self.assertEqual(generator.get_text_method(), "fastembed")
            print("Generator switch successful.")
        except ImportError:
            print("FastEmbed not available for generator test")

if __name__ == '__main__':
    with open("test_selection_results.txt", "w") as f:
        runner = unittest.TextTestRunner(stream=f, verbosity=2)
        unittest.main(testRunner=runner, exit=False)

