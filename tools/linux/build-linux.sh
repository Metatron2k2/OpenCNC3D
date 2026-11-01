#!/usr/bin/env bash
# Native desktop build; no ROM, baked packs, or asset-generation tools required.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"

if [[ ${1:-} == --container ]]; then
    shift
    container=${OPENCNC3D_LINUX_CONTAINER:-opencnc3d-build}
    if ! podman container exists "$container"; then
        toolbox create --assumeyes --release 44 "$container"
    fi
    # Installation occurs only inside the container. Toolbox shares this checkout.
    toolbox run --container "$container" sudo dnf install -y \
        clang gcc-c++ cmake ninja-build pkgconf-pkg-config sdl2-compat-devel \
        libglvnd-devel libcurl-devel zlib-devel python3 git diffutils perl file \
        binutils xorg-x11-server-Xvfb mesa-dri-drivers xorg-x11-xauth
    container_env=()
    for name in CC CXX CFLAGS CXXFLAGS LDFLAGS OPENCNC3D_JOBS OPENCNC3D_COOKED OPENCNC3D_SITE; do
        [[ ! -v $name ]] || container_env+=("$name=${!name}")
    done
    exec toolbox run --container "$container" env "${container_env[@]}" bash "$ROOT/tools/linux/build-linux.sh" "$@"
fi
launcher_only=0
if [[ ${1:-} == --launcher-only ]]; then launcher_only=1; shift; fi
if [[ $# != 0 ]]; then
    echo "usage: $0 [--container] [--launcher-only]" >&2
    exit 2
fi
[[ $(uname -s) == Linux ]] || { echo 'This build requires Linux.' >&2; exit 1; }
CC=${CC:-clang}
CXX=${CXX:-clang++}
for tool in "$CC" "$CXX" cmake ninja pkg-config python3; do
    command -v "$tool" >/dev/null || { echo "Missing $tool; use --container or install the Linux build dependencies." >&2; exit 1; }
done
"$CXX" --version | head -1 | grep -qi clang || { echo 'The Linux build requires Clang C++.' >&2; exit 1; }
pkg-config --exists sdl2 gl libcurl zlib || {
    echo 'Missing SDL2/OpenGL/curl/zlib development packages; use --container.' >&2; exit 1;
}

OUT="$ROOT/build/linux"
OBJ="$OUT/obj"
mkdir -p "$OBJ/launcher"
if (( launcher_only )); then
    exec > >(tee "$OUT/launcher-build.log") 2>&1
else
    exec > >(tee "$OUT/build.log") 2>&1
fi
sh tools/win/check-sources.sh
if [[ ${OPENCNC3D_SKIP_VERSION_HEADER:-0} != 1 || ! -f game/opencnc3d_build.h ]]; then
    sh tools/version.sh --header game/opencnc3d_build.h
fi
sh tools/launcher/make-config.sh
# These lists describe portable sources, despite the historical WIN_ names.
source tools/win/sources.sh
source launcher/sources.sh
read -r -a DEPCFLAGS <<< "$(pkg-config --cflags sdl2 gl libcurl zlib)"
read -r -a DEPLIBS <<< "$(pkg-config --libs sdl2 gl libcurl zlib)"
read -r -a EXTRA_CFLAGS <<< "${CFLAGS:-}"
read -r -a EXTRA_CXXFLAGS <<< "${CXXFLAGS:-}"
read -r -a EXTRA_LDFLAGS <<< "${LDFLAGS:-}"
FLAGS=(-O2 -g -Wall -DGL_GLEXT_PROTOTYPES=1)
[[ ${OPENCNC3D_COOKED:-0} == 0 ]] || FLAGS+=(-DOPENCNC3D_COOKED=1)
INC=(-I"$ROOT/game" -I"$ROOT/menu" -I"$ROOT/video" -I"$ROOT/audio" -I"$ROOT/launcher"
     -I"$ROOT/brain/vanilla/tiberiandawn" "${DEPCFLAGS[@]}")
CPPFLAGS=(-std=c++14 -fms-extensions -fdeclspec '-D__int64=long long'
          -include "$ROOT/game/opencnc3d_build.h")
objects=()
compile_c() {
    local dialect=$1 source object
    shift
    for source in "$@"; do
        object="$OBJ/$(basename "${source%.c}").o"
        "$CC" "-std=$dialect" "${FLAGS[@]}" "${EXTRA_CFLAGS[@]}" "${INC[@]}" -c "$ROOT/$source" -o "$object"
        objects+=("$object")
    done
}
if (( !launcher_only )); then
echo '== portable C sources'
for source in $WIN_AUDIO_C; do
    [[ $source == audio/audio_sdl.c ]] || compile_c c89 "$source"
done
compile_c c89 $WIN_GAME_C net/lockstep.c
compile_c gnu99 audio/audio_sdl.c $WIN_MENU_C $WIN_VIDEO_C $WIN_APP_C $WIN_HTTP_C
for source in $WIN_NET_C; do
    [[ $source == net/lockstep.c ]] || compile_c gnu89 "$source"
done
echo '== desktop renderer and application'
"$CXX" "${FLAGS[@]}" "${EXTRA_CXXFLAGS[@]}" "${INC[@]}" -std=c++14 -c "$WIN_MENU_CPP" -o "$OBJ/enhanced_menu.o"
objects+=("$OBJ/enhanced_menu.o")
"$CXX" "${FLAGS[@]}" "${EXTRA_CXXFLAGS[@]}" "${INC[@]}" "${CPPFLAGS[@]}" -DOPENCNC3D_NO_MAIN -c "$WIN_EYES_CPP" -o "$OBJ/cnc_eyes_lib.o"
"$CXX" "${FLAGS[@]}" "${EXTRA_CXXFLAGS[@]}" "${INC[@]}" "${CPPFLAGS[@]}" -c "$WIN_EYES_CPP" -o "$OBJ/cnc_eyes_main.o"
"$CXX" "${FLAGS[@]}" "${EXTRA_CXXFLAGS[@]}" "${INC[@]}" "${CPPFLAGS[@]}" -c "$WIN_APP_CPP" -o "$OBJ/opencnc3d.o"
"$CXX" "${EXTRA_LDFLAGS[@]}" -o "$OUT/cnc_eyes" "$OBJ/cnc_eyes_main.o" "${objects[@]}" "${DEPLIBS[@]}" -ldl -lm
"$CXX" "${EXTRA_LDFLAGS[@]}" -o "$OUT/opencnc3d" "$OBJ/opencnc3d.o" "$OBJ/cnc_eyes_lib.o" "${objects[@]}" "${DEPLIBS[@]}" -ldl -lm
fi

echo '== launcher'
launcher_objects=()
for source in $LAUNCHER_SOURCES; do
    object="$OBJ/launcher/$(basename "${source%.c}").o"
    "$CC" -std=gnu99 "${FLAGS[@]}" "${EXTRA_CFLAGS[@]}" "${INC[@]}" -c "$ROOT/launcher/$source" -o "$object"
    launcher_objects+=("$object")
done
"$CC" "${EXTRA_LDFLAGS[@]}" -o "$OUT/opencnc3d-launcher" "${launcher_objects[@]}" "${DEPLIBS[@]}" -lm
test_objects=()
for object in "${launcher_objects[@]}"; do
    case $(basename "$object") in launcher.o|lupdate.o) ;; *) test_objects+=("$object") ;; esac
done
"$CC" -std=gnu99 "${FLAGS[@]}" "${INC[@]}" -o "$OUT/linux_platform_test" \
    tools/linux/platform-test.c "${test_objects[@]}" "${DEPLIBS[@]}" -ldl -lm
"$CC" -std=gnu99 "${FLAGS[@]}" "${INC[@]}" -o "$OUT/linux_assets_test" \
    tools/linux/assets-test.c "${test_objects[@]}" "${DEPLIBS[@]}" -ldl -lm
if (( launcher_only )); then
    echo "Built native Linux launcher and installer tests in $OUT."
    exit 0
fi

echo '== connectivity tools and asset-free gates'
gate() { local name=$1; shift; "$CC" -std=gnu99 -O2 -g -Wall "${INC[@]}" -o "$OUT/$name" "$@" -lz -ldl -lm; }
gate gate_optlayout game/gate_optlayout.c "$OBJ/dosopt.o" "$OBJ/dosbar.o"
gate gate_lockstep net/gate_lockstep.c "$OBJ/lockstep.o"
gate gate_netloop net/gate_netloop.c "$OBJ/lockstep.o" "$OBJ/net_udp.o"
gate gate_tunnel net/gate_tunnel.c "$OBJ/net_udp.o"
gate gate_beacon net/gate_beacon.c "$OBJ/netbeacon.o" "$OBJ/net_udp.o"
gate gate_lobby net/gate_lobby.c "$OBJ/netmatch.o" "$OBJ/lockstep.o" "$OBJ/net_udp.o" "$OBJ/roomcode.o"
gate gate_roomcode net/gate_roomcode.c "$OBJ/roomcode.o"
gate netcheck net/netcheck.c "$OBJ/lockstep.o" "$OBJ/net_udp.o" "$OBJ/roomcode.o"
gate cncbrain brain/host/cnc_host.c
gate cnc_twobrain brain/host/cnc_twobrain.c
gate ra_bootstrap brain/host/ra_bootstrap.c
gate ra_twobrain brain/host/ra_twobrain.c
"$CC" -std=c99 -O2 -g "${INC[@]}" -o "$OUT/gl_smoke" tools/linux/gl-smoke.c "${DEPLIBS[@]}"

jobs=${OPENCNC3D_JOBS:-$(nproc)}
(( jobs <= 8 )) || jobs=8
echo "== Tiberian Dawn and Red Alert brains ($jobs jobs)"
cmake -S brain/vanilla -B "$OUT/brain" -G Ninja \
    -DCMAKE_C_COMPILER="$CC" -DCMAKE_CXX_COMPILER="$CXX" \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DBUILD_REMASTERTD=ON -DBUILD_REMASTERRA=ON -DBUILD_VANILLATD=OFF \
    -DBUILD_VANILLARA=OFF -DSDL2=OFF -DOPENAL=OFF -DNETWORKING=OFF
cmake --build "$OUT/brain" --target TiberianDawn RedAlert --parallel "$jobs"
cp "$OUT/brain/tiberiandawn/TiberianDawn.so" "$OUT/brain/redalert/RedAlert.so" "$OUT/"
echo '== XL brain'
cmake -S brain/xl -B "$OUT/brain-xl" -G Ninja \
    -DCMAKE_C_COMPILER="$CC" -DCMAKE_CXX_COMPILER="$CXX" \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_POSITION_INDEPENDENT_CODE=ON
cmake --build "$OUT/brain-xl" --target TiberianDawnXL --parallel "$jobs"
cp "$OUT/brain-xl/tiberiandawn/TiberianDawnXL.so" "$OUT/"
echo "Built native Linux desktop binaries in $OUT (game data supplied separately)."
