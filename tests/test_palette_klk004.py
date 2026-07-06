# KLK-004 配色ジェネレーターv1.1 のテストを unittest スイートへ束ねるラッパー（tester所有）
# - 静的チェック: tests/site/check_klk004.py（S1-S12・Python標準のみ）
# - 動的スモーク: tests/site/smoke_klk004.node.js（D1-D6・Node.jsが無い環境ではskip）
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk004.py"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk004.node.js"


class TestKLK004Static(unittest.TestCase):
    """check_klk004.py（設計書 §9 S群 S1-S12）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk004.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK004DynamicSmoke(unittest.TestCase):
    """smoke_klk004.node.js（D1-D6: clampMetalBand極端入力・ジャンル空値ガード・
    cssVarsOf形式・URL往復/不正値fail-safe）が全PASSすること。"""

    def test_dynamic_smoke_pass(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "smoke_klk004.node.js failed:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
