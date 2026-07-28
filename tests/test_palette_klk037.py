# KLK-037 HERO/ABOUT のプール化（§12.1.3・overlap/img-overlap 追加）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk037.py（H1-H10・Python標準のみ・§12.1.3 本文 HERO/ABOUT パース／check_klk034 定数の
#   ドリフト検出／HERO整列4型distinct／fixtures klk036・既存 klk023/034/034b の不変確認）
# - D群: git ls-files サブプロセスで golden fixtures が Git 追跡対象であること（git不在時skip）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk037.py"


class TestKLK037Static(unittest.TestCase):
    """check_klk037.py（設計書 §9 の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk037.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK037FixturesTracked(unittest.TestCase):
    """KLK-037 が依存する golden（klk036 は KLK-036 で追跡済み）が Git 追跡対象であることを確認（再掲・回帰防止）。"""

    TARGETS = [
        "tests/fixtures/klk036/index-a.html",
        "tests/fixtures/klk036/index-b.html",
        "tests/fixtures/klk036/index-c.html",
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
