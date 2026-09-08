# KLK-107 カタログ取り込みの不安定さを解消する（tester所有）。
#
# ★理恵さんの報告と、調べて分かったこと
#   「複数枚登録すると画面が何ページも開く／取り込みできなくなる」
#     ① 取り込みに枚数の上限が無く、.pending の全部を1セッションで処理していた
#        （実測 1枚110〜125秒。10枚溜まると約21分でタイムアウトに余裕なし）
#     ② 失敗しても画像が残るので、入れ直すと二重になり、再試行のたびに悪化した
#     ③ 二重起動で Python の生トレースバックを吐いて落ち、押し直すたびにタブが増えた
#
#   ★どれか1つ欠けると「失敗が次の失敗を呼ぶ」悪循環が復活する。
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk107.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "klk107w_bridge", str(ROOT / "draft-gen" / "bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK107Static(unittest.TestCase):
    def test_static_checks_pass(self):
        p = subprocess.run(["python3", str(STATIC_CHECKER)],
                           capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        self.assertEqual(p.returncode, 0, "check_klk107.py failed:\n" + p.stdout + p.stderr)


class TestKLK107BatchLimit(unittest.TestCase):
    """1回に処理する量を絞ること。"""

    def setUp(self):
        self.b = load_bridge()
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _mk(self, name, size=1000):
        with open(os.path.join(self.d, name), "wb") as fh:
            fh.write(bytes(size))
        return name

    def test_limit_is_calibrated_against_the_timeout(self):
        """実測（1枚125秒）に照らして、上限がタイムアウトの半分以内に収まること。

        ここが緩むと、また30分待って何も残らない失敗が起きる。
        """
        worst = self.b.CATALOG_IMPORT_MAX_FILES * 125
        self.assertLess(worst, self.b.BRIDGE_TIMEOUT_SEC / 2,
                        "%d枚は最悪 %d 秒。タイムアウト %d 秒に対して余裕が無い"
                        % (self.b.CATALOG_IMPORT_MAX_FILES, worst, self.b.BRIDGE_TIMEOUT_SEC))

    def test_defers_rest_instead_of_refusing(self):
        """★超えた分は「断る」のではなく「次回へ回す」。

        断るだけだと、利用者は何枚なら通るのか分からず自分で選び直す羽目になる。
        """
        names = [self._mk("%d.jpg" % i) for i in range(5)]
        take, rest, _ = self.b.split_import_batch(self.d, names)
        self.assertEqual(len(take), self.b.CATALOG_IMPORT_MAX_FILES)
        self.assertEqual(len(rest), 5 - len(take))
        self.assertEqual(take + rest, names, "取りこぼしや重複がある")

    def test_single_oversized_file_is_still_processed(self):
        """1枚で上限を超えても処理する。でないと永久に取り込めない画像ができる。"""
        n = self._mk("huge.jpg", (self.b.CATALOG_IMPORT_MAX_BYTES * 2))
        take, rest, _ = self.b.split_import_batch(self.d, [n])
        self.assertEqual(take, [n])
        self.assertEqual(rest, [])

    def test_missing_file_does_not_crash(self):
        """途中で消えたファイルがあっても落ちない（fail-open）。"""
        take, rest, _ = self.b.split_import_batch(self.d, ["gone.jpg"])
        self.assertEqual(take, ["gone.jpg"])


class TestKLK107DuplicateUpload(unittest.TestCase):
    """同じ画像を二重に溜めないこと。"""

    def setUp(self):
        self.b = load_bridge()
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_detects_by_content_not_by_name(self):
        """★保存名はサーバが uuid で作るので、名前では判定できない。"""
        raw = b"\xff\xd8\xff" + b"payload" * 50
        with open(os.path.join(self.d, "pnd-aaa.jpg"), "wb") as fh:
            fh.write(raw)
        self.assertEqual(self.b.find_duplicate_pending(self.d, raw), "pnd-aaa.jpg")

    def test_different_content_is_not_a_duplicate(self):
        raw = b"\xff\xd8\xff" + b"payload" * 50
        with open(os.path.join(self.d, "pnd-aaa.jpg"), "wb") as fh:
            fh.write(raw)
        self.assertIsNone(self.b.find_duplicate_pending(self.d, raw + b"x"))

    def test_same_size_different_content_is_not_a_duplicate(self):
        """サイズで先に弾く実装なので、同サイズ別内容で誤検出しないことを見る。"""
        a = b"\xff\xd8\xff" + b"A" * 100
        c = b"\xff\xd8\xff" + b"B" * 100
        with open(os.path.join(self.d, "pnd-aaa.jpg"), "wb") as fh:
            fh.write(a)
        self.assertIsNone(self.b.find_duplicate_pending(self.d, c))

    def test_non_image_files_are_ignored(self):
        """ジョブ仕様(.import.json)などを重複判定に巻き込まない。"""
        raw = b"{}"
        with open(os.path.join(self.d, "job.import.json"), "wb") as fh:
            fh.write(raw)
        self.assertIsNone(self.b.find_duplicate_pending(self.d, raw))


class TestKLK107DoubleLaunch(unittest.TestCase):
    """二重起動でトレースバックを見せないこと。"""

    def setUp(self):
        self.b = load_bridge()

    def test_no_false_positive_on_free_port(self):
        self.assertFalse(self.b.is_bridge_already_running("127.0.0.1", 59998))

    def test_detects_a_running_bridge(self):
        """実際にブリッジを起動して、検出できること。"""
        import time
        import urllib.request
        port = 8814
        env = dict(os.environ, KLK_BRIDGE_PORT=str(port))
        pr = subprocess.Popen(["python3", str(ROOT / "draft-gen" / "bridge.py")],
                              cwd=str(ROOT), env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            up = False
            for _ in range(40):
                try:
                    urllib.request.urlopen(
                        "http://127.0.0.1:%d/health" % port, timeout=0.4).read()
                    up = True
                    break
                except Exception:
                    time.sleep(0.15)
            if not up:
                self.skipTest("ブリッジを起動できなかった")
            self.assertTrue(self.b.is_bridge_already_running("127.0.0.1", port))
        finally:
            pr.terminate()
            try:
                pr.wait(timeout=5)
            except Exception:
                pr.kill()

    def test_second_launch_exits_cleanly_without_traceback(self):
        """★同じポートで2度目を起動しても、生のトレースバックを出さないこと。

        利用者はこれを見て「何が起きたか分からない」まま押し直し、
        そのたびに設定画面のタブが増えていた。
        """
        import time
        import urllib.request
        port = 8815
        env = dict(os.environ, KLK_BRIDGE_PORT=str(port))
        first = subprocess.Popen(["python3", str(ROOT / "draft-gen" / "bridge.py")],
                                 cwd=str(ROOT), env=env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            up = False
            for _ in range(40):
                try:
                    urllib.request.urlopen(
                        "http://127.0.0.1:%d/health" % port, timeout=0.4).read()
                    up = True
                    break
                except Exception:
                    time.sleep(0.15)
            if not up:
                self.skipTest("ブリッジを起動できなかった")
            second = subprocess.run(["python3", str(ROOT / "draft-gen" / "bridge.py")],
                                    cwd=str(ROOT), env=env,
                                    capture_output=True, text=True, timeout=30)
            out = (second.stderr or "") + (second.stdout or "")
            self.assertNotIn("Traceback", out, "トレースバックを見せている")
            self.assertNotIn("Address already in use", out, "生のエラーを見せている")
            self.assertIn("すでに起動しています", out, "分かる言葉で案内していない")
            self.assertEqual(second.returncode, 0, "異常終了扱いになっている")
        finally:
            first.terminate()
            try:
                first.wait(timeout=5)
            except Exception:
                first.kill()


if __name__ == "__main__":
    unittest.main()
