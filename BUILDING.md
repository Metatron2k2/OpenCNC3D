# Building OpenCNC3D

This repository is source. It contains no game data, so a fresh clone will compile but
will not run until you supply two things you already own.

## 1. What you have to bring

| | Where it goes | Why |
|---|---|---|
| A dump of your **European** C&C Nintendo 64 cartridge | `data/rom/cnc_eu.z64` | All 3D: models, textures, terrain, the camera |
| Your 1995 **MS-DOS** Command & Conquer discs | `data/dosdata/` | All 2D and all audio: sidebar, sprites, music, speech, movies |

Each of those directories has a README saying exactly which files are expected and,
for the movies, how to reconstruct the set. Read those first.

The EU cartridge specifically: it carries the Covert Operations missions, and every
offset in `docs/re-findings.md` is quoted against it. A US dump will not line up.

## 2. Prerequisites

**Linux (x86_64)**: Clang, CMake 3.25+, Ninja, pkg-config, Python 3, and development
packages for SDL2 (SDL2 or sdl2-compat), desktop OpenGL, libcurl, and zlib.
On Bazzite/Fedora Atomic, the rootless Fedora 44 Toolbox build installs these
inside a container without layering packages onto the host:

```sh
tools/linux/build-linux.sh --container
```

The container is named `opencnc3d-build`; `OPENCNC3D_LINUX_CONTAINER` overrides
the name. Subsequent runs reuse it. On a configured Linux development system,
run `tools/linux/build-linux.sh` directly. Clang is required; `CC`, `CXX`,
`CFLAGS`, `CXXFLAGS`, `LDFLAGS`, and `OPENCNC3D_JOBS` can customize the build
(parallel brain compilation is capped at eight jobs).

Linux outputs are in `build/linux/`: `opencnc3d`, `opencnc3d-launcher`,
`cnc_eyes`, `netcheck`, the headless probes and gates, and `TiberianDawn.so`,
`RedAlert.so`, and `TiberianDawnXL.so`. All use native system runtime libraries.
The driver compiles source only: it uses committed generated asset headers and
does not invoke the incomplete asset baker or require ROM/disc data. Compilation
warnings and diagnostics are retained in `build/linux/build.log`.

On first launch, `build/linux/opencnc3d-launcher` offers to download the missing
menu art, then opens Setup to download game data and choose optional movies/music.
The data release defaults to the version of the local build. Linux keeps its
compiled executables and libraries; only shared runtime data is installed from
the corresponding Windows package, verified against its release checksum.
Downloads resume after an interruption, and failed extraction rolls back.
The game-data download is approximately 2.1 GB for v0.9.0.

For installation from a terminal, with movies and music left out:

```sh
build/linux/opencnc3d-launcher --install-game --media none --dir "$(pwd)/build/linux"
```

`--fetch-menu-art --dir /path/to/folder` fetches only the small menu bootstrap.
An asset install retains the native build identity in `version`, with its data
release recorded separately as `data_version`. A launcher-only rebuild is available
as `tools/linux/build-linux.sh --container --launcher-only`.

Run asset-free checks on the host after building:

```sh
python3 tools/linux/test-linux.py
python3 tools/linux/test-assets.py # disposable local server; no game downloads
build/linux/gl_smoke             # the current desktop's SDL/OpenGL backend
SDL_VIDEODRIVER=x11 build/linux/gl_smoke  # X11 / XWayland
```

The options-layout gate is compiled, but its runtime check needs the original
`GRAD6FNT` in `game/dossidebar.pack`; the test suite explicitly skips it when
that data is absent. The networking, loader, launcher and synthetic engine
checks need no game assets.

For a headless software-rendered graphics check in the build container:

```sh
toolbox run --container opencnc3d-build xvfb-run -a env SDL_VIDEODRIVER=x11 LIBGL_ALWAYS_SOFTWARE=1 build/linux/gl_smoke
```

To use an existing baked play folder instead, copy `opencnc3d`, `opencnc3d-launcher`,
`cnc_eyes` and `TiberianDawn.so` into the existing play folder and run
`./opencnc3d-launcher` there, or use `opencnc3d-launcher --dir /path/to/play-folder`.
The Red Alert module uses its own `ra3d/RedAlert.so`; placing that library alone
does not install the module's required game data. `cnc_eyes --dylib /path/to/library.so`
selects an explicit engine. `cncbrain` accepts `OPENCNC3D_BRAIN=/path/to/library.so`
and otherwise finds the Linux library beside itself.
Linux binary update checks select Linux packages; until those are published, the
launcher reports that no Linux build is available. Game-data setup works through
the version-matched shared-data download described above. No portable release
package is created.

For a Linux Flatpak with an application-menu entry, icons, software-center metadata,
and persistent game-data downloads, run `tools/linux/make-flatpak.sh`. See
[`packaging/flatpak/README.md`](packaging/flatpak/README.md) for build prerequisites,
installation and storage locations. The bundle is produced under `build/flatpak/`.

**macOS**: Xcode command line tools, cmake and ninja, and Python 3 for the asset tools.
The Mac build is universal (Apple Silicon and Intel in one package, built on either), so
it links an SDL built for both rather than Homebrew's, which carries only the build
machine's CPU:

```
xcode-select --install
brew install cmake ninja
tools/mac/setup-sdl-mac.sh            # once: universal SDL3 + sdl2-compat, into ~/.opencnc3d-macsdk
```

The build scripts find that SDL by themselves. `OPENCNC3D_MAC_ARCHS=arm64` (or `x86_64`)
makes a quicker one-CPU development build; the play folder check then says it is not
universal, so it cannot be shipped by mistake.

**Windows**: the shipped binary is 32-bit, built with mingw-w64 i686. This retains the
existing Windows release architecture and keeps the Win98 target reachable; native Linux
uses 64-bit libraries with pointer-width-safe placement decoding.
The scripts below drive the Windows toolchain from a Unix shell,
which is also how CI builds it.

```
tools/win/setup-toolchain.sh          # once: fetches the two SDKs mingw-w64 lacks, into ~/.opencnc3d-winsdk
```

**All platforms** need Python 3 with `pillow` and `numpy` for the extraction and baking tools.

## 3. The brain

The game logic is EA's 2020 GPL release of Tiberian Dawn, unforked, with four additive
portability patches. It builds as a shared library the renderer loads at runtime.

```
tools/mac/build-brain-mac.sh          # -> TiberianDawn.dylib
tools/win/build-win.sh                # builds TiberianDawn.dll as part of the Windows build
```

`tools/check-brain-checkout.sh` verifies the checkout and the patches match byte for byte
before anything compiles.

The desktop game probes the working tree and the folder beside its executable for
the platform's library. Use `--dylib /path/to/library` to select it explicitly.
The headless `cncbrain` probe uses `OPENCNC3D_BRAIN=/path/to/library`.

## 4. Extracting and baking the data

With the cartridge in place, `tools/romdump/` decodes the archive and `tools/bakery/`
turns the result into the packs the renderer loads. **One step of that chain is missing
from this snapshot:** the PK4 pack baker is compiled bytecode whose source was lost and
is not published, so `tools/bakery/bake5.py` stops at its first import. See
`tools/bakery/README.md` for exactly what still runs and what does not. The `game/bake_*.py` scripts each own
one slice: sidebar, infantry, tiberium, campaign, effects, verdict screens.

These are the least documented part of the project and they were built to be run by
someone who already knew the pipeline. Start from `docs/re-findings.md` for the formats
and read the script you are about to run; each says at the top what it consumes and
produces.

Two environment variables are honoured throughout:

```
OPENCNC3D_ROOT      the repository root, when a tool is run from outside the tree
OPENCNC3D_ROM       the cartridge, when it is not at data/rom/cnc_eu.z64
```

## 5. The build

```
game/make-build.sh                    # macOS: renderer + app, into a playable folder
tools/linux/build-linux.sh --container # Linux: native binaries; game data is separate
tools/win/make-build-win.sh           # Windows: a zip of the game, without the movies and music
tools/win/build-win.sh --no-brain     # skip the DLL, which changes rarely
```

`game/make-build.sh` takes the destination as its first argument and reads the baked data
from `OPENCNC3D_DATA`. The Windows zip expands to `OpenCNC3D-windows-<commit>/`, whose one
file to run is `OpenCNC3D.exe`, the launcher, and needs nothing installed on the target
machine.

The play folder `game/make-build.sh` makes keeps the 1995 movies and music, because the
gates that play a movie or measure the score run in it. The packages do not carry them:
`tools/mac/make-package-mac.sh` and the Windows packager leave out every path in
`tools/media/media-paths.txt`. A player gets them through the Windows installer or the
launcher's Setup screen, downloaded from disc images on archive.org: the movies from the
1995 Gold discs (EA's 2007 freeware release), the music from the Covert Operations disc
image. The game plays without them.

The SDL libraries are copied into the macOS build by `tools/bundle-sdl.sh`, which is
called with no file list on purpose so it scans the whole output folder. Skipping that
step produces a build that runs only on the machine that made it.

## 6. Two render tiers

Tier 2 is the modern desktop build, Linux, Windows and macOS, and may use shaders. Tier 1 is
the constrained one kept reachable as a stretch goal: Windows 98 on a 3dfx Voodoo 2
through Glide, fixed function, no shaders, no render targets, 640x480, 16-bit colour.

`docs/tier1-gap.md` is the contract between them. Any feature that cannot run on Tier 1
is listed there with its fallback. A Tier 2 feature that is not in that file is a bug,
because it turns a known list of compromises into a surprise.

The desktop presentation chain (bloom, ambient occlusion, sun shadows, colour grade, CRT)
is off unless asked for, so the default build draws the same picture on both tiers.

## 7. If it does not run

- **"Could not find the game"**: the executable resolves its own data directory relative
  to itself. It is looking for the baked packs, not the source tree.
- **Missing movies or music**: no package carries them. Tick them in Setup, or in the
  launcher's Settings (the gear button), and the launcher downloads them. In a development
  tree, the campaign names 72 `.VQA` files and they are split across both 1995 discs; see
  `data/dosdata/README.md`.
- **A tool cannot find the ROM**: set `OPENCNC3D_ROM`. Nothing hardcodes a path any more, and
  anything that appears to is a bug worth reporting.
