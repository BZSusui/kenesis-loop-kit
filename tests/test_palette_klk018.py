# KLK-018 ブリッジ成功判定の堅牢化（終了コード単独判定→成果物ベース・失敗message
# 日本語化・生JSON非露出）のテストを unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的/コア）: tests/site/check_klk018.py（S1-S9・Python標準のみ・
#   対象＝draft-gen/bridge.py(import 純関数 is_job_success + ソース静的検査)）。
# - D群（動的）:
#   - D1: `python3 -m unittest discover -s tests` の回帰全緑（NFR-006）は
#     スイート全体の実行そのものが担保する。ここでは S群 subprocess 実行を束ねる。
#   - D2: `python3 tests/site/check_klk018.py` を subprocess 実行し exit0 を確認。
#   - D3: subprocess.run を「returncode=1」noop に差し替え、mockups/ 配下（Git除外）に
#     表示物を置いた状態で live サーバ経由に POST /generate を投げ、非0でも成果物ありで
#     state=="done"（成功合流）／成果物なしで state=="error" かつ message が日本語要約
#     （usage/cost/total_cost_usd 等の生JSON非露出）になることを確認する（設計 §9 D3・
#     KLK-012 の live防御テストと同型。claude は実起動しない＝noop 化）。
#
# M群（実ブリッジ起動＋ブラウザ実機での成功/失敗表示の目視）は自動化不能のため
# tester=人間（理恵さん）が手動確認しチケットのログへ記録する。
# check_klk002〜017（既存 S群）は各チケットの正のため触らない（本ラッパーは独立）。
import datetime
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
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk018.py"
BRIDGE_PATH = ROOT / "draft-gen" / "bridge.py"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("klk018_bridge_live", str(BRIDGE_PATH))
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


class TestKLK018Static(unittest.TestCase):
    """D2: check_klk018.py（設計書 KLK-018 §9 S群 S1-S9）が全PASS（exit0）すること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk018.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(_can_bind_localhost(), "127.0.0.1 へ bind できないため /generate 動的検証をskip")
class TestKLK018SuccessDetection(unittest.TestCase):
    """D3: 非0終了でも成果物の有無で成否を決めることを live サーバで動的確認。

    claude は実起動しない（subprocess.run を returncode=1 の noop に差し替え）。
    - 成果物あり: 表示物（index.html）を先に置いた状態 → state=="done"（非0でも成功合流）。
    - 成果物なし: 表示物を置かない → state=="error" かつ message は日本語要約で
      使用量JSON（usage/cost/total_cost_usd）を含まない（生JSON非露出）。
    """

    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge()
        # subprocess.run を「claude が非0で終了」する noop に差し替え。
        # 起動時のブラウザ自動オープン・表示物オープンも同じ noop を通り無害（rc=1）。
        cls._orig_run = cls.bridge.subprocess.run
        cls.bridge.subprocess.run = lambda *a, **k: types.SimpleNamespace(
            returncode=1, stdout='{"total_cost_usd":0.42,"usage":{"input_tokens":1}}', stderr="")

        cls.port = _free_port()
        cls.origin = "http://127.0.0.1:{0}".format(cls.port)
        cls.created_dirs = []

        cls._server_thread = threading.Thread(
            target=cls.bridge._run_server, args=(cls.port,), daemon=True)
        cls._server_thread.start()
        if not cls._wait_health(cls.port, timeout=8.0):
            cls.tearDownClass()
            raise unittest.SkipTest("ブリッジが起動しなかったため /generate 動的検証をskip")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_orig_run", None) is not None:
            cls.bridge.subprocess.run = cls._orig_run
        for d in getattr(cls, "created_dirs", []):
            if d and Path(d).exists():
                shutil.rmtree(d, ignore_errors=True)

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
    def _instruction(self, project, variants):
        return {
            "schema": "design-draft-instruction",
            "version": 1,
            "meta": {"project": project},
            "industry": {"resolved": "カフェ"},
            "layout": {"columns": "1col"},
            "colors": {"main": "#3366cc"},
            "output": {"variants": variants},
        }

    def _post_generate(self, instruction):
        payload = json.dumps(instruction).encode("utf-8")
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5.0)
        conn.putrequest("POST", "/generate")
        conn.putheader("Origin", self.origin)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(len(payload)))
        conn.endheaders()
        conn.send(payload)
        res = conn.getresponse()
        status = res.status
        data = json.loads(res.read().decode("utf-8"))
        conn.close()
        return status, data

    def _poll_status(self, job_id, timeout=8.0):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            conn = HTTPConnection("127.0.0.1", self.port, timeout=2.0)
            conn.request("GET", "/status/" + job_id)
            res = conn.getresponse()
            last = json.loads(res.read().decode("utf-8"))
            conn.close()
            if last.get("state") in ("done", "error"):
                return last
            time.sleep(0.1)
        return last

    def _expected_abs_target(self, project, variants):
        """worker と同じ純関数で表示物の絶対パスを決定論的に構築する。"""
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        folder = self.bridge.build_folder(date_str, project)
        open_target = self.bridge.select_open_target(folder, variants)
        abs_target = os.path.join(self.bridge.repo_root(), open_target)
        return folder, abs_target

    # -- tests -------------------------------------------------------------
    def test_d3_nonzero_with_artifact_is_done(self):
        """非0終了でも表示物が存在すれば state=="done"（成果物あり優先の成功合流）。"""
        project = "klk018_test_done"
        variants = 1
        folder, abs_target = self._expected_abs_target(project, variants)
        abs_dir = os.path.join(self.bridge.repo_root(), folder)
        self.created_dirs.append(abs_dir)
        os.makedirs(abs_dir, exist_ok=True)
        # 表示物（index.html）を先に置く → os.path.exists(abs_target)==True。
        with open(abs_target, "w", encoding="utf-8") as fh:
            fh.write("<!doctype html><title>klk018</title>")

        st, data = self._post_generate(self._instruction(project, variants))
        self.assertEqual(st, 202, "POST /generate は 202 を返すべき")
        result = self._poll_status(data["jobId"])
        self.assertIsNotNone(result, "status がタイムアウトした")
        self.assertEqual(
            result.get("state"), "done",
            "非0終了でも成果物ありなら done になるべき: {0}".format(result))

    def test_d3_nonzero_without_artifact_is_error_japanese(self):
        """非0終了かつ表示物なしなら state=="error" かつ message は日本語要約（生JSON非露出）。"""
        project = "klk018_test_error"
        variants = 1
        folder, abs_target = self._expected_abs_target(project, variants)
        # 表示物を置かない（存在しないことを保証）。
        self.assertFalse(os.path.exists(abs_target), "前提: 表示物は存在しないこと")

        st, data = self._post_generate(self._instruction(project, variants))
        self.assertEqual(st, 202, "POST /generate は 202 を返すべき")
        result = self._poll_status(data["jobId"])
        self.assertIsNotNone(result, "status がタイムアウトした")
        self.assertEqual(
            result.get("state"), "error",
            "非0終了かつ成果物なしなら error になるべき: {0}".format(result))
        msg = result.get("message") or ""
        self.assertIn("生成できませんでした", msg, "日本語の失敗要約であるべき: " + msg)
        for tok in ("total_cost_usd", "usage", "cost", "input_tokens"):
            self.assertNotIn(
                tok, msg, "失敗message に生JSONトークン '{0}' が露出している: {1}".format(tok, msg))


if __name__ == "__main__":
    unittest.main()
