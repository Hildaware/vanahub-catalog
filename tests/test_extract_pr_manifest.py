import base64
import importlib.util
import sys
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
