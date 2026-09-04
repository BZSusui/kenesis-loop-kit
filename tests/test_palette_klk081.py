# KLK-081 を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk081.py（R群=規約 / G群=グリッドの実測 / U群=UI）
# - 動的: tests/site/smoke_klk079.node.js（N11-N13 が本件のケース）
# - 追加: **グリッドの列数とアイテム数の突き合わせ**を数式で固定する。
#   KLK-075 は列数だけを計算し、パネル数(6)と照らさなかったため段落ちした。
#   同じ形（auto-fit + 固定個数）が規約や見本へ戻っていないかを見張る。
import glob
import re
import shutil as _shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk081.py"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk079.node.js"
RULES = ROOT / ".claude" / "skills" / "draft-generate" / "templates" / "DRAFT_RULES.md"


class TestKLK081Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0, "check_klk081.py failed:\n" + proc.stdout + proc.stderr
        )


@unittest.skipUnless(_shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK081CompareUiSmoke(unittest.TestCase):
    """見本・取得失敗・未起動で「読み込み中…」のまま固まらないこと（N11-N13）。"""

    def test_dynamic_smoke_passes(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0, "smoke_klk079.node.js failed:\n" + proc.stdout + proc.stderr
        )


class TestKLK081NoFixedCountWithAutoFit(unittest.TestCase):
    """★「個数が固定のグリッド」に auto-fit を使わないこと。

    auto-fit は列数を画面幅から決めるので、アイテム数と一致する保証がない。
    KLK-075 はここを突き合わせず、1200〜1280px で 6枚が 5+1 に段落ちした。
    規約と見本の両方で、同じ形が戻っていないかを見張る。
    """

    @staticmethod
    def _cols_autofit(width, minw=220, gap=4):
        return max(1, int((width + gap) // (minw + gap)))

    def test_autofit_would_wrap_six_panels(self):
        """前提の確認: auto-fit(220px) は 1024〜1280px で 6枚を収めきれない。"""
        for width in (1024, 1200, 1280):
            self.assertLess(
                self._cols_autofit(width), 6,
                "%dpx で6列入ってしまう（前提が変わった）" % width,
            )
        for width in (1366, 1440):
            self.assertGreaterEqual(self._cols_autofit(width), 6)

    def test_rules_do_not_prescribe_autofit_for_panel_band(self):
        text = RULES.read_text(encoding="utf-8")
        i = text.find("#### 3.0.1")
        seg = text[i:text.find("### 3.1", i)] if i >= 0 else ""
        self.assertIn("grid-auto-flow: column", seg)
        # 「使わない」という**禁止の文脈**以外で auto-fit を勧めていないこと
        for line in seg.splitlines():
            if "auto-fit" in line:
                self.assertTrue(
                    ("使わない" in line) or ("列数" in line) or ("|" in line),
                    "§3.0.1 が auto-fit を勧める書き方で残っている: " + line.strip()[:90],
                )

    def test_samples_panel_band_guarantees_one_row(self):
        band_re = re.compile(r"panel-band[^{}]*\.film(?:-band)?\s*\{([^}]*)\}")
        found = 0
        for p in sorted(glob.glob(str(ROOT / "samples" / "*" / "index-*.html"))):
            html = Path(p).read_text(encoding="utf-8")
            if not re.search(r'data-hero=["\']?panel-band', html):
                continue
            css = re.sub(r"/\*.*?\*/", "", "\n".join(
                re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)), flags=re.S)
            m = band_re.search(css)
            self.assertIsNotNone(m, "帯のルールが見つからない: %s" % p)
            flat = re.sub(r"\s+", "", m.group(1))
            self.assertIn("grid-auto-flow:column", flat, "1行が保証されていない: %s" % p)
            self.assertNotIn("auto-fit", flat, "auto-fit が戻っている: %s" % p)
            found += 1
        self.assertGreaterEqual(found, 2, "panel-band の見本が足りない（検査が素通り）")


if __name__ == "__main__":
    unittest.main()
