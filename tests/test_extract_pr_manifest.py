import base64
import hashlib
import importlib.util
import sys
import unittest
import io
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).parents[1] / "scripts" / "extract_pr_manifest.py"
spec = importlib.util.spec_from_file_location("extract_pr_manifest", SCRIPT)
extract = importlib.util.module_from_spec(spec)
sys.modules["extract_pr_manifest"] = extract
spec.loader.exec_module(extract)


class ExtractManifestTests(unittest.TestCase):
    def test_decodes_line_wrapped_github_content(self):
        document = b'{"schemaVersion":1,"id":"sample"}\n'
        encoded = base64.encodebytes(document).decode("ascii")
        self.assertEqual(extract.decode_github_content(encoded), document)

    def test_rejects_non_string_github_content(self):
        with self.assertRaisesRegex(ValueError, "not a string"):
            extract.decode_github_content(None)

    def test_rejects_privileged_id_from_unofficial_source(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            extract.validate_privileged_source({
                "id": "vanahub",
                "sourceUrl": "https://github.com/attacker/vanahub",
            })

    def test_allows_only_automated_content_addressed_package_media(self):
        digest = "a" * 64
        manifest, media = extract.constrained_paths(
            [
                "packages/sample/manifest.json",
                f"media/sample/{digest}.jpg",
            ],
            True,
        )
        self.assertEqual(manifest, "packages/sample/manifest.json")
        self.assertEqual(media, [f"media/sample/{digest}.jpg"])
        with self.assertRaisesRegex(ValueError, "may not add"):
            extract.constrained_paths(
                ["packages/sample/manifest.json", f"media/sample/{digest}.jpg"],
                False,
            )

    def test_media_bytes_must_match_filename_and_manifest(self):
        output = io.BytesIO()
        Image.new("RGB", (32, 32), (20, 40, 60)).save(output, "JPEG")
        content = output.getvalue()
        digest = hashlib.sha256(content).hexdigest()
        path = f"media/sample/{digest}.jpg"
        manifest = {
            "id": "sample",
            "screenshots": [f"https://catalog.example/media/sample/{digest}.jpg"],
        }
        extract.validate_media(
            path, content, manifest, "https://catalog.example/media"
        )
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            extract.validate_media(
                f"media/sample/{'a' * 64}.jpg",
                content,
                manifest,
                "https://catalog.example/media",
            )

    def test_icon_media_reference_is_accepted(self):
        output = io.BytesIO()
        Image.new("RGB", (32, 32)).save(output, "JPEG")
        content = output.getvalue()
        digest = hashlib.sha256(content).hexdigest()
        extract.validate_media(
            f"media/sample/{digest}.jpg",
            content,
            {"id": "sample", "iconUrl": f"https://catalog.example/media/sample/{digest}.jpg"},
            "https://catalog.example/media",
        )

    def test_manifest_rejects_external_media_references(self):
        with self.assertRaisesRegex(ValueError, "content-addressed catalog media"):
            extract.validate_catalog_media_references(
                {"id": "sample", "iconUrl": "https://images.example/icon.png"},
                "https://catalog.example/media",
            )

    def test_manifest_maps_every_media_reference_to_catalog_content(self):
        first = "a" * 64
        second = "b" * 64
        self.assertEqual(
            extract.catalog_media_paths(
                {
                    "id": "sample",
                    "iconUrl": f"https://catalog.example/media/sample/{first}.jpg",
                    "screenshots": [
                        f"https://catalog.example/media/sample/{second}.jpg",
                        f"https://catalog.example/media/sample/{second}.jpg",
                    ],
                },
                "https://catalog.example/media",
            ),
            [f"media/sample/{first}.jpg", f"media/sample/{second}.jpg"],
        )


if __name__ == "__main__":
    unittest.main()
