#!/usr/bin/env python3
"""Extract one generated profile manifest from an exact PR head."""

import argparse
import base64
import json
import os
import re
import urllib.request
from pathlib import Path


PROFILE_PATH = re.compile(r"profiles/([a-z0-9][a-z0-9._-]{1,63})/manifest\.json")


def constrained_path(paths: list[str]) -> tuple[str, str]:
    if len(paths) != 1:
        raise ValueError("Profile admission PRs must change exactly one file")
    match = PROFILE_PATH.fullmatch(paths[0])
    if not match:
        raise ValueError("Profile admission PRs may change only profiles/<id>/manifest.json")
    return paths[0], match.group(1)


def decode_content(value: object) -> bytes:
    if not isinstance(value, str):
        raise ValueError("GitHub content response is not a string")
    return base64.b64decode("".join(value.split()), validate=True)


def github_content(repository: str, path: str, ref: str, token: str) -> bytes:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/contents/{path}?ref={ref}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "vanahub-profile-admission/1",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return decode_content(json.load(response)["content"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("changed", type=Path)
    parser.add_argument("repository")
    parser.add_argument("ref")
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    paths = [item["filename"] for item in json.loads(args.changed.read_text(encoding="utf-8"))]
    try:
        path, profile_id = constrained_path(paths)
        content = github_content(args.repository, path, args.ref, os.environ.get("GH_TOKEN", ""))
        if len(content) > 128 * 1024:
            raise ValueError("profile manifest exceeds 128 KiB")
        manifest = json.loads(content)
        if manifest.get("id") != profile_id:
            raise ValueError("manifest id must match its profile directory")
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    args.output.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
