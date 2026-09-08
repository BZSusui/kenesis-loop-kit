# KLK-110 配布用にカタログ画像を軽くする（tester所有）。
#
# ★経緯: 理恵さんのご指示は「長辺1600pxへ縮小」だったが、調べたら使えなかった。
#   ・実績画像は縦長のフルページで、167枚のうち118枚が縦が横の3倍以上（最大17.2倍）。
#     長辺で揃えると横幅が93〜194pxまで潰れ、**実績が読めなくなる**。
#   ・`sips -Z` は小さい画像を拡大する（1253x1589 → 1261x1600）。
#   事実を報告して「横幅基準 ＋ PNG→JPEG」で合意した（773MB → 217MB・72%減）。
#
# ★守るべき優先順位: 「軽くすること」より「実績が読めること」。
import importlib.util
import io
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "shrink-catalog-images.py"
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk110.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("klk110w", str(TOOL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def dim(p):
    r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(p)],
                       capture_output=True, text=True, timeout=30).stdout
    m = re.findall(r":\s*(\d+)", r)
    return (int(m[0]), int(m[1])) if len(m) >= 2 else (0, 0)


class TestKLK110Static(unittest.TestCase):
    def test_static_checks_pass(self):
        p = subprocess.run(["python3", str(STATIC_CHECKER)],
                           capture_output=True, text=True, cwd=str(ROOT), timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk110.py failed:\n" + p.stdout + p.stderr)


class TestKLK110NeverUpscales(unittest.TestCase):
    """★拡大しないこと。`sips -Z` の罠。"""

    def setUp(self):
        self.m = load_tool()

    def test_at_or_below_limit_is_untouched(self):
        for w in (1, 800, 1599, 1600):
            with self.subTest(w):
                self.assertFalse(self.m.needs_resize(w, 1600))

    def test_above_limit_is_resized(self):
        for w in (1601, 2506, 4000):
            with self.subTest(w):
                self.assertTrue(self.m.needs_resize(w, 1600))

    def test_unknown_width_is_left_alone(self):
        for bad in (None, "x", -1, 0):
            with self.subTest(bad):
                self.assertFalse(self.m.needs_resize(bad, 1600))


class TestKLK110UsesWidthNotLongEdge(unittest.TestCase):
    """★長辺基準へ逆戻りしないこと。これが一番避けたい失敗。"""

    def test_tool_resizes_by_width(self):
        s = TOOL.read_text(encoding="utf-8")
        self.assertIn("--resampleWidth", s)
        self.assertNotIn('"-Z"', s,
                         "sips -Z は長辺基準。縦長画像の横幅が潰れ、実績が読めなくなる")

    def test_reason_is_recorded(self):
        """なぜ横幅基準なのかが残っていること（また長辺に戻されないため）。"""
        s = TOOL.read_text(encoding="utf-8")
        self.assertIn("横幅", s)
        self.assertIn("長辺", s)
        self.assertIn("118枚", s, "実測の根拠が残っていない")


@unittest.skipUnless(shutil.which("sips") and (ROOT / "catalog" / "img").is_dir(),
                     "sips または catalog/img が無い環境")
class TestKLK110AgainstRealImages(unittest.TestCase):
    """★実データで、実績が読める状態を保つか。"""

    MIN_READABLE_WIDTH = 700

    @classmethod
    def setUpClass(cls):
        cls.m = load_tool()
        files = sorted((ROOT / "catalog" / "img").glob("*"))
        ratios = []
        for p in files:
            w, h = dim(p)
            if w:
                ratios.append((h / w, p))
        ratios.sort()
        # 極端な形状を必ず含める
        cls.picks = sorted({ratios[-1][1], ratios[0][1],
                            min(files, key=lambda p: p.stat().st_size),
                            max(files, key=lambda p: p.stat().st_size)})
        cls.max_ratio = ratios[-1][0]
        cls.wd = tempfile.mkdtemp()
        src = os.path.join(cls.wd, "src")
        cls.dst = os.path.join(cls.wd, "dst")
        os.makedirs(src)
        cls.before = {}
        for p in cls.picks:
            shutil.copy2(p, os.path.join(src, p.name))
            cls.before[p.name] = p.stat().st_size
        cls.m.shrink_all(src, cls.dst, quiet=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.wd, ignore_errors=True)

    def test_aspect_ratio_preserved(self):
        for p in self.picks:
            with self.subTest(p.name):
                a, b = dim(p), dim(os.path.join(self.dst, p.name))
                if not (a[0] and b[0]):
                    continue
                self.assertAlmostEqual(a[1] / a[0], b[1] / b[0], delta=0.02)

    def test_width_stays_readable(self):
        """★★縦長画像の横幅が読める大きさで残ること。

        縦横比の検査だけでは足りない。長辺基準は比率を保ったまま横幅を
        93〜194px まで潰すので「比率OK」で通り抜ける（実際に通した）。
        """
        for p in self.picks:
            with self.subTest(p.name):
                a, b = dim(p), dim(os.path.join(self.dst, p.name))
                if a[0] < self.MIN_READABLE_WIDTH:
                    continue
                self.assertGreaterEqual(
                    b[0], self.MIN_READABLE_WIDTH,
                    "%s の横幅が %dpx → %dpx。実績が読めない（最大縦横比 %.1f 倍）"
                    % (p.name, a[0], b[0], self.max_ratio))

    def test_never_wider_than_limit(self):
        for p in self.picks:
            with self.subTest(p.name):
                self.assertLessEqual(dim(os.path.join(self.dst, p.name))[0],
                                     self.m.DEFAULT_WIDTH)

    def test_filenames_unchanged(self):
        """★catalog.json は名前で参照している。拡張子を変えると参照が切れる。"""
        for p in self.picks:
            with self.subTest(p.name):
                self.assertTrue(os.path.isfile(os.path.join(self.dst, p.name)))

    def test_output_is_a_displayable_image(self):
        for p in self.picks:
            with self.subTest(p.name):
                head = io.open(os.path.join(self.dst, p.name), "rb").read(4)
                self.assertTrue(head[:2] == b"\xff\xd8" or head[:4] == b"\x89PNG",
                                "ブラウザが表示できない形式")

    def test_originals_untouched(self):
        """★元画像を書き換えないこと。取り返しがつかない。"""
        for p in self.picks:
            with self.subTest(p.name):
                self.assertEqual(p.stat().st_size, self.before[p.name])


class TestKLK110Packaging(unittest.TestCase):
    """パッケージ作成に組み込まれ、失敗しても配布を止めないこと。"""

    def setUp(self):
        self.pkg = (ROOT / "tools" / "make-package.sh").read_text(encoding="utf-8")

    def test_wired_into_with_catalog(self):
        self.assertIn("shrink-catalog-images.py", self.pkg)

    def test_fails_soft(self):
        self.assertIn("元のサイズでコピー", self.pkg,
                      "軽量化の失敗で配布が止まってはいけない（見た目の話）")

    def test_rollback_does_not_undo_the_resize(self):
        """★「軽くならなければ元に戻す」が横幅の縮小まで巻き戻さないこと。

        JPEG は再エンコードで増えることがあり、そのせいで
        2506px のまま残った画像が12枚あった（実装時に全数調査で判明）。
        """
        s = TOOL.read_text(encoding="utf-8")
        self.assertIn('"幅" not in " ".join(actions)', s)
        self.assertIn("12枚", s, "経緯が残っていない")


if __name__ == "__main__":
    unittest.main()
