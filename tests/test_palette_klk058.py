# KLK-058 CTA マルチボタンと自動整列（§4.4・buttons 1〜4・文字数で整列）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk058.py（CB1-CB8・DRAFT_RULES§4.4／SKILL／bridge buttons／golden klk058・klk058b）
# - D群: git check-ignore で golden fixtures が Git 追跡対象であること（git不在時skip）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk058.py"


class TestKLK058Static(unittest.TestCase):
    """check_klk058.py（CTA マルチボタン整列の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk058.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK058FixturesTracked(unittest.TestCase):
    """KLK-058 の golden（klk058・klk058b）が Git 追跡対象であることを確認。"""

    TARGETS = [
        "tests/fixtures/klk058/index-a.html",
        "tests/fixtures/klk058/index-b.html",
        "tests/fixtures/klk058/index-c.html",
        "tests/fixtures/klk058/compare.html",
        "tests/fixtures/klk058/instruction.json",
        "tests/fixtures/klk058b/index-a.html",
        "tests/fixtures/klk058b/index-b.html",
        "tests/fixtures/klk058b/index-c.html",
        "tests/fixtures/klk058b/compare.html",
        "tests/fixtures/klk058b/instruction.json",
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
