# KLK-127 業種の自由入力が一覧選択を打ち消して参考素材が絞れない（tester所有）。
#
# ★経緯: 理恵さんが「クリニック・病院・介護リハビリ」を選び、自由入力に
#   「小児科・アレルギー科のクリニック」と書き足したところ、参考素材が
#   3件に絞れるはずが167件すべて（食品・美容・教育…）並んだ。
#   チップも「クリニックに近い実績を表示中」と言いながら全件が出ており、画面の中で矛盾していた。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk127.py … 絞り込みキーの優先順・生成指示書は不変・チップの書き手
#   2. ここ … 関数本体を読む純関数を突く＋★実ブラウザで描かれたサムネイルの業種と枚数を見る
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk127.py"
E2E = ROOT / "tests" / "site" / "e2e_klk127.node.js"
INDEX = ROOT / "draft-gen" / "index.html"

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
    """checker を『関数だけ』読み込む（実行すると全チェックが走るため・klk125 と同じ作法）。"""
    src = STATIC.read_text(encoding="utf-8")
    cut = src.index("CUR = body_of(")
    ns = {"__file__": str(STATIC)}
    exec(compile(src[:cut], str(STATIC), "exec"), ns)
    return ns


class TestKLK127Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk127.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("K1 ★絞り込みのキーは一覧選択を先に見る", p.stdout)
        self.assertIn("G1 ★生成指示書の業種は従来どおり自由入力が優先", p.stdout)


class TestFunctionReader(unittest.TestCase):
    """関数本体を切り出す純関数。ここが緩いと「逆になっていない」判定が空になる。"""

    @classmethod
    def setUpClass(cls):
        cls.c = load_checker_functions()
        cls.src = INDEX.read_text(encoding="utf-8")

    def test_reads_the_real_body(self):
        body = self.c["body_of"](self.src, "currentIndustry")
        self.assertIsNotNone(body)
        self.assertIn("industrySelect", body)
        self.assertIn("industryCustom", body)
        # 隣の関数まで飲み込んでいないこと（波括弧の対応が取れている）
        self.assertNotIn("isCustomIndustry", body)

    def test_detects_the_reversed_order(self):
        # 妨害: 不具合当時の順（自由入力が先）に戻したら「一覧が先」と言わないこと
        broken = self.src.replace(
            "  var preset = document.getElementById('industrySelect').value;\n"
            "  return preset || document.getElementById('industryCustom').value.trim() || '';",
            "  var custom = document.getElementById('industryCustom').value.trim();\n"
            "  return custom || document.getElementById('industrySelect').value || '';", 1)
        self.assertNotEqual(broken, self.src, "妨害注入が効いていない")
        body = self.c["body_of"](broken, "currentIndustry")
        self.assertGreater(body.find("industrySelect"), body.find("industryCustom"),
                           "逆順を検知できない")

    def test_returns_none_when_absent(self):
        self.assertIsNone(self.c["body_of"]("<html>なにもない</html>", "currentIndustry"))


class TestKLK127E2E(unittest.TestCase):
    """★実効果: 実ブリッジ＋実ブラウザで、描かれたサムネイルの業種と枚数を見る。"""

    def test_reference_thumbs_narrow_to_the_selected_industry(self):
        if not shutil.which("node"):
            self.skipTest("node が無い環境")
        ch = chrome_path()
        if not ch:
            self.skipTest("ヘッドレス Chrome が無い環境")
        env = dict(os.environ, KLK_E2E_CHROME=ch)
        p = subprocess.run(["node", str(E2E)], capture_output=True, text=True,
                           timeout=300, env=env, cwd=str(ROOT))
        if p.returncode == 3:
            self.skipTest("e2e が環境理由で SKIP: %s" % (p.stdout + p.stderr)[-300:])
        self.assertEqual(p.returncode, 0, "e2e_klk127.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("E1 ★一覧で選び、自由入力にも書いたとき、その業種だけに絞られる", p.stdout)
        self.assertIn("E6 ★生成指示書の industry は自由入力が優先される", p.stdout)


if __name__ == "__main__":
    unittest.main()
