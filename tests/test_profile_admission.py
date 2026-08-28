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
            "addons": [{
                "id": "sample-addon",
                "source": {"builtin": True},
                "autoLoad": True,
                "settings": True,
            }],
        }

    def write_package(self, root, version="2.0.0", sha256="a" * 64):
        package = root / "packages" / "sample-addon"
        package.mkdir(parents=True)
        (package / "manifest.json").write_text(json.dumps({
            "id": "sample-addon", "version": version, "sha256": sha256,
        }))

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
            profiles = root / "profiles"
            (profiles / "raid-profile").mkdir(parents=True)
            (profiles / "raid-profile" / "manifest.json").write_text(json.dumps(self.manifest("1.0.0")))
            self.write_package(root)
            verify.validate(self.manifest(), profiles, "Hildaware/vanahub-catalog")
            with self.assertRaisesRegex(ValueError, "increase"):
                verify.validate(self.manifest("1.0.0"), profiles, "Hildaware/vanahub-catalog")
            wrong = self.manifest()
            wrong["downloadUrl"] = "https://example.com/profile.zip"
            with self.assertRaisesRegex(ValueError, "downloadUrl"):
                verify.validate(wrong, profiles, "Hildaware/vanahub-catalog")

    def test_requires_resolvable_builtin_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profiles = root / "profiles"
            profiles.mkdir()
            with self.assertRaisesRegex(ValueError, "not present"):
                verify.validate(self.manifest(), profiles, "Hildaware/vanahub-catalog")
            self.write_package(root)
            pinned = self.manifest()
            pinned["addons"][0]["version"] = "1.0.0"
            with self.assertRaisesRegex(ValueError, "version is unavailable"):
                verify.validate(pinned, profiles, "Hildaware/vanahub-catalog")

    def test_rejects_empty_profiles_and_unsafe_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profiles = root / "profiles"
            profiles.mkdir()
            empty = self.manifest()
            empty["addons"] = []
            with self.assertRaisesRegex(ValueError, "one to 256"):
                verify.validate(empty, profiles, "Hildaware/vanahub-catalog")
            self.write_package(root)
            unsafe = self.manifest()
            unsafe["iconUrl"] = "javascript:alert(1)"
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                verify.validate(unsafe, profiles, "Hildaware/vanahub-catalog")


if __name__ == "__main__":
    unittest.main()
