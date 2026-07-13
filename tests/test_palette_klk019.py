# KLK-019 ブリッジ経由の配色ジェネレーター(palette/index.html)配信ルート追加のテストを
# unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的/コア）: tests/site/check_klk019.py（S1-S8・Python標準のみ・
#   対象＝draft-gen/bridge.py(import + do_GET/_serve_palette ソース静的) /
#   draft-gen/index.html(起動リンク)）。
# - D群（動的）:
#   - D1: check_klk019.py を subprocess 実行し exit 0。
#   - D2: 実HTTPスモーク。bridge._run_server(port) を 127.0.0.1 のデーモンスレッドで起動し
#     （/health 応答待ち・test_palette_klk013 と同型・_can_bind_localhost で skip 可）、
#     GET /palette/index.html→200 text/html（palette の HTML マーカーを含む・非空）、
#     GET /palette・/palette/→200（3パス正規化）、想定外パス(/palette/foo.html・/nope)→404
#     ({"error": "not found"})、回帰 GET /health→200・GET /→200 text/html を確認。
#     **claude は実起動しない**（GET配信のみで worker に到達しないが、念のため subprocess.run を
#     noop 化しブラウザ自動オープンも抑止）。
#   - D3: `python3 -m unittest discover -s tests` の回帰全緑（KLK-006〜018 が回帰しない）は
#     スイート全体の実行そのものが担保する。ここでは S群 subprocess 実行を束ねる。
#
# M群（ブリッジ実起動＋ブラウザ実機）は自動化不能のため tester が手動確認しチケットの
# ログへ記録する（test_palette_klk013 ラッパーと同型）。
# check_klk006〜018（既存 S群）は各チケットの正のため触らない（本ラッパーは独立・additive）。
import importlib.util
import os
import socket
import subprocess
import threading
import time
import types
import unittest
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk019.py"
BRIDGE_PATH = ROOT / "draft-gen" / "bridge.py"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("klk019_bridge_live", str(BRIDGE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _can_bind_localhost():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.close()
        return True
    except OSError:
        return False


class TestKLK019Static(unittest.TestCase):
    """D1: check_klk019.py（設計書 KLK-019 §9 S群 S1-S8）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk019.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(_can_bind_localhost(), "127.0.0.1 へ bind できないため palette 配信スモークをskip")
class TestKLK019PaletteServe(unittest.TestCase):
    """D2: palette 配信ルートを実HTTPで確認（GET配信のみ・claude は起動しない）。

    GET /palette/index.html→200 text/html・非空HTML、/palette・/palette/→200（3パス正規化）、
    想定外パス→404、既存 /health・/ は不変。KLK_BRIDGE_PORT で衝突回避・環境依存で skip 可。"""

    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        # subprocess.run を noop 化（起動時のブラウザ自動オープン抑止・万一の claude 実行防止）。
        cls._orig_run = cls.bridge.subprocess.run
        cls.bridge.subprocess.run = lambda *a, **k: types.SimpleNamespace(
            returncode=0, stdout="", stderr="")

        env_port = os.environ.get("KLK_BRIDGE_PORT")
        cls.port = int(env_port) if env_port else _free_port()

        # サーバをデーモンスレッドで起動し /health が応答するまで待つ。
        cls._server_thread = threading.Thread(
            target=cls.bridge._run_server, args=(cls.port,), daemon=True)
        cls._server_thread.start()
        if not cls._wait_health(cls.port, timeout=8.0):
            cls.tearDownClass()
            raise unittest.SkipTest("ブリッジが起動しなかったため palette 配信スモークをskip")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_orig_run", None) is not None:
            cls.bridge.subprocess.run = cls._orig_run
        # デーモンサーバスレッドはプロセス終了時に破棄される（明示停止手段は本体に無い）。

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

    # -- helper ------------------------------------------------------------
    def _get(self, path):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5.0)
        conn.request("GET", path)
        res = conn.getresponse()
        status = res.status
        ctype = res.getheader("Content-Type")
        body = res.read()
        conn.close()
        return status, ctype, body

    # -- tests: palette 配信 ----------------------------------------------
    def test_palette_index_200_html(self):
        st, ctype, body = self._get("/palette/index.html")
        self.assertEqual(st, 200, "GET /palette/index.html は200であるべき")
        self.assertEqual(ctype, "text/html; charset=utf-8",
                         "Content-Type は text/html; charset=utf-8 であるべき")
        self.assertTrue(body, "body は非空であるべき")
        self.assertIn(b"<!DOCTYPE html>", body[:200],
                      "palette/index.html の HTML マーカーを含むべき")

    def test_palette_no_slash_200(self):
        st, ctype, _ = self._get("/palette")
        self.assertEqual(st, 200, "GET /palette は200であるべき（3パス正規化）")
        self.assertEqual(ctype, "text/html; charset=utf-8")

    def test_palette_trailing_slash_200(self):
        st, ctype, _ = self._get("/palette/")
        self.assertEqual(st, 200, "GET /palette/ は200であるべき（3パス正規化）")
        self.assertEqual(ctype, "text/html; charset=utf-8")

    def test_palette_same_body_for_3paths(self):
        _, _, b1 = self._get("/palette")
        _, _, b2 = self._get("/palette/")
        _, _, b3 = self._get("/palette/index.html")
        self.assertEqual(b1, b2, "/palette と /palette/ は同一ファイルを返すべき")
        self.assertEqual(b2, b3, "/palette/ と /palette/index.html は同一ファイルを返すべき")

    # -- tests: 想定外パスは404維持 ---------------------------------------
    def test_palette_subpath_404(self):
        st, _, body = self._get("/palette/foo.html")
        self.assertEqual(st, 404, "未知サブパス /palette/foo.html は404であるべき（配下配信しない）")
        self.assertIn(b'"error"', body)
        self.assertIn("not found".encode("utf-8"), body)

    def test_unknown_path_404(self):
        st, _, body = self._get("/nope")
        self.assertEqual(st, 404, "未知パス /nope は404であるべき")
        self.assertIn("not found".encode("utf-8"), body)

    # -- tests: 既存ルート不変（回帰） ------------------------------------
    def test_health_200(self):
        st, _, _ = self._get("/health")
        self.assertEqual(st, 200, "GET /health は200であるべき（既存ルート不変）")

    def test_index_200_html(self):
        st, ctype, _ = self._get("/")
        self.assertEqual(st, 200, "GET / は200であるべき（既存ルート不変）")
        self.assertEqual(ctype, "text/html; charset=utf-8")


if __name__ == "__main__":
    unittest.main()
