# KLK-092 1案生成の機能同等化を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk092.py（R群=規約 / K群=スキル / T群=検証の道具）
# - 追加: **機能同等性チェックが実際に欠落を捕まえるか**を合成HTMLで確かめる。
#
#   ★理恵さんの実使用で「1案だと幅切替も 🔄 も無い」が発覚した。
#     規約自身が「1案には幅切替が無い」と書いており、**仕様の文章が機能の欠落を
#     正当化していた**。同じことを繰り返さないよう、道具側で見張る。
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk092.py"
TOOL = ROOT / "tools" / "verify-mockup.py"

GOOD_SINGLE_COMPARE = '''<html><body data-variants="1">
<input type="radio" name="vw" id="vwfull" checked>
<input type="radio" name="vw" id="vw768"><input type="radio" name="vw" id="vw375">
<div class="vwseg"><label for="vwfull">全幅</label></div>
<select id="regen-addr"></select><select id="regen-type"></select><button id="regen-btn"></button>
<div class="canvas"><div class="pane"><iframe src="index.html"></iframe></div></div>
<a href="index.html">原寸</a>
<script>fetch(BASE+'/sections?folder='+folder)</script></body></html>'''

PAGE = ('<html><head><style>.x{}</style></head><body>'
        '<section class="sec"><div class="addr"><span class="pin">MV-01</span></div>'
        '<div class="m-hero" data-hero="full"></div></section></body></html>')


def _load_tool():
    spec = importlib.util.spec_from_file_location("klk092_verify", str(TOOL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK092Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0, "check_klk092.py failed:\n" + proc.stdout + proc.stderr
        )


class TestKLK092ParityCheck(unittest.TestCase):
    """機能同等性チェックが欠落を捕まえること。"""

    def setUp(self):
        self.tool = _load_tool()
        self.dir = Path(tempfile.mkdtemp(prefix="klk092_"))
        (self.dir / "index.html").write_text(PAGE, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _check(self, compare_html=None):
        if compare_html is not None:
            (self.dir / "compare.html").write_text(compare_html, encoding="utf-8")
        return self.tool.check_compare(str(self.dir))

    def test_good_single_passes(self):
        self.assertEqual(self._check(GOOD_SINGLE_COMPARE), [])

    def test_missing_compare_is_caught(self):
        """★これが理恵さんの踏んだ状態そのもの。"""
        out = self._check()
        self.assertTrue(any("compare.html がありません" in w for w in out), out)
        self.assertTrue(any("幅切替と 🔄" in w for w in out), out)

    def test_missing_width_switch_is_caught(self):
        out = self._check(GOOD_SINGLE_COMPARE.replace('id="vw375"', 'id="vwX"'))
        self.assertTrue(any("375px" in w for w in out), out)

    def test_missing_regen_is_caught(self):
        out = self._check(GOOD_SINGLE_COMPARE.replace('id="regen-addr"', 'id="x"'))
        self.assertTrue(any("🔄 が使えない" in w for w in out), out)

    def test_missing_data_variants_is_caught(self):
        """data-variants が無いと JS が letter='a' を送り index-a.html で 404 になる。"""
        out = self._check(GOOD_SINGLE_COMPARE.replace(' data-variants="1"', ''))
        self.assertTrue(any("letter を誤る" in w for w in out), out)

    def test_stray_variant_radio_is_caught(self):
        out = self._check(GOOD_SINGLE_COMPARE.replace('name="vw" id="vwfull"',
                                                      'name="variant" id="ra"'))
        self.assertTrue(any("案切替のラジオ" in w for w in out), out)

    def test_reference_to_index_a_is_caught(self):
        out = self._check(GOOD_SINGLE_COMPARE.replace('src="index.html"', 'src="index-a.html"'))
        self.assertTrue(any("index-a.html" in w for w in out), out)


class TestKLK092MultiVariantUnaffected(unittest.TestCase):
    """3案の見本が引き続き違反ゼロ（既存を壊していない）。"""

    def test_samples_still_clean(self):
        dirs = sorted(str(d) for d in (ROOT / "samples").glob("*") if d.is_dir())
        self.assertGreaterEqual(len(dirs), 3)
        proc = subprocess.run(
            ["python3", str(TOOL)] + dirs,
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("違反 0 件", proc.stdout)


if __name__ == "__main__":
    unittest.main()
