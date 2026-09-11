# KLK-115 配布パッケージにデザインシステム（DADS）が入らないこと（tester所有）。
#
# ★経緯: モック生成システムとデザインシステム（DADS）は別案件になった（2026-09-09）。
#   理恵さんの指示は「モック生成のパッケージに DADS 関連を含めない」
#   「デザインシステム側で生成した項目が混入しないように（共有部分は除く）」。
#   リポジトリは分割しない（2026-09-10 判断）ので、**組み立て時に外す**方式をとる。
#
# ★このテストが守っているもの:
#   - checker 本体が全件PASSし、実ビルド部（P）が省略されずに走ること
#   - 除去の純粋関数 strip_dads_sections が、正常系・壊した系の両方で正しく振る舞うこと
#     （実ファイルは書き換えない — 文字列へ注入する）
#   - 「外す」だけでなく「付ければ入る」も成り立つこと。片側だけなら空検査になりうる
import subprocess
import unittest
from importlib import util as importlib_util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk115.py"
STRIP_TOOL = ROOT / "tools" / "strip-dads-sections.py"


def load_strip():
    spec = importlib_util.spec_from_file_location("strip_dads_sections", STRIP_TOOL)
    mod = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK115StaticChecker(unittest.TestCase):
    def test_static_checker_passes(self):
        """checker本体（パッケージ実ビルド込み）が全件PASSする。"""
        p = subprocess.run(["python3", str(STATIC_CHECKER)],
                           capture_output=True, text=True, timeout=900)
        self.assertEqual(p.returncode, 0,
                         "check_klk115.py 失敗:\n%s" % p.stdout[-2000:])
        self.assertIn(", 0 failed", p.stdout)
        # 実ビルド部（P）が省略されずに走ったことまで確認する
        # （--fast で走ると P が無くても "0 failed" になり得るため）
        self.assertIn("P1 既定ビルドが成功する", p.stdout)
        self.assertIn("P3 ★配布物の全テキストに DADS 語が1つも無い", p.stdout)
        self.assertIn("P5 ★リポジトリ直下に置いた別案件のフォルダが配布物に現れない", p.stdout)


class TestStripDadsSections(unittest.TestCase):
    """除去の純粋関数を、正常系と壊した系の両方で検証する。"""

    @classmethod
    def setUpClass(cls):
        cls.m = load_strip()

    def test_removes_marked_block(self):
        text = "前\n%s\n消える\n%s\n後" % (self.m.BEGIN, self.m.END)
        out, n = self.m.strip_dads_sections(text)
        self.assertEqual(n, 1)
        self.assertNotIn("消える", out)
        self.assertIn("前", out)
        self.assertIn("後", out)

    def test_keeps_unmarked_text_byte_identical(self):
        text = "見出し\n\n- 箇条書き\n\n本文\n"
        out, n = self.m.strip_dads_sections(text)
        self.assertEqual(n, 0)
        self.assertEqual(out, text, "マーカーが無いのに書き換えている")

    def test_collapses_only_the_seam(self):
        # 区切りが二重に残らないこと。ただし関係ない空行は触らない
        text = "A\n\n%s\nX\n%s\n\nB\n\n\nC" % (self.m.BEGIN, self.m.END)
        out, _ = self.m.strip_dads_sections(text)
        self.assertEqual(out, "A\n\nB\n\n\nC")

    def test_unclosed_marker_raises(self):
        # 妨害: END を落とす。壊れたことを確かめてから判定する
        text = "前\n%s\n中身\n後" % self.m.BEGIN
        self.assertNotIn(self.m.END, text)
        with self.assertRaises(ValueError):
            self.m.strip_dads_sections(text)

    def test_orphan_end_raises(self):
        text = "前\n%s\n後" % self.m.END
        self.assertNotIn(self.m.BEGIN, text)
        with self.assertRaises(ValueError):
            self.m.strip_dads_sections(text)

    def test_nested_begin_raises(self):
        text = "%s\n%s\nX\n%s" % (self.m.BEGIN, self.m.BEGIN, self.m.END)
        with self.assertRaises(ValueError):
            self.m.strip_dads_sections(text)

    def test_real_docs_have_no_leftover(self):
        # 実物6文書。マーカーを外したら DADS 語が1つも残らないこと（囲み漏れの検知）
        tokens = ("design-system", "デジタル庁", "DADS")
        for rel in ("CLAUDE.md", "README.md", "CHANGELOG.md",
                    "agents/architect.md", "agents/implementer.md", "agents/reviewer.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn(self.m.BEGIN, text, "%s にマーカーが無い" % rel)
            out, n = self.m.strip_dads_sections(text)
            self.assertGreater(n, 0, "%s で1ブロックも外れていない" % rel)
            left = [l for l in out.split("\n") if any(t in l for t in tokens)]
            self.assertEqual(left, [], "%s に囲み漏れ: %s" % (rel, left[:3]))

    def test_sabotage_outside_marker_is_visible(self):
        # 妨害: マーカーの外へ DADS 語を足すと、除去後も残って検知できること
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        base, _ = self.m.strip_dads_sections(text)
        self.assertNotIn("DADS", base, "基線が既に汚染")
        sabotaged = text + "\n- 配色は DADS に準拠する\n"
        out, _ = self.m.strip_dads_sections(sabotaged)
        self.assertIn("DADS", out, "マーカー外の混入を検知できない")


class TestPackageSymmetry(unittest.TestCase):
    """「外す」と「付ければ入る」の両方が成り立つこと（片側だけの空検査を防ぐ）。"""

    def test_flag_is_optin_and_documented(self):
        src = (ROOT / "tools" / "make-package.sh").read_text(encoding="utf-8")
        self.assertIn("--with-design-system", src)
        self.assertIn("WITH_DESIGN_SYSTEM=0", src)      # 既定OFF
        # 無条件コピーの列挙にマニュアルが残っていない
        uncond = [l for l in src.split("\n") if l.startswith("for f in 起動.command")]
        self.assertEqual(len(uncond), 1)
        self.assertNotIn("デザインシステムの使い方.html", uncond[0])

    def test_optin_side_is_covered_by_sibling_checkers(self):
        # --with-design-system 側（付ければ入る）は klk111 D2 / klk112 G1 が見ている。
        # ここが消えると本チケットの検査は「常に空」でも通ってしまうので、存在を固定する。
        k111 = (ROOT / "tests" / "site" / "check_klk111.py").read_text(encoding="utf-8")
        k112 = (ROOT / "tests" / "site" / "check_klk112.py").read_text(encoding="utf-8")
        self.assertIn("--with-design-system", k111, "klk111 が opt-in 側を見ていない")
        self.assertIn("--with-design-system", k112, "klk112 が opt-in 側を見ていない")


if __name__ == "__main__":
    unittest.main()
