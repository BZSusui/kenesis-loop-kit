# KLK-015 番地ラベル HERO-01 → MV-01（メインビジュアル）リネームのテストを
# unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的/コア）: tests/site/check_klk015.py（S1-S7・Python標準のみ・
#   対象＝DRAFT_RULES / draft-generate SKILL / draft-regenerate SKILL /
#   draft-gen/bridge.py(import 純関数) / tests/fixtures/klk007|008|009|012/*.html）。
# - D群（動的）:
#   - D1: `python3 -m unittest discover -s tests` の回帰全緑（NFR-006）は
#     スイート全体の実行そのものが担保する。更新した check_klk007/008/009/012 と
#     test_palette_klk012 が MV-01 で通り、既存（KLK-006〜014）が回帰しないことを、
#     ここでは discover を subprocess 実行して確認する。
#   - D2: check_klk015.py を subprocess 実行し exit 0（S群全項目通過）。
#
# M群（実 /draft-generate ＋compare.html＋任意の再生成＋SPEC/ワイヤー目視）は
# 自動化不能のため tester/人間が手動確認しチケットのログへ記録する
# （test_palette_klk010/011/012 ラッパーと同型）。
# check_klk006〜014（既存 S群）は各チケットの正のため触らない（本ラッパーは独立）。
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk015.py"


class TestKLK015Static(unittest.TestCase):
    """D2: check_klk015.py（設計書 KLK-015 §9 S群 S1-S7）が全PASS＝exit 0。"""

    def test_d2_static_checks_pass(self):
        proc = subprocess.run(
            [sys.executable, str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk015.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK015Regression(unittest.TestCase):
    """D1: discover 回帰全緑。MV-01 化した既存テストが通り、KLK-006〜014 が回帰しない。

    無限再帰を避けるため、本ラッパー自身（test_palette_klk015）を除外して
    tests/ を discover 実行し、全テストの成功を確認する。"""

    def test_d1_full_suite_green(self):
        # discover をサブプロセスで実行し、本ラッパーを除外して回帰全緑を確認する。
        script = (
            "import unittest, sys\n"
            "loader = unittest.TestLoader()\n"
            "top = loader.discover('tests')\n"
            "def keep(suite):\n"
            "    out = unittest.TestSuite()\n"
            "    for item in suite:\n"
            "        if isinstance(item, unittest.TestSuite):\n"
            "            out.addTest(keep(item))\n"
            "        else:\n"
            "            if 'test_palette_klk015' not in type(item).__module__:\n"
            "                out.addTest(item)\n"
            "    return out\n"
            "filtered = keep(top)\n"
            "res = unittest.TextTestRunner(verbosity=0).run(filtered)\n"
            "sys.exit(0 if res.wasSuccessful() else 1)\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, cwd=str(ROOT), timeout=300,
        )
        self.assertEqual(
            proc.returncode, 0,
            "discover 回帰が全緑ではありません:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
