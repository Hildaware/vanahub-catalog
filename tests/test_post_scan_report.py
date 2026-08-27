import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "post_scan_report.py"
spec = importlib.util.spec_from_file_location("post_scan_report", SCRIPT)
reporter = importlib.util.module_from_spec(spec)
sys.modules["post_scan_report"] = reporter
spec.loader.exec_module(reporter)


class ScanReportTests(unittest.TestCase):
    def test_renders_stable_marker_and_escapes_findings(self):
        report = {
            "packageId": "sample",
            "version": "1.2.0",
            "sha256": "a" * 64,
            "policyVersion": 1,
            "accepted": False,
            "files": ["sample.lua"],
            "detectedCapabilities": ["chat-output"],
            "findings": [{"severity": "error", "rule": "lua.blocked", "message": "bad <tag>", "path": "sample.lua", "line": 4}],
        }
        rendered = reporter.render(report, "https://example.test/run", "14")
        self.assertIn("vanahub-scan:sample:1.2.0", rendered)
        self.assertIn("**Result:** Rejected", rendered)
        self.assertIn("bad &lt;tag&gt;", rendered)
        self.assertIn("<code>sample.lua</code>", rendered)
        self.assertIn("Catalog PR: #14", rendered)
        self.assertIn("issue was reopened", rendered)

    def test_marker_distinguishes_policy_and_result(self):
        report = {"packageId": "sample", "version": "1.0.0", "sha256": "a", "policyVersion": 1, "accepted": True}
        changed = dict(report, policyVersion=2)
        rejected = dict(report, accepted=False)
        self.assertNotEqual(reporter.marker(report), reporter.marker(changed))
        self.assertNotEqual(reporter.marker(report), reporter.marker(rejected))


if __name__ == "__main__":
    unittest.main()
