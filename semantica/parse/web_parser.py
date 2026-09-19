"""
Web Content Parsing Module

This module handles parsing of web content and HTML documents, including JavaScript
rendering, content extraction, and web scraping support.

Key Features:
    - HTML content parsing and cleaning
    - XML document processing
    - Web scraping content extraction
    - JavaScript rendering support
    - Content structure analysis
    - Link and media extraction
    - BeautifulSoup integration

Main Classes:
    - WebParser: Main web content parser
    - HTMLContentParser: HTML-specific parser
    - JavaScriptRenderer: JavaScript rendering engine

Example Usage:
    >>> from semantica.parse import WebParser
    >>> parser = WebParser()
    >>> content = parser.parse_html("https://example.com")
    >>> text = parser.extract_text("https://example.com")
    >>> links = parser.extract_links("https://example.com")

Author: Semantica Contributors
License: MIT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except (ImportError, OSError):
    BeautifulSoup = None

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .html_parser import HTMLParser
from .xml_parser import XMLParser


class WebParser:
    """
    Web content parsing handler.

    • Parses HTML, XML, and web content
    • Extracts text, links, and media
    • Handles JavaScript-rendered content
    • Processes web scraping results
    • Cleans and normalizes web content
    • Supports various web formats
    """

    def __init__(self, config=None, **kwargs):
        """
        Initialize web parser.

        • Setup HTML and XML parsers
        • Configure content extraction
        • Initialize JavaScript renderer
        • Setup content cleaning tools
        • Configure link extraction
        """
        self.logger = get_logger("web_parser")
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize parsers
        self.html_parser = HTMLParser(**self.config.get("html", {}))
        self.xml_parser = XMLParser(**self.config.get("xml", {}))
        self.js_renderer = JavaScriptRenderer(**self.config.get("js", {}))

    def parse_web_content(
        self,
        content: Union[str, Path],
        content_type: str = "html",
        base_url: Optional[str] = None,
        **options,
    ) -> Dict[str, Any]:
        """
        Parse web content of various types.

        Args:
            content: Web content or file path
            content_type: Content type ("html", "xml")
            base_url: Base URL for resolving relative links
            **options: Parsing options

        Returns:
            dict: Parsed content data
        """
        if content_type == "html":
            return self.html_parser.parse(content, base_url=base_url, **options)
        elif content_type == "xml":
            return self.xml_parser.parse(content, **options)
        else:
            raise ValidationError(f"Unsupported content type: {content_type}")

    def extract_text(self, web_content: Union[str, Path], **options) -> str:
        """
        Extract clean text from web content.

        Args:
            web_content: Web content or file path
            **options: Extraction options

        Returns:
            str: Extracted text
        """
        content_type = options.get("content_type", "html")

        # Handle JavaScript rendering if requested
        if options.get("render_javascript", False):
            html_content = self.js_renderer.render_page(web_content, **options)
            return self.html_parser.extract_text(
                html_content, clean=options.get("clean", True)
            )
        else:
            return self.html_parser.extract_text(
                web_content, clean=options.get("clean", True)
            )

    def extract_links(
        self, web_content: Union[str, Path], base_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract links from web content.

        Args:
            web_content: Web content or file path
            base_url: Base URL for resolving relative links

        Returns:
            list: Extracted links
        """
        return self.html_parser.extract_links(web_content, base_url=base_url)

    def render_javascript(self, html_content: Union[str, Path], **options) -> str:
        """
        Render JavaScript content in HTML.

        Args:
            html_content: HTML content or file path
            **options: Rendering options

        Returns:
            str: Rendered HTML content
        """
        return self.js_renderer.render_page(html_content, **options)


class HTMLContentParser(HTMLParser):
    """
    HTML content parsing engine.

    • Parses HTML documents and fragments
    • Extracts structured content
    • Handles various HTML versions
    • Processes forms and interactive elements
    • Cleans and validates HTML content
    """

    def extract_structured_content(
        self, html_content: Union[str, Path], **options
    ) -> Dict[str, Any]:
        """
        Extract structured content from HTML.

        Args:
            html_content: HTML content or file path
            **options: Extraction options

        Returns:
            dict: Structured content
        """
        parsed = self.parse(html_content, **options)

        structure = {
            "headings": [],
            "paragraphs": [],
            "lists": [],
            "tables": parsed.get("tables", []),
            "forms": parsed.get("forms", []),
        }

        # Load HTML for structure extraction
        if BeautifulSoup is None:
            raise ProcessingError(
                "beautifulsoup4 is required for HTML structure extraction. "
                "Install it with: pip install 'semantica[documents]'"
            )

        if isinstance(html_content, Path) or (
            isinstance(html_content, str) and Path(html_content).exists()
        ):
            with open(html_content, "r", encoding="utf-8", errors="ignore") as f:
                html_string = f.read()
        else:
            html_string = html_content

        soup = BeautifulSoup(html_string, "html.parser")

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

        # Extract paragraphs
        for para in soup.find_all("p"):
            text = para.get_text().strip()
            if text:
                structure["paragraphs"].append(text)

        # Extract lists
        for list_elem in soup.find_all(["ul", "ol"]):
            items = []
            for item in list_elem.find_all("li"):
                items.append(item.get_text().strip())
            if items:
                structure["lists"].append({"type": list_elem.name, "items": items})

        return structure

    def clean_html(self, html_content: Union[str, Path], **options) -> str:
        """
        Clean and normalize HTML content.

        Args:
            html_content: HTML content or file path
            **options: Cleaning options

        Returns:
            str: Cleaned HTML
        """
        if isinstance(html_content, Path) or (
            isinstance(html_content, str) and Path(html_content).exists()
        ):
            with open(html_content, "r", encoding="utf-8", errors="ignore") as f:
                html_string = f.read()
        else:
            html_string = html_content

        if BeautifulSoup is None:
            raise ProcessingError(
                "beautifulsoup4 is required for HTML cleaning. "
                "Install it with: pip install 'semantica[documents]'"
            )

        soup = BeautifulSoup(html_string, "html.parser")

        # Remove scripts and styles
        if options.get("remove_scripts", True):
            for script in soup(["script", "style", "noscript"]):
                script.decompose()

        # Remove comments
        if options.get("remove_comments", True):
            from bs4 import Comment

            comments = soup.find_all(string=lambda text: isinstance(text, Comment))
            for comment in comments:
                comment.extract()

        # Normalize whitespace
        if options.get("normalize_whitespace", True):
            for elem in soup.find_all(string=True):
                if elem.parent.name not in ["pre", "code"]:
                    elem.replace_with(" ".join(elem.split()))

        return str(soup)


class JavaScriptRenderer:
    """
    JavaScript rendering engine.

    • Executes JavaScript in web content
    • Renders dynamic content
    • Handles AJAX and API calls
    • Manages browser automation
    • Extracts rendered content
    """

    def __init__(self, **config):
        """
        Initialize JavaScript renderer.

        • Setup browser automation tools
        • Configure JavaScript execution
        • Initialize content extraction
        • Setup error handling
        """
        self.logger = get_logger("js_renderer")
        self.config = config
        self.use_selenium = config.get("use_selenium", False)

        # Initialize Selenium if requested
        if self.use_selenium:
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options

                self.driver_options = Options()
                self.driver_options.add_argument("--headless")
                self.driver_options.add_argument("--no-sandbox")
                self.driver_options.add_argument("--disable-dev-shm-usage")

                self.driver = None  # Initialize on first use
                self.logger.info("Selenium WebDriver configured")
            except (ImportError, OSError):
                self.logger.warning(
                    "Selenium not available, JavaScript rendering disabled"
                )
                self.use_selenium = False

    def render_page(self, html_content: Union[str, Path], **options) -> str:
        """
        Render HTML page with JavaScript.

        Args:
            html_content: HTML content or file path
            **options: Rendering options:
                - wait_time: Time to wait for page load (default: 5)
                - wait_for_selector: CSS selector to wait for

        Returns:
            str: Rendered HTML content
        """
        if not self.use_selenium:
            self.logger.warning(
                "JavaScript rendering not available (Selenium not configured)"
            )
            # Return original content if JavaScript rendering is not available
            if isinstance(html_content, Path) or (
                isinstance(html_content, str) and Path(html_content).exists()
            ):
                with open(html_content, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            return html_content

        try:
            # Initialize driver if needed
            if self.driver is None:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options

                self.driver = webdriver.Chrome(options=self.driver_options)

            # Load HTML content
            if isinstance(html_content, Path) or (
                isinstance(html_content, str) and Path(html_content).exists()
            ):
                file_path = Path(html_content)
                url = f"file://{file_path.absolute()}"
            else:
                # Create temporary HTML file
                import tempfile

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".html", delete=False
                ) as f:
                    f.write(html_content)
                    url = f"file://{f.name}"

            # Load page
            self.driver.get(url)

            # Wait for page load
            wait_time = options.get("wait_time", 5)
            self.wait_for_content(timeout=wait_time)

            # Wait for specific selector if requested
            if options.get("wait_for_selector"):
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.support.ui import WebDriverWait

                WebDriverWait(self.driver, wait_time).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, options["wait_for_selector"])
                    )
                )

            # Get rendered HTML
            rendered_html = self.driver.page_source

            return rendered_html

        except Exception as e:
            self.logger.error(f"Failed to render JavaScript: {e}")
            raise ProcessingError(f"Failed to render JavaScript: {e}")

    def execute_script(self, script: str, **context: Any) -> Any:
        """
        Execute JavaScript code.

        Args:
            script: JavaScript code to execute
            **context: Execution context

        Returns:
            Result of JavaScript execution
        """
        if not self.use_selenium or self.driver is None:
            raise ProcessingError("JavaScript execution requires Selenium WebDriver")

        try:
            return self.driver.execute_script(script)
        except Exception as e:
            self.logger.error(f"Failed to execute script: {e}")
            raise ProcessingError(f"Failed to execute script: {e}")

    def wait_for_content(
        self, condition: Optional[str] = None, timeout: int = 30
    ) -> bool:
        """
        Wait for specific content to load.

        Args:
            condition: Condition to wait for
            timeout: Timeout in seconds

        Returns:
            bool: True if condition met
        """
        if not self.use_selenium or self.driver is None:
            return False

        try:
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import WebDriverWait

            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState")
                == "complete"
            )
            return True
        except Exception as e:
            self.logger.warning(f"Wait timeout: {e}")
            return False

    def __del__(self):
        """Cleanup WebDriver on deletion."""
        if hasattr(self, "driver") and self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
