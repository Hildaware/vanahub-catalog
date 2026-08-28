#!/usr/bin/env python3
"""Verify immutable release naming and monotonic profile versions."""

import argparse
import json
import re
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
