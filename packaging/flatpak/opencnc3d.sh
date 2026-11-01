#!/bin/sh
# Flatpak owns /app; downloaded assets and settings live in persistent app data.
set -eu
game_dir="${XDG_DATA_HOME:?}/OpenCNC3D/game"
runtime_dir=/app/lib/opencnc3d
if [ -L "$game_dir" ]; then
    echo 'The OpenCNC3D data folder must be a real directory.' >&2
    exit 1
fi
mkdir -p "$game_dir"
for runtime_file in opencnc3d opencnc3d-launcher cnc_eyes netcheck gl_smoke TiberianDawn.so RedAlert.so TiberianDawnXL.so; do
    ln -sfn "$runtime_dir/$runtime_file" "$game_dir/$runtime_file"
done
# Let both desktop backends associate SDL windows with the exported menu icon.
export SDL_VIDEO_X11_WMCLASS=io.github.Metatron2k2.OpenCNC3D
export SDL_VIDEO_WAYLAND_WMCLASS=io.github.Metatron2k2.OpenCNC3D
export SDL_APP_ID=io.github.Metatron2k2.OpenCNC3D
cd "$game_dir"
# The desktop Play action opens first-run Setup while the data is still absent.
if [ "${1:-}" = --play ] && { [ ! -s dosmenu.pack ] || [ ! -s SCG01EA.pack ] || [ ! -s CONQUER.MIX ]; }; then
    shift
fi
exec "$runtime_dir/opencnc3d-launcher" --dir "$game_dir" "$@"
