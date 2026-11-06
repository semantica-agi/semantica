"""Media parsing with real files and an unpatched progress tracker."""

import wave

from PIL import Image

from semantica.parse.media_parser import MediaParser


def test_parse_media_image_without_metadata(tmp_path):
    image_path = tmp_path / "image.png"
    Image.new("RGB", (4, 4)).save(image_path)

    result = MediaParser().parse_media(image_path, extract_metadata=False)

    assert result == {"metadata": None, "ocr": None, "text": None}


def test_parse_media_audio(tmp_path):
    audio_path = tmp_path / "audio.wav"
    with wave.open(str(audio_path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 80)

    result = MediaParser().parse_media(audio_path)

    assert result["type"] == "audio"
    assert result["metadata"]["file_path"] == str(audio_path)
    assert result["metadata"]["file_size"] == audio_path.stat().st_size
    assert result["metadata"]["format"] == ".wav"
