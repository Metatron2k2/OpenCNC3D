#!/usr/bin/env python3
"""First-run data installation through the real launcher and a loopback release host."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "build/linux/linux_assets_test"
VERSION = (ROOT / "VERSION").read_text().strip()
REQUIRED = ("dosmenu.pack", "dossidebar.pack", "SCG01EA.pack", "SCB01EA.pack", "CONQUER.MIX",
            "missions/SCG01EA.INI", "missions/SCB01EA.INI")


def archive(entries):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_STORED) as output:
        for name, data in entries.items():
            output.writestr(f"OpenCNC3D-windows-v{VERSION}/{name}", data)
    return memory.getvalue()


class Host(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        state = self.server.state
        url = urlsplit(self.path)
        if url.path == "/api/builds":
            body = json.dumps(state["feed"]).encode()
        elif url.path == "/api/changelog":
            body = b'{"entries":[]}'
        elif url.path == "/api/download":
            asset = int(parse_qs(url.query)["asset"][0])
            body = state["assets"][asset]
            start, end = 0, len(body) - 1
            if self.headers.get("Range"):
                span = self.headers["Range"].removeprefix("bytes=").split("-")
                start = int(span[0]); end = min(int(span[1] or end), end)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(body)}")
            else:
                self.send_response(200)
            state["requests"].append((asset, start))
            body = body[start:end + 1]
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if asset == 1 and state.get("drop_once"):
                state["drop_once"] = False
                self.wfile.write(body[:8192]); self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                self.close_connection = True
            else:
                self.wfile.write(body)
            return
        else:
            self.send_error(404); return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Assets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Host)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.site = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="opencnc3d native assets ")
        self.addCleanup(self.temp.cleanup)
        self.dest = Path(self.temp.name)
        self.protected = {"opencnc3d": b"native game", "opencnc3d-launcher": b"native launcher",
                          "TiberianDawn.so": b"native brain", "opencnc3d-fx.cfg": b"my preferences",
                          "saves/slot.sav": b"my saved game"}
        for name, data in self.protected.items():
            path = self.dest / name
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        self.entries = {name: f"asset {name}".encode() for name in REQUIRED}
        self.entries.update({"opencnc3d": b"foreign executable", "TiberianDawn.so": b"foreign code",
                             "opencnc3d-game.exe": b"Windows game", "TiberianDawn.dll": b"Windows brain",
                             "opencnc3d-fx.cfg": b"foreign preferences", "saves/slot.sav": b"foreign save",
                             "desert-details/padding.bin": os.urandom(32768)})
        self.publish()

    def publish(self, bad_hash=False, missing_manifest=False, corrupt_crc=False):
        full = archive(self.entries)
        if corrupt_crc:
            full = bytearray(full)
            at = full.index(b"asset SCB01EA.pack")
            full[at] ^= 1
            full = bytes(full)
        bins = archive({"dosmenu.pack": self.entries["dosmenu.pack"], "opencnc3d": b"foreign executable"})
        names = {1: f"OpenCNC3D-windows-v{VERSION}.zip", 2: f"OpenCNC3DBinaries-windows-v{VERSION}.zip",
                 3: f"OpenCNC3D-v{VERSION}-manifest.txt"}
        manifest = "manifest 1\nversion " + VERSION + "\n"
        for asset, data in ((1, full), (2, bins)):
            sha = "0" * 64 if bad_hash and asset == 1 else hashlib.sha256(data).hexdigest()
            manifest += f"windows_{'full' if asset == 1 else 'bins'} {names[asset]} {len(data)} {sha}\n"
        manifest += "windows_data_id " + "a" * 64 + "\n"
        assets = {1: full, 2: bins, 3: manifest.encode()}
        release = {"tag": "v" + VERSION, "assets": [dict(id=i, name=names[i], size=len(assets[i]))
                   for i in (1, 2, 3) if not (missing_manifest and i == 3)]}
        feed = {"ok": True, "latest": {"tag": "v99.0.0", "assets": [
            {"id": 999, "name": "OpenCNC3D-windows-v99.0.0.zip", "size": 10}]}, "releases": [release]}
        self.server.state = dict(feed=feed, assets=assets, requests=[])

    def call(self, *args, success=True):
        result = subprocess.run([str(GATE), self.site, *args, "--dir", str(self.dest)],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
                                env=dict(os.environ, OPENCNC3D_BACKGROUND="1"))
        self.assertEqual(result.returncode == 0, success, result.stdout)
        for name, data in self.protected.items():
            self.assertEqual((self.dest / name).read_bytes(), data, name)
        return result.stdout

    def test_install_and_repair_preserve_native_code(self):
        offered = subprocess.check_output([str(GATE), "offer", str(self.dest)], text=True)
        self.assertEqual(offered.strip(), "offer=1")
        self.call("--install-game", "--media", "none")
        for name in REQUIRED:
            self.assertEqual((self.dest / name).read_bytes(), self.entries[name])
        self.assertFalse((self.dest / "opencnc3d-game.exe").exists())
        self.assertFalse((self.dest / "TiberianDawn.dll").exists())
        record = (self.dest / "opencnc3d-install.txt").read_text()
        self.assertIn("platform linux", record)
        self.assertIn("data_version " + VERSION, record)
        count = sum(i == 1 for i, _ in self.server.state["requests"])
        self.call("--install-game", "--media", "none")
        self.assertEqual(sum(i == 1 for i, _ in self.server.state["requests"]), count)
        (self.dest / "dosmenu.pack").unlink()
        self.call("--install-game", "--media", "none")
        self.assertEqual((self.dest / "dosmenu.pack").read_bytes(), self.entries["dosmenu.pack"])

    def test_menu_bootstrap_only(self):
        self.call("--fetch-menu-art")
        self.assertEqual((self.dest / "dosmenu.pack").read_bytes(), self.entries["dosmenu.pack"])
        self.assertFalse((self.dest / "SCG01EA.pack").exists())
        self.assertFalse((self.dest / "opencnc3d-install.txt").exists())

    def test_setup_controller_repairs_existing_install(self):
        (self.dest / "opencnc3d-install.txt").write_text("version 0.0.0\ndata_version 0.0.0\n")
        result = subprocess.run([str(GATE), self.site, "ui-install", str(self.dest)],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("offer=0", result.stdout)
        self.assertTrue((self.dest / "SCG01EA.pack").exists())
        for name, data in self.protected.items():
            self.assertEqual((self.dest / name).read_bytes(), data)

    def test_missing_and_wrong_checksums(self):
        self.publish(missing_manifest=True)
        self.assertIn("Verified game data", self.call("--install-game", success=False))
        self.assertNotIn(1, [i for i, _ in self.server.state["requests"]])
        self.publish(bad_hash=True)
        self.assertIn("did not arrive intact", self.call("--install-game", success=False))
        self.assertFalse((self.dest / "dosmenu.pack").exists())

    def test_required_assets_preflight(self):
        del self.entries["SCG01EA.pack"]
        self.publish()
        self.assertIn("missing SCG01EA.pack", self.call("--install-game", success=False))
        self.assertFalse((self.dest / "dosmenu.pack").exists())
        self.assertFalse((self.dest / "opencnc3d-install.txt").exists())

    def test_unsafe_path_rejected(self):
        self.entries["../escape.pack"] = b"must not escape"
        self.publish()
        self.assertIn("unsafe path", self.call("--install-game", success=False))
        self.assertFalse((self.dest / "dosmenu.pack").exists())

    def test_crc_failure_rolls_back(self):
        (self.dest / "dosmenu.pack").write_bytes(b"old menu")
        self.publish(corrupt_crc=True)
        self.call("--install-game", success=False)
        self.assertEqual((self.dest / "dosmenu.pack").read_bytes(), b"old menu")
        self.assertFalse((self.dest / "SCG01EA.pack").exists())
        self.assertFalse((self.dest / "opencnc3d-install.txt").exists())

    def test_interrupted_download_resumes(self):
        self.server.state["drop_once"] = True
        self.call("--install-game", "--media", "none")
        self.assertTrue(any(i == 1 and start > 0 for i, start in self.server.state["requests"]))
        self.assertTrue((self.dest / "SCG01EA.pack").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
