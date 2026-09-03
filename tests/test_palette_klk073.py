# KLK-073/074 型ごとの調整を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk073.py（B1-B20）
# - 追加: 新設した3節が SKILL.md から**すべて**参照されていること。
#   規約に書いても生成手順から辿れなければ、生成時に読まれず守られない
#   （KLK-072 で masonry の「意図だけ書いて手順が無い」問題を踏んだのと同じ構造）。
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk073.py"
RULES = ROOT / ".claude" / "skills" / "draft-generate" / "templates" / "DRAFT_RULES.md"
SKILL = ROOT / ".claude" / "skills" / "draft-generate" / "SKILL.md"


class TestKLK073Static(unittest.TestCase):
    """check_klk073.py（型ごとの調整の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk073.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK073RulesAreReachable(unittest.TestCase):
    """新設した節が SKILL.md から辿れること。

    DRAFT_RULES に書いても、生成手順（SKILL.md）から参照されていなければ
    生成時に読まれず守られない。節を足したら参照も足す、を不変条件にする。
    """

    NEW_SECTIONS = ["§3.0", "§8.1", "§4.1.1", "§4.3.1"]

    def test_new_sections_exist_in_rules(self):
        text = RULES.read_text(encoding="utf-8")
        for sec in ("### 3.0 ", "### 8.1 ", "#### 4.1.1 ", "#### 4.3.1 "):
            with self.subTest(section=sec):
                self.assertIn(sec, text, f"DRAFT_RULES に {sec} が無い")

    def test_new_sections_referenced_from_skill(self):
        skill = SKILL.read_text(encoding="utf-8")
        for sec in self.NEW_SECTIONS:
            with self.subTest(section=sec):
                self.assertIn(
                    sec, skill,
                    f"SKILL.md が {sec} を参照していない（生成時に読まれず守られない）",
                )


if __name__ == "__main__":
    unittest.main()
