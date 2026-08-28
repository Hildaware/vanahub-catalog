#!/usr/bin/env python3
"""Verify GitHub repository controls required for profile publication."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable


class PreflightError(Exception):
    pass


def gh_api(path: str) -> object:
    result = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()[0] if result.stderr.strip() else path
        raise PreflightError(detail)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PreflightError(f"GitHub returned invalid JSON for {path}") from exc


def evaluate(repository: str, api: Callable[[str], object]) -> list[str]:
    failures: list[str] = []
    details = api(f"repos/{repository}")
    if not isinstance(details, dict):
        raise PreflightError("repository response is invalid")
    if details.get("allow_auto_merge") is not True:
        failures.append("repository auto-merge is disabled")

    rule_types: set[str] = set()
    review_count = 0
    rulesets = api(f"repos/{repository}/rulesets")
    if not isinstance(rulesets, list):
        raise PreflightError("rulesets response is invalid")
    for summary in rulesets:
        if not isinstance(summary, dict) or summary.get("target") != "branch" or summary.get("enforcement") != "active":
            continue
        identifier = summary.get("id")
        if not isinstance(identifier, int):
            continue
        ruleset = api(f"repos/{repository}/rulesets/{identifier}")
        if not isinstance(ruleset, dict):
            continue
        conditions = ruleset.get("conditions", {}).get("ref_name", {})
        includes = conditions.get("include", []) if isinstance(conditions, dict) else []
        excludes = conditions.get("exclude", []) if isinstance(conditions, dict) else []
        applies = ("~DEFAULT_BRANCH" in includes or "refs/heads/main" in includes) and not (
            "~DEFAULT_BRANCH" in excludes or "refs/heads/main" in excludes
        )
        if not applies:
            continue
        for rule in ruleset.get("rules", []):
            if not isinstance(rule, dict) or not isinstance(rule.get("type"), str):
                continue
            rule_types.add(rule["type"])
            if rule["type"] == "pull_request":
                parameters = rule.get("parameters", {})
                if isinstance(parameters, dict):
                    review_count = max(review_count, parameters.get("required_approving_review_count", 0))

    if "pull_request" not in rule_types:
        failures.append("main does not require pull requests before merging")
    elif review_count < 1:
        failures.append("main does not require an approving pull-request review")
    if "non_fast_forward" not in rule_types:
        failures.append("main does not block force pushes")
    if "deletion" not in rule_types:
        failures.append("main does not block deletion")

    environments = api(f"repos/{repository}/environments")
    if not isinstance(environments, dict) or not isinstance(environments.get("environments"), list):
        raise PreflightError("environments response is invalid")
    profile = next(
        (item for item in environments["environments"] if item.get("name") == "profile-publishing"),
        None,
    )
    if profile is None:
        failures.append("profile-publishing environment does not exist")
    else:
        rules = profile.get("protection_rules", [])
        if not any(isinstance(rule, dict) and rule.get("type") == "required_reviewers" for rule in rules):
            failures.append("profile-publishing environment has no required reviewers")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", help="GitHub owner/repository")
    args = parser.parse_args()
    try:
        failures = evaluate(args.repository, gh_api)
    except PreflightError as exc:
        raise SystemExit(f"profile publication preflight failed: {exc}") from exc
    if failures:
        formatted = "\n".join(f"- {failure}" for failure in failures)
        raise SystemExit(f"profile publication is not ready:\n{formatted}")
    print("profile publication repository controls are ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
