# KLK-028 配色カラーコードの「#」省略入力（6桁）受理のテストを unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的）: tests/site/check_klk028.py（S1-S4・Python標準のみ・対象＝draft-gen/index.html）
# - K群（動的スモーク）: tests/site/smoke_klk028.node.js（H1-H4: normalizeHex/validateRequired/buildInstruction の
#   実挙動・node 無ければ skip）。smoke_klk006 D4 の既存ピン維持はスイート全体の実行が担保する。
# M群（Photoshopコピー値の貼り付け実機確認）は人間が確認しチケットのログへ記録する。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk028.py"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk028.node.js"


class TestKLK028Static(unittest.TestCase):
    """check_klk028.py（設計書 §9 S群 S1-S4）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk028.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK028Smoke(unittest.TestCase):
    """smoke_klk028.node.js（H1-H4: 6桁受理・既存ピン維持・必須充足・#つき出力）が全PASSすること。"""

    def test_dynamic_smoke_pass(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "smoke_klk028.node.js failed:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
