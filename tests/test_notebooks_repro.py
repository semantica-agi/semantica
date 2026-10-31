import unittest
import sys
import os
import numpy as np

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

pytestmark = pytest.mark.integration

class TestNotebooks(unittest.TestCase):
    
    def test_12_embedding_generation(self):
        print("\nTesting 12_Embedding_Generation.ipynb logic...")
        try:
            from semantica.embeddings import EmbeddingGenerator, TextEmbedder
            
            # Test EmbeddingGenerator
            generator = EmbeddingGenerator()
            texts = [
                "Apple Inc. is a technology company.",
                "Microsoft Corporation develops software.",
                "Amazon provides cloud services."
            ]
            embeddings = generator.generate_embeddings(texts, data_type="text")
            
            self.assertEqual(len(embeddings), 3)
            # Assuming default dimension is not 0
            self.assertTrue(len(embeddings[0]) > 0)
            print("EmbeddingGenerator: OK")
            
            # Test TextEmbedder
            text_embedder = TextEmbedder()
            text = "Semantic knowledge graphs enable intelligent data processing."
            embedding = text_embedder.embed_text(text)
            
            self.assertTrue(len(embedding) > 0)
            print("TextEmbedder: OK")
            
        except Exception as e:
            self.fail(f"12_Embedding_Generation.ipynb failed: {e}")

    def test_13_vector_store_basic(self):
        # Needs the optional vectorstore-faiss extra; skip rather than fail on a
        # core install.
        pytest.importorskip("faiss")
        print("\nTesting 13_Vector_Store.ipynb logic...")
        try:
            from semantica.vector_store import VectorStore
            
            # Initialize
            store = VectorStore(backend="faiss", dimension=768)
            
            # Store vectors
            vectors = [np.random.rand(768).astype('float32') for _ in range(10)]
            metadata = [{"id": i, "text": f"doc_{i}"} for i in range(10)]
            
            vector_ids = store.store_vectors(vectors, metadata=metadata)
            self.assertEqual(len(vector_ids), 10)
            
            # Search
            query = np.random.rand(768).astype('float32')
            results = store.search_vectors(query, k=5)
            self.assertEqual(len(results), 5)
            print("VectorStore Basic: OK")
            
        except Exception as e:
            self.fail(f"13_Vector_Store.ipynb failed: {e}")

    def test_advanced_vector_store(self):
        # Needs the optional vectorstore-faiss extra; skip rather than fail on a
        # core install.
        pytest.importorskip("faiss")
        print("\nTesting Advanced_Vector_Store_and_Search.ipynb logic...")
        try:
            from semantica.vector_store import FAISSStore, HybridSearch, MetadataFilter, SearchRanker, NamespaceManager
            
            # Part 1: FAISSStore
            store = FAISSStore(dimension=768)
            index = store.create_index(index_type="hnsw", metric="L2", m=16)
            vectors = np.random.rand(100, 768).astype('float32')
            ids = [f"doc_{i}" for i in range(len(vectors))]
            store.add_vectors(vectors, ids=ids)
            
            query = np.random.rand(768).astype('float32')
            results = store.search_similar(query, k=5)
            # Check results structure
            self.assertEqual(len(results), 5)
            self.assertTrue(isinstance(results[0], dict))
            self.assertIn("id", results[0])
            print("FAISSStore: OK")
            
            # Part 2: Hybrid Search
            search = HybridSearch()
            # Mock data for hybrid search
            docs = [
                {"id": 0, "category": "Tech", "year": 2024},
                {"id": 1, "category": "Tech", "year": 2023},
                {"id": 2, "category": "Biz", "year": 2024}
            ]
            vecs = [np.random.rand(768).astype('float32') for _ in docs]
            meta = [{"category": d["category"], "year": d["year"]} for d in docs]
            v_ids = [f"doc_{d['id']}" for d in docs]
            
            # Filter
            filt = MetadataFilter().eq("category", "Tech").eq("year", 2024)
            # Note: search signature might vary, adapting to notebook usage
            # search.search(query, vectors, metadata, vector_ids, filter=filter1, k=10)
            results = search.search(query, vecs, meta, v_ids, filter=filt, k=10)
            # Should find doc 0
            found_ids = [r['id'] for r in results]
            self.assertIn("doc_0", found_ids)
            print("HybridSearch: OK")
            
            # Part 3: SearchRanker
            ranker = SearchRanker(strategy="reciprocal_rank_fusion")
            res1 = [{"id": "doc_1", "score": 0.9}, {"id": "doc_2", "score": 0.8}]
            res2 = [{"id": "doc_2", "score": 0.85}, {"id": "doc_3", "score": 0.7}]
            combined = ranker.rank([res1, res2])
            self.assertTrue(len(combined) > 0)
            print("SearchRanker: OK")
            
            # Part 4: NamespaceManager
            manager = NamespaceManager()
            ns_a = manager.create_namespace("ns_a", "Namespace A")
            manager.add_vector_to_namespace("doc_1", "ns_a")
            vecs_a = manager.get_namespace_vectors("ns_a")
            # Note: add_vector_to_namespace might need actual vector storage or just ID tracking depending on implementation
            # Notebook says: manager.add_vector_to_namespace(f"company_a_doc_{i}", "company_a")
            # And then: a_docs = manager.get_namespace_vectors("company_a")
            # Checking if it returns the list of IDs or vectors. 
            # Assuming it tracks IDs based on notebook context.
            self.assertTrue(len(vecs_a) > 0)
            print("NamespaceManager: OK")
            
        except Exception as e:
            self.fail(f"Advanced_Vector_Store_and_Search.ipynb failed: {e}")

if __name__ == '__main__':
    unittest.main()
