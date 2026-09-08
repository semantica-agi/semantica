"""
HTML Document Parser Module

This module handles HTML parsing using BeautifulSoup and lxml for content extraction
and structure analysis, including metadata, links, and element extraction.

Key Features:
    - HTML content parsing and cleaning
    - Metadata extraction (title, description, Open Graph, Twitter cards)
    - Link and media extraction
    - Element structure analysis
    - Text content extraction
    - BeautifulSoup integration

Main Classes:
    - HTMLParser: HTML document parser
    - HTMLMetadata: Dataclass for HTML metadata representation
    - HTMLElement: Dataclass for HTML element representation

Example Usage:
    >>> from semantica.parse import HTMLParser
    >>> parser = HTMLParser()
    >>> text = parser.parse("page.html")
    >>> metadata = parser.extract_metadata("page.html")
    >>> links = parser.extract_links("page.html")

Author: Semantica Contributors
License: MIT
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

try:
    from bs4 import BeautifulSoup
except (ImportError, OSError):
    BeautifulSoup = None

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


@dataclass
class HTMLMetadata:
    """HTML metadata representation."""

    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    author: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_url: Optional[str] = None
    twitter_card: Optional[str] = None
    canonical_url: Optional[str] = None


@dataclass
class HTMLElement:
    """HTML element representation."""

    tag: str
    text: str
    attributes: Dict[str, str] = field(default_factory=dict)
    children: List["HTMLElement"] = field(default_factory=list)


@dataclass
class HTMLData:
    """HTML document representation."""

    metadata: Dict[str, Any]
    text: str
    html: str
    links: List[Dict[str, Any]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)
    forms: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    structure: List[Dict[str, Any]] = field(default_factory=list)


class HTMLParser:
    """HTML document parser."""

    def __init__(self, **config):
        """
        Initialize HTML parser.

        Args:
            **config: Parser configuration
        """
        self.logger = get_logger("html_parser")
        self.config = config
        self.progress_tracker = get_progress_tracker()

    def parse(
        self, html_content: Union[str, Path], base_url: Optional[str] = None, **options
    ) -> HTMLData:
        """
        Parse HTML content.

        Args:
            html_content: HTML content as string or file path
            base_url: Base URL for resolving relative links
            **options: Parsing options:
                - extract_links: Whether to extract links (default: True)
                - extract_images: Whether to extract images (default: True)
                - extract_forms: Whether to extract forms (default: False)
                - extract_tables: Whether to extract tables (default: True)
                - clean_text: Whether to clean extracted text (default: True)

        Returns:
            HTMLData: Parsed HTML data
        """
        if BeautifulSoup is None:
            raise ProcessingError(
                "beautifulsoup4 is required to parse HTML files. "
                "Install it with: pip install 'semantica[documents]'"
            )

        # Track HTML parsing
        file_path = None
        if isinstance(html_content, Path) or (
            isinstance(html_content, str) and Path(html_content).exists()
        ):
            file_path = Path(html_content)

        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path) if file_path else None,
            module="parse",
            submodule="HTMLParser",
            message=f"HTML: {file_path.name if file_path else 'content'}",
        )

        try:
            # Load HTML content
            if file_path:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    html_string = f.read()
            else:
                html_string = html_content

            try:
                soup = BeautifulSoup(html_string, "html.parser")

                # Extract metadata
                metadata = self._extract_metadata(soup)

                # Extract text content
                if options.get("clean_text", True):
                    text = self._extract_clean_text(soup)
                else:
                    text = soup.get_text()

                # Extract links
                links = []
                if options.get("extract_links", True):
                    links = self._extract_links(soup, base_url)

                # Extract images
                images = []
                if options.get("extract_images", True):
                    images = self._extract_images(soup, base_url)

                # Extract forms
                forms = []
                if options.get("extract_forms", False):
                    forms = self._extract_forms(soup)

                # Extract tables
                tables = []
                if options.get("extract_tables", True):
                    tables = self._extract_tables(soup)

                # Extract structure
                structure = self._extract_structure(soup)

                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Parsed HTML: {len(links)} links, {len(images)} images",
                )
                return HTMLData(
                    metadata=metadata.__dict__,
                    text=text,
                    html=html_string,
                    links=links,
                    images=images,
                    forms=forms,
                    tables=tables,
                    structure=structure,
                )

            except Exception as e:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message=str(e)
                )
                self.logger.error(f"Failed to parse HTML: {e}")
                raise ProcessingError(f"Failed to parse HTML: {e}")

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def extract_metadata(self, html_content: Union[str, Path]) -> Dict[str, Any]:
        """
        Extract metadata from HTML.

        Args:
            html_content: HTML content or file path

        Returns:
            dict: Extracted metadata
        """
        result = self.parse(
            html_content,
            extract_links=False,
            extract_images=False,
            extract_forms=False,
            extract_tables=False,
            clean_text=False,
        )
        return result.metadata

    def extract_text(self, html_content: Union[str, Path], clean: bool = True) -> str:
        """
        Extract text from HTML.

        Args:
            html_content: HTML content or file path
            clean: Whether to clean extracted text

        Returns:
            str: Extracted text
        """
        result = self.parse(
            html_content,
            extract_links=False,
            extract_images=False,
            extract_forms=False,
            extract_tables=False,
            clean_text=clean,
        )
        return result.text

    def extract_links(
        self, html_content: Union[str, Path], base_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract links from HTML.

        Args:
            html_content: HTML content or file path
            base_url: Base URL for resolving relative links

        Returns:
            list: Extracted links
        """
        result = self.parse(
            html_content,
            base_url=base_url,
            extract_images=False,
            extract_forms=False,
            extract_tables=False,
        )
        return result.links

    def _extract_metadata(self, soup: BeautifulSoup) -> HTMLMetadata:
        """Extract metadata from HTML."""
        metadata = HTMLMetadata()

        # Extract title
        title_tag = soup.find("title")
        if title_tag:
            metadata.title = title_tag.get_text().strip()

        # Extract meta tags
        for meta_tag in soup.find_all("meta"):
            name = meta_tag.get("name") or meta_tag.get("property", "")
            content = meta_tag.get("content", "")

            if name.lower() == "description":
                metadata.description = content
            elif name.lower() == "keywords":
                metadata.keywords = content
            elif name.lower() == "author":
                metadata.author = content
            elif name == "og:title":
                metadata.og_title = content
            elif name == "og:description":
                metadata.og_description = content
            elif name == "og:image":
                metadata.og_image = content
            elif name == "og:url":
                metadata.og_url = content
            elif name == "twitter:card":
                metadata.twitter_card = content

        # Extract canonical URL
        canonical = soup.find("link", rel="canonical")
        if canonical:
            metadata.canonical_url = canonical.get("href")

        return metadata

    def _extract_clean_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text from HTML."""
        # Remove script and style elements
        for element in soup(["script", "style", "noscript"]):
            element.decompose()

        # Get text
        text = soup.get_text()

        # Clean whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)

        return text

    def _extract_links(
        self, soup: BeautifulSoup, base_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract links from HTML."""
        links = []

        for link_tag in soup.find_all("a", href=True):
            href = link_tag["href"]

            # Resolve relative URLs
            if base_url:
                url = urljoin(base_url, href)
            else:
                url = href

            link_info = {
                "url": url,
                "text": link_tag.get_text().strip(),
                "title": link_tag.get("title"),
                "rel": link_tag.get("rel"),
            }
            links.append(link_info)

        return links

    def _extract_images(
        self, soup: BeautifulSoup, base_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract images from HTML."""
        images = []

        for img_tag in soup.find_all("img"):
            src = img_tag.get("src")
            if src:
                # Resolve relative URLs
                if base_url:
                    url = urljoin(base_url, src)
                else:
                    url = src

                img_info = {
                    "url": url,
                    "alt": img_tag.get("alt", ""),
                    "title": img_tag.get("title"),
                    "width": img_tag.get("width"),
                    "height": img_tag.get("height"),
                }
                images.append(img_info)

        return images

    def _extract_forms(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract forms from HTML."""
        forms = []

        for form_tag in soup.find_all("form"):
            form_info = {
                "action": form_tag.get("action", ""),
                "method": form_tag.get("method", "get").lower(),
                "fields": [],
            }

            # Extract form fields
            for input_tag in form_tag.find_all(["input", "textarea", "select"]):
                field_info = {
                    "name": input_tag.get("name"),
                    "type": input_tag.get("type") or input_tag.name,
                    "value": input_tag.get("value", ""),
                    "required": input_tag.has_attr("required"),
                }
                form_info["fields"].append(field_info)

            forms.append(form_info)

        return forms

    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract tables from HTML."""
        tables = []

        for table_tag in soup.find_all("table"):
            table_data = {"headers": [], "rows": []}

            # Extract headers
            thead = table_tag.find("thead")
            if thead:
                for th in thead.find_all(["th", "td"]):
                    table_data["headers"].append(th.get_text().strip())

            # Extract rows
            tbody = table_tag.find("tbody") or table_tag
            for row in tbody.find_all("tr"):
                cells = []
                for cell in row.find_all(["td", "th"]):
                    cells.append(cell.get_text().strip())
                if cells:
                    table_data["rows"].append(cells)

            tables.append(table_data)

        return tables

    def _extract_structure(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract document structure."""
        structure = {"headings": [], "sections": []}

        # Extract headings
        for level in range(1, 7):
            for heading in soup.find_all(f"h{level}"):
                structure["headings"].append(
                    {
                        "level": level,
                        "text": heading.get_text().strip(),
                        "id": heading.get("id"),
                    }
                )

        return structure
