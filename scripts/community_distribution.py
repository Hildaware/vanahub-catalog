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
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def fields(body: str) -> dict[str, str]:
    return {
        heading.strip().casefold().replace("-", ""): value.strip()
        for heading, value in re.findall(r"###\s+([^\n]+)\s*\n+(.+?)(?=\n###|\Z)", body, re.DOTALL)
    }


def context(event: dict, expected_author: str) -> dict:
    issue = event.get("issue") or {}
    author = str(issue.get("user", {}).get("login", ""))
    if not expected_author or author.casefold() != expected_author.casefold():
        raise ValueError("community distribution handoff was not created by the trusted distributor App")
    values = fields(str(issue.get("body", "")))
    required = ["distro repository", "distro issue", "distro commit", "candidate path", "package id", "version", "sha256"]
    if any(not values.get(name) for name in required):
        raise ValueError("community distribution issue is incomplete")
    if values["distro repository"].rstrip("/") != DISTRO:
        raise ValueError("community distribution issue names an untrusted distro repository")
    package_id = values["package id"]
    commit = values["distro commit"]
    candidate_path = values["candidate path"]
    artifact_sha = values["sha256"]
    if not PACKAGE_ID.fullmatch(package_id):
        raise ValueError("community distribution package ID is invalid")
    if not COMMIT.fullmatch(commit):
        raise ValueError("community distribution commit is invalid")
    if not re.fullmatch(rf"packages/{re.escape(package_id)}/releases/[0-9A-Za-z.+-]+\.json", candidate_path):
        raise ValueError("community distribution candidate path is invalid")
    if not SHA256.fullmatch(artifact_sha):
        raise ValueError("community distribution SHA-256 is invalid")
    if not values["distro issue"].isdigit() or int(values["distro issue"]) < 1:
        raise ValueError("community distribution distro issue is invalid")
    return {
        "catalogIssue": int(issue["number"]),
        "distroIssue": int(values["distro issue"]),
        "distroCommit": commit,
        "candidatePath": candidate_path,
        "packageId": package_id,
        "version": values["version"],
        "sha256": artifact_sha,
        "attemptId": values.get("attempt id", ""),
    }


def validate_attestation(candidate: dict, manifest: dict, provenance: dict) -> dict:
    semantic = candidate.get("semanticReview")
    if not isinstance(semantic, dict) or semantic.get("schemaVersion") not in {1, 2}:
        raise ValueError("candidate semantic attestation is missing or unsupported")
    if semantic.get("artifactSha256") != manifest.get("sha256"):
        raise ValueError("candidate semantic attestation is for a different artifact")
    baseline = semantic.get("baseline")
    if not isinstance(baseline, dict) or baseline.get("schemaVersion") != 1:
        raise ValueError("candidate semantic baseline is invalid")
    if baseline.get("packageId") != manifest.get("id") or not isinstance(baseline.get("files"), dict):
        raise ValueError("candidate semantic baseline does not match package")
    reviewed_commit = baseline.get("reviewedCommit")
    if not isinstance(reviewed_commit, str) or not COMMIT.fullmatch(reviewed_commit):
        raise ValueError("candidate semantic baseline reviewed commit is invalid")
    if reviewed_commit != provenance.get("upstreamCommit"):
        raise ValueError("candidate semantic baseline commit does not match provenance upstream commit")
    if semantic["schemaVersion"] == 2:
        if semantic.get("upstreamCommit") != provenance.get("upstreamCommit"):
            raise ValueError("candidate semantic attestation upstream commit does not match provenance")
        scanner = semantic.get("scanner") or {}
        if (
            not isinstance(scanner.get("repository"), str)
            or not COMMIT.fullmatch(str(scanner.get("revision", "")))
            or not SHA256.fullmatch(str(scanner.get("policySha256", "")))
            or not isinstance(scanner.get("semgrepVersion"), str)
            or not scanner["semgrepVersion"]
            or not SHA256.fullmatch(str(semantic.get("reportSha256", "")))
        ):
            raise ValueError("candidate semantic scanner identity is invalid")
    return semantic


def prepare(candidate: dict, handoff: dict) -> tuple[dict, dict, dict]:
    if candidate.get("schemaVersion") != 1:
        raise ValueError("candidate record schema is unsupported")
    manifest = candidate.get("manifest")
    provenance = candidate.get("provenance")
    if not isinstance(manifest, dict) or not isinstance(provenance, dict):
        raise ValueError("candidate record is incomplete")
    if manifest.get("id") != handoff["packageId"] or provenance.get("packageId") != handoff["packageId"]:
        raise ValueError("candidate package ID does not match handoff")
    if manifest.get("version") != handoff["version"]:
        raise ValueError("candidate version does not match handoff")
    if manifest.get("sha256") != handoff["sha256"]:
        raise ValueError("candidate SHA-256 does not match handoff")
    if provenance.get("schemaVersion") != 2 or provenance.get("distributorRepository") != DISTRO:
        raise ValueError("candidate provenance is not from the trusted distributor")
    if provenance.get("distributionMethod") != "upstream-asset":
        raise ValueError("candidate distribution method is invalid")
    asset = provenance.get("upstreamAsset")
    if not isinstance(asset, dict) or asset.get("url") != manifest.get("downloadUrl"):
        raise ValueError("candidate upstream asset does not match manifest")
    if provenance.get("distroIssue") != handoff["distroIssue"]:
        raise ValueError("candidate distro issue does not match handoff")
    semantic = validate_attestation(candidate, manifest, provenance)
    bound_provenance = dict(provenance)
    bound_provenance["distroCommit"] = handoff["distroCommit"]
    bound_provenance["catalogSubmissionIssue"] = handoff["catalogIssue"]
    return manifest, bound_provenance, semantic["baseline"]


def audit(candidate: dict, manifest: dict, provenance: dict) -> tuple[dict, dict]:
    candidate_manifest = candidate.get("manifest") or {}
    candidate_provenance = candidate.get("provenance") or {}
    if (
        candidate_manifest.get("id") != manifest.get("id")
        or candidate_manifest.get("version") != manifest.get("version")
        or candidate_manifest.get("sha256") != manifest.get("sha256")
    ):
        raise ValueError("published manifest does not match immutable distro candidate")
    if provenance.get("distroCommit") is None or provenance.get("distroIssue") != candidate_provenance.get("distroIssue"):
        raise ValueError("published provenance does not match immutable distro candidate")
    if provenance.get("upstreamCommit") != candidate_provenance.get("upstreamCommit"):
        raise ValueError("published upstream commit does not match immutable distro candidate")
    semantic = validate_attestation(candidate, candidate_manifest, candidate_provenance)
    return semantic["baseline"], semantic


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
    prepare_command.add_argument("--semantic-attestation", type=Path)
    audit_command = commands.add_parser("audit")
    audit_command.add_argument("--candidate", type=Path, required=True)
    audit_command.add_argument("--manifest", type=Path, required=True)
    audit_command.add_argument("--provenance", type=Path, required=True)
    audit_command.add_argument("--semantic-baseline", type=Path, required=True)
    audit_command.add_argument("--semantic-attestation", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "context":
            value = context(json.loads(args.event.read_text(encoding="utf-8")), args.expected_author)
            args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif args.command == "prepare":
            candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
            handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
            manifest, provenance, baseline = prepare(candidate, handoff)
            args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            args.provenance.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            args.semantic_baseline.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if args.semantic_attestation:
                args.semantic_attestation.write_text(
                    json.dumps(candidate["semanticReview"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
        else:
            candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
            baseline, attestation = audit(candidate, manifest, provenance)
            args.semantic_baseline.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            args.semantic_attestation.write_text(json.dumps(attestation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"community distribution error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
