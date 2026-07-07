# KLK-005 配色ジェネレーター可読性表示・コピー形式切替のテストを unittest スイートへ束ねるラッパー（tester所有）
# - 静的チェック: tests/site/check_klk005.py（S1-S12・Python標準のみ）
# - 動的スモーク: tests/site/smoke_klk005.node.js（D1-D6・Node.jsが無い環境ではskip）
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk005.py"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk005.node.js"


class TestKLK005Static(unittest.TestCase):
    """check_klk005.py（設計書 §9 S群 S1-S12）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk005.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK005DynamicSmoke(unittest.TestCase):
    """smoke_klk005.node.js（D1-D6: バッジ3段・判定不変・hexListOf/cssVarsOf形式・
    copyTextOf呼び分け・例外安全）が全PASSすること。"""

    def test_dynamic_smoke_pass(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "smoke_klk005.node.js failed:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
