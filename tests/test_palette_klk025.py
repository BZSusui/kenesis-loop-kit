# KLK-025 配色「②メインカラーだけ」初回反映バグ修正のテストを unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的）: tests/site/check_klk025.py（S1-S4・Python標準のみ・対象＝draft-gen/index.html のイベント登録）
# - D1（Quality Gate 全緑）はスイート全体の実行そのものが担保する。
# M群（macOS Safari 実機で初回反映）は人間が確認しチケットのログへ記録する。
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk025.py"


class TestKLK025Static(unittest.TestCase):
    """check_klk025.py（設計書 §9 S群 S1-S4）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk025.py failed:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
