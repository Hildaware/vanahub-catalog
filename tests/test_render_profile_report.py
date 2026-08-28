import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "render_profile_report", ROOT / "scripts" / "render_profile_report.py"
)
renderer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = renderer
spec.loader.exec_module(renderer)


class RenderProfileReportTests(unittest.TestCase):
    def test_renders_safe_finding_details(self):
        output = renderer.render({
            "redacted": 1,
            "warnings": 1,
            "findings": [{
                "severity": "warning",
                "ruleId": "privacy.email",
                "path": "settings/addon/<script>.txt",
                "key": "",
                "action": "review",
                "message": "Possible email address",
            }],
        })
        self.assertIn("Privacy warnings requiring review: 1", output)
        self.assertIn("privacy.email", output)
        self.assertNotIn("settings/addon/", output)
        self.assertNotIn("<script>", output)

    def test_rejects_malformed_report(self):
        with self.assertRaisesRegex(ValueError, "missing counts"):
            renderer.render({"findings": []})


if __name__ == "__main__":
    unittest.main()
