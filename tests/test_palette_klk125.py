# KLK-125 SCR-001 の型選択に日本語ラベルを出す（tester所有）。
#
# ★経緯: KLK-117 で型の日本語ラベルを入れたが、**比較画面にしか適用していなかった**。
#   SCR-001（生成設定）の「行ごとの設定 → レイアウト型」は英語マーカーのみで、
#   理恵さんが見る2箇所のうち片方が取り残されていた（KLK-124 の調査で判明）。
#   KLK-124 の段取りの**第1段**。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk125.py … ラベル表が bridge（正）と一字一句一致すること・画面の作り
#   2. ここ … 写しの純関数を突く＋★実ブラウザで描かれた選択肢を見る
import importlib.util
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk125.py"
E2E = ROOT / "tests" / "site" / "e2e_klk125.node.js"

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
)


def chrome_path():
    for c in CHROME_CANDIDATES:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def load_checker_functions():
    """checker を『関数だけ』読み込む（実行すると全チェックが走るため・klk111 と同じ作法）。"""
    src = STATIC.read_text(encoding="utf-8")
    cut = src.index("b = load_bridge()")
    ns = {"__file__": str(STATIC)}
    exec(compile(src[:cut], str(STATIC), "exec"), ns)
    return ns


def load_bridge():
    spec = importlib.util.spec_from_file_location("bridge_klk125_t", ROOT / "draft-gen" / "bridge.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK125Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk125.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("V3 ★84型すべてのラベルが bridge と一字一句一致する", p.stdout)


class TestLabelParser(unittest.TestCase):
    """写しを読む純関数。ここが緩いと「一致している」判定が空になる。"""

    @classmethod
    def setUpClass(cls):
        cls.c = load_checker_functions()
        cls.b = load_bridge()

    def test_parses_all_84(self):
        src = (ROOT / "draft-gen" / "index.html").read_text(encoding="utf-8")
        got = self.c["js_labels"](src)
        self.assertIsNotNone(got, "写しをパースできない")
        self.assertEqual(sum(len(v) for v in got.values()), 84)

    def test_matches_bridge_exactly(self):
        src = (ROOT / "draft-gen" / "index.html").read_text(encoding="utf-8")
        got = self.c["js_labels"](src)
        for sec, tbl in self.b.SECTION_TYPE_LABELS.items():
            with self.subTest(sec=sec):
                self.assertEqual(got.get(sec), tbl, "%s のラベルが bridge と違う" % sec)

    def test_parser_detects_a_changed_label(self):
        # 妨害: 写しのラベルを1つ書き換えたら「一致」と言わないこと
        src = (ROOT / "draft-gen" / "index.html").read_text(encoding="utf-8")
        base = self.c["js_labels"](src)
        broken = src.replace("'横並びリスト'", "'よこならびりすと'", 1)
        self.assertNotEqual(broken, src, "妨害注入が効いていない")
        got = self.c["js_labels"](broken)
        self.assertNotEqual(got, base, "書き換えを検知できない")

    def test_parser_returns_none_when_absent(self):
        self.assertIsNone(self.c["js_labels"]("<html>なにもない</html>"))


class TestKLK125E2E(unittest.TestCase):
    """★実効果: 実際に描かれた <option> の文字を見る。"""

    def test_options_show_japanese_labels(self):
        if not shutil.which("node"):
            self.skipTest("node が無い環境")
        ch = chrome_path()
        if not ch:
            self.skipTest("ヘッドレス Chrome が無い環境")
        env = dict(os.environ, KLK_E2E_CHROME=ch)
        p = subprocess.run(["node", str(E2E)], capture_output=True, text=True,
                           timeout=300, env=env, cwd=str(ROOT))
        if p.returncode == 3:
            self.skipTest("e2e が環境理由で SKIP: %s" % (p.stdout + p.stderr)[-300:])
        self.assertEqual(p.returncode, 0, "e2e_klk125.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("E2 ★選択肢が「日本語ラベル（マーカー）」で描かれる", p.stdout)
        self.assertIn("E3 ★option の value はマーカーのまま", p.stdout)


if __name__ == "__main__":
    unittest.main()
