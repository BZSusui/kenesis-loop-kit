# KLK-026 カタログ非表示時の開き方ガイダンスと自動復帰のテストを unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的）: tests/site/check_klk026.py（S1-S7・Python標準のみ・対象＝draft-gen/index.html のガイダンス/再探知）
# - D1（Quality Gate 全緑）はスイート全体の実行そのものが担保する（check_klk017 のピン温存を含む）。
# M群（file://+稼働中の開き直しリンク / 未稼働案内→自動更新 / 起動.command 経由の通常表示）は人間が確認する。
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk026.py"


class TestKLK026Static(unittest.TestCase):
    """check_klk026.py（設計書 §9 S群 S1-S7）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk026.py failed:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
