# KLK-111 DADS導入がモック生成システムと競合しないこと（tester所有）。
#
# ★経緯: 別環境でDADS導入時に WIREFRAME_RULES.md へDADS規則を混入させ、
#   配色設定が競合して組込みが一度中止された。再導入では
#   「docs/design-system/ への配置＋設計・実装・レビュー3工程の参照ルール」に限定し、
#   生成規約（DRAFT_RULES / WIREFRAME_RULES）と palette/ は既存の配色規約を正として維持する。
#
# ★このテストが守っているもの:
#   - 隔離の機械的強制（生成システム側に DADS 参照が二度と混入しない）
#   - checker 自体が劣化を検知できること（妨害文字列を注入して検出を確認する。
#     実ファイルは書き換えない — 純粋関数へ注入する）
import io
import os
import subprocess
import tempfile
import unittest
from importlib import util as importlib_util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk111.py"


def load_checker_functions():
    """checker を『関数だけ』読み込む（実行はしない）。

    check_klk111.py はスクリプト形式で import すると全チェックが走るため、
    ソースから関数定義部（最初のチェック実行より前）だけを切り出して exec する。
    """
    src = io.open(STATIC_CHECKER, encoding="utf-8").read()
    cut = src.index("# A. 隔離")
    head = src[:cut]
    ns = {"__file__": str(STATIC_CHECKER)}
    exec(compile(head, str(STATIC_CHECKER), "exec"), ns)
    return ns


class TestKLK111StaticChecker(unittest.TestCase):
    def test_static_checker_passes(self):
        """checker本体（パッケージ実ビルド込み）が全件PASSする。"""
        p = subprocess.run(["python3", str(STATIC_CHECKER)],
                           capture_output=True, text=True, timeout=900)
        self.assertEqual(p.returncode, 0,
                         "check_klk111.py 失敗:\n%s" % p.stdout[-2000:])
        self.assertIn(", 0 failed", p.stdout)
        # 実ビルド部（D）が省略されずに走ったことまで確認する
        # （--fast で走ると D が無くても "0 failed" になり得るため）
        self.assertIn("D1 パッケージ実ビルドが成功する", p.stdout)
        self.assertIn("D2 ★実際に作ったパッケージに DADS 49種と出典が同梱される", p.stdout)
        self.assertIn("D3 ★パッケージ内の生成システム側にも DADS 参照が無い", p.stdout)


class TestDadsIsolation(unittest.TestCase):
    """隔離判定の純粋関数を直接検証する（実ファイルは書き換えない）。"""

    @classmethod
    def setUpClass(cls):
        cls.ns = load_checker_functions()

    def test_clean_text_is_clean(self):
        self.assertEqual(self.ns["find_dads_refs"]("配色はDRAFT_RULES §5に従う"), [])

    def test_sabotage_each_token_is_detected(self):
        # 妨害: 生成規約へDADS参照が混入した想定の3パターン。すべて検知できること
        cases = {
            "design-system": "UIは docs/design-system/ の仕様に従うこと",
            "デジタル庁": "配色はデジタル庁デザインシステムの基準を優先する",
            "DADS": "フォーカスは DADS の Yellow-300 + Black とする",
        }
        for token, text in cases.items():
            hits = self.ns["find_dads_refs"](text)
            self.assertIn(token, hits, "妨害が検知されない: %r" % text)

    def test_real_rules_would_fail_if_contaminated(self):
        # 実物の WIREFRAME_RULES に「前回の競合と同種の1行」を足した状態を模す。
        # （前回はここへの混入が競合の正体だった）
        rules = (ROOT / ".claude" / "skills" / "wireframe-gen" /
                 "templates" / "WIREFRAME_RULES.md").read_text(encoding="utf-8")
        self.assertEqual(self.ns["find_dads_refs"](rules), [], "基線が既に汚染")
        sabotaged = rules + "\n- 配色はデジタル庁デザインシステムに準拠する\n"
        self.assertTrue(self.ns["find_dads_refs"](sabotaged), "混入を検知できない")

    def test_isolated_targets_cover_the_rules_files(self):
        # 隔離対象の走査が、前回競合した当のファイルを実際に含んでいること
        files = self.ns["isolated_tracked_files"]()
        self.assertIn(".claude/skills/wireframe-gen/templates/WIREFRAME_RULES.md", files)
        self.assertIn(".claude/skills/draft-generate/templates/DRAFT_RULES.md", files)
        self.assertTrue(any(f.startswith("palette/") for f in files))
        self.assertTrue(any(f.startswith("draft-gen/") for f in files))


class TestDadsIntegrityFunctions(unittest.TestCase):
    """整全性判定の関数を、正常系と壊した系の両方で検証する。"""

    @classmethod
    def setUpClass(cls):
        cls.ns = load_checker_functions()
        cls.ds = ROOT / "docs" / "design-system"

    def test_real_manifest_has_no_dead_links(self):
        links, dead = self.ns["manifest_dead_links"](str(self.ds))
        self.assertGreaterEqual(len(links), 70)
        self.assertEqual(dead, [])

    def test_dead_link_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, "MANIFEST.md"), "w", encoding="utf-8") as fh:
                fh.write("- [ボタン](components/button/index.md)\n")
            links, dead = self.ns["manifest_dead_links"](tmp)
            self.assertEqual(dead, ["components/button/index.md"],
                             "死にリンクを検知できない")

    def test_real_components_are_49(self):
        self.assertEqual(len(self.ns["component_dirs"](str(self.ds))), 49)

    def test_reference_guide_matches_dirs(self):
        rg = self.ns["reference_guide_slugs"](str(self.ds))
        actual = set(self.ns["component_dirs"](str(self.ds)))
        self.assertEqual(rg, actual)

    def test_missing_component_is_detected(self):
        # 妨害: 49種のうち1つが消えた想定。component_dirs は実在だけを返すので
        # 「49でない」ことが B1 で検知される
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "components", "button"))
            self.assertEqual(self.ns["component_dirs"](tmp), ["button"])
            self.assertNotEqual(len(self.ns["component_dirs"](tmp)), 49)


if __name__ == "__main__":
    unittest.main()
