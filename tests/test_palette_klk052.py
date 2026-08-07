# KLK-052 PRICE セクションのプール化（§12.1.3・6型・mod6・NEWS/MENU 流用）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk052.py（P1-P11・§12.1.3 PRICE プール／割り当て mod6／SKILL／bridge／golden klk052・klk052b）
# - D群: git check-ignore で golden fixtures が Git 追跡対象であること（git不在時skip）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk052.py"


class TestKLK052Static(unittest.TestCase):
    """check_klk052.py（PRICE プール化の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk052.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK052FixturesTracked(unittest.TestCase):
    """KLK-052 の golden（klk052・klk052b）が Git 追跡対象であることを確認。"""

    TARGETS = [
        "tests/fixtures/klk052/index-a.html",
        "tests/fixtures/klk052/index-b.html",
        "tests/fixtures/klk052/index-c.html",
        "tests/fixtures/klk052/compare.html",
        "tests/fixtures/klk052/instruction.json",
        "tests/fixtures/klk052b/index-a.html",
        "tests/fixtures/klk052b/index-b.html",
        "tests/fixtures/klk052b/index-c.html",
        "tests/fixtures/klk052b/compare.html",
        "tests/fixtures/klk052b/instruction.json",
    ]

    def test_fixtures_not_ignored(self):
        pre = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        if pre.returncode != 0:
            self.skipTest("git リポジトリ外のためskip")
        for target in self.TARGETS:
            with self.subTest(path=target):
                proc = subprocess.run(
                    ["git", "check-ignore", target],
                    capture_output=True, text=True, cwd=str(ROOT), timeout=60,
                )
                self.assertEqual(proc.returncode, 1, f"golden が除外されている: {target}")
                self.assertTrue((ROOT / target).exists(), f"golden が存在しない: {target}")


if __name__ == "__main__":
    unittest.main()
