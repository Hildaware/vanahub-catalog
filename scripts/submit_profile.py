#!/usr/bin/env python3
"""Stage a local profile export and start catalog preparation."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import zipfile
from pathlib import Path

from profile_repository_preflight import evaluate, gh_api


PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
CATEGORIES = {
    "combat", "jobs", "inventory", "crafting", "economy", "maps-travel",
    "user-interface", "chat-communication", "data-tracking",
    "quality-of-life", "development-tools",
}


def inspect_source(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("profile export is missing or exceeds 64 MiB")
    try:
        with zipfile.ZipFile(path) as archive:
            matches = [item for item in archive.infolist() if item.filename.casefold() == "profile.json"]
            if len(matches) != 1 or matches[0].file_size > 2 * 1024 * 1024:
                raise ValueError("profile export must contain one bounded profile.json")
            value = json.loads(archive.read(matches[0]).decode("utf-8"))
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise ValueError(f"profile export is invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("profile export manifest is invalid")
    profile = value.get("profile")
    name = profile.get("name") if isinstance(profile, dict) else None
    addons = profile.get("addons") if isinstance(profile, dict) else None
    if value.get("schemaVersion") != 1 or not isinstance(name, str) or not name.strip():
        raise ValueError("profile export manifest is invalid")
    if not isinstance(addons, list) or not 1 <= len(addons) <= 256:
        raise ValueError("profile export must contain one to 256 addons")
    return name.strip()


def validate_metadata(profile_id: str, version: str, categories: str) -> list[str]:
    if not PROFILE_ID.fullmatch(profile_id):
        raise ValueError("profile id must be lowercase and contain two to 64 safe characters")
    if not SEMVER.fullmatch(version):
        raise ValueError("version must be SemVer")
    parsed = [item.strip() for item in categories.split(",") if item.strip()]
    if len(parsed) > 3 or len(parsed) != len(set(parsed)) or not set(parsed) <= CATEGORIES:
        raise ValueError("categories must contain up to three unique catalog category ids")
    return parsed


def command(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(arguments, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "command failed")
    return result


def submit(args: argparse.Namespace) -> None:
    name = inspect_source(args.source)
    categories = validate_metadata(args.profile_id, args.version, args.categories)
    failures = evaluate(args.repository, gh_api)
    if failures:
        raise RuntimeError("profile publication is not ready:\n" + "\n".join(f"- {item}" for item in failures))
    tag = f"profile-{args.profile_id}-v{args.version}"
    asset_name = f"{args.profile_id}-{args.version}.source.vanahub-profile.zip"
    encoded_tag = urllib.parse.quote(tag, safe="")
    release = command(["gh", "api", f"repos/{args.repository}/releases/tags/{encoded_tag}"], check=False)
    if release.returncode == 0:
        details = json.loads(release.stdout)
        if details.get("draft") is not True or details.get("prerelease") is True:
            raise RuntimeError(f"existing release {tag} must remain a non-prerelease draft")
    elif "HTTP 404" in release.stderr:
        command(["gh", "release", "create", tag, "--repo", args.repository, "--draft", "--title", f"{name} {args.version}"])
    else:
        raise RuntimeError(release.stderr.strip() or f"could not inspect release {tag}")
    with tempfile.TemporaryDirectory(prefix="vanahub-profile-submit-") as directory:
        staged = Path(directory) / asset_name
        shutil.copy2(args.source, staged)
        upload = ["gh", "release", "upload", tag, str(staged), "--repo", args.repository]
        if args.replace_source:
            upload.append("--clobber")
        command(upload)
    dispatch = [
        "gh", "workflow", "run", "profile.yml", "--repo", args.repository, "--ref", "main",
        "-f", f"profile_id={args.profile_id}", "-f", f"version={args.version}",
        "-f", f"description={args.description}", "-f", f"author={args.author}",
        "-f", f"categories={','.join(categories)}", "-f", "confirm_public=true",
    ]
    command(dispatch)
    print(f"Profile preparation started: https://github.com/{args.repository}/actions/workflows/profile.yml")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--id", dest="profile_id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--categories", default="")
    parser.add_argument("--repository", default="Hildaware/vanahub-catalog")
    parser.add_argument("--replace-source", action="store_true", help="Replace an existing source asset when retrying")
    parser.add_argument("--confirm-public", action="store_true", help="Confirm that this profile is intended for public distribution")
    args = parser.parse_args()
    if not args.confirm_public:
        parser.error("--confirm-public is required")
    try:
        submit(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
