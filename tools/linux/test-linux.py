#!/usr/bin/env python3
"""Asset-free Linux runtime checks. Runs on the host as well as in the build container."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/linux"


def run(*args, cwd=ROOT, env=None, check=True):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=300, check=False)
    if check and result.returncode:
        raise AssertionError(f"{args[0]} exited {result.returncode}:\n{result.stdout}")
    return result


class LinuxRuntime(unittest.TestCase):
    def test_elf_and_dependencies(self):
        binaries = []
        for path in OUT.iterdir():
            if path.is_file():
                with path.open("rb") as stream:
                    if stream.read(4) == b"\x7fELF":
                        binaries.append(path)
        self.assertGreaterEqual(len(binaries), 18)
        for binary in binaries:
            with self.subTest(binary=binary.name):
                with binary.open("rb") as stream:
                    data = stream.read(20)
                self.assertEqual(data[4], 2, "expected 64-bit ELF")
                self.assertEqual(int.from_bytes(data[18:20], "little"), 62, "expected x86_64")
                self.assertNotIn("not found", run("ldd", binary).stdout)

    def test_network_gates(self):
        for name in ("lockstep", "netloop", "tunnel", "beacon", "lobby", "roomcode"):
            with self.subTest(gate=name):
                result = run(OUT / f"gate_{name}")
                self.assertEqual(result.returncode, 0)

    def test_options_layout(self):
        pack = ROOT / "game/dossidebar.pack"
        if not pack.is_file():
            pack = OUT / "dossidebar.pack"
        if not pack.is_file():
            self.skipTest("gate_optlayout requires the original GRAD6FNT from dossidebar.pack")
        run(OUT / "gate_optlayout", pack)

    def test_linux_release_and_module_catalogs(self):
        self.assertIn("LINUX-PLATFORM|PASS", run(OUT / "linux_platform_test").stdout)

    def test_library_discovery(self):
        with tempfile.TemporaryDirectory(prefix="opencnc3d foreign cwd ") as work:
            work = Path(work)
            self.assertIn("dlopen + symbol resolution: OK", run(OUT / "cncbrain", cwd=work).stdout)
            # The binary must find its own library even from an unrelated directory.
            found = run(OUT / "linux_platform_test", "discover", cwd=work).stdout.strip()
            self.assertEqual(Path(found).resolve(), OUT / "TiberianDawn.so")
            # A bare explicit path must use the cwd, rather than ELF's library search path.
            shutil.copy2(OUT / "TiberianDawnXL.so", work / "TiberianDawn.so")
            found = run(OUT / "linux_platform_test", "discover", "TiberianDawn.so", cwd=work).stdout.strip()
            self.assertEqual(found, "./TiberianDawn.so")
            self.assertEqual(run(OUT / "linux_platform_test", "discover", cwd=work).stdout.strip(), "./TiberianDawn.so")
            # Relocating a built folder into a path containing spaces also works.
            shutil.copy2(OUT / "linux_platform_test", work / "linux_platform_test")
            self.assertEqual(Path(run(work / "linux_platform_test", "discover", cwd="/tmp").stdout.strip()), work / "TiberianDawn.so")

    def test_module_presence(self):
        with tempfile.TemporaryDirectory(prefix="opencnc3d module ") as work:
            work = Path(work)
            def presence():
                return run(OUT / "linux_platform_test", "module", work).stdout.strip()
            self.assertEqual(presence(), "td=0|ra=0")
            (work / "opencnc3d").touch()
            (work / "TiberianDawn.dylib").touch()
            self.assertEqual(presence(), "td=0|ra=0")
            (work / "TiberianDawn.so").touch()
            self.assertEqual(presence(), "td=1|ra=0")
            for name in ("opencnc3d", "RedAlert.so", "dosmenu.pack", "SCG01EA.pack", "audio/SOUNDS.MIX",
                         "audio/SPEECH.MIX", "audio/RA_LOCAL.MIX", "missions/SCG01EA.INI",
                         "missions/TUTORIAL.INI", "missions/RULES.INI"):
                path = work / "ra3d" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            self.assertEqual(presence(), "td=1|ra=1")
            (work / "ra3d/RedAlert.so").unlink()
            (work / "ra3d/RedAlert.dylib").touch()
            self.assertEqual(presence(), "td=1|ra=0")

    def test_red_alert_bootstrap(self):
        result = run("python3", ROOT / "tools/ra3d/run-bootstrap-gate.py",
                     "--host", OUT / "ra_bootstrap", "--brain", OUT / "RedAlert.so",
                     "--fixture", ROOT / "brain/tests/ra3d", "--report", OUT / "ra-bootstrap-linux.txt")
        self.assertIn("passed twice", result.stdout)

    def test_launcher_argument_forwarding(self):
        with tempfile.TemporaryDirectory(prefix="opencnc3d forwarding ") as work:
            env = dict(os.environ, TMPDIR=work)
            result = run("sh", ROOT / "tools/launcher/forward-check.sh", OUT / "opencnc3d-launcher", env=env)
            self.assertNotIn("FWD|FAIL", result.stdout)

    def test_missing_data_startup(self):
        with tempfile.TemporaryDirectory(prefix="opencnc3d missing data ") as work:
            env = dict(os.environ, OPENCNC3D_BACKGROUND="1", SDL_VIDEODRIVER="dummy",
                       SDL_AUDIODRIVER="dummy", XDG_DATA_HOME=work)
            isolated = Path(work) / "opencnc3d-launcher"
            shutil.copy2(OUT / "opencnc3d-launcher", isolated)
            result = run(isolated, "--dir", work, env=env, cwd=work, check=False)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("dosmenu.pack", result.stdout)
            self.assertRegex(result.stdout, "not installed|could not find its game files")
            result = run(OUT / "cnc_eyes", "--help", cwd=work, check=False)
            self.assertEqual(result.returncode, 2)  # Existing usage exit status.
            self.assertIn("usage:", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
