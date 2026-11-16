"""
Performance Benchmarks for Enhanced Vector Store

This module contains comprehensive performance benchmarks for the enhanced
vector store decision tracking functionality.

Benchmarks:
    - Vector storage and retrieval performance
    - Decision processing throughput
    - Hybrid search performance
    - KG algorithm integration performance
    - Memory usage and scalability
    - Concurrent operation performance
"""

import pytest
import numpy as np
import time
import threading
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any


from semantica.vector_store import VectorStore, DecisionEmbeddingPipeline, HybridSimilarityCalculator
from semantica.context import DecisionContext, ContextRetriever
from semantica.vector_store.decision_vector_methods import (
    quick_decision, find_precedents, batch_decisions
)

# psutil is not declared in any extra and is not in base-deps.txt.
# This module measures RSS through psutil in its benchmark helpers.
pytest.importorskip("psutil")
import psutil  # noqa: E402


class TestPerformanceBenchmarks:
    """Performance benchmarks for enhanced vector store."""
    
    def setup_method(self):
        """Set up benchmark environment."""
        self.vector_store = VectorStore(backend="inmemory", dimension=384)
        self.process = psutil.Process(os.getpid())
        
        # Performance thresholds (in seconds)
        self.thresholds = {
            "single_decision": 0.1,      # 100ms per decision
            "batch_decision": 0.01,       # 10ms per decision in batch
            "search_query": 0.05,         # 50ms per search
            "precedent_search": 0.1,      # 100ms per precedent search
            "context_retrieval": 0.15,    # 150ms for context retrieval
            "memory_per_decision": 1024,   # 1KB per decision
        }
    
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024
    
    def benchmark_single_decision_processing(self):
        """Benchmark single decision processing performance."""
        print("\n=== Benchmark: Single Decision Processing ===")
        
        # Test decision
        test_decision = {
            "scenario": "Credit limit increase request for performance testing",
            "reasoning": "Performance benchmark test decision with comprehensive metadata",
            "outcome": "approved",
            "confidence": 0.85,
            "entities": ["customer_perf", "account_test", "benchmark"],
            "category": "performance_test"
        }
        
        # Initialize context
        context = DecisionContext(vector_store=self.vector_store, graph_store=None)
        
        # Benchmark single decision
        start_time = time.time()
        start_memory = self.get_memory_usage()
        
        decision_id = context.record_decision(**test_decision)
        
        end_time = time.time()
        end_memory = self.get_memory_usage()
        
        processing_time = end_time - start_time
        memory_used = end_memory - start_memory
        
        print(f"✅ Single decision: {processing_time:.3f}s, {memory_used:.2f}MB")
        
        # Verify performance
        assert processing_time < self.thresholds["single_decision"], \
            f"Single decision too slow: {processing_time:.3f}s > {self.thresholds['single_decision']}s"
        
        assert memory_used < self.thresholds["memory_per_decision"] / 1024, \
            f"Memory usage too high: {memory_used:.2f}MB > {self.thresholds['memory_per_decision']/1024}MB"
        
        return processing_time, memory_used
    
    def benchmark_batch_processing(self):
        """Benchmark batch processing performance."""
        print("\n=== Benchmark: Batch Processing ===")
        
        # Generate test batch
        batch_size = 100
        test_batch = []
        for i in range(batch_size):
            test_batch.append({
                "scenario": f"Batch decision {i}: Credit assessment",
                "reasoning": f"Automated decision {i} for performance testing",
                "outcome": "approved" if i % 3 != 0 else "rejected",
                "confidence": 0.7 + (i % 10) * 0.03,
                "entities": [f"entity_{i}", f"account_{i}"],
                "category": "batch_test"
            })
        
        # Benchmark batch processing
        start_time = time.time()
        start_memory = self.get_memory_usage()
        
        results = self.vector_store.process_decision_batch(test_batch, batch_size=20)
        
        end_time = time.time()
        end_memory = self.get_memory_usage()
        
        total_time = end_time - start_time
        memory_used = end_memory - start_memory
        avg_time_per_decision = total_time / batch_size
        avg_memory_per_decision = (memory_used * 1024) / batch_size  # Convert to KB
        
        print(f"✅ Batch processing: {batch_size} decisions in {total_time:.3f}s")
        print(f"✅ Average: {avg_time_per_decision:.3f}s per decision, {avg_memory_per_decision:.1f}KB per decision")
        
        # Verify performance
        assert avg_time_per_decision < self.thresholds["batch_decision"], \
            f"Batch processing too slow: {avg_time_per_decision:.3f}s > {self.thresholds['batch_decision']}s"
        
        assert len(results) == batch_size, "Should process all decisions"
        assert all("vector_id" in result for result in results), "All should have vector IDs"
        
        return total_time, memory_used
    
    def benchmark_search_performance(self):
        """Benchmark search and retrieval performance."""
        print("\n=== Benchmark: Search Performance ===")
        
        # Create test data
        num_documents = 500
        for i in range(num_documents):
            vector = np.random.rand(384)
            metadata = {
                "content": f"Document {i} about various topics for search testing",
                "category": f"category_{i % 10}",
                "importance": (i % 5) / 4.0
            }
            self.vector_store.store_vectors([vector], [metadata])
        
        print(f"✅ Created {num_documents} test documents")
        
        # Benchmark different search types
        search_tests = [
            ("Vector Search", lambda: self.vector_store.search_vectors(np.random.rand(384), k=10)),
            ("Decision Search", lambda: self.vector_store.search_decisions("test query", limit=10)),
            ("Precedent Search", lambda: find_precedents("test scenario", limit=10)),
        ]
        
        search_results = {}
        
        for search_name, search_func in search_tests:
            # Warm up
            search_func()
            
            # Benchmark
            times = []
            for _ in range(10):
                start_time = time.time()
                results = search_func()
                end_time = time.time()
                times.append(end_time - start_time)
            
            avg_time = sum(times) / len(times)
            search_results[search_name] = avg_time
            
            print(f"✅ {search_name}: {avg_time:.3f}s average")
            
            # Verify performance
            assert avg_time < self.thresholds["search_query"], \
                f"{search_name} too slow: {avg_time:.3f}s > {self.thresholds['search_query']}s"
        
        return search_results
    
    def benchmark_hybrid_search_performance(self):
        """Benchmark hybrid search with different weight configurations."""
        print("\n=== Benchmark: Hybrid Search Performance ===")
        
        # Create decision context
        context = DecisionContext(vector_store=self.vector_store, graph_store=None)
        
        # Record test decisions
        for i in range(50):
            context.record_decision(
                scenario=f"Decision {i}: Credit assessment",
                reasoning=f"Reasoning for decision {i}",
                outcome="approved" if i % 2 == 0 else "rejected",
                confidence=0.7 + (i % 10) * 0.03,
                entities=[f"entity_{i}"],
                category="hybrid_test"
            )
        
        # Test different weight configurations
        weight_configs = [
            (1.0, 0.0, "Semantic Only"),
            (0.0, 1.0, "Structural Only"),
            (0.7, 0.3, "Default"),
            (0.5, 0.5, "Balanced"),
            (0.9, 0.1, "Semantic Heavy"),
            (0.1, 0.9, "Structural Heavy"),
        ]
        
        hybrid_results = {}
        
        for sem_weight, struct_weight, config_name in weight_configs:
            times = []
            for _ in range(5):
                start_time = time.time()
                precedents = context.find_similar_decisions(
                    scenario="Credit assessment",
                    limit=10,
                    semantic_weight=sem_weight,
                    structural_weight=struct_weight
                )
                end_time = time.time()
                times.append(end_time - start_time)
                
                # Verify results
                assert len(precedents) > 0, f"Should find precedents for {config_name}"
            
            avg_time = sum(times) / len(times)
            hybrid_results[config_name] = avg_time
            
            print(f"✅ {config_name}: {avg_time:.3f}s average")
            
            # Verify performance
            assert avg_time < self.thresholds["precedent_search"], \
                f"{config_name} too slow: {avg_time:.3f}s > {self.thresholds['precedent_search']}s"
        
        return hybrid_results
    
    def benchmark_context_retrieval_performance(self):
        """Benchmark context retriever performance."""
        print("\n=== Benchmark: Context Retrieval Performance ===")
        
        # Create context retriever
        retriever = ContextRetriever(vector_store=self.vector_store, knowledge_graph=None)
        
        # Store test context data
        for i in range(100):
            vector = np.random.rand(384)
            metadata = {
                "content": f"Context document {i} with comprehensive information",
                "type": f"type_{i % 5}",
                "source": f"source_{i % 3}"
            }
            self.vector_store.store_vectors([vector], [metadata])
        
        # Benchmark context retrieval
        retrieval_tests = [
            ("Basic Retrieval", lambda: retriever.retrieve("test query", max_results=10)),
            ("With Expansion", lambda: retriever.retrieve("test query", max_results=10, use_graph_expansion=True)),
            ("Decision Precedents", lambda: retriever.retrieve_decision_precedents("test scenario", limit=10)),
        ]
        
        retrieval_results = {}
        
        for retrieval_name, retrieval_func in retrieval_tests:
            times = []
            for _ in range(5):
                start_time = time.time()
                results = retrieval_func()
                end_time = time.time()
                times.append(end_time - start_time)
            
            avg_time = sum(times) / len(times)
            retrieval_results[retrieval_name] = avg_time
            
            print(f"✅ {retrieval_name}: {avg_time:.3f}s average")
            
            # Verify performance
            assert avg_time < self.thresholds["context_retrieval"], \
                f"{retrieval_name} too slow: {avg_time:.3f}s > {self.thresholds['context_retrieval']}s"
        
        return retrieval_results
    
    def benchmark_concurrent_operations(self):
        """Benchmark concurrent operation performance."""
        print("\n=== Benchmark: Concurrent Operations ===")
        
        # Create decision context
        context = DecisionContext(vector_store=self.vector_store, graph_store=None)
        
        # Concurrent decision recording
        def record_decision_batch(batch_id, batch_size=10):
            """Record a batch of decisions concurrently."""
            results = []
            for i in range(batch_size):
                decision_id = context.record_decision(
                    scenario=f"Concurrent decision {batch_id}-{i}",
                    reasoning=f"Concurrent processing test",
                    outcome="approved",
                    confidence=0.8,
                    entities=[f"entity_{batch_id}_{i}"],
                    category="concurrent_test"
                )
                results.append(decision_id)
            return results
        
        # Test concurrent batches
        num_batches = 10
        batch_size = 5
        
        start_time = time.time()
        start_memory = self.get_memory_usage()
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(record_decision_batch, i, batch_size)
                for i in range(num_batches)
            ]
            
            all_results = []
            for future in as_completed(futures):
                batch_results = future.result()
                all_results.extend(batch_results)
        
        end_time = time.time()
        end_memory = self.get_memory_usage()
        
        total_time = end_time - start_time
        memory_used = end_memory - start_memory
        total_decisions = len(all_results)
        avg_time_per_decision = total_time / total_decisions
        
        print(f"✅ Concurrent: {total_decisions} decisions in {total_time:.3f}s")
        print(f"✅ Average: {avg_time_per_decision:.3f}s per decision, {memory_used:.2f}MB total")
        
        # Verify performance
        assert avg_time_per_decision < self.thresholds["single_decision"] * 2, \
            f"Concurrent processing too slow: {avg_time_per_decision:.3f}s"
        
        assert len(all_results) == num_batches * batch_size, "Should process all decisions"
        
        return total_time, memory_used
    
    def benchmark_memory_scalability(self):
        """Benchmark memory usage scalability."""
        print("\n=== Benchmark: Memory Scalability ===")
        
        memory_snapshots = []
        
        # Test memory usage at different scales
        scales = [100, 500, 1000, 2000]
        
        for scale in scales:
            # Clear vector store
            self.vector_store = VectorStore(backend="inmemory", dimension=384)
            
            start_memory = self.get_memory_usage()
            
            # Add decisions at current scale
            context = DecisionContext(vector_store=self.vector_store, graph_store=None)
            
            for i in range(scale):
                context.record_decision(
                    scenario=f"Scalability test {i}",
                    reasoning=f"Memory usage test at scale {scale}",
                    outcome="approved",
                    confidence=0.8,
                    entities=[f"entity_{i}"],
                    category="scalability_test"
                )
            
            end_memory = self.get_memory_usage()
            memory_used = end_memory - start_memory
            memory_per_decision = (memory_used * 1024) / scale  # KB per decision
            
            memory_snapshots.append({
                "scale": scale,
                "total_memory_mb": memory_used,
                "memory_per_decision_kb": memory_per_decision
            })
            
            print(f"✅ Scale {scale}: {memory_used:.2f}MB total, {memory_per_decision:.1f}KB per decision")
            
            # Verify memory efficiency
            assert memory_per_decision < self.thresholds["memory_per_decision"], \
                f"Memory usage too high at scale {scale}: {memory_per_decision:.1f}KB"
        
        # Verify linear scalability
        if len(memory_snapshots) >= 3:
            # Check that memory growth is roughly linear
            first = memory_snapshots[0]
            last = memory_snapshots[-1]
            
            expected_growth = (last["scale"] / first["scale"]) * first["total_memory_mb"]
            actual_growth = last["total_memory_mb"]
            
            # Allow 50% overhead for indexing and metadata
            assert actual_growth < expected_growth * 1.5, \
                f"Memory growth not linear: expected ~{expected_growth:.1f}MB, got {actual_growth:.1f}MB"
        
        return memory_snapshots
    
    def benchmark_kg_algorithm_performance(self):
        """Benchmark KG algorithm integration performance."""
        print("\n=== Benchmark: KG Algorithm Performance ===")
        
        from unittest.mock import Mock
        from semantica.kg.path_finder import PathFinder
        from semantica.kg.community_detector import CommunityDetector
        from semantica.kg.centrality_calculator import CentralityCalculator
        
        # Mock KG algorithms
        mock_kg = Mock()
        mock_kg.get_neighbors.return_value = [f"neighbor_{i}" for i in range(5)]
        
        # Create retriever with KG algorithms
        retriever = ContextRetriever(vector_store=self.vector_store, knowledge_graph=mock_kg)
        
        # Store test data
        for i in range(50):
            vector = np.random.rand(384)
            metadata = {"content": f"KG test document {i}", "entities": [f"entity_{i}"]}
            self.vector_store.store_vectors([vector], [metadata])
        
        # Benchmark KG-enhanced context expansion
        entities = [{"name": f"entity_{i}", "type": "entity"} for i in range(10)]
        
        kg_times = []
        for _ in range(10):
            start_time = time.time()
            expanded = retriever._expand_decision_context(entities, max_hops=2)
            end_time = time.time()
            kg_times.append(end_time - start_time)
            
            assert len(expanded) > len(entities), "Should expand context"
        
        avg_kg_time = sum(kg_times) / len(kg_times)
        print(f"✅ KG Context Expansion: {avg_kg_time:.3f}s average")
        
        # Verify KG algorithm performance
        assert avg_kg_time < 0.5, f"KG processing too slow: {avg_kg_time:.3f}s"
        
        return avg_kg_time
    
    def run_comprehensive_benchmark(self):
        """Run comprehensive performance benchmark."""
        print("\n" + "="*60)
        print("COMPREHENSIVE PERFORMANCE BENCHMARK")
        print("="*60)
        
        results = {}
        
        # Run all benchmarks
        results["single_decision"] = self.benchmark_single_decision_processing()
        results["batch_processing"] = self.benchmark_batch_processing()
        results["search_performance"] = self.benchmark_search_performance()
        results["hybrid_search"] = self.benchmark_hybrid_search_performance()
        results["context_retrieval"] = self.benchmark_context_retrieval_performance()
        results["concurrent_operations"] = self.benchmark_concurrent_operations()
        results["memory_scalability"] = self.benchmark_memory_scalability()
        results["kg_algorithms"] = self.benchmark_kg_algorithm_performance()
        
        # Summary
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)
        
        print(f"✅ Single Decision: {results['single_decision'][0]:.3f}s")
        print(f"✅ Batch Processing: {results['batch_processing'][0]:.3f}s for 100 decisions")
        print(f"✅ Search Performance: {len(results['search_performance'])} search types tested")
        print(f"✅ Hybrid Search: {len(results['hybrid_search'])} weight configs tested")
        print(f"✅ Context Retrieval: {len(results['context_retrieval'])} retrieval types tested")
        print(f"✅ Concurrent Operations: {results['concurrent_operations'][0]:.3f}s for 50 decisions")
        print(f"✅ Memory Scalability: Tested up to {results['memory_scalability'][-1]['scale']} decisions")
        print(f"✅ KG Algorithms: {results['kg_algorithms']:.3f}s average")
        
        # Performance summary
        all_thresholds_met = True
        for benchmark_name, threshold_key in [
            ("single_decision", "single_decision"),
            ("batch_processing", "batch_decision"),
            ("kg_algorithms", "precedent_search"),
        ]:
            if benchmark_name in results:
                actual_time = results[benchmark_name][0] if isinstance(results[benchmark_name], tuple) else results[benchmark_name]
                if actual_time > self.thresholds[threshold_key]:
                    all_thresholds_met = False
                    print(f"❌ {benchmark_name}: {actual_time:.3f}s > {self.thresholds[threshold_key]}s")
        
        if all_thresholds_met:
            print("\n🎉 ALL PERFORMANCE BENCHMARKS PASSED!")
        else:
            print("\n⚠️  Some performance benchmarks exceeded thresholds")
        
        return results


class TestStressTests:
    """Stress tests for enhanced vector store."""
    
    def setup_method(self):
        """Set up stress test environment."""
        self.vector_store = VectorStore(backend="inmemory", dimension=384)
    
    def stress_test_high_volume_decisions(self):
        """Stress test with high volume of decisions."""
        print("\n=== Stress Test: High Volume Decisions ===")
        
        # Test with large number of decisions
        num_decisions = 1000
        context = DecisionContext(vector_store=self.vector_store, graph_store=None)
        
        start_time = time.time()
        
        # Process in batches to avoid memory issues
        batch_size = 50
        for batch_start in range(0, num_decisions, batch_size):
            batch_end = min(batch_start + batch_size, num_decisions)
            
            for i in range(batch_start, batch_end):
                context.record_decision(
                    scenario=f"Stress test decision {i}",
                    reasoning=f"High volume test decision {i}",
                    outcome="approved" if i % 2 == 0 else "rejected",
                    confidence=0.8,
                    entities=[f"entity_{i}"],
                    category="stress_test"
                )
            
            if batch_start % 100 == 0:
                print(f"✅ Processed {batch_end} decisions...")
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / num_decisions
        
        print(f"✅ Stress test: {num_decisions} decisions in {total_time:.1f}s")
        print(f"✅ Average: {avg_time:.3f}s per decision")
        
        # Verify all decisions processed
        total_vectors = len(self.vector_store.vectors)
        assert total_vectors >= num_decisions, f"Should have at least {num_decisions} vectors, got {total_vectors}"
        
        # Test search performance under load
        search_start = time.time()
        precedents = context.find_similar_decisions("Stress test", limit=20)
        search_time = time.time() - search_start
        
        print(f"✅ Search under load: {search_time:.3f}s for {len(precedents)} results")
        
        assert len(precedents) > 0, "Should find precedents even under load"
        assert search_time < 1.0, "Search should remain fast under load"
    
    def stress_test_memory_pressure(self):
        """Stress test under memory pressure."""
        print("\n=== Stress Test: Memory Pressure ===")
        
        import psutil
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create decisions with large metadata
        context = DecisionContext(vector_store=self.vector_store, graph_store=None)
        
        for i in range(200):
            # Large metadata to stress memory
            large_metadata = {
                "scenario": f"Memory stress test {i}",
                "reasoning": "A" * 1000,  # Large reasoning string
                "outcome": "approved",
                "confidence": 0.8,
                "entities": [f"entity_{j}" for j in range(10)],  # Many entities
                "category": "memory_stress",
                "large_field": "X" * 5000,  # Very large field
            }
            
            context.record_decision(**large_metadata)
            
            if i % 50 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory
                print(f"✅ {i} decisions: {memory_growth:.1f}MB memory growth")
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024
        total_memory_growth = final_memory - initial_memory
        
        print(f"✅ Total memory growth: {total_memory_growth:.1f}MB")
        
        # Should not grow excessively (allow 100MB for 200 decisions)
        assert total_memory_growth < 100, f"Memory growth too high: {total_memory_growth:.1f}MB"
        
        # Verify functionality still works
        precedents = context.find_similar_decisions("Memory stress", limit=5)
        assert len(precedents) > 0, "Should still work under memory pressure"


if __name__ == "__main__":
    # Run performance benchmarks
    pytest.main([__file__, "-v", "-s"])
