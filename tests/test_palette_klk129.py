# KLK-129 せり出し横長画像の文言側が狭い（tester所有）。
#
# ★経緯: 規約は「半分ずつ（1fr 1fr）」と書いていたが、`1fr` は `minmax(auto,1fr)` で
#   中身の最小幅より小さくならない。画像側のアタリにある「検索: …」の折り返さない一行が
#   列を押し広げ、文言側だけが 273px まで削られていた（実測・全体860px）。
#   見出しが2行に割れ、本文も数文字ごとに折り返していた。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk129.py … 規約の書き方・見本の追従・ゴールデン不変
#   2. ここ … 規約を読む純関数を突く＋★実ブラウザで列幅を実測する
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk129.py"
E2E = ROOT / "tests" / "site" / "e2e_klk129.node.js"
SAMPLE = ROOT / "samples" / "03_クリニック_ナビ下配置" / "index-a.html"

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
    src = STATIC.read_text(encoding="utf-8")
    cut = src.index("RULES = io.open(")
    ns = {"__file__": str(STATIC)}
    exec(compile(src[:cut], str(STATIC), "exec"), ns)
    # body だけ使うので、依存する関数は改めて読み込む
    start = src.index("def overlap_rule(")
    end = src.index("# ---", start)
    exec(compile(src[start:end], str(STATIC), "exec"), ns)
    return ns


class TestKLK129Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk129.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("R2 ★列の書き方を指示している", p.stdout)
        self.assertIn("G1 ★ゴールデンを書き換えていない", p.stdout)


class TestOverlapRuleReader(unittest.TestCase):
    """列指定を読み取る純関数。ここが緩いと「直っている」判定が空になる。"""

    @classmethod
    def setUpClass(cls):
        cls.c = load_checker_functions()

    def test_reads_the_column_rule(self):
        got = self.c["overlap_rule"](SAMPLE.read_text(encoding="utf-8"))
        self.assertIsNotNone(got, "列指定を読み取れない")
        self.assertIn("480px", got)
        self.assertIn("minmax", got)

    def test_detects_the_old_form(self):
        # 妨害: 不具合当時の書き方に戻したら「直っている」と言わないこと
        src = SAMPLE.read_text(encoding="utf-8")
        broken = src.replace("minmax(0,1fr) minmax(0,480px)", "1fr 1fr", 1)
        self.assertNotEqual(broken, src, "妨害注入が効いていない")
        got = self.c["overlap_rule"](broken)
        self.assertEqual(got, "1fr 1fr")
        self.assertNotIn("480px", got)

    def test_returns_none_when_absent(self):
        self.assertIsNone(self.c["overlap_rule"]("<html>なにもない</html>"))


class TestKLK129E2E(unittest.TestCase):
    """★実効果: 見本を実描画し、ブラウザが決めた列幅を測る。"""

    def test_text_side_is_wide_enough(self):
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
        self.assertEqual(p.returncode, 0, "e2e_klk129.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("E1 ★白背景の文言側が 460px 以上ある", p.stdout)
        self.assertIn("E5 ★`1fr 1fr` に戻すと文言側が痩せる", p.stdout)


if __name__ == "__main__":
    unittest.main()
