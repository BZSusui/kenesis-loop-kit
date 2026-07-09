# KLK-013 実績カタログ（SCR-004・タグ絞り込み閲覧＋画像取り込み・REQ-105/106）のテストを
# unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的/コア）: tests/site/check_klk013.py（S1-S15・Python標準のみ・
#   対象＝draft-gen/catalog.html(静的) / draft-gen/bridge.py(import 純関数 + ソース静的) /
#   catalog-import SKILL / CATALOG_RULES / tests/fixtures/klk013/catalog.sample.json /
#   .gitignore 3ファイル）。
# - D群（動的）:
#   - D1: git check-ignore で catalog/catalog.json・catalog/img/cat-0001.jpg・
#     catalog/.pending/x.import.json・catalog/catalog.html の Git 除外成立を検証
#     （REQ-011 / NFR-004・git不在時skip）。
#   - D2: `python3 -m unittest discover -s tests` の回帰全緑（NFR-006）は
#     スイート全体の実行そのものが担保する。ここでは S群 subprocess 実行を束ねる。
# - /catalog-import 実HTTP疎通（S10 の防御を実挙動で確認）: bridge の /catalog-import を
#   127.0.0.1 の実サーバで起動し、別オリジン403・巨大body413・不正JSON400・不正入力400・
#   取り込み対象不在404 を確認する。**claude は実起動しない**（subprocess.run を noop に
#   差し替え＝ブラウザ自動オープンも抑止／防御はいずれも worker 起動前に応答するため
#   claude 実行に到達しない）。
#
# M群（実 /catalog-import ＋ブラウザ実機の取り込み品質）は自動化不能のため tester が
# 手動確認しチケットのログへ記録する（test_palette_klk012 ラッパーと同型）。
# check_klk006〜012（既存 S群）は各チケットの正のため触らない（本ラッパーは独立）。
import importlib.util
import json
import os
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
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk013.py"
BRIDGE_PATH = ROOT / "draft-gen" / "bridge.py"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("klk013_bridge_live", str(BRIDGE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestKLK013Static(unittest.TestCase):
    """check_klk013.py（設計書 KLK-013 §9 S群 S1-S15）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk013.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため check-ignore をskip")
class TestKLK013GitIgnore(unittest.TestCase):
    """D1: catalog/ 配下（画像・タグJSON・取り込みステージング・オフラインスナップショット）が
    .gitignore（catalog/）で除外され、git check-ignore が exit 0（除外成立）を返すこと。
    社外秘の画像・クライアント名がコミットされない（REQ-011 / NFR-004）。"""

    TARGETS = (
        "catalog/catalog.json",
        "catalog/img/cat-0001.jpg",
        "catalog/.pending/x.import.json",
        "catalog/catalog.html",
    )

    def _inside_worktree(self):
        pre = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        return pre.returncode == 0

    def test_d1_catalog_ignored(self):
        if not self._inside_worktree():
            self.skipTest("git リポジトリ外のため D1 をskip")
        for target in self.TARGETS:
            proc = subprocess.run(
                ["git", "check-ignore", target],
                capture_output=True, text=True, cwd=str(ROOT), timeout=60,
            )
            self.assertEqual(
                proc.returncode, 0,
                f"git check-ignore で除外不成立(exit {proc.returncode}): {target}\n"
                f"{proc.stdout}{proc.stderr}",
            )


def _can_bind_localhost():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.close()
        return True
    except OSError:
        return False


@unittest.skipUnless(_can_bind_localhost(), "127.0.0.1 へ bind できないため /catalog-import 疎通をskip")
class TestKLK013CatalogImportDefense(unittest.TestCase):
    """POST /catalog-import の防御を実HTTPで確認（S10 の実挙動）。

    別オリジン403・巨大body413・不正JSON400・不正入力（安全名でない files）400・
    取り込み対象不在404。いずれも worker(claude) 起動前に応答するため claude は実行されない
    （subprocess.run を noop 化してブラウザ自動オープンも抑止）。"""

    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        # subprocess.run を noop 化（起動時のブラウザ自動オープン抑止・万一の claude 実行防止）。
        cls._orig_run = cls.bridge.subprocess.run
        cls.bridge.subprocess.run = lambda *a, **k: types.SimpleNamespace(
            returncode=0, stdout="", stderr="")

        cls.port = _free_port()

        # サーバをデーモンスレッドで起動し /health が応答するまで待つ。
        cls._server_thread = threading.Thread(
            target=cls.bridge._run_server, args=(cls.port,), daemon=True)
        cls._server_thread.start()
        if not cls._wait_health(cls.port, timeout=8.0):
            cls.tearDownClass()
            raise unittest.SkipTest("ブリッジが起動しなかったため /catalog-import 疎通をskip")

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

    # -- helpers -----------------------------------------------------------
    def _post(self, body_obj, origin=None, raw_len=None, raw_body=None):
        """POST /catalog-import。origin 未指定なら Origin ヘッダ無し(None=許可)。
        raw_len 指定時は Content-Length をその値に偽装しボディは送らない(413経路)。
        raw_body 指定時はそのバイト列をそのまま送る(不正JSON経路)。"""
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5.0)
        conn.putrequest("POST", "/catalog-import", skip_host=False, skip_accept_encoding=True)
        if origin is not None:
            conn.putheader("Origin", origin)
        conn.putheader("Content-Type", "application/json")
        if raw_len is not None:
            conn.putheader("Content-Length", str(raw_len))
            conn.endheaders()  # ボディ非送信（413 は読取前に返る）
        elif raw_body is not None:
            conn.putheader("Content-Length", str(len(raw_body)))
            conn.endheaders()
            conn.send(raw_body)
        else:
            payload = json.dumps(body_obj).encode("utf-8")
            conn.putheader("Content-Length", str(len(payload)))
            conn.endheaders()
            conn.send(payload)
        res = conn.getresponse()
        status = res.status
        data = res.read()
        conn.close()
        return status, data

    # -- tests -------------------------------------------------------------
    def test_bad_origin_403(self):
        st, _ = self._post({"all": True}, origin="http://evil.example")
        self.assertEqual(st, 403, "別オリジンは403で拒否されるべき")

    def test_oversize_413(self):
        big = self.bridge.MAX_BODY_BYTES + 1
        st, _ = self._post(None, raw_len=big)
        self.assertEqual(st, 413, "MAX_BODY_BYTES 超過は413で拒否されるべき")

    def test_bad_json_400(self):
        st, _ = self._post(None, raw_body=b"{ not json")
        self.assertEqual(st, 400, "不正JSONは400で拒否されるべき")

    def test_bad_input_400(self):
        # files に安全名でない値（パストラバーサル）→ validate_import_request で400
        st, _ = self._post({"files": ["../etc/passwd"]})
        self.assertEqual(st, 400, "安全名でない files は400で拒否されるべき")

    def test_missing_target_404(self):
        # 実在しない安全名ファイル → .pending 内に無く404（worker 未起動）
        st, _ = self._post({"files": ["definitely_missing_klk013.jpg"]})
        self.assertEqual(st, 404, "取り込み対象不在は404で拒否されるべき（worker 未起動）")


if __name__ == "__main__":
    unittest.main()
