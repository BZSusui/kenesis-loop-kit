# KLK-056 SEARCH セクションのプール化（§12.1.3・6型・mod6・入力は静的アタリ）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk056.py（SR1-SR11・§12.1.3 SEARCH プール／割り当て mod6／SKILL／bridge／golden klk056・klk056b・静的入力）
# - D群: git check-ignore で golden fixtures が Git 追跡対象であること（git不在時skip）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk056.py"


class TestKLK056Static(unittest.TestCase):
    """check_klk056.py（SEARCH プール化の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk056.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK056FixturesTracked(unittest.TestCase):
    """KLK-056 の golden（klk056・klk056b）が Git 追跡対象であることを確認。"""

    TARGETS = [
        "tests/fixtures/klk056/index-a.html",
        "tests/fixtures/klk056/index-b.html",
        "tests/fixtures/klk056/index-c.html",
        "tests/fixtures/klk056/compare.html",
        "tests/fixtures/klk056/instruction.json",
        "tests/fixtures/klk056b/index-a.html",
        "tests/fixtures/klk056b/index-b.html",
        "tests/fixtures/klk056b/index-c.html",
        "tests/fixtures/klk056b/compare.html",
        "tests/fixtures/klk056b/instruction.json",
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
