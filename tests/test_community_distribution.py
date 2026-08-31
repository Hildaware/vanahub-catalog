import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import community_distribution


class CommunityDistributionTests(unittest.TestCase):
    def event(self, author="vanahub-distributor[bot]"):
        return {"issue": {"number": 33, "user": {"login": author}, "body": """### Attempt ID
eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee

### Distro repository
https://github.com/Hildaware/vanahub-addon-distro

### Distro issue
12

### Distro commit
aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

### Candidate path
packages/sample/releases/1.2.3.json

### Package ID
sample

### Version
1.2.3

### SHA-256
bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
"""}}

    def candidate(self, schema=1):
        asset_url = "https://github.com/author/sample/releases/download/v1.2.3/sample.zip"
        semantic = {
            "schemaVersion": schema,
            "artifactSha256": "b" * 64,
            "baseline": {
                "schemaVersion": 1,
                "packageId": "sample",
                "reviewedCommit": "a" * 40,
                "files": {"sample.lua": "c" * 64},
            },
        }
        if schema == 2:
            semantic.update({
                "upstreamCommit": "a" * 40,
                "scanner": {
                    "repository": "https://github.com/Hildaware/vanahub",
                    "revision": "d" * 40,
                    "policySha256": "e" * 64,
                    "semgrepVersion": "1.2.3",
                },
                "reportSha256": "f" * 64,
            })
        return {
            "schemaVersion": 1,
            "manifest": {"id": "sample", "version": "1.2.3", "sha256": "b" * 64, "downloadUrl": asset_url},
            "semanticReview": semantic,
            "provenance": {
                "schemaVersion": 2,
                "packageId": "sample",
                "distributionMethod": "upstream-asset",
                "distributorRepository": community_distribution.DISTRO,
                "distroIssue": 12,
                "upstreamCommit": "a" * 40,
                "upstreamAsset": {"id": 34, "name": "sample.zip", "url": asset_url},
            },
        }

    def test_parses_trusted_handoff_and_binds_provenance(self):
        handoff = community_distribution.context(self.event(), "vanahub-distributor[bot]")
        manifest, provenance, baseline = community_distribution.prepare(self.candidate(2), handoff)
        self.assertEqual(handoff["attemptId"], "e" * 64)
        self.assertEqual(manifest["id"], "sample")
        self.assertEqual(provenance["distroCommit"], "a" * 40)
        self.assertEqual(provenance["catalogSubmissionIssue"], 33)
        self.assertEqual(baseline["reviewedCommit"], provenance["upstreamCommit"])

    def test_accepts_legacy_attestation_for_existing_exact_artifact(self):
        handoff = community_distribution.context(self.event(), "vanahub-distributor[bot]")
        manifest, _, _ = community_distribution.prepare(self.candidate(1), handoff)
        self.assertEqual(manifest["sha256"], "b" * 64)

    def test_fixture_survives_handoff_admission_and_publish_audit(self):
        handoff = community_distribution.context(self.event(), "vanahub-distributor[bot]")
        candidate = self.candidate(2)
        manifest, provenance, baseline = community_distribution.prepare(candidate, handoff)
        audited_baseline, attestation = community_distribution.audit(candidate, manifest, provenance)
        self.assertEqual(audited_baseline, baseline)
        self.assertEqual(attestation["artifactSha256"], manifest["sha256"])

    def test_rejects_semantic_attestation_for_a_different_artifact(self):
        candidate = self.candidate()
        candidate["semanticReview"]["artifactSha256"] = "c" * 64
        handoff = community_distribution.context(self.event(), "vanahub-distributor[bot]")
        with self.assertRaisesRegex(ValueError, "different artifact"):
            community_distribution.prepare(candidate, handoff)

    def test_rejects_baseline_for_different_upstream_commit(self):
        candidate = self.candidate()
        candidate["semanticReview"]["baseline"]["reviewedCommit"] = "c" * 40
        handoff = community_distribution.context(self.event(), "vanahub-distributor[bot]")
        with self.assertRaisesRegex(ValueError, "does not match provenance"):
            community_distribution.prepare(candidate, handoff)

    def test_rejects_distro_hosted_build_candidate(self):
        candidate = self.candidate()
        candidate["provenance"]["distributionMethod"] = "vanahub-build"
        handoff = community_distribution.context(self.event(), "vanahub-distributor[bot]")
        with self.assertRaisesRegex(ValueError, "distribution method"):
            community_distribution.prepare(candidate, handoff)

    def test_rejects_untrusted_author_and_path_escape(self):
        with self.assertRaisesRegex(ValueError, "trusted distributor"):
            community_distribution.context(self.event("attacker"), "vanahub-distributor[bot]")
        event = self.event()
        event["issue"]["body"] = event["issue"]["body"].replace(
            "packages/sample/releases/1.2.3.json", "packages/sample/releases/../../secret.json"
        )
        with self.assertRaisesRegex(ValueError, "candidate path"):
            community_distribution.context(event, "vanahub-distributor[bot]")


if __name__ == "__main__":
    unittest.main()
