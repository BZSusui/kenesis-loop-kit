# KLK-130 マニュアルの更新と mac 初回起動の警告対応（tester所有）。
#
# ★経緯: 理恵さんから「mac の初回に開けないという声が多い」と依頼。
#   調べると README.md と はじめにお読みください.txt には既に書いてあったが、
#   利用者が読む 使い方マニュアル.html には無く、しかも既存の記述は
#   「右クリック →『開く』」だけで新しい macOS では開けないことがあった。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk130.py … 両経路の記載・理由・対処表・同梱文書・改修への追従
#   2. ここ … 節を切り出す純関数を突く＋★実ブラウザで表示崩れとリンク切れを見る
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk130.py"
MANUAL = ROOT / "使い方マニュアル.html"

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


def load_checker_functions():
    src = STATIC.read_text(encoding="utf-8")
    cut = src.index('M = read("')
    ns = {"__file__": str(STATIC)}
    exec(compile(src[:cut], str(STATIC), "exec"), ns)
    start = src.index("def section_of(")
    end = src.index("MAC = section_of(")
    exec(compile(src[start:end], str(STATIC), "exec"), ns)
    return ns


class TestKLK130Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk130.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("M4 ★経路2: システム設定", p.stdout)
        self.assertIn("U4 ★型を図解アイコンの一覧から選ぶ", p.stdout)

    def test_existing_manual_checker_still_passes(self):
        """★KLK-098 の約束（外部依存ゼロ・実装との一致など）を壊していないこと。"""
        p = subprocess.run(["python3", str(ROOT / "tests" / "site" / "check_klk098.py")],
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk098.py 失敗:\n%s" % p.stdout[-3000:])


class TestSectionReader(unittest.TestCase):
    """節を切り出す純関数。ここが緩いと「書いてある」判定が空になる。"""

    @classmethod
    def setUpClass(cls):
        cls.c = load_checker_functions()
        cls.src = MANUAL.read_text(encoding="utf-8")

    def test_reads_only_that_section(self):
        got = self.c["section_of"](self.src, "Mac で初回")
        self.assertTrue(got)
        self.assertIn("このまま開く", got)
        # 隣の節まで飲み込んでいないこと
        self.assertNotIn("操作画面の全体像", got)

    def test_returns_empty_when_absent(self):
        self.assertEqual(self.c["section_of"]("<html>なにもない</html>", "Mac で初回"), "")

    def test_detects_a_removed_route(self):
        # 妨害: システム設定の経路を消したら「書いてある」と言わないこと
        broken = self.src.replace("このまま開く", "○○○", 1)
        self.assertNotEqual(broken, self.src, "妨害注入が効いていない")
        self.assertNotIn("このまま開く", self.c["section_of"](broken, "Mac で初回"))


class TestKLK130Render(unittest.TestCase):
    """★実効果: 実ブラウザで開き、リンク切れと横はみ出しが無いことを見る。"""

    def test_manual_renders_without_broken_links_or_overflow(self):
        if not shutil.which("node"):
            self.skipTest("node が無い環境")
        ch = chrome_path()
        if not ch:
            self.skipTest("ヘッドレス Chrome が無い環境")
        script = ROOT / "tests" / "site" / "e2e_klk130.node.js"
        env = dict(os.environ, KLK_E2E_CHROME=ch)
        p = subprocess.run(["node", str(script)], capture_output=True, text=True,
                           timeout=300, env=env, cwd=str(ROOT))
        if p.returncode == 3:
            self.skipTest("e2e が環境理由で SKIP: %s" % (p.stdout + p.stderr)[-300:])
        self.assertEqual(p.returncode, 0, "e2e_klk130.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn(", 0 failed", p.stdout)


if __name__ == "__main__":
    unittest.main()
