#!/usr/bin/env python3
"""Canonicalize catalog screenshots into immutable GitHub Pages media."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import ipaddress
import json
import socket
import ssl
import urllib.parse
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_DOWNLOAD = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_OUTPUT = 750 * 1024
MAX_DIMENSIONS = (1280, 720)
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

class NSFWImageError(ValueError):
    pass

_nsfw_classifier = None

def check_nsfw(image: Image.Image) -> None:
    global _nsfw_classifier
    if _nsfw_classifier is None:
        try:
            from transformers import pipeline
            import os
            # Prevent huggingface from spamming stdout
            os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3" 
            _nsfw_classifier = pipeline("image-classification", model="Falconsai/nsfw_image_detection")
        except ImportError:
            return
    if _nsfw_classifier:
        results = _nsfw_classifier(image)
        nsfw_score = next((item["score"] for item in results if item["label"] == "nsfw"), 0.0)
        if nsfw_score > 0.8:
            raise NSFWImageError(f"Image flagged for inappropriate content (NSFW score: {nsfw_score:.2f})")

def public_addresses(hostname: str) -> list[str]:
    try:
        addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    if not addresses:
        return []
    result = []
    for address in addresses:
        value = ipaddress.ip_address(address[4][0])
        if not value.is_global:
            return []
        if str(value) not in result:
            result.append(str(value))
    return result


def safe_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("screenshots must use credential-free HTTPS URLs")
    if not public_addresses(parsed.hostname):
        raise ValueError("screenshot host must resolve exclusively to public addresses")
    return value


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname: str, address: str, port: int):
        super().__init__(hostname, port=port, timeout=30, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def download(url: str) -> bytes:
    current = url
    for _ in range(6):
        parsed = urllib.parse.urlparse(safe_url(current))
        addresses = public_addresses(parsed.hostname or "")
        if not addresses:
            raise ValueError("screenshot host must resolve exclusively to public addresses")
        port = parsed.port or 443
        path = urllib.parse.urlunparse(("", "", parsed.path or "/", parsed.params, parsed.query, ""))
        connection = PinnedHTTPSConnection(parsed.hostname or "", addresses[0], port)
        try:
            connection.request(
                "GET",
                path,
                headers={"User-Agent": "vanahub-media/1", "Accept": "image/png,image/jpeg,image/webp"},
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise ValueError("screenshot redirect omitted its destination")
                current = urllib.parse.urljoin(current, location)
                continue
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"screenshot download returned HTTP {response.status}")
            declared = response.getheader("Content-Length")
            if declared and int(declared) > MAX_DOWNLOAD:
                raise ValueError("screenshot exceeds the 10 MB download limit")
            data = response.read(MAX_DOWNLOAD + 1)
            if len(data) > MAX_DOWNLOAD:
                raise ValueError("screenshot exceeds the 10 MB download limit")
            return data
        finally:
            connection.close()
    raise ValueError("screenshot exceeded the redirect limit")


def canonical_jpeg(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise ValueError("screenshot must decode as PNG, JPEG, or WebP")
            if getattr(source, "n_frames", 1) != 1:
                raise ValueError("animated screenshots are not accepted")
            width, height = source.size
            if width < 1 or height < 1 or width * height > MAX_PIXELS:
                raise ValueError("screenshot dimensions exceed the 40 megapixel limit")
            image = ImageOps.exif_transpose(source)
            image.load()
            image.thumbnail(MAX_DIMENSIONS, Image.Resampling.LANCZOS)
            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, (7, 16, 28))
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise ValueError("screenshot could not be decoded safely") from exc

    check_nsfw(image)

    for quality in (80, 72, 64):
        output = io.BytesIO()
        image.save(
            output,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
            subsampling="4:2:0",
        )
        encoded = output.getvalue()
        if len(encoded) <= MAX_OUTPUT:
            return encoded
    raise ValueError("normalized screenshot exceeds the 750 KB catalog limit")


def is_catalog_media(url: str, public_base: str, package_id: str) -> bool:
    prefix = f"{public_base.rstrip('/')}/{package_id}/"
    if not url.startswith(prefix):
        return False
    name = url.removeprefix(prefix)
    if name == "icon.jpg":
        return True
    return len(name) == 68 and name.endswith(".jpg") and all(character in "0123456789abcdef" for character in name[:-4])


def process(
    manifest: dict,
    media_root: Path,
    public_base: str,
    previous: dict | None = None,
) -> dict:
    package_id = manifest.get("id", "")
    output_directory = media_root / package_id

    icon_url = manifest.get("iconUrl")
    if icon_url and isinstance(icon_url, str):
        if is_catalog_media(icon_url, public_base, package_id) and icon_url.endswith("/icon.jpg"):
            pass
        else:
            output_directory.mkdir(parents=True, exist_ok=True)
            try:
                encoded = canonical_jpeg(download(icon_url))
                destination = output_directory / "icon.jpg"
                destination.write_bytes(encoded)
                manifest["iconUrl"] = f"{public_base.rstrip('/')}/{package_id}/icon.jpg"
            except NSFWImageError as e:
                print(f"Discarding icon for {package_id}: {e}")
                del manifest["iconUrl"]

    screenshots = manifest.get("screenshots")
    if not screenshots:
        return manifest

    previous_screenshots = (previous or {}).get("screenshots", [])
    if previous_screenshots and all(
        isinstance(url, str) and is_catalog_media(url, public_base, package_id)
        for url in previous_screenshots
    ):
        manifest["screenshots"] = previous_screenshots
        return manifest

    output_directory.mkdir(parents=True, exist_ok=True)
    canonical = []
    for url in screenshots:
        if not isinstance(url, str):
            raise ValueError("screenshot entries must be URLs")
        if is_catalog_media(url, public_base, package_id):
            canonical.append(url)
            continue
        try:
            encoded = canonical_jpeg(download(url))
        except NSFWImageError as e:
            print(f"Discarding screenshot for {package_id}: {e}")
            continue
            
        digest = hashlib.sha256(encoded).hexdigest()
        destination = output_directory / f"{digest}.jpg"
        if destination.exists() and destination.read_bytes() != encoded:
            raise ValueError("catalog media hash collision")
        destination.write_bytes(encoded)
        canonical.append(f"{public_base.rstrip('/')}/{package_id}/{digest}.jpg")
    manifest["screenshots"] = list(dict.fromkeys(canonical))
    return manifest


def preview_markdown(manifest: dict) -> str:
    lines = ["## Media preview", ""]
    icon_url = manifest.get("iconUrl")
    if icon_url:
        escaped_icon = str(icon_url).replace(">", "%3E")
        lines.append(f"**Icon:**")
        lines.append(f"![Icon](<{escaped_icon}>)")
        lines.append("")
    
    screenshots = manifest.get("screenshots", [])
    if screenshots:
        for index, url in enumerate(screenshots, 1):
            escaped = str(url).replace(">", "%3E")
            lines.append(f"![Screenshot {index}](<{escaped}>)")
            lines.append("")
    
    if len(lines) > 2:
        lines.append("These images will be validated and normalized before catalog publication.")
        return "\n".join(lines) + "\n"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--public-base", required=True)
    parser.add_argument("--previous-manifest", type=Path)
    parser.add_argument("--preview-output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.input.read_text(encoding="utf-8"))
    if args.preview_output:
        args.preview_output.write_text(preview_markdown(manifest), encoding="utf-8")
    previous = None
    if args.previous_manifest and args.previous_manifest.exists():
        previous = json.loads(args.previous_manifest.read_text(encoding="utf-8"))
    result = process(manifest, args.media_root, args.public_base, previous)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
