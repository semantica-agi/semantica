"""Regression tests for PDFParser's default page selection.

``parse()`` read its page selection with
``options.get("pages", range(len(pdf.pages)))``. ``dict.get`` applies its
default only when the key is *absent*, but ``extract_text()`` and
``extract_tables()`` always forward ``pages=pages`` -- so omitting the
argument put ``None`` in ``options`` and the default never applied. ``for
page_num in None`` then raised ``TypeError``, which ``parse()`` wrapped and
re-raised, making both documented calls fail on every PDF::

    PDFParser().extract_text("document.pdf")
    ProcessingError: Failed to parse PDF: 'NoneType' object is not iterable

``extract_images()`` was unaffected because it does not forward ``pages``.

pdfplumber is mocked, as in test_pdf_scanned_detection.py, so these run on a
core install.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from semantica.parse.pdf_parser import PDFParser


def _mock_pdfplumber(page_count=3):
    """A fake pdfplumber whose PDF has page_count distinct text pages."""
    pages = []
    for i in range(page_count):
        page = MagicMock()
        page.extract_text.return_value = f"Text of page {i}"
        page.extract_tables.return_value = [[["cell", str(i)]]]
        page.width = 612
        page.height = 792
        pages.append(page)

    pdf = MagicMock()
    pdf.pages = pages
    pdf.metadata = {}

    module = MagicMock()
    context_manager = MagicMock()
    context_manager.__enter__.return_value = pdf
    module.open.return_value = context_manager
    return module


class TestPagesDefault(unittest.TestCase):
    """Omitting `pages` must mean every page, not None."""

    def setUp(self):
        tracker_patcher = patch(
            "semantica.parse.pdf_parser.get_progress_tracker"
        )
        tracker_patcher.start()
        self.addCleanup(tracker_patcher.stop)

        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, suffix=".pdf"
        ) as tmp:
            tmp.write(b"dummy pdf content")
            self.path = tmp.name
        self.addCleanup(lambda: os.unlink(self.path))

        self.parser = PDFParser()
        self.pdfplumber = _mock_pdfplumber()

    def _patched(self):
        return patch.dict(sys.modules, {"pdfplumber": self.pdfplumber})

    def test_extract_text_without_pages_reads_every_page(self):
        """The documented default call must not raise."""
        with self._patched():
            text = self.parser.extract_text(self.path)

        for i in range(3):
            self.assertIn(f"Text of page {i}", text)

    def test_extract_tables_without_pages_reads_every_page(self):
        with self._patched():
            tables = self.parser.extract_tables(self.path)

        self.assertEqual(len(tables), 3)
        self.assertEqual(
            sorted(t["page_number"] for t in tables), [1, 2, 3]
        )

    def test_parse_with_pages_none_reads_every_page(self):
        """An explicit pages=None means the same as omitting it."""
        with self._patched():
            result = self.parser.parse(self.path, pages=None)

        self.assertEqual(result["total_pages"], 3)
        self.assertEqual(len(result["pages"]), 3)

    def test_explicit_page_selection_is_still_honoured(self):
        with self._patched():
            result = self.parser.parse(self.path, pages=[0, 2])

        self.assertEqual(len(result["pages"]), 2)
        self.assertEqual(
            [p["page_number"] for p in result["pages"]], [1, 3]
        )

    def test_empty_page_selection_still_selects_nothing(self):
        """pages=[] must stay "no pages", which is why the guard tests
        `is None` rather than falsiness: an `or`-based fix would silently
        turn an empty selection into every page."""
        with self._patched():
            result = self.parser.parse(self.path, pages=[])

        self.assertEqual(result["pages"], [])
        self.assertEqual(result["full_text"], "")


if __name__ == "__main__":
    unittest.main()
