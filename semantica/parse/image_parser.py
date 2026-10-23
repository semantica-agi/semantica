"""
Image Parser Module

This module handles image parsing using Tesseract OCR and PIL for text extraction
and image analysis, including metadata extraction and OCR processing.

Key Features:
    - Image metadata extraction (EXIF, format, size)
    - OCR text extraction using Tesseract
    - Image format support (PNG, JPEG, WebP, BMP by default; TIFF and GIF
      opt-in via the allowed_formats config)
    - File size and pixel count limits on untrusted input
    - Image analysis and properties
    - Optional Tesseract OCR integration
    - PIL/Pillow integration

Main Classes:
    - ImageParser: Image parser for OCR and metadata extraction
    - ImageMetadata: Dataclass for image metadata representation
    - OCRResult: Dataclass for OCR result representation

Example Usage:
    >>> from semantica.parse import ImageParser
    >>> parser = ImageParser()
    >>> metadata = parser.extract_metadata("image.jpg")
    >>> ocr_result = parser.extract_text("image.jpg")
    >>> text = ocr_result.text

Author: Semantica Contributors
License: MIT
"""

import io
import os
import stat
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import ExifTags, Image, UnidentifiedImageError
from PIL.Image import Image as PILImage

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker

from ..utils.helpers import safe_import

pytesseract, TESSERACT_AVAILABLE = safe_import("pytesseract")

# Pillow formats opened by default. The TIFF and GIF decoders carry open
# pillow 12.3.0 advisories that can't be fixed until docling allows pillow 13
# (#2067), so callers that need them opt in through `allowed_formats`.
DEFAULT_ALLOWED_FORMATS = ("PNG", "JPEG", "WEBP", "BMP")

# Never opened, even when requested: Pillow renders EPS by running
# Ghostscript on the file.
BLOCKED_FORMATS = frozenset({"EPS"})

# Common names that aren't Pillow open-plugin names. Multi-picture JPEGs (MPO)
# are opened by the JPEG plugin.
FORMAT_ALIASES = {"JPG": "JPEG", "TIF": "TIFF", "MPO": "JPEG"}

DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024  # bytes

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Most chunks accepted between a PNG's IHDR and its image data. Real files
# have a few dozen; libpng stops storing ancillary chunks after 1000.
MAX_PNG_HEADER_CHUNKS = 1000

# Image modes Pillow's PNG encoder can write. 32-bit "I" is not one of them:
# Pillow 13 no longer clips it to 16 bits on save, so it is converted first.
PNG_MODES = frozenset({"1", "L", "LA", "I;16", "I;16B", "P", "RGB", "RGBA"})

# Pillow's own default for Image.MAX_IMAGE_PIXELS, used when an application
# has set that to None to disable Pillow's check.
DEFAULT_MAX_PIXELS = 89_478_485


def _webp_canvas_size(data: bytes) -> Optional[tuple]:
    """
    Read the canvas size from a WebP header without decoding.

    Pillow builds the libwebp decoder, which allocates the full canvas,
    before it checks the image size, so a tiny WebP can claim a huge canvas.

    Args:
        data: File contents

    Returns:
        tuple: (width, height), or None if the header can't be read
    """
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        # Extended format: 24-bit canvas width - 1 and height - 1.
        return (
            1 + int.from_bytes(data[24:27], "little"),
            1 + int.from_bytes(data[27:30], "little"),
        )
    if chunk == b"VP8 ":
        # Lossy: frame tag, start code, then 14-bit width and height.
        if data[23:26] != b"\x9d\x01\x2a":
            return None
        return (
            int.from_bytes(data[26:28], "little") & 0x3FFF,
            int.from_bytes(data[28:30], "little") & 0x3FFF,
        )
    if chunk == b"VP8L":
        # Lossless: signature byte, then 14-bit width - 1 and height - 1.
        if data[20] != 0x2F:
            return None
        bits = int.from_bytes(data[21:25], "little")
        return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    return None


def _png_canvas_size(data: bytes) -> Optional[tuple]:
    """
    Read the canvas size from a PNG header without decoding.

    For an APNG whose first frame disposes to the background, Pillow before
    13.0 allocates the full canvas inside Image.open, before it checks the
    image size (GHSA-5xm2-6676-qcp9), so a tiny PNG can claim a huge canvas.

    Args:
        data: File contents

    Returns:
        tuple: (width, height), or None if the header can't be read, there
            is more than one IHDR chunk, or there are more than
            MAX_PNG_HEADER_CHUNKS chunks before the image data
    """
    # IHDR must be the first chunk: length, type, then big-endian width and
    # height.
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        return None

    # Image.open reads chunks up to the image data and takes the size from
    # the last IHDR, so a second one could claim a bigger canvas than the
    # first. The PNG spec allows only one. The walk is bounded, so a file of
    # millions of empty chunks can't stall it.
    pos = 20 + int.from_bytes(data[8:12], "big")
    for _ in range(MAX_PNG_HEADER_CHUNKS + 1):
        if pos + 8 > len(data):
            break
        length, chunk = struct.unpack_from(">I4s", data, pos)
        if chunk == b"IHDR":
            return None
        if chunk in (b"IDAT", b"fdAT", b"IEND"):
            break
        pos += 12 + length
    else:
        return None

    return (
        int.from_bytes(data[16:20], "big"),
        int.from_bytes(data[20:24], "big"),
    )


def _ocr_copy(img: PILImage) -> PILImage:
    """
    Make the RGB copy that is handed to tesseract.

    A plain convert("RGB") loses text in two common cases: it clips 16- and
    32-bit grayscale to white instead of scaling it, and it drops alpha, so
    dark text on a transparent dark background turns solid black.

    Args:
        img: Opened image

    Returns:
        PILImage: An RGB copy with no format set
    """
    if img.mode == "I" or img.mode.startswith("I;16"):
        img = img.point(lambda value: value / 256).convert("L")

    has_alpha = "A" in img.getbands()
    if has_alpha or (img.mode == "P" and "transparency" in img.info):
        # Flatten onto white, as pytesseract does for images with alpha.
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, (0, 0), rgba.getchannel("A"))
        return background

    return img.convert("RGB")


@dataclass
class ImageMetadata:
    """Image metadata representation."""

    format: Optional[str] = None
    mode: Optional[str] = None
    size: tuple = (0, 0)
    width: int = 0
    height: int = 0
    exif: Dict[str, Any] = field(default_factory=dict)
    info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OCRResult:
    """OCR result representation."""

    text: str
    confidence: float = 0.0
    language: str = "eng"
    boxes: List[Dict[str, Any]] = field(default_factory=list)


class ImageParser:
    """Image parser for OCR and metadata extraction."""

    def __init__(self, **config):
        """
        Initialize image parser.

        Args:
            **config: Parser configuration:
                - tesseract_path: Path to the tesseract binary
                - allowed_formats: Pillow format names to accept. Replaces
                  the default list (PNG, JPEG, WEBP, BMP), so include every
                  format you need. Adding "TIFF" or "GIF" re-exposes their
                  open advisories (#2067); "EPS" is always refused. "JPEG"
                  also accepts multi-picture JPEGs (MPO).
                - max_file_size: Largest file accepted, in bytes
                  (default: 50 MB; None for no limit)
                - max_pixels: Largest width * height accepted
                  (default: PIL.Image.MAX_IMAGE_PIXELS, or 89,478,485 if
                  that is None). Pillow refuses anything over twice
                  MAX_IMAGE_PIXELS on its own, so it can't be raised past
                  that cap, and between 1x and 2x Pillow still emits its
                  DecompressionBombWarning. Lower it on memory-constrained
                  hosts: OCR and preprocessing decode the full image, and a
                  WebP at the default limit can take about 2 GB.
        """
        self.logger = get_logger("image_parser")
        self.config = config
        self.progress_tracker = get_progress_tracker()
        self.tesseract_path = config.get("tesseract_path")
        if self.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

        self.allowed_formats = self._validate_formats(
            config.get("allowed_formats", DEFAULT_ALLOWED_FORMATS)
        )
        self.max_file_size = config.get("max_file_size", DEFAULT_MAX_FILE_SIZE)
        if self.max_file_size is not None and (
            not isinstance(self.max_file_size, int)
            or isinstance(self.max_file_size, bool)
            or self.max_file_size < 1
        ):
            raise ValidationError("max_file_size must be a positive int or None")
        self.max_pixels = self._validate_max_pixels(
            config.get("max_pixels", Image.MAX_IMAGE_PIXELS or DEFAULT_MAX_PIXELS)
        )

    @staticmethod
    def _validate_formats(formats: Any) -> tuple:
        """
        Normalise allowed_formats and check every name is a Pillow format.

        Pillow only looks a format name up when a file reaches it, and then
        raises a bare KeyError, so bad names are rejected here instead.

        Args:
            formats: The allowed_formats config value

        Returns:
            tuple: Upper-case Pillow format names
        """
        if isinstance(formats, str) or not isinstance(formats, (list, tuple, set)):
            raise ValidationError(
                "allowed_formats must be a list of format names, "
                f'such as ["PNG", "JPEG"], not {formats!r}'
            )
        if isinstance(formats, set):
            # A set has no order; sort so Pillow tries formats predictably.
            formats = sorted(formats, key=str)
        names = tuple(
            FORMAT_ALIASES.get(str(fmt).upper(), str(fmt).upper()) for fmt in formats
        )
        if not names:
            raise ValidationError("allowed_formats must name at least one format")

        blocked = BLOCKED_FORMATS.intersection(names)
        if blocked:
            raise ValidationError(
                f"Image formats {sorted(blocked)} cannot be enabled: Pillow "
                "decodes them by running external tools on the file."
            )

        # Registers every plugin Pillow has, so Image.OPEN is complete. A
        # format can be registered but still unusable (WEBP without
        # libwebp); such files are then refused as unidentified at open.
        Image.init()
        unknown = [name for name in names if name not in Image.OPEN]
        if unknown:
            raise ValidationError(
                f"Unknown or unavailable image formats {unknown}. "
                f"Available: {', '.join(sorted(Image.OPEN))}"
            )
        return names

    @staticmethod
    def _validate_max_pixels(max_pixels: Any) -> int:
        """
        Check max_pixels against Pillow's own hard limit.

        Args:
            max_pixels: The max_pixels config value

        Returns:
            int: The validated limit
        """
        if (
            not isinstance(max_pixels, int)
            or isinstance(max_pixels, bool)
            or max_pixels < 1
        ):
            raise ValidationError("max_pixels must be a positive int")
        if (
            Image.MAX_IMAGE_PIXELS is not None
            and max_pixels > 2 * Image.MAX_IMAGE_PIXELS
        ):
            raise ValidationError(
                f"max_pixels can't exceed {2 * Image.MAX_IMAGE_PIXELS}: Pillow "
                "refuses larger images itself (2 * PIL.Image.MAX_IMAGE_PIXELS)."
            )
        return max_pixels

    def _open_image(self, file_path: Path) -> PILImage:
        """
        Open an image with the format, file size and pixel limits applied.

        Every Pillow decode in this class goes through here, so untrusted
        files only ever reach the decoders for allowed formats.

        Args:
            file_path: Path to image file

        Returns:
            PILImage: The opened image. Pixel data isn't decoded yet, though
                some later reads load it (PNG EXIF, convert, verify).

        Raises:
            ValidationError: If the file is missing, not a regular file, too
                large, in a format that is not allowed, or has too many pixels
        """
        data = self._read_file(file_path)

        # Pillow's WebP plugin allocates the whole canvas before any size
        # check, so check the header first.
        is_webp = data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        if is_webp and "WEBP" in self.allowed_formats:
            size = _webp_canvas_size(data)
            if size is None:
                raise ValidationError(f"Unreadable WebP header: {file_path}")
            self._check_pixels(size, file_path)

        # Likewise Pillow's PNG plugin for some APNGs, before Pillow 13.0.
        # Every PNG is checked, since they all share the header.
        is_png = data[:8] == PNG_SIGNATURE
        if is_png and "PNG" in self.allowed_formats:
            size = _png_canvas_size(data)
            if size is None:
                raise ValidationError(f"Unreadable PNG header: {file_path}")
            self._check_pixels(size, file_path)

        try:
            img = Image.open(io.BytesIO(data), formats=self.allowed_formats)
        except UnidentifiedImageError:
            raise ValidationError(
                f"Not a supported image, or a damaged one: {file_path}. "
                f"Allowed formats: {', '.join(self.allowed_formats)}. To accept "
                "TIFF or GIF, add them to allowed_formats, e.g. ImageParser("
                'allowed_formats=["PNG", "JPEG", "WEBP", "BMP", "TIFF"]).'
            )
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
            # The warning only arrives as an exception when warnings are
            # errors (-W error). It isn't suppressed with catch_warnings(),
            # which changes process-wide state and isn't thread-safe.
            raise ValidationError(f"Image exceeds the pixel limit: {e}")

        try:
            self._check_pixels(img.size, file_path)
        except ValidationError:
            img.close()
            raise
        return img

    def _read_file(self, file_path: Path) -> bytes:
        """
        Read a file once, bounded by max_file_size.

        Decoding this snapshot instead of reopening the path means a file
        that changes after the checks can't get past them.

        Args:
            file_path: Path to image file

        Returns:
            bytes: File contents

        Raises:
            ValidationError: If the file is missing, not a regular file or
                over max_file_size
        """
        # O_NONBLOCK so opening a FIFO returns at once instead of waiting for
        # a writer; it has no effect on regular files.
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        try:
            fd = os.open(file_path, flags)
        except FileNotFoundError:
            raise ValidationError(f"Image file not found: {file_path}")
        except IsADirectoryError:
            raise ValidationError(f"Not a regular file: {file_path}")
        except PermissionError:
            # Windows reports a directory as EACCES rather than EISDIR.
            if os.path.isdir(file_path):
                raise ValidationError(f"Not a regular file: {file_path}")
            raise

        # Checked on the open descriptor, so the path can't be swapped for a
        # FIFO, device or directory after the check.
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValidationError(f"Not a regular file: {file_path}")
            f = os.fdopen(fd, "rb")
        except BaseException:
            os.close(fd)
            raise

        with f:
            if self.max_file_size is None:
                data = f.read()
            else:
                data = f.read(self.max_file_size + 1)

        if self.max_file_size is not None and len(data) > self.max_file_size:
            raise ValidationError(
                f"Image file is over the {self.max_file_size} byte limit: {file_path}"
            )
        return data

    def _check_pixels(self, size: tuple, file_path: Path) -> None:
        """
        Reject an image whose width * height is over max_pixels.

        Args:
            size: (width, height)
            file_path: Path to image file, for the error message
        """
        pixels = size[0] * size[1]
        if pixels > self.max_pixels:
            raise ValidationError(
                f"Image has {pixels} pixels, over the {self.max_pixels} pixel "
                f"limit: {file_path}"
            )

    def parse(self, file_path: Union[str, Path], **options) -> Dict[str, Any]:
        """
        Parse image file.

        Args:
            file_path: Path to image file
            **options: Parsing options:
                - extract_text: Whether to extract text using OCR (default: False)
                - ocr_language: OCR language code (default: "eng")
                - extract_metadata: Whether to extract metadata (default: True)

        Returns:
            dict: Parsed image data
        """
        file_path = Path(file_path)

        # Track image parsing
        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="parse",
            submodule="ImageParser",
            message=f"Image: {file_path.name}",
        )

        try:
            if not file_path.exists():
                raise ValidationError(f"Image file not found: {file_path}")

            # Validate image file
            try:
                with self._open_image(file_path) as img:
                    img.verify()
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(f"Invalid image file: {e}")

            try:
                with self._open_image(file_path) as img:
                    # Extract metadata
                    metadata = None
                    if options.get("extract_metadata", True):
                        self.progress_tracker.update_tracking(
                            tracking_id, message="Extracting metadata..."
                        )
                        metadata = self._extract_metadata(img)

                    # Extract text using OCR
                    ocr_result = None
                    if options.get("extract_text", False) and TESSERACT_AVAILABLE:
                        self.progress_tracker.update_tracking(
                            tracking_id, message="Running OCR..."
                        )
                        ocr_result = self.extract_text(
                            file_path, language=options.get("ocr_language", "eng")
                        )

                    self.progress_tracker.stop_tracking(
                        tracking_id,
                        status="completed",
                        message="Image parsed successfully",
                    )
                    return {
                        "metadata": metadata.__dict__ if metadata else None,
                        "ocr": ocr_result.__dict__ if ocr_result else None,
                        "text": ocr_result.text if ocr_result else None,
                    }

            # A rejected file stays a ValidationError, and extract_text's
            # ProcessingError isn't wrapped a second time.
            except (ValidationError, ProcessingError):
                raise
            except Exception as e:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message=str(e)
                )
                self.logger.error(f"Failed to parse image {file_path}: {e}")
                raise ProcessingError(f"Failed to parse image: {e}")

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def extract_text(
        self, file_path: Union[str, Path], language: str = "eng", **options
    ) -> OCRResult:
        """
        Extract text from image using OCR.

        Args:
            file_path: Path to image file
            language: OCR language code
            **options: OCR options

        Returns:
            OCRResult: Extracted text and confidence
        """
        if not TESSERACT_AVAILABLE:
            raise ProcessingError(
                "Tesseract OCR is not available. Install pytesseract and tesseract."
            )

        file_path = Path(file_path)

        try:
            # Given a path, tesseract decodes the raw file with its own image
            # libraries, outside the format allowlist. Hand it a converted
            # copy instead: with no format set, pytesseract writes it out as
            # PNG, which also covers MPO JPEGs (pytesseract rejects that
            # format) and keeps the TIFF and GIF encoders off the OCR path.
            with self._open_image(file_path) as img, _ocr_copy(img) as ocr_img:
                # Extract text
                text = pytesseract.image_to_string(ocr_img, lang=language)

                # Get detailed data with boxes
                data = pytesseract.image_to_data(
                    ocr_img, lang=language, output_type=pytesseract.Output.DICT
                )

            # Calculate average confidence
            confidences = [conf for conf in data["conf"] if conf != -1]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Extract boxes
            boxes = []
            n_boxes = len(data["level"])
            for i in range(n_boxes):
                if data["text"][i].strip():
                    boxes.append(
                        {
                            "text": data["text"][i],
                            "confidence": data["conf"][i],
                            "left": data["left"][i],
                            "top": data["top"][i],
                            "width": data["width"][i],
                            "height": data["height"][i],
                        }
                    )

            return OCRResult(
                text=text.strip(),
                confidence=avg_confidence / 100.0,
                language=language,
                boxes=boxes,
            )

        except ValidationError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to extract text from image {file_path}: {e}")
            raise ProcessingError(f"Failed to extract text from image: {e}")

    def extract_metadata(self, file_path: Union[str, Path]) -> ImageMetadata:
        """
        Extract metadata from image.

        Args:
            file_path: Path to image file

        Returns:
            ImageMetadata: Image metadata
        """
        file_path = Path(file_path)

        try:
            with self._open_image(file_path) as img:
                return self._extract_metadata(img)

        except ValidationError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to extract metadata from image {file_path}: {e}")
            raise ProcessingError(f"Failed to extract metadata from image: {e}")

    def _extract_metadata(self, img: PILImage) -> ImageMetadata:
        """
        Extract metadata from an already opened image.

        Args:
            img: Opened image

        Returns:
            ImageMetadata: Image metadata
        """
        # Extract EXIF data. For PNG, _getexif() loads the pixel data.
        exif_data = {}
        exif_dict = img._getexif() if hasattr(img, "_getexif") else None
        if exif_dict:
            for tag_id, value in exif_dict.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                exif_data[str(tag)] = str(value)

        return ImageMetadata(
            format=img.format,
            mode=img.mode,
            size=img.size,
            width=img.width,
            height=img.height,
            exif=exif_data,
            info=img.info or {},
        )

    def preprocess_image(self, file_path: Union[str, Path], **options) -> Path:
        """
        Preprocess image for better OCR results.

        Args:
            file_path: Path to image file
            **options: Preprocessing options:
                - resize: Resize factor
                - grayscale: Convert to grayscale
                - enhance_contrast: Enhance contrast

        Returns:
            Path: Path to the preprocessed image, always written as PNG
                (<stem>_preprocessed.png next to the input). Inputs that
                differ only by extension, such as a.png and a.jpg, share an
                output path, so the later call overwrites the earlier one.
        """
        file_path = Path(file_path)

        try:
            with self._open_image(file_path) as img:
                # Convert to grayscale if requested
                if options.get("grayscale", True):
                    img = img.convert("L")

                # Resize if requested, within the same pixel limit as input
                if options.get("resize"):
                    resize_factor = options["resize"]
                    new_size = (
                        int(img.width * resize_factor),
                        int(img.height * resize_factor),
                    )
                    self._check_pixels(new_size, file_path)
                    img = img.resize(new_size, Image.Resampling.LANCZOS)

                # Enhance contrast if requested
                if options.get("enhance_contrast", True):
                    from PIL import ImageEnhance

                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.5)

                # Save as PNG whatever the input's extension: choosing the
                # encoder from the extension would let a file named .tiff or
                # .gif reach the TIFF or GIF encoder.
                output_path = file_path.parent / f"{file_path.stem}_preprocessed.png"
                # PNG can't store modes such as CMYK (JPEG) or YCbCr.
                if img.mode == "I":
                    img = img.convert("I;16")
                elif img.mode not in PNG_MODES:
                    img = img.convert("RGB")
                img.save(output_path, format="PNG")

                return output_path

        except ValidationError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to preprocess image {file_path}: {e}")
            raise ProcessingError(f"Failed to preprocess image: {e}")
