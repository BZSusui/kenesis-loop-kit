# KLK-080 型を入れ替えた実物の機械検査を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk080.py（Q群=検出力 / B群=配線 / T群=ツール / S群=見本の実物）
# - 追加: **warnings が実HTTPで返り、成功と区別されること**を stub 経由で確かめる。
#   後段検証は「型が変わったか」だけでは足りず（KLK-079）、規約違反も見る（KLK-080）。
#   その配線が壊れても静的検査は通ってしまうので、実挙動で見張る。
import importlib.util
import json
import re
import shutil
import socket
import subprocess
import threading
import time
import types
import unittest
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk080.py"
BRIDGE_PATH = ROOT / "draft-gen" / "bridge.py"
SAMPLE = ROOT / "samples" / "01_カフェ_1カラム"
WORK_NAME = "2026-09-04_klk080_smoke"
WORK = ROOT / "mockups" / WORK_NAME


def _load_bridge():
    spec = importlib.util.spec_from_file_location("klk080_bridge_live", str(BRIDGE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestKLK080Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=300,
        )
        self.assertEqual(
            proc.returncode, 0, "check_klk080.py failed:\n" + proc.stdout + proc.stderr
        )


class TestKLK080WarningsReachTheUser(unittest.TestCase):
    """規約違反を作るスキルを模し、warnings が /status で返ることを確かめる。"""

    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        cls._orig_run = cls.bridge.subprocess.run

        def stub(cmd, *a, **kw):
            ok = types.SimpleNamespace(returncode=0, stdout="", stderr="")
            if not (isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "claude"):
                return ok
            m = re.search(r"(\S+\.regen\.json)$", cmd[2] if len(cmd) > 2 else "")
            if not m:
                return ok
            spec = json.loads((ROOT / m.group(1)).read_text(encoding="utf-8"))
            target = ROOT / spec["target"]
            html = target.read_text(encoding="utf-8")
            # 型は正しく入れ替えるが、アタリの比率を規約違反（16/7）にしてしまうスキル。
            # ★新しい型に**実際に当たる**セレクタで違反を作ること。
            #   旧型のセレクタ（.m-gallery.pat-grid .atari）を壊しても、
            #   そのルールはもうこのセクションに当たらないので検査は正しく無視する
            #   （実装時にここで一度つまずいた＝絞り込みが効いている証拠）。
            desired = spec.get("desiredType")
            if desired:
                html = html.replace('class="m-gallery pat-grid"',
                                    'class="m-gallery %s"' % desired, 1)
                html = html.replace(
                    "</style>",
                    ".m-gallery.%s .atari{ aspect-ratio:16/7; }</style>" % desired, 1)
            html = html.replace('.map-atari{ position:relative; aspect-ratio:4/3;',
                                '.map-atari{ position:relative; aspect-ratio:16/7;', 1)
            target.write_text(html, encoding="utf-8")
            return ok

        cls.bridge.subprocess.run = stub
        if WORK.exists():
            shutil.rmtree(WORK)
        shutil.copytree(SAMPLE, WORK)
        cls.port = _free_port()
        cls._t = threading.Thread(target=cls.bridge._run_server, args=(cls.port,), daemon=True)
        cls._t.start()
        if not cls._wait_health(cls.port):
            cls.tearDownClass()
            raise unittest.SkipTest("ブリッジが起動しなかったため skip")

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

    def _post(self, body):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10.0)
        conn.request("POST", "/regenerate", json.dumps(body), {"Content-Type": "application/json"})
        res = conn.getresponse()
        raw = res.read().decode("utf-8")
        conn.close()
        return res.status, json.loads(raw) if raw else {}

    def _wait_done(self, job_id, timeout=30.0):
        deadline = time.time() + timeout
        last = {}
        while time.time() < deadline:
            conn = HTTPConnection("127.0.0.1", self.port, timeout=5.0)
            conn.request("GET", "/status/" + job_id)
            res = conn.getresponse()
            last = json.loads(res.read().decode("utf-8"))
            conn.close()
            if last.get("state") in ("done", "error"):
                return last
            time.sleep(0.15)
        return last

    def test_type_applied_but_rule_violated_is_not_plain_success(self):
        """★型は変わったが規約違反がある＝これを「成功」で終わらせない。"""
        status, obj = self._post({
            "folder": "mockups/" + WORK_NAME, "letter": "a",
            "addr": "GALLERY-01", "desiredType": "pat-slider",
        })
        self.assertEqual(status, 202, obj)
        st = self._wait_done(obj["jobId"])
        self.assertEqual(st.get("state"), "done", st)
        self.assertIs(st.get("typeApplied"), True, "型は入れ替わっているはず: %s" % st)
        self.assertTrue(
            st.get("warnings"),
            "規約違反（アタリ 16/7）を作ったのに warnings が空（配線が壊れている）:\n%s" % st,
        )
        self.assertIn("規約違反の疑い", st.get("message", ""))

    def test_warnings_are_reported_without_type_change_too(self):
        """型指定なしの作り直しでも規約違反は見る。"""
        status, obj = self._post({
            "folder": "mockups/" + WORK_NAME, "letter": "b", "addr": "ACCESS-01",
        })
        self.assertEqual(status, 202, obj)
        st = self._wait_done(obj["jobId"])
        self.assertEqual(st.get("state"), "done", st)
        self.assertIsNone(st.get("typeApplied"))
        self.assertTrue(
            any("極端な横長比率" in w for w in st.get("warnings") or []),
            "型指定なしでは品質を見ていない:\n%s" % st,
        )


if __name__ == "__main__":
    unittest.main()
