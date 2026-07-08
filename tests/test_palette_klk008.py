# KLK-008 生成オプション拡張（カラム6系統・生成時アニメ ON/OFF）のテストを
# unittest スイートへ束ねるラッパー（tester所有）。
# - 静的チェック(S群): tests/site/check_klk008.py（S1-S12・Python標準のみ）
# - 動的スモーク(D群): tests/site/smoke_klk006.node.js（buildInstruction の
#   新enum透過・output.animation 既定/透過を含む・Node.js が無い環境ではskip）
#
# D群は KLK-006 の smoke に R-A 回帰更新（D6/D7 を新カラム値へ・D7 に animation
# boolean 検証を追加）として集約されているため、専用の smoke_klk008 は設けず
# 既存 smoke_klk006.node.js を @skipUnless(node) で束ねる（設計書 §9 D群）。
# M群（/draft-generate 実生成＋ブラウザ実機）は自動化不能のため tester が手動確認し
# チケットのログへ記録する。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk008.py"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk006.node.js"


class TestKLK008Static(unittest.TestCase):
    """check_klk008.py（設計書 §9 S群 S1-S12・縦串の一貫＋R-A集合同期）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk008.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK008DynamicSmoke(unittest.TestCase):
    """smoke_klk006.node.js（D群: buildInstruction 新enum透過・output.animation
    既定true/false 透過・入力非破壊）が新仕様で全PASSすること。"""

    def test_dynamic_smoke_pass(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "smoke_klk006.node.js failed:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
