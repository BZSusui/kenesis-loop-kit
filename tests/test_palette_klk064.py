# KLK-064 カタログ取り込みの画面承認化（提案→確認・修正→登録の2段階方式）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的+純関数: tests/site/check_klk064.py（P1-P16）
# - 追加: カタログ実データが壊れていないこと（validate_catalog を実データに対して実行）。
#   本チケットで bridge が catalog.json を書くようになったため、破壊の退行を常時検出する。
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk064.py"
CATALOG = ROOT / "catalog" / "catalog.json"


class TestKLK064Static(unittest.TestCase):
    """check_klk064.py（2段階方式の静的+純関数チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk064.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(CATALOG.exists(), "catalog/catalog.json が無い環境のためskip（Git除外・REQ-011）")
class TestKLK064CatalogIntegrity(unittest.TestCase):
    """実データ catalog.json が validate_catalog を満たすこと。

    KLK-064 で登録の書き込み主体が AI から bridge(Python) へ移った。書き込みバグで
    社外秘のカタログを壊すと復元できない（Git 管理外）ため、実データの健全性を常時検査する。
    """

    def test_real_catalog_is_valid(self):
        sys.path.insert(0, str(ROOT / "draft-gen"))
        import bridge  # noqa: E402
        with open(CATALOG, encoding="utf-8") as fh:
            data = json.load(fh)
        ok, errors = bridge.validate_catalog(data)
        self.assertTrue(ok, "catalog.json が検証を満たさない: %s" % errors[:5])

    def test_ids_are_unique(self):
        with open(CATALOG, encoding="utf-8") as fh:
            entries = json.load(fh).get("entries", [])
        ids = [e.get("id") for e in entries]
        self.assertEqual(len(ids), len(set(ids)), "catalog.json の id が重複している")


if __name__ == "__main__":
    unittest.main()
