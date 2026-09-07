# KLK-103 compare.html のテンプレート化（tester所有のラッパー）。
# - 静的＋レンダリング: tests/site/check_klk103.py（A〜P）
# - 追加: **決定論**（同じ入力から同じ出力）と、**手書きへの逆戻り**を見張る。
#   テンプレート化の価値は「毎回同じものが出る」ことなので、そこを直接確かめる。
import io
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "draft-gen"))
import make_compare as mc  # noqa: E402

STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk103.py"


class TestKLK103Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(proc.returncode, 0,
                         "check_klk103.py failed:\n" + proc.stdout + proc.stderr)


class TestKLK103Deterministic(unittest.TestCase):
    """★同じ入力から同じ出力になること。

    テンプレート化の狙いは「毎回同じものが出る」こと。
    LLM に書かせていた頃は、同じ指示書から**毎回違う compare.html** が出ていた
    （見本3点はクラス名すら別物だった：`.proj-name` と `.pname`）。
    """

    def test_same_input_same_output(self):
        folder = str(ROOT / "samples" / "01_カフェ_1カラム")
        a = mc.build_compare_html(folder, data_folder="samples/01_カフェ_1カラム")
        b = mc.build_compare_html(folder, data_folder="samples/01_カフェ_1カラム")
        self.assertEqual(a, b, "同じ入力なのに出力が違う（決定論が壊れている）")

    def test_all_samples_share_the_same_js(self):
        """3つの見本の JS が**完全に同一**であること。

        以前は見本ごとに手で書かれていて、同じ振る舞いなのに実装が違った。
        いまは同じテンプレート由来なのだから、1バイトも違ってはならない。
        """
        js = {}
        for p in sorted((ROOT / "samples").glob("*/compare.html")):
            h = p.read_text(encoding="utf-8")
            blocks = re.findall(r"<script[^>]*>(.*?)</script>", h, re.S)
            js[p.parent.name] = "\n".join(blocks)
        self.assertGreaterEqual(len(js), 3)
        first = sorted(js)[0]
        for name in sorted(js):
            with self.subTest(name):
                self.assertEqual(js[name], js[first],
                                 "%s の JS が %s と違う（テンプレート由来でない）" % (name, first))


class TestKLK103NoRegressionToHandAuthoring(unittest.TestCase):
    """規約とスキルが「書くな」と言い続けていること。

    ここが緩むと生成側が再び書き始め、テンプレートが使われなくなる。
    その時点で KLK-102 の欠落が再発する（が、誰も気づかない）。
    """

    def test_rules_forbid_authoring(self):
        rules = (ROOT / ".claude" / "skills" / "draft-generate" / "templates"
                 / "DRAFT_RULES.md").read_text(encoding="utf-8")
        seg = rules[rules.find("### ★13.0"):rules.find("### 13.1")]
        self.assertTrue(seg, "§13.0 が無い")
        self.assertIn("書いてはならない", seg)
        self.assertIn("make_compare.py", seg)
        self.assertIn("毎回同じものを書かせるな", seg)

    def test_skill_runs_the_tool(self):
        skill = (ROOT / ".claude" / "skills" / "draft-generate"
                 / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("make_compare.py", skill)

    def test_bridge_writes_it_automatically(self):
        bridge = (ROOT / "draft-gen" / "bridge.py").read_text(encoding="utf-8")
        self.assertIn("def write_compare_html", bridge)
        self.assertIn("write_compare_html(abs_folder", bridge)

    def test_bridge_does_not_import_sibling_at_module_level(self):
        """隣のモジュールをモジュール先頭で import しないこと。

        bridge.py は「import で bind/実行が起きない」設計で、テストは
        spec_from_file_location で直接読み込む。先頭に `import make_compare` を置くと
        sys.path に draft-gen/ が無いローダーで**丸ごと import できなくなる**
        （実際に checker 10本が ModuleNotFoundError で落ちた）。
        """
        bridge = (ROOT / "draft-gen" / "bridge.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"(?m)^(import|from) make_compare\b", bridge))

    def test_bridge_loads_via_spec_from_file_location(self):
        """テストと同じ読み込み方（spec_from_file_location）で bridge が読めること。

        これが壊れると checker が一斉に落ちる。実際に落ちたので回帰として残す。
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "klk_bridge_probe", str(ROOT / "draft-gen" / "bridge.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)          # 例外が出なければ OK
        self.assertTrue(hasattr(mod, "write_compare_html"))


class TestKLK103PureFunctions(unittest.TestCase):
    """純関数の境界。副作用なしで組めることを確かめる。"""

    def test_find_variant_files_prefers_multi(self):
        self.assertEqual(
            [L for L, _ in mc.find_variant_files(str(ROOT / "samples" / "01_カフェ_1カラム"))],
            ["a", "b", "c"])

    def test_find_variant_files_empty_folder(self):
        self.assertEqual(mc.find_variant_files(str(ROOT / "docs")), [])

    def test_missing_instruction_is_survivable(self):
        """指示書が無くても組めること（fail-soft）。案件名はフォルダ名から復元する。"""
        self.assertEqual(mc.read_instruction(str(ROOT / "docs")), {})
        self.assertEqual(mc.project_name_from_folder("mockups/2026-09-07_案件名"), "案件名")
        self.assertEqual(mc.date_from_folder("mockups/2026-09-07_案件名"), "2026-09-07")

    def test_safe_color_rejects_non_hex(self):
        for bad in ("red", "#12345", "#gggggg", None, 42, "#123456;}"):
            with self.subTest(bad):
                self.assertEqual(mc.safe_color(bad, "#ffffff"), "#ffffff")
        self.assertEqual(mc.safe_color("#A1B2C3", "#ffffff"), "#A1B2C3")

    def test_single_variant_drops_variant_switch_only(self):
        files = [("", "index.html")]
        self.assertNotIn('name="variant"', mc.render_radios(files))
        self.assertEqual(mc.render_seg(files), "")
        self.assertEqual(mc.render_thumbstrip(files), "")
        # 幅切替と 🔄 はテンプレート側にあるので単案でも残る（KLK-092）
        self.assertIn("🖨", mc.render_print_buttons(files))
        self.assertIn("index.html", mc.render_panes(files))


if __name__ == "__main__":
    unittest.main()
