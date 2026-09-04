# KLK-083 見本サイトURLからの配色読み取りを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk083.py（X群/S群/C群/B群/U群/R群）
# - 追加: **本物の HTTP 通信**でガードと取得の仕組みを確かめる。
#
#   ★テストは第三者サイトへ一切アクセスしない。ローカルに立てた HTTP サーバだけを使う。
#     そのため「本番と同じガード」ではローカル宛が拒否される——それ自体が S 群の検査になる。
#     HTTP の仕組み（転送の追従・サイズ上限・文字コード）を見るときだけ、
#     名前解決の判定を差し替えてローカルを公開扱いにする。
import http.server
import importlib.util
import json
import socket
import socketserver
import subprocess
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk083.py"
BRIDGE_PATH = ROOT / "draft-gen" / "bridge.py"

PAGE = (b'<!doctype html><html><head><style>'
        b'body{background:#f7f5f0;color:#333333}'
        b'.btn{background:#2e7d6b;border:1px solid #2e7d6b}'
        b'.ac{color:#e8a33d}</style>'
        b'<link rel="stylesheet" href="/s.css"></head><body></body></html>')
SHEET = b'.x{color:#2e7d6b}.y{color:#8fb9ae}'


def _load_bridge():
    spec = importlib.util.spec_from_file_location("klk083_bridge", str(BRIDGE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Site(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/s.css":
            self._send(SHEET, "text/css")
        elif self.path == "/redir":
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
        elif self.path == "/loop":
            self.send_response(302)
            self.send_header("Location", "/loop")
            self.end_headers()
        elif self.path == "/internal":
            self.send_response(302)
            self.send_header("Location",
                             "http://127.0.0.1:%d/" % self.server.server_address[1])
            self.end_headers()
        elif self.path == "/big":
            self._send(b"<style>" + b"/*x*/" * 500000 + b"#abcdef</style>")
        else:
            self._send(PAGE)


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestKLK083Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0, "check_klk083.py failed:\n" + proc.stdout + proc.stderr
        )


class _SiteBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        cls.srv = socketserver.TCPServer(("127.0.0.1", 0), _Site)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.port

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()


class TestKLK083GuardBlocksLocal(_SiteBase):
    """★本番と同じガードで、ローカル宛が確実に拒否されること。"""

    def test_localhost_is_refused(self):
        text, err = self.bridge.fetch_text(self.base + "/")
        self.assertIsNone(text, "ローカルサーバの中身を取得できてしまった（SSRF）")
        self.assertIn("外部の公開サイトではない", err)

    def test_read_site_colors_refuses_localhost(self):
        res = self.bridge.read_site_colors(self.base + "/")
        self.assertFalse(res["ok"], res)
        self.assertEqual(res["colors"], [])

    def test_redirect_to_internal_is_refused(self):
        """公開サイトが内部アドレスへ転送してくる形（SSRF の本命）を止めること。"""
        orig = self.bridge._resolve_public_addrs
        seen = []

        def guard(host):
            seen.append(host)
            # 1ホップ目だけ「公開」とみなし、転送先は本物のガードで判定させる
            return (True, ["203.0.113.1"]) if len(seen) == 1 else orig(host)

        self.bridge._resolve_public_addrs = guard
        try:
            text, err = self.bridge.fetch_text(self.base + "/internal")
        finally:
            self.bridge._resolve_public_addrs = orig
        self.assertIsNone(text, "転送で内部アドレスへ到達してしまった（SSRF）")
        self.assertIn("外部の公開サイトではない", err)


class TestKLK083HttpMechanics(_SiteBase):
    """HTTP の仕組み（ガードだけ緩めてローカルを公開扱いにする）。"""

    def setUp(self):
        self._orig = self.bridge._resolve_public_addrs
        self.bridge._resolve_public_addrs = lambda host: (True, ["203.0.113.1"])

    def tearDown(self):
        self.bridge._resolve_public_addrs = self._orig

    def test_fetch_and_extract_over_real_http(self):
        res = self.bridge.read_site_colors(self.base + "/")
        self.assertTrue(res["ok"], res)
        hexes = [c["hex"] for c in res["colors"]]
        self.assertIn("#2e7d6b", hexes)
        self.assertIn("#8fb9ae", hexes, "同一オリジンCSSを読めていない")
        self.assertEqual(res["suggestion"]["bg"], "#f7f5f0")
        self.assertEqual(res["suggestion"]["main"], "#2e7d6b")

    def test_redirect_is_followed(self):
        text, err = self.bridge.fetch_text(self.base + "/redir")
        self.assertIsNone(err, err)
        self.assertIn("#2e7d6b", text)

    def test_redirect_loop_is_bounded(self):
        text, err = self.bridge.fetch_text(self.base + "/loop")
        self.assertIsNone(text)
        self.assertIn("転送が多すぎます", err)

    def test_size_cap(self):
        text, err = self.bridge.fetch_text(self.base + "/big", max_bytes=5000)
        self.assertIsNone(err, err)
        self.assertLessEqual(len(text), 5000)

    def test_result_is_deterministic(self):
        a = self.bridge.read_site_colors(self.base + "/")
        b = self.bridge.read_site_colors(self.base + "/")
        self.assertEqual(a, b, "同じページで結果が揺れた（決定的でない）")


class TestKLK083EndpointLive(unittest.TestCase):
    """POST /read-colors の実HTTPスモーク（防御が入口で効くこと）。"""

    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        cls._orig_run = cls.bridge.subprocess.run
        cls.bridge.subprocess.run = lambda *a, **k: None  # 起動時のブラウザ自動オープン抑止
        cls.port = _free_port()
        threading.Thread(target=cls.bridge._run_server, args=(cls.port,), daemon=True).start()
        import time
        for _ in range(80):
            try:
                c = HTTPConnection("127.0.0.1", cls.port, timeout=1.0)
                c.request("GET", "/health")
                c.getresponse().read()
                c.close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise unittest.SkipTest("ブリッジが起動しなかったため skip")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_orig_run", None) is not None:
            cls.bridge.subprocess.run = cls._orig_run

    def _post(self, body, origin=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10.0)
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        conn.request("POST", "/read-colors", json.dumps(body), headers)
        res = conn.getresponse()
        raw = res.read().decode("utf-8")
        conn.close()
        return res.status, json.loads(raw) if raw else {}

    def test_rejects_internal_and_bad_urls(self):
        for url in ("http://127.0.0.1:9/", "http://192.168.1.1/",
                    "http://169.254.169.254/latest/meta-data/",
                    "file:///etc/passwd", "http://u:p@example.com/", 123, None):
            status, obj = self._post({"url": url})
            self.assertEqual(status, 400, "url=%r を拒否していない: %s" % (url, obj))
            self.assertIn("error", obj)

    def test_rejects_foreign_origin(self):
        status, _ = self._post({"url": "http://example.com/"}, origin="https://evil.example")
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
