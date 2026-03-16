from typing import Any, Dict, List, Optional

from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .ontology_generator import OntologyGenerator
from .class_inferrer import ClassInferrer
from .property_generator import PropertyGenerator
from .owl_generator import OWLGenerator
from .ontology_evaluator import OntologyEvaluator
from .ontology_validator import OntologyValidator
from .llm_generator import LLMOntologyGenerator


class OntologyEngine:
    def __init__(self, **config):
        self.logger = get_logger("ontology_engine")
        self.progress = get_progress_tracker()
        self.config = config

        self.generator = OntologyGenerator(**config)
        self.inferrer = ClassInferrer(**config)
        self.propgen = PropertyGenerator(**config)
        self.owl = OWLGenerator(**config)
        self.evaluator = OntologyEvaluator(**config)
        self.validator = OntologyValidator(**config)
        self.llm = LLMOntologyGenerator(**config)
        self.store = config.get("store")

        # Deferred to avoid circular import: change_management → ontology → change_management
        from ..change_management.ontology_version_manager import VersionManager
        self.version_manager = config.get("version_manager") or VersionManager(**config)

    def from_data(self, data: Dict[str, Any], **options) -> Dict[str, Any]:
        tracking_id = self.progress.start_tracking(
            module="ontology",
            submodule="OntologyEngine",
            message="Generating ontology from data",
        )
        try:
            ontology = self.generator.generate_ontology(data, **options)
            self.progress.update_tracking(tracking_id, message="Ontology generated")
            return ontology
        except Exception as e:
            self.progress.update_tracking(tracking_id, message="Generation failed")
            raise

    def from_text(self, text: str, provider: Optional[str] = None, model: Optional[str] = None, **options) -> Dict[str, Any]:
        if provider:
            self.llm.set_provider(provider, model=model)
        return self.llm.generate_ontology_from_text(text, **options)

    def infer_classes(self, entities: List[Dict[str, Any]], **options) -> List[Dict[str, Any]]:
        return self.inferrer.infer_classes(entities, **options)

    def infer_properties(
        self,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        classes: List[Dict[str, Any]],
        **options,
    ) -> List[Dict[str, Any]]:
        return self.propgen.infer_properties(entities, relationships, classes, **options)

    def evaluate(self, ontology: Dict[str, Any], **options):
        return self.evaluator.evaluate_ontology(ontology, **options)

    def validate(self, ontology: Dict[str, Any], **options):
        return self.validator.validate(ontology, **options)

    def to_owl(self, ontology: Dict[str, Any], format: str = "turtle", **options):
        return self.owl.generate_owl(ontology, format=format, **options)

    def export_owl(self, ontology: Dict[str, Any], path: str, format: str = "turtle"):
        return self.owl.export_owl(ontology, path, format=format)

    def get_ontology_version_dict(self, version_id: str) -> Dict[str, Any]:
        """Utility to load an ontology version as plain dict ready for diffing."""
        version_record = self.version_manager.get_version(version_id)
        if not version_record:
            raise ProcessingError(f"Version {version_id} not found.")
        return version_record.metadata.get("structure", {"classes": [], "properties": []})

    def compare_versions(self, base_id: str, target_id: str, **options) -> Dict[str, Any]:
        """
        Orchestrates version loading, diff computation, and report generation.

        Args:
            base_id: Version ID of the old ontology
            target_id: Version ID of the new ontology
            **options: Can pass 'base_dict' and 'target_dict' directly to bypass loading.
                       Can pass 'run_validation=True' to validate schema.
                       Can pass 'graph_data' to validate instances against new schema.

        Returns:
            A structured dictionary containing the impact report and machine-readable diff.
        """
        tracking_id = self.progress.start_tracking(
            module="ontology",
            submodule="OntologyEngine",
            message=f"Comparing ontology versions: {base_id} -> {target_id}"
        )

        try:
            # Deferred to avoid circular import
            from ..change_management.change_log import generate_change_report
            from ..kg.graph_validator import GraphValidator

            base_dict = options.get("base_dict") or self.get_ontology_version_dict(base_id)
            target_dict = options.get("target_dict") or self.get_ontology_version_dict(target_id)

            diff_result = self.version_manager.diff_ontologies(base_dict, target_dict)
            report = generate_change_report(diff_result)
            report["diff"] = diff_result

            if options.get("run_validation"):
                self.progress.update_tracking(tracking_id, message="Running validation on target schema...")
                val_res = self.validate(target_dict, **options)
                report["validation_results"] = {
                    "valid": getattr(val_res, "valid", getattr(val_res, "is_valid", False)),
                    "consistent": getattr(val_res, "consistent", True),
                    "satisfiable": getattr(val_res, "satisfiable", True),
                    "errors": getattr(val_res, "errors", []),
                    "warnings": getattr(val_res, "warnings", [])
                }

                if "graph_data" in options:
                    self.progress.update_tracking(tracking_id, message="Running graph data validation...")
                    kg_validator = GraphValidator(**self.config)
                    kg_res = kg_validator.validate(options["graph_data"], ontology=target_dict, **options)
                    report["graph_validation"] = {
                        "valid": getattr(kg_res, "valid", getattr(kg_res, "is_valid", False)),
                        "errors": getattr(kg_res, "errors", []),
                        "warnings": getattr(kg_res, "warnings", [])
                    }

            self.progress.stop_tracking(tracking_id, status="completed", message="Comparison complete")
            return report

        except Exception as e:
            self.progress.stop_tracking(tracking_id, status="failed", message=str(e))
            self.logger.error(f"Failed to compare versions: {e}")
            raise ProcessingError(f"Version comparison failed: {e}") from e
