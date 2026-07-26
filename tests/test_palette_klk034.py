# KLK-034 参考準拠生成（案A=カタログ準拠・席替え規則 §12.2・7カテゴリ→hex表 §5.1）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - R/U/T群（静的）: tests/site/check_klk034.py（Python標準のみ・対象＝ゴールデン fixtures/klk034・klk034b/*
#   ＋ DRAFT_RULES.md / SKILL.md / draft-gen/index.html / bridge.validate_instruction 機能検証）
# - D群（動的）: git ls-files サブプロセスで golden fixtures が Git 追跡対象であること（テストの再現性の担保・
#   git不在時skip）。mockups/ の生成物とは逆に、fixtures は追跡されねばならない。
#
# M群（/draft-generate 実生成＋ブラウザ実機）は自動化不能のため tester が手動確認しチケットのログへ記録する。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk034.py"


class TestKLK034Static(unittest.TestCase):
    """check_klk034.py（設計書 §4.6 R/U/T群）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk034.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK034FixturesTracked(unittest.TestCase):
    """golden fixtures（klk034/ klk034b/ の index-a/b/c.html・compare.html・instruction.json）が
    Git 追跡対象であること。mockups/ 生成物（除外）とは逆に、テスト固定物は追跡されねばならない
    （新規追加ファイルは `git add` 済みか untracked でも存在する状態を許容し、除外されていないことを確認）。"""

    TARGETS = [
        "tests/fixtures/klk034/index-a.html",
        "tests/fixtures/klk034/index-b.html",
        "tests/fixtures/klk034/index-c.html",
        "tests/fixtures/klk034/compare.html",
        "tests/fixtures/klk034/instruction.json",
        "tests/fixtures/klk034b/index-a.html",
        "tests/fixtures/klk034b/index-b.html",
        "tests/fixtures/klk034b/index-c.html",
        "tests/fixtures/klk034b/compare.html",
        "tests/fixtures/klk034b/instruction.json",
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
                # git check-ignore は「除外されている」なら exit 0 を返す。fixtures は除外されて
                # いてはならないので exit 1（＝除外なし）を期待する。
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
