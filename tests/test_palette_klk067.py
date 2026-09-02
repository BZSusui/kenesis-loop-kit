# KLK-067 主配色をムードカラー ジェネレーター準拠の16種へ拡張した変更を
# unittest スイートへ束ねるラッパー（tester所有）。
# - 静的+純関数: tests/site/check_klk067.py（K1-K11）
# - 追加: 実データ catalog.json の colors が 1..3 件・カラフル単独の規約を満たすこと。
#   語彙拡張で「4件入れられる」「カラフルと具体色を併用する」といった崩れが起きないか実データで見る。
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk067.py"
CATALOG = ROOT / "catalog" / "catalog.json"


class TestKLK067Static(unittest.TestCase):
    """check_klk067.py（主配色16種の静的+純関数チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk067.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(CATALOG.exists(), "catalog/catalog.json が無い環境のためskip（Git除外・REQ-011）")
class TestKLK067CatalogColorRules(unittest.TestCase):
    """実データの colors が件数・排他の規約を満たすこと。"""

    def _entries(self):
        with open(CATALOG, encoding="utf-8") as fh:
            return json.load(fh).get("entries", [])

    def test_colors_count_and_exclusivity(self):
        sys.path.insert(0, str(ROOT / "draft-gen"))
        import bridge  # noqa: E402
        for e in self._entries():
            with self.subTest(entry=e.get("id")):
                cols = e.get("colors") or []
                self.assertTrue(1 <= len(cols) <= 3, f"colors の件数が 1..3 でない: {cols}")
                self.assertTrue(set(cols) <= bridge.CANONICAL_COLORS,
                                f"語彙外の主配色: {sorted(set(cols) - bridge.CANONICAL_COLORS)}")
                if "カラフル" in cols:
                    self.assertEqual(len(cols), 1, f"カラフルは単独指定のみ: {cols}")


if __name__ == "__main__":
    unittest.main()
