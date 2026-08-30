#!/usr/bin/env python3
"""Validate a machine-created handoff from vanahub-addon-distro."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


DISTRO = "https://github.com/Hildaware/vanahub-addon-distro"
PACKAGE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def fields(body: str) -> dict[str, str]:
    return {
        heading.strip().casefold().replace("-", ""): value.strip()
        for heading, value in re.findall(r"###\s+([^\n]+)\s*\n+(.+?)(?=\n###|\Z)", body, re.DOTALL)
    }


def context(event: dict, expected_author: str) -> dict:
    issue = event.get("issue") or {}
    if not expected_author or str(issue.get("user", {}).get("login", "")).casefold() != expected_author.casefold():
        raise ValueError("community distribution handoff was not created by the trusted distributor App")
    values = fields(str(issue.get("body", "")))
    required = ["distro repository", "distro issue", "distro commit", "candidate path", "package id", "version", "sha256"]
    if any(not values.get(name) for name in required):
        raise ValueError("community distribution issue is incomplete")
    if values["distro repository"].rstrip("/") != DISTRO:
        raise ValueError("community distribution issue names an untrusted distro repository")
    if not PACKAGE_ID.fullmatch(values["package id"]):
        raise ValueError("community distribution package ID is invalid")
    if not COMMIT.fullmatch(values["distro commit"]):
        raise ValueError("community distribution commit is invalid")
    if not re.fullmatch(rf"packages/{re.escape(values['package id'])}/releases/[0-9A-Za-z.+-]+\.json", values["candidate path"]):
        raise ValueError("community distribution candidate path is invalid")
    if not re.fullmatch(r"[a-f0-9]{64}", values["sha256"]):
        raise ValueError("community distribution SHA-256 is invalid")
    if not values["distro issue"].isdigit() or int(values["distro issue"]) < 1:
        raise ValueError("community distribution distro issue is invalid")
    return {
        "catalogIssue": int(issue["number"]),
        "distroIssue": int(values["distro issue"]),
        "distroCommit": values["distro commit"],
        "candidatePath": values["candidate path"],
        "packageId": values["package id"],
        "version": values["version"],
        "sha256": values["sha256"],
    }


def prepare(candidate: dict, handoff: dict) -> tuple[dict, dict, dict]:
    if candidate.get("schemaVersion") != 1:
        raise ValueError("candidate record schema is unsupported")
    manifest = candidate.get("manifest")
    provenance = candidate.get("provenance")
    if not isinstance(manifest, dict) or not isinstance(provenance, dict):
        raise ValueError("candidate record is incomplete")
    if manifest.get("id") != handoff["packageId"] or provenance.get("packageId") != handoff["packageId"]:
        raise ValueError("candidate package ID does not match handoff")
    if manifest.get("version") != handoff["version"] or manifest.get("sha256") != handoff["sha256"]:
        raise ValueError("candidate version or SHA-256 does not match handoff")
    if provenance.get("schemaVersion") != 2 or provenance.get("distributorRepository") != DISTRO:
        raise ValueError("candidate provenance is not a trusted distro record")
    if provenance.get("distroIssue") != handoff["distroIssue"]:
        raise ValueError("candidate distro issue does not match handoff")
    semantic = candidate.get("semanticReview")
    if not isinstance(semantic, dict) or semantic.get("schemaVersion") != 1:
        raise ValueError("candidate semantic review attestation is missing")
    if semantic.get("artifactSha256") != manifest.get("sha256"):
        raise ValueError("candidate semantic review attestation does not match artifact")
    baseline = semantic.get("baseline")
    if not isinstance(baseline, dict) or baseline.get("schemaVersion") != 1 or baseline.get("packageId") != manifest.get("id"):
        raise ValueError("candidate semantic review baseline is invalid")
    if not isinstance(baseline.get("reviewedCommit"), str) or not COMMIT.fullmatch(baseline["reviewedCommit"]):
        raise ValueError("candidate semantic review baseline commit is invalid")
    if not isinstance(baseline.get("files"), dict) or not all(
        isinstance(path, str) and isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest)
        for path, digest in baseline["files"].items()
    ):
        raise ValueError("candidate semantic review baseline files are invalid")
    provenance = dict(provenance)
    provenance["distroCommit"] = handoff["distroCommit"]
    provenance["catalogSubmissionIssue"] = handoff["catalogIssue"]
    return manifest, provenance, baseline


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    parse = commands.add_parser("context")
    parse.add_argument("--event", type=Path, required=True)
    parse.add_argument("--expected-author", required=True)
    parse.add_argument("--output", type=Path, required=True)
    prepare_command = commands.add_parser("prepare")
    prepare_command.add_argument("--candidate", type=Path, required=True)
    prepare_command.add_argument("--handoff", type=Path, required=True)
    prepare_command.add_argument("--manifest", type=Path, required=True)
    prepare_command.add_argument("--provenance", type=Path, required=True)
    prepare_command.add_argument("--semantic-baseline", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "context":
            value = context(json.loads(args.event.read_text(encoding="utf-8")), args.expected_author)
            args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
            handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
            manifest, provenance, baseline = prepare(candidate, handoff)
            args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            args.provenance.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            args.semantic_baseline.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"community distribution error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
