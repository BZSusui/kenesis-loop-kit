# KLK-017 SCR-001 参考画像ピッカーの実績カタログ接続（REQ-004）を unittest スイートへ
# 束ねるラッパー（tester所有）。
# - S群（静的/コア）: tests/site/check_klk017.py（T1-T7・Python標準のみ・
#   対象＝draft-gen/index.html。実データ接続・絞り込み結線・S13/S9温存・機密・NFR-005）。
# - D群（動的）:
#   - D1: `python3 -m unittest discover -s tests` の回帰全緑（KLK-006〜016 温存）を、
#     本ラッパー自身を除外して discover を subprocess 実行して確認する。
#   - D2: check_klk017.py を subprocess 実行し exit 0（T群全項目通過）。
#
# M群（実 /catalog.json・/catalog/img 疎通＋ブラウザ実機の選択→references.thumbnails・
# 業種フィルタ・拡大モーダル・空状態）は自動化不能のため tester/人間が手動確認しログへ記録する
# （test_palette_klk015 ラッパーと同型）。check_klk006〜016（既存 S群）は各チケットの正のため触らない。
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk017.py"


class TestKLK017Static(unittest.TestCase):
    """D2: check_klk017.py（設計書 KLK-017 §9 T群 T1-T7）が全PASS＝exit 0。"""

    def test_d2_static_checks_pass(self):
        proc = subprocess.run(
            [sys.executable, str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk017.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK017Regression(unittest.TestCase):
    """D1: discover 回帰全緑。KLK-006〜016（S13/S9 含む）が本改修で回帰しない。

    無限再帰を避けるため、本ラッパー自身（test_palette_klk017）を除外して
    tests/ を discover 実行し、全テストの成功を確認する。"""

    def test_d1_full_suite_green(self):
        # 除外対象は「nested discover を subprocess 起動する回帰ラッパー」全て
        # （klk015・klk017）。相互に相手を含むと再帰的にプロセスが増殖するため、
        # 両方を除外して回帰を有限段で終わらせる（静的 check_klk006〜016 は全て走る）。
        script = (
            "import unittest, sys\n"
            "SKIP = ('test_palette_klk015', 'test_palette_klk017')\n"
            "loader = unittest.TestLoader()\n"
            "top = loader.discover('tests')\n"
            "def keep(suite):\n"
            "    out = unittest.TestSuite()\n"
            "    for item in suite:\n"
            "        if isinstance(item, unittest.TestSuite):\n"
            "            out.addTest(keep(item))\n"
            "        else:\n"
            "            mod = type(item).__module__\n"
            "            if not any(s in mod for s in SKIP):\n"
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
