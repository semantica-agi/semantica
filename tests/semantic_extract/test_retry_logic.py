
import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os
from typing import List, Optional
from pydantic import BaseModel
import importlib.util

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Save originals before injecting mocks so they can be restored after import.
_MOCKED_MODULES = ["spacy", "instructor", "groq", "openai", "sentence_transformers", "transformers"]
_original_modules = {k: sys.modules.get(k) for k in _MOCKED_MODULES}

# Mock external dependencies with __spec__ for importlib checks
mock_spacy = MagicMock()
mock_spacy.__spec__ = MagicMock()
sys.modules["spacy"] = mock_spacy

sys.modules["instructor"] = MagicMock()
sys.modules["groq"] = MagicMock()

# Better mock for openai
mock_openai = MagicMock()
mock_openai.__spec__ = MagicMock()
sys.modules["openai"] = mock_openai

# Mock sentence_transformers and transformers to avoid heavy imports and dependency checks
sys.modules["sentence_transformers"] = MagicMock()
mock_transformers = MagicMock()
mock_transformers.__spec__ = MagicMock()
sys.modules["transformers"] = mock_transformers

from semantica.semantic_extract import NERExtractor
from semantica.semantic_extract.methods import extract_entities_llm, _extract_entities_chunked, extract_relations_llm, extract_triplets_llm
from semantica.semantic_extract.providers import BaseProvider

# Restore real sys.modules entries now that the mocks have served their purpose
# for the imports above. Leaving them in place would poison other test modules
# (e.g. test_pr482_deepseek_openai) that need the real packages at test run time.
for _key, _original in _original_modules.items():
    if _original is None:
        sys.modules.pop(_key, None)
    else:
        sys.modules[_key] = _original


class EntitiesResponse(BaseModel):
    entities: List[dict]

class TestRetryLogic(unittest.TestCase):

    def setUp(self):
        self.mock_provider = MagicMock()
        self.mock_provider.is_available.return_value = True
        self.mock_provider.generate_typed.return_value = MagicMock(entities=[])
        # Clear the module-level extraction cache to avoid cross-test interference
        from semantica.semantic_extract.methods import _result_cache
        _result_cache.clear()
        
    def test_ner_extractor_init_default(self):
        """Test default max_retries in NERExtractor"""
        ner = NERExtractor(method="llm", provider="test")
        # Check internal config, max_retries not in config means default behavior downstream
        self.assertIsNone(ner.config.get("max_retries"))

    def test_ner_extractor_init_custom(self):
        """Test custom max_retries in NERExtractor init"""
        ner = NERExtractor(method="llm", provider="test", max_retries=5)
        self.assertEqual(ner.config.get("max_retries"), 5)

    @patch('semantica.semantic_extract.methods.create_provider')
    def test_extract_entities_uses_init_value(self, mock_create_provider):
        """Test extract_entities uses initialized max_retries"""
        mock_create_provider.return_value = self.mock_provider
        
        ner = NERExtractor(method="llm", provider="test", max_retries=5)
        ner.extract_entities("test text")
        
        # Verify generate_typed called with max_retries=5
        args, kwargs = self.mock_provider.generate_typed.call_args
        self.assertEqual(kwargs.get("max_retries"), 5)

    @patch('semantica.semantic_extract.methods.create_provider')
    def test_extract_entities_override(self, mock_create_provider):
        """Test extract_entities override max_retries"""
        mock_create_provider.return_value = self.mock_provider
        
        ner = NERExtractor(method="llm", provider="test", max_retries=5)
        # Override with 1
        ner.extract_entities("test text", max_retries=1)
        
        args, kwargs = self.mock_provider.generate_typed.call_args
        self.assertEqual(kwargs.get("max_retries"), 1)

    @patch('semantica.semantic_extract.methods.create_provider')
    def test_chunked_extraction_propagation(self, mock_create_provider):
        """Test max_retries propagation in chunked extraction"""
        mock_create_provider.return_value = self.mock_provider
        
        # Patch TextSplitter where it lives
        with patch('semantica.split.TextSplitter') as MockSplitter:
            mock_splitter_instance = MockSplitter.return_value
            # Mock split to return 2 chunks
            mock_chunk1 = MagicMock()
            mock_chunk1.text = "chunk1"
            mock_chunk2 = MagicMock()
            mock_chunk2.text = "chunk2"
            mock_splitter_instance.split.return_value = [mock_chunk1, mock_chunk2]
            
            # Force chunking by setting max_text_length small
            extract_entities_llm(
                "very long text",
                provider="test",
                model="test-model",
                max_text_length=10, # Force chunking
                max_retries=7,
                structured_output_mode="typed"
            )
            
            # Check if generate_typed was called with max_retries=7 for chunks
            # It should be called twice (once for each chunk)
            self.assertEqual(self.mock_provider.generate_typed.call_count, 2)
            
            # Check arguments of the calls
            call_args_list = self.mock_provider.generate_typed.call_args_list
            for args, kwargs in call_args_list:
                self.assertEqual(kwargs.get("max_retries"), 7)

    def test_provider_base_logic(self):
        """Test BaseProvider logic for max_retries with manual loop"""
        provider = BaseProvider()
        provider.client = MagicMock()
        provider.logger = MagicMock()
        provider.generate_structured = MagicMock(side_effect=Exception("Fail"))
        
        # Mock instructor failing
        with patch('semantica.semantic_extract.providers.instructor') as mock_instructor:
             # Make instructor client fail
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("Instructor Fail")
            mock_instructor.from_provider.return_value = mock_client
            mock_instructor.from_openai.return_value = mock_client
            
            # Run with max_retries=2
            try:
                provider.generate_typed("prompt", EntitiesResponse, max_retries=2)
            except Exception:
                pass
            
            # Should try manual generation exactly 2 times
            self.assertEqual(provider.generate_structured.call_count, 2)

    def test_provider_zero_retries(self):
        """Test BaseProvider with max_retries=0"""
        provider = BaseProvider()
        provider.client = MagicMock()
        provider.logger = MagicMock()
        provider.generate_structured = MagicMock(side_effect=Exception("Fail"))
        
        # Mock instructor failing
        with patch('semantica.semantic_extract.providers.instructor') as mock_instructor:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("Instructor Fail")
            mock_instructor.from_provider.return_value = mock_client
            mock_instructor.from_openai.return_value = mock_client
            
            try:
                provider.generate_typed("prompt", EntitiesResponse, max_retries=0)
            except Exception:
                pass
            
            # Should NOT try manual generation loop (range(0) is empty)
            self.assertEqual(provider.generate_structured.call_count, 0)

    @patch('semantica.semantic_extract.methods.create_provider')
    def test_relations_retry_propagation(self, mock_create_provider):
        """Test max_retries propagation in relation extraction"""
        mock_create_provider.return_value = self.mock_provider
        
        # Create a mock entity
        mock_entity = MagicMock()
        mock_entity.text = "entity"
        mock_entity.start_char = 0
        mock_entity.end_char = 5
        
        extract_relations_llm(
            "test text",
            entities=[mock_entity],
            provider="test",
            max_retries=4
        )
        
        args, kwargs = self.mock_provider.generate_typed.call_args
        self.assertEqual(kwargs.get("max_retries"), 4)

    @patch('semantica.semantic_extract.methods.create_provider')
    def test_relations_chunked_propagation(self, mock_create_provider):
        """Test max_retries propagation in chunked relation extraction"""
        mock_create_provider.return_value = self.mock_provider
        
        with patch('semantica.split.TextSplitter') as MockSplitter:
            mock_splitter_instance = MockSplitter.return_value
            mock_chunk1 = MagicMock()
            mock_chunk1.text = "chunk1"
            mock_chunk1.start_index = 0
            mock_chunk1.end_index = 6
            mock_splitter_instance.split.return_value = [mock_chunk1]
            
            # Create a mock entity
            mock_entity = MagicMock()
            mock_entity.text = "entity"
            mock_entity.start_char = 0
            mock_entity.end_char = 5
            
            extract_relations_llm(
                "very long text",
                entities=[mock_entity],
                provider="test",
                max_text_length=10,
                max_retries=6
            )
            
            # Check call count - should be called for the chunk
            # Note: _extract_relations_chunked creates a new future for each chunk
            # which calls extract_relations_llm, which calls generate_typed
            self.assertEqual(self.mock_provider.generate_typed.call_count, 1)
            
            args, kwargs = self.mock_provider.generate_typed.call_args
            self.assertEqual(kwargs.get("max_retries"), 6)

    @patch('semantica.semantic_extract.methods.create_provider')
    def test_triplets_retry_propagation(self, mock_create_provider):
        """Test max_retries propagation in triplet extraction"""
        mock_create_provider.return_value = self.mock_provider
        
        extract_triplets_llm(
            "test text",
            entities=[],
            relations=[],
            provider="test",
            max_retries=7
        )
        
        args, kwargs = self.mock_provider.generate_typed.call_args
        self.assertEqual(kwargs.get("max_retries"), 7)

    @patch('semantica.semantic_extract.methods.create_provider')
    def test_triplets_chunked_propagation(self, mock_create_provider):
        """Test max_retries propagation in chunked triplet extraction"""
        mock_create_provider.return_value = self.mock_provider
        
        with patch('semantica.split.TextSplitter') as MockSplitter:
            mock_splitter_instance = MockSplitter.return_value
            mock_chunk1 = MagicMock()
            mock_chunk1.text = "chunk1"
            mock_chunk1.start_index = 0
            mock_chunk1.end_index = 6
            mock_splitter_instance.split.return_value = [mock_chunk1]
            
            # Use max_text_length > 100 to pass the minimum viable chunk size check
            # and make text longer than that
            extract_triplets_llm(
                "very long text " * 20, # length > 101
                entities=[],
                relations=[],
                provider="test",
                max_text_length=101,
                max_retries=8
            )
            
            # Check call count
            self.assertEqual(self.mock_provider.generate_typed.call_count, 1)
            
            args, kwargs = self.mock_provider.generate_typed.call_args
            self.assertEqual(kwargs.get("max_retries"), 8)

if __name__ == "__main__":
    unittest.main()
