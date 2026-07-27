# KLK-035 セクション型プール拡充 第1弾（VOICE/FLOW/STAFF を各6型・新型 *-zigzag を index5 に追加）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk035.py（E1-E11・Python標準のみ・対象＝DRAFT_RULES §12.1.2 本文パース／
#   check_klk029・034 定数の三者一致(R2)／fixtures klk035・klk029・klk029b）
# - D群: git ls-files サブプロセスで golden fixtures が Git 追跡対象であること（再現性の担保・git不在時skip）。
#
# M群（/draft-generate 実生成＋ブラウザ実機）は自動化不能のため tester が手動確認しチケットのログへ記録する。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk035.py"


class TestKLK035Static(unittest.TestCase):
    """check_klk035.py（設計書 §9 の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk035.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK035FixturesTracked(unittest.TestCase):
    """golden fixtures（klk035 の index-a/b/c.html・compare.html・instruction.json）が Git 追跡対象であること。"""

    TARGETS = [
        "tests/fixtures/klk035/index-a.html",
        "tests/fixtures/klk035/index-b.html",
        "tests/fixtures/klk035/index-c.html",
        "tests/fixtures/klk035/compare.html",
        "tests/fixtures/klk035/instruction.json",
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
