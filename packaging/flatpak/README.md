# OpenCNC3D Flatpak

The local Flatpak ID is `io.github.Metatron2k2.OpenCNC3D`. The package includes
the launcher, game, standalone renderer, three engine libraries, connectivity and
graphics tools, the existing multi-size application icon, a Games menu entry,
and AppStream metadata. Its menu also has a Play action for an installed game.

Build on an x86_64 Linux host with Flatpak, flatpak-builder, Python 3.11+,
appstreamcli, and desktop-file-validate installed:

```sh
tools/linux/make-flatpak.sh
```

The driver installs the Freedesktop 26.08 SDK and LLVM 22 extension in the user's
Flatpak installation, stages a source-only archive from the current working
tree, and runs the native Linux build recipe inside the SDK. It produces a local
OSTree repository and `build/flatpak/OpenCNC3D-<version>-x86_64.flatpak`.
An accompanying `.sha256` file records the bundle checksum.
The source archive includes working-tree changes and a generated developer build
stamp. Downloaded game data, host binaries, and build caches are excluded.

```sh
flatpak install --user build/flatpak/OpenCNC3D-0.9.0-x86_64.flatpak
flatpak run io.github.Metatron2k2.OpenCNC3D
```

Search for OpenCNC3D in the desktop's application menu after installation. The
launcher offers the game-data download on first use. Movies and music are optional.
The bundle contains no game data and needs the Freedesktop 26.08 runtime; the
runtime repository is recorded in the bundle for installation.

The package keeps executable code in read-only `/app/lib/opencnc3d`. The wrapper
places managed links in its writable game folder so the existing downloader and
game retain their shared-folder layout. Game assets persist on the host at:

```text
~/.var/app/io.github.Metatron2k2.OpenCNC3D/data/OpenCNC3D/game/
```

SDL saves and settings also stay in the app's private data tree. Updating the
Flatpak changes the managed runtime and retains those files. The sandbox permits
networking, Wayland/X11 fallback, audio, and GPU access. It requires no general
home-directory or host-filesystem access.

This creates a local installable bundle; it does not publish to Flathub.
