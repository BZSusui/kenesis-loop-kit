# KLK-126 型ピッカーを図解アイコンのモーダルにする（tester所有）。
#
# ★経緯: 型を選ぶ UI は KLK-117/125 で「日本語ラベル（マーカー）」まで来たが、
#   <option> の中には図を描けない。KLK-124 の検証の結論どおり、
#   セレクタ自体をアイコン付きの一覧へ作り替えたのがこのチケット（第1段＝SCR-002）。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk126.py … レシピが全マーカーを覆う・select を残す・外部依存ゼロ
#   2. ここ … レシピを読む純関数を突く＋★実ブラウザで開いて選んで実測する
import importlib.util
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk126.py"
E2E = ROOT / "tests" / "site" / "e2e_klk126.node.js"
TPL = ROOT / "draft-gen" / "compare_template.html"

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
    """checker を『関数だけ』読み込む（実行すると全チェックが走るため・klk125 と同じ作法）。"""
    src = STATIC.read_text(encoding="utf-8")
    cut = src.index("b = load_bridge()")
    ns = {"__file__": str(STATIC)}
    exec(compile(src[:cut], str(STATIC), "exec"), ns)
    return ns


def load_bridge():
    spec = importlib.util.spec_from_file_location("bridge_klk126_t", ROOT / "draft-gen" / "bridge.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK126Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk126.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("R2 ★プールの全マーカーにレシピがある", p.stdout)
        self.assertIn("K2 <select> は hidden で隠してある", p.stdout)


class TestRecipeParser(unittest.TestCase):
    """レシピ表を読む純関数。ここが緩いと「全部ある」判定が空になる。"""

    @classmethod
    def setUpClass(cls):
        cls.c = load_checker_functions()
        cls.b = load_bridge()
        cls.src = TPL.read_text(encoding="utf-8")

    def test_covers_every_marker_in_the_pools(self):
        keys = self.c["recipe_keys"](self.src)
        needed = sorted({t for pool in self.b.SECTION_TYPE_POOLS.values() for t in pool})
        self.assertIsNotNone(keys, "レシピ表をパースできない")
        self.assertEqual(sorted(set(keys)), needed, "レシピとプールが食い違う")

    def test_parser_detects_a_removed_recipe(self):
        # 妨害: レシピを1つ消したら「全部ある」と言わないこと
        base = self.c["recipe_keys"](self.src)
        broken = self.src.replace("      'pat-cards':      { k:'grid', cols:3, cell:'img+2' },\n", "", 1)
        self.assertNotEqual(broken, self.src, "妨害注入が効いていない")
        got = self.c["recipe_keys"](broken)
        self.assertNotIn("pat-cards", got, "消したレシピを検知できない")
        self.assertEqual(len(base) - 1, len(got))

    def test_parser_returns_none_when_absent(self):
        self.assertIsNone(self.c["recipe_keys"]("<html>なにもない</html>"))

    def test_shares_icons_across_sections(self):
        """★セクションを跨いで同じ内容の型は同じ絵を指す（理恵さんの方針）。

        規約が「流用」「同機構」と書いている群が根拠。ここでは代表例を1つ固定しておく。
        絵の数を数えるのではなく、**同じであるべき組が同じか**を見る。
        """
        import re
        body = re.search(r"var\s+ICONS\s*=\s*\{(.*?)\n\s*\};", self.src, re.S).group(1)
        recipes = dict(re.findall(r"^\s*'([^']+)':\s*(\{.*?\}),\s*(?://.*)?$", body, re.M))
        for a, b in [("pat-cards", "news-cards"), ("faq-accordion", "news-accordion"),
                     ("pat-zigzag", "img-zigzag"), ("overlap", "img-overlap")]:
            with self.subTest(pair=(a, b)):
                self.assertEqual(recipes[a], recipes[b], "%s と %s は同じ絵であるべき" % (a, b))


class TestKLK126E2E(unittest.TestCase):
    """★実効果: 実ブラウザで開いて選び、位置と大きさを実測する。"""

    def test_picker_opens_and_picks(self):
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
        self.assertEqual(p.returncode, 0, "e2e_klk126.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("E4 ★行を押すと <select> の値がそのマーカーになり", p.stdout)
        self.assertIn("E8 ★375px でも1行が保たれ", p.stdout)


if __name__ == "__main__":
    unittest.main()
