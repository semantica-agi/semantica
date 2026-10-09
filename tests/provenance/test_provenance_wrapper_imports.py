"""
Regression tests for provenance wrapper import resolution.

Every ``*WithProvenance`` wrapper imports its underlying implementation lazily,
inside ``__init__``.  A wrong import path is therefore invisible at import time
and only surfaces when the wrapper is instantiated.  The surrounding suites
guard those instantiations with ``except ImportError: pytest.skip(...)``, which
converts the failure into a skip and hides it from CI.

These tests intentionally do not skip: if a wrapper cannot resolve its
underlying implementation, the test fails.
"""


class TestIngestProvenanceWrapper:
    """PDFIngestorWithProvenance must resolve the file ingestor it wraps."""

    def test_instantiates_and_wraps_file_ingestor(self):
        from semantica.ingest.file_ingestor import FileIngestor
        from semantica.ingest.ingest_provenance import PDFIngestorWithProvenance

        wrapper = PDFIngestorWithProvenance(provenance=False)
        assert isinstance(wrapper._ingestor, FileIngestor)

    def test_delegates_unknown_attributes(self):
        from semantica.ingest.ingest_provenance import PDFIngestorWithProvenance

        wrapper = PDFIngestorWithProvenance(provenance=False)
        # `ingest_file` is defined on FileIngestor, not on the wrapper.
        assert callable(wrapper.ingest_file)


def _tracked_ingest_wrapper():
    """Return a PDF wrapper whose provenance manager is a recording mock."""
    from unittest.mock import MagicMock

    from semantica.ingest.ingest_provenance import PDFIngestorWithProvenance

    wrapper = PDFIngestorWithProvenance(provenance=False)
    wrapper.provenance = True
    wrapper._prov_manager = MagicMock()
    return wrapper


class TestPDFIngestProvenanceContract:
    """Provenance must never label a non-PDF (or a directory) as ``pdf``."""

    def test_pdf_file_is_ingested_and_tracked_as_pdf(self, tmp_path):
        pdf = tmp_path / "doc.PDF"
        pdf.write_bytes(b"%PDF-1.4 minimal")
        wrapper = _tracked_ingest_wrapper()

        docs = wrapper.ingest(str(pdf))

        assert [d.file_type for d in docs] == ["pdf"]
        wrapper._prov_manager.track_entity.assert_called_once()
        kwargs = wrapper._prov_manager.track_entity.call_args.kwargs
        assert kwargs["source"] == str(pdf)
        assert kwargs["metadata"]["file_type"] == "pdf"

    def test_non_pdf_file_is_rejected_without_provenance(self, tmp_path):
        import pytest

        from semantica.utils.exceptions import ValidationError

        txt = tmp_path / "notes.txt"
        txt.write_text("not a pdf")
        wrapper = _tracked_ingest_wrapper()

        with pytest.raises(ValidationError):
            wrapper.ingest(str(txt))
        wrapper._prov_manager.track_entity.assert_not_called()

    def test_directories_are_rejected_without_provenance(self, tmp_path):
        import pytest

        from semantica.utils.exceptions import ValidationError

        (tmp_path / "inner.pdf").write_bytes(b"%PDF-1.4")
        wrapper = _tracked_ingest_wrapper()

        # A plain directory and a directory whose *name* ends in .pdf.
        fake_pdf_dir = tmp_path / "looks_like.pdf"
        fake_pdf_dir.mkdir()
        (fake_pdf_dir / "secret.txt").write_text("x")

        for target in (tmp_path, fake_pdf_dir):
            with pytest.raises(ValidationError):
                wrapper.ingest(str(target))
        wrapper._prov_manager.track_entity.assert_not_called()


class TestParseProvenanceWrapper:
    """ParserWithProvenance must resolve the document parser it wraps."""

    def test_instantiates_and_wraps_document_parser(self):
        from semantica.parse.document_parser import DocumentParser
        from semantica.parse.parse_provenance import ParserWithProvenance

        wrapper = ParserWithProvenance(provenance=False)
        assert isinstance(wrapper._parser, DocumentParser)

    def test_delegates_unknown_attributes(self):
        from semantica.parse.parse_provenance import ParserWithProvenance

        wrapper = ParserWithProvenance(provenance=False)
        # `parse_document` is defined on DocumentParser, not on the wrapper.
        assert callable(wrapper.parse_document)

    def test_parse_delegates_and_tracks_provenance(self, tmp_path):
        from unittest.mock import MagicMock

        from semantica.parse.parse_provenance import ParserWithProvenance

        txt = tmp_path / "a.txt"
        txt.write_text("hello")
        wrapper = ParserWithProvenance(provenance=False)
        wrapper.provenance = True
        wrapper._prov_manager = MagicMock()

        result = wrapper.parse(str(txt))

        assert result["text"] == "hello"
        wrapper._prov_manager.track_entity.assert_called_once()
        kwargs = wrapper._prov_manager.track_entity.call_args.kwargs
        assert kwargs["source"] == str(txt)
        assert kwargs["entity_type"] == "parsed_data"
