import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SemanticWorkflowTests(unittest.TestCase):
    def workflow(self, name: str) -> str:
        return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_every_package_boundary_runs_the_semantic_wrapper(self):
        for workflow in ("submission.yml", "discover.yml", "admission.yml", "publish.yml"):
            with self.subTest(workflow=workflow):
                source = self.workflow(workflow)
                self.assertIn("semgrep==1.175.0", source)
                self.assertIn("scan_catalog_package.sh", source)

    def test_admission_uses_only_the_trusted_base_review_directory(self):
        admission = self.workflow("admission.yml")
        self.assertIn("catalog-base/reviews", admission)
        self.assertNotIn("--baseline manifest", admission)

    def test_catalog_owns_review_instructions_and_xiui_baseline(self):
        self.assertTrue((ROOT / "reviews" / "README.md").is_file())
        self.assertTrue((ROOT / "reviews" / "xiui.json").is_file())


if __name__ == "__main__":
    unittest.main()
