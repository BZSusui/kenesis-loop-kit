# KLK-036 GALLERY プール化（§12.1.3・GALLERY を archetype 固定から独立プールへ・pat-slider 追加）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk036.py（G1-G10・Python標準のみ・§12.1.3 本文パース／check_klk034 GALLERY定数の
#   ドリフト検出／fixtures klk036・既存 klk023/034/034b の不変確認）
# - D群: git ls-files サブプロセスで golden fixtures が Git 追跡対象であること（git不在時skip）。
#
# M群（/draft-generate 実生成＋ブラウザ実機）は自動化不能のため tester が手動確認しチケットのログへ記録する。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk036.py"


class TestKLK036Static(unittest.TestCase):
    """check_klk036.py（設計書 §9 の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk036.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK036FixturesTracked(unittest.TestCase):
    """golden fixtures（klk036 の index-a/b/c.html・compare.html・instruction.json）が Git 追跡対象であること。"""

    TARGETS = [
        "tests/fixtures/klk036/index-a.html",
        "tests/fixtures/klk036/index-b.html",
        "tests/fixtures/klk036/index-c.html",
        "tests/fixtures/klk036/compare.html",
        "tests/fixtures/klk036/instruction.json",
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
                self.assertEqual(
                    proc.returncode, 1,
                    f"golden fixture が .gitignore で除外されている(exit {proc.returncode}): {target}\n"
                    f"{proc.stdout}{proc.stderr}",
                )
                self.assertTrue(
                    (ROOT / target).exists(),
                    f"golden fixture が存在しない: {target}",
                )


if __name__ == "__main__":
    unittest.main()
