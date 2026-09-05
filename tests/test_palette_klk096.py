# KLK-096 冷えた状態での規約検証と、検証の道具の完成（tester所有）。
#
# ★KLK-076 が残した宿題:
#   当時の「再生成」は既存フォルダの上に重ねて実行されたため、
#   違反の無かったファイルは1バイトも変わらなかった＝**差分修正であって、
#   まっさらな状態からの生成ではない**。よって「規約が冷えた状態でも効くか」は未実証だった。
#
# ★この期で答えが出た:
#   KLK-088/089/092 の実機検証は**すべて新規フォルダ**（＝冷えた状態）への生成で、
#   4規約（§3.0・§3.0.1・§4.1.1・§8.1）がすべて守られていた。
#   ただし §3.0.1 と §4.1.1 は道具が見ていなかったので、ここで足した。
#   これで **verify-mockup 1本で6規約すべてを任意のフォルダに当てられる**。
import glob
import importlib.util
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "verify-mockup.py"
sys.path.insert(0, str(ROOT / "draft-gen"))
import bridge  # noqa: E402


def _load_tool():
    spec = importlib.util.spec_from_file_location("klk096_verify", str(TOOL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK096ToolCoversAllSixRules(unittest.TestCase):
    """★verify-mockup 1本で6規約すべてを見られること（第6期の見本作り直しで使う）。"""

    def test_tool_documents_all_six(self):
        text = TOOL.read_text(encoding="utf-8")
        for rule in ("§3.0 ", "§3.0.1", "§4.1.1", "§8.1", "§12.1.3", "composition"):
            self.assertIn(rule, text, "verify-mockup が %s を挙げていない" % rule)

    def test_panel_band_autofit_is_caught(self):
        """§3.0.1 — auto-fit へ戻すと段落ちする（KLK-081 の再発を防ぐ）。"""
        good = ('<style>.m-hero[data-hero=panel-band] .film{display:grid;'
                'grid-auto-flow:column;grid-auto-columns:1fr;gap:4px;}</style>'
                '<section class="sec"><div class="addr"><span class="pin">MV-01</span></div>'
                '<div class="m-hero" data-hero="panel-band"><div class="film">'
                '<div class="cell"></div></div></div></section>')
        self.assertEqual(bridge.find_quality_warnings(good, "MV-01"), [])
        bad = good.replace("grid-auto-flow:column;grid-auto-columns:1fr",
                           "grid-template-columns:repeat(auto-fit,minmax(220px,1fr))")
        self.assertTrue(any("auto-fit" in w for w in bridge.find_quality_warnings(bad, "MV-01")))

    def test_panel_band_max_height_is_caught(self):
        html = ('<style>.m-hero[data-hero=panel-band] .film{display:grid;'
                'grid-auto-flow:column;grid-auto-columns:1fr;gap:4px;max-height:130px;}</style>'
                '<section class="sec"><div class="addr"><span class="pin">MV-01</span></div>'
                '<div class="m-hero" data-hero="panel-band"><div class="film">'
                '<div class="cell"></div></div></div></section>')
        self.assertTrue(any("max-height" in w for w in bridge.find_quality_warnings(html, "MV-01")))

    def test_mv_line_break_is_caught(self):
        """§4.1.1 — 2文あるのに <br> が無いと、幅によって毎回違う位置で切れる。"""
        tool = _load_tool()
        d = Path(tempfile.mkdtemp(prefix="klk096_"))
        try:
            page = ('<html><head><style>.x{}</style></head><body>'
                    '<section class="sec"><div class="addr"><span class="pin">MV-01</span></div>'
                    '<div class="m-hero" data-hero="full">'
                    '<p class="lead">%s</p></div></section></body></html>')
            ok = d / "index.html"
            ok.write_text(page % "初回相談は無料です。<br>まずはお話をお聞かせください。", encoding="utf-8")
            self.assertEqual([w for w in tool.check_file(str(ok)) if "§4.1.1" in w], [])
            ok.write_text(page % "初回相談は無料です。まずはお話をお聞かせください。", encoding="utf-8")
            out = [w for w in tool.check_file(str(ok)) if "§4.1.1" in w]
            self.assertTrue(out, "句点で改行されていないのに検出しない")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestKLK096ColdGenerationsAreClean(unittest.TestCase):
    """★冷えた状態（新規フォルダ）で生成したものが6規約を守っていること。

    KLK-076 の宿題への答え。このセッションの実機検証で作った3件は、
    いずれも**既存フォルダの上書きではなく新規生成**だった。
    """

    COLD = [
        "mockups/2026-09-05_サンプル2カラム構成",
        "mockups/2026-09-05_サンプル単案テスト",
    ]

    def test_cold_generations_pass_strict(self):
        dirs = [str(ROOT / d) for d in self.COLD if (ROOT / d).is_dir()]
        if not dirs:
            self.skipTest("冷えた生成の検証フォルダが残っていない（掃除後は skip）")
        proc = subprocess.run(
            ["python3", str(TOOL)] + dirs + ["--strict"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(proc.returncode, 0,
                         "冷えた状態の生成が規約に違反している:\n" + proc.stdout)

    def test_samples_pass_strict(self):
        """同梱の見本も6規約すべてで違反ゼロ（配布物の品質）。"""
        dirs = sorted(str(d) for d in (ROOT / "samples").glob("*") if d.is_dir())
        proc = subprocess.run(
            ["python3", str(TOOL)] + dirs + ["--strict"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()
