# KLK-117 型セレクタの日本語ラベル（tester所有）。
#
# ★経緯: 実ユーザーのフィードバック（2026-09-11）
#   「生成後に型を入れ替える際、型名が英語のみだとどのような型なのか掴めない」。
#   84型（14セクション×6型）に日本語ラベルを付け、compare.html のセレクタで
#   「日本語ラベル（マーカー）」として見せる。送る desiredType はマーカーのまま。
#
# ★このテストが守っているもの（3層）:
#   1. 静的   tests/site/check_klk117.py … ラベル表の網羅・一意・長さ／★規約からの根拠照合／
#             ブリッジの純粋関数／画面の使い方／規約 §13 の規定
#   2. 単体   ここ … 説明文の抽出とラベル語の分割（純粋関数）を、正常系と壊した系で突く。
#             とくに「規約を言い換えたラベル」を検知できることを妨害注入で確かめる
#   3. 実効果 tests/site/e2e_klk117.node.js … テンプレート→make_compare→実ブリッジ→
#             ヘッドレス Chrome で、**実際に描かれた <option> の文字**を見る。
#             labels を返さない旧ブリッジを模す妨害注入つき（剥がせたことを assert してから判定）
import importlib.util
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk117.py"
E2E = ROOT / "tests" / "site" / "e2e_klk117.node.js"

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


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_checker_functions():
    """checker を『関数だけ』読み込む（実行はしない・test_palette_klk111 と同じ作法）。

    check_klk117.py はスクリプト形式なので、そのまま import すると全チェックが走り
    最後の sys.exit でテストごと落ちる。ソースから関数定義部
    （最初のチェック実行 = bridge = load_bridge() より前）だけを切り出して exec する。
    """
    src = STATIC.read_text(encoding="utf-8")
    cut = src.index("bridge = load_bridge()")
    ns = {"__file__": str(STATIC)}
    exec(compile(src[:cut], str(STATIC), "exec"), ns)
    return ns


class TestKLK117Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk117.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        # 根拠の照合が実際に走っていること（ここが消えたら「自分で作って自分で正しいと言う」に戻る）
        self.assertIn("G2 ★ラベルの語がすべて規約の説明文に実在する", p.stdout)


class TestGroundingFunctions(unittest.TestCase):
    """根拠照合の純粋関数を、正常系と壊した系の両方で突く。"""

    @classmethod
    def setUpClass(cls):
        cls.c = load_checker_functions()

    def test_label_terms_splits_on_separators(self):
        self.assertEqual(self.c["label_terms"]("全面ビジュアル＋スクロール誘導"),
                         ["全面ビジュアル", "スクロール誘導"])
        self.assertEqual(self.c["label_terms"]("円形／型抜き画像"), ["円形", "型抜き画像"])
        self.assertEqual(self.c["label_terms"]("全面中央"), ["全面中央"])

    def test_label_terms_drops_one_char_fragments(self):
        # 1文字の断片は照合に使わない（「の」「＋」などで誤判定しない）
        self.assertNotIn("の", self.c["label_terms"]("左に絞り込みナビ＋右に結果"))

    def test_rule_description_reads_table_rows(self):
        d = self.c["rule_description"]("tab-switch")
        self.assertIn("タブ切替", d)
        self.assertNotIn("**", d, "強調記号が残っている（照合が偽陰性になる）")

    def test_rule_description_reads_prose_including_first_of_list(self):
        # §12.1.2 の散文。各セクションの先頭型は `- **VOICE** — ` の前置きが付く
        for marker, word in (("voice-cards", "声カード"),
                             ("flow-row", "横並び"),
                             ("staff-grid", "顔写真グリッド"),
                             ("voice-slider", "横スクロール風1行")):
            with self.subTest(marker=marker):
                self.assertIn(word, self.c["rule_description"](marker))

    def test_unknown_marker_has_no_description(self):
        self.assertEqual(self.c["rule_description"]("no-such-type-xyz"), "")

    def test_sabotage_paraphrased_label_is_caught(self):
        # 妨害: 規約の言い回しを勝手に言い換えたラベルは、根拠なしと判定されなければならない
        desc = self.c["rule_description"]("voice-slider")
        self.assertTrue(desc, "基線が取れていない")
        good = self.c["label_terms"]("横スクロール風1行")
        self.assertTrue(all(t in desc for t in good), "正しいラベルが落ちている")
        bad = self.c["label_terms"]("よこ스크롤っぽい1行")     # 言い換え＋別言語混入
        self.assertTrue(any(t not in desc for t in bad), "言い換えラベルを検知できない")

    def test_all_84_labels_are_grounded(self):
        # 静的 checker と同じ判定を、テスト側からも独立に行う（片方だけ緩むのを防ぐ）
        bridge = load(ROOT / "draft-gen" / "bridge.py", "bridge_klk117_test")
        n = 0
        for sec, table in bridge.SECTION_TYPE_LABELS.items():
            for marker, label in table.items():
                desc = self.c["rule_description"](marker)
                self.assertTrue(desc, "%s:%s に規約の説明が無い" % (sec, marker))
                for term in self.c["label_terms"](label):
                    self.assertIn(term, desc,
                                  "%s:%s ラベル「%s」の語「%s」が規約に無い" % (sec, marker, label, term))
                n += 1
        self.assertEqual(n, 84, "84型そろっていない（%d件）" % n)


class TestBridgeLookup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load(ROOT / "draft-gen" / "bridge.py", "bridge_klk117_lookup")

    def test_labels_match_pool_exactly(self):
        for sec, pool in self.b.SECTION_TYPE_POOLS.items():
            with self.subTest(sec=sec):
                self.assertEqual(set(self.b.SECTION_TYPE_LABELS[sec]), set(pool))

    def test_addr_lookup(self):
        self.assertEqual(len(self.b.labels_for_addr("GALLERY-01")), 6)
        self.assertEqual(self.b.labels_for_addr("NAV-01"), {})
        self.assertEqual(self.b.labels_for_addr("CTA-01"), {})
        self.assertEqual(self.b.labels_for_addr("../../etc/passwd"), {})

    def test_missing_label_falls_back_to_marker(self):
        # ラベル表に穴が空いても画面が空欄にならない（穴自体は check_klk117 L2 が落とす）
        saved = self.b.SECTION_TYPE_LABELS["MENU"].pop("tab-switch")
        try:
            self.assertEqual(self.b.labels_for_addr("MENU-01")["tab-switch"], "tab-switch")
        finally:
            self.b.SECTION_TYPE_LABELS["MENU"]["tab-switch"] = saved


class TestKLK117E2E(unittest.TestCase):
    """★実効果: 実際に描かれた選択肢の文字を見る。"""

    def test_selector_shows_japanese_labels(self):
        if not shutil.which("node"):
            self.skipTest("node が無い環境")
        ch = chrome_path()
        if not ch:
            self.skipTest("ヘッドレス Chrome が無い環境（静的・単体は上で担保）")
        env = dict(os.environ, KLK_E2E_CHROME=ch)
        p = subprocess.run(["node", str(E2E)], capture_output=True, text=True,
                           timeout=300, env=env, cwd=str(ROOT))
        if p.returncode == 3:
            self.skipTest("e2e が環境理由で SKIP: %s" % (p.stdout + p.stderr)[-300:])
        self.assertEqual(p.returncode, 0, "e2e_klk117.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("E1 ★選択肢が「日本語ラベル（マーカー）」で描かれる", p.stdout)
        self.assertIn("E6 ★labels を実際に剥がした応答", p.stdout)


if __name__ == "__main__":
    unittest.main()
