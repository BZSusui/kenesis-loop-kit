# KLK-088 composition を生成側へ通す変更を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk088.py（A〜F群=規約とスキル / V群=verify-mockup の照合）
# - 追加: **composition 照合が実際に違反を捕まえるか**を、合成HTMLで確かめる。
#
#   ★規約に書いただけでは効かない（KLK-072〜076 で4回踏んだ）。
#     「規約が効いたか」を実物で見る道具が verify-mockup の check_composition であり、
#     その道具自体が壊れていないことを、ここで固定する。
import importlib.util
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk088.py"
TOOL = ROOT / "tools" / "verify-mockup.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("klk088_verify", str(TOOL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _page(addrs, menu_types=(), menu_headings=()):
    """番地列から最小の生成物HTMLを組む（MENU だけ型と見出しを差し込める）。"""
    parts = ['<html><head><style>.x{}</style></head><body>',
             '<section class="sec"><div class="addr"><span class="pin">NAV-01</span></div>'
             '<div class="m-nav"></div></section>',
             '<section class="sec"><div class="addr"><span class="pin">MV-01</span></div>'
             '<div class="m-hero" data-hero="full"></div></section>']
    n = 0
    for a in addrs:
        key = a.rsplit("-", 1)[0]
        if key == "MENU":
            ty = menu_types[n] if n < len(menu_types) else "pat-cards"
            hd = menu_headings[n] if n < len(menu_headings) else ""
            n += 1
            parts.append(
                '<section class="sec"><div class="addr"><span class="pin">%s</span></div>'
                '<div class="m-menu" data-menu="%s"><h2>%s</h2></div></section>' % (a, ty, hd))
        else:
            parts.append(
                '<section class="sec"><div class="addr"><span class="pin">%s</span></div>'
                '<div class="m-%s"></div></section>' % (a, key.lower()))
    parts.append('<section class="sec"><div class="addr"><span class="pin">FOOTER-01</span></div>'
                 '<div class="m-foot"></div></section></body></html>')
    return "".join(parts)


class TestKLK088Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0, "check_klk088.py failed:\n" + proc.stdout + proc.stderr
        )


class TestKLK088CompositionMatcher(unittest.TestCase):
    """composition 照合が並び・連番・型・見出しの違反を捕まえること。"""

    COMP = [
        {"key": "ABOUT"},
        {"key": "MENU", "type": "pat-cards", "heading": "ランチ"},
        {"key": "MENU", "type": "price-table"},
    ]

    def setUp(self):
        self.tool = _load_tool()
        self.dir = Path(tempfile.mkdtemp(prefix="klk088_"))
        (self.dir / "instruction.json").write_text(
            json.dumps({"schema": "design-draft-instruction", "version": 1,
                        "composition": self.COMP}, ensure_ascii=False),
            encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _check(self, html):
        """違反だけを返す（型・見出しの食い違いは注意なので含まれない）。"""
        return self.tool.check_composition(str(self.dir), str(self.dir / "index-a.html"), html)

    def _notices(self, html):
        """注意（生成後に 🔄 で変えたなら正常なもの）を返す。"""
        n = []
        self.tool.check_composition(str(self.dir), str(self.dir / "index-a.html"), html, n)
        return n

    def test_correct_page_passes(self):
        html = _page(["ABOUT-01", "MENU-01", "MENU-02"],
                     ("pat-cards", "price-table"), ("ランチ", ""))
        self.assertEqual(self._check(html), [], "正しい生成物で警告が出た")

    def test_wrong_order_is_caught(self):
        html = _page(["ABOUT-01", "MENU-02", "MENU-01"],
                     ("pat-cards", "price-table"), ("ランチ", ""))
        out = self._check(html)
        self.assertTrue(any("並びが違う" in w for w in out), out)

    def test_wrong_type_is_a_notice_not_a_violation(self):
        """★型の食い違いは「注意」。生成後に 🔄 で変えたのなら正常な状態だから。

        違反にすると、意図的に型を入れ替えたフォルダが毎回赤くなる（KLK-089 で実際に起きた）。
        """
        html = _page(["ABOUT-01", "MENU-01", "MENU-02"],
                     ("pat-list", "price-table"), ("ランチ", ""))
        self.assertEqual(self._check(html), [], "型の食い違いを違反にしている")
        self.assertTrue(any("型が指示書と違う" in w for w in self._notices(html)),
                        self._notices(html))

    def test_missing_heading_is_a_notice(self):
        html = _page(["ABOUT-01", "MENU-01", "MENU-02"],
                     ("pat-cards", "price-table"), ("", ""))
        self.assertEqual(self._check(html), [])
        self.assertTrue(any("見出しが無い" in w for w in self._notices(html)),
                        self._notices(html))

    def test_order_is_still_a_violation(self):
        """★並びの食い違いは違反のまま（🔄 は並びを変えないので、間違いでしかない）。"""
        html = _page(["ABOUT-01", "MENU-02", "MENU-01"],
                     ("pat-cards", "price-table"), ("ランチ", ""))
        self.assertTrue(any("並びが違う" in w for w in self._check(html)), self._check(html))

    def test_duplicate_address_is_caught(self):
        """★連番が重複すると 🔄 部分再生成が止まるので、必ず捕まえる。"""
        (self.dir / "instruction.json").write_text(
            json.dumps({"composition": [{"key": "ABOUT"}, {"key": "MENU"}, {"key": "MENU"}]},
                       ensure_ascii=False), encoding="utf-8")
        html = _page(["ABOUT-01", "MENU-01", "MENU-01"])
        out = self._check(html)
        # 並びの照合が先に出る（期待 MENU-01,MENU-02 と違うため）＝どちらでも検出できていればよい
        self.assertTrue(out, "重複を見逃した")

    def test_no_composition_is_silent(self):
        """composition の無い指示書では何も言わない（既存の見本を壊さない）。"""
        (self.dir / "instruction.json").write_text(
            json.dumps({"sections": ["ABOUT", "MENU"]}, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self._check(_page(["ABOUT-01", "MENU-01"])), [])

    def test_no_instruction_file_is_silent(self):
        (self.dir / "instruction.json").unlink()
        self.assertEqual(self._check(_page(["ABOUT-01"])), [])

    def test_broken_instruction_is_silent(self):
        (self.dir / "instruction.json").write_text("{ broken", encoding="utf-8")
        self.assertEqual(self._check(_page(["ABOUT-01"])), [])


class TestKLK088SelfContainmentGranularity(unittest.TestCase):
    """★自己完結の検査は「いま読み込むもの」に限ること（KLK-088 の実機検証で誤検出して気づいた）。

    §4.3 の moreLink は**これから作る下層ページ**を指すプレースホルダ。
    そこを「参照先がありません」と言うと、正しい生成物が毎回赤くなり、
    やがて誰も警告を読まなくなる（KLK-080 で学んだのと同じ失敗）。
    かといって緩めすぎると、本当に要る参照の欠落を見逃す。両方を固定する。
    """

    def setUp(self):
        self.tool = _load_tool()
        self.dir = Path(tempfile.mkdtemp(prefix="klk088sc_"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _check(self, extra_html):
        html = ('<html><head><style>.x{}</style></head><body>'
                '<section class="sec"><div class="addr"><span class="pin">MV-01</span></div>'
                '<div class="m-hero" data-hero="full"></div></section>'
                + extra_html + '</body></html>')
        p = self.dir / "index-a.html"
        p.write_text(html, encoding="utf-8")
        return self.tool.check_file(str(p))

    def test_missing_image_is_caught(self):
        out = self._check('<img src="assets/mv.jpg">')
        self.assertTrue(any("読み込む先がありません（src）" in w for w in out), out)

    def test_missing_stylesheet_is_caught(self):
        out = self._check('<link rel="stylesheet" href="style.css">')
        self.assertTrue(any("読み込む先がありません（link）" in w for w in out), out)

    def test_missing_sibling_page_is_caught(self):
        """compare.html → index-*.html のような同フォルダの生成物リンクは在るべき。"""
        out = self._check('<a href="index-z.html">案Z</a>')
        self.assertTrue(any("リンク先の生成物がありません" in w for w in out), out)

    def test_placeholder_sub_page_link_is_allowed(self):
        """下層ページへの誘導（moreLink）は存在を求めない。"""
        self.assertEqual(self._check('<a href="/menu/">お品書き</a>'), [])
        self.assertEqual(self._check('<a href="#">詳しく</a>'), [])

    def test_external_url_is_still_caught(self):
        out = self._check('<a href="https://evil.example/">外</a>')
        self.assertTrue(any("外部URL" in w for w in out), out)


class TestKLK088ExistingSamplesUnaffected(unittest.TestCase):
    """既存の見本（composition 無し）が引き続き違反ゼロで通ること。"""

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
