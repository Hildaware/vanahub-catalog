#!/usr/bin/env python3
"""Re-verify a catalog-generated manifest PR without trusting its bot actor."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from discover_releases import authorization, repository_parts


SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
PRIVILEGED_SOURCES = {"vanahub": "https://github.com/Hildaware/vanahub"}


def parse_semver(value: str):
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError(f"invalid SemVer: {value}")
    core = tuple(int(part) for part in match.groups()[:3])
    prerelease = match.group(4)
    identifiers = [] if prerelease is None else prerelease.split(".")
    return core, identifiers, prerelease is None


def greater(candidate: str, previous: str) -> bool:
    left_core, left_pre, left_stable = parse_semver(candidate)
    right_core, right_pre, right_stable = parse_semver(previous)
    if left_core != right_core:
        return left_core > right_core
    if left_stable != right_stable:
        return left_stable
    if left_stable:
        return False
    for left, right in zip(left_pre, right_pre):
        if left == right:
            continue
        if left.isdigit() and right.isdigit():
            return int(left) > int(right)
        if left.isdigit() != right.isdigit():
            return not left.isdigit()
        return left > right
    return len(left_pre) > len(right_pre)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--previous-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    privileged_source = PRIVILEGED_SOURCES.get(manifest.get("id"))
    if privileged_source and manifest.get("sourceUrl", "").rstrip("/").casefold() != privileged_source.casefold():
        raise SystemExit("privileged package ID is reserved for its official source repository")
    owner, repository = repository_parts(manifest.get("sourceUrl", ""))
    download = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+)/releases/download/[^/]+/[^/]+", manifest.get("downloadUrl", ""))
    if not download or tuple(value.casefold() for value in download.groups()) != (owner.casefold(), repository.casefold()):
        raise SystemExit("downloadUrl must be a GitHub Release asset from sourceUrl")
    authorized = authorization(owner, repository, manifest.get("id", ""))
    declared = {str(name).casefold() for name in manifest.get("maintainers", [])}
    if not declared or not declared.issubset(authorized):
        raise SystemExit("catalog maintainers exceed source authorization")
    previous_path = args.previous_root / manifest.get("id", "") / "manifest.json"
    if previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        if not greater(manifest.get("version", ""), previous.get("version", "")):
            raise SystemExit("updates must increase the package SemVer")
    print(f"authorized catalog automation for {manifest['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
