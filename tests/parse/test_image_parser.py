"""
Tests for the untrusted-input limits in ImageParser (#2067).

Covers:
    - Default formats (PNG, JPEG, WEBP, BMP) open; TIFF and GIF are refused
      unless enabled through allowed_formats
    - EPS can never be enabled
    - File size and pixel count limits
    - Every entry point (parse, extract_metadata, preprocess_image,
      extract_text) applies the limits
    - The size limit applies to the bytes read; FIFOs and directories are
      refused without blocking
    - Unexpected open failures are logged and wrapped as ProcessingError
    - The OCR input keeps text in 16-bit and transparent images
    - Config validation, pixel limits (including WebP and PNG headers and
      Pillow's own bomb check) and error mapping
"""

import os
import struct
import tempfile
import threading
import unittest
import warnings
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from semantica.parse.image_parser import (
    MAX_PNG_HEADER_CHUNKS,
    ImageParser,
    _png_canvas_size,
    _webp_canvas_size,
)
from semantica.utils.exceptions import ProcessingError, ValidationError


class TestImageParserLimits(unittest.TestCase):
    def setUp(self):
        logger_patcher = patch("semantica.parse.image_parser.get_logger")
        tracker_patcher = patch("semantica.parse.image_parser.get_progress_tracker")
        logger_patcher.start()
        tracker_patcher.start()
        self.addCleanup(logger_patcher.stop)
        self.addCleanup(tracker_patcher.stop)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def _image(self, name, fmt, size=(8, 8)):
        path = self.dir / name
        Image.new("RGB", size, "white").save(path, format=fmt)
        return path

    def test_default_formats_parse(self):
        parser = ImageParser()
        for name, fmt in [
            ("a.png", "PNG"),
            ("a.jpg", "JPEG"),
            ("a.webp", "WEBP"),
            ("a.bmp", "BMP"),
        ]:
            with self.subTest(fmt=fmt):
                result = parser.parse(self._image(name, fmt))
                self.assertEqual(result["metadata"]["format"], fmt)

    def test_tiff_and_gif_refused_by_default(self):
        parser = ImageParser()
        for name, fmt in [("a.tiff", "TIFF"), ("a.gif", "GIF")]:
            with self.subTest(fmt=fmt):
                with self.assertRaises(ValidationError):
                    parser.parse(self._image(name, fmt))

    def test_tiff_and_gif_open_when_allowed(self):
        parser = ImageParser(allowed_formats=["png", "tiff", "gif"])
        for name, fmt in [("a.tiff", "TIFF"), ("a.gif", "GIF")]:
            with self.subTest(fmt=fmt):
                metadata = parser.extract_metadata(self._image(name, fmt))
                self.assertEqual(metadata.format, fmt)

    def test_extension_does_not_bypass_format_check(self):
        # A TIFF renamed to .png is still decoded as TIFF, so it's refused.
        path = self.dir / "disguised.png"
        Image.new("RGB", (8, 8)).save(path, format="TIFF")
        with self.assertRaises(ValidationError):
            ImageParser().parse(path)

    def test_eps_cannot_be_enabled(self):
        with self.assertRaises(ValidationError):
            ImageParser(allowed_formats=["PNG", "eps"])

    def test_file_size_limit(self):
        path = self._image("a.png", "PNG")
        parser = ImageParser(max_file_size=path.stat().st_size - 1)
        with self.assertRaises(ValidationError):
            parser.parse(path)

    def test_pixel_limit(self):
        path = self._image("a.png", "PNG", size=(20, 20))
        parser = ImageParser(max_pixels=399)
        with self.assertRaises(ValidationError):
            parser.extract_metadata(path)
        self.assertEqual(ImageParser(max_pixels=400).extract_metadata(path).width, 20)

    def test_missing_file(self):
        with self.assertRaises(ValidationError):
            ImageParser().extract_metadata(self.dir / "missing.png")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs os.mkfifo")
    def test_fifo_is_refused_without_blocking(self):
        fifo = self.dir / "pipe.png"
        os.mkfifo(fifo)
        errors = []

        def run():
            try:
                ImageParser().extract_metadata(fifo)
            except Exception as e:
                errors.append(e)

        # In a thread with a timeout, so a regression fails instead of
        # hanging the test run.
        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive(), "opening a FIFO blocked")
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValidationError)

    def test_unexpected_open_error_is_logged_and_wrapped(self):
        parser = ImageParser()
        path = self._image("a.png", "PNG")
        with patch.object(parser, "_open_image", side_effect=OSError("disk error")):
            with self.assertRaises(ProcessingError):
                parser.extract_metadata(path)
        parser.logger.error.assert_called_once()

    def test_rejected_input_is_not_wrapped(self):
        # ValidationError for a rejected file must reach the caller as is,
        # not as a ProcessingError.
        with self.assertRaises(ValidationError) as ctx:
            ImageParser().extract_metadata(self._image("a.gif", "GIF"))
        self.assertNotIsInstance(ctx.exception, ProcessingError)

    def test_preprocess_image_applies_limits(self):
        parser = ImageParser()
        with self.assertRaises(ValidationError):
            parser.preprocess_image(self._image("a.gif", "GIF"))
        output = parser.preprocess_image(self._image("a.png", "PNG"))
        self.assertTrue(output.exists())

    def test_preprocess_image_always_writes_png(self):
        # The output encoder must not follow the input's extension: a PNG
        # named .tiff would otherwise be written by the TIFF encoder.
        path = self.dir / "scan.tiff"
        Image.new("RGB", (8, 8)).save(path, format="PNG")
        output = ImageParser().preprocess_image(path)
        self.assertEqual(output.name, "scan_preprocessed.png")
        with Image.open(output) as out:
            self.assertEqual(out.format, "PNG")

    def test_preprocess_resize_is_limited(self):
        parser = ImageParser(max_pixels=1000)
        with self.assertRaises(ValidationError):
            parser.preprocess_image(self._image("a.png", "PNG"), resize=10)

    def test_preprocess_cmyk_without_grayscale(self):
        # PNG can't store CMYK, so a CMYK JPEG must be converted to RGB.
        path = self.dir / "cmyk.jpg"
        Image.new("CMYK", (8, 8), (0, 255, 255, 0)).save(path, format="JPEG")
        output = ImageParser().preprocess_image(path, grayscale=False)
        with Image.open(output) as out:
            self.assertEqual((out.format, out.mode), ("PNG", "RGB"))

    def test_preprocess_32bit_grayscale_without_grayscale(self):
        # Pillow 13 refuses to write 32-bit "I" images as PNG, so a 32-bit
        # grayscale TIFF must be converted to 16 bits first.
        path = self.dir / "depth.tiff"
        Image.new("I", (8, 8), 70000).save(path, format="TIFF")
        parser = ImageParser(allowed_formats=["TIFF"])
        output = parser.preprocess_image(
            path, grayscale=False, enhance_contrast=False
        )
        with Image.open(output) as out:
            self.assertEqual((out.format, out.mode), ("PNG", "I;16"))
            self.assertEqual(out.getpixel((0, 0)), 65535)

    def _fake_tesseract(self):
        fake = MagicMock()
        fake.image_to_string.return_value = "hello"
        fake.image_to_data.return_value = {
            "level": [1],
            "conf": [90],
            "text": ["hello"],
            "left": [0],
            "top": [0],
            "width": [8],
            "height": [8],
        }
        return fake

    def test_extract_text_passes_checked_image_to_tesseract(self):
        fake_tesseract = self._fake_tesseract()
        with (
            patch("semantica.parse.image_parser.TESSERACT_AVAILABLE", True),
            patch("semantica.parse.image_parser.pytesseract", fake_tesseract),
        ):
            parser = ImageParser()
            with self.assertRaises(ValidationError):
                parser.extract_text(self._image("a.gif", "GIF"))
            fake_tesseract.image_to_string.assert_not_called()

            result = parser.extract_text(self._image("a.png", "PNG"))

        self.assertEqual(result.text, "hello")
        # Tesseract gets a checked, converted image, never the path, so it
        # can't decode the raw file with its own image libraries.
        passed = fake_tesseract.image_to_string.call_args.args[0]
        self.assertIsInstance(passed, Image.Image)

    def test_extract_text_hands_tesseract_a_formatless_rgb_copy(self):
        # pytesseract re-saves an image in its own format and rejects MPO;
        # a converted copy has no format, so it is written as PNG.
        path = self.dir / "phone.jpg"
        first, second = Image.new("RGB", (8, 8)), Image.new("RGB", (8, 8))
        first.save(path, format="MPO", save_all=True, append_images=[second])
        with Image.open(path) as check:
            self.assertEqual(check.format, "MPO")

        fake_tesseract = self._fake_tesseract()
        with (
            patch("semantica.parse.image_parser.TESSERACT_AVAILABLE", True),
            patch("semantica.parse.image_parser.pytesseract", fake_tesseract),
        ):
            ImageParser().extract_text(path)

        passed = fake_tesseract.image_to_string.call_args.args[0]
        self.assertIsNone(passed.format)
        self.assertEqual(passed.mode, "RGB")

    def _ocr_input(self, path):
        """Run extract_text and return a copy of the image tesseract got."""
        captured = []
        fake_tesseract = self._fake_tesseract()
        fake_tesseract.image_to_string.side_effect = lambda img, **kwargs: (
            captured.append(img.copy()) or "hello"
        )
        with (
            patch("semantica.parse.image_parser.TESSERACT_AVAILABLE", True),
            patch("semantica.parse.image_parser.pytesseract", fake_tesseract),
        ):
            ImageParser().extract_text(path)
        return captured[0]

    def test_ocr_input_scales_16_bit_grayscale(self):
        # A plain convert("RGB") clips 16-bit values, turning the text and
        # the background both white.
        path = self.dir / "scan16.png"
        img = Image.new("I;16", (8, 8), 60000)
        img.putpixel((0, 0), 8000)
        img.save(path, format="PNG")

        ocr_input = self._ocr_input(path)
        self.assertEqual(ocr_input.mode, "RGB")
        self.assertEqual(ocr_input.getpixel((0, 0)), (31, 31, 31))
        self.assertEqual(ocr_input.getpixel((1, 1)), (234, 234, 234))

    def test_ocr_input_flattens_alpha_onto_white(self):
        # Black text on a transparent black background must stay readable,
        # not turn solid black.
        path = self.dir / "transparent.png"
        img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        img.putpixel((0, 0), (0, 0, 0, 255))
        img.save(path, format="PNG")

        ocr_input = self._ocr_input(path)
        self.assertEqual(ocr_input.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(ocr_input.getpixel((1, 1)), (255, 255, 255))

    def test_ocr_input_flattens_palette_transparency(self):
        path = self.dir / "palette.png"
        img = Image.new("P", (8, 8), 0)
        img.putpalette([0, 0, 0] * 256)
        img.putpixel((0, 0), 1)
        img.info["transparency"] = 0
        img.save(path, format="PNG", transparency=0)

        ocr_input = self._ocr_input(path)
        self.assertEqual(ocr_input.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(ocr_input.getpixel((1, 1)), (255, 255, 255))

    # --- Config validation ---

    def test_allowed_formats_validation(self):
        for bad in ["PNG", None, ["FOO"], [], ["PNG", "EPS"]]:
            with self.subTest(allowed_formats=bad):
                with self.assertRaises(ValidationError):
                    ImageParser(allowed_formats=bad)

    def test_allowed_formats_aliases(self):
        parser = ImageParser(allowed_formats=["png", "jpg", "tif", "mpo"])
        self.assertEqual(parser.allowed_formats, ("PNG", "JPEG", "TIFF", "JPEG"))
        metadata = parser.extract_metadata(self._image("a.tiff", "TIFF"))
        self.assertEqual(metadata.format, "TIFF")

    def test_allowed_formats_set_has_stable_order(self):
        parser = ImageParser(allowed_formats={"WEBP", "BMP", "PNG", "JPEG"})
        self.assertEqual(parser.allowed_formats, ("BMP", "JPEG", "PNG", "WEBP"))

    def test_max_pixels_validation(self):
        for bad in [0, -1, None, True, "100", 2 * Image.MAX_IMAGE_PIXELS + 1]:
            with self.subTest(max_pixels=bad):
                with self.assertRaises(ValidationError):
                    ImageParser(max_pixels=bad)

    def test_max_file_size_validation(self):
        for bad in [0, -1, True, "100"]:
            with self.subTest(max_file_size=bad):
                with self.assertRaises(ValidationError):
                    ImageParser(max_file_size=bad)
        ImageParser(max_file_size=None)

    def test_constructs_when_pillow_limit_disabled(self):
        # Applications that accept large scans set MAX_IMAGE_PIXELS = None;
        # the parser must still construct, with Pillow's usual default.
        with patch.object(Image, "MAX_IMAGE_PIXELS", None):
            parser = ImageParser()
            self.assertEqual(parser.max_pixels, 89_478_485)
            path = self._image("a.png", "PNG")
            self.assertEqual(parser.extract_metadata(path).format, "PNG")

    # --- Paths ---

    def test_directory_is_refused(self):
        with self.assertRaises(ValidationError):
            ImageParser().extract_metadata(self.dir)

    def test_directory_reported_as_permission_error_is_refused(self):
        # Windows raises PermissionError, not IsADirectoryError, when
        # opening a directory.
        with patch("semantica.parse.image_parser.os.open", side_effect=PermissionError):
            with self.assertRaises(ValidationError):
                ImageParser().extract_metadata(self.dir)

    def test_permission_error_on_a_file_is_not_hidden(self):
        path = self._image("a.png", "PNG")
        with patch("semantica.parse.image_parser.os.open", side_effect=PermissionError):
            with self.assertRaises(ProcessingError):
                ImageParser().extract_metadata(path)

    # --- Pixel limits ---

    def _png_header(self, width, height, animated=False):
        """
        A PNG with only a header and an empty IDAT: opens, never decodes.

        animated adds the acTL and fcTL chunks of an APNG whose first frame
        disposes to the background, for which Pillow before 13.0 allocates
        the whole canvas inside Image.open.
        """

        def chunk(kind, body):
            return (
                struct.pack(">I", len(body))
                + kind
                + body
                + struct.pack(">I", zlib.crc32(kind + body))
            )

        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        frames = b""
        if animated:
            # Sequence, size, offset, delay, then dispose_op 1 (background).
            fctl = struct.pack(">IIIIIHHBB", 0, width, height, 0, 0, 1, 1, 1, 0)
            frames = chunk(b"acTL", struct.pack(">II", 1, 0)) + chunk(b"fcTL", fctl)
        path = self.dir / f"{width}x{height}.png"
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + frames
            + chunk(b"IDAT", b"")
            + chunk(b"IEND", b"")
        )
        return path

    def _bmp_header(self, width, height):
        """
        A BMP with only a header: opens, never decodes.

        Unlike PNG and WebP, its size isn't checked before Image.open, so
        it reaches Pillow's own bomb check.
        """
        info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, 0, 0, 0, 0, 0)
        path = self.dir / f"{width}x{height}.bmp"
        path.write_bytes(struct.pack("<2sIHHI", b"BM", 54, 0, 0, 54) + info)
        return path

    def test_over_pillow_hard_limit_is_validation_error(self):
        # Over 2 * MAX_IMAGE_PIXELS, Pillow raises DecompressionBombError.
        side = int((2 * Image.MAX_IMAGE_PIXELS) ** 0.5) + 10
        with self.assertRaises(ValidationError):
            ImageParser().extract_metadata(self._bmp_header(side, side))

    def test_pillow_warning_does_not_escape(self):
        # Between MAX and 2 * MAX Pillow only warns; our own check must
        # still produce a ValidationError, even when warnings are errors.
        side = int((1.5 * Image.MAX_IMAGE_PIXELS) ** 0.5)
        path = self._bmp_header(side, side)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with self.assertRaises(ValidationError):
                ImageParser().extract_metadata(path)

    def test_opening_leaves_global_warning_filters_alone(self):
        # The parser must not change process-wide warning filters (as
        # catch_warnings() + simplefilter() do), which other threads
        # depend on.
        parser = ImageParser()
        png = self._image("a.png", "PNG")
        oversized = self._bmp_header(10_000, 10_000)

        # Pillow's own warning still reaches the caller as usual; our check
        # then rejects the image.
        with self.assertWarns(Image.DecompressionBombWarning):
            with patch.object(
                warnings,
                "simplefilter",
                side_effect=AssertionError("warning filters changed"),
            ):
                parser.extract_metadata(png)
                with self.assertRaises(ValidationError):
                    parser.extract_metadata(oversized)

    def test_webp_canvas_checked_before_pillow_opens_it(self):
        # A tiny WebP claiming a 16384 x 16384 canvas: libwebp would
        # allocate it inside Image.open, so it must be refused before that.
        path = self._image("a.webp", "WEBP")
        data = bytearray(path.read_bytes())
        vp8x = b"VP8X" + struct.pack("<I", 10) + b"\x00" * 4
        vp8x += (16383).to_bytes(3, "little") * 2
        data[12:12] = vp8x
        struct.pack_into("<I", data, 4, len(data) - 8)
        path.write_bytes(bytes(data))

        with patch("semantica.parse.image_parser.Image.open") as image_open:
            with self.assertRaises(ValidationError):
                ImageParser().extract_metadata(path)
            image_open.assert_not_called()

    def test_webp_header_size_matches_pillow(self):
        # The header reader must agree with Pillow for every WebP variant.
        variants = {
            "lossy": {"lossless": False},
            "lossless": {"lossless": True},
            "animated": {
                "save_all": True,
                "append_images": [Image.new("RGB", (37, 21), "red")],
            },
        }
        for name, kwargs in variants.items():
            with self.subTest(variant=name):
                path = self.dir / f"{name}.webp"
                Image.new("RGB", (37, 21)).save(path, format="WEBP", **kwargs)
                with Image.open(path) as img:
                    expected = img.size
                self.assertEqual(_webp_canvas_size(path.read_bytes()), expected)

    def test_png_canvas_checked_before_pillow_opens_it(self):
        # A tiny APNG claiming a 22000 x 22000 canvas: Pillow before 13.0
        # would allocate about 1.9 GB inside Image.open (GHSA-5xm2-6676-qcp9),
        # so it must be refused before that. Plain PNGs are checked the same
        # way.
        for animated in (True, False):
            with self.subTest(animated=animated):
                path = self._png_header(22_000, 22_000, animated=animated)
                with patch("semantica.parse.image_parser.Image.open") as image_open:
                    with self.assertRaises(ValidationError):
                        ImageParser().extract_metadata(path)
                    image_open.assert_not_called()

    def test_unreadable_png_header_is_refused(self):
        # The PNG signature, but no IHDR chunk after it.
        path = self.dir / "a.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
        with patch("semantica.parse.image_parser.Image.open") as image_open:
            with self.assertRaises(ValidationError):
                ImageParser().extract_metadata(path)
            image_open.assert_not_called()

    def test_second_png_ihdr_is_refused(self):
        # Pillow takes the size from the last IHDR, so a small first one
        # followed by a 22000 x 22000 one must not get past the check.
        big_ihdr = self._png_header(22_000, 22_000).read_bytes()[8:33]
        path = self._png_header(1, 1, animated=True)
        data = path.read_bytes()
        path.write_bytes(data[:33] + big_ihdr + data[33:])
        with patch("semantica.parse.image_parser.Image.open") as image_open:
            with self.assertRaises(ValidationError):
                ImageParser().extract_metadata(path)
            image_open.assert_not_called()

    def test_png_header_chunk_walk_is_bounded(self):
        # Up to MAX_PNG_HEADER_CHUNKS chunks before the image data are
        # walked; one more is refused without walking the rest, so millions
        # of empty chunks can't stall the check.
        data = self._image("a.png", "PNG").read_bytes()
        empty = struct.pack(">I", 0) + b"tEXt" + struct.pack(">I", zlib.crc32(b"tEXt"))
        path = self.dir / "chunks.png"

        path.write_bytes(data[:33] + empty * MAX_PNG_HEADER_CHUNKS + data[33:])
        self.assertEqual(ImageParser().extract_metadata(path).width, 8)

        path.write_bytes(data[:33] + empty * (MAX_PNG_HEADER_CHUNKS + 1) + data[33:])
        with patch("semantica.parse.image_parser.Image.open") as image_open:
            with self.assertRaises(ValidationError):
                ImageParser().extract_metadata(path)
            image_open.assert_not_called()

    def test_png_header_size_matches_pillow(self):
        # The header reader must agree with Pillow for PNG and APNG.
        variants = {
            "plain": {},
            "animated": {
                "save_all": True,
                "append_images": [Image.new("RGB", (37, 21), "red")],
            },
        }
        for name, kwargs in variants.items():
            with self.subTest(variant=name):
                path = self.dir / f"{name}.png"
                Image.new("RGB", (37, 21)).save(path, format="PNG", **kwargs)
                with Image.open(path) as img:
                    expected = img.size
                self.assertEqual(_png_canvas_size(path.read_bytes()), expected)

    # --- Error mapping and metadata ---

    def test_corrupt_allowed_image_fails_validation(self):
        path = self._image("a.png", "PNG")
        data = bytearray(path.read_bytes())
        data[-20] ^= 0xFF  # corrupt the IDAT data, so verify() fails
        path.write_bytes(bytes(data))
        with self.assertRaises(ValidationError):
            ImageParser().parse(path)

    def test_parse_keeps_validation_error_from_second_open(self):
        # The file can change between parse()'s two opens; a rejection on
        # the second one must still be a ValidationError.
        parser = ImageParser()
        path = self._image("a.png", "PNG")
        real_open = parser._open_image
        calls = []

        def open_then_reject(file_path):
            calls.append(file_path)
            if len(calls) == 2:
                raise ValidationError("now a TIFF")
            return real_open(file_path)

        with patch.object(parser, "_open_image", side_effect=open_then_reject):
            with self.assertRaises(ValidationError) as ctx:
                parser.parse(path)
        self.assertNotIsInstance(ctx.exception, ProcessingError)

    def test_parse_does_not_double_wrap_ocr_errors(self):
        parser = ImageParser()
        path = self._image("a.png", "PNG")
        with (
            patch("semantica.parse.image_parser.TESSERACT_AVAILABLE", True),
            patch.object(
                parser, "extract_text", side_effect=ProcessingError("ocr failed")
            ),
        ):
            with self.assertRaises(ProcessingError) as ctx:
                parser.parse(path, extract_text=True)
        self.assertEqual(str(ctx.exception), "ocr failed")

    def test_jpeg_exif_is_extracted(self):
        path = self.dir / "photo.jpg"
        exif = Image.Exif()
        exif[0x010F] = "TestCam"  # Make
        Image.new("RGB", (8, 8)).save(path, format="JPEG", exif=exif)
        metadata = ImageParser().extract_metadata(path)
        self.assertEqual(metadata.exif.get("Make"), "TestCam")


if __name__ == "__main__":
    unittest.main()
