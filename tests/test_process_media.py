import hashlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from PIL import Image
except ImportError:
    Image = None


SCRIPT = Path(__file__).parents[1] / "scripts" / "process_media.py"


@unittest.skipIf(Image is None, "Pillow is installed by catalog media CI")
class ProcessMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("process_media", SCRIPT)
        cls.media = importlib.util.module_from_spec(spec)
        sys.modules["process_media"] = cls.media
        spec.loader.exec_module(cls.media)
        cls.media._nsfw_classifier = lambda image: [
            {"label": "normal", "score": 0.99},
            {"label": "nsfw", "score": 0.01},
        ]

    def image(self, size=(1600, 900), color=(20, 40, 60, 255)):
        output = io.BytesIO()
        Image.new("RGBA", size, color).save(output, "PNG")
        return output.getvalue()

    def test_normalizes_to_bounded_content_addressed_jpeg(self):
        source = self.image()
        staged = "https://uploads.example/pending/12345678-1234-1234-1234-123456789abc/" + "b" * 64 + ".png"
        manifest = {"id": "sample", "screenshots": [staged]}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            self.media, "download", return_value=source
        ):
            result = self.media.process(
                manifest,
                Path(directory),
                "https://catalog.example/media",
                staging_base="https://uploads.example",
            )
            url = result["screenshots"][0]
            path = Path(directory) / "sample" / url.rsplit("/", 1)[-1]
            data = path.read_bytes()
            self.assertEqual(path.stem, hashlib.sha256(data).hexdigest())
            self.assertLessEqual(len(data), self.media.MAX_OUTPUT)
            with Image.open(path) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertLessEqual(image.width, 1280)
                self.assertLessEqual(image.height, 720)

    def test_preserves_existing_canonical_media_on_package_updates(self):
        canonical = "https://catalog.example/media/sample/" + "a" * 64 + ".jpg"
        manifest = {"id": "sample", "screenshots": ["https://expired.example/staged.png"]}
        previous = {"id": "sample", "screenshots": [canonical]}
        with tempfile.TemporaryDirectory() as directory:
            result = self.media.process(
                manifest, Path(directory), "https://catalog.example/media", previous
            )
        self.assertEqual(result["screenshots"], [canonical])

    def test_icon_is_content_addressed_and_referenced(self):
        staged = "https://uploads.example/pending/12345678-1234-1234-1234-123456789abc/" + "c" * 64 + ".png"
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            self.media, "download", return_value=self.image((128, 128))
        ):
            result = self.media.process(
                {"id": "sample", "iconUrl": staged},
                Path(directory),
                "https://catalog.example/media",
                staging_base="https://uploads.example",
            )
            self.assertRegex(result["iconUrl"], r"/[a-f0-9]{64}\.jpg$")
            self.assertNotIn("icon.jpg", result["iconUrl"])

    def test_partial_expiry_blocks_replacement(self):
        prefix = "https://uploads.example/pending/12345678-1234-1234-1234-123456789abc/"
        values = [prefix + "a" * 64 + ".png", prefix + "b" * 64 + ".png"]
        previous = {"screenshots": ["https://catalog.example/media/sample/" + "c" * 64 + ".jpg"]}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            self.media,
            "download",
            side_effect=[self.image(), self.media.StagedMediaExpired("expired")],
        ):
            with self.assertRaisesRegex(ValueError, "complete media set"):
                self.media.process(
                    {"id": "sample", "screenshots": values},
                    Path(directory),
                    "https://catalog.example/media",
                    previous,
                    "https://uploads.example",
                )

    def test_moderation_flag_and_missing_label_block(self):
        image = Image.new("RGB", (32, 32))
        with mock.patch.object(
            self.media,
            "_nsfw_classifier",
            lambda value: [{"label": "nsfw", "score": 0.99}],
        ):
            with self.assertRaises(self.media.NSFWImageError):
                self.media.check_nsfw(image)
        with mock.patch.object(
            self.media,
            "_nsfw_classifier",
            lambda value: [{"label": "normal", "score": 1.0}],
        ):
            with self.assertRaisesRegex(RuntimeError, "expected nsfw label"):
                self.media.check_nsfw(image)


if __name__ == "__main__":
    unittest.main()
