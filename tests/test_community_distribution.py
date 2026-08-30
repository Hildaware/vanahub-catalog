import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import community_distribution


class CommunityDistributionTests(unittest.TestCase):
    def event(self, author="vanahub-distributor[bot]"):
        return {"issue": {"number": 33, "user": {"login": author}, "body": """### Distro repository
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

    def candidate(self):
        return {"schemaVersion": 1, "manifest": {"id": "sample", "version": "1.2.3", "sha256": "b" * 64}, "semanticReview": {
            "schemaVersion": 1,
            "artifactSha256": "b" * 64,
            "baseline": {
                "schemaVersion": 1,
                "packageId": "sample",
                "reviewedCommit": "a" * 40,
                "files": {"sample.lua": "c" * 64},
            },
        }, "provenance": {
            "schemaVersion": 2, "packageId": "sample", "distributionMethod": "upstream-asset",
            "distributorRepository": community_distribution.DISTRO, "distroIssue": 12,
        }}

    def test_parses_trusted_handoff_and_binds_provenance(self):
        handoff = community_distribution.context(self.event(), "vanahub-distributor[bot]")
        manifest, provenance, baseline = community_distribution.prepare(self.candidate(), handoff)
        self.assertEqual(manifest["id"], "sample")
        self.assertEqual(provenance["distroCommit"], "a" * 40)
        self.assertEqual(provenance["catalogSubmissionIssue"], 33)
        self.assertEqual(baseline["files"]["sample.lua"], "c" * 64)

    def test_rejects_semantic_attestation_for_a_different_artifact(self):
        candidate = self.candidate()
        candidate["semanticReview"]["artifactSha256"] = "d" * 64
        handoff = community_distribution.context(self.event(), "vanahub-distributor[bot]")
        with self.assertRaisesRegex(ValueError, "does not match artifact"):
            community_distribution.prepare(candidate, handoff)

    def test_rejects_untrusted_author_and_path_escape(self):
        with self.assertRaisesRegex(ValueError, "trusted distributor"):
            community_distribution.context(self.event("attacker"), "vanahub-distributor[bot]")
        event = self.event()
        event["issue"]["body"] = event["issue"]["body"].replace("packages/sample/releases/1.2.3.json", "../candidate.json")
        with self.assertRaisesRegex(ValueError, "candidate path"):
            community_distribution.context(event, "vanahub-distributor[bot]")


if __name__ == "__main__":
    unittest.main()
