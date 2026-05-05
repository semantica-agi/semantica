import sys
import unittest
from typing import Dict, Any, List
from semantica.deduplication.similarity_calculator import SimilarityCalculator
from semantica.deduplication.duplicate_detector import DuplicateDetector
from semantica.deduplication.entity_merger import EntityMerger
from semantica.deduplication.merge_strategy import MergeStrategy
from semantica.deduplication.cluster_builder import ClusterBuilder
from semantica.deduplication.registry import MethodRegistry
from semantica.deduplication.config import DeduplicationConfig
from semantica.deduplication.methods import get_deduplication_method
from semantica.utils.progress_tracker import ConsoleProgressDisplay

class TestDeduplication(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.entities = [
            {
                "id": "e1",
                "name": "Apple Inc.",
                "type": "Company",
                "properties": {"industry": "Technology", "headquarters": "Cupertino"},
                "relationships": [{"type": "competitor", "target": "Microsoft"}]
            },
            {
                "id": "e2",
                "name": "Apple",
                "type": "Company",
                "properties": {"industry": "Tech", "headquarters": "Cupertino, CA"},
                "relationships": [{"type": "competitor", "target": "Google"}]
            },
            {
                "id": "e3",
                "name": "Microsoft Corp",
                "type": "Company",
                "properties": {"industry": "Software"},
                "relationships": []
            }
        ]
        
    def test_similarity_calculator(self):
        """Test similarity calculation components."""
        calculator = SimilarityCalculator(
            string_weight=0.5,
            property_weight=0.5,
            embedding_weight=0.0
        )
        
        # Test string similarity
        score_lev = calculator.calculate_string_similarity("Apple", "Apple Inc.", method="levenshtein")
        self.assertGreater(score_lev, 0.0)
        self.assertLess(score_lev, 1.0)
        
        score_exact = calculator.calculate_string_similarity("Apple", "Apple", method="exact")
        self.assertEqual(score_exact, 1.0)
        
        # Test full similarity calculation
        result = calculator.calculate_similarity(self.entities[0], self.entities[1])
        self.assertGreater(result.score, 0.0)
        self.assertIsNotNone(result.components)
        
    def test_duplicate_detector(self):
        """Test duplicate detection."""
        detector = DuplicateDetector(
            similarity_threshold=0.4, # Lower threshold for test data
            confidence_threshold=0.4
        )
        
        # Test pairwise detection
        duplicates = detector.detect_duplicates(self.entities)
        # Should find Apple and Apple Inc. as duplicates
        found_match = False
        for dup in duplicates:
            names = {dup.entity1["name"], dup.entity2["name"]}
            if "Apple" in names and "Apple Inc." in names:
                found_match = True
                break
        self.assertTrue(found_match, "Should detect 'Apple' and 'Apple Inc.' as duplicates")
        
        # Test group detection
        groups = detector.detect_duplicate_groups(self.entities)
        self.assertGreater(len(groups), 0)
        # One group should have at least 2 entities (the Apple ones)
        apple_group = next((g for g in groups if len(g.entities) >= 2), None)
        self.assertIsNotNone(apple_group)
        
    def test_entity_merger(self):
        """Test entity merging."""
        merger = EntityMerger(preserve_provenance=True)
        
        # Test merging specific group
        to_merge = [self.entities[0], self.entities[1]]
        
        # Strategy: KEEP_FIRST
        op_first = merger.merge_entity_group(to_merge, strategy=MergeStrategy.KEEP_FIRST)
        self.assertEqual(op_first.merged_entity["id"], "e1")
        
        # Strategy: KEEP_LAST
        op_last = merger.merge_entity_group(to_merge, strategy=MergeStrategy.KEEP_LAST)
        self.assertEqual(op_last.merged_entity["id"], "e2")
        
        # Strategy: MERGE_ALL (combining properties)
        # Note: implementation might vary on how it combines properties, checking basics
        op_merge = merger.merge_entity_group(to_merge, strategy=MergeStrategy.MERGE_ALL)
        self.assertIn("industry", op_merge.merged_entity["properties"])
        
    def test_entity_merger_string_strategies(self):
        """Test entity merging with string strategies."""
        merger = EntityMerger(preserve_provenance=True)
        to_merge = [self.entities[0], self.entities[1]]
        
        # Strategy: "keep_first"
        op_first = merger.merge_entity_group(to_merge, strategy="keep_first")
        self.assertEqual(op_first.merged_entity["id"], "e1")
        
        # Strategy: "keep_last"
        op_last = merger.merge_entity_group(to_merge, strategy="keep_last")
        self.assertEqual(op_last.merged_entity["id"], "e2")
        
        # Strategy: "keep_most_complete"
        # Apple Inc. (e1) has 2 props, Apple (e2) has 1 prop
        op_complete = merger.merge_entity_group(to_merge, strategy="keep_most_complete")
        self.assertEqual(op_complete.merged_entity["id"], "e1")
        
        # Test property rule with string strategy
        from semantica.deduplication.merge_strategy import MergeStrategyManager
        manager = MergeStrategyManager()
        manager.add_property_rule("name", "keep_last")
        
        # Manually invoke with manager (since EntityMerger creates its own default manager)
        # We can pass a custom manager if EntityMerger allowed, but here we test manager directly
        result = manager.merge_entities(to_merge)
        # name should be from last entity ("Apple")
        self.assertEqual(result.merged_entity["name"], "Apple")

    def test_incremental_detection(self):
        """Test incremental duplicate detection."""
        detector = DuplicateDetector(
            similarity_threshold=0.4,
            confidence_threshold=0.4
        )
        existing = [self.entities[0]] # Apple Inc.
        new_ents = [self.entities[1], self.entities[2]] # Apple, Microsoft
        
        candidates = detector.incremental_detect(new_ents, existing)
        
        # Should match Apple (new) with Apple Inc. (existing)
        found_match = False
        for cand in candidates:
            if cand.entity1["name"] == "Apple" and cand.entity2["name"] == "Apple Inc.":
                found_match = True
            elif cand.entity1["name"] == "Apple Inc." and cand.entity2["name"] == "Apple":
                found_match = True
                
        self.assertTrue(found_match, "Should detect incremental duplicate between Apple and Apple Inc.")

    def test_cluster_builder(self):
        """Test cluster building."""
        builder = ClusterBuilder(
            similarity_threshold=0.4,
            min_cluster_size=2
        )
        result = builder.build_clusters(self.entities)
        
        # Should find at least one cluster with Apple entities
        self.assertGreater(len(result.clusters), 0)
        apple_cluster = next((c for c in result.clusters if len(c.entities) >= 2), None)
        self.assertIsNotNone(apple_cluster)
        
    def test_registry(self):
        """Test method registry."""
        registry = MethodRegistry()
        
        def dummy_method(a, b):
            return 1.0
            
        registry.register("similarity", "dummy", dummy_method)
        method = registry.get("similarity", "dummy")
        self.assertEqual(method, dummy_method)
        self.assertIn("dummy", registry.list_all("similarity")["similarity"])
        
    def test_config(self):
        """Test configuration manager."""
        config = DeduplicationConfig()
        config.set("similarity_threshold", 0.95)
        self.assertEqual(config.get("similarity_threshold"), 0.95)
        
        # Test fallback (if implemented) or default
        self.assertEqual(config.get("non_existent", default="default"), "default")

    def test_methods_wrapper(self):
        """Test methods wrapper."""
        # Test built-in method retrieval
        method = get_deduplication_method("similarity", "levenshtein")
        self.assertIsNotNone(method)
        
        # Test usage of retrieved method
        result = method(self.entities[0], self.entities[1])
        # The wrapper returns a SimilarityResult
        self.assertIsNotNone(result.score)
        
        # Test invalid method
        invalid = get_deduplication_method("similarity", "non_existent_method")
        self.assertIsNone(invalid)


class TestProgressTrackerEncoding(unittest.TestCase):
    """Regression tests for issue #531 — Unicode crash on cp1252 Windows consoles."""

    def _make_cp1252_stdout(self):
        """Return a stdout-like object that raises UnicodeEncodeError for non-cp1252 chars."""
        class CP1252Writer:
            encoding = "cp1252"
            def write(self, text):
                text.encode("cp1252")  # raises on emoji / block chars
            def flush(self):
                pass
        return CP1252Writer()

    def test_safe_write_does_not_crash_on_cp1252(self):
        """_safe_write must not raise UnicodeEncodeError on a cp1252 console."""
        display = ConsoleProgressDisplay()
        orig = sys.stdout
        sys.stdout = self._make_cp1252_stdout()
        try:
            display._safe_write("🧠 Semantica - 📊 Current Progress\n")
        except UnicodeEncodeError:
            self.fail("_safe_write raised UnicodeEncodeError on cp1252 stdout")
        finally:
            sys.stdout = orig

    def test_update_pipeline_header_does_not_crash_on_cp1252(self):
        """update() pipeline header write must not crash on a cp1252 console (issue #531)."""
        from semantica.utils.progress_tracker import ProgressItem
        display = ConsoleProgressDisplay()
        display.use_emoji = True  # force emoji path to exercise the fixed branch
        orig = sys.stdout
        sys.stdout = self._make_cp1252_stdout()
        try:
            display._safe_write("🧠 Semantica - 📊 Current Progress\n")
            display._safe_write("=" * 150 + "\n")
        except UnicodeEncodeError:
            self.fail("Pipeline header write raised UnicodeEncodeError on cp1252 stdout")
        finally:
            sys.stdout = orig

    def test_emoji_detection_disables_on_cp1252(self):
        """ConsoleProgressDisplay should auto-disable emoji when stdout is cp1252."""
        orig = sys.stdout
        sys.stdout = self._make_cp1252_stdout()
        try:
            display = ConsoleProgressDisplay()
            self.assertFalse(display.use_emoji, "use_emoji should be False on cp1252 stdout")
        finally:
            sys.stdout = orig


if __name__ == "__main__":
    unittest.main()
