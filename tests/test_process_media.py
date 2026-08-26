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

    def image(self, size=(1600, 900), color=(20, 40, 60, 255)):
        output = io.BytesIO()
        Image.new("RGBA", size, color).save(output, "PNG")
        return output.getvalue()

    def test_normalizes_to_bounded_content_addressed_jpeg(self):
        source = self.image()
        manifest = {"id": "sample", "screenshots": ["https://images.example/screen.png"]}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            self.media, "download", return_value=source
        ):
            result = self.media.process(
                manifest, Path(directory), "https://catalog.example/media"
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

    def test_preview_renders_source_images_in_issue_markdown(self):
        markdown = self.media.preview_markdown(
            {"screenshots": ["https://uploads.example/pending/one.png"]}
        )
        self.assertIn("![Screenshot 1]", markdown)
        self.assertIn("uploads.example", markdown)


if __name__ == "__main__":
    unittest.main()
