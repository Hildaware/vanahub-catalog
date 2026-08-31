#!/usr/bin/env python3
"""Extract exactly one permitted PR manifest through the GitHub contents API."""

import argparse
import base64
import hashlib
import json
import os
import re
import urllib.request
import io
from pathlib import Path

from PIL import Image, UnidentifiedImageError

PRIVILEGED_SOURCES = {"vanahub": "https://github.com/Hildaware/vanahub"}


def decode_github_content(content: object) -> bytes:
    if not isinstance(content, str):
        raise ValueError("GitHub content response is not a string")
    return base64.b64decode("".join(content.split()), validate=True)


def validate_privileged_source(manifest: dict) -> None:
    expected = PRIVILEGED_SOURCES.get(manifest.get("id"))
    if expected and manifest.get("sourceUrl", "").rstrip("/").casefold() != expected.casefold():
        raise ValueError("privileged package ID is reserved for its official source repository")


def catalog_media_paths(manifest: dict, media_base: str) -> list[str]:
    package_id = manifest.get("id", "")
    prefix = f"{media_base.rstrip('/')}/{package_id}/"
    references = []
    if manifest.get("iconUrl") is not None:
        references.append(manifest["iconUrl"])
    references.extend(manifest.get("screenshots", []))
    for value in references:
        if not isinstance(value, str) or not re.fullmatch(
            re.escape(prefix) + r"[a-f0-9]{64}\.jpg", value
        ):
            raise ValueError("catalog manifests may reference only content-addressed catalog media")
    return list(dict.fromkeys(
        f"media/{package_id}/{value.removeprefix(prefix)}" for value in references
    ))


def validate_catalog_media_references(manifest: dict, media_base: str) -> None:
    catalog_media_paths(manifest, media_base)


def constrained_paths(paths: list[str], allow_media: bool, allow_provenance: bool = False, allow_community_review: bool = False) -> tuple[str, list[str], str | None]:
    manifests = [path for path in paths if re.fullmatch(r"packages/[a-z0-9][a-z0-9._-]{1,63}/manifest\.json", path)]
    if len(manifests) != 1:
        raise ValueError("Routine admission PRs must change exactly one package manifest")
    manifest_path = manifests[0]
    package_id = manifest_path.split("/")[1]
    provenance_path = f"packages/{package_id}/provenance.json"
    provenance = provenance_path if provenance_path in paths else None
    review_path = f"reviews/{package_id}.json"
    review = review_path if review_path in paths else None
    if provenance and not allow_provenance:
        raise ValueError("Maintainer admission PRs may not change package provenance")
    if review and not allow_community_review:
        raise ValueError("Only trusted community distribution automation may add a review baseline")
    if review and not provenance:
        raise ValueError("A community review baseline requires package provenance")
    media = [path for path in paths if path not in {manifest_path, provenance_path, review_path}]
    if media and not allow_media:
        raise ValueError("Maintainer admission PRs may not add catalog media")
    if len(media) > 11 or any(
        not re.fullmatch(rf"media/{re.escape(package_id)}/[a-f0-9]{{64}}\.jpg", path)
        for path in media
    ):
        raise ValueError("Automated media changes must be content-addressed JPEGs for the submitted package")
    return manifest_path, media, provenance


def validate_provenance(content: bytes, package_id: str) -> dict:
    if len(content) > 4096:
        raise ValueError("package provenance exceeds the 4 KiB admission limit")
    document = json.loads(content)
    if document.get("schemaVersion") == 1:
        if set(document) != {"schemaVersion", "packageId", "submissionIssue"}:
            raise ValueError("package provenance has unknown or missing fields")
        issue = document.get("submissionIssue")
        if document.get("packageId") != package_id or not isinstance(issue, int) or isinstance(issue, bool) or issue < 1:
            raise ValueError("package provenance is invalid")
        return document
    required = {
        "schemaVersion", "packageId", "distributionMethod", "distributorRepository", "distroIssue",
        "distroCommit", "upstreamRepository", "upstreamReleaseId", "upstreamReleaseUrl", "upstreamTag",
        "upstreamCommit", "license", "catalogSubmissionIssue",
    }
    optional = {"upstreamAsset", "reviewedException"}
    if document.get("schemaVersion") != 2 or not required.issubset(document) or set(document) - required - optional:
        raise ValueError("community distribution provenance has unknown or missing fields")
    if document.get("packageId") != package_id or document.get("distributorRepository") != "https://github.com/Hildaware/vanahub-addon-distro":
        raise ValueError("community distribution provenance is invalid")
    if not isinstance(document.get("distroIssue"), int) or not isinstance(document.get("catalogSubmissionIssue"), int):
        raise ValueError("community distribution provenance issues are invalid")
    if document.get("distributionMethod") != "upstream-asset":
        raise ValueError("community distribution method is invalid")
    asset = document.get("upstreamAsset")
    if not isinstance(asset, dict) or set(asset) != {"id", "name", "url"}:
        raise ValueError("community upstream-asset provenance is invalid")
    return document


def validate_community_review(content: bytes, package_id: str, provenance: dict) -> None:
    if provenance.get("distributorRepository") != "https://github.com/Hildaware/vanahub-addon-distro":
        raise ValueError("only community distribution provenance may carry a review baseline")
    document = json.loads(content)
    if (
        document.get("schemaVersion") != 1
        or document.get("packageId") != package_id
        or document.get("reviewedCommit") != provenance.get("upstreamCommit")
        or not isinstance(document.get("files"), dict)
        or set(document) - {"schemaVersion", "packageId", "reviewedCommit", "files", "findings"}
    ):
        raise ValueError("community review baseline is invalid")


def validate_media(path: str, content: bytes, manifest: dict, media_base: str) -> None:
    if len(content) < 4 or len(content) > 750 * 1024 or not content.startswith(b"\xff\xd8") or not content.endswith(b"\xff\xd9"):
        raise ValueError("catalog media must be a JPEG no larger than 750 KiB")
    digest = hashlib.sha256(content).hexdigest()
    if Path(path).stem != digest:
        raise ValueError("catalog media filename must match its SHA-256")
    expected = f"{media_base.rstrip('/')}/{manifest['id']}/{digest}.jpg"
    references = [manifest.get("iconUrl"), *manifest.get("screenshots", [])]
    if expected not in references:
        raise ValueError("changed catalog media must be referenced by the package manifest")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format != "JPEG" or getattr(image, "n_frames", 1) != 1:
                raise ValueError("catalog media must be a single-frame JPEG")
            image.load()
            if image.width < 1 or image.height < 1 or image.width > 1280 or image.height > 720:
                raise ValueError("catalog media dimensions exceed 1280x720")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("catalog media is not a valid JPEG") from exc


def github_content(repository: str, path: str, ref: str, token: str) -> bytes:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/contents/{path}?ref={ref}",
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "User-Agent": "vanahub-admission/1"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return decode_github_content(json.load(response)["content"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("changed")
    parser.add_argument("repository")
    parser.add_argument("ref")
    parser.add_argument("output")
    parser.add_argument("--allow-media", action="store_true")
    parser.add_argument("--allow-provenance", action="store_true")
    parser.add_argument("--media-base", default="https://hildaware.github.io/vanahub-catalog/media")
    parser.add_argument("--allow-community-review", action="store_true")
    args = parser.parse_args(argv)
    changed = json.loads(Path(args.changed).read_text(encoding="utf-8"))
    paths = [item["filename"] for item in changed]
    try:
        manifest_path, media_paths, provenance_path = constrained_paths(
            paths, args.allow_media, args.allow_provenance, args.allow_community_review
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    token = os.environ.get("GH_TOKEN", "")
    decoded = github_content(args.repository, manifest_path, args.ref, token)
    if len(decoded) > 128 * 1024:
        raise SystemExit("manifest exceeds the 128 KiB admission limit")
    manifest = json.loads(decoded)
    validate_privileged_source(manifest)
    package_id = manifest_path.split("/")[1]
    if manifest.get("id") != package_id:
        raise SystemExit("manifest id must match its catalog package directory")
    try:
        provenance = None
        if provenance_path:
            provenance = validate_provenance(
                github_content(args.repository, provenance_path, args.ref, token), package_id
            )
        review_path = f"reviews/{package_id}.json"
        if review_path in paths:
            if provenance is None:
                raise ValueError("community review baseline requires provenance")
            validate_community_review(
                github_content(args.repository, review_path, args.ref, token), package_id, provenance
            )
        referenced_media = catalog_media_paths(manifest, args.media_base)
        if any(path not in referenced_media for path in media_paths):
            raise ValueError("changed catalog media must be referenced by the package manifest")
        for path in referenced_media:
            validate_media(
                path,
                github_content(args.repository, path, args.ref, token),
                manifest,
                args.media_base,
            )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    Path(args.output).write_bytes(decoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
