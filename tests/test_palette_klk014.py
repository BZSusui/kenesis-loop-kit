# KLK-014 生成導線の改善（ワンクリック起動ランチャー＋フォールバック文言の正確化・SCR-001）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的/コア）: tests/site/check_klk014.py（S1-S10・Python標準のみ・
#   対象＝draft-gen/index.html(静的) / draft-gen/起動.command(静的・**実行しない**)）。
# - D群（動的）:
#   - D1: check_klk014.py を subprocess 実行し exit 0（S群 束ね）。
#   - D2: `python3 -m unittest discover -s tests` の回帰全緑（NFR-006）は
#     スイート全体の実行そのものが担保する。ここでは S群 subprocess 実行を束ねる
#     （特に文言変更で check_klk010 S7 が PASS 維持であることをスイート全体で回帰確認）。
#   - D3: `bash -n draft-gen/起動.command` が exit 0（**構文解析のみ・実行しない**＝
#     ブリッジ起動の副作用なし。bash 不在時 skip）。
#
# 【重要】起動.command は決して実行しない（ブリッジが起動してしまう）。D3 は `bash -n`
# による構文チェックのみ。M群（実機ダブルクリック起動・ワンクリック生成・claude不在案内・
# 文言の分かりやすさ・実行ビット復旧・実機 PATH）は自動化不能のため人間[臼井さん]が
# 手動確認しチケットのログへ記録する（test_palette_klk013 ラッパーと同型）。
# check_klk006〜013（既存 S群）は各チケットの正のため触らない（本ラッパーは独立）。
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk014.py"
LAUNCHER = ROOT / "draft-gen" / "起動.command"


class TestKLK014Static(unittest.TestCase):
    """D1: check_klk014.py（設計書 KLK-014 §9 S群 S1-S10）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk014.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("bash"), "bash が見つからないため構文チェックをskip")
class TestKLK014LauncherSyntax(unittest.TestCase):
    """D3: 起動ランチャーの構文健全性を `bash -n` で確認する。

    **構文解析のみで実行はしない**（-n＝no-exec）。したがってブリッジ起動・claude 呼出・
    ブラウザ自動オープン等の副作用は一切発生しない。受入1（ダブルクリック起動）の
    静的健全性を担保する。"""

    def test_d3_launcher_syntax_ok(self):
        self.assertTrue(LAUNCHER.is_file(), f"起動ランチャーが存在しない: {LAUNCHER}")
        proc = subprocess.run(
            ["bash", "-n", str(LAUNCHER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        self.assertEqual(
            proc.returncode, 0,
            "bash -n 構文チェック失敗（実行はしていない）:\n" + proc.stdout + proc.stderr,
        )


class TestKLK014LauncherExecBit(unittest.TestCase):
    """S10 補強（D群）: 起動ランチャーに実行ビットが立っていること（os.X_OK）。
    ダブルクリック起動の前提（mode 755）を動的側からも確認する。"""

    def test_launcher_executable(self):
        self.assertTrue(LAUNCHER.is_file(), f"起動ランチャーが存在しない: {LAUNCHER}")
        self.assertTrue(
            os.access(str(LAUNCHER), os.X_OK),
            f"起動.command に実行ビットが無い（chmod +x が必要）: {LAUNCHER}",
        )


if __name__ == "__main__":
    unittest.main()
