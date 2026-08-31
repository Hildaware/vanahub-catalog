import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DistributionWorkflowTests(unittest.TestCase):
    def test_private_distro_reads_use_distributor_app(self):
        community = (ROOT / ".github/workflows/community-distribution.yml").read_text(encoding="utf-8")
        publish = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
        for workflow in (community, publish):
            self.assertIn("VANAHUB_DISTRIBUTOR_APP_ID", workflow)
            self.assertIn("VANAHUB_DISTRIBUTOR_APP_PRIVATE_KEY", workflow)
            self.assertIn("repositories: vanahub-addon-distro", workflow)

    def test_catalog_has_no_distro_hosting_exception(self):
        paths = [
            ROOT / ".github/workflows/admission.yml",
            ROOT / ".github/workflows/community-distribution.yml",
            ROOT / ".github/workflows/publish.yml",
            ROOT / "scripts/extract_pr_manifest.py",
            ROOT / "scripts/verify_automated.py",
        ]
        for path in paths:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("vanahub-build", content, path)
            self.assertNotIn("buildRevision", content, path)


if __name__ == "__main__":
    unittest.main()
