"""
Word Document Parser Module

This module handles DOCX document parsing using python-docx for text, formatting,
and structure extraction, including sections, paragraphs, tables, and metadata.

Key Features:
    - DOCX text and formatting extraction
    - Document structure analysis (sections, headings)
    - Table extraction
    - Metadata extraction (title, author, dates)
    - Paragraph and style information
    - Embedded image handling

Main Classes:
    - DOCXParser: DOCX document parser
    - DocxSection: Dataclass for document section representation
    - DocxMetadata: Dataclass for document metadata representation

Example Usage:
    >>> from semantica.parse import DOCXParser
    >>> parser = DOCXParser()
    >>> text = parser.parse("document.docx")
    >>> sections = parser.extract_sections("document.docx")
    >>> metadata = parser.extract_metadata("document.docx")

Author: Semantica Contributors
License: MIT
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    from docx import Document
    from docx.document import Document as DocxDocument
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph
except (ImportError, OSError):
    Document = None
    DocxDocument = None
    CT_Tbl = None
    CT_P = None
    Table = None
    Paragraph = None

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker

# Text boxes.
#
# `Paragraph.text` concatenates only the text of the paragraph's own runs.
# Text box content sits one level deeper -- `w:txbxContent` holds its own
# `w:p`/`w:r`/`w:t` tree -- so a callout written in a text box is invisible to
# that API and gets dropped without a warning. A box can hold further boxes, and
# Word stores each box twice, as DrawingML under `mc:Choice` and as VML under
# `mc:Fallback`, so walking every `w:t` under the paragraph would report the
# text twice or more. The reader below walks a paragraph once, in document
# order, reads only one branch of each `mc:AlternateContent`, and reads a box's
# own paragraphs the same way, so nested boxes come out once, where they sit.
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_TXBX_CONTENT = _W + "txbxContent"
_W_P = _W + "p"
_W_R = _W + "r"
_W_HYPERLINK = _W + "hyperlink"
_MC_ALTERNATE_CONTENT = _MC + "AlternateContent"
_MC_CHOICE = _MC + "Choice"
_MC_FALLBACK = _MC + "Fallback"
# The run children python-docx turns into text for `Run.text`; `str()` of each
# gives that text.
_RUN_TEXT_TAGS = frozenset(
    _W + tag for tag in ("br", "cr", "noBreakHyphen", "ptab", "t", "tab")
)
# Elements whose runs are read as paragraph text. `Paragraph.text` reads
# through hyperlinks only, and body paragraphs keep that. Box paragraphs never
# went through `Paragraph.text`: they were read from every `w:t` in them, so
# they also read through insertions, content controls, fields and the like
# (but not `w:del`, whose text is `w:delText`).
_BODY_RUN_WRAPPERS = frozenset({_W_HYPERLINK})
_BOX_RUN_WRAPPERS = frozenset(
    _W + tag
    for tag in (
        "bdo",
        "customXml",
        "dir",
        "fldSimple",
        "hyperlink",
        "ins",
        "moveTo",
        "sdt",
        "sdtContent",
        "smartTag",
    )
)


def _text_boxes(element):
    """The text boxes under ``element``, outermost first, in document order.

    Boxes nested in a box are left to that box's own paragraphs, and only the
    chosen branch of each ``mc:AlternateContent`` is searched.
    """
    if element.tag == _TXBX_CONTENT:
        yield element
        return
    if element.tag == _MC_ALTERNATE_CONTENT:
        branch = _chosen_branch(element)
        if branch is not None:
            yield from _text_boxes(branch)
        return
    for child in element:
        yield from _text_boxes(child)


def _chosen_branch(alternate_content):
    """The first ``mc:Choice`` holding a text box, else the ``mc:Fallback``."""
    fallback = None
    for branch in alternate_content:
        if branch.tag == _MC_CHOICE and next(_text_boxes(branch), None) is not None:
            return branch
        if branch.tag == _MC_FALLBACK:
            fallback = branch
    return fallback


def _box_paragraphs(box):
    """The paragraphs of ``box`` itself, not those of boxes nested in it."""
    for paragraph in box.iter(_W_P):
        if next(paragraph.iterancestors(_TXBX_CONTENT), None) is box:
            yield paragraph


def _paragraph_lines(p, wrappers=_BODY_RUN_WRAPPERS) -> List[str]:
    """The text of the ``w:p`` element ``p``, one line per block, in order.

    Run text stays on one line until a text box interrupts it; each paragraph
    of the box then gets its own line(s), and the run text after the box starts
    a new line. Runs are read inside ``p`` and inside the ``wrappers`` in it.
    """
    lines: List[str] = []
    pending: List[str] = []

    def flush() -> None:
        text = "".join(pending).strip()
        if text:
            lines.append(text)
        pending.clear()

    def read_boxes(element) -> None:
        for box in _text_boxes(element):
            flush()
            for inner in _box_paragraphs(box):
                lines.extend(_paragraph_lines(inner, _BOX_RUN_WRAPPERS))

    def read_runs(element) -> None:
        for child in element:
            if child.tag == _W_R:
                for item in child:
                    if item.tag in _RUN_TEXT_TAGS:
                        pending.append(str(item))
                    else:
                        read_boxes(item)
            elif child.tag in wrappers:
                read_runs(child)
            else:
                # Not read as text, but a box can still sit inside.
                read_boxes(child)

    read_runs(p)
    flush()
    return lines


def _paragraph_text(paragraph: Paragraph) -> str:
    """``Paragraph.text`` with the text of its text boxes where they sit."""
    if next(_text_boxes(paragraph._p), None) is None:
        return paragraph.text
    return "\n".join(_paragraph_lines(paragraph._p))


@dataclass
class DocxSection:
    """Document section representation."""

    heading: str
    level: int
    content: str
    paragraphs: List[str] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DocxMetadata:
    """Document metadata representation."""

    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    comments: Optional[str] = None
    category: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    last_modified_by: Optional[str] = None


class DOCXParser:
    """DOCX document parser."""

    def __init__(self, **config):
        """
        Initialize DOCX parser.

        Args:
            **config: Parser configuration
        """
        self.logger = get_logger("docx_parser")
        self.config = config
        self.progress_tracker = get_progress_tracker()

    def parse(
        self, file_path: Union[str, Path], pipeline_id: Optional[str] = None, **options
    ) -> Dict[str, Any]:
        """
        Parse DOCX document.

        Args:
            file_path: Path to DOCX file
            pipeline_id: Optional pipeline ID for progress tracking
            **options: Parsing options:
                - extract_formatting: Whether to extract formatting (default: False)
                - extract_tables: Whether to extract tables (default: True)
                - extract_comments: Whether to extract comments (default: False)

        Returns:
            dict: Parsed document data
        """
        if Document is None:
            raise ProcessingError(
                "python-docx is required to parse DOCX files. "
                "Install it with: pip install 'semantica[documents]'"
            )

        file_path = Path(file_path)

        # Track DOCX parsing
        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="parse",
            submodule="DOCXParser",
            message=f"DOCX: {file_path.name}",
            pipeline_id=pipeline_id,
        )

        try:
            if not file_path.exists():
                raise ValidationError(f"DOCX file not found: {file_path}")

            if not file_path.suffix.lower() in [".docx", ".doc"]:
                raise ValidationError(f"File is not a DOCX: {file_path}")

            try:
                doc = Document(str(file_path))

                # Extract metadata
                metadata = self._extract_metadata(doc)

                # Extract paragraphs
                paragraphs = []
                for para in doc.paragraphs:
                    text = _paragraph_text(para).strip()
                    if text:
                        paragraphs.append(text)

                # Extract tables
                tables = []
                if options.get("extract_tables", True):
                    for table in doc.tables:
                        table_data = self._extract_table(table)
                        tables.append(table_data)

                # Extract structure
                sections = self._extract_sections(doc, options)

                # Extract comments if requested
                comments = []
                if options.get("extract_comments", False):
                    comments = self._extract_comments(doc)

                # Extract formatting if requested
                formatting_info = None
                if options.get("extract_formatting", False):
                    formatting_info = self._extract_formatting(doc)

                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=(
                        f"Parsed {len(paragraphs)} paragraphs, {len(tables)} tables"
                    ),
                )
                return {
                    "metadata": metadata.__dict__,
                    "full_text": "\n\n".join(paragraphs),
                    "paragraphs": paragraphs,
                    "tables": tables,
                    "sections": [s.__dict__ for s in sections],
                    "comments": comments,
                    "formatting": formatting_info,
                    "total_paragraphs": len(paragraphs),
                    "total_tables": len(tables),
                }

            except Exception as e:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message=str(e)
                )
                self.logger.error(f"Failed to parse DOCX {file_path}: {e}")
                raise ProcessingError(f"Failed to parse DOCX: {e}")

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def extract_text(self, file_path: Union[str, Path]) -> str:
        """
        Extract text from DOCX.

        Args:
            file_path: Path to DOCX file

        Returns:
            str: Extracted text
        """
        result = self.parse(
            file_path,
            extract_tables=False,
            extract_comments=False,
            extract_formatting=False,
        )
        return result["full_text"]

    def extract_tables(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Extract tables from DOCX.

        Args:
            file_path: Path to DOCX file

        Returns:
            list: Extracted tables
        """
        result = self.parse(file_path, extract_formatting=False, extract_comments=False)
        return result["tables"]

    def _extract_table(self, table: Table) -> Dict[str, Any]:
        """Extract data from table."""
        table_data = {
            "rows": [],
            "row_count": len(table.rows),
            "col_count": len(table.columns) if table.rows else 0,
        }

        for row in table.rows:
            row_data = []
            for cell in row.cells:
                cell_text = "\n".join(
                    _paragraph_text(p) for p in cell.paragraphs
                ).strip()
                row_data.append(cell_text)
            table_data["rows"].append(row_data)

        return table_data

    def _extract_sections(
        self, doc: DocxDocument, options: Dict[str, Any]
    ) -> List[DocxSection]:
        """Extract document sections based on headings."""
        sections = []
        current_section = None

        for para in doc.paragraphs:
            text = _paragraph_text(para).strip()
            # Check if paragraph is a heading
            if para.style.name.startswith("Heading"):
                # Get heading level
                level = (
                    int(para.style.name.split()[-1])
                    if para.style.name.split()[-1].isdigit()
                    else 1
                )

                # Save previous section if exists
                if current_section:
                    sections.append(current_section)

                # Create new section
                current_section = DocxSection(
                    heading=text,
                    level=level,
                    content="",
                    paragraphs=[],
                    tables=[],
                )
            elif current_section:
                # Add paragraph to current section
                if text:
                    current_section.paragraphs.append(text)
                    current_section.content += text + "\n\n"

        # Add last section
        if current_section:
            sections.append(current_section)

        return sections

    def _extract_metadata(self, doc: DocxDocument) -> DocxMetadata:
        """Extract document metadata."""
        core_props = doc.core_properties

        return DocxMetadata(
            title=core_props.title,
            author=core_props.author,
            subject=core_props.subject,
            keywords=core_props.keywords,
            comments=core_props.comments,
            category=core_props.category,
            created=str(core_props.created) if core_props.created else None,
            modified=str(core_props.modified) if core_props.modified else None,
            last_modified_by=core_props.last_modified_by,
        )

    def _extract_comments(self, doc: DocxDocument) -> List[Dict[str, Any]]:
        """Extract comments from document."""
        comments = []
        # Note: python-docx doesn't directly support comments
        # This would require additional processing
        return comments

    def _extract_formatting(self, doc: DocxDocument) -> Dict[str, Any]:
        """Extract formatting information."""
        formatting = {"paragraphs": []}

        for para in doc.paragraphs:
            para_formatting = {
                "text": _paragraph_text(para),
                "style": para.style.name,
                "alignment": str(para.alignment) if para.alignment else None,
                "runs": [],
            }

            for run in para.runs:
                run_formatting = {
                    "text": run.text,
                    "bold": run.bold,
                    "italic": run.italic,
                    "underline": run.underline,
                    "font_name": run.font.name if run.font.name else None,
                    "font_size": run.font.size.pt if run.font.size else None,
                }
                para_formatting["runs"].append(run_formatting)

            formatting["paragraphs"].append(para_formatting)

        return formatting
