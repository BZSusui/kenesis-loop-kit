# KLK-109 カタログの語彙とデータの整合（tester所有・総点検で発見）。
#
# ★見つかったこと
#   語彙の数が文書と実装で食い違っていた:
#     ・CATALOG_RULES に「テイスト語彙(暫定7種)」という古い記述（実装は10種）
#     ・SKILL に「主配色(16カテゴリ)」と書きながら括弧内の列挙が7つだけ
#     ・SKILL の別の行に「主配色7」
#   実データは正しかったので実害は出ていなかったが、**この規約は AI が読む**。
#   「16から選べ」と言いながら7つしか見せなければ、AI は7つから選ぶ。
#
#   ★さらに: 語彙は CANON_* の配列だけでなく**絞り込みチップ**にも書かれていた。
#     セレクタだけ見ていた検査は、チップを書き換える改悪をすり抜けた。
import importlib.util
import io
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk109.py"
CAT_HTML = (ROOT / "draft-gen" / "catalog.html").read_text(encoding="utf-8")
RULES = (ROOT / ".claude" / "skills" / "catalog-import" / "templates"
         / "CATALOG_RULES.md").read_text(encoding="utf-8")
SKILL = (ROOT / ".claude" / "skills" / "catalog-import" / "SKILL.md").read_text(encoding="utf-8")


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "klk109w_bridge", str(ROOT / "draft-gen" / "bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def js_array(name):
    m = re.search(name + r"\s*=\s*\[(.*?)\]", CAT_HTML, re.S)
    return [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()] if m else []


class TestKLK109Static(unittest.TestCase):
    def test_static_checks_pass(self):
        p = subprocess.run(["python3", str(STATIC_CHECKER)],
                           capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        self.assertEqual(p.returncode, 0, "check_klk109.py failed:\n" + p.stdout + p.stderr)


class TestKLK109OneSourceOfTruth(unittest.TestCase):
    """語彙の正が1つであること。数だけでなく中身まで。"""

    def test_industries_all_in_rules(self):
        for x in js_array("CANON_INDUSTRIES"):
            with self.subTest(x):
                self.assertIn(x, RULES)

    def test_tastes_all_in_rules(self):
        for x in js_array("CANON_TASTES"):
            with self.subTest(x):
                self.assertIn(x, RULES)

    def test_colors_all_in_rules(self):
        b = load_bridge()
        self.assertEqual(len(b.CANONICAL_COLORS), 16)
        for x in sorted(b.CANONICAL_COLORS):
            with self.subTest(x):
                self.assertIn(x, RULES)

    def test_filter_chips_share_the_same_vocabulary(self):
        """★絞り込みチップも同じ正から来ていること。

        セレクタだけ見ていた検査は、チップを書き換える改悪をすり抜けた。
        画面に出る語彙は**すべて**同じ正から来ていなければならない。
        """
        chips = [c for c in re.findall(r'<span class="fchip" data-val="([^"]+)"', CAT_HTML)
                 if c not in ("own", "ref") and c.strip()]
        self.assertGreater(len(chips), 20, "チップを読めていない（検査が空振り）")
        vocab = set(js_array("CANON_INDUSTRIES")) | set(js_array("CANON_TASTES"))
        for c in chips:
            with self.subTest(c):
                self.assertIn(c, RULES, "チップ %s が規約に無い" % c)
                self.assertIn(c, vocab, "チップ %s がセレクタの語彙に無い" % c)


class TestKLK109SkillShowsTheWholeVocabulary(unittest.TestCase):
    """★AI が読む規約は「見せた数」が実質の語彙になる。"""

    def test_skill_lists_all_16_colors(self):
        b = load_bridge()
        seg = SKILL[SKILL.find("**主配色**(`colors`)"):][:400]
        listed = [c for c in b.CANONICAL_COLORS if c in seg]
        self.assertGreaterEqual(
            len(listed), 16,
            "「16カテゴリから選べ」と書きながら %d 個しか見せていない。"
            "AI は見せた数から選ぶ" % len(listed))

    def test_no_stale_counts(self):
        for bad in ("暫定7種", "主配色7"):
            with self.subTest(bad):
                self.assertNotIn(bad, RULES)
                self.assertNotIn(bad, SKILL)


class TestKLK109DataIntegrity(unittest.TestCase):
    """実データが語彙に収まり、画像と1対1で対応していること。"""

    def setUp(self):
        p = ROOT / "catalog" / "catalog.json"
        if not p.is_file():
            self.skipTest("catalog.json が無い環境")
        self.entries = json.loads(p.read_text(encoding="utf-8")).get("entries", [])

    def test_all_values_in_vocabulary(self):
        b = load_bridge()
        ind, tas = set(js_array("CANON_INDUSTRIES")), set(js_array("CANON_TASTES"))
        bad = []
        for e in self.entries:
            if e.get("industry") and e["industry"] not in ind:
                bad.append(("industry", e.get("id"), e["industry"]))
            if e.get("taste") and e["taste"] not in tas:
                bad.append(("taste", e.get("id"), e["taste"]))
            for c in (e.get("colors") or []):
                if c not in b.CANONICAL_COLORS:
                    bad.append(("colors", e.get("id"), c))
            if e.get("columns") and e["columns"] not in b.CANONICAL_COLUMNS:
                bad.append(("columns", e.get("id"), e["columns"]))
        self.assertFalse(bad, "語彙外の値がある（絞り込みが効かなくなる）: %s" % bad[:5])

    def test_images_and_entries_are_one_to_one(self):
        used, missing = set(), []
        for e in self.entries:
            f = e.get("file") or e.get("image")
            if not f:
                missing.append((e.get("id"), "file キー無し"))
                continue
            name = Path(f).name
            used.add(name)
            if not (ROOT / "catalog" / "img" / name).is_file():
                missing.append((e.get("id"), f))
        orphan = [p.name for p in (ROOT / "catalog" / "img").glob("*") if p.name not in used]
        self.assertFalse(missing, "画像が無いエントリ: %s" % missing[:5])
        self.assertFalse(orphan, "参照されない画像: %s" % orphan[:5])

    def test_ids_unique_and_present(self):
        import collections
        ids = [e.get("id") for e in self.entries]
        self.assertTrue(all(ids), "ID が無いエントリがある")
        dup = [k for k, v in collections.Counter(ids).items() if v > 1]
        self.assertFalse(dup, "ID が重複している: %s" % dup)


if __name__ == "__main__":
    unittest.main()
