import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "profile_repository_preflight", ROOT / "scripts" / "profile_repository_preflight.py"
)
preflight = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = preflight
spec.loader.exec_module(preflight)


class ProfileRepositoryPreflightTests(unittest.TestCase):
    def responses(self):
        return {
            "repos/Hildaware/vanahub-catalog": {
                "allow_auto_merge": True,
            },
            "repos/Hildaware/vanahub-catalog/rulesets": [
                {"id": 1, "target": "branch", "enforcement": "active"},
            ],
            "repos/Hildaware/vanahub-catalog/rulesets/1": {
                "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                "rules": [
                    {"type": "deletion"},
                    {"type": "non_fast_forward"},
                    {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
                ],
            },
            "repos/Hildaware/vanahub-catalog/environments": {
                "environments": [{
                    "name": "profile-publishing",
                    "protection_rules": [{"type": "required_reviewers"}],
                }]
            },
        }

    def test_accepts_ready_repository(self):
        responses = self.responses()
        self.assertEqual(preflight.evaluate("Hildaware/vanahub-catalog", responses.__getitem__), [])

    def test_reports_every_missing_control(self):
        responses = self.responses()
        responses["repos/Hildaware/vanahub-catalog"] = {
            "allow_auto_merge": False,
        }
        responses["repos/Hildaware/vanahub-catalog/rulesets"] = []
        responses["repos/Hildaware/vanahub-catalog/environments"] = {
            "environments": [{"name": "profile-publishing", "protection_rules": []}]
        }
        failures = preflight.evaluate("Hildaware/vanahub-catalog", responses.__getitem__)
        self.assertEqual(len(failures), 5)
        self.assertTrue(any("auto-merge" in item for item in failures))
        self.assertTrue(any("required reviewers" in item for item in failures))

    def test_ignores_rulesets_that_do_not_apply_to_main(self):
        responses = self.responses()
        responses["repos/Hildaware/vanahub-catalog/rulesets/1"]["conditions"]["ref_name"]["include"] = [
            "refs/heads/release"
        ]
        failures = preflight.evaluate("Hildaware/vanahub-catalog", responses.__getitem__)
        self.assertEqual(failures, [
            "main does not require pull requests before merging",
            "main does not block force pushes",
            "main does not block deletion",
        ])


if __name__ == "__main__":
    unittest.main()
