# KLK-006 設定画面(SCR-001)デザインラフ生成指示書ビルダーのテストを unittest スイートへ束ねるラッパー（tester所有）
# - 静的チェック: tests/site/check_klk006.py（S1-S15・Python標準のみ）
# - 動的スモーク: tests/site/smoke_klk006.node.js（D1-D8・Node.jsが無い環境ではskip）
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk006.py"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk006.node.js"


class TestKLK006Static(unittest.TestCase):
    """check_klk006.py（設計書 §9 S群 S1-S15）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk006.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK006DynamicSmoke(unittest.TestCase):
    """smoke_klk006.node.js（D1-D8: parsePalette両形式・normalizeHex・validateRequired・
    buildInstruction契約・例外安全）が全PASSすること。"""

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
