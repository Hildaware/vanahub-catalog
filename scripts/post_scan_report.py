#!/usr/bin/env python3
"""Post an idempotent release-scan summary to a package's submission issue."""

from __future__ import annotations

import argparse
import html
import json
import os
import urllib.request
from pathlib import Path


API = "https://api.github.com"


def marker(report: dict) -> str:
    result = "accepted" if report.get("accepted") else "rejected"
    values = (
        report.get("packageId", ""),
        report.get("version", ""),
        report.get("sha256", ""),
        report.get("policyVersion", ""),
        result,
    )
    return "<!-- vanahub-scan:" + ":".join(str(value) for value in values) + " -->"


def render(report: dict, run_url: str, pull_request: str = "") -> str:
    accepted = bool(report.get("accepted"))
    findings = report.get("findings", [])
    files = report.get("files", [])
    lines = [
        marker(report),
        f"### VanaHub release scan: `{report.get('version', '')}`",
        "",
        f"**Result:** {'Accepted' if accepted else 'Rejected'}",
        "",
        f"- Package: `{report.get('packageId', '')}`",
        f"- Artifact SHA-256: `{report.get('sha256', '')}`",
        f"- Scanner policy: `{report.get('policyVersion', '')}`",
        f"- Files inspected: {len(files)}",
        f"- Detected capabilities: {', '.join(f'`{value}`' for value in report.get('detectedCapabilities', [])) or 'None'}",
        f"- Findings: {len(findings)}",
    ]
    if pull_request:
        lines.append(f"- Catalog PR: #{pull_request}")
    lines.extend([f"- [Workflow run]({run_url})", ""])
    if findings:
        lines.extend(["<details>", "<summary>Findings</summary>", ""])
        for finding in findings[:50]:
            severity = html.escape(str(finding.get("severity") or "unknown"))
            rule = html.escape(str(finding.get("rule") or "unknown"))
            message = html.escape(str(finding.get("message") or ""))
            location = html.escape(str(finding.get("path") or ""))
            if finding.get("line"):
                location += f":{finding['line']}"
            suffix = f" — <code>{location}</code>" if location else ""
            lines.append(f"- **{severity}** <code>{rule}</code>: {message}{suffix}")
        if len(findings) > 50:
            lines.append(f"- …and {len(findings) - 50} additional findings.")
        lines.extend(["", "</details>", ""])
    if files:
        lines.extend(["<details>", "<summary>Inspected files</summary>", ""])
        for path in files[:100]:
            lines.append(f"- <code>{html.escape(str(path))}</code>")
        if len(files) > 100:
            lines.append(f"- …and {len(files) - 100} additional files.")
        lines.extend(["", "</details>", ""])
    lines.append(
        "The issue was reopened for maintainer attention." if not accepted
        else "Admission will independently re-verify this release before publication."
    )
    return "\n".join(lines) + "\n"


def request(repository: str, path: str, token: str, method: str = "GET", body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        f"{API}/repos/{repository}/{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "vanahub-scan-reporter/1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def already_reported(repository: str, issue: int, token: str, value: str) -> bool:
    for page in range(1, 11):
        comments = request(repository, f"issues/{issue}/comments?per_page=100&page={page}", token)
        if any(value in str(comment.get("body", "")) for comment in comments):
            return True
        if len(comments) < 100:
            return False
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("provenance", type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--pull-request", default="")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
    if provenance.get("schemaVersion") != 1 or provenance.get("packageId") != report.get("packageId"):
        raise SystemExit("scan report does not match package provenance")
    issue = provenance.get("submissionIssue")
    if not isinstance(issue, int) or isinstance(issue, bool) or issue < 1:
        raise SystemExit("package provenance has an invalid submission issue")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    value = marker(report)
    if already_reported(args.repository, issue, token, value):
        print(f"scan report already posted to issue #{issue}")
        return 0
    if not report.get("accepted"):
        request(args.repository, f"issues/{issue}", token, "PATCH", {"state": "open"})
    request(
        args.repository,
        f"issues/{issue}/comments",
        token,
        "POST",
        {"body": render(report, args.run_url, args.pull_request)},
    )
    print(f"posted scan report to issue #{issue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
