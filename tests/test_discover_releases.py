import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "discover_releases.py"
spec = importlib.util.spec_from_file_location("discover_releases", SCRIPT)
discover = importlib.util.module_from_spec(spec)
sys.modules["discover_releases"] = discover
spec.loader.exec_module(discover)

VERIFY_SCRIPT = Path(__file__).parents[1] / "scripts" / "verify_automated.py"
verify_spec = importlib.util.spec_from_file_location("verify_automated", VERIFY_SCRIPT)
verify = importlib.util.module_from_spec(verify_spec)
verify_spec.loader.exec_module(verify)


class DiscoveryTests(unittest.TestCase):
    def test_rejects_privileged_id_from_unofficial_repository(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            discover.release_manifest("https://github.com/attacker/vanahub", "vanahub")

    def test_semver_order_matches_catalog_admission(self):
        self.assertTrue(verify.greater("1.0.0", "1.0.0-rc.1"))
        self.assertTrue(verify.greater("1.0.0-rc.1", "1.0.0-1"))
        self.assertFalse(verify.greater("1.0.0-1", "1.0.0-rc.1"))

    def test_issue_form_fields(self):
        event = {"issue": {"user": {"login": "author"}, "body": "### Repository URL\n\nhttps://github.com/author/sample\n\n### Package ID\n\nsample\n\n### Confirmation\n\n- [x] yes"}}
        self.assertEqual(discover.issue_fields(event), ("https://github.com/author/sample", "sample", "author"))

    def test_release_discovery_chooses_highest_stable_version(self):
        releases = [
            {"tag_name": "v1.1.0", "draft": False, "prerelease": False, "assets": [
                {"name": "vanahub-manifest.json", "url": "manifest-1"},
                {"name": "sample-1.1.0.zip", "browser_download_url": "https://github.com/author/sample/releases/download/v1.1.0/sample-1.1.0.zip"},
            ]},
            {"tag_name": "v2.0.0-beta.1", "draft": False, "prerelease": True, "assets": []},
        ]
        manifest = {
            "id": "sample", "version": "1.1.0", "sourceUrl": "https://github.com/author/sample",
            "downloadUrl": "https://github.com/author/sample/releases/download/v1.1.0/sample-1.1.0.zip",
            "maintainers": ["author"],
        }
        with mock.patch.object(discover, "authorization", return_value={"author"}), mock.patch.object(discover, "request_json", return_value=releases), mock.patch.object(discover, "request", return_value=json.dumps(manifest).encode()):
            self.assertEqual(discover.release_manifest("https://github.com/author/sample", "sample", "1.0.0"), manifest)

    def test_rejects_issue_actor_outside_authorization(self):
        event = {"issue": {"user": {"login": "intruder"}, "body": "### Repository URL\n\nhttps://github.com/author/sample\n\n### Package ID\n\nsample"}}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(discover, "authorization", return_value={"author"}):
            event_path = Path(directory) / "event.json"
            event_path.write_text(json.dumps(event), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not an authorized"):
                discover.initial(event_path, Path(directory) / "manifest.json")


if __name__ == "__main__":
    unittest.main()
