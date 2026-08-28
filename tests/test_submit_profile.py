import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("submit_profile", ROOT / "scripts" / "submit_profile.py")
submit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = submit
spec.loader.exec_module(submit)


class SubmitProfileTests(unittest.TestCase):
    def write_profile(self, path, addons=None):
        value = {
            "schemaVersion": 1,
            "profile": {"name": "Starter", "addons": addons if addons is not None else [{"id": "sample"}]},
        }
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("profile.json", json.dumps(value))

    def test_inspects_profile_name_and_addons(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "profile.zip"
            self.write_profile(source)
            self.assertEqual(submit.inspect_source(source), "Starter")
            self.write_profile(source, [])
            with self.assertRaisesRegex(ValueError, "one to 256"):
                submit.inspect_source(source)

    def test_validates_metadata(self):
        self.assertEqual(submit.validate_metadata("starter-profile", "1.2.3", "jobs,combat"), ["jobs", "combat"])
        with self.assertRaisesRegex(ValueError, "SemVer"):
            submit.validate_metadata("starter-profile", "latest", "")
        with self.assertRaisesRegex(ValueError, "category ids"):
            submit.validate_metadata("starter-profile", "1.2.3", "unknown")


if __name__ == "__main__":
    unittest.main()
