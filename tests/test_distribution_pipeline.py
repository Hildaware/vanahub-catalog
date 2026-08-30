import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DistributionPipelineWorkflowTests(unittest.TestCase):
    def workflow(self, name: str) -> str:
        return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_trusted_handoff_has_guarded_retry_and_durable_evidence(self):
        source = self.workflow("community-distribution.yml")
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("issue_number:", source)
        self.assertIn("distro-semantic-attestation.json", source)
        self.assertIn("scanner-drift.json", source)
        self.assertIn("retention-days: 90", source)
        self.assertIn("semgrep==1.175.0", source)

    def test_publish_audits_candidate_and_reconciles_issue(self):
        source = self.workflow("publish.yml")
        self.assertIn("community_distribution.py audit", source)
        self.assertIn("reconcile-community-distributions:", source)
        self.assertIn("--add-label published", source)

    def test_every_catalog_push_uses_explicit_token_remote(self):
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            source = path.read_text(encoding="utf-8")
            if "git push" in source:
                with self.subTest(workflow=path.name):
                    self.assertIn("git remote set-url origin", source)


if __name__ == "__main__":
    unittest.main()
