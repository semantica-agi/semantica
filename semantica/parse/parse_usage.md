# Data Parsing Module Usage Guide

This comprehensive guide demonstrates how to use the data parsing module for document parsing, web content parsing, structured data parsing, email parsing, code parsing, and media parsing. The module supports parsing various file formats including PDF, DOCX, PPTX, HTML, JSON, CSV, XML, images, and more.

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Document Parsing](#document-parsing)
3. [Web Content Parsing](#web-content-parsing)
4. [Structured Data Parsing](#structured-data-parsing)
5. [Email Parsing](#email-parsing)
6. [Code Parsing](#code-parsing)
7. [Media Parsing](#media-parsing)
8. [Format-Specific Parsers](#format-specific-parsers)
9. [Using Methods](#using-methods)
10. [Using Registry](#using-registry)
11. [Configuration](#configuration)
12. [Advanced Examples](#advanced-examples)

## Basic Usage

### Using Main Classes

```python
from semantica.parse import DocumentParser, WebParser, StructuredDataParser

# Create parsers
doc_parser = DocumentParser()
web_parser = WebParser()
data_parser = StructuredDataParser()

# Parse document
doc = doc_parser.parse_document("document.pdf")
print(f"Text: {doc.get('full_text', '')}")

# Parse web content
web = web_parser.parse_web_content("https://example.com", content_type="html")
print(f"Content: {web.get('text', '')}")

# Parse structured data
data = data_parser.parse_data("data.json", data_format="json")
print(f"Data: {data}")
```

## Document Parsing

### PDF Parsing

```python
from semantica.parse import PDFParser

# Using PDFParser
pdf_parser = PDFParser()
pdf_data = pdf_parser.parse("document.pdf", extract_text=True, extract_tables=True)

# Extract specific pages
pdf_pages = pdf_parser.parse("document.pdf", pages=[1, 2, 3])

# Extract only text
text = pdf_parser.extract_text("document.pdf")

# Extract only tables
tables = pdf_parser.extract_tables("document.pdf")
```

### DOCX Parsing

```python
from semantica.parse import DOCXParser

# Using DOCXParser
docx_parser = DOCXParser()
docx_data = docx_parser.parse("document.docx", extract_tables=True)

# Extract sections
sections = docx_parser.extract_sections("document.docx")

# Extract metadata
metadata = docx_parser.extract_metadata("document.docx")
print(f"Author: {metadata.author}")
print(f"Title: {metadata.title}")
```

### PPTX Parsing

```python
from semantica.parse import PPTXParser

pptx_parser = PPTXParser()
pptx_data = pptx_parser.parse("presentation.pptx")

print(f"Title: {pptx_data.title}")
print(f"Slides: {len(pptx_data.slides)}")

for slide in pptx_data.slides:
    print(f"Slide {slide.slide_number}: {slide.title}")
    print(f"  Text: {slide.text}")
    print(f"  Notes: {slide.notes}")
```

### Excel Parsing

```python
from semantica.parse import ExcelParser

excel_parser = ExcelParser()
excel_data = excel_parser.parse("spreadsheet.xlsx")

print(f"Sheets: {excel_data.sheet_names}")

for sheet_name, sheet in excel_data.sheets.items():
    print(f"Sheet: {sheet_name}")
    print(f"  Rows: {sheet.row_count}")
    print(f"  Columns: {sheet.column_count}")
    print(f"  Headers: {sheet.headers}")
```

### HTML Document Parsing

```python
from semantica.parse import HTMLParser

# Using HTMLParser
html_parser = HTMLParser()
html_data = html_parser.parse("page.html", extract_links=True, extract_images=True)

# Extract metadata
metadata = html_parser.extract_metadata("page.html")
print(f"Title: {metadata.title}")
print(f"Description: {metadata.description}")

# Extract links
links = html_parser.extract_links("page.html")
for link in links:
    print(f"Link: {link.get('href', '')} - {link.get('text', '')}")
```

### Text File Parsing

```python
from semantica.parse import DocumentParser

# Parse plain text file
doc_parser = DocumentParser()
text_doc = doc_parser.parse_document("document.txt")
print(f"Text: {text_doc.get('text', '')}")
```

### Docling Parsing (Enhanced Layout & Tables)

`DoclingParser` is a specialized parser that provides superior extraction for complex documents with nested tables, multi-column layouts, and varied structures. It is recommended for production-grade document processing.

#### Features
- **Multi-format Support**: PDF, DOCX, PPTX, XLSX, HTML, and images.
- **Superior Table Extraction**: Advanced layout analysis for nested and complex tables.
- **OCR Support**: Built-in support for scanned documents and images.
- **Multiple Export Formats**: Export to Markdown, HTML, or JSON.

#### Basic Usage

```python
from semantica.parse import DoclingParser

# Initialize DoclingParser
# Requires 'docling' package: pip install docling
parser = DoclingParser()

# 1. Parse document
result = parser.parse("complex_invoice.pdf")

# 2. Extract structured content
# result contains the full Docling document object if available
print(f"Extracted Text (Markdown): {result['full_text']}")

# 3. Access extracted tables with high accuracy
for i, table in enumerate(result['tables']):
    print(f"Table {i+1} headers: {table.get('headers', [])}")
    print(f"Table {i+1} row count: {len(table.get('rows', []))}")

# 4. Extract metadata
metadata = result['metadata']
print(f"Title: {metadata.get('title')}")
print(f"Page Count: {metadata.get('page_count')}")
```

#### Advanced Configuration

You can customize the parser with various options:

```python
from semantica.parse import DoclingParser

# Initialize with custom export format and OCR enabled
parser = DoclingParser(
    export_format="html",  # Options: "markdown", "html", "json"
    enable_ocr=True        # Enable OCR for scanned documents
)

# Parse with specific export format
result = parser.parse("scanned_document.pdf")
print(f"HTML Content: {result['full_text']}")

# Batch processing
results = parser.parse_batch(["doc1.pdf", "doc2.docx"])
```

#### Direct Extraction Methods

For simple use cases, use direct extraction methods:

```python
from semantica.parse import DoclingParser

parser = DoclingParser()

# Extract only text (as markdown)
markdown_text = parser.extract_text("report.pdf")

# Extract only tables
tables = parser.extract_tables("data_sheet.pdf")

# Extract metadata
metadata = parser.extract_metadata("document.pdf")
```

## Web Content Parsing

### HTML Content Parsing

```python
from semantica.parse import WebParser

# Using WebParser
web_parser = WebParser()
html_data = web_parser.parse_web_content("https://example.com", content_type="html")

# Extract text
text = web_parser.extract_text("https://example.com")

# Extract links
links = web_parser.extract_links("https://example.com")
for link in links:
    print(f"Link: {link.get('href', '')}")

# Render JavaScript content
rendered = web_parser.render_javascript("https://example.com", wait_time=5)
```

### XML Content Parsing

```python
from semantica.parse import XMLParser

# Using XMLParser
xml_parser = XMLParser()
xml_data = xml_parser.parse("data.xml")

# Find elements using XPath
elements = xml_parser.find_elements("data.xml", "//item")
for element in elements:
    print(f"Element: {element.tag} - {element.text}")
```

### JavaScript-Rendered Content

```python
from semantica.parse import WebParser, JavaScriptRenderer

# Using JavaScript renderer
js_renderer = JavaScriptRenderer()
rendered_html = js_renderer.render_page("https://example.com", wait_time=5)

# Using WebParser with JavaScript rendering
web_parser = WebParser()
rendered_content = web_parser.parse_web_content(
    "https://example.com",
    content_type="html",
    render_javascript=True,
    wait_time=5
)
```

## Structured Data Parsing

### JSON Parsing

```python
from semantica.parse import JSONParser

# Using JSONParser
json_parser = JSONParser()
json_data = json_parser.parse("data.json", flatten=True)

# Extract JSON paths
paths = json_parser.extract_paths("data.json")
for path in paths:
    print(f"Path: {path}")
```

### CSV Parsing

```python
from semantica.parse import CSVParser

# Using CSVParser
csv_parser = CSVParser()
csv_data = csv_parser.parse("data.csv", delimiter=",", has_header=True)

# Parse to dictionary list
rows = csv_parser.parse_to_dict("data.csv")
for row in rows:
    print(f"Row: {row}")
```

### XML Parsing

```python
from semantica.parse import XMLParser

# Using XMLParser
xml_parser = XMLParser()
xml_data = xml_parser.parse("data.xml", engine="lxml")

# Find elements
elements = xml_parser.find_elements("data.xml", "//item")
for element in elements:
    print(f"Element: {element.tag} - {element.text}")
```

### YAML Parsing

```python
from semantica.parse import StructuredDataParser

data_parser = StructuredDataParser()
yaml_data = data_parser.parse_data("config.yaml", data_format="yaml")
print(f"Data: {yaml_data}")
```

## Email Parsing

### Basic Email Parsing

```python
from semantica.parse import EmailParser

# Using EmailParser
email_parser = EmailParser()
email_data = email_parser.parse_email("email.eml", extract_attachments=True)

# Access headers from parsed email
headers = email_data.headers
print(f"Subject: {headers.subject}")
print(f"Date: {headers.date}")

# Access body from parsed email
body = email_data.body
print(f"Text: {body.text}")
print(f"HTML: {body.html}")
```

### Email Thread Analysis

```python
from semantica.parse import EmailParser

email_parser = EmailParser()

# Analyze email thread
emails = []
for email_file in ["email1.eml", "email2.eml", "email3.eml"]:
    emails.append(email_parser.parse_email(email_file))

thread = email_parser.analyze_thread(emails)
print(f"Messages: {len(thread.get('messages', []))}")
```

### Email Attachment Extraction

```python
from semantica.parse import EmailParser

email_parser = EmailParser()
email_data = email_parser.parse_email("email.eml", extract_attachments=True)

# Access attachments
for attachment in email_data.body.attachments:
    print(f"Filename: {attachment.get('filename', '')}")
    print(f"Content Type: {attachment.get('content_type', '')}")
    print(f"Size: {attachment.get('size', 0)}")
```

## Code Parsing

### Basic Code Parsing

```python
from semantica.parse import CodeParser

# Using CodeParser
code_parser = CodeParser()
code_data = code_parser.parse_code("script.py", language="python")

# Access structure, comments, dependencies
structure = code_data.get("structure", {})
print(f"Functions: {structure.get('functions', [])}")
print(f"Classes: {structure.get('classes', [])}")
print(f"Imports: {structure.get('imports', [])}")

comments = code_data.get("comments", [])
for comment in comments:
    print(f"Comment: {comment.get('text', '')} (Line {comment.get('line_number', 0)})")

dependencies = code_data.get("dependencies", {})
print(f"Dependencies: {dependencies}")
```

### AST Parsing

```python
from semantica.parse import CodeParser, SyntaxTreeParser

code_parser = CodeParser()
syntax_parser = SyntaxTreeParser()

# Parse file content then build syntax tree
with open("script.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

tree = syntax_parser.parse_syntax_tree(content, language="python")

# Structure and imports are provided via parse_code
code_data = code_parser.parse_code("script.py", language="python")
structure = code_data.get("structure", {})
print(f"Functions: {structure.get('functions', [])}")
print(f"Classes: {structure.get('classes', [])}")
print(f"Imports: {structure.get('imports', [])}")
```

### Multi-Language Code Parsing

```python
from semantica.parse import CodeParser

code_parser = CodeParser()

# Parse Python code
python_code = code_parser.parse_code("script.py", language="python")

# Parse JavaScript code
js_code = code_parser.parse_code("script.js", language="javascript")

# Parse Java code
java_code = code_parser.parse_code("Main.java", language="java")
```

## Media Parsing

### Image Parsing with OCR

```python
from semantica.parse import ImageParser

# Using ImageParser
image_parser = ImageParser()
image_data = image_parser.parse("image.jpg", extract_text=True, ocr_language="eng")

# Extract metadata only
metadata = image_parser.extract_metadata("image.jpg")
print(f"Format: {metadata.format}")
print(f"Size: {metadata.size}")
print(f"EXIF: {metadata.exif}")

# Extract text with OCR
ocr_result = image_parser.extract_text("image.jpg", language="eng")
print(f"Text: {ocr_result.text}")
print(f"Confidence: {ocr_result.confidence}")
```

`ImageParser` only opens PNG, JPEG (including multi-picture JPEGs), WebP and
BMP by default, and rejects files over 50 MB or `PIL.Image.MAX_IMAGE_PIXELS`
pixels. The format is detected from the file contents, not the extension.

- TIFF and GIF must be enabled explicitly. Their Pillow decoders have open
  advisories (#2067), and enabling TIFF re-exposes all four TIFF ones.
- `allowed_formats` replaces the default list, so include every format you
  need. `"JPG"` and `"TIF"` are accepted as aliases. EPS can't be enabled.
- `max_pixels` can't exceed `2 * PIL.Image.MAX_IMAGE_PIXELS`, because Pillow
  refuses larger images itself. If your application sets
  `PIL.Image.MAX_IMAGE_PIXELS = None`, the default is 89,478,485 pixels.
- On memory-constrained hosts, lower `max_pixels`: `extract_text()` and
  `preprocess_image()` decode the whole image, and a WebP at the default
  limit can take about 2 GB.
- Rejected files raise `ValidationError`, not `ProcessingError`; both derive
  from `SemanticaError`.
- `preprocess_image()` always writes PNG, as `<stem>_preprocessed.png` next
  to the input. Inputs that differ only by extension (`a.png`, `a.jpg`)
  share that output path.

```python
image_parser = ImageParser(
    allowed_formats=["PNG", "JPEG", "WEBP", "BMP", "TIFF"],  # defaults + TIFF
    max_file_size=20 * 1024 * 1024,  # bytes
    max_pixels=50_000_000,
)
```

### Media File Parsing

```python
from semantica.parse import MediaParser

# Using MediaParser
media_parser = MediaParser()
media_data = media_parser.parse_media("image.jpg", media_type="image")

# Parse audio/video similarly by specifying media_type
video = media_parser.parse_media("video.mp4", media_type="video")
audio = media_parser.parse_media("audio.mp3", media_type="audio")
```

## Format-Specific Parsers

### PDF Parser

```python
from semantica.parse import PDFParser, PDFPage, PDFMetadata

pdf_parser = PDFParser()

# Parse PDF
pdf_data = pdf_parser.parse("document.pdf", extract_text=True, extract_tables=True)

# Access pages
for page in pdf_data.get("pages", []):
    print(f"Page {page['page_number']}: {len(page['text'])} characters")
    print(f"  Tables: {len(page['tables'])}")
    print(f"  Images: {len(page['images'])}")

# Access metadata
metadata = pdf_data.get("metadata", {})
print(f"Title: {metadata.get('title')}")
print(f"Author: {metadata.get('author')}")
print(f"Page Count: {metadata.get('page_count')}")
```

### DOCX Parser

```python
from semantica.parse import DOCXParser

docx_parser = DOCXParser()

# Parse DOCX
docx_data = docx_parser.parse("document.docx", extract_tables=True)

# Access sections
for section in docx_data.get("sections", []):
    print(f"Section: {section['heading']} (Level {section['level']})")
    print(f"  Content: {section['content'][:100]}...")

# Access metadata
metadata = docx_data.get("metadata", {})
print(f"Title: {metadata.get('title')}")
print(f"Author: {metadata.get('author')}")
```

### JSON Parser

```python
from semantica.parse import JSONParser, JSONData

json_parser = JSONParser()

# Parse JSON
json_data = json_parser.parse("data.json", flatten=True)

# Access data
print(f"Type: {json_data.type}")
print(f"Data: {json_data.data}")
print(f"Metadata: {json_data.metadata}")

# Extract paths
paths = json_parser.extract_paths("data.json")
for path in paths:
    print(f"Path: {path}")
```

### CSV Parser

```python
from semantica.parse import CSVParser, CSVData

csv_parser = CSVParser()

# Parse CSV
csv_data = csv_parser.parse("data.csv", delimiter=",", has_header=True)

# Access data
print(f"Headers: {csv_data.headers}")
print(f"Row Count: {csv_data.row_count}")

# Access rows
for row in csv_data.rows:
    print(f"Row: {row}")

# Parse to dictionary list
rows = csv_parser.parse_to_dict("data.csv")
for row in rows:
    print(f"Row: {row}")
```

### XML Parser

```python
from semantica.parse import XMLParser, XMLData, XMLElement

xml_parser = XMLParser()

# Parse XML
xml_data = xml_parser.parse("data.xml", engine="lxml")

# Access root element
root = xml_data.root
print(f"Root Tag: {root.tag}")
print(f"Root Text: {root.text}")

# Access children
for child in root.children:
    print(f"Child: {child.tag} - {child.text}")

# Find elements
elements = xml_parser.find_elements("data.xml", "//item")
for element in elements:
    print(f"Element: {element.tag} - {element.text}")
```

### Image Parser

```python
from semantica.parse import ImageParser, ImageMetadata, OCRResult

image_parser = ImageParser()

# Parse image
image_data = image_parser.parse("image.jpg", extract_text=True, ocr_language="eng")

# Access metadata
metadata = ImageMetadata(**image_data.get("metadata", {}))
print(f"Format: {metadata.format}")
print(f"Size: {metadata.size}")
print(f"EXIF: {metadata.exif}")

# Access OCR result
if "ocr_result" in image_data:
    ocr = OCRResult(**image_data["ocr_result"])
    print(f"OCR Text: {ocr.text}")
    print(f"Confidence: {ocr.confidence}")
    print(f"Language: {ocr.language}")
```

 

## Using Registry

### Registering Custom Methods

```python
from semantica.parse import method_registry

# Register document parsing method
def my_document_parser(file_path, file_type=None, **kwargs):
    # Custom implementation
    return {"text": "Parsed", "metadata": {}}

method_registry.register("document", "my_parser", my_document_parser)

# Register web parsing method
def my_web_parser(content, content_type="html", base_url=None, **kwargs):
    # Custom implementation
    return {"text": "Parsed", "links": []}

method_registry.register("web", "my_parser", my_web_parser)
```

### Listing Registered Methods

```python
from semantica.parse import method_registry

# List all methods
all_methods = method_registry.list_all()
print(f"All methods: {all_methods}")

# List methods for specific task
document_methods = method_registry.list_all("document")
print(f"Document methods: {document_methods}")

web_methods = method_registry.list_all("web")
print(f"Web methods: {web_methods}")
```

### Getting Methods

```python
from semantica.parse import method_registry

# Get method directly
method = method_registry.get("document", "default")
if method:
    result = method("document.pdf")
```

### Unregistering Methods

```python
from semantica.parse import method_registry

# Unregister specific method
method_registry.unregister("document", "custom")

# Clear all methods for a task
method_registry.clear("document")

# Clear all methods
method_registry.clear()
```

## Configuration

### Environment Variables

```python
import os

# Set environment variables
os.environ["PARSE_DEFAULT_ENCODING"] = "utf-8"
os.environ["PARSE_OCR_LANGUAGE"] = "eng"
os.environ["PARSE_EXTRACT_TABLES"] = "true"
os.environ["PARSE_EXTRACT_IMAGES"] = "false"
os.environ["PARSE_EXTRACT_METADATA"] = "true"
os.environ["PARSE_JS_RENDERING"] = "false"
```

### Config File

Create a `config.yaml` file:

```yaml
parse:
  default_encoding: "utf-8"
  ocr_language: "eng"
  extract_tables: true
  extract_images: false
  extract_metadata: true
  js_rendering: false

parse_methods:
  document:
    extract_tables: true
    extract_images: false
  web:
    render_javascript: false
  structured:
    encoding: "utf-8"
```

Load config:

```python
from semantica.parse.config import ParseConfig

# Load from config file
parse_config = ParseConfig(config_file="config.yaml")

# Access configuration
encoding = parse_config.get("default_encoding", default="utf-8")
ocr_lang = parse_config.get("ocr_language", default="eng")
```

### Programmatic Configuration

```python
from semantica.parse import parse_config

# Set configuration
parse_config.set("default_encoding", "utf-8")
parse_config.set("ocr_language", "eng")
parse_config.set("extract_tables", True)

# Get configuration
encoding = parse_config.get("default_encoding", default="utf-8")
ocr_lang = parse_config.get("ocr_language", default="eng")

# Method-specific configuration
parse_config.set_method_config("document", extract_tables=True, extract_images=False)
parse_config.set_method_config("web", render_javascript=False)

# Get method configuration
doc_config = parse_config.get_method_config("document")
web_config = parse_config.get_method_config("web")

# Get all configuration
all_config = parse_config.get_all()
print(f"All config: {all_config}")
```

## Advanced Examples

### Batch Document Processing

```python
from semantica.parse import DocumentParser
from pathlib import Path

# Process multiple documents
documents = ["doc1.pdf", "doc2.docx", "doc3.html"]
results = []

doc_parser = DocumentParser()

for doc_path in documents:
    try:
        result = doc_parser.parse_document(doc_path)
        results.append({
            "file": doc_path,
            "text": result.get("full_text", ""),
            "metadata": result.get("metadata", {})
        })
    except Exception as e:
        print(f"Error parsing {doc_path}: {e}")

# Process all PDFs in a directory
pdf_dir = Path("documents")
pdf_files = list(pdf_dir.glob("*.pdf"))

for pdf_file in pdf_files:
    result = doc_parser.parse_document(pdf_file)
    print(f"Processed: {pdf_file.name} ({result.get('total_pages', 0)} pages)")
```

### Multi-Format Data Extraction

```python
from semantica.parse import DocumentParser, JSONParser, CSVParser, XMLParser

doc_parser = DocumentParser()
json_parser = JSONParser()
csv_parser = CSVParser()
xml_parser = XMLParser()

files = [
    ("document.pdf", lambda p: doc_parser.parse_document(p)),
    ("data.json", lambda p: json_parser.parse(p)),
    ("data.csv", lambda p: csv_parser.parse(p)),
    ("data.xml", lambda p: xml_parser.parse(p)),
]

extracted_data = {}

for file_path, parse_fn in files:
    try:
        data = parse_fn(file_path)
        extracted_data[file_path] = data
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")

for file_path, data in extracted_data.items():
    print(f"File: {file_path}")
    if isinstance(data, dict):
        print(f"  Keys: {list(data.keys())}")
```

### Email Thread Reconstruction

```python
from semantica.parse import EmailParser
from pathlib import Path

email_parser = EmailParser()

# Process email thread
email_files = ["email1.eml", "email2.eml", "email3.eml"]
thread_messages = []

for email_file in email_files:
    email = email_parser.parse_email(email_file)
    thread_messages.append({
        "subject": email.headers.subject,
        "from": email.headers.from_address,
        "date": email.headers.date,
        "body": email.body.text,
        "in_reply_to": email.headers.in_reply_to,
        "references": email.headers.references
    })

# Sort by date
thread_messages.sort(key=lambda x: x["date"] or "")

# Display thread
for i, msg in enumerate(thread_messages, 1):
    print(f"Message {i}:")
    print(f"  From: {msg['from']}")
    print(f"  Subject: {msg['subject']}")
    print(f"  Date: {msg['date']}")
    print(f"  Body: {msg['body'][:100]}...")
```

### Code Repository Analysis

```python
from semantica.parse import CodeParser
from pathlib import Path

code_parser = CodeParser()

# Analyze code repository
repo_path = Path("repository")
code_files = list(repo_path.rglob("*.py"))

all_functions = []
all_classes = []
all_imports = []

for code_file in code_files:
    try:
        code_data = code_parser.parse_code(code_file, language="python")
        structure = code_data.get("structure", {})
        
        all_functions.extend(structure.get("functions", []))
        all_classes.extend(structure.get("classes", []))
        all_imports.extend(structure.get("imports", []))
    except Exception as e:
        print(f"Error parsing {code_file}: {e}")

print(f"Total functions: {len(all_functions)}")
print(f"Total classes: {len(all_classes)}")
print(f"Total imports: {len(set(all_imports))}")
```

### OCR Batch Processing

```python
from semantica.parse import ImageParser
from pathlib import Path

# Process all images in a directory
image_dir = Path("images")
image_files = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png"))

ocr_results = []

parser = ImageParser()

for image_file in image_files:
    try:
        image_data = parser.parse(image_file, extract_text=True)
        
        if "ocr_result" in image_data:
            ocr_results.append({
                "file": image_file.name,
                "text": image_data["ocr_result"].text,
                "confidence": image_data["ocr_result"].confidence
            })
    except Exception as e:
        print(f"Error processing {image_file}: {e}")

# Display results
for result in ocr_results:
    print(f"File: {result['file']}")
    print(f"  Text: {result['text'][:100]}...")
    print(f"  Confidence: {result['confidence']:.2f}")
```

### Custom Parser Pipeline

```python
from semantica.parse import DocumentParser, StructuredDataParser, method_registry

doc_parser = DocumentParser()
data_parser = StructuredDataParser()

def pipeline_parser(file_path, file_type=None, **kwargs):
    doc = doc_parser.parse_document(file_path, file_type=file_type, **kwargs)
    structured_data = {}
    suffix = str(file_path).lower()
    if suffix.endswith(".json"):
        structured_data = data_parser.parse_data(file_path, data_format="json")
    elif suffix.endswith(".csv"):
        structured_data = data_parser.parse_data(file_path, data_format="csv")
    elif suffix.endswith(".xml"):
        structured_data = data_parser.parse_data(file_path, data_format="xml")
    return {
        "document": doc,
        "structured": structured_data,
        "combined_text": doc.get("full_text", "") + str(structured_data)
    }

method_registry.register("document", "pipeline", pipeline_parser)

method = method_registry.get("document", "pipeline")
if method:
    result = method("document.pdf")
    print(f"Combined text: {result['combined_text']}")
```

This comprehensive guide covers all major features of the data parsing module. For more specific use cases or advanced scenarios, refer to the individual parser class documentation or explore the source code.

