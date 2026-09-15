# KLK-131 配布パッケージにサムネイルが入っていない（tester所有）。
#
# ★経緯: パッケージ化の依頼を受けて点検したところ、--with-catalog が
#   catalog/img と catalog.json しか写しておらず、KLK-128 の catalog/thumb/ が
#   配布物に入らなかった。表示は壊れないが原寸へ戻るため、直した重さが元通りになる。
#   あわせて、空のカタログで「絞り込みを変えてみてください」と出ていたのを直した
#   （1件も無いのだから変えても出ない。パッケージBを初めて使う人が迷う）。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk131.py … パッケージの手順・ツールの引数・画面の出し分け
#   2. ここ … 引数を読む純関数を突く＋★実際に小さなパッケージを組んで中身を見る
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk131.py"
TOOL = ROOT / "tools" / "make-catalog-thumbs.py"


def load_tool():
    import importlib.util
    spec = importlib.util.spec_from_file_location("klk131_tool", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK131Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk131.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("P1 ★--with-catalog でサムネイルを作る", p.stdout)


class TestArgParsing(unittest.TestCase):
    """引数を読む純関数。ここが緩いと「配布物の中で作れている」判定が空になる。"""

    @classmethod
    def setUpClass(cls):
        cls.m = load_tool()

    def test_defaults_unchanged(self):
        src, dst, w, q, force = self.m.parse_args([])
        self.assertTrue(src.endswith(os.path.join("catalog", "img")))
        self.assertTrue(dst.endswith(os.path.join("catalog", "thumb")))
        self.assertEqual(w, self.m.DEFAULT_WIDTH)
        self.assertFalse(force)

    def test_src_and_out_are_honoured(self):
        src, dst, w, q, force = self.m.parse_args(["--src=/tmp/a", "--out=/tmp/b"])
        self.assertEqual(src, "/tmp/a")
        self.assertEqual(dst, "/tmp/b")

    def test_width_quality_force(self):
        src, dst, w, q, force = self.m.parse_args(["--force", "--width", "200", "--quality", "60"])
        self.assertEqual((w, q, force), (200, 60, True))

    def test_out_does_not_default_to_src(self):
        """★出力先を指定しなかったときに、元画像の場所へ書かないこと。"""
        src, dst, _w, _q, _f = self.m.parse_args(["--src=/tmp/onlysrc"])
        self.assertNotEqual(src, dst)


class TestPackageContents(unittest.TestCase):
    """★実効果: 小さなカタログで実際にパッケージを組み、中身を数える。"""

    def test_with_catalog_package_contains_thumbs(self):
        if not shutil.which("bash"):
            self.skipTest("bash が無い環境")
        cat = ROOT / "catalog" / "img"
        if not cat.is_dir() or len(list(cat.iterdir())) < 3:
            self.skipTest("実績カタログが無い環境（catalog/ は Git 管理外）")
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "pkg")
            p = subprocess.run(["bash", str(ROOT / "tools" / "make-package.sh"), dest, "--with-catalog"],
                               capture_output=True, text=True, timeout=1800, cwd=str(ROOT))
            self.assertEqual(p.returncode, 0, "パッケージ作成に失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
            img = os.path.join(dest, "catalog", "img")
            thumb = os.path.join(dest, "catalog", "thumb")
            self.assertTrue(os.path.isdir(thumb), "catalog/thumb/ が入っていない")
            imgs = sorted(os.listdir(img))
            thumbs = sorted(os.listdir(thumb))
            self.assertEqual(imgs, thumbs, "画像とサムネイルの顔ぶれが一致しない")
            # ★サムネイルは原寸より確実に軽いこと（入っているだけでは意味がない）
            si = sum(os.path.getsize(os.path.join(img, f)) for f in imgs)
            st = sum(os.path.getsize(os.path.join(thumb, f)) for f in thumbs)
            self.assertLess(st * 2, si, "サムネイルが軽くなっていない（%d → %d バイト）" % (si, st))

    def test_without_catalog_package_has_no_images(self):
        if not shutil.which("bash"):
            self.skipTest("bash が無い環境")
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "pkg")
            p = subprocess.run(["bash", str(ROOT / "tools" / "make-package.sh"), dest],
                               capture_output=True, text=True, timeout=600, cwd=str(ROOT))
            self.assertEqual(p.returncode, 0, "パッケージ作成に失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
            cat = os.path.join(dest, "catalog")
            files = []
            for root, _dirs, names in os.walk(cat):
                files.extend(os.path.join(root, n) for n in names)
            self.assertEqual(files, [], "カタログ無しの配布物にファイルが入っている: %s" % files[:5])


if __name__ == "__main__":
    unittest.main()
