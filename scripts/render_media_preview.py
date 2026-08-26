#!/usr/bin/env python3
"""Render catalog-controlled media at a raw URL pinned to an automation commit."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--catalog-base", required=True)
    parser.add_argument("--raw-base", required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    def raw(value: str) -> str:
        prefix = args.catalog_base.rstrip("/") + "/"
        if not value.startswith(prefix):
            raise ValueError("preview media must be catalog controlled")
        return args.raw_base.rstrip("/") + "/" + value.removeprefix(prefix)

    lines = ["## Validated media preview", ""]
    if manifest.get("iconUrl"):
        lines.extend(["**Icon:**", f"![Icon](<{raw(manifest['iconUrl'])}>)", ""])
    for index, url in enumerate(manifest.get("screenshots", []), 1):
        lines.extend([f"![Screenshot {index}](<{raw(url)}>)", ""])
    if len(lines) > 2:
        lines.append("These are normalized catalog bytes pinned to the automation commit.")
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
