# KLK-054 ACCESS セクションのプール化（§12.1.3・6型・mod6・全型に地図アタリ内包）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk054.py（A1-A11・§12.1.3 ACCESS プール／割り当て mod6／SKILL／bridge／golden klk054・klk054b・実地図/実埋め込み不在）
# - D群: git check-ignore で golden fixtures が Git 追跡対象であること（git不在時skip）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk054.py"


class TestKLK054Static(unittest.TestCase):
    """check_klk054.py（ACCESS プール化の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk054.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK054FixturesTracked(unittest.TestCase):
    """KLK-054 の golden（klk054・klk054b）が Git 追跡対象であることを確認。"""

    TARGETS = [
        "tests/fixtures/klk054/index-a.html",
        "tests/fixtures/klk054/index-b.html",
        "tests/fixtures/klk054/index-c.html",
        "tests/fixtures/klk054/compare.html",
        "tests/fixtures/klk054/instruction.json",
        "tests/fixtures/klk054b/index-a.html",
        "tests/fixtures/klk054b/index-b.html",
        "tests/fixtures/klk054b/index-c.html",
        "tests/fixtures/klk054b/compare.html",
        "tests/fixtures/klk054b/instruction.json",
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
