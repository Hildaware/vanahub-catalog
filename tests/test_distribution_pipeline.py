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
        self.assertIn("gh workflow run admission.yml", source)
        self.assertIn("expected_head_sha=\"$head_sha\"", source)
        self.assertIn("catalog:prepared", source)
        self.assertIn("actions: write", source)

    def test_release_intake_is_consolidated_and_dispatches_exact_heads(self):
        source = self.workflow("discover.yml")
        self.assertFalse((ROOT / ".github" / "workflows" / "submission.yml").exists())
        self.assertIn("startsWith(github.event.issue.title, 'Add package:')", source)
        self.assertIn("startsWith(github.event.issue.title, 'Check update:')", source)
        self.assertIn("discover_releases.py initial", source)
        self.assertIn("discover_releases.py update", source)
        self.assertIn("discover_releases.py poll", source)
        self.assertIn("expected_head_sha=\"$head_sha\"", source)
        self.assertIn("render_media_preview.py", source)

    def test_scanner_setup_is_shared_and_pinned(self):
        action = (ROOT / ".github" / "actions" / "setup-catalog-scanner" / "action.yml").read_text(encoding="utf-8")
        self.assertIn("semgrep==1.175.0", action)
        self.assertIn("51eca79806b7167b7c332e4b7fdfed0aee14cc71", action)
        for workflow in ("admission.yml", "community-distribution.yml", "discover.yml", "publish.yml"):
            with self.subTest(workflow=workflow):
                source = self.workflow(workflow)
                self.assertIn("setup-catalog-scanner", source)
                self.assertNotIn("semgrep==1.175.0", source)

    def test_publish_audits_candidate_and_reconciles_issue(self):
        source = self.workflow("publish.yml")
        self.assertIn("community_distribution.py audit", source)
        self.assertIn("reconcile-community-distributions:", source)
        self.assertIn("--add-label published", source)
        self.assertIn("group: catalog-publish", source)

    def test_admission_serializes_each_pull_request(self):
        source = self.workflow("admission.yml")
        self.assertIn("group: catalog-admission-${{ inputs.pr_number || github.event.pull_request.number }}", source)
        self.assertIn("cancel-in-progress: true", source)

    def test_every_catalog_push_uses_explicit_token_remote(self):
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            source = path.read_text(encoding="utf-8")
            if "git push" in source:
                with self.subTest(workflow=path.name):
                    self.assertIn("git remote set-url origin", source)


if __name__ == "__main__":
    unittest.main()
