import sys
import traceback
from unittest.mock import MagicMock, patch

import pytest

from semantica.semantic_extract.methods import (
    extract_entities_huggingface,
    extract_relations_huggingface,
    extract_triplets_huggingface,
)
from semantica.semantic_extract.ner_extractor import Entity

# transformers and torch are imported lazily by the HuggingFace model loader, so
# they are swapped in only while the test runs. Replacing them in sys.modules at
# import time would leak into every test collected after this module.
mock_transformers = MagicMock()
mock_pipeline = MagicMock()
mock_transformers.pipeline = mock_pipeline
mock_torch = MagicMock()
mock_torch.cuda.is_available.return_value = False
MOCKED_MODULES = {"transformers": mock_transformers, "torch": mock_torch}


@pytest.fixture(autouse=True)
def mocked_hf_modules():
    with patch.dict(sys.modules, MOCKED_MODULES):
        yield


def test_enhanced_impl():
    print("Testing enhanced implementation...", flush=True)

    try:
        # 1. Test NER with aggregation strategy
        print("\n--- Testing NER ---", flush=True)
        
        # Setup mock pipeline return value
        mock_ner_pipeline = MagicMock()
        mock_ner_pipeline.return_value = [
            {"entity_group": "PERSON", "score": 0.99, "word": "Elon Musk", "start": 0, "end": 9},
        ]
        
        # Configure pipeline side effect
        def pipeline_side_effect(task, **kwargs):
            if task == "ner": return mock_ner_pipeline
            return MagicMock()
            
        mock_pipeline.side_effect = pipeline_side_effect
        
        # Test calling with aggregation_strategy
        entities = extract_entities_huggingface(
            "Elon Musk founded SpaceX.", 
            model="dslim/bert-base-NER", 
            aggregation_strategy="max"
        )
        print(f"Entities: {entities}", flush=True)
        
        # Verify aggregation_strategy was passed
        mock_pipeline.assert_any_call(
            "ner", 
            model="dslim/bert-base-NER", 
            device=-1, 
            aggregation_strategy="max",
            tokenizer=None
        )

        # 2. Test Relations with Input Formatting
        print("\n--- Testing Relations ---", flush=True)
        e1 = Entity(text="Elon Musk", label="PERSON", start_char=0, end_char=9)
        e2 = Entity(text="SpaceX", label="ORG", start_char=18, end_char=24)
        
        mock_rel_pipeline = MagicMock()
        mock_rel_pipeline.return_value = [{"label": "founded", "score": 0.9}]
        
        # Update pipeline mock to return rel pipeline
        def pipeline_side_effect_rel(task, **kwargs):
            if task == "ner": return mock_ner_pipeline
            if task == "text-classification": return mock_rel_pipeline
            return MagicMock()
            
        mock_pipeline.side_effect = pipeline_side_effect_rel
        
        relations = extract_relations_huggingface(
            "Elon Musk founded SpaceX.", 
            entities=[e1, e2], 
            model="some-relation-model"
        )
        print(f"Relations: {relations}", flush=True)
        
        # Verify input formatting
        # Check if ANY call contained the correct formatting
        found_match = False
        for call in mock_rel_pipeline.call_args_list:
            args, _ = call
            if "<subj> Elon Musk </subj>" in args[0] and "<obj> SpaceX </obj>" in args[0]:
                found_match = True
                break
        
        if not found_match:
            print("Failed to find expected call args in:", flush=True)
            for call in mock_rel_pipeline.call_args_list:
                print(f"  {call[0]}", flush=True)
                
        assert found_match, "Did not find relation call with Elon Musk as subject"

        # 3. Test Triplets with REBEL parsing
        print("\n--- Testing Triplets ---", flush=True)
        
        # Mock Tokenizer and Model
        mock_tokenizer_instance = MagicMock()
        mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer_instance
        mock_tokenizer_instance.encode.return_value = MagicMock()
        # Mock decode to return REBEL format
        mock_tokenizer_instance.decode.return_value = "<s><triplet> Elon Musk <subj> founded <obj> SpaceX <triplet> SpaceX <subj> created <obj> Starship</s>"
        
        mock_model_instance = MagicMock()
        mock_transformers.AutoModelForSeq2SeqLM.from_pretrained.return_value = mock_model_instance
        mock_model_instance.generate.return_value = [MagicMock()]
        
        triplets = extract_triplets_huggingface(
            "Elon Musk founded SpaceX and created Starship.",
            model="Babelscape/rebel-large"
        )
        print(f"Triplets: {triplets}", flush=True)
        
        # Verify parsing
        assert len(triplets) == 2
        assert triplets[0].subject == "Elon Musk"
        assert triplets[0].predicate == "founded"
        assert triplets[0].object == "SpaceX"
        assert triplets[1].subject == "SpaceX"
        assert triplets[1].predicate == "created"
        assert triplets[1].object == "Starship"
        
        # Verify skip_special_tokens=False was passed
        mock_tokenizer_instance.decode.assert_called_with(
            mock_model_instance.generate.return_value[0], 
            skip_special_tokens=False
        )

    except Exception as e:
        print(f"Error during test execution: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        with patch.dict(sys.modules, MOCKED_MODULES):
            test_enhanced_impl()
        print("\nAll tests passed!", flush=True)
    except Exception as e:
        print(f"\nTest failed: {e}", flush=True)
        traceback.print_exc()
