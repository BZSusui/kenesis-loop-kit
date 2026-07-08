# KLK-011 ローカルブリッジのセキュリティハードニング（Origin検証・サイズ上限・
# 保存先日付整合）のテストを unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的/コア）: tests/site/check_klk011.py（S11-S15・Python標準のみ・
#   対象＝draft-gen/bridge.py(import 純関数 + ソース静的検査)）。
# - D群（動的）: `python3 -m unittest discover -s tests` の回帰全緑（D1・NFR-006）は
#   スイート全体の実行そのものが担保する。ここでは S群 subprocess 実行を束ねる。
#
# M群（ブリッジ起動＋別オリジン403/巨大body413/null許可の擬似HTTP疎通）は tester が
# 手動確認しチケットのログへ記録する（test_palette_klk010 ラッパーと同型）。
# check_klk010（S1-S10）は KLK-010 の正のため触らない（本ラッパーは独立）。
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk011.py"


class TestKLK011Static(unittest.TestCase):
    """check_klk011.py（設計書 KLK-011 §9 S群 S11-S15）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk011.py failed:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
