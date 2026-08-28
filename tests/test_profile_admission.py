import base64
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(ROOT / "scripts"))
extract = load("extract_profile_manifest", ROOT / "scripts" / "extract_profile_manifest.py")
verify = load("verify_profile_update", ROOT / "scripts" / "verify_profile_update.py")


class ProfileAdmissionTests(unittest.TestCase):
    def manifest(self, version="1.2.3"):
        return {
            "id": "raid-profile",
            "version": version,
            "downloadUrl": f"https://github.com/Hildaware/vanahub-catalog/releases/download/profile-raid-profile-v{version}/raid-profile-{version}.vanahub-profile.zip",
        }

    def test_constrains_profile_pr(self):
        self.assertEqual(
            extract.constrained_path(["profiles/raid-profile/manifest.json"]),
            ("profiles/raid-profile/manifest.json", "raid-profile"),
        )
        with self.assertRaisesRegex(ValueError, "exactly one"):
            extract.constrained_path(["profiles/raid-profile/manifest.json", "README.md"])
        with self.assertRaisesRegex(ValueError, "only profiles"):
            extract.constrained_path(["packages/raid-profile/manifest.json"])

    def test_decodes_wrapped_content(self):
        payload = b'{"id":"raid-profile"}\n'
        self.assertEqual(extract.decode_content(base64.encodebytes(payload).decode()), payload)

    def test_release_naming_and_version_increase(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "raid-profile").mkdir()
            (root / "raid-profile" / "manifest.json").write_text(json.dumps(self.manifest("1.0.0")))
            verify.validate(self.manifest(), root, "Hildaware/vanahub-catalog")
            with self.assertRaisesRegex(ValueError, "increase"):
                verify.validate(self.manifest("1.0.0"), root, "Hildaware/vanahub-catalog")
            wrong = self.manifest()
            wrong["downloadUrl"] = "https://example.com/profile.zip"
            with self.assertRaisesRegex(ValueError, "downloadUrl"):
                verify.validate(wrong, root, "Hildaware/vanahub-catalog")


if __name__ == "__main__":
    unittest.main()
