#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
APP_ID=io.github.Metatron2k2.OpenCNC3D
OUT="$ROOT/build/flatpak"
for tool in flatpak flatpak-builder python3 appstreamcli desktop-file-validate; do
    command -v "$tool" >/dev/null || { echo "Missing Flatpak build prerequisite: $tool" >&2; exit 1; }
done
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user --assumeyes --noninteractive flathub org.freedesktop.Sdk//26.08 org.freedesktop.Sdk.Extension.llvm22//26.08
python3 packaging/flatpak/prepare-source.py
desktop-file-validate "packaging/flatpak/$APP_ID.desktop"
appstreamcli validate --no-net "$OUT/$APP_ID.metainfo.xml"
flatpak-builder --user --assumeyes --install-deps-from=flathub --sandbox \
    --force-clean --state-dir="$OUT/builder-state" --repo="$OUT/repo" \
    "$OUT/app" "$OUT/$APP_ID.json" 2>&1 | tee "$OUT/build.log"
version=$(tr -d '[:space:]' < VERSION)
bundle="$OUT/OpenCNC3D-$version-$(flatpak --default-arch).flatpak"
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
    "$OUT/repo" "$bundle" "$APP_ID" stable
(cd "$OUT" && sha256sum "$(basename "$bundle")" > "$(basename "$bundle").sha256")
echo "Built $bundle"
echo "Install: flatpak install --user $bundle"
echo "Run: flatpak run $APP_ID"
