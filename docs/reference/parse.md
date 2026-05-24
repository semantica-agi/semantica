---
title: "Parse Module"
description: "Document parsing and text extraction — DocumentParser for standard formats and DoclingParser for complex layouts."
icon: "file-lines"
---

`semantica.parse` extracts structured text, layout, tables, and metadata from unstructured documents. `DocumentParser` handles clean machine-readable files; `DoclingParser` handles complex layouts, scanned PDFs, and multi-column documents.

## Exported Classes

```python
from semantica.parse import (
    DocumentParser,    # auto-detect format — delegates to format-specific parser
    PDFParser,         # PDF text extraction
    DOCXParser,        # Word .docx documents
    HTMLParser,        # HTML / web pages
    MarkdownParser,    # Markdown files
    TXTParser,         # plain text
    JSONParser,        # JSON documents
    XMLParser,         # XML documents
    CSVParser,         # CSV / TSV files
    WebParser,         # URL fetch + HTML parsing
    EmailParser,       # .eml / .msg email files
    CodeParser,        # source code files
    # Data types
    ParsedDocument,    # {text, sections, tables, metadata, source_id}
    DocumentMetadata,  # {title, author, created_date, page_count, language, ...}
)

# Optional — requires: pip install "semantica[docling]"
from semantica.parse import DoclingParser  # advanced OCR + layout analysis
```

## What You Get

- **`DocumentParser`** — standard parser for PDF, DOCX, HTML, TXT, JSON, CSV, PPTX, XLSX — auto-detects format
- **`DoclingParser`** — advanced parser for complex layouts, merged-cell tables, multi-column PDFs, and OCR (optional dep)
- **`ParsedDocument`** — structured output with `text`, `sections`, `tables`, and `metadata`
- **Format-specific parsers** — `PDFParser`, `DOCXParser`, `HTMLParser`, `WebParser`, `EmailParser`, `CodeParser`, etc.

## DocumentParser

Standard parser for clean, machine-readable documents:

```python
from semantica.parse import DocumentParser

parser = DocumentParser()
parsed = parser.parse("data/report.pdf")

print(parsed.text)       # full clean text
print(parsed.metadata)   # title, author, date, page_count, language, etc.
print(parsed.sections)   # document structure as a list of Section objects
```

Supported formats: PDF, DOCX, HTML, TXT, JSON, CSV, PPTX, XLSX.

## DoclingParser

Advanced parser using the Docling backend — handles layouts that `DocumentParser` cannot:

```bash
pip install "semantica[docling]"
```

```python
from semantica.parse import DoclingParser

parser = DoclingParser(
    extract_tables=True,       # structured table extraction with cell type detection
    extract_images=True,       # extract image regions for downstream OCR
    output_format="markdown",  # "markdown" | "html" | "json"
)

parsed = parser.parse("data/annual_report.pdf")

print(parsed.text)     # full clean text
print(parsed.tables)   # structured TableData objects with headers and rows
print(parsed.sections) # document structure with heading hierarchy
```

Use `DoclingParser` for:

- Multi-column PDF layouts
- Tables with merged cells or complex headers
- PPTX slides with embedded charts
- XLSX spreadsheets with formulas
- Scanned documents with OCR
- Academic papers and technical reports

## OCR Support

```python
parser = DoclingParser(
    ocr=True,
    ocr_language=["en"],   # ISO 639-1 codes; list for multi-language documents
    extract_tables=True,
)

parsed = parser.parse("data/scanned_contract.pdf")
```

## Parsed Document Object

Both parsers return a `ParsedDocument` with the same structure:

```python
@dataclass
class ParsedDocument:
    text:      str                  # full extracted text
    sections:  List[Section]        # heading-based document structure
    tables:    List[TableData]      # structured table data (DoclingParser only)
    metadata:  DocumentMetadata     # title, author, dates, page count
    source_id: str                  # links back to the original DataSource

@dataclass
class DocumentMetadata:
    title:        Optional[str]
    author:       Optional[str]
    created_date: Optional[datetime]
    page_count:   int
    language:     Optional[str]     # ISO 639-1 code
    has_tables:   bool
    has_images:   bool
    word_count:   int
    format:       str               # "pdf" | "docx" | "pptx" | ...
```

## Integration with FileIngestor

The most common pattern — ingest a directory then parse each source:

```python
from semantica.ingest import FileIngestor
from semantica.parse import DoclingParser

ingestor = FileIngestor()
parser   = DoclingParser(extract_tables=True)

sources = ingestor.ingest("data/reports/")
for source in sources:
    parsed = parser.parse(source)
    # → parsed.text, parsed.tables, parsed.sections
```

<Note>
  Docling is an optional dependency. If `docling` is not installed, `DoclingParser` raises an `ImportError` with installation instructions. `DocumentParser` is always available and requires no extras.
</Note>

<CardGroup cols={2}>
  <Card title="Ingest" icon="database" href="ingest">
    Load files before parsing.
  </Card>
  <Card title="Split" icon="scissors" href="split">
    Chunk parsed text for embedding and extraction.
  </Card>
  <Card title="Docling Integration" icon="file-pdf" href="../integrations/docling">
    Full Docling integration setup guide.
  </Card>
  <Card title="Semantic Extract" icon="magnifying-glass" href="semantic_extract">
    Extract entities and relations from parsed text.
  </Card>
</CardGroup>
