# KLK-012 部分再生成（番地ラベル指定でセクション単位に作り直す・REQ-103）のテストを
# unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的/コア）: tests/site/check_klk012.py（S1-S12・Python標準のみ・
#   対象＝draft-gen/bridge.py(import 純関数 + ソース静的) / draft-regenerate SKILL /
#   DRAFT_RULES / draft-generate SKILL / tests/fixtures/klk012/*.html）。
# - D群（動的）:
#   - D1: `python3 -m unittest discover -s tests` の回帰全緑（NFR-006）は
#     スイート全体の実行そのものが担保する。ここでは S群 subprocess 実行を束ねる。
#   - D2: git check-ignore で mockups/.pending/{jobId}.regen.json・
#     mockups/{…}/index-a.html の Git 除外成立を検証（REQ-011 / NFR-004・git不在時skip）。
# - /regenerate 実HTTP疎通（S6/S7 の防御を実挙動で確認）: bridge の /regenerate を
#   127.0.0.1 の実サーバで起動し、別オリジン403・巨大body413・traversal/検証400・
#   不在/unknown404・duplicate400 を確認する。**claude は実起動しない**
#   （subprocess.run を noop に差し替え＝ブラウザ自動オープンも抑止／防御はいずれも
#   worker 起動前に応答するため claude 実行に到達しない）。エラー経路では
#   .regen.json が作られず対象ファイルが無変更であることも確認する。
#
# M群（実 /draft-regenerate ＋ブラウザ実機の再生成品質）は自動化不能のため tester が
# 手動確認しチケットのログへ記録する（test_palette_klk010/011 ラッパーと同型）。
# check_klk006〜011（既存 S群）は各チケットの正のため触らない（本ラッパーは独立）。
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
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk012.py"
BRIDGE_PATH = ROOT / "draft-gen" / "bridge.py"
BEFORE_FIXTURE = ROOT / "tests" / "fixtures" / "klk012" / "index-a-before.html"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("klk012_bridge_live", str(BRIDGE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestKLK012Static(unittest.TestCase):
    """check_klk012.py（設計書 KLK-012 §9 S群 S1-S12）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk012.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため check-ignore をskip")
class TestKLK012GitIgnore(unittest.TestCase):
    """D2: 再生成の一時ジョブ仕様 mockups/.pending/{jobId}.regen.json と生成物
    mockups/{…}/index-a.html が .gitignore（mockups/）で除外され、git check-ignore が
    exit 0（除外成立）を返すこと（一時ファイル・生成物がコミットされない）。
    （REQ-011 / NFR-004）"""

    TARGETS = (
        "mockups/.pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.regen.json",
        "mockups/2026-07-08_サンプル案件/index-a.html",
    )

    def _inside_worktree(self):
        pre = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        return pre.returncode == 0

    def test_d2_regen_artifacts_ignored(self):
        if not self._inside_worktree():
            self.skipTest("git リポジトリ外のため D2 をskip")
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


@unittest.skipUnless(_can_bind_localhost(), "127.0.0.1 へ bind できないため /regenerate 疎通をskip")
class TestKLK012RegenerateDefense(unittest.TestCase):
    """POST /regenerate の防御を実HTTPで確認（S6/S7 の実挙動）。

    別オリジン403・巨大body413・traversal/letter/addr/JSON 400・不在/unknown 404・
    duplicate 400。いずれも worker(claude) 起動前に応答するため claude は実行されない
    （subprocess.run を noop 化してブラウザ自動オープンも抑止）。エラー経路では
    .regen.json が作られず対象ファイルが無変更であることも確認する。"""

    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        # subprocess.run を noop 化（起動時のブラウザ自動オープン抑止・万一の claude 実行防止）。
        cls._orig_run = cls.bridge.subprocess.run
        cls.bridge.subprocess.run = lambda *a, **k: types.SimpleNamespace(
            returncode=0, stdout="", stderr="")

        cls.port = _free_port()
        cls.origin = "http://127.0.0.1:{0}".format(cls.port)
        cls.pending_dir = ROOT / "mockups" / ".pending"

        # テスト用の実フォルダ/ファイルを mockups/ 配下（Git除外）に作成。
        cls.clean_dir = ROOT / "mockups" / ".klk012_test_clean"
        cls.dup_dir = ROOT / "mockups" / ".klk012_test_dup"
        cls.clean_dir.mkdir(parents=True, exist_ok=True)
        cls.dup_dir.mkdir(parents=True, exist_ok=True)
        before_html = BEFORE_FIXTURE.read_text(encoding="utf-8")
        cls.clean_html = before_html
        (cls.clean_dir / "index-a.html").write_text(before_html, encoding="utf-8")
        # 重複: HERO-01 セクションを丸ごと複製したもの（find_target_section→duplicate）。
        hero_block = (
            '  <div class="sec reveal">\n'
            '    <div class="addr"><span class="pin">HERO-01</span></div>\n'
            '    <div class="m-hero">DUP</div>\n'
            '  </div>\n')
        dup_html = before_html.replace("</body>", hero_block + "</body>")
        (cls.dup_dir / "index-a.html").write_text(dup_html, encoding="utf-8")

        # サーバをデーモンスレッドで起動し /health が応答するまで待つ。
        cls._server_thread = threading.Thread(
            target=cls.bridge._run_server, args=(cls.port,), daemon=True)
        cls._server_thread.start()
        if not cls._wait_health(cls.port, timeout=8.0):
            cls.tearDownClass()
            raise unittest.SkipTest("ブリッジが起動しなかったため /regenerate 疎通をskip")

    @classmethod
    def tearDownClass(cls):
        # subprocess.run を復元。
        if getattr(cls, "_orig_run", None) is not None:
            cls.bridge.subprocess.run = cls._orig_run
        for d in (getattr(cls, "clean_dir", None), getattr(cls, "dup_dir", None)):
            if d and d.exists():
                shutil.rmtree(d, ignore_errors=True)
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
    def _post(self, body_obj, origin=None, raw_len=None):
        """POST /regenerate。origin 未指定なら Origin ヘッダ無し(None=許可)。
        raw_len 指定時は Content-Length をその値に偽装しボディは送らない(413経路検証)。"""
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5.0)
        conn.putrequest("POST", "/regenerate", skip_host=False, skip_accept_encoding=True)
        if origin is not None:
            conn.putheader("Origin", origin)
        conn.putheader("Content-Type", "application/json")
        if raw_len is not None:
            conn.putheader("Content-Length", str(raw_len))
            conn.endheaders()  # ボディ非送信（413 は読取前に返る）
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

    def _pending_regen_count(self):
        if not self.pending_dir.exists():
            return 0
        return len([p for p in self.pending_dir.iterdir()
                    if p.name.endswith(".regen.json")])

    # -- tests -------------------------------------------------------------
    def test_bad_origin_403(self):
        st, _ = self._post({"folder": "mockups/.klk012_test_clean", "letter": "a",
                            "addr": "HERO-01"}, origin="http://evil.example")
        self.assertEqual(st, 403, "別オリジンは403で拒否されるべき")

    def test_oversize_413(self):
        big = self.bridge.MAX_BODY_BYTES + 1
        st, _ = self._post(None, raw_len=big)
        self.assertEqual(st, 413, "MAX_BODY_BYTES 超過は413で拒否されるべき")

    def test_bad_json_400(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5.0)
        body = b"{ not json"
        conn.putrequest("POST", "/regenerate")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(len(body)))
        conn.endheaders()
        conn.send(body)
        res = conn.getresponse()
        st = res.status
        res.read()
        conn.close()
        self.assertEqual(st, 400, "不正JSONは400で拒否されるべき")

    def test_traversal_folder_400(self):
        st, _ = self._post({"folder": "mockups/../etc", "letter": "a", "addr": "HERO-01"})
        self.assertEqual(st, 400, "パストラバーサル folder は400で拒否されるべき")

    def test_bad_letter_400(self):
        st, _ = self._post({"folder": "mockups/.klk012_test_clean", "letter": "z",
                            "addr": "HERO-01"})
        self.assertEqual(st, 400, "不正 letter は400で拒否されるべき")

    def test_bad_addr_400(self):
        st, _ = self._post({"folder": "mockups/.klk012_test_clean", "letter": "a",
                            "addr": "hero-01"})
        self.assertEqual(st, 400, "不正 addr（小文字）は400で拒否されるべき")

    def test_missing_file_404(self):
        st, _ = self._post({"folder": "mockups/.klk012_test_clean", "letter": "b",
                            "addr": "HERO-01"})
        self.assertEqual(st, 404, "対象ファイル不在は404で拒否されるべき")

    def test_unknown_addr_404(self):
        st, _ = self._post({"folder": "mockups/.klk012_test_clean", "letter": "a",
                            "addr": "ZZZZ-01"})
        self.assertEqual(st, 404, "未知番地は404で拒否されるべき（SPEC §7）")

    def test_duplicate_addr_400(self):
        st, _ = self._post({"folder": "mockups/.klk012_test_dup", "letter": "a",
                            "addr": "HERO-01"})
        self.assertEqual(st, 400, "重複番地は400で拒否されるべき（SPEC §7）")

    def test_errors_leave_file_unchanged_and_no_pending(self):
        """エラー経路では対象ファイルが無変更で、.regen.json が作られない
        （claude 起動前に応答＝SPEC §7 ラフを壊さない）。"""
        before_count = self._pending_regen_count()
        target = self.clean_dir / "index-a.html"
        before_bytes = target.read_bytes()
        # 未知番地（claude 起動前に404）
        self._post({"folder": "mockups/.klk012_test_clean", "letter": "a",
                    "addr": "ZZZZ-01"})
        # 重複番地（claude 起動前に400）
        self._post({"folder": "mockups/.klk012_test_dup", "letter": "a",
                    "addr": "HERO-01"})
        after_bytes = target.read_bytes()
        after_count = self._pending_regen_count()
        self.assertEqual(before_bytes, after_bytes, "エラー経路で対象ファイルが変更された")
        self.assertEqual(before_count, after_count,
                         "エラー経路で .regen.json（ジョブ仕様）が作成された")


if __name__ == "__main__":
    unittest.main()
