#!/usr/bin/env python3
"""Discover VanaHub manifests attached to authorized public GitHub releases."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path


SOURCE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?$")
PACKAGE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
SEMVER = re.compile(r"^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
PRIVILEGED_SOURCES = {"vanahub": "https://github.com/Hildaware/vanahub"}


def request(url: str, accept: str = "application/vnd.github+json"):
    headers = {"Accept": accept, "User-Agent": "vanahub-discovery/1"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        return response.read()


def request_json(url: str):
    return json.loads(request(url))


def semver(value: str):
    match = SEMVER.fullmatch(value)
    if not match or match.group(4) is not None:
        return None
    return tuple(int(part) for part in match.groups()[:3])


def repository_parts(url: str) -> tuple[str, str]:
    match = SOURCE.fullmatch(url.strip())
    if not match:
        raise ValueError("repository must be a public GitHub repository URL")
    return match.group(1), match.group(2)


def authorization(owner: str, repository: str, package_id: str) -> set[str]:
    metadata = request_json(f"https://api.github.com/repos/{owner}/{repository}")
    if metadata.get("private"):
        raise ValueError("private repositories are not accepted by the public catalog")
    branch = urllib.parse.quote(metadata["default_branch"], safe="")
    document = json.loads(request(f"https://raw.githubusercontent.com/{owner}/{repository}/{branch}/.vanahub.json"))
    if document.get("schemaVersion") != 1:
        raise ValueError("source .vanahub.json has an unsupported schema")
    package = document.get("packages", {}).get(package_id)
    if not isinstance(package, dict):
        raise ValueError("source repository does not authorize this package ID")
    maintainers = package.get("maintainers")
    if not isinstance(maintainers, list) or not maintainers:
        raise ValueError("source repository has no authorized maintainers")
    return {str(name).casefold() for name in maintainers}


def release_manifest(repository_url: str, package_id: str, previous: str | None = None) -> dict:
    privileged_source = PRIVILEGED_SOURCES.get(package_id)
    if privileged_source and repository_url.rstrip("/").casefold() != privileged_source.casefold():
        raise ValueError("privileged package ID is reserved for its official source repository")
    owner, repository = repository_parts(repository_url)
    authorized = authorization(owner, repository, package_id)
    releases = request_json(f"https://api.github.com/repos/{owner}/{repository}/releases?per_page=100")
    candidates = []
    previous_version = semver(previous) if previous else None
    for release in releases:
        version = semver(str(release.get("tag_name", "")))
        if version is None or release.get("draft") or release.get("prerelease"):
            continue
        if previous_version is not None and version <= previous_version:
            continue
        manifest_asset = next((asset for asset in release.get("assets", []) if asset.get("name") == "vanahub-manifest.json"), None)
        if manifest_asset:
            candidates.append((version, release, manifest_asset))
    if not candidates:
        raise LookupError("no newer stable VanaHub release was found")
    _, release, manifest_asset = max(candidates, key=lambda item: item[0])
    manifest = json.loads(request(manifest_asset["url"], "application/octet-stream"))
    if manifest.get("id") != package_id:
        raise ValueError("release manifest package ID does not match")
    if manifest.get("sourceUrl", "").rstrip("/").casefold() != repository_url.rstrip("/").casefold():
        raise ValueError("release manifest source repository does not match")
    tag_version = str(release["tag_name"]).removeprefix("v")
    if manifest.get("version") != tag_version:
        raise ValueError("release manifest version does not match its tag")
    declared = {str(name).casefold() for name in manifest.get("maintainers", [])}
    if not declared or not declared.issubset(authorized):
        raise ValueError("release manifest maintainers exceed source authorization")
    artifact_name = urllib.parse.unquote(urllib.parse.urlparse(manifest.get("downloadUrl", "")).path.rsplit("/", 1)[-1])
    artifact = next((asset for asset in release.get("assets", []) if asset.get("name") == artifact_name), None)
    if not artifact or artifact.get("browser_download_url") != manifest.get("downloadUrl"):
        raise ValueError("release manifest artifact is not attached to the same release")
    return manifest


def issue_fields(event: dict) -> tuple[str, str, str]:
    body = event.get("issue", {}).get("body", "")
    values = {}
    for heading, value in re.findall(r"###\s+([^\n]+)\s*\n+([^#]+?)(?=\n###|\Z)", body, re.DOTALL):
        values[heading.strip().casefold()] = value.strip()
    repository = values.get("repository url", "")
    package_id = values.get("package id", "")
    actor = event.get("issue", {}).get("user", {}).get("login", "")
    if not repository or not PACKAGE_ID.fullmatch(package_id) or not actor:
        raise ValueError("submission issue is missing a valid repository URL, package ID, or actor")
    return repository, package_id, actor


def initial(event_path: Path, output: Path):
    repository, package_id, actor = issue_fields(json.loads(event_path.read_text(encoding="utf-8")))
    owner, name = repository_parts(repository)
    if actor.casefold() not in authorization(owner, name, package_id):
        raise ValueError("submission issue author is not an authorized package maintainer")
    output.write_text(json.dumps(release_manifest(repository, package_id), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def poll(packages_root: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(packages_root.glob("*/manifest.json")):
        current = json.loads(path.read_text(encoding="utf-8"))
        try:
            manifest = release_manifest(current["sourceUrl"], current["id"], current["version"])
        except LookupError:
            continue
        except Exception as exc:
            print(f"warning: {current.get('id', path.parent.name)}: {exc}")
            continue
        (output_dir / f"{current['id']}.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update(event_path: Path, packages_root: Path, output_dir: Path):
    repository, package_id, actor = issue_fields(json.loads(event_path.read_text(encoding="utf-8")))
    current_path = packages_root / package_id / "manifest.json"
    if not current_path.exists():
        raise ValueError("package is not registered; use the initial submission form")
    current = json.loads(current_path.read_text(encoding="utf-8"))
    if current.get("sourceUrl", "").rstrip("/").casefold() != repository.rstrip("/").casefold():
        raise ValueError("update repository does not match the registered package")
    owner, name = repository_parts(repository)
    if actor.casefold() not in authorization(owner, name, package_id):
        raise ValueError("update issue author is not an authorized package maintainer")
    manifest = release_manifest(repository, package_id, current.get("version"))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{package_id}.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    issue = subparsers.add_parser("initial")
    issue.add_argument("--event", type=Path, required=True)
    issue.add_argument("--output", type=Path, required=True)
    scheduled = subparsers.add_parser("poll")
    scheduled.add_argument("--packages-root", type=Path, required=True)
    scheduled.add_argument("--output-dir", type=Path, required=True)
    immediate = subparsers.add_parser("update")
    immediate.add_argument("--event", type=Path, required=True)
    immediate.add_argument("--packages-root", type=Path, required=True)
    immediate.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "initial":
        initial(args.event, args.output)
    elif args.command == "poll":
        poll(args.packages_root, args.output_dir)
    else:
        update(args.event, args.packages_root, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
