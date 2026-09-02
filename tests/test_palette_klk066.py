# KLK-066 登録後に取り込み待ち画像・提案JSONが残る不具合の修正を
# unittest スイートへ束ねるラッパー（tester所有）。
# - 静的+純関数: tests/site/check_klk066.py（C1-C10）
# - 追加: catalog.json に **同一ファイルの重複登録が無い**こと。
#   本不具合は残骸の再変換により同一画像の二重登録（cat-0054 / cat-0056 がバイト一致）を
#   誘発した。同種の再発を実データで検出する。
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk066.py"
CATALOG = ROOT / "catalog" / "catalog.json"


class TestKLK066Static(unittest.TestCase):
    """check_klk066.py（残留物の片付けの静的+純関数チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk066.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(CATALOG.exists(), "catalog/catalog.json が無い環境のためskip（Git除外・REQ-011）")
class TestKLK066NoDuplicateFiles(unittest.TestCase):
    """catalog.json の file が重複していないこと（二重登録の検出）。"""

    def test_files_are_unique(self):
        with open(CATALOG, encoding="utf-8") as fh:
            entries = json.load(fh).get("entries", [])
        files = [e.get("file") for e in entries if isinstance(e, dict)]
        dupes = sorted({f for f in files if files.count(f) > 1})
        self.assertFalse(dupes, f"catalog.json に同じ file を持つエントリがある: {dupes}")


if __name__ == "__main__":
    unittest.main()
