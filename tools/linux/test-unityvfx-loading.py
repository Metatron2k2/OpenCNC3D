#!/usr/bin/env python3
"""Run the production seed/mesh decoders with checked vectors and synthetic files."""
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "game/unityvfx_mod.h").read_text()


def function(name):
    match = re.search(r"^static [^\n]+ " + name + r"\(", SOURCE, re.MULTILINE)
    assert match, name
    end = SOURCE.index("\n}", match.start()) + 2
    return SOURCE[match.start():end]


def main():
    seed_struct = SOURCE[SOURCE.index("struct UvfxSeed {"):SOURCE.index("\n};", SOURCE.index("struct UvfxSeed {")) + 3]
    record_size = int(re.search(r"UVR_N = (\d+)", SOURCE)[1])
    program = """#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <zlib.h>
""" + seed_struct + f"\nenum {{ UVR_N = {record_size} }};\n" + """
struct UvfxPack { int nsys = 1, frames = 2; };
struct UvfxMesh { std::vector<float> v; std::vector<unsigned> idx; };
"""
    for name in ("uvfx_read_file", "uvfx_u32", "uvfx_inflate", "uvfx_load_seed", "uvfx_load_mesh"):
        program += function(name) + "\n"
    program += """
int main(int argc, char **argv) {
    if (argc != 4) return 2;
    UvfxPack pack; UvfxSeed seed; UvfxMesh mesh;
    bool ok;
    if (!strcmp(argv[1], "mesh")) ok = uvfx_load_mesh(argv[2], mesh);
    else {
        ok = uvfx_load_seed(argv[2], seed, pack);
        if (ok && seed.off.size() != 2) return 3;
        if (ok && !strcmp(argv[1], "mixed") && (seed.recs.size() != UVR_N || seed.off[1] != 1 || seed.cnt[1] != 0)) return 4;
    }
    return ok == (argv[3][0] == '1') ? 0 : 5;
}
"""
    with tempfile.TemporaryDirectory(prefix="opencnc3d checked vectors ") as work:
        work = Path(work)
        (work / "test.cpp").write_text(program)
        binary = work / "test"
        subprocess.run([os.environ.get("CXX", "c++"), "-std=c++14", "-O1", "-D_GLIBCXX_ASSERTIONS",
                        str(work / "test.cpp"), "-lz", "-o", str(binary)], check=True)
        def seed(name, records, expected=True, truncated=False):
            raw = b"C3VX" + struct.pack("<5I", 1, 1, 2, 30, record_size)
            for n in records:
                raw += struct.pack("<II", 1, n) + b"\0" * (n * record_size * 4)
            if truncated: raw = raw[:-4]
            path = work / (name + ".c3vz")
            path.write_bytes(b"C3VZ" + struct.pack("<I", len(raw)) + zlib.compress(raw))
            subprocess.run([str(binary), name, str(path), str(int(expected))], check=True)
        seed("empty", [0, 0])
        seed("mixed", [1, 0])
        seed("truncated", [0, 0], expected=False, truncated=True)
        path = work / "empty.c3vm"
        path.write_bytes(b"C3VM" + struct.pack("<3I", 1, 0, 0))
        subprocess.run([str(binary), "mesh", str(path), "1"], check=True)
    print("UNITYVFX-LOADING|PASS|empty-frames|mixed-frames|truncated-header|empty-mesh|checked-vectors")


if __name__ == "__main__":
    main()
