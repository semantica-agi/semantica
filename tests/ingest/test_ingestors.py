import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from semantica.ingest.file_ingestor import FileIngestor, FileTypeDetector, FileObject
from semantica.ingest.web_ingestor import WebIngestor, WebContent
from semantica.ingest.feed_ingestor import FeedIngestor, FeedData
from semantica.ingest.stream_ingestor import StreamIngestor
from semantica.ingest import ingest

class TestFileIngestor:
    def test_file_type_detector(self):
        detector = FileTypeDetector()
        
        # Test known extension
        assert detector.detect_type("test.txt") == "txt"
        assert detector.detect_type("test.pdf") == "pdf"
        assert detector.detect_type("test.jpg") == "jpg"
        
        # Test unknown extension with content
        # Note: python-magic might not be installed or behave differently on Windows
        # so we rely on what we can easily test.
        
    def test_ingest_file(self):
        ingestor = FileIngestor()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w") as tmp:
            tmp.write("Hello World")
            tmp_path = tmp.name
            
        try:
            result = ingestor.ingest_file(tmp_path, read_content=True)
            assert isinstance(result, FileObject)
            assert result.path == tmp_path
            assert result.file_type == "txt"
            assert result.mime_type == "text/plain"
            assert result.content == b"Hello World"
        finally:
            os.remove(tmp_path)

    def test_ingest_directory(self):
        ingestor = FileIngestor()
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create some files
            with open(os.path.join(tmp_dir, "f1.txt"), "w") as f: f.write("content1")
            with open(os.path.join(tmp_dir, "f2.md"), "w") as f: f.write("content2")
            os.makedirs(os.path.join(tmp_dir, "subdir"))
            with open(os.path.join(tmp_dir, "subdir", "f3.log"), "w") as f: f.write("content3")
            
            # Non-recursive
            results = ingestor.ingest_directory(tmp_dir, recursive=False)
            assert len(results) == 2
            
            # Recursive
            results = ingestor.ingest_directory(tmp_dir, recursive=True)
            assert len(results) == 3

class TestWebIngestor:
    def test_ingest_url(self):
        # Patch Session to return a mock session
        with patch("requests.Session") as MockSession:
            mock_session_instance = MockSession.return_value
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><head><title>Test Page</title></head><body><p>Test content</p></body></html>"
            mock_response.content = b"<html>...</html>"
            mock_session_instance.get.return_value = mock_response

            # Also patch RobotsChecker to avoid real network calls
            with patch("semantica.ingest.web_ingestor.RobotsChecker.can_fetch", return_value=True):
                ingestor = WebIngestor()
                result = ingestor.ingest_url("http://example.com")
        
                assert isinstance(result, WebContent)
                assert result.url == "http://example.com"
                assert result.title == "Test Page"
                assert "Test content" in result.text

class TestFeedIngestor:
    @patch("semantica.ingest.feed_ingestor.request_with_ssrf_guard")
    def test_ingest_feed(self, mock_request):
        ingestor = FeedIngestor()
        
        rss_content = """
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>http://example.com/feed</link>
            <description>Test Description</description>
            <item>
                <title>Test Item</title>
                <link>http://example.com/item1</link>
                <description>Item Description</description>
            </item>
        </channel>
        </rss>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = rss_content
        mock_response.content = rss_content.encode('utf-8')
        mock_request.return_value = mock_response
        
        result = ingestor.ingest_feed("http://example.com/feed.xml")
        
        assert isinstance(result, FeedData)
        assert result.title == "Test Feed"
        assert len(result.items) == 1
        assert result.items[0].title == "Test Item"

class TestUnifiedIngest:
    def test_ingest_file_dispatch(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w") as tmp:
            tmp.write("Unified Test")
            tmp_path = tmp.name
            
        try:
            # Should detect as file
            result = ingest(tmp_path)
            assert isinstance(result, dict)
            assert "files" in result
            assert isinstance(result["files"], FileObject)
            
            # Explicit type
            result = ingest(tmp_path, source_type="file")
            assert isinstance(result, dict)
            assert "files" in result
            assert isinstance(result["files"], FileObject)
        finally:
            os.remove(tmp_path)

    def test_ingest_web_dispatch(self):
        # Patch Session to return a mock session
        with patch("requests.Session") as MockSession:
            mock_session_instance = MockSession.return_value
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><title>Web</title></html>"
            mock_session_instance.get.return_value = mock_response

            # Also patch RobotsChecker to avoid real network calls
            with patch("semantica.ingest.web_ingestor.RobotsChecker.can_fetch", return_value=True):
                # Should detect as web
                result = ingest("http://example.com")
                assert isinstance(result, dict)
                assert "content" in result
                assert isinstance(result["content"], WebContent)
