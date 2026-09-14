# KLK-118 768px での実描画レイアウト検査（tester所有）。
#
# ★経緯: 実ユーザーのフィードバック（2026-09-11）
#   「生成後のレスポンシブ(特に768px)が崩れている。背景から要素がはみ出たり、
#     横並びが画面外にはみ出たりする」「アタリの比率が 3:4(4:3) から大きく逸脱して細長い」
#
# ★なぜ既存の検査では足りなかったか:
#   verify-mockup.py / bridge.find_quality_warnings は **CSS の宣言**を読む。
#   「aspect-ratio:16/7 と書いてある」は捕まえられるが、
#   「4/3 と書いてあるのに描かれた結果が細長い」「768px で画面からはみ出す」は捕まえられない。
#   そこで tools/verify-responsive.node.js（実際に描いて測る）を新設した。
#
# ★このテストが守っているもの:
#   1. 出荷中の見本（samples/）が 768px で崩れていないこと ＝ 回帰の防止
#   2. 検査そのものが**壊れた入力を捕まえられる**こと（妨害注入）。
#      「崩れが無い」と「検査が空回りしている」は見分けが付かないので、
#      わざと崩したページを食わせて検出できることを確かめる
#   3. 規約 §3.0.2／§3.0.3 に、判定の根拠（許容帯・表を器で包む）が書かれていること
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "verify-responsive.node.js"
RULES = ROOT / ".claude" / "skills" / "draft-generate" / "templates" / "DRAFT_RULES.md"
SAMPLES = sorted((ROOT / "samples").glob("*/index*.html"))

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
)


def chrome_path():
    for c in CHROME_CANDIDATES:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def run_tool(paths, width=768, extra=()):
    env = dict(os.environ)
    ch = chrome_path()
    if ch:
        env["KLK_CHROME"] = ch
    p = subprocess.run(["node", str(TOOL)] + [str(x) for x in paths]
                       + ["--width=%d" % width] + list(extra),
                       capture_output=True, text=True, timeout=600, env=env, cwd=str(ROOT))
    return p


class TestRulesDocument(unittest.TestCase):
    """判定の根拠が規約にあること（数値をツールだけが知っている状態にしない）。"""

    @classmethod
    def setUpClass(cls):
        cls.rules = RULES.read_text(encoding="utf-8")

    def test_band_section_exists(self):
        self.assertIn("#### 3.0.2 実際に描いたときの許容帯", self.rules)
        for v in ("0.68", "1.47", "0.40", "3.00", "1.35", "1.65"):
            self.assertIn(v, self.rules, "許容帯の数値 %s が規約に無い" % v)

    def test_band_matches_tool(self):
        # 規約の数値とツールの数値がずれていないこと（片方だけ直すのを防ぐ）
        src = TOOL.read_text(encoding="utf-8")
        for lo, hi in (("0.68", "1.47"), ("0.40", "3.00"), ("1.35", "1.65")):
            self.assertRegex(src, r"lo:\s*%s,\s*hi:\s*%s" % (lo, hi),
                             "ツールの帯 %s〜%s が規約と一致しない" % (lo, hi))

    def test_table_wrapper_rule_exists(self):
        self.assertIn("#### 3.0.3 列数の多い表は、幅に関係なく横スクロールできる器に入れる", self.rules)
        self.assertIn("640px 以下に限定しない", self.rules)

    def test_mosaic_guard_exists(self):
        self.assertIn("1つのタイルを1行の高さのまま3列以上にまたがせない", self.rules)


class TestSamplesAreClean(unittest.TestCase):
    """出荷中の見本が 768px で崩れていないこと。"""

    def test_samples_pass_at_768(self):
        if not shutil.which("node"):
            self.skipTest("node が無い環境")
        if not chrome_path():
            self.skipTest("ヘッドレス Chrome が無い環境")
        self.assertTrue(SAMPLES, "見本が見つからない")
        p = run_tool(SAMPLES, 768)
        if p.returncode == 3:
            self.skipTest("環境理由で SKIP: %s" % (p.stdout + p.stderr)[-200:])
        self.assertEqual(p.returncode, 0,
                         "見本が 768px で崩れています:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn("崩れは見つかりませんでした", p.stdout)


class TestSabotageIsCaught(unittest.TestCase):
    """★検査が空回りしていないこと。わざと崩して、捕まえられるかを見る。"""

    @classmethod
    def setUpClass(cls):
        if not shutil.which("node") or not chrome_path():
            raise unittest.SkipTest("node / ヘッドレス Chrome が無い環境")
        cls.base = SAMPLES[0] if SAMPLES else None
        if cls.base is None:
            raise unittest.SkipTest("見本が無い")
        cls.tmp = tempfile.mkdtemp(prefix="klk118_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def _sabotage(self, extra_css, name):
        """見本に CSS を1つ足した複製を作る（原本は触らない）。"""
        html = self.base.read_text(encoding="utf-8")
        self.assertIn("</style>", html, "style が見つからない")
        broken = html.replace("</style>", extra_css + "\n</style>", 1)
        self.assertNotEqual(broken, html, "妨害注入が効いていない")
        path = Path(self.tmp) / name
        path.write_text(broken, encoding="utf-8")
        return path

    def test_detects_horizontal_overflow(self):
        # 画面より広い要素を差し込む → 横スクロール／はみ出しとして捕まるはず
        p = self._sabotage(".m-sec{width:1200px;}", "overflow.html")
        r = run_tool([p], 768)
        self.assertEqual(r.returncode, 1, "はみ出しを検出できない:\n%s" % r.stdout[-1500:])
        self.assertTrue("横スクロール" in r.stdout or "はみ出し" in r.stdout, r.stdout[-1500:])

    def test_detects_flat_atari(self):
        # アタリを極端に平たくする（16/3）→ 比率逸脱として捕まるはず
        p = self._sabotage(".atari{aspect-ratio:16/3 !important;min-height:0 !important;}", "flat.html")
        r = run_tool([p], 768)
        self.assertEqual(r.returncode, 1, "比率逸脱を検出できない:\n%s" % r.stdout[-1500:])
        self.assertIn("アタリの比率逸脱", r.stdout)

    def test_16_9_is_not_allowed(self):
        # 16/9（1.778）は規約が明確に否定している平たさ。帯の外であること
        p = self._sabotage(".atari{aspect-ratio:16/9 !important;min-height:0 !important;}", "wide169.html")
        r = run_tool([p], 768)
        self.assertEqual(r.returncode, 1, "16/9 が通ってしまう:\n%s" % r.stdout[-1500:])

    def test_4_3_and_3_4_are_allowed(self):
        # 4:3 と 3:4 はどちらも許容（理恵さんの指示）。誤検知しないこと
        for ratio, name in (("4/3", "ok43.html"), ("3/4", "ok34.html")):
            with self.subTest(ratio=ratio):
                p = self._sabotage(".atari{aspect-ratio:%s !important;min-height:0 !important;}" % ratio, name)
                r = run_tool([p], 768)
                self.assertNotIn("アタリの比率逸脱", r.stdout,
                                 "%s を誤って違反と判定している:\n%s" % (ratio, r.stdout[-1200:]))

    def test_detects_sibling_overlap(self):
        # 横並びのきょうだいを重ねる → 重なりとして捕まるはず
        # （見本03 の ACCESS で地図が隣の情報パネルに重なっていたのが実例）
        p = self._sabotage(".m-menu > *{margin-right:-120px;}", "overlap.html")
        r = run_tool([p], 768)
        self.assertEqual(r.returncode, 1, "重なりを検出できない:\n%s" % r.stdout[-1500:])


if __name__ == "__main__":
    unittest.main()
