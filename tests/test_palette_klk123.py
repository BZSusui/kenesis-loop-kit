# KLK-123 カタログ登録時の自動リサイズ（tester所有）。
#
# ★経緯: 理恵さんの明示的な要望（引き継ぎ書の保留中の宿題）
#   「カタログ登録時の自動リサイズ。shrink_one を /catalog-import 時に適用する形」
#   KLK-110 で「167枚 773MB → 217MB」と後からまとめて縮めた作業を、二度とやらずに済ませる。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk123.py … 組み込み位置・失敗時の振る舞い・記載
#   2. ここ … 純関数を**実画像**で突く。縮むこと／原本を壊さないこと／
#      壊れた入力でも例外を投げず登録を止めないこと
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk123.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("bridge_klk123_t", ROOT / "draft-gen" / "bridge.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def has_sips():
    return shutil.which("sips") is not None


def pixel_width(path):
    r = subprocess.run(["sips", "-g", "pixelWidth", str(path)], capture_output=True, text=True)
    vals = [l.split(":")[1].strip() for l in r.stdout.splitlines() if "pixelWidth" in l]
    return int(vals[0]) if vals else None


def make_png(path, width, height=120):
    """指定した幅の PNG を作る。**作れた幅まで確かめて**返す。

    ★「作れた」だけで判定すると、素材が壊れていて中身が別物でもテストが通ってしまう
      （実際に素材が 54 バイトのリンクで、確かめずに通していた）。
      期待した幅で作れなかったら None を返し、呼び手は skip する。
    """
    subprocess.run(["sips", "-s", "format", "png", "-z", str(height), str(width),
                    "/System/Library/CoreServices/DefaultDesktop.heic", "--out", str(path)],
                   capture_output=True, timeout=120)
    if not (os.path.isfile(path) and os.path.getsize(path) > 0):
        return None
    return pixel_width(path)


class TestKLK123Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk123.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("S3 ★画像移動のあと・catalog.json 保存の前に置く", p.stdout)


class TestShrinkRegisteredImage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load_bridge()
        cls.tmp = tempfile.mkdtemp(prefix="klk123_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_missing_file_is_safe(self):
        self.assertEqual(self.b.shrink_registered_image("/no/such/file.png")[:2], (0, 0))

    def test_broken_file_is_safe(self):
        p = os.path.join(self.tmp, "broken.png")
        with open(p, "wb") as fh:
            fh.write(b"not an image at all")
        size = os.path.getsize(p)
        before, after, _why = self.b.shrink_registered_image(p)
        self.assertEqual((before, after), (size, size), "壊れた画像でサイズが変わった")
        self.assertTrue(os.path.isfile(p), "壊れた画像が消えた")

    def test_missing_tool_is_safe(self):
        p = os.path.join(self.tmp, "x.png")
        with open(p, "wb") as fh:
            fh.write(b"x" * 100)
        before, after, why = self.b.shrink_registered_image(p, tool_path="/no/such/tool.py")
        self.assertEqual(before, after)
        self.assertIn("ツール", why)

    def test_no_temp_file_left_behind(self):
        p = os.path.join(self.tmp, "y.png")
        with open(p, "wb") as fh:
            fh.write(b"y" * 100)
        self.b.shrink_registered_image(p)
        self.assertFalse(os.path.isfile(p + ".shrink.tmp"), "一時ファイルが残った")

    def test_wide_png_is_shrunk(self):
        if not has_sips():
            self.skipTest("sips が無い環境（macOS 以外）")
        p = os.path.join(self.tmp, "wide.png")
        made = make_png(p, 2400)
        if made is None:
            self.skipTest("テスト用の画像を作れない環境")
        # ★縮める前に「本当に広い画像である」ことを確かめる（そうでなければ何も検証していない）
        self.assertEqual(made, 2400, "前提が崩れている: 2400px の画像を作れていない")
        before = os.path.getsize(p)
        b2, _a2, why = self.b.shrink_registered_image(p)
        self.assertEqual(b2, before)
        width = pixel_width(p)
        self.assertLessEqual(width, 1600, "横幅が縮んでいない（%s）" % why)
        self.assertLess(width, made, "幅が変わっていない（%s）" % why)
        self.assertTrue(os.path.isfile(p), "画像が消えた")

    def test_narrow_image_is_left_alone(self):
        if not has_sips():
            self.skipTest("sips が無い環境")
        p = os.path.join(self.tmp, "narrow.jpg")
        made = make_png(p, 800)
        if made is None:
            self.skipTest("テスト用の画像を作れない環境")
        self.assertEqual(made, 800, "前提が崩れている: 800px の画像を作れていない")
        subprocess.run(["sips", "-s", "format", "jpeg", p], capture_output=True, timeout=120)
        before = os.path.getsize(p)
        self.b.shrink_registered_image(p)
        self.assertEqual(pixel_width(p), 800, "縮める必要の無い画像を縮めた")
        self.assertLessEqual(os.path.getsize(p), before + 1024, "無駄に太らせた")


class TestRealCatalogUntouched(unittest.TestCase):
    """★この機能は**これから取り込む分**にしか効かない。既存の画像を触らないこと。"""

    def test_commit_only_touches_new_images(self):
        src = (ROOT / "draft-gen" / "bridge.py").read_text(encoding="utf-8")
        seg = src[src.index("def _catalog_commit"):src.index("def _catalog_delete")]
        # 軽量化の対象は planned（今回登録する分）だけ
        self.assertIn("for _src, dst, _e in planned:", seg)
        self.assertNotIn("glob", seg, "既存ファイルを走査していないこと")


if __name__ == "__main__":
    unittest.main()
