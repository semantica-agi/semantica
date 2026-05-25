"""
Pipeline Validator Module

This module provides pipeline validation and testing for workflow correctness and
performance, detecting errors, circular dependencies, and performance issues.

Key Features:
    - Pipeline validation and testing
    - Workflow correctness checking
    - Performance validation and benchmarking
    - Error detection and reporting
    - Circular dependency detection
    - Step dependency validation

Main Classes:
    - PipelineValidator: Pipeline validation engine
    - ValidationResult: Dataclass for validation results

Example Usage:
    >>> from semantica.pipeline import PipelineValidator
    >>> validator = PipelineValidator()
    >>> result = validator.validate_pipeline(pipeline)
    >>> if result.valid: print("Pipeline is valid")

Author: Semantica Contributors
License: MIT
"""

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker

if TYPE_CHECKING:
    from .pipeline_builder import Pipeline, PipelineBuilder, PipelineStep


@dataclass
class ValidationResult:
    """Pipeline validation result."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PipelineValidator:
    """
    Pipeline validation engine.

    • Pipeline validation and testing
    • Workflow correctness checking
    • Performance validation and benchmarking
    • Error detection and reporting
    • Performance optimization
    • Advanced validation techniques
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize pipeline validator.

        Args:
            config: Configuration dictionary
            **kwargs: Additional configuration options
        """
        self.logger = get_logger("pipeline_validator")
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

    def validate(
        self, pipeline: Union["Pipeline", "PipelineBuilder"], **options
    ) -> ValidationResult:
        """Alias for validate_pipeline."""
        return self.validate_pipeline(pipeline, **options)

    def validate_pipeline(
        self, pipeline: Union["Pipeline", "PipelineBuilder"], **options
    ) -> ValidationResult:
        """
        Validate entire pipeline.

        Args:
            pipeline: Pipeline object or builder
            **options: Additional options

        Returns:
            Validation result
        """
        from .pipeline_builder import Pipeline, PipelineBuilder

        tracking_id = self.progress_tracker.start_tracking(
            module="pipeline",
            submodule="PipelineValidator",
            message="Validating pipeline",
        )

        try:
            errors = []
            warnings = []

            # Convert builder to pipeline if needed
            if isinstance(pipeline, PipelineBuilder):
                # Check structure
                self.progress_tracker.update_tracking(
                    tracking_id, message="Validating pipeline structure..."
                )
                structure_result = self._validate_structure(pipeline)
                errors.extend(structure_result.get("errors", []))
                warnings.extend(structure_result.get("warnings", []))

                # Check dependencies
                self.progress_tracker.update_tracking(
                    tracking_id, message="Checking dependencies..."
                )
                dependency_result = self.check_dependencies(pipeline)
                errors.extend(dependency_result.get("errors", []))
                warnings.extend(dependency_result.get("warnings", []))

            elif isinstance(pipeline, Pipeline):
                # Validate pipeline steps
                self.progress_tracker.update_tracking(
                    tracking_id,
                    message=f"Validating {len(pipeline.steps)} pipeline steps...",
                )
                for step in pipeline.steps:
                    step_result = self.validate_step(step)
                    if not step_result.valid:
                        errors.extend(step_result.errors)
                    warnings.extend(step_result.warnings)

                # Check dependencies
                self.progress_tracker.update_tracking(
                    tracking_id, message="Checking dependencies..."
                )
                dependency_result = self.check_dependencies(pipeline)
                errors.extend(dependency_result.get("errors", []))
                warnings.extend(dependency_result.get("warnings", []))

            result = ValidationResult(
                valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                metadata={
                    "step_count": len(pipeline.steps)
                    if hasattr(pipeline, "steps")
                    else 0
                },
            )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Validation complete: {'Valid' if result.valid else 'Invalid'} ({len(errors)} errors, {len(warnings)} warnings)",
            )
            return result

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _validate_structure(self, pipeline: "PipelineBuilder") -> Dict[str, Any]:
        """Validate pipeline structure."""
        errors = []
        warnings = []

        # Check if pipeline has steps
        if not pipeline.steps:
            errors.append("Pipeline has no steps")

        # Check step names are unique
        step_names = [step.name for step in pipeline.steps]
        duplicates = [
            name
            for name, count in Counter(step_names).items()
            if count > 1
        ]
        if duplicates:
            errors.append(f"Duplicate step names found: {duplicates}")

        # Check step configurations
        for step in pipeline.steps:
            if not step.name:
                errors.append("Step missing name")
            if not step.step_type:
                errors.append(f"Step '{step.name}' missing type")

        return {"errors": errors, "warnings": warnings}

    def validate_step(self, step: "PipelineStep", **constraints) -> ValidationResult:
        """
        Validate individual pipeline step.

        Args:
            step: Pipeline step
            **constraints: Validation constraints

        Returns:
            Validation result
        """
        errors = []
        warnings = []

        # Check required fields
        if not step.name:
            errors.append("Step missing name")
        if not step.step_type:
            errors.append("Step missing type")

        # Check handler
        if not step.handler and not constraints.get("allow_no_handler", False):
            warnings.append(f"Step '{step.name}' has no handler")

        # Check configuration
        if not step.config:
            warnings.append(f"Step '{step.name}' has no configuration")

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def check_dependencies(
        self, pipeline: Union["Pipeline", "PipelineBuilder"]
    ) -> Dict[str, Any]:
        """
        Check pipeline dependencies.

        Args:
            pipeline: Pipeline object or builder

        Returns:
            Dependency analysis results
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="pipeline",
            submodule="PipelineValidator",
            message="Checking pipeline dependencies",
        )

        try:
            errors = []
            warnings = []

            steps = pipeline.steps if hasattr(pipeline, "steps") else []
            step_names = {step.name for step in steps}

            # Check for circular dependencies
            self.progress_tracker.update_tracking(
                tracking_id, message="Detecting circular dependencies..."
            )
            circular = self._detect_circular_dependencies(steps)
            if circular:
                errors.append(f"Circular dependency detected: {circular}")

            # Check for missing dependencies
            self.progress_tracker.update_tracking(
                tracking_id, message="Checking for missing dependencies..."
            )
            for step in steps:
                for dep in step.dependencies:
                    if dep not in step_names:
                        errors.append(
                            f"Missing dependency '{dep}' for step '{step.name}'"
                        )

            # Check for unreachable steps
            self.progress_tracker.update_tracking(
                tracking_id, message="Finding reachable steps..."
            )
            reachable = self._find_reachable_steps(steps)
            unreachable = set(step_names) - reachable
            if unreachable:
                warnings.append(f"Unreachable steps found: {unreachable}")

            result = {
                "errors": errors,
                "warnings": warnings,
                "circular_dependencies": circular,
                "reachable_steps": reachable,
            }

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Dependency check complete: {len(errors)} errors, {len(warnings)} warnings",
            )
            return result

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _detect_circular_dependencies(
        self, steps: List["PipelineStep"]
    ) -> List[List[str]]:
        """Detect circular dependencies using DFS."""
        step_map = {step.name: step for step in steps}
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            step = step_map.get(node)
            if step:
                for dep in step.dependencies:
                    if dep not in step_map:
                        continue

                    if dep in rec_stack:
                        # Found cycle
                        cycle_start = path.index(dep)
                        cycles.append(path[cycle_start:] + [dep])
                    elif dep not in visited:
                        dfs(dep, path)

            rec_stack.remove(node)
            path.pop()

        for step in steps:
            if step.name not in visited:
                dfs(step.name, [])

        return cycles

    def _find_reachable_steps(self, steps: List["PipelineStep"]) -> set:
        """Find reachable steps from entry points."""
        step_map = {step.name: step for step in steps}
        reachable = set()

        # Find entry points (steps with no dependencies)
        entry_points = [step.name for step in steps if not step.dependencies]

        # BFS from entry points
        queue = deque(entry_points)
        while queue:
            step_name = queue.popleft()
            if step_name in reachable:
                continue

            reachable.add(step_name)
            step = step_map.get(step_name)
            if step:
                # Add dependent steps
                for dependent_step in steps:
                    if step_name in dependent_step.dependencies:
                        queue.append(dependent_step.name)

        return reachable

    def validate_performance(self, pipeline: "Pipeline", **options) -> Dict[str, Any]:
        """
        Validate pipeline performance.

        Args:
            pipeline: Pipeline object
            **options: Additional options

        Returns:
            Performance validation results
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="pipeline",
            submodule="PipelineValidator",
            message="Validating pipeline performance",
        )

        try:
            warnings = []

            # Check for potential bottlenecks
            self.progress_tracker.update_tracking(
                tracking_id, message="Analyzing pipeline structure..."
            )
            step_count = len(pipeline.steps)
            if step_count > 100:
                warnings.append("Pipeline has many steps, may impact performance")

            # Check for sequential dependencies
            sequential_steps = sum(
                1 for step in pipeline.steps if len(step.dependencies) > 0
            )
            if sequential_steps == step_count:
                warnings.append("All steps are sequential, consider parallelization")

            result = {
                "step_count": step_count,
                "sequential_steps": sequential_steps,
                "warnings": warnings,
            }

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Performance validation complete: {len(warnings)} warnings",
            )
            return result

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise
