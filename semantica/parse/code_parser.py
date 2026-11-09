"""
Source Code Parsing Module

This module handles parsing of source code files and repositories, providing
syntax tree analysis, code structure extraction, comment parsing, and dependency
analysis for multiple programming languages.

Key Features:
    - Multi-language code parsing (Python, JavaScript, Java, etc.)
    - Syntax tree analysis using AST
    - Code structure extraction (functions, classes, imports)
    - Comment and documentation parsing
    - Dependency analysis
    - Code metadata extraction
    - Repository-wide analysis

Main Classes:
    - CodeParser: Main code parsing class
    - SyntaxTreeParser: Syntax tree analyzer
    - CommentExtractor: Code comment processor
    - DependencyAnalyzer: Code dependency analyzer
    - CodeStructure: Dataclass for code structure representation
    - CodeComment: Dataclass for code comment representation

Example Usage:
    >>> from pathlib import Path
    >>> from semantica.parse import CodeParser
    >>> parser = CodeParser()
    >>> parsed = parser.parse_code("script.py")
    >>> source = Path("script.py").read_text()
    >>> comments = parser.extract_comments(source, "python")
    >>> dependencies = parser.analyze_dependencies(source, "python")

Author: Semantica Contributors
License: MIT
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


@dataclass
class CodeStructure:
    """Code structure representation."""

    functions: List[Dict[str, Any]] = field(default_factory=list)
    classes: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)
    constants: List[str] = field(default_factory=list)


@dataclass
class CodeComment:
    """Code comment representation."""

    text: str
    line_number: int
    type: str  # "inline", "block", "docstring"
    language: str


class CodeParser:
    """
    Source code parsing handler.

    • Parses source code in multiple languages
    • Extracts code structure and syntax
    • Processes comments and documentation
    • Analyzes code dependencies
    • Handles various code formats
    • Supports batch code processing
    """

    def __init__(self, config=None, **kwargs):
        """
        Initialize code parser.

        • Setup language-specific parsers
        • Configure syntax analysis
        • Initialize comment extraction
        • Setup dependency analysis
        • Configure batch processing
        """
        self.logger = get_logger("code_parser")
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize sub-parsers
        self.syntax_parser = SyntaxTreeParser(**self.config.get("syntax", {}))
        self.comment_extractor = CommentExtractor(**self.config.get("comments", {}))
        self.dependency_analyzer = DependencyAnalyzer(
            **self.config.get("dependencies", {})
        )

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()

        # Supported languages
        self.supported_languages = {
            ".py": "python",
            ".js": "javascript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".rb": "ruby",
            ".go": "go",
            ".rs": "rust",
            ".php": "php",
        }

    def parse_code(
        self, file_path: Union[str, Path], language: Optional[str] = None, **options
    ) -> Dict[str, Any]:
        """
        Parse source code file.

        Args:
            file_path: Path to code file
            language: Programming language (auto-detected if None)
            **options: Parsing options

        Returns:
            dict: Parsed code data
        """
        file_path = Path(file_path)

        # Track code parsing
        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="parse",
            submodule="CodeParser",
            message=f"Code: {file_path.name}",
        )

        try:
            if not file_path.exists():
                raise ValidationError(f"Code file not found: {file_path}")

            # Detect language if not specified
            if language is None:
                language = self._detect_language(file_path)

            if language not in self.supported_languages.values():
                self.logger.warning(f"Language {language} may not be fully supported")

            try:
                # Read code content
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    code_content = f.read()

                # Extract structure
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Analyzing {language} code..."
                )
                structure = self.extract_structure(code_content, language)

                # Extract comments
                comments = self.extract_comments(code_content, language)

                # Analyze dependencies
                dependencies = self.analyze_dependencies(code_content, language)

                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Parsed {language} code: {len(structure.functions)} functions, {len(structure.classes)} classes",
                )
                return {
                    "file_path": str(file_path),
                    "language": language,
                    "structure": structure.__dict__,
                    "comments": [c.__dict__ for c in comments],
                    "dependencies": dependencies,
                    "line_count": len(code_content.splitlines()),
                    "size": len(code_content),
                }

            except Exception as e:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message=str(e)
                )
                raise

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            self.logger.error(f"Failed to parse code {file_path}: {e}")
            raise ProcessingError(f"Failed to parse code: {e}")

    def extract_structure(self, code_content: str, language: str) -> CodeStructure:
        """
        Extract code structure and elements.

        Args:
            code_content: Code content as string
            language: Programming language

        Returns:
            CodeStructure: Code structure
        """
        return self.syntax_parser.extract_elements(code_content, language)

    def extract_comments(self, code_content: str, language: str) -> List[CodeComment]:
        """
        Extract comments and documentation.

        Args:
            code_content: Code content as string
            language: Programming language

        Returns:
            list: List of comments
        """
        return self.comment_extractor.extract_comments(code_content, language)

    def analyze_dependencies(self, code_content: str, language: str) -> Dict[str, Any]:
        """
        Analyze code dependencies and imports.

        Args:
            code_content: Code content as string
            language: Programming language

        Returns:
            dict: Dependency analysis
        """
        return self.dependency_analyzer.analyze_dependencies(code_content, language)

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        suffix = file_path.suffix.lower()
        return self.supported_languages.get(suffix, "unknown")


class SyntaxTreeParser:
    """
    Syntax tree parsing engine.

    • Parses code into syntax trees
    • Analyzes code structure
    • Extracts code elements
    • Handles multiple languages
    • Processes complex syntax
    """

    def __init__(self, **config):
        """Initialize syntax tree parser."""
        self.logger = get_logger("syntax_tree_parser")
        self.config = config

    def parse_syntax_tree(self, code_content: str, language: str) -> Any:
        """
        Parse code into syntax tree.

        Args:
            code_content: Code content
            language: Programming language

        Returns:
            Syntax tree object
        """
        if language == "python":
            try:
                return ast.parse(code_content)
            except SyntaxError as e:
                self.logger.warning(f"Syntax error in Python code: {e}")
                return None
        else:
            # For other languages, return None (would need language-specific parsers)
            return None

    def extract_elements(self, code_content: str, language: str) -> CodeStructure:
        """
        Extract code elements from syntax tree.

        Args:
            code_content: Code content
            language: Programming language

        Returns:
            CodeStructure: Extracted structure
        """
        structure = CodeStructure()

        if language == "python":
            try:
                tree = ast.parse(code_content)

                # Extract functions and classes
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        structure.functions.append(
                            {
                                "name": node.name,
                                "line_number": node.lineno,
                                "args": [arg.arg for arg in node.args.args],
                                "decorators": [
                                    ast.unparse(d) for d in node.decorator_list
                                ],
                            }
                        )
                    elif isinstance(node, ast.ClassDef):
                        structure.classes.append(
                            {
                                "name": node.name,
                                "line_number": node.lineno,
                                "bases": [ast.unparse(b) for b in node.bases],
                            }
                        )
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            structure.imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        for alias in node.names:
                            structure.imports.append(f"{module}.{alias.name}")

            except SyntaxError:
                # Fallback to regex-based extraction
                structure = self._extract_with_regex(code_content, language)
        else:
            # Use regex-based extraction for other languages
            structure = self._extract_with_regex(code_content, language)

        return structure

    def _extract_with_regex(self, code_content: str, language: str) -> CodeStructure:
        """Extract code elements using regex patterns."""
        structure = CodeStructure()

        # Extract imports (common patterns)
        import_patterns = {
            "python": r"^import\s+(\S+)|^from\s+(\S+)\s+import",
            "javascript": r'^import\s+.*?from\s+[\'"](\S+)[\'"]|^require\([\'"](\S+)[\'"]',
            "java": r"^import\s+(\S+);",
            "c": r'^#include\s+[<"](\S+)[>"]',
        }

        pattern = import_patterns.get(language, r"import|require|include")
        for line in code_content.splitlines():
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                structure.imports.append(
                    match.group(1) or match.group(2) or match.group(0)
                )

        # Extract functions (common patterns)
        func_patterns = {
            "python": r"^def\s+(\w+)",
            "javascript": r"^function\s+(\w+)|^(\w+)\s*=\s*function",
            "java": r"^\s*(?:public|private|protected)?\s*\w+\s+(\w+)\s*\(",
            "c": r"^\w+\s+(\w+)\s*\(",
        }

        pattern = func_patterns.get(language, r"function|def")
        for i, line in enumerate(code_content.splitlines(), 1):
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                func_name = match.group(1) or match.group(2) or f"function_{i}"
                structure.functions.append({"name": func_name, "line_number": i})

        # Extract classes (common patterns)
        class_patterns = {
            "python": r"^class\s+(\w+)",
            "javascript": r"^class\s+(\w+)",
            "java": r"^public\s+class\s+(\w+)",
            "c": r"^struct\s+(\w+)|^class\s+(\w+)",
        }

        pattern = class_patterns.get(language, r"class|struct")
        for i, line in enumerate(code_content.splitlines(), 1):
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                class_name = match.group(1) or match.group(2) or f"class_{i}"
                structure.classes.append({"name": class_name, "line_number": i})

        return structure

    def analyze_structure(self, syntax_tree: Any) -> Dict[str, Any]:
        """
        Analyze code structure and organization.

        Args:
            syntax_tree: Syntax tree object

        Returns:
            dict: Structure analysis
        """
        if syntax_tree is None:
            return {}

        # For Python AST
        if isinstance(syntax_tree, ast.Module):
            functions = sum(
                1 for node in ast.walk(syntax_tree) if isinstance(node, ast.FunctionDef)
            )
            classes = sum(
                1 for node in ast.walk(syntax_tree) if isinstance(node, ast.ClassDef)
            )
            imports = sum(
                1
                for node in ast.walk(syntax_tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
            )

            return {
                "function_count": functions,
                "class_count": classes,
                "import_count": imports,
                "complexity": "low"
                if functions + classes < 10
                else "medium"
                if functions + classes < 50
                else "high",
            }

        return {}


class CommentExtractor:
    """
    Code comment extraction engine.

    • Extracts comments from code
    • Processes documentation strings
    • Handles various comment styles
    • Analyzes comment content
    • Extracts metadata from comments
    """

    def __init__(self, **config):
        """Initialize comment extractor."""
        self.logger = get_logger("comment_extractor")
        self.config = config

    def extract_comments(self, code_content: str, language: str) -> List[CodeComment]:
        """
        Extract all comments from code.

        Args:
            code_content: Code content
            language: Programming language

        Returns:
            list: List of comments
        """
        comments = []

        # Comment patterns by language
        patterns = {
            "python": [
                (r"#(.+?)$", "inline"),
                (r'"""(.*?)"""', "docstring"),
                (r"'''(.*?)'''", "docstring"),
            ],
            "javascript": [(r"//(.+?)$", "inline"), (r"/\*(.*?)\*/", "block")],
            "java": [(r"//(.+?)$", "inline"), (r"/\*(.*?)\*/", "block")],
            "c": [(r"//(.+?)$", "inline"), (r"/\*(.*?)\*/", "block")],
        }

        patterns_list = patterns.get(
            language, [(r"//(.+?)$", "inline"), (r"/\*(.*?)\*/", "block")]
        )

        for i, line in enumerate(code_content.splitlines(), 1):
            for pattern, comment_type in patterns_list:
                matches = re.finditer(pattern, line, re.MULTILINE | re.DOTALL)
                for match in matches:
                    comment_text = match.group(1).strip()
                    if comment_text:
                        comments.append(
                            CodeComment(
                                text=comment_text,
                                line_number=i,
                                type=comment_type,
                                language=language,
                            )
                        )

        return comments

    def extract_docstrings(self, code_content: str, language: str) -> List[CodeComment]:
        """
        Extract documentation strings.

        Args:
            code_content: Code content
            language: Programming language

        Returns:
            list: List of docstrings
        """
        comments = self.extract_comments(code_content, language)
        return [c for c in comments if c.type == "docstring"]


class DependencyAnalyzer:
    """
    Code dependency analysis engine.

    • Analyzes code dependencies
    • Maps import relationships
    • Identifies external packages
    • Tracks dependency versions
    • Analyzes dependency conflicts
    """

    def __init__(self, **config):
        """Initialize dependency analyzer."""
        self.logger = get_logger("dependency_analyzer")
        self.config = config

    def analyze_dependencies(self, code_content: str, language: str) -> Dict[str, Any]:
        """
        Analyze code dependencies.

        Args:
            code_content: Code content
            language: Programming language

        Returns:
            dict: Dependency analysis
        """
        dependencies = {
            "imports": [],
            "external": [],
            "internal": [],
            "standard_library": [],
        }

        if language == "python":
            try:
                tree = ast.parse(code_content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            dependencies["imports"].append(alias.name)
                            if self._is_standard_library(alias.name):
                                dependencies["standard_library"].append(alias.name)
                            else:
                                dependencies["external"].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        for alias in node.names:
                            full_name = (
                                f"{module}.{alias.name}" if module else alias.name
                            )
                            dependencies["imports"].append(full_name)
                            if self._is_standard_library(module or alias.name):
                                dependencies["standard_library"].append(full_name)
                            else:
                                dependencies["external"].append(full_name)
            except SyntaxError:
                # Fallback to regex
                pass

        # Regex fallback
        import_pattern = (
            r'(?:import|from|require|include)\s+[\'"](.*?)[\'"]|(?:import|from)\s+(\S+)'
        )
        for line in code_content.splitlines():
            matches = re.finditer(import_pattern, line, re.IGNORECASE)
            for match in matches:
                dep = match.group(1) or match.group(2)
                if dep:
                    dependencies["imports"].append(dep)

        return dependencies

    def _is_standard_library(self, module_name: str) -> bool:
        """Check if module is from Python standard library."""
        stdlib_modules = [
            "os",
            "sys",
            "json",
            "csv",
            "xml",
            "html",
            "urllib",
            "http",
            "email",
            "datetime",
            "time",
            "re",
            "math",
            "random",
            "collections",
            "itertools",
            "functools",
            "operator",
            "pathlib",
            "shutil",
        ]
        return any(module_name.startswith(mod) for mod in stdlib_modules)
