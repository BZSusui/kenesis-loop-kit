# KLK-140 配色ジェネレーターに辞書に無い4語を新設する のテストを unittest スイートへ束ねるラッパー
# - 動的検査: tests/site/smoke_klk140.node.js（K1-K6・Node.jsが無い環境ではskip）
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk140.node.js"


@unittest.skipUnless(shutil.which("node"), "node が見つからないため動的検査をskip")
class TestKLK140DynamicSmoke(unittest.TestCase):
    """smoke_klk140.node.js（K1 辞書・K2/K3 差し色・K4 型B・K5 適用しない条件・K6 両方のヒント）が全PASSすること。"""

    def test_dynamic_smoke_pass(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "smoke_klk140.node.js failed:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
