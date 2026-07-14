# KLK-021 複数案のレイアウト差別化（data-archetype で配色とレイアウトを両振り）のテストを
# unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的）: tests/site/check_klk021.py（S1-S11・Python標準のみ・
#   対象＝ゴールデン fixtures/klk021/{index-a/b/c,compare}.html ＋ instruction.json /
#   DRAFT_RULES.md / SKILL.md）
# - D群（動的）: git check-ignore サブプロセスで mockups/ 複数案の Git 除外成立を
#   検証（D2・git不在時skip）。D1（Quality Gate 全緑）はスイート全体の実行そのものが担保する。
#
# M群（/draft-generate 実生成＋ブラウザ実機）は自動化不能のため tester が手動確認し
# チケットのログへ記録する（check_klk009 ラッパーと同型）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk021.py"


class TestKLK021Static(unittest.TestCase):
    """check_klk021.py（設計書 §9 S群 S1-S11）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk021.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため check-ignore をskip")
class TestKLK021GitIgnore(unittest.TestCase):
    """D2: mockups/{日付}_{案件名}/ 配下の複数案生成物（compare.html /
    index-a.html / instruction.json）が .gitignore で除外され
    git check-ignore が exit 0（除外成立）を返すこと。（REQ-011 / NFR-004）"""

    TARGETS = [
        "mockups/2026-07-14_サンプル案件/compare.html",
        "mockups/2026-07-14_サンプル案件/index-a.html",
        "mockups/2026-07-14_サンプル案件/instruction.json",
    ]

    def _check_ignored(self, path):
        return subprocess.run(
            ["git", "check-ignore", path],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )

    def test_d2_mockups_ignored(self):
        pre = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        if pre.returncode != 0:
            self.skipTest("git リポジトリ外のため D2 をskip")
        for target in self.TARGETS:
            with self.subTest(path=target):
                proc = self._check_ignored(target)
                self.assertEqual(
                    proc.returncode, 0,
                    f"git check-ignore で除外不成立(exit {proc.returncode}): {target}\n"
                    f"{proc.stdout}{proc.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
