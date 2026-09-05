# KLK-094 参考サムネイルの段階表示を unittest スイートへ束ねるラッパー（tester所有）。
# - 動的: tests/site/smoke_klk094.node.js（純関数の実挙動＋配線）
# - 追加: **実データ（catalog.json）で本当に畳まれるか**を確かめる。
#   件数が閾値を割ると機能が無意味になり、逆に増えすぎると当初の問題が再発する。
import importlib.util
import json
import re
import shutil as _shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk094.node.js"
INDEX = ROOT / "draft-gen" / "index.html"
CATALOG = ROOT / "catalog" / "catalog.json"


@unittest.skipUnless(_shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK094Smoke(unittest.TestCase):
    def test_dynamic_smoke_passes(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0, "smoke_klk094.node.js failed:\n" + proc.stdout + proc.stderr
        )


class TestKLK094AgainstRealCatalog(unittest.TestCase):
    """★実データで本当に畳まれるか（閾値が実態と合っているか）。

    18件は「6列×3行の目安」として選んだ数。カタログが減って18件を割ると
    この機能は一度も働かなくなるし、業種で絞った結果が常に18件超なら
    「毎回ボタンを押す」体験になる。実データで妥当性を確かめる。
    """

    def setUp(self):
        if not CATALOG.is_file():
            self.skipTest("catalog.json が無い環境（空カタログ）")
        self.entries = json.loads(CATALOG.read_text(encoding="utf-8")).get("entries", [])

    def _limit(self):
        m = re.search(r"THUMBS_COLLAPSED_LIMIT\s*=\s*(\d+)", INDEX.read_text(encoding="utf-8"))
        self.assertIsNotNone(m, "THUMBS_COLLAPSED_LIMIT が見つからない")
        return int(m.group(1))

    def test_full_list_is_collapsed(self):
        """「すべての実績」や業種未選択では畳まれること（＝この機能が働くこと）。"""
        self.assertGreater(
            len(self.entries), self._limit(),
            "カタログが %d 件しかなく段階表示が働かない（閾値 %d）"
            % (len(self.entries), self._limit()),
        )

    def test_industry_filtered_lists_mostly_fit(self):
        """業種で絞った結果は、たいてい閾値に収まること（毎回ボタンを押させない）。

        既定の絞り込みは「近い業種のみ」。ここが常に溢れていたら閾値が小さすぎる。
        """
        counts = {}
        for e in self.entries:
            k = e.get("industry") or "(未設定)"
            counts[k] = counts.get(k, 0) + 1
        limit = self._limit()
        over = {k: v for k, v in counts.items() if v > limit}
        self.assertFalse(
            over,
            "業種で絞っても閾値 %d を超える業種がある（毎回「さらに表示」を押すことになる）: %s"
            % (limit, over),
        )

    def test_limit_is_a_sane_grid(self):
        """閾値が実用的な範囲にあること（極端な値への変更を検出）。"""
        limit = self._limit()
        self.assertGreaterEqual(limit, 6, "少なすぎて一覧性が失われる")
        self.assertLessEqual(limit, 36, "多すぎて畳む意味が薄れる")


if __name__ == "__main__":
    unittest.main()
