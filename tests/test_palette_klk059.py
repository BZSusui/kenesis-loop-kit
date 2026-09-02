# KLK-059 業種・テイスト語彙の一本化（SCR-001 ↔ SCR-004 ↔ CATALOG_RULES ↔ catalog.json）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk059.py（V0-V11・語彙の正のパース／四者一致／多対一マッピング／
#         旧表記の回帰防止／絞り込みの実効性）
# - catalog/catalog.json は社外秘ゆえ Git 除外（REQ-011）。存在しない環境では
#   checker 側が該当検証を SKIP する（fail-open）ため、本ラッパーは環境を問わず成立する。
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk059.py"


class TestKLK059Static(unittest.TestCase):
    """check_klk059.py（語彙一本化の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk059.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK059VocabularySourceOfTruth(unittest.TestCase):
    """語彙の正（CATALOG_RULES §3）が配布物として追跡され、参照が壊れていないこと。

    catalog/ 配下（社外秘・Git除外）とは異なり、CATALOG_RULES はスキル定義の一部として
    配布される。語彙の正が失われると四者一致の検証そのものが成立しなくなるため、
    ファイルの存在と必須見出しの両方を確認する。
    """

    RULES = ROOT / ".claude" / "skills" / "catalog-import" / "templates" / "CATALOG_RULES.md"

    def test_rules_file_exists(self):
        self.assertTrue(self.RULES.exists(), f"語彙の正が存在しない: {self.RULES}")

    def test_rules_declares_both_vocabularies(self):
        text = self.RULES.read_text(encoding="utf-8")
        self.assertIn("推奨業種語彙(17区分", text, "業種 canonical の宣言が見つからない")
        self.assertIn("推奨テイスト語彙(10種", text, "テイスト canonical の宣言が見つからない")


if __name__ == "__main__":
    unittest.main()
