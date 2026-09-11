# KLK-112 デザインシステム（DADS）の使い方マニュアル（tester所有）。
#
# ★このマニュアル特有のリスク
#   DADSのMarkdownには色の値（HEX）が無い。それを知らずに「DADSの色は #xxxxxx」と
#   書いてしまう事故が起きやすく、マニュアルは全員が読むので間違いがそのまま伝播する。
#   また、出典表記はデジタル庁の利用条件であり、抜けは単なる不備では済まない。
#
# ★このテストが守っているもの
#   - checker本体が全PASSすること（パッケージ実ビルドまで含めて）
#   - checkerが劣化を検知できること。判定は純粋関数へ妨害を注入して確かめる
#     （実ファイルは書き換えない）
#   - とくに「<a href> でデジタル庁サイトを指すのは出典表記であって外部依存ではない」
#     という区別ができていること。ここを雑に禁止すると、出典が書けなくなる
import io
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk112.py"
MANUAL = ROOT / "デザインシステムの使い方.html"


def load_checker_functions():
    """checker を『関数だけ』読み込む（チェック実行はしない）。"""
    src = STATIC_CHECKER.read_text(encoding="utf-8")
    cut = src.index("HTML = io.open(MANUAL")
    ns = {"__file__": str(STATIC_CHECKER)}
    exec(compile(src[:cut], str(STATIC_CHECKER), "exec"), ns)
    return ns


class TestKLK112StaticChecker(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC_CHECKER)],
                           capture_output=True, text=True, timeout=900)
        self.assertEqual(p.returncode, 0,
                         "check_klk112.py 失敗:\n%s" % p.stdout[-2500:])
        self.assertIn(", 0 failed", p.stdout)
        # 実ビルド部（G）が省略されずに走ったことまで確認する
        # KLK-115: マニュアルは --with-design-system を付けたときだけ同梱される
        self.assertIn("G1 ★--with-design-system で組んだパッケージへ同梱される", p.stdout)
        self.assertIn("G2 ★配布される実物が原本と同一で、出典行が残り、リンクが切れない",
                      p.stdout)
        # G2 が「原本と同一」「出典行あり」まで見ていることを確認する。
        # KLK-113 でマニュアルからローカルリンクが無くなり、リンク検査だけでは
        # 何も守らない空検査になっていたため作り直した経緯がある
        self.assertIn("原本と同一=True", p.stdout)
        self.assertIn("出典行=True", p.stdout)


class TestContrastMath(unittest.TestCase):
    """本文に載せた実測値の検算に使う計算そのものを検証する。"""

    @classmethod
    def setUpClass(cls):
        cls.ns = load_checker_functions()

    def test_known_ratios(self):
        c = self.ns["contrast_ratio"]
        self.assertAlmostEqual(c("#000000", "#ffffff"), 21.0, places=2)
        self.assertAlmostEqual(c("#ffffff", "#ffffff"), 1.0, places=2)
        # 対称であること（どちらを背景にしても同じ）
        self.assertAlmostEqual(c("#0f41af", "#ffffff"), c("#ffffff", "#0f41af"), places=6)

    def test_manual_demo_color_meets_dads_floor(self):
        c = self.ns["contrast_ratio"]
        self.assertGreaterEqual(c("#0f41af", "#ffffff"), 4.5)

    def test_a_failing_color_is_detected(self):
        # 妨害: 下限を割る配色。検算が甘いと見逃す
        c = self.ns["contrast_ratio"]
        self.assertLess(c("#9bb7e8", "#ffffff"), 4.5)


class TestExternalResourceDetection(unittest.TestCase):
    """外部リソースの読み込みと、出典としての<a>リンクを取り違えないこと。"""

    @classmethod
    def setUpClass(cls):
        cls.ns = load_checker_functions()

    def test_attribution_link_is_not_a_dependency(self):
        html = ('<p>出典：デジタル庁デザインシステムウェブサイト '
                '<a href="https://design.digital.go.jp/dads/">DADS</a></p>')
        self.assertEqual(self.ns["external_resource_refs"](html), [],
                         "出典リンクを外部依存と誤判定している")

    def test_each_external_load_is_detected(self):
        cases = {
            "script": '<script src="https://cdn.example.com/x.js"></script>',
            "stylesheet": '<link rel="stylesheet" href="https://fonts.example.com/x.css">',
            "image": '<img src="photo.png">',
            "import": '@import "https://example.com/a.css";',
            "url()": 'body{background:url(https://example.com/bg.png)}',
        }
        for label, html in cases.items():
            self.assertTrue(self.ns["external_resource_refs"](html),
                            "%s の読み込みを検知できない" % label)

    def test_real_manual_has_no_external_loads(self):
        html = MANUAL.read_text(encoding="utf-8")
        self.assertEqual(self.ns["external_resource_refs"](html), [])


class TestTextExtraction(unittest.TestCase):
    """読者の目に入る部分だけを見る処理（コメントや<style>に騙されない）。"""

    @classmethod
    def setUpClass(cls):
        cls.ns = load_checker_functions()

    def test_comment_and_script_are_stripped(self):
        s = self.ns["strip_non_text"](
            '<!-- 出典：デジタル庁デザインシステムウェブサイト -->'
            '<style>.a{}</style><script>var x=1;</script><p>本文</p>')
        self.assertNotIn("出典", s)
        self.assertNotIn("var x", s)
        self.assertIn("本文", s)

    def test_attribution_must_be_visible_not_hidden_in_comment(self):
        # 妨害: 出典をコメントに書いただけで済ませた場合、D3 は落ちるべき
        ns = self.ns
        line = "出典：デジタル庁デザインシステムウェブサイト https://design.digital.go.jp/dads/"
        hidden = "<!-- %s --><p>本文</p>" % line
        self.assertNotIn(line, ns["strip_non_text"](hidden))
        visible = "<p>%s</p>" % line
        self.assertIn(line, ns["strip_non_text"](visible))


class TestFactsAgainstRealData(unittest.TestCase):
    """本文の数字を実データから照合する（書き写した数字は腐る）。"""

    @classmethod
    def setUpClass(cls):
        cls.ns = load_checker_functions()
        cls.text = cls.ns["strip_non_text"](MANUAL.read_text(encoding="utf-8"))

    def test_component_count_is_real(self):
        self.assertEqual(self.ns["component_count"](), 49)

    def test_file_counts_are_real(self):
        dads, kit = self.ns["dads_file_counts"]()
        self.assertEqual(kit, 2, "キット側の補助ファイルは _ATTRIBUTION と _REFERENCE_GUIDE の2つ")
        self.assertIn("全部で%d個" % (dads + kit), self.text)
        self.assertIn("うち%d個がデジタル庁の配布物" % dads, self.text)

    def test_no_mock_generator_reference(self):
        """2026-09-09 方針: モック生成とは別案件。マニュアルは言及しない。

        妨害注入で、言及が復活したら検知できることまで確かめる。"""
        for w in ("モック生成", "使い方マニュアル.html", "デザインラフ", "draft-gen"):
            self.assertNotIn(w, self.text, "モック生成への言及が復活している: %s" % w)
        sabotaged = self.text + "\n詳しくはモック生成の使い方マニュアル.html を参照。"
        self.assertTrue([w for w in ("モック生成", "使い方マニュアル.html") if w in sabotaged],
                        "言及の混入を検知できない")

    def test_no_fabricated_dads_color(self):
        import re
        self.assertEqual(
            re.findall(r"DADS[^。]{0,20}(?:定める|規定する)[^。]{0,10}色[^。]{0,20}#[0-9a-fA-F]{6}",
                       self.text), [])


if __name__ == "__main__":
    unittest.main()
