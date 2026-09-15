# KLK-128 一覧用のサムネイル画像（tester所有）。
#
# ★経緯: 理恵さんの環境で参考素材の枠だけが残り、画像が出なかった（再起動で復帰）。
#   点検したところ壊れたものは無く、原因は**原寸を一覧に並べていたこと**だった。
#   1500x12391px のような全ページ画像を 123x91px のカードで18枚並べると、
#   ブラウザの展開メモリが 634MB になる（実測）。167枚なら 5.8GB。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk128.py … 道具・配信・両画面の使い方・拡大は原寸・黙らないこと
#   2. ここ … 生成ツールの純関数を突く＋★実ブラウザで展開メモリを実測して比べる
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk128.py"
E2E = ROOT / "tests" / "site" / "e2e_klk128.node.js"
TOOL = ROOT / "tools" / "make-catalog-thumbs.py"

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


def load_tool():
    import importlib.util
    spec = importlib.util.spec_from_file_location("klk128_tool", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK128Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk128.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("B2 ★/catalog/thumb/ を配信する", p.stdout)
        self.assertIn("U2 ★生成設定画面が原寸へ戻す", p.stdout)


class TestThumbTool(unittest.TestCase):
    """生成ツールの純関数。ここが緩いと「作った」判定が空になる。"""

    @classmethod
    def setUpClass(cls):
        cls.m = load_tool()

    def test_only_images(self):
        self.assertTrue(self.m.is_image("a.PNG"))
        self.assertTrue(self.m.is_image("a.jpeg"))
        self.assertFalse(self.m.is_image("catalog.json"))
        self.assertFalse(self.m.is_image("a.txt"))

    def test_needs_thumb_rules(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "a.png")
            dst = os.path.join(d, "b.png")
            open(src, "wb").write(b"x")
            # 出力が無ければ作る
            self.assertTrue(self.m.needs_thumb(src, dst, False))
            open(dst, "wb").write(b"x")
            os.utime(dst, (os.path.getmtime(src) + 10, os.path.getmtime(src) + 10))
            # 出力のほうが新しければ据え置き
            self.assertFalse(self.m.needs_thumb(src, dst, False))
            # --force なら作り直す
            self.assertTrue(self.m.needs_thumb(src, dst, True))
            # 元が新しくなったら作り直す
            os.utime(src, (os.path.getmtime(dst) + 10, os.path.getmtime(dst) + 10))
            self.assertTrue(self.m.needs_thumb(src, dst, False))

    def test_does_not_write_into_the_source_dir(self):
        """★原寸を壊さない。出力先は catalog/thumb/ だけ。"""
        self.assertTrue(self.m.DST_DIR.endswith(os.path.join("catalog", "thumb")))
        self.assertTrue(self.m.SRC_DIR.endswith(os.path.join("catalog", "img")))
        self.assertNotEqual(self.m.SRC_DIR, self.m.DST_DIR)

    def test_make_one_reports_failure_instead_of_raising(self):
        """1枚失敗しても全体を止めない（取り込みを止めないための土台）。"""
        with tempfile.TemporaryDirectory() as d:
            before, after, what = self.m.make_one(
                self.m.load_shrink(), os.path.join(d, "ない.png"), os.path.join(d, "out.png"), 400, 80)
            self.assertEqual(before, 0)
            self.assertIn("失敗", what)


class TestKLK128E2E(unittest.TestCase):
    """★実効果: 実ブラウザで展開メモリを実測し、原寸のときと比べる。"""

    def test_list_uses_thumbnails_and_is_lighter(self):
        if not shutil.which("node"):
            self.skipTest("node が無い環境")
        ch = chrome_path()
        if not ch:
            self.skipTest("ヘッドレス Chrome が無い環境")
        env = dict(os.environ, KLK_E2E_CHROME=ch)
        p = subprocess.run(["node", str(E2E)], capture_output=True, text=True,
                           timeout=420, env=env, cwd=str(ROOT))
        if p.returncode == 3:
            self.skipTest("e2e が環境理由で SKIP: %s" % (p.stdout + p.stderr)[-300:])
        self.assertEqual(p.returncode, 0, "e2e_klk128.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("E2 ★展開メモリが原寸より1桁小さい", p.stdout)
        self.assertIn("E4 ★サムネイルが無いときは原寸で出る", p.stdout)


if __name__ == "__main__":
    unittest.main()
