
import pytest
from unittest.mock import MagicMock, patch
from typing import List, Type, Union
from pydantic import BaseModel, ValidationError

from semantica.semantic_extract.providers import BaseProvider
from semantica.semantic_extract.methods import (
    extract_entities_llm, 
    extract_relations_llm, 
    extract_triplets_llm
)
from semantica.semantic_extract.schemas import EntitiesResponse, RelationsResponse, TripletsResponse
from semantica.semantic_extract.ner_extractor import Entity
from semantica.semantic_extract.relation_extractor import Relation

# Mock Pydantic models for responses
class MockEntity(BaseModel):
    text: str
    label: str
    start: int = 0
    end: int = 0
    confidence: float = 1.0

class MockEntitiesResponse(BaseModel):
    entities: List[MockEntity]

class MockRelation(BaseModel):
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0

class MockRelationsResponse(BaseModel):
    relations: List[MockRelation]

class MockTriplet(BaseModel):
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0

class MockTripletsResponse(BaseModel):
    triplets: List[MockTriplet]

class MockProvider(BaseProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.generate_typed_called = False
        self.generate_structured_called = False
        self.model = "mock-model"
        self.is_available_val = True

    def is_available(self) -> bool:
        return self.is_available_val

    def generate(self, prompt: str, **kwargs) -> str:
        return "{}"

    def generate_structured(self, prompt: str, **kwargs) -> Union[dict, list]:
        self.generate_structured_called = True
        if "entities" in prompt.lower():
            return [{"text": "Apple", "label": "ORG", "start": 0, "end": 5}]
        elif "relations" in prompt.lower():
            return [{"subject": "Steve Jobs", "predicate": "founded", "object": "Apple"}]
        elif "triplets" in prompt.lower():
            return [{"subject": "Steve Jobs", "predicate": "founded", "object": "Apple"}]
        return {}

    def generate_typed(
        self, 
        prompt: str, 
        schema: Type[BaseModel], 
        max_retries: int = 3, 
        **kwargs
    ) -> BaseModel:
        self.generate_typed_called = True
        
        if schema.__name__ == "EntitiesResponse":
            return EntitiesResponse(entities=[
                {"text": "Apple", "label": "ORG", "start_char": 0, "end_char": 5, "confidence": 0.99}
            ])
        elif schema.__name__ == "RelationsResponse":
            return RelationsResponse(relations=[
                {"subject": "Steve Jobs", "predicate": "founded", "object": "Apple", "confidence": 0.95}
            ])
        elif schema.__name__ == "TripletsResponse":
            return TripletsResponse(triplets=[
                {"subject": "Steve Jobs", "predicate": "founded", "object": "Apple", "confidence": 0.95}
            ])
        return schema()

@pytest.fixture
def mock_provider():
    return MockProvider()

@patch("semantica.semantic_extract.methods.create_provider")
def test_extract_entities_typed(mock_create_provider, mock_provider):
    mock_create_provider.return_value = mock_provider
    
    text = "Apple was founded by Steve Jobs."
    entities = extract_entities_llm(
        text, 
        provider="mock", 
        structured_output_mode="typed"
    )
    
    assert mock_provider.generate_typed_called
    assert len(entities) == 1
    assert entities[0].text == "Apple"
    assert entities[0].label == "ORG"
    assert entities[0].metadata["extraction_method"] == "llm_typed"

@patch("semantica.semantic_extract.methods.create_provider")
def test_extract_entities_legacy(mock_create_provider, mock_provider):
    mock_create_provider.return_value = mock_provider
    
    text = "Apple was founded by Steve Jobs."
    entities = extract_entities_llm(
        text, 
        provider="mock", 
        structured_output_mode="legacy"
    )
    
    # Legacy mode now redirects to typed mode
    assert mock_provider.generate_typed_called
    assert not mock_provider.generate_structured_called
    assert len(entities) == 1
    assert entities[0].text == "Apple"
    assert entities[0].label == "ORG"
    assert entities[0].metadata["extraction_method"] == "llm_typed"

@patch("semantica.semantic_extract.methods.create_provider")
def test_extract_relations_typed(mock_create_provider, mock_provider):
    mock_create_provider.return_value = mock_provider
    
    text = "Steve Jobs founded Apple."
    entities = [
        Entity(text="Steve Jobs", label="PERSON", start_char=0, end_char=10),
        Entity(text="Apple", label="ORG", start_char=19, end_char=24)
    ]
    
    relations = extract_relations_llm(
        text,
        entities=entities,
        provider="mock",
        structured_output_mode="typed"
    )
    
    assert mock_provider.generate_typed_called
    assert len(relations) == 1
    assert relations[0].subject.text == "Steve Jobs"
    assert relations[0].object.text == "Apple"
    assert relations[0].predicate == "founded"
    assert relations[0].metadata["extraction_method"] == "llm_typed"

@patch("semantica.semantic_extract.methods.create_provider")
def test_extract_triplets_typed(mock_create_provider, mock_provider):
    mock_create_provider.return_value = mock_provider
    
    text = "Steve Jobs founded Apple."
    
    triplets = extract_triplets_llm(
        text,
        provider="mock",
        structured_output_mode="typed"
    )
    
    assert mock_provider.generate_typed_called
    assert len(triplets) == 1
    assert triplets[0].subject == "Steve Jobs"
    assert triplets[0].object == "Apple"
    assert triplets[0].predicate == "founded"
    assert triplets[0].metadata["extraction_method"] == "llm_typed"

if __name__ == "__main__":
    pytest.main([__file__])
