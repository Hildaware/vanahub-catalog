#!/usr/bin/env python3
"""Render a profile scan report without exposing matched values."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path


def render(value: object) -> str:
    if not isinstance(value, dict):
        raise ValueError("profile report must be an object")
    redacted = value.get("redacted")
    warnings = value.get("warnings")
    findings = value.get("findings")
    if not isinstance(redacted, int) or not isinstance(warnings, int) or not isinstance(findings, list):
        raise ValueError("profile report is missing counts or findings")
    lines = [
        "### Profile privacy and safety report",
        "",
        f"- Redacted values: {redacted}",
        f"- Privacy warnings requiring review: {warnings}",
        "",
    ]
    if not findings:
        lines.append("No findings were reported.")
        return "\n".join(lines) + "\n"
    lines.extend([
        "The public summary omits matched values, setting keys, and archive paths. Authorized reviewers can inspect the retained JSON artifact.",
        "",
        "<table>",
        "<thead><tr><th>Count</th><th>Severity</th><th>Rule</th><th>Action</th><th>Message</th></tr></thead>",
        "<tbody>",
    ])
    grouped: Counter[tuple[str, str, str, str]] = Counter()
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("profile finding must be an object")
        grouped[tuple(str(finding.get(field, "")) for field in ("severity", "ruleId", "action", "message"))] += 1
    for values, count in sorted(grouped.items()):
        cells = [str(count), *(html.escape(value, quote=True) for value in values)]
        lines.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    lines.extend(["</tbody>", "</table>"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        value = json.loads(args.report.read_text(encoding="utf-8"))
        args.output.write_text(render(value), encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
