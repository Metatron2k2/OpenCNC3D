#!/usr/bin/env python3
"""Prepare a source-only Flatpak build input from this working tree, without game data."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import tarfile
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/flatpak"
APP_ID = "io.github.Metatron2k2.OpenCNC3D"
CODE_SUFFIXES = {".c", ".cpp", ".h", ".hpp", ".inc", ".cmake", ".in", ".sh", ".py", ".json", ".txt"}
SOURCE_DIRS = {"app", "audio", "brain", "compat", "game", "input", "launcher", "menu", "net", "sidebar", "tier1", "tools", "video", "art", "packaging"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    version = (ROOT / "VERSION").read_text().strip()
    build_id = subprocess.check_output(["sh", str(ROOT / "tools/version.sh")], text=True).strip()
    stamp = OUT / "opencnc3d_build.h"
    subprocess.run(["sh", str(ROOT / "tools/version.sh"), "--developer-header", str(stamp)], check=True)
    epoch = int(subprocess.check_output(["git", "-C", str(ROOT), "show", "-s", "--format=%ct", "HEAD"], text=True))
    raw = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    names = sorted(set(raw.decode().split("\0")) - {""})
    generated = {"game/opencnc3d_build.h": stamp.read_bytes()}
    xml = (ROOT / f"packaging/flatpak/{APP_ID}.metainfo.xml.in").read_text()
    generated[f"packaging/flatpak/{APP_ID}.metainfo.xml"] = xml.replace("@VERSION@", version).replace(
        "@DATE@", datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()).encode()
    # Reuse every PNG already embedded in the project's existing multi-size icon.
    icon = (ROOT / "tools/launchers/opencnc3d.ico").read_bytes()
    count = struct.unpack_from("<H", icon, 4)[0]
    for i in range(count):
        width, _, _, _, _, _, length, offset = struct.unpack_from("<BBBBHHII", icon, 6 + i * 16)
        png = icon[offset:offset + length]
        if png.startswith(b"\x89PNG\r\n\x1a\n"):
            generated[f"packaging/flatpak/icons/{width or 256}.png"] = png

    def add_bytes(tar, name, data, mode=0o644):
        info = tarfile.TarInfo(name)
        info.size = len(data); info.mode = mode; info.mtime = epoch
        tar.addfile(info, io.BytesIO(data))

    source = OUT / "opencnc3d-source.tar.gz"
    with source.open("wb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as tar:
            for name in names:
                path = ROOT / name
                if name in generated or not path.is_file() or path.is_symlink():
                    continue
                if name not in {"VERSION", "LICENSE", "NOTICE.md", "README.md"}:
                    if path.relative_to(ROOT).parts[0] not in SOURCE_DIRS:
                        continue
                    if path.suffix not in CODE_SUFFIXES and path.name != "CMakeLists.txt" and not name.endswith(".desktop"):
                        continue
                    if name.startswith("packaging/flatpak/") and name.endswith(".json.in"):
                        continue
                add_bytes(tar, name, path.read_bytes(), 0o755 if path.stat().st_mode & 0o111 else 0o644)
            for name, data in sorted(generated.items()):
                add_bytes(tar, name, data)
    with source.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = (ROOT / f"packaging/flatpak/{APP_ID}.json.in").read_text()
    manifest = manifest.replace("@SOURCE_SHA256@", sha).replace("@BUILD_ID@", build_id)
    json.loads(manifest)
    (OUT / f"{APP_ID}.json").write_text(manifest)
    # Host-side metadata validation uses the exact file installed into the package.
    (OUT / f"{APP_ID}.metainfo.xml").write_bytes(generated[f"packaging/flatpak/{APP_ID}.metainfo.xml"])
    print(f"Source-only build input: {source} ({source.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
