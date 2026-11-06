"""
Performance and Latency Tests for Enhanced Change Management Module

This module provides comprehensive performance testing for all change management
components including storage backends, version managers, and diff algorithms.
"""

import gc
import time
import tempfile
import os
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple

import pytest

# psutil is not declared in any extra and is not in base-deps.txt.
# Every test class's setup_method builds a PerformanceTestSuite, which
# calls psutil.Process() to measure RSS, so the whole module needs it.
pytest.importorskip("psutil")
import psutil  # noqa: E402

from semantica.change_management import (
    TemporalVersionManager,
    OntologyVersionManager,
    InMemoryVersionStorage,
    SQLiteVersionStorage,
    ChangeLogEntry,
    compute_checksum,
    verify_checksum
)


class PerformanceTestSuite:
    """Comprehensive performance test suite for change management module."""
    
    def __init__(self):
        """Initialize performance test suite."""
        self.results = {}
        self.process = psutil.Process()
    
    def measure_time(self, func, *args, **kwargs) -> Tuple[Any, float]:
        """Measure execution time of a function.

        Garbage collection is paused for the timed call, as ``timeit`` does.
        Late in the full suite the heap holds millions of objects, and a full
        collection that happens to start inside the call added ~0.8s to one
        snapshot and failed its 500ms bound on CI (#2167).
        """
        gc_was_enabled = gc.isenabled()
        gc.disable()
        try:
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
        finally:
            if gc_was_enabled:
                gc.enable()
        return result, end_time - start_time
    
    def measure_memory(self, func, *args, **kwargs) -> Tuple[Any, float]:
        """Measure memory usage of a function."""
        initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        result = func(*args, **kwargs)
        final_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        return result, final_memory - initial_memory
    
    def generate_test_graph(self, num_entities: int, num_relationships: int) -> Dict[str, Any]:
        """Generate test knowledge graph with specified size."""
        entities = []
        for i in range(num_entities):
            entities.append({
                "id": f"entity_{i}",
                "name": f"Entity {i}",
                "type": f"Type_{i % 10}",
                "description": f"Description for entity {i}" * 5,  # Make it longer
                "properties": {
                    "category": f"Category_{i % 5}",
                    "score": i * 0.1,
                    "active": i % 2 == 0
                }
            })
        
        relationships = []
        for i in range(num_relationships):
            source_idx = i % num_entities
            target_idx = (i + 1) % num_entities
            relationships.append({
                "source": f"entity_{source_idx}",
                "target": f"entity_{target_idx}",
                "type": f"relation_type_{i % 5}",
                "weight": i * 0.01,
                "properties": {
                    "strength": i % 10,
                    "confidence": 0.8 + (i % 20) * 0.01
                }
            })
        
        return {
            "entities": entities,
            "relationships": relationships
        }
    
    def generate_test_ontology(self, num_classes: int, num_properties: int) -> Dict[str, Any]:
        """Generate test ontology with specified size."""
        classes = [f"Class_{i}" for i in range(num_classes)]
        properties = [f"property_{i}" for i in range(num_properties)]
        individuals = [f"individual_{i}" for i in range(num_classes // 2)]
        axioms = [f"Class_{i} hasProperty property_{i % num_properties}" for i in range(num_classes)]
        
        return {
            "uri": "https://test.com/ontology",
            "version_info": {"version": "1.0", "date": "2024-01-30"},
            "structure": {
                "classes": classes,
                "properties": properties,
                "individuals": individuals,
                "axioms": axioms
            }
        }


class TestMeasureTime:
    """measure_time keeps a garbage collection pause out of the timing (#2167)."""

    def test_gc_is_paused_during_the_call_and_restored_after(self):
        suite = PerformanceTestSuite()
        enabled, _ = suite.measure_time(gc.isenabled)
        assert enabled is False
        assert gc.isenabled()

    def test_gc_is_restored_when_the_call_raises(self):
        def boom():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            PerformanceTestSuite().measure_time(boom)
        assert gc.isenabled()

    def test_gc_stays_disabled_if_it_was_disabled_before(self):
        gc.disable()
        try:
            PerformanceTestSuite().measure_time(lambda: None)
            assert not gc.isenabled()
        finally:
            gc.enable()


class TestStoragePerformance:
    """Test performance of storage backends."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.perf_suite = PerformanceTestSuite()
        self.test_sizes = [10, 50, 100, 500, 1000]
    
    def test_inmemory_storage_performance(self):
        """Test InMemoryVersionStorage performance across different data sizes."""
        print("\n=== InMemoryVersionStorage Performance ===")
        
        storage = InMemoryVersionStorage()
        results = {}
        
        for size in self.test_sizes:
            graph = self.perf_suite.generate_test_graph(size, size * 2)
            snapshot = {
                "label": f"test_v{size}",
                "timestamp": "2024-01-30T12:00:00Z",
                "author": "test@example.com",
                "description": f"Test snapshot with {size} entities",
                "entities": graph["entities"],
                "relationships": graph["relationships"],
                "checksum": compute_checksum(graph)
            }
            
            # Test save performance
            _, save_time = self.perf_suite.measure_time(storage.save, snapshot)
            
            # Test get performance
            _, get_time = self.perf_suite.measure_time(storage.get, f"test_v{size}")
            
            # Test list performance
            _, list_time = self.perf_suite.measure_time(storage.list_all)
            
            results[size] = {
                "save_time": save_time,
                "get_time": get_time,
                "list_time": list_time
            }
            
            print(f"Size {size:4d}: Save={save_time*1000:6.2f}ms, Get={get_time*1000:6.2f}ms, List={list_time*1000:6.2f}ms")
        
        # Verify performance requirements
        assert results[1000]["save_time"] < 0.1, "Large snapshot save should be under 100ms"
        assert results[1000]["get_time"] < 0.05, "Large snapshot retrieval should be under 50ms"
        
        self.perf_suite.results["inmemory_storage"] = results
    
    def test_sqlite_storage_performance(self):
        """Test SQLiteVersionStorage performance across different data sizes."""
        print("\n=== SQLiteVersionStorage Performance ===")
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            storage = SQLiteVersionStorage(db_path)
            results = {}
            
            for size in self.test_sizes:
                graph = self.perf_suite.generate_test_graph(size, size * 2)
                snapshot = {
                    "label": f"test_v{size}",
                    "timestamp": "2024-01-30T12:00:00Z",
                    "author": "test@example.com",
                    "description": f"Test snapshot with {size} entities",
                    "entities": graph["entities"],
                    "relationships": graph["relationships"],
                    "checksum": compute_checksum(graph)
                }
                
                # Test save performance
                _, save_time = self.perf_suite.measure_time(storage.save, snapshot)
                
                # Test get performance
                _, get_time = self.perf_suite.measure_time(storage.get, f"test_v{size}")
                
                # Test list performance
                _, list_time = self.perf_suite.measure_time(storage.list_all)
                
                results[size] = {
                    "save_time": save_time,
                    "get_time": get_time,
                    "list_time": list_time
                }
                
                print(f"Size {size:4d}: Save={save_time*1000:6.2f}ms, Get={get_time*1000:6.2f}ms, List={list_time*1000:6.2f}ms")
            
            # Verify performance requirements
            assert results[1000]["save_time"] < 0.5, "Large snapshot save should be under 500ms"
            assert results[1000]["get_time"] < 0.1, "Large snapshot retrieval should be under 100ms"
            
            self.perf_suite.results["sqlite_storage"] = results
            
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
    
    def test_storage_comparison(self):
        """Compare performance between InMemory and SQLite storage."""
        print("\n=== Storage Backend Comparison ===")
        
        # Test with medium-sized dataset
        test_size = 500
        graph = self.perf_suite.generate_test_graph(test_size, test_size * 2)
        snapshot = {
            "label": f"comparison_test",
            "timestamp": "2024-01-30T12:00:00Z",
            "author": "test@example.com",
            "description": f"Comparison test with {test_size} entities",
            "entities": graph["entities"],
            "relationships": graph["relationships"],
            "checksum": compute_checksum(graph)
        }
        
        # InMemory performance
        inmemory_storage = InMemoryVersionStorage()
        _, inmemory_save = self.perf_suite.measure_time(inmemory_storage.save, snapshot)
        _, inmemory_get = self.perf_suite.measure_time(inmemory_storage.get, "comparison_test")
        
        # SQLite performance
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            sqlite_storage = SQLiteVersionStorage(db_path)
            _, sqlite_save = self.perf_suite.measure_time(sqlite_storage.save, snapshot)
            _, sqlite_get = self.perf_suite.measure_time(sqlite_storage.get, "comparison_test")
            
            print(f"InMemory: Save={inmemory_save*1000:6.2f}ms, Get={inmemory_get*1000:6.2f}ms")
            print(f"SQLite:   Save={sqlite_save*1000:6.2f}ms, Get={sqlite_get*1000:6.2f}ms")
            print(f"SQLite overhead: Save={sqlite_save/inmemory_save:.1f}x, Get={sqlite_get/inmemory_get:.1f}x")
            
            # SQLite should be reasonably close to InMemory for typical use cases
            assert sqlite_save < inmemory_save * 10, "SQLite save shouldn't be more than 10x slower"
            assert sqlite_get < inmemory_get * 5, "SQLite get shouldn't be more than 5x slower"
            
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)


class TestVersionManagerPerformance:
    """Test performance of enhanced version managers."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.perf_suite = PerformanceTestSuite()
        self.test_sizes = [50, 100, 500, 1000, 2000]
    
    def test_temporal_version_manager_performance(self):
        """Test TemporalVersionManager performance."""
        print("\n=== TemporalVersionManager Performance ===")
        
        manager = TemporalVersionManager()
        results = {}
        
        for size in self.test_sizes:
            graph = self.perf_suite.generate_test_graph(size, size * 2)
            
            # Test snapshot creation performance
            _, create_time = self.perf_suite.measure_time(
                manager.create_snapshot,
                graph,
                f"perf_test_v{size}",
                "test@example.com",
                f"Performance test with {size} entities"
            )
            
            # Test version listing performance
            _, list_time = self.perf_suite.measure_time(manager.list_versions)
            
            # Test version retrieval performance
            _, get_time = self.perf_suite.measure_time(manager.get_version, f"perf_test_v{size}")
            
            results[size] = {
                "create_time": create_time,
                "list_time": list_time,
                "get_time": get_time
            }
            
            print(f"Size {size:4d}: Create={create_time*1000:6.2f}ms, List={list_time*1000:6.2f}ms, Get={get_time*1000:6.2f}ms")
        
        # Verify performance requirements (as specified in original requirements)
        assert results[2000]["create_time"] < 0.5, "Large snapshot creation should be under 500ms"
        
        self.perf_suite.results["temporal_manager"] = results
    
    def test_version_comparison_performance(self):
        """Test version comparison performance with different graph sizes."""
        print("\n=== Version Comparison Performance ===")
        
        manager = TemporalVersionManager()
        results = {}
        
        for size in [100, 500, 1000]:
            # Create two similar graphs with some differences
            graph1 = self.perf_suite.generate_test_graph(size, size * 2)
            graph2 = self.perf_suite.generate_test_graph(size + 10, size * 2 + 20)  # Slightly different
            
            # Create snapshots
            manager.create_snapshot(graph1, f"v1_{size}", "test@example.com", "Version 1")
            manager.create_snapshot(graph2, f"v2_{size}", "test@example.com", "Version 2")
            
            # Test comparison performance
            _, compare_time = self.perf_suite.measure_time(
                manager.compare_versions, f"v1_{size}", f"v2_{size}"
            )
            
            results[size] = {"compare_time": compare_time}
            print(f"Size {size:4d}: Compare={compare_time*1000:6.2f}ms")
        
        # Verify comparison performance
        assert results[1000]["compare_time"] < 1.0, "Large graph comparison should be under 1 second"
        
        self.perf_suite.results["version_comparison"] = results
    
    def test_ontology_version_manager_performance(self):
        """Test OntologyVersionManager performance with ontologies."""
        print("\n=== OntologyVersionManager Performance ===")
        
        manager = OntologyVersionManager()
        results = {}
        
        ontology_sizes = [50, 100, 500, 1000]
        
        for size in ontology_sizes:
            ontology = self.perf_suite.generate_test_ontology(size, size // 2)
            
            # Test ontology snapshot creation
            _, create_time = self.perf_suite.measure_time(
                manager.create_snapshot,
                ontology,
                f"ont_v{size}",
                "test@example.com",
                f"Ontology with {size} classes"
            )
            
            results[size] = {"create_time": create_time}
            print(f"Classes {size:4d}: Create={create_time*1000:6.2f}ms")
        
        # Test structural comparison
        ont1 = self.perf_suite.generate_test_ontology(500, 250)
        ont2 = self.perf_suite.generate_test_ontology(520, 260)  # Slightly different
        
        manager.create_snapshot(ont1, "ont_comp_1", "test@example.com", "Ontology 1")
        manager.create_snapshot(ont2, "ont_comp_2", "test@example.com", "Ontology 2")
        
        _, compare_time = self.perf_suite.measure_time(
            manager.compare_versions, "ont_comp_1", "ont_comp_2"
        )
        
        print(f"Ontology comparison: {compare_time*1000:6.2f}ms")
        
        self.perf_suite.results["ontology_manager"] = results


class TestChecksumPerformance:
    """Test checksum computation and verification performance."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.perf_suite = PerformanceTestSuite()
    
    def test_checksum_performance(self):
        """Test checksum computation performance across different data sizes."""
        print("\n=== Checksum Performance ===")
        
        results = {}
        
        for size in [100, 500, 1000, 5000, 10000]:
            graph = self.perf_suite.generate_test_graph(size, size * 2)
            
            # Test checksum computation
            _, compute_time = self.perf_suite.measure_time(compute_checksum, graph)
            
            # Test checksum verification
            checksum = compute_checksum(graph)
            graph_with_checksum = graph.copy()
            graph_with_checksum["checksum"] = checksum
            
            _, verify_time = self.perf_suite.measure_time(verify_checksum, graph_with_checksum)
            
            results[size] = {
                "compute_time": compute_time,
                "verify_time": verify_time
            }
            
            print(f"Size {size:5d}: Compute={compute_time*1000:6.2f}ms, Verify={verify_time*1000:6.2f}ms")
        
        # Verify checksum performance requirements
        assert results[10000]["compute_time"] < 0.5, "Large checksum computation should be under 500ms"
        assert results[10000]["verify_time"] < 0.5, "Large checksum verification should be under 500ms"
        
        self.perf_suite.results["checksum"] = results


class TestConcurrencyPerformance:
    """Test concurrent operations and thread safety."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.perf_suite = PerformanceTestSuite()
    
    def test_concurrent_storage_operations(self):
        """Test concurrent storage operations."""
        print("\n=== Concurrent Storage Operations ===")
        
        storage = InMemoryVersionStorage()
        num_threads = 10
        operations_per_thread = 50
        
        def worker_function(thread_id: int):
            """Worker function for concurrent testing."""
            times = []
            for i in range(operations_per_thread):
                graph = self.perf_suite.generate_test_graph(50, 100)
                snapshot = {
                    "label": f"thread_{thread_id}_snapshot_{i}",
                    "timestamp": "2024-01-30T12:00:00Z",
                    "author": f"thread_{thread_id}@example.com",
                    "description": f"Concurrent test snapshot {i}",
                    "entities": graph["entities"],
                    "relationships": graph["relationships"],
                    "checksum": compute_checksum(graph)
                }
                
                start_time = time.perf_counter()
                storage.save(snapshot)
                end_time = time.perf_counter()
                times.append(end_time - start_time)
            
            return times
        
        # Run concurrent operations
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_function, i) for i in range(num_threads)]
            all_times = []
            
            for future in as_completed(futures):
                thread_times = future.result()
                all_times.extend(thread_times)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Calculate statistics
        avg_operation_time = statistics.mean(all_times)
        max_operation_time = max(all_times)
        total_operations = num_threads * operations_per_thread
        
        print(f"Total operations: {total_operations}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Operations per second: {total_operations/total_time:.1f}")
        print(f"Average operation time: {avg_operation_time*1000:.2f}ms")
        print(f"Max operation time: {max_operation_time*1000:.2f}ms")
        
        # Verify concurrent performance
        assert avg_operation_time < 0.1, "Average concurrent operation should be under 100ms"
        assert total_operations/total_time > 50, "Should handle at least 50 operations per second"
    
    def test_concurrent_version_manager_operations(self):
        """Test concurrent version manager operations."""
        print("\n=== Concurrent Version Manager Operations ===")
        
        manager = TemporalVersionManager()
        num_threads = 5
        snapshots_per_thread = 20
        
        def create_snapshots(thread_id: int):
            """Create snapshots concurrently."""
            times = []
            for i in range(snapshots_per_thread):
                graph = self.perf_suite.generate_test_graph(100, 200)
                
                start_time = time.perf_counter()
                manager.create_snapshot(
                    graph,
                    f"concurrent_t{thread_id}_s{i}",
                    f"thread{thread_id}@example.com",
                    f"Concurrent snapshot {i}"
                )
                end_time = time.perf_counter()
                times.append(end_time - start_time)
            
            return times
        
        # Run concurrent snapshot creation
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_snapshots, i) for i in range(num_threads)]
            all_times = []
            
            for future in as_completed(futures):
                thread_times = future.result()
                all_times.extend(thread_times)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Verify all snapshots were created
        versions = manager.list_versions()
        expected_count = num_threads * snapshots_per_thread
        
        print(f"Created {len(versions)} snapshots in {total_time:.2f}s")
        print(f"Average creation time: {statistics.mean(all_times)*1000:.2f}ms")
        
        assert len(versions) == expected_count, f"Expected {expected_count} snapshots, got {len(versions)}"


class TestMemoryUsage:
    """Test memory usage and resource consumption."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.perf_suite = PerformanceTestSuite()
    
    def test_memory_usage_scaling(self):
        """Test memory usage scaling with data size."""
        print("\n=== Memory Usage Scaling ===")
        
        manager = TemporalVersionManager()
        initial_memory = self.perf_suite.process.memory_info().rss / 1024 / 1024  # MB
        
        memory_usage = {}
        
        for size in [100, 500, 1000, 2000]:
            graph = self.perf_suite.generate_test_graph(size, size * 2)
            
            # Create snapshot and measure memory
            manager.create_snapshot(
                graph,
                f"memory_test_{size}",
                "test@example.com",
                f"Memory test with {size} entities"
            )
            
            current_memory = self.perf_suite.process.memory_info().rss / 1024 / 1024  # MB
            memory_used = current_memory - initial_memory
            memory_usage[size] = memory_used
            
            print(f"Size {size:4d}: Memory used: {memory_used:.1f}MB")
        
        # Verify memory usage is reasonable
        memory_per_entity = memory_usage[2000] / 2000
        print(f"Memory per entity: {memory_per_entity*1024:.2f}KB")
        
        # Should use less than 1MB per 1000 entities for reasonable efficiency
        assert memory_usage[1000] < 50, "Memory usage should be reasonable for large datasets"


def run_comprehensive_performance_tests():
    """Run all performance tests and generate summary report."""
    print("=" * 80)
    print("COMPREHENSIVE CHANGE MANAGEMENT PERFORMANCE TEST SUITE")
    print("=" * 80)
    
    # Initialize test classes
    storage_tests = TestStoragePerformance()
    storage_tests.setup_method()
    
    manager_tests = TestVersionManagerPerformance()
    manager_tests.setup_method()
    
    checksum_tests = TestChecksumPerformance()
    checksum_tests.setup_method()
    
    concurrency_tests = TestConcurrencyPerformance()
    concurrency_tests.setup_method()
    
    memory_tests = TestMemoryUsage()
    memory_tests.setup_method()
    
    # Run all tests
    try:
        # Storage performance tests
        storage_tests.test_inmemory_storage_performance()
        storage_tests.test_sqlite_storage_performance()
        storage_tests.test_storage_comparison()
        
        # Version manager performance tests
        manager_tests.test_temporal_version_manager_performance()
        manager_tests.test_version_comparison_performance()
        manager_tests.test_ontology_version_manager_performance()
        
        # Checksum performance tests
        checksum_tests.test_checksum_performance()
        
        # Concurrency tests
        concurrency_tests.test_concurrent_storage_operations()
        concurrency_tests.test_concurrent_version_manager_operations()
        
        # Memory usage tests
        memory_tests.test_memory_usage_scaling()
        
        print("\n" + "=" * 80)
        print("ALL PERFORMANCE TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\nPERFORMANCE TEST FAILED: {e}")
        return False


if __name__ == "__main__":
    success = run_comprehensive_performance_tests()
    exit(0 if success else 1)
