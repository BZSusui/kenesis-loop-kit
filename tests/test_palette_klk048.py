# KLK-048 詳細ページ誘導ボタンの横展開（opt-in moreLink・共通 .sec-more）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk048.py（Q1-Q10・§4.3 規約／SKILL／bridge.validate_instruction の moreLink 検証／
#   golden klk044 の opt-in デモ・feature-large の .sec-more 統一・既存 golden 不変）
# - D群: git check-ignore で golden fixtures が Git 追跡対象であること（git不在時skip）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk048.py"


class TestKLK048Static(unittest.TestCase):
    """check_klk048.py（詳細誘導ボタン横展開の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk048.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK048FixturesTracked(unittest.TestCase):
    """KLK-048 が依存する golden（klk044・既に追跡済み）が Git 追跡対象であることを確認（回帰防止）。"""

    TARGETS = [
        "tests/fixtures/klk044/index-a.html",
        "tests/fixtures/klk044/index-b.html",
        "tests/fixtures/klk044/index-c.html",
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
