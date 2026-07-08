# KLK-010 ローカルブリッジによるワンクリック生成のテストを unittest スイートへ
# 束ねるラッパー（tester所有）。
# - S群（静的/コア）: tests/site/check_klk010.py（S1-S10・Python標準のみ・
#   対象＝draft-gen/bridge.py(import 純関数) / draft-gen/index.html(静的) /
#   SKILL.md / docs/SPEC.md）
# - D群（動的）: git check-ignore サブプロセスで mockups/.pending/{id}.json の
#   Git 除外成立を検証（D1・git不在時skip）。
#
# M群（ブリッジ起動＋/draft-generate 実生成＋ブラウザ実機）は自動化不能のため
# tester が手動確認しチケットのログへ記録する（test_palette_klk009 ラッパーと同型）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk010.py"


class TestKLK010Static(unittest.TestCase):
    """check_klk010.py（設計書 §9 S群 S1-S10）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk010.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため check-ignore をskip")
class TestKLK010GitIgnore(unittest.TestCase):
    """D1: ブリッジが検証済みJSONを一時保存する mockups/.pending/{jobId}.json が
    .gitignore（mockups/）で除外され、git check-ignore が exit 0（除外成立）を
    返すこと（一時ファイルがコミットされない）。（REQ-011 / NFR-004）"""

    TARGET = "mockups/.pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.json"

    def test_d1_pending_ignored(self):
        # git 管理下でない環境は skip（fail にしない）
        pre = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        if pre.returncode != 0:
            self.skipTest("git リポジトリ外のため D1 をskip")
        proc = subprocess.run(
            ["git", "check-ignore", self.TARGET],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        self.assertEqual(
            proc.returncode, 0,
            f"git check-ignore で除外不成立(exit {proc.returncode}): {self.TARGET}\n"
            f"{proc.stdout}{proc.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
