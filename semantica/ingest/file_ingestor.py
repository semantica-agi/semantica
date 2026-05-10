"""
File Ingestion Module

This module provides comprehensive file ingestion capabilities from local filesystems
and cloud storage providers, with automatic file type detection and validation.

Key Features:
    - Local file system scanning (recursive and filtered)
    - Cloud storage integration (AWS S3, Google Cloud Storage, Azure Blob)
    - Automatic file type detection (extension, MIME type, magic numbers)
    - Batch processing with progress tracking
    - File size validation and limits
    - Support for all common document, image, audio, and video formats

Example Usage:
    >>> from semantica.ingest import FileIngestor
    >>> ingestor = FileIngestor()
    >>> files = ingestor.ingest_directory("./documents", recursive=True)
    >>> file = ingestor.ingest_file("document.pdf", read_content=True)

Author: Semantica Contributors
License: MIT
"""

import mimetypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..utils.constants import (
    FILE_SIZE_LIMITS,
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_DOCUMENT_FORMATS,
    SUPPORTED_IMAGE_FORMATS,
    SUPPORTED_VIDEO_FORMATS,
)
from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


@dataclass
class FileObject:
    """File object representation."""

    path: str
    name: str
    size: int
    file_type: str
    mime_type: Optional[str] = None
    content: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)

    @property
    def text(self) -> str:
        """
        Get the file content as text.

        Returns:
            str: Decoded file content or empty string if no content
        """
        if self.content is None:
            return ""

        if isinstance(self.content, str):
            return self.content

        try:
            # Try to decode as UTF-8
            return self.content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                # Fallback to latin-1
                return self.content.decode("latin-1")
            except Exception:
                return ""


class FileTypeDetector:
    """
    File type detection and validation.

    This class identifies file types using multiple detection methods:
    1. File extension analysis
    2. MIME type detection
    3. Magic number (file signature) analysis

    It supports a wide range of document, image, audio, and video formats.
    """

    def __init__(self):
        """
        Initialize file type detector.

        Sets up the detector with all supported file formats and initializes
        the MIME types database for accurate type detection.
        """
        self.logger = get_logger("file_type_detector")

        # Combine all supported formats into a single list
        self.supported_formats = (
            SUPPORTED_DOCUMENT_FORMATS
            + SUPPORTED_IMAGE_FORMATS
            + SUPPORTED_AUDIO_FORMATS
            + SUPPORTED_VIDEO_FORMATS
        )

        # Initialize Python's MIME types database
        mimetypes.init()

        self.logger.debug(
            "File type detector initialized with "
            f"{len(self.supported_formats)} supported formats"
        )

    def detect_type(
        self, file_path: Union[str, Path], content: Optional[bytes] = None
    ) -> str:
        """
        Detect file type using multiple detection methods.

        This method tries three detection strategies in order:
        1. File extension (fastest, most common)
        2. MIME type detection (if file exists)
        3. Magic number analysis (most reliable, requires content)

        Args:
            file_path: Path to file (can be string or Path object)
            content: Optional file content bytes for magic number detection

        Returns:
            str: Detected file type (extension without dot, e.g., "pdf", "jpg")
                 Returns "unknown" if type cannot be determined
        """
        file_path = Path(file_path)

        # Method 1: Check file extension (fastest method)
        extension = file_path.suffix.lstrip(".").lower()
        if extension:
            self.logger.debug(f"Detected file type by extension: {extension}")
            return extension

        # Method 2: Check MIME type (if file exists on filesystem)
        if file_path.exists():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type:
                # Convert MIME type to file extension
                ext = mimetypes.guess_extension(mime_type)
                if ext:
                    detected_type = ext.lstrip(".").lower()
                    self.logger.debug(
                        f"Detected file type by MIME type: {detected_type}"
                    )
                    return detected_type

        # Method 3: Check magic numbers (file signatures) if content provided
        # This is the most reliable method but requires reading file content
        if content:
            file_type = self._detect_by_magic_numbers(content)
            if file_type:
                self.logger.debug(f"Detected file type by magic numbers: {file_type}")
                return file_type

        # Could not determine file type
        self.logger.warning(f"Could not determine file type for: {file_path}")
        return "unknown"

    def _detect_by_magic_numbers(self, content: bytes) -> Optional[str]:
        """
        Detect file type by analyzing magic numbers (file signatures).

        Magic numbers are specific byte sequences at the beginning of files
        that uniquely identify the file format. This is the most reliable
        detection method but requires file content.

        Args:
            content: File content bytes (at least first few bytes)

        Returns:
            str: Detected file type or None if not recognized
        """
        # Need at least 4 bytes for most magic number checks
        if len(content) < 4:
            return None

        # Dictionary of magic numbers (file signatures) mapped to file types
        # Format: {magic_bytes: file_extension}
        magic_numbers = {
            b"\x25\x50\x44\x46": "pdf",  # PDF (binary)
            b"%PDF": "pdf",  # PDF (text header)
            b"\x50\x4b\x03\x04": "zip",  # ZIP, DOCX, XLSX, PPTX (Office Open XML)
            b"\x89\x50\x4e\x47": "png",  # PNG image
            b"\xff\xd8\xff": "jpg",  # JPEG image
            b"\x47\x49\x46\x38": "gif",  # GIF image
            b"PK\x03\x04": "zip",  # ZIP (alternative)
            b"PAR1": "parquet",  # Apache Parquet
        }

        # Check if content starts with any known magic number
        for magic_bytes, file_type in magic_numbers.items():
            if content.startswith(magic_bytes):
                return file_type

        # No matching magic number found
        return None

    def is_supported(self, file_type: str) -> bool:
        """
        Check if file type is supported.

        Args:
            file_type: File type to check

        Returns:
            bool: Whether type is supported
        """
        return file_type.lower() in self.supported_formats


class CloudStorageIngestor:
    """
    Cloud storage specific ingestion handler.

    Handles authentication, object listing, and downloading
    from various cloud storage providers.
    """

    def __init__(self, provider: str, **config):
        """
        Initialize cloud storage ingestor.

        Args:
            provider: Cloud provider name (s3, gcs, azure)
            **config: Provider-specific configuration
        """
        self.logger = get_logger("cloud_storage_ingestor")
        self.provider = provider.lower()
        self.config = config
        self._client = None

        # Initialize provider-specific client
        self._initialize_client()

    def _initialize_client(self):
        """Initialize cloud storage client based on provider."""
        if self.provider == "s3":
            import boto3

            self._client = boto3.client(
                "s3",
                aws_access_key_id=self.config.get("access_key_id"),
                aws_secret_access_key=self.config.get("secret_access_key"),
                region_name=self.config.get("region", "us-east-1"),
            )
        elif self.provider == "gcs":
            from google.cloud import storage

            self._client = storage.Client()
        elif self.provider == "azure":
            from azure.storage.blob import BlobServiceClient

            self._client = BlobServiceClient.from_connection_string(
                self.config.get("connection_string")
            )
        else:
            raise ValueError(f"Unsupported cloud provider: {self.provider}")

    def list_objects(
        self, bucket: str, prefix: str = "", **filters
    ) -> List[Dict[str, Any]]:
        """
        List objects in cloud storage.

        Args:
            bucket: Storage bucket name
            prefix: Object prefix filter
            **filters: Additional filters

        Returns:
            list: List of object metadata
        """
        try:
            objects = []

            if self.provider == "s3":
                paginator = self._client.get_paginator("list_objects_v2")
                pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

                for page in pages:
                    if "Contents" in page:
                        for obj in page["Contents"]:
                            objects.append(
                                {
                                    "key": obj["Key"],
                                    "size": obj["Size"],
                                    "last_modified": obj["LastModified"],
                                    "etag": obj["ETag"],
                                }
                            )
            elif self.provider == "gcs":
                bucket_obj = self._client.bucket(bucket)
                blobs = bucket_obj.list_blobs(prefix=prefix)

                for blob in blobs:
                    objects.append(
                        {
                            "key": blob.name,
                            "size": blob.size,
                            "last_modified": blob.updated,
                            "etag": blob.etag,
                        }
                    )
            elif self.provider == "azure":
                container_client = self._client.get_container_client(bucket)
                blobs = container_client.list_blobs(name_starts_with=prefix)

                for blob in blobs:
                    objects.append(
                        {
                            "key": blob.name,
                            "size": blob.size,
                            "last_modified": blob.last_modified,
                            "etag": blob.etag,
                        }
                    )

            # Apply additional filters
            if filters:
                objects = self._apply_filters(objects, filters)

            return objects

        except Exception as e:
            self.logger.error(f"Failed to list objects from {self.provider}: {e}")
            raise ProcessingError(f"Failed to list objects: {e}")

    def _apply_filters(
        self, objects: List[Dict[str, Any]], filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply filters to object list."""
        filtered = objects

        if "min_size" in filters:
            filtered = [obj for obj in filtered if obj["size"] >= filters["min_size"]]

        if "max_size" in filters:
            filtered = [obj for obj in filtered if obj["size"] <= filters["max_size"]]

        if "extensions" in filters:
            exts = filters["extensions"]
            filtered = [
                obj for obj in filtered if Path(obj["key"]).suffix.lstrip(".") in exts
            ]

        return filtered

    def download_object(self, bucket: str, key: str, **options) -> bytes:
        """
        Download object from cloud storage.

        Args:
            bucket: Storage bucket name
            key: Object key
            **options: Download options

        Returns:
            bytes: Object content
        """
        try:
            if self.provider == "s3":
                response = self._client.get_object(Bucket=bucket, Key=key)
                content = response["Body"].read()
            elif self.provider == "gcs":
                bucket_obj = self._client.bucket(bucket)
                blob = bucket_obj.blob(key)
                content = blob.download_as_bytes()
            elif self.provider == "azure":
                container_client = self._client.get_container_client(bucket)
                blob_client = container_client.get_blob_client(key)
                content = blob_client.download_blob().readall()
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            return content

        except Exception as e:
            self.logger.error(
                f"Failed to download object {key} from {self.provider}: {e}"
            )
            raise ProcessingError(f"Failed to download object: {e}")


class FileIngestor:
    """
    File system and cloud storage ingestion handler.

    This class provides comprehensive file ingestion capabilities from:
    - Local filesystem (files and directories)
    - Cloud storage providers (AWS S3, Google Cloud Storage, Azure Blob)

    Features:
    - Automatic file type detection
    - Recursive directory scanning
    - File size validation
    - Progress tracking callbacks
    - Batch processing with error handling

    Example Usage:
        >>> ingestor = FileIngestor()
        >>> files = ingestor.ingest_directory("./documents", recursive=True)
        >>> single_file = ingestor.ingest_file("report.pdf", read_content=True)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize file ingestor.

        Sets up the ingestor with configuration and initializes the file type
        detector. Cloud storage providers are initialized lazily when needed.

        Args:
            config: Ingestion configuration dictionary
            **kwargs: Additional configuration parameters (merged into config)
        """
        self.logger = get_logger("file_ingestor")

        # Merge configuration
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize file type detector for automatic format detection
        self.type_detector = FileTypeDetector()
        self.supported_formats = self.type_detector.supported_formats

        # Cloud storage providers (initialized on-demand for better performance)
        self._cloud_providers: Dict[str, CloudStorageIngestor] = {}

        # Progress tracking callback (can be set by user)
        self._progress_callback: Optional[callable] = None

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()

        self.logger.info("File ingestor initialized")

    def ingest(self, source: Union[str, Path], **options) -> List[FileObject]:
        """
        Alias for ingest_directory (for backward compatibility or convenience).

        Args:
            source: Path to directory or file
            **options: Additional options

        Returns:
            List[FileObject]: List of ingested file objects
        """
        path = Path(source)
        if path.is_dir():
            return self.ingest_directory(path, **options)
        elif path.is_file():
            return [self.ingest_file(path, **options)]
        else:
            raise ValidationError(f"Path not found: {path}")

    def ingest_directory(
        self, directory_path: Union[str, Path], recursive: bool = True, **filters
    ) -> List[FileObject]:
        """
        Ingest all files from a directory.

        Args:
            directory_path: Path to directory
            recursive: Whether to scan subdirectories
            **filters: File filtering criteria

        Returns:
            list: List of ingested file objects
        """
        directory_path = Path(directory_path)

        # Track directory ingestion
        tracking_id = self.progress_tracker.start_tracking(
            file=str(directory_path),
            module="ingest",
            submodule="FileIngestor",
            message=f"Directory: {directory_path.name}",
        )

        try:
            # Validate directory path
            if not directory_path.exists():
                raise ValidationError(f"Directory not found: {directory_path}")

            if not directory_path.is_dir():
                raise ValidationError(f"Path is not a directory: {directory_path}")

            # Scan directory for files
            files = self.scan_directory(directory_path, recursive=recursive, **filters)

            # Process each file
            file_objects = []
            total_files = len(files)

            self.progress_tracker.update_tracking(
                tracking_id, message=f"Processing {total_files} files"
            )

            for idx, file_info in enumerate(files, 1):
                try:
                    file_obj = self.ingest_file(file_info["path"], **file_info)
                    file_objects.append(file_obj)

                    # Track progress with ETA
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=idx,
                        total=total_files,
                        message=(
                            f"Processing file {idx}/{total_files}: "
                            f"{Path(file_info['path']).name}"
                        ),
                    )

                    # Track progress via callback if provided
                    if self._progress_callback:
                        self._progress_callback(idx, total_files, file_obj)

                    self.logger.debug(
                        f"Ingested file {idx}/{total_files}: {file_info['path']}"
                    )

                except Exception as e:
                    self.logger.error(f"Failed to ingest file {file_info['path']}: {e}")
                    if self.config.get("fail_fast", False):
                        raise ProcessingError(f"Failed to ingest file: {e}")

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Ingested {len(file_objects)} files",
            )
            return file_objects

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def ingest_file(self, file_path: Union[str, Path], **options) -> FileObject:
        """
        Ingest a single file from the filesystem.

        This method reads a file, detects its type, validates its size,
        and creates a FileObject with all relevant metadata.

        Args:
            file_path: Path to the file to ingest (string or Path object)
            **options: Processing options:
                - read_content: Whether to read file content (default: True)
                - Additional metadata to include in FileObject

        Returns:
            FileObject: Ingested file object with metadata and optional content

        Raises:
            ValidationError: If file doesn't exist, isn't a file, or exceeds size limits
            ProcessingError: If file cannot be read
        """
        file_path = Path(file_path)

        # Track file ingestion
        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="ingest",
            submodule="FileIngestor",
            message=f"File: {file_path.name}",
        )

        try:
            # Validate file exists
            if not file_path.exists():
                raise ValidationError(f"File not found: {file_path}")

            # Validate it's actually a file (not a directory)
            if not file_path.is_file():
                raise ValidationError(f"Path is not a file: {file_path}")

            # Check file size against limits
            file_size = file_path.stat().st_size
            max_size = FILE_SIZE_LIMITS.get(
                "MAX_DOCUMENT_SIZE", 104857600
            )  # 100MB default
            if file_size > max_size:
                raise ValidationError(
                    f"File size {file_size:,} bytes exceeds maximum {max_size:,} bytes "
                    f"({file_path.name})"
                )

            # Detect file type using multiple methods
            file_type = self.type_detector.detect_type(file_path)

            # Warn if file type is not in supported formats list
            if not self.type_detector.is_supported(file_type):
                self.logger.warning(
                    f"Unsupported file type '{file_type}' for file: {file_path}. "
                    "Processing may be limited."
                )

            # Read file content if requested (default: True)
            content = None
            read_content = options.get("read_content", True)
            if read_content:
                try:
                    with open(file_path, "rb") as file_handle:
                        content = file_handle.read()
                    self.logger.debug(
                        f"Read {len(content):,} bytes from {file_path.name}"
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to read file content from {file_path}: {e}"
                    )
                    raise ProcessingError(f"Failed to read file: {e}") from e

            # Detect MIME type for additional metadata
            mime_type, _ = mimetypes.guess_type(str(file_path))

            # Create and return FileObject with all metadata
            file_obj = FileObject(
                path=str(file_path.absolute()),
                name=file_path.name,
                size=file_size,
                file_type=file_type,
                mime_type=mime_type,
                content=content,
                metadata={
                    "extension": file_path.suffix,
                    "parent": str(file_path.parent),
                    "is_supported": self.type_detector.is_supported(file_type),
                    "read_content": read_content,
                    **options,  # Include any additional options as metadata
                },
            )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Ingested {file_path.name} ({file_type})",
            )
            self.logger.debug(
                f"Successfully ingested file: {file_path.name} ({file_type})"
            )
            return file_obj

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def ingest_cloud(
        self, provider: str, bucket: str, prefix: str = "", **config
    ) -> List[FileObject]:
        """
        Ingest files from cloud storage.

        Args:
            provider: Cloud provider (s3, gcs, azure)
            bucket: Storage bucket name
            prefix: Object prefix filter
            **config: Cloud provider configuration

        Returns:
            list: List of ingested file objects
        """
        # Initialize cloud client if not already done
        if provider not in self._cloud_providers:
            self._cloud_providers[provider] = CloudStorageIngestor(provider, **config)

        cloud_ingestor = self._cloud_providers[provider]

        # List objects in bucket
        objects = cloud_ingestor.list_objects(bucket, prefix=prefix)

        # Process each object
        file_objects = []

        for obj_info in objects:
            try:
                # Download object
                content = cloud_ingestor.download_object(bucket, obj_info["key"])

                # Detect file type
                file_type = self.type_detector._detect_by_magic_numbers(
                    content
                ) or self.type_detector.detect_type(obj_info["key"])

                # Create file object
                file_obj = FileObject(
                    path=obj_info["key"],
                    name=Path(obj_info["key"]).name,
                    size=obj_info["size"],
                    file_type=file_type,
                    content=content,
                    metadata={
                        "provider": provider,
                        "bucket": bucket,
                        "etag": obj_info.get("etag"),
                        "last_modified": str(obj_info.get("last_modified")),
                    },
                )

                file_objects.append(file_obj)

            except Exception as e:
                self.logger.error(f"Failed to ingest object {obj_info['key']}: {e}")
                if self.config.get("fail_fast", False):
                    raise ProcessingError(f"Failed to ingest object: {e}")

        return file_objects

    def scan_directory(
        self, directory_path: Union[str, Path], **filters
    ) -> List[Dict[str, Any]]:
        """
        Scan directory and return file information without processing.

        Args:
            directory_path: Path to directory
            **filters: File filtering criteria:
                - recursive: Whether to scan subdirectories (default: True)
                - extensions: List of allowed extensions
                - min_size: Minimum file size
                - max_size: Maximum file size
                - pattern: Filename pattern (glob)

        Returns:
            list: List of file metadata
        """
        directory_path = Path(directory_path)
        recursive = filters.pop("recursive", True)

        # Walk directory tree
        files = []

        if recursive:
            for file_path in directory_path.rglob("*"):
                if file_path.is_file():
                    files.append(self._get_file_info(file_path))
        else:
            for file_path in directory_path.iterdir():
                if file_path.is_file():
                    files.append(self._get_file_info(file_path))

        # Apply filters
        if filters:
            files = self._apply_file_filters(files, filters)

        return files

    def _get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get file information."""
        stat = file_path.stat()
        return {
            "path": str(file_path),
            "name": file_path.name,
            "size": stat.st_size,
            "extension": file_path.suffix.lstrip("."),
            "modified": stat.st_mtime,
        }

    def _apply_file_filters(
        self, files: List[Dict[str, Any]], filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply filters to file list."""
        filtered = files

        if "extensions" in filters:
            exts = [ext.lstrip(".") for ext in filters["extensions"]]
            filtered = [f for f in filtered if f["extension"] in exts]

        if "min_size" in filters:
            filtered = [f for f in filtered if f["size"] >= filters["min_size"]]

        if "max_size" in filters:
            filtered = [f for f in filtered if f["size"] <= filters["max_size"]]

        if "pattern" in filters:
            import fnmatch

            pattern = filters["pattern"]
            filtered = [f for f in filtered if fnmatch.fnmatch(f["name"], pattern)]

        return filtered

    def set_progress_callback(self, callback):
        """Set progress tracking callback."""
        self._progress_callback = callback
