# KLK-119 背景トーン（bgTone）を主配色と別の2軸目として足す（tester所有）。
#
# ★経緯: 実ユーザーのフィードバック（2026-09-11）
#   「主配色にモノトーンはあるがホワイト・ブラックが無い。
#     背景で白や黒を使いつつモノトーンでない配色のラフが選びにくい」
#
#   主配色へ「ホワイト」「ブラック」を足す案は採らなかった。主配色は palette の
#   **色相ファミリー16種**であり、白黒は色相ではなく**背景の明暗**で軸が違う。
#   混ぜると「メインカラー＝白」から配色を作る意味が立たず、KLK-067 の
#   「タグ付けと配色生成が同じ言葉を話す」原則も崩れる。→ 2軸目にした（理恵さん判断）。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk119.py … 縦串の語彙一致・additive・検証の妨害注入・画面・規約
#   2. ここ … 絞り込みの純関数を直接突く（未設定の扱い・ファセット間 AND・主配色との独立）
#      「未設定のものがトーン絞り込みで出てこない」は仕様であり、事故ではない
import importlib.util
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk119.py"
CAT_HTML = ROOT / "draft-gen" / "catalog.html"


def load_bridge():
    spec = importlib.util.spec_from_file_location("bridge_klk119_t", ROOT / "draft-gen" / "bridge.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK119Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk119.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        # 主配色を汚していないこと・既存が壊れないことが実際に検査されたこと
        self.assertIn("A1 ★既存カタログが未設定のまま妥当", p.stdout)
        self.assertIn("U5 ★主配色のチップ数を汚していない", p.stdout)


class TestVocabulary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load_bridge()

    def test_two_values_in_order(self):
        self.assertEqual(self.b.CANONICAL_BG_TONES_ORDER, ["ライト", "ダーク"])
        self.assertEqual(self.b.CANONICAL_BG_TONES, {"ライト", "ダーク"})

    def test_colors_untouched(self):
        # 主配色は16種のまま。白黒を混ぜていないこと（この設計判断そのものを固定する）
        self.assertEqual(len(self.b.CANONICAL_COLORS), 16)
        self.assertNotIn("ホワイト", self.b.CANONICAL_COLORS)
        self.assertNotIn("ブラック", self.b.CANONICAL_COLORS)

    def test_screen_matches_bridge(self):
        src = CAT_HTML.read_text(encoding="utf-8")
        m = re.search(r'var CANONICAL_BG_TONES = \[(.*?)\];', src, re.S)
        self.assertIsNotNone(m, "画面に語彙が無い")
        self.assertEqual(re.findall(r'"([^"]+)"', m.group(1)), self.b.CANONICAL_BG_TONES_ORDER)


class TestValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load_bridge()

    def _cat(self, entry_extra):
        e = {"id": "cat-0001", "file": "cat-0001.png", "source": "own", "colors": ["ブルー"]}
        e.update(entry_extra)
        return {"schema": "klk-catalog", "version": 1, "entries": [e]}

    def test_optional(self):
        self.assertTrue(self.b.validate_catalog(self._cat({}))[0], "未設定が弾かれる")
        self.assertTrue(self.b.validate_catalog(self._cat({"bgTone": None}))[0], "null が弾かれる")

    def test_accepts_vocabulary(self):
        for v in self.b.CANONICAL_BG_TONES_ORDER:
            with self.subTest(v=v):
                self.assertTrue(self.b.validate_catalog(self._cat({"bgTone": v}))[0])

    def test_rejects_outside_vocabulary(self):
        # 妨害: 主配色に足したくなる語をそのまま bgTone へ入れる／別言語／空文字
        for bad in ("ホワイト", "ブラック", "light", "", "ライト ", ["ライト"]):
            with self.subTest(bad=bad):
                ok, errs = self.b.validate_catalog(self._cat({"bgTone": bad}))
                self.assertFalse(ok, "語彙外 %r が通った" % (bad,))
                self.assertTrue(any("bgTone" in e for e in errs), errs)

    def test_independent_of_colors(self):
        # 主配色と背景トーンは独立。ブルー×ダーク／モノトーン×ライト どちらも妥当
        for cols, bg in ((["ブルー"], "ダーク"), (["モノトーン"], "ライト"), (["ゴールド"], "ライト")):
            with self.subTest(cols=cols, bg=bg):
                self.assertTrue(self.b.validate_catalog(self._cat({"colors": cols, "bgTone": bg}))[0])

    def test_proposal_validated_too(self):
        mk = lambda bg: {"schema": self.b.PROPOSAL_SCHEMA, "version": self.b.PROPOSAL_VERSION,
                         "jobId": "a1", "items": [{"file": "x.png", "bgTone": bg}]}
        self.assertTrue(self.b.validate_proposal(mk("ライト"))[0])
        ok, errs = self.b.validate_proposal(mk("グレー"))
        self.assertFalse(ok, "取り込み案で語彙外が通った")
        self.assertTrue(any("bgTone" in e for e in errs), errs)

    def test_real_catalog_still_valid(self):
        path = ROOT / "catalog" / "catalog.json"
        if not path.is_file():
            self.skipTest("catalog.json が無い環境（社外秘・Git除外）")
        data = json.loads(path.read_text(encoding="utf-8"))
        ok, errs = self.b.validate_catalog(data)
        self.assertTrue(ok, "既存カタログが壊れた（additive でない）: %s" % errs[:3])


class TestFilterSemantics(unittest.TestCase):
    """絞り込みの意味を固定する。とくに「未設定は出ない」は仕様。"""

    @classmethod
    def setUpClass(cls):
        src = CAT_HTML.read_text(encoding="utf-8")
        i = src.index("function filterEntries")
        j = src.index("function sortEntries")
        cls.js = src[i:j]

    def test_bgtone_clause_exists(self):
        self.assertIn("s.bgTone", self.js)
        self.assertIn("e.bgTone", self.js)

    def test_unset_is_excluded_when_filtering(self):
        # 「白背景のものを探す」のに未タグが混ざったら絞り込みにならない。
        # indexOf(e.bgTone) < 0 は undefined を弾く＝未設定は出ない、という意味である
        self.assertRegex(self.js, r"s\.bgTone\.indexOf\(e\.bgTone\)\s*<\s*0")

    def test_facets_are_and(self):
        # ファセット間は AND（既存の流儀）。bgTone も早期 return で AND になっている
        for clause in ("s.industry", "s.taste", "s.source", "s.bgTone", "s.colors"):
            with self.subTest(clause=clause):
                self.assertIn(clause, self.js)


if __name__ == "__main__":
    unittest.main()
