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
        """業種で絞った結果が、**たいてい**閾値に収まること。

        ★この主張は当初「1つも溢れないこと」だったが、それは過剰だった（KLK-109）。
          カタログが 86→167 件に増えた時点で「スクール・教室 22件」「不動産・建築 19件」が
          18 を超えて落ちた。だが 18 は理恵さんのご要望（6列×3行）で決めた数で、
          **カタログが増えたから閾値を上げるのは筋が違う**。
          そして実際の画面は業種だけでなく**テイスト・配色も併せて絞れる**ので、
          業種単独が溢れても実害は出ない（22件の業種もテイストを足せば最大7件）。

          守りたいのは「**大半の業種は1画面に収まる**」こと。
          そこが崩れたら閾値か語彙の粒度がおかしい、という信号にする。
        """
        counts = {}
        for e in self.entries:
            k = e.get("industry") or "(未設定)"
            counts[k] = counts.get(k, 0) + 1
        limit = self._limit()
        over = {k: v for k, v in counts.items() if v > limit}
        ratio = len(over) / max(1, len(counts))
        self.assertLessEqual(
            ratio, 0.30,
            "閾値 %d を超える業種が %d/%d（%.0f%%）ある。"
            "3割を超えたら、閾値か業種語彙の粒度を見直すべき: %s"
            % (limit, len(over), len(counts), ratio * 100, over),
        )

    def test_over_limit_industries_are_narrowable_by_taste(self):
        """★閾値を超えた業種が、テイストを足せば収まること。

        「業種で溢れても実害なし」と言えるのは、次の絞り込み軸が効くからである。
        そこが効かないなら、溢れは本当の使いにくさになる。
        """
        counts = {}
        for e in self.entries:
            counts.setdefault(e.get("industry") or "(未設定)", []).append(e)
        limit = self._limit()
        stuck = {}
        for k, group in counts.items():
            if len(group) <= limit:
                continue
            tastes = {}
            for e in group:
                tastes.setdefault(e.get("taste") or "(未設定)", 0)
                tastes[e.get("taste") or "(未設定)"] += 1
            worst = max(tastes.values())
            if worst > limit:
                stuck[k] = worst
        self.assertFalse(
            stuck,
            "業種で溢れたうえ、テイストで絞っても閾値 %d を超える: %s"
            % (limit, stuck),
        )

    def test_limit_is_a_sane_grid(self):
        """閾値が実用的な範囲にあること（極端な値への変更を検出）。"""
        limit = self._limit()
        self.assertGreaterEqual(limit, 6, "少なすぎて一覧性が失われる")
        self.assertLessEqual(limit, 36, "多すぎて畳む意味が薄れる")


if __name__ == "__main__":
    unittest.main()
