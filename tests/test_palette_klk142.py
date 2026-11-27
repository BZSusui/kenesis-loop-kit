# KLK-142 アクセントカラーの傾向を選べるようにする のテストを unittest スイートへ束ねるラッパー
# - 動的検査: tests/site/smoke_klk142.node.js（A1-A10・Node.jsが無い環境ではskip）
# - 静的検査: palette/index.html の欄・ACCENT_FAMS・リセット・イベント・URL・注記・配布物の禁止語
# 設計: docs/designs/KLK-142.md §4.8
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PALETTE = ROOT / "palette" / "index.html"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk142.node.js"
# 配布物に入れない3語（check_klk115 P3 と同じ）。この行自体が検査対象にならないよう分割して持つ
FORBIDDEN = ("DA" + "DS", "デジタル" + "庁", "design" + "-system")


@unittest.skipUnless(shutil.which("node"), "node が見つからないため動的検査をskip")
class TestKLK142DynamicSmoke(unittest.TestCase):
    """smoke_klk142.node.js（A1 未指定時の一致〜A10 明るい案を混ぜる語）が全PASSすること。"""

    def test_dynamic_smoke_pass(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "smoke_klk142.node.js failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK142Static(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PALETTE.read_text(encoding="utf-8")

    def test_section_follows_main_color(self):
        h = self.html
        i = h.index("メインカラーの傾向（カラー）")
        j = h.index("</details>", i)
        k = h.index("<details", j)
        nxt = h[k:h.index("</details>", k)]
        self.assertIn("アクセントカラーの傾向（カラー）", nxt)
        self.assertIn('id="accentfam"', nxt)
        self.assertIn('id="sumAccentFam"', nxt)

    def _accent_fams(self):
        m = re.search(r"const ACCENT_FAMS = \{(.*?)\n\};", self.html, re.S)
        self.assertIsNotNone(m, "ACCENT_FAMS が見つからない")
        rows = re.findall(
            r"^\s*(\w+):\s*\{\s*hJit:\s*[\d.]+,\s*light:\s*\[\s*[\d.]+,\s*([\d.]+),\s*[\d.]+\],"
            r"\s*dark:\s*\[\s*[\d.]+,\s*([\d.]+),\s*[\d.]+\]\s*\},",
            m.group(1), re.M,
        )
        return rows

    def test_accent_fams_keys_and_saturation(self):
        rows = self._accent_fams()
        cm = re.search(r"const COLORS = \[(.*?)\n\];", self.html, re.S)
        color_keys = re.findall(r"key:\s*'(\w+)'", cm.group(1))
        want = set(color_keys) - {"mono", "colorful"}
        self.assertEqual(len(want), 14)
        self.assertEqual({r[0] for r in rows}, want)
        self.assertEqual(len(rows), 14)
        for key, s_light, s_dark in rows:
            self.assertLessEqual(float(s_light), 0.72, key)
            self.assertLessEqual(float(s_dark), 0.72, key)

    def test_reset_event_init(self):
        h = self.html
        self.assertIn("document.querySelector('input[name=accentfam][value=\"\"]').checked = true;", h)
        self.assertIn("'#colorfam input, #accentfam input, #keywords input, .panel .slider input'", h)
        self.assertIn("buildColors();\nbuildAccentFams();", h)

    def test_url_key_and_notes(self):
        h = self.html
        m = re.search(r"const KNOWN = \[([^\]]*)\]", h)
        self.assertIsNotNone(m)
        self.assertIn("'ac'", m.group(1))
        self.assertIn("p.set('ac', accKey)", h)
        self.assertIn("同系色モード: メイン・サブの色相を揃え、アクセントは選んだ傾向の色", h)
        self.assertIn("エレガント: ベージュに濃い一点（黒・濃茶）と、選んだアクセントの色を添えた型", h)
        self.assertIn("金属色の定番ペアのサブに、選んだアクセントの傾向を合わせた配色", h)
        self.assertIn("（固定が優先）", h)

    def test_no_forbidden_words(self):
        for w in FORBIDDEN:
            self.assertNotIn(w, self.html, w)


if __name__ == "__main__":
    unittest.main()
