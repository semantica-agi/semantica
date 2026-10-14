from unittest.mock import MagicMock, patch

import pytest
import requests

from semantica.ingest.web_ingestor import (
    ContentExtractor,
    ProcessingError,
    RateLimiter,
    RobotsChecker,
    SitemapCrawler,
    WebContent,
    WebIngestor,
)


# --- Fixtures ---
@pytest.fixture
def sample_html() -> str:
    """Return a simple HTML string."""

    return """<html>
            <head><title>T</title></head>
            <body><a href='/1'>1</a></body>
            </html>"""


# --- Sitemap Tests ---
def test_sitemap_index_recursion() -> None:
    """Test crawling a sitemap index that points to other sitemaps."""

    crawler = SitemapCrawler()

    index_xml = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
       <sitemap><loc>http://ex.com/s1.xml</loc></sitemap>
    </sitemapindex>
    """

    child_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
       <url><loc>http://ex.com/page1</loc></url>
    </urlset>
    """

    with patch(
        "semantica.ingest.web_ingestor.request_with_ssrf_guard"
    ) as mock_get:
        mock_get.side_effect = [
            MagicMock(status_code=200, content=index_xml.encode()),
            MagicMock(status_code=200, content=child_xml.encode()),
        ]
        urls = crawler.crawl_sitemap_index("http://ex.com/index.xml")

    assert "http://ex.com/page1" in urls


def test_sitemap_fallback_parsing() -> None:
    """Test sitemap parsing without namespaces."""

    crawler = SitemapCrawler()
    xml = "<urlset><url><loc>http://a.com</loc></url></urlset>"

    with patch(
        "semantica.ingest.web_ingestor.request_with_ssrf_guard",
        return_value=MagicMock(
            status_code=200,
            content=xml.encode(),
        ),
    ):
        urls = crawler.parse_sitemap("http://s.xml")

    assert any(url == "http://a.com" for url in urls)


def test_sitemap_invalid_xml() -> None:
    """Test parsing invalid XML raises ProcessingError."""

    crawler = SitemapCrawler()

    with patch(
        "semantica.ingest.web_ingestor.request_with_ssrf_guard",
        return_value=MagicMock(status_code=200, content=b"NOT XML"),
    ) as mock_request:
        with pytest.raises(ProcessingError):
            crawler.parse_sitemap("http://s.xml")

    mock_request.assert_called_once()


# --- Content Extraction Tests ---
def test_extract_links_schemes() -> None:
    """Ensure we ignore mailto and javascript links."""

    extractor = ContentExtractor()
    html = """
    <a href="http://good.com">Good</a>
    <a href="mailto:me@me.com">Mail</a>
    <a href="tel:123">Phone</a>
    <a href="javascript:void(0)">JS</a>
    """
    links = extractor.extract_links(html)

    assert len(links) == 1
    assert links[0] == "http://good.com"


def test_extract_metadata_empty() -> None:
    """Test extraction with missing meta tags."""

    extractor = ContentExtractor()
    html = "<html><body>No Head</body></html>"
    meta = extractor.extract_metadata(html, "http://u.com")

    assert meta.get("title") is None or meta.get("title") == ""
    assert meta.get("description") is None or meta.get("description") == ""


# --- WebIngestor Tests ---
@patch("semantica.ingest.web_ingestor.request_with_ssrf_guard")
def test_ingest_url_happy(mock_get: MagicMock, sample_html: str) -> None:
    """Test successful URL ingestion."""

    mock_get.return_value = MagicMock(status_code=200, text=sample_html)
    ingestor = WebIngestor(respect_robots=False)
    res = ingestor.ingest_url("http://site.com")

    assert res.title == "T"


@patch("semantica.ingest.web_ingestor.RobotFileParser")
def test_robots_blocking(mock_parser_cls: MagicMock) -> None:
    """Test that we actually block if robots says no."""

    mock_inst = mock_parser_cls.return_value
    mock_inst.can_fetch.return_value = False

    ingestor = WebIngestor(respect_robots=True)

    with pytest.raises(ProcessingError):
        ingestor.ingest_url("http://site.com/private")


def test_crawl_domain_visited_logic() -> None:
    """Test that we don't crawl the same page twice."""

    with patch.object(WebIngestor, "ingest_url") as mock_ingest:
        p1 = WebContent(url="http://a.com", links=["http://a.com"])
        mock_ingest.return_value = p1

        ingestor = WebIngestor(respect_robots=False)
        results = ingestor.crawl_domain("http://a.com", max_pages=10)

    assert len(results) == 1
    assert mock_ingest.call_count == 1


def test_rate_limiter() -> None:
    """Test that rate limiter actually sleeps."""

    limiter = RateLimiter(delay=0.1)

    with patch("time.sleep") as mock_sleep:
        # Need 4 values: [init_check, init_set, 2nd_check, 2nd_set]
        with patch("time.time", side_effect=[100.0, 100.0, 100.05, 100.2]):
            limiter.wait_if_needed()
            limiter.wait_if_needed()

    assert mock_sleep.called


def test_rate_limiter_no_delay() -> None:
    """Test that 0 delay does not sleep."""

    limiter = RateLimiter(delay=0.0)
    with patch("time.sleep") as mock_sleep:
        limiter.wait_if_needed()

    assert not mock_sleep.called


@patch("requests.Session.get")
def test_ingest_url_retry(mock_get: MagicMock) -> None:
    """Test that it retries on failure."""

    mock_get.side_effect = [
        requests.exceptions.ConnectionError("Fail 1"),
        requests.exceptions.ConnectionError("Fail 2"),
        MagicMock(status_code=200, text="<html></html>"),
    ]

    ingestor = WebIngestor(respect_robots=False)

    assert ingestor.session.adapters["https://"].max_retries.total == 3


def test_url_filters() -> None:
    """Test URL filtering logic."""

    ingestor = WebIngestor(respect_robots=False)
    urls = ["https://good.com/a", "https://bad.com/b", "https://good.com/skip"]

    f1 = ingestor._apply_url_filters(urls, {"domains": ["good.com"]})
    f2 = ingestor._apply_url_filters(urls, {"pattern": r"/a$"})
    f3 = ingestor._apply_url_filters(urls, {"exclude_pattern": "skip"})

    assert len(f1) == 2
    assert f2 == ["https://good.com/a"]
    assert "https://good.com/skip" not in f3


def test_extract_text_cleaning() -> None:
    """Test stripping scripts and styles from text."""

    extractor = ContentExtractor()
    html = """
    <html>
        <style>body { color: red; }</style>
        <script>alert('x');</script>
        <body>
            <h1>Real Text</h1>
        </body>
    </html>
    """
    text = extractor.extract_text(html)

    assert "Real Text" in text
    assert "alert" not in text
    assert "color: red" not in text


def test_robots_checker_cache() -> None:
    """Test that robots.txt is cached per domain."""

    with patch("semantica.ingest.web_ingestor.RobotFileParser") as mock_parser:
        mock_parser.return_value.can_fetch.return_value = True
        checker = RobotsChecker()

        # First call: Should trigger parser creation
        checker.can_fetch("http://example.com/a")

        # Second call: Should use cache (no new parser)
        checker.can_fetch("http://example.com/b")

        # Verify parser was initialized only once
        assert mock_parser.call_count == 1


def test_web_ingestor_crawl_sitemap_integration() -> None:
    """Test the high-level crawl_sitemap method in WebIngestor."""

    ingestor = WebIngestor(respect_robots=False)

    # 1. Mock the SitemapCrawler to return 2 URLs
    with patch(
        "semantica.ingest.web_ingestor.SitemapCrawler.parse_sitemap"
    ) as mock_parse:
        mock_parse.return_value = ["http://site.com/1", "http://site.com/2"]

        # 2. Mock ingest_url to successfully process those URLs
        with patch.object(ingestor, "ingest_url") as mock_ingest:
            mock_ingest.return_value = MagicMock(url="http://site.com/1")

            results = ingestor.crawl_sitemap("http://site.com/sitemap.xml")

            # Should have called ingest_url twice
            assert len(results) == 2
            assert mock_ingest.call_count == 2


def test_metadata_priority() -> None:
    """Test that OpenGraph tags take precedence over standard meta tags."""

    extractor = ContentExtractor()
    html = """
    <html>
    <head>
        <meta name="description" content="Standard Description">
        <meta property="og:description" content="OG Description">
        <meta name="author" content="Standard Author">
    </head>
    </html>
    """
    meta = extractor.extract_metadata(html, "http://site.com")

    assert meta["description"] == "Standard Description"
    assert meta["og"]["description"] == "OG Description"
    assert meta["author"] == "Standard Author"


def test_crawl_domain_max_depth() -> None:
    """Test that crawling respects max depth/pages."""

    ingestor = WebIngestor(respect_robots=False)

    # Create a chain of links: P1 -> P2 -> P3
    p1 = WebContent(url="http://a.com/1", links=["http://a.com/2"])
    p2 = WebContent(url="http://a.com/2", links=["http://a.com/3"])
    p3 = WebContent(url="http://a.com/3", links=[])

    with patch.object(ingestor, "ingest_url") as mock_ingest:
        mock_ingest.side_effect = [p1, p2, p3]

        # Limit to 2 pages
        results = ingestor.crawl_domain("http://a.com/1", max_pages=2)

        assert len(results) == 2
        # Should have stopped before P3
        assert "http://a.com/3" not in [r.url for r in results]


def test_crawl_sitemap_integration() -> None:
    """Test the full flow of crawling a sitemap and ingesting its URLs."""

    ingestor = WebIngestor(respect_robots=False)

    # 1. Mock the sitemap parser to return specific URLs
    with patch(
        "semantica.ingest.web_ingestor.SitemapCrawler.parse_sitemap"
    ) as mock_parse:
        mock_parse.return_value = ["http://site.com/1", "http://site.com/2"]

        # 2. Mock ingest_url to simulate successful extraction for each URL
        with patch.object(ingestor, "ingest_url") as mock_ingest:
            # Return dummy content for each call
            mock_ingest.side_effect = [
                WebContent(
                    url="http://site.com/1",
                    title="Page 1",
                    text="1",
                    html="",
                    metadata={},
                    links=[],
                ),
                WebContent(
                    url="http://site.com/2",
                    title="Page 2",
                    text="2",
                    html="",
                    metadata={},
                    links=[],
                ),
            ]

            results = ingestor.crawl_sitemap("http://site.com/sitemap.xml")

            # Verify the loop ran correctly
            assert len(results) == 2
            assert results[0].title == "Page 1"
            assert mock_ingest.call_count == 2


def test_crawl_domain_max_pages() -> None:
    """Test that the crawler stops exactly at max_pages."""
    ingestor = WebIngestor(respect_robots=False)

    # Create a chain: P1 -> P2 -> P3 -> P4
    p1 = WebContent(
        url="http://a.com/1",
        links=["http://a.com/2"],
        title="",
        text="",
        html="",
        metadata={},
    )
    p2 = WebContent(
        url="http://a.com/2",
        links=["http://a.com/3"],
        title="",
        text="",
        html="",
        metadata={},
    )
    p3 = WebContent(
        url="http://a.com/3",
        links=["http://a.com/4"],
        title="",
        text="",
        html="",
        metadata={},
    )

    with patch.object(ingestor, "ingest_url") as mock_ingest:
        mock_ingest.side_effect = [p1, p2, p3]

        # Set limit to 2 pages
        results = ingestor.crawl_domain("http://a.com/1", max_pages=2)

        assert len(results) == 2
        assert results[0].url == "http://a.com/1"
        assert results[1].url == "http://a.com/2"

        # Verify P3 was never ingested
        res = [c[0][0] for c in mock_ingest.call_args_list]
        assert "http://a.com/3" not in res


def test_metadata_opengraph_priority() -> None:
    """Test that OpenGraph tags are captured correctly."""
    extractor = ContentExtractor()
    # HTML with both standard meta and OG tags
    html = """
    <html>
    <head>
        <meta name="description" content="Basic Desc">
        <meta property="og:description" content="OG Desc">
        <meta property="og:title" content="OG Title">
        <meta property="og:image" content="http://img.jpg">
    </head>
    </html>
    """
    meta = extractor.extract_metadata(html, "http://site.com")

    # Check that OG data is structured correctly in the 'og' dict
    assert meta["og"]["description"] == "OG Desc"
    assert meta["og"]["title"] == "OG Title"
    assert meta["og"]["image"] == "http://img.jpg"
    # Basic description should still be available
    assert meta["description"] == "Basic Desc"
