#!/usr/bin/env python3
"""Verify immutable release naming and monotonic profile versions."""

import argparse
import json
import re
import urllib.parse
from pathlib import Path

from verify_automated import greater, parse_semver


def validate(manifest: dict, previous_root: Path, repository: str) -> None:
    profile_id = manifest.get("id", "")
    version = manifest.get("version", "")
    parse_semver(version)
    escaped_repository = re.escape(repository)
    expected = (
        f"https://github.com/{repository}/releases/download/"
        f"profile-{profile_id}-v{version}/{profile_id}-{version}.vanahub-profile.zip"
    )
    if manifest.get("downloadUrl") != expected:
        raise ValueError(f"downloadUrl must be {expected}")
    addons = manifest.get("addons")
    if not isinstance(addons, list) or not 1 <= len(addons) <= 256:
        raise ValueError("profile must contain one to 256 addons")
    packages_root = previous_root.parent / "packages"
    for entry in addons:
        if not isinstance(entry, dict) or not isinstance(entry.get("source"), dict):
            raise ValueError("profile addon entry is invalid")
        if entry["source"].get("builtin") is not True:
            continue
        package_id = entry.get("id", "")
        package_path = packages_root / package_id / "manifest.json"
        if not package_path.is_file():
            raise ValueError(f"builtin addon is not present in this catalog: {package_id}")
        package = json.loads(package_path.read_text(encoding="utf-8"))
        if package.get("id") != package_id:
            raise ValueError(f"builtin addon manifest id does not match: {package_id}")
        for field in ("version", "sha256"):
            if field in entry and entry[field] != package.get(field):
                raise ValueError(f"builtin addon {field} is unavailable: {package_id}")
    for key in ("iconUrl",):
        if key in manifest:
            value = manifest[key]
            if not isinstance(value, str) or len(value) > 2048 or urllib.parse.urlsplit(value).scheme != "https":
                raise ValueError("profile iconUrl must be an HTTPS URL")
    if "screenshots" in manifest:
        screenshots = manifest["screenshots"]
        if not isinstance(screenshots, list) or not 1 <= len(screenshots) <= 10 or len(screenshots) != len(set(screenshots)):
            raise ValueError("profile screenshots are invalid")
        if any(not isinstance(value, str) or len(value) > 2048 or urllib.parse.urlsplit(value).scheme != "https" for value in screenshots):
            raise ValueError("profile screenshots must be HTTPS URLs")
    previous = previous_root / profile_id / "manifest.json"
    if previous.exists():
        old = json.loads(previous.read_text(encoding="utf-8"))
        if not greater(version, old.get("version", "")):
            raise ValueError("profile updates must increase SemVer")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--previous-root", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    try:
        validate(json.loads(args.manifest.read_text(encoding="utf-8")), args.previous_root, args.repository)
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
