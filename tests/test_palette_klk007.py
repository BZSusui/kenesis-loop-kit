# KLK-007 デザインラフ生成エンジンのテストを unittest スイートへ束ねるラッパー（tester所有）
# - S群（静的）: tests/site/check_klk007.py（S1-S13・Python標準のみ・
#   対象＝ゴールデンサンプル sample-draft.html / DRAFT_RULES.md / .gitignore x3）
# - D群（動的）: git check-ignore サブプロセスで mockups/ のGit除外成立を検証（D1・git不在時skip）
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk007.py"


class TestKLK007Static(unittest.TestCase):
    """check_klk007.py（設計書 §9 S群 S1-S13）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk007.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため check-ignore をskip")
class TestKLK007GitIgnore(unittest.TestCase):
    """D1: mockups/{日付}_{案件名}/ 配下（index.html / instruction.json）が
    .gitignore で除外され git check-ignore が exit 0（除外成立）を返すこと。（REQ-011 / NFR-004）"""

    TARGETS = [
        "mockups/2026-07-07_サンプル案件/index.html",
        "mockups/2026-07-07_サンプル案件/instruction.json",
    ]

    def _check_ignored(self, path):
        # git check-ignore: exit 0 = 除外成立, 1 = 未除外, 128 = git管理外/エラー
        return subprocess.run(
            ["git", "check-ignore", path],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )

    def test_repo_is_git(self):
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        if proc.returncode != 0:
            self.skipTest("git リポジトリ外のため D1 をskip")

    def test_d1_mockups_ignored(self):
        # git 管理下でない環境は skip（fail にしない）
        pre = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        if pre.returncode != 0:
            self.skipTest("git リポジトリ外のため D1 をskip")
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
