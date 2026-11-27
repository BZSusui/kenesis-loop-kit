# KLK-141 記録・雛形・配布物に個人名を入れないこと（tester所有）。
#
# ★経緯: KLK-140 のレビューで、CHANGELOG.md に依頼者の呼称が書かれていることが見つかった。
#   CHANGELOG は配布物にそのまま入る。洗い出すと、比較ページの雛形（compare_template.html）
#   にもあり、生成物ごとに書き出されていた。置き換えたうえで、再発を検査で止める。
#
# ★このテストが守っているもの:
#   - checker 本体が全件PASSし、実ビルド部（K3・K5）と Git 追跡下の走査（K2）が走ること
#   - 照合関数 find_hits / load_terms が正しく振る舞うこと
#     （実在の照合語は書かない。**架空の語**を引数で渡して確かめる）
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "tests" / "site" / "check_klk141.py"
sys.path.insert(0, str(ROOT / "tests" / "site"))
import _private_terms as pt  # noqa: E402


class TestKLK141Checker(unittest.TestCase):
    def test_checker_passes(self):
        """checker 本体（Git 追跡下の走査・パッケージ実ビルド込み）が全件PASSする。"""
        p = subprocess.run(["python3", str(CHECKER)], capture_output=True, text=True, timeout=900)
        self.assertEqual(p.returncode, 0, "check_klk141.py 失敗:\n%s" % p.stdout[-2000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("K2 ★Git 追跡下の全テキストファイルに個人名が無い", p.stdout)
        self.assertIn("K3 ★既定ビルド（パッケージB）の配布物に個人名が無い", p.stdout)
        self.assertIn("K5 ★--with-tests --with-design-system ビルドの配布物に個人名が無い", p.stdout)


class TestFindHits(unittest.TestCase):
    """照合関数を架空の語で検証する（実在の照合語はテストに書かない）。"""

    TERMS = ["テスト太郎", "Taro"]

    def test_hits_plain_term(self):
        hits = pt.find_hits("これはテスト太郎さんの要望", self.TERMS, [])
        self.assertEqual([h[0] for h in hits], ["テスト太郎"])

    def test_allow_word_removes_false_positive(self):
        text = "テスト太郎丸という船"
        self.assertTrue(pt.find_hits(text, self.TERMS, []), "基線: 除外語なしでは一致する")
        self.assertEqual(pt.find_hits(text, self.TERMS, ["テスト太郎丸"]), [])

    def test_allow_word_keeps_other_hits(self):
        # 除外語を取り除いても、同じ行の本物の一致は残ること（取り除き過ぎない）
        hits = pt.find_hits("テスト太郎丸とテスト太郎", self.TERMS, ["テスト太郎丸"])
        self.assertEqual(len(hits), 1)

    def test_ascii_word_boundary(self):
        self.assertEqual(pt.find_hits("Taroko gorge", self.TERMS, []), [])
        self.assertEqual(pt.find_hits("myTaro", self.TERMS, []), [])
        self.assertTrue(pt.find_hits("by Taro.", self.TERMS, []))

    def test_ascii_case_insensitive(self):
        self.assertTrue(pt.find_hits("TARO said", self.TERMS, []))
        self.assertTrue(pt.find_hits("taro_said", self.TERMS, []), "_ は英字ではないので境界になる")


class TestLoadTerms(unittest.TestCase):
    def test_missing_file_is_fail_open(self):
        self.assertIsNone(pt.load_terms(str(ROOT / ".private" / "__no_such_file__.txt")))

    def test_parse_format(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "terms.txt")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("# コメント\n\nテスト太郎\n!テスト太郎丸\n  Taro  \n")
            terms, allows = pt.load_terms(p)
        self.assertEqual(terms, ["テスト太郎", "Taro"])
        self.assertEqual(allows, ["テスト太郎丸"])

    def test_only_allows_is_fail_open(self):
        # 照合語が0件なら照合不能（素通り）として扱う
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "terms.txt")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("# コメントだけ\n!除外語\n")
            self.assertIsNone(pt.load_terms(p))

    def test_scan_tree_returns_no_terms(self):
        # 走査結果は (相対パス, 行番号) だけで、一致した語を含まない（ログへの再漏洩防止）
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.md"), "w", encoding="utf-8") as fh:
                fh.write("一行目\nテスト太郎の指示\n")
            with open(os.path.join(d, "b.bin"), "wb") as fh:
                fh.write(b"\xff\xfe\x00\x01")
            hits = pt.scan_tree(d, ["テスト太郎"], [])
        self.assertEqual(hits, [("a.md", 2)])
        self.assertNotIn("テスト太郎", pt.summarize(hits))


if __name__ == "__main__":
    unittest.main()
