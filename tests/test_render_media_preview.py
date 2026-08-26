import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "render_media_preview.py"


class RenderPreviewTests(unittest.TestCase):
    def test_preview_uses_only_commit_pinned_catalog_paths(self):
        digest = "a" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            output = root / "preview.md"
            manifest.write_text(
                json.dumps(
                    {
                        "id": "sample",
                        "screenshots": [
                            f"https://catalog.example/media/sample/{digest}.jpg"
                        ],
                    }
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    str(manifest),
                    str(output),
                    "--catalog-base",
                    "https://catalog.example/media",
                    "--raw-base",
                    "https://raw.example/commit/media",
                ],
                check=True,
            )
            markdown = output.read_text(encoding="utf-8")
            self.assertIn("https://raw.example/commit/media/sample/", markdown)
            self.assertNotIn("catalog.example", markdown)


if __name__ == "__main__":
    unittest.main()
