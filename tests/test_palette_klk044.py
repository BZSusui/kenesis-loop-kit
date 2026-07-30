# KLK-044 MENU のプール化（§12.1.3・price-table 追加・MENU 4型化）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk044.py（P1-P10・Python標準のみ・§12.1.3 本文 MENU パース／check_klk034 定数の
#   ドリフト検出／price-table 実CSS差／fixtures klk044・既存 klk023/034/034b の MENU 不変確認）
# - D群: git ls-files サブプロセスで golden fixtures が Git 追跡対象であること（git不在時skip）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk044.py"


class TestKLK044Static(unittest.TestCase):
    """check_klk044.py（MENU §12.1.3 移譲＋price-table の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk044.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK044FixturesTracked(unittest.TestCase):
    """KLK-044 の golden（klk044）が Git 追跡対象（除外されていない）であることを確認。"""

    TARGETS = [
        "tests/fixtures/klk044/index-a.html",
        "tests/fixtures/klk044/index-b.html",
        "tests/fixtures/klk044/index-c.html",
        "tests/fixtures/klk044/compare.html",
        "tests/fixtures/klk044/instruction.json",
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
