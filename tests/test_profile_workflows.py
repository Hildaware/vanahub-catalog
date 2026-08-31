import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class ProfileWorkflowTests(unittest.TestCase):
    def text(self, name):
        return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_review_starts_exact_head_admission(self):
        prepare = self.text("profile.yml")
        admission = self.text("profile-admission.yml")
        self.assertIn("pull_request_review:", admission)
        self.assertIn("github.event.review.commit_id", admission)
        self.assertIn("startsWith(github.event.pull_request.head.ref, 'automation/profile/')", admission)
        self.assertIn('test "$(jq -r .headRefOid <<< "$details")" = "$VH_EXPECTED_HEAD"', admission)
        self.assertNotIn("gh workflow run profile-admission.yml", prepare)

    def test_release_is_published_only_after_merge_validation_and_signing(self):
        admission = self.text("profile-admission.yml")
        publish = self.text("publish.yml")
        self.assertNotIn('gh release edit "$VH_TAG"', admission)
        self.assertIn("needs: [validate, sign]", publish)
        self.assertIn("environment: profile-publishing", publish)
        self.assertIn('gh release edit "$VH_TAG"', publish)

    def test_public_report_omits_archive_locations(self):
        renderer = (ROOT / "scripts" / "render_profile_report.py").read_text(encoding="utf-8")
        self.assertIn("omits matched values, setting keys, and archive paths", renderer)


if __name__ == "__main__":
    unittest.main()
