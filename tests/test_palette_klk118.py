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

    def test_cramped_rule_exists(self):
        # KLK-122: 短いラベルの窮屈な折り返し
        self.assertIn("### 8.2 短いラベルを折らない", self.rules)
        self.assertIn("1行に6文字も入らない幅へ詰めてはならない", self.rules)
        self.assertIn("箱の高さ ÷ 行高では測れない", self.rules)

    def test_inline_label_rule_exists(self):
        # KLK-122: 見出しと説明が同じ行に流れる（幅とは無関係の不具合）
        self.assertIn("### 8.3 見出しと説明文を同じ行に流さない", self.rules)
        self.assertIn("`margin` を指定しても**同じ行につながる**", self.rules)

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


class TestE2EHarnessDoesNotHang(unittest.TestCase):
    """★e2e ハーネスが「開かないまま永久に待つ」作りになっていないこと（KLK-122）。

    単独なら5秒で終わる e2e が、入れ子でスイートを回すと 300 秒のタイムアウトで落ちていた。
    原因は CDP の WebSocket 接続待ちに上限が無かったこと
    （`await new Promise(r => ws.addEventListener('open', r))`）。
    Chrome が何個も立ち上がる状況で接続できないと、そこで固まる。
    **待ちには必ず上限を置く**＝開かなければ「開かなかった」と分かる形で早く失敗する。
    """

    E2E_FILES = ("e2e_klk116.node.js", "e2e_klk117.node.js", "e2e_klk120.node.js")

    @staticmethod
    def _code_only(src):
        """コメントを取り除いて**実際に動く部分**だけ返す。

        ★注意書きの中で悪い書き方を引用していると、素朴な文字列検索がそれに当たる
        （実際に踏んだ）。検査は「コードがどう書かれているか」を見るものなので、
        コメントは除いてから判定する。
        """
        import re
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)      # ブロックコメント
        return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))

    def test_no_unbounded_websocket_wait(self):
        for name in self.E2E_FILES:
            with self.subTest(name=name):
                src = (ROOT / "tests" / "site" / name).read_text(encoding="utf-8")
                code = self._code_only(src)
                self.assertNotIn("await new Promise(r => ws.addEventListener('open', r))", code,
                                 "%s に上限の無い接続待ちが残っている" % name)
                self.assertIn("function openWs(", code, "%s に上限つきの待ちが無い" % name)

    def test_code_only_strips_comments(self):
        # 判定のしかた自体を確かめる（コメントの引用に当たらないこと・コードは残ること）
        sample = "// `await new Promise(r => ws.addEventListener('open', r))` は駄目\n"
        sample += "/* これも await new Promise(r => ws.addEventListener('open', r)); */\n"
        sample += "await openWs(ws);\n"
        code = self._code_only(sample)
        self.assertNotIn("await new Promise(r => ws.addEventListener('open', r))", code)
        self.assertIn("await openWs(ws);", code)

    def test_wait_has_timeout_and_error_paths(self):
        for name in self.E2E_FILES:
            with self.subTest(name=name):
                src = (ROOT / "tests" / "site" / name).read_text(encoding="utf-8")
                self.assertIn("setTimeout(() => rej(", src, "%s: 期限切れで失敗しない" % name)
                self.assertIn("addEventListener('error'", src, "%s: エラーで失敗しない" % name)
                self.assertIn("addEventListener('close'", src, "%s: 切断で失敗しない" % name)


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

    def test_detects_cramped_label(self):
        # 妨害: ナビ項目を極端に狭くする → 短いラベルが折れて捕まるはず
        # 見本01 に実在する日本語の短いラベル（「席を予約する」）を極端に狭くする
        p = self._sabotage(".hero-cta{max-width:30px !important;}", "cramped.html")
        r = run_tool([p], 768)
        self.assertEqual(r.returncode, 1, "窮屈な折り返しを検出できない:\n%s" % r.stdout[-1500:])
        self.assertIn("短いラベルの窮屈な折り返し", r.stdout)

    def test_padding_does_not_cause_false_positive(self):
        # ★上下に大きな余白を足しただけでは「2行」と誤判定しないこと
        #   （箱の高さ÷行高で測っていたときは、ボタンの余白で誤検出していた）
        p = self._sabotage(".hero-cta, .contact-btn, a{padding-top:40px !important;padding-bottom:40px !important;}",
                           "padded.html")
        r = run_tool([p], 768)
        self.assertNotIn("短いラベルの窮屈な折り返し", r.stdout,
                         "余白だけで窮屈と誤判定している:\n%s" % r.stdout[-1200:])

    def test_detects_sibling_overlap(self):
        # 横並びのきょうだいを重ねる → 重なりとして捕まるはず
        # （見本03 の ACCESS で地図が隣の情報パネルに重なっていたのが実例）
        p = self._sabotage(".m-menu > *{margin-right:-120px;}", "overlap.html")
        r = run_tool([p], 768)
        self.assertEqual(r.returncode, 1, "重なりを検出できない:\n%s" % r.stdout[-1500:])


if __name__ == "__main__":
    unittest.main()
