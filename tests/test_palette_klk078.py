# KLK-078 型入れ替えの土台を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk078.py（R1-R6 規約 / U1-U9 純関数 / S1-S6 見本の実物）
# - 追加: **GET /sections の実HTTPスモーク**。
#   純関数が正しくても、エンドポイントの引数取り出し・防御・JSON 形が壊れていれば
#   画面からは何も選べない。KLK-020 の /upload 実HTTPスモークと同型で見張る。
import importlib.util
import json
import shutil
import socket
import subprocess
import threading
import time
import types
import unittest
import urllib.parse
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk078.py"
BRIDGE_PATH = ROOT / "draft-gen" / "bridge.py"
SAMPLE = ROOT / "samples" / "03_クリニック_ナビ下配置"
WORK = ROOT / "mockups" / "2026-09-04_klk078_smoke"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("klk078_bridge_live", str(BRIDGE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestKLK078Static(unittest.TestCase):
    """check_klk078.py が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk078.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK078SectionsLive(unittest.TestCase):
    """GET /sections の実HTTPスモーク（見本をコピーした作業フォルダに対して）。"""

    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        # 起動時のブラウザ自動オープン／万一の claude 実行を抑止する（KLK-020 と同型）
        cls._orig_run = cls.bridge.subprocess.run
        cls.bridge.subprocess.run = lambda *a, **k: types.SimpleNamespace(
            returncode=0, stdout="", stderr="")

        if WORK.exists():
            shutil.rmtree(WORK)
        shutil.copytree(SAMPLE, WORK)

        cls.port = _free_port()
        cls._t = threading.Thread(target=cls.bridge._run_server, args=(cls.port,), daemon=True)
        cls._t.start()
        if not cls._wait_health(cls.port):
            cls.tearDownClass()
            raise unittest.SkipTest("ブリッジが起動しなかったため /sections 実HTTPスモークをskip")

    @classmethod
    def tearDownClass(cls):
        if WORK.exists():
            shutil.rmtree(WORK, ignore_errors=True)
        if getattr(cls, "_orig_run", None) is not None:
            cls.bridge.subprocess.run = cls._orig_run

    @staticmethod
    def _wait_health(port, timeout=8.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1.0)
                conn.request("GET", "/health")
                res = conn.getresponse()
                res.read()
                conn.close()
                if res.status == 200:
                    return True
            except OSError:
                pass
            time.sleep(0.1)
        return False

    def _get(self, folder, letter):
        q = urllib.parse.urlencode({"folder": folder, "letter": letter})
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5.0)
        conn.request("GET", "/sections?" + q)
        res = conn.getresponse()
        body = res.read().decode("utf-8")
        conn.close()
        return res.status, json.loads(body) if body else {}

    def test_returns_real_addresses_and_types(self):
        status, obj = self._get("mockups/2026-09-04_klk078_smoke", "c")
        self.assertEqual(status, 200, obj)
        addrs = [s["addr"] for s in obj["sections"]]
        # 実ページの番地が返ること（固定6番地ではないこと）
        self.assertIn("FLOW-01", addrs, "実在する FLOW-01 が返っていない")
        self.assertIn("STAFF-01", addrs, "実在する STAFF-01 が返っていない")
        self.assertNotIn("GALLERY-01", addrs, "存在しない GALLERY-01 が返っている（404 の元）")
        # 型とプールが載ること
        mv = [s for s in obj["sections"] if s["addr"] == "MV-01"][0]
        self.assertEqual(mv["current"], "panel-band")
        self.assertIn("overlap", mv["pool"])
        # プールを持たない番地は current=None・pool=[]
        nav = [s for s in obj["sections"] if s["addr"] == "NAV-01"][0]
        self.assertIsNone(nav["current"])
        self.assertEqual(nav["pool"], [])

    def test_types_differ_between_variants(self):
        """案ごとに型が違うこと（＝案切替で読み直す必要がある根拠）。"""
        seen = []
        for letter in ("a", "b", "c"):
            status, obj = self._get("mockups/2026-09-04_klk078_smoke", letter)
            self.assertEqual(status, 200, obj)
            seen.append(tuple(sorted((s["addr"], s["current"]) for s in obj["sections"])))
        self.assertEqual(len(set(seen)), 3, "3案の型の組合せが同一（表引きが効いていない）")

    def test_defenses(self):
        """folder/letter/不在ファイルの防御（既存 /regenerate と同じ関数を使っていること）。"""
        for folder, letter, want in (
            ("mockups/../etc", "a", 400),
            ("/etc", "a", 400),
            ("catalog", "a", 400),
            ("mockups/2026-09-04_klk078_smoke", "z", 400),
            ("mockups/2026-09-04_klk078_smoke/..", "a", 400),
            ("mockups/no-such-folder", "a", 404),
        ):
            status, _obj = self._get(folder, letter)
            self.assertEqual(status, want, "folder=%r letter=%r で %d を期待" % (folder, letter, want))


if __name__ == "__main__":
    unittest.main()
