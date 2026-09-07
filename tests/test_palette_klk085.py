# KLK-085 画面から要件ID・チケットIDを見えなくする（tester所有のラッパー）。
# - 静的: tests/site/check_klk085.py（A〜L）
# - 追加: **追跡可能性を捨てていないこと**を独立に確かめる。
#   ID を「消す」のではなく「HTML コメントへ移す」のが方針なので、
#   見えなくなったことだけを検査すると、うっかり削除しても気づけない。
import io
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk085.py"
UI = ROOT / "draft-gen" / "index.html"
CAT = ROOT / "draft-gen" / "catalog.html"
ID_RE = r"(?:REQ|KLK|SCR|NFR|OQ)-\d+"


def visible_text(html):
    s = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    s = re.sub(r"<script\b.*?</script>", "", s, flags=re.S)
    s = re.sub(r"<style\b.*?</style>", "", s, flags=re.S)
    return re.sub(r"<[^>]+>", "\x00", s)


class TestKLK085Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(proc.returncode, 0,
                         "check_klk085.py failed:\n" + proc.stdout + proc.stderr)


class TestKLK085Invisible(unittest.TestCase):
    """利用者に見える文字として ID が出ていないこと。"""

    def test_no_ids_in_visible_text(self):
        for p in (UI, CAT, ROOT / "palette" / "index.html",
                  ROOT / "使い方マニュアル.html"):
            with self.subTest(p.name):
                found = re.findall(ID_RE, visible_text(p.read_text(encoding="utf-8")))
                self.assertFalse(found, "%s に %s が見えている" % (p.name, sorted(set(found))))


class TestKLK085TraceabilityKept(unittest.TestCase):
    """★消したのではなく移したこと。ID は grep で従来どおり追えること。

    「見えなくする」だけを検査すると、**うっかり削除しても PASS してしまう**。
    どの要件の実装かを追う手掛かりを失うのは、見えていることより高くつく。
    """

    def test_ids_survive_as_comments(self):
        comments = " ".join(re.findall(r"<!--(.*?)-->", UI.read_text(encoding="utf-8"), re.S))
        for i in ("SCR-001", "REQ-010", "REQ-001", "REQ-002", "REQ-005", "KLK-022",
                  "REQ-101", "REQ-003", "REQ-004", "REQ-006", "REQ-008",
                  "REQ-011", "REQ-102", "REQ-201"):
            with self.subTest(i):
                self.assertIn(i, comments, "%s がコメントからも消えている" % i)

    def test_grep_still_finds_them(self):
        proc = subprocess.run(
            ["grep", "-c", "-E", ID_RE, str(UI)],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(proc.returncode, 0, "grep が ID を1件も見つけられない")
        self.assertGreaterEqual(int(proc.stdout.strip()), 20)


class TestKLK085GeneratedOutput(unittest.TestCase):
    """生成物（見本・配布物）にも同じ規律が当たっていること（§4.1.2）。

    生成物は提案資料として社外の方の目にも触れる。実際に compare.html の
    ボタン名へ「（SCR-001）」が混入していた（見本01・02＋mockups 3件）。
    """

    def test_samples_have_no_visible_ids(self):
        for p in sorted((ROOT / "samples").glob("*/*.html")):
            with self.subTest(p.parent.name + "/" + p.name):
                found = re.findall(ID_RE, visible_text(p.read_text(encoding="utf-8")))
                self.assertFalse(found, "%s に %s が見えている" % (p, sorted(set(found))))

    def test_rule_exists_and_names_the_real_mistake(self):
        rules = (ROOT / ".claude" / "skills" / "draft-generate" / "templates"
                 / "DRAFT_RULES.md").read_text(encoding="utf-8")
        seg = rules[rules.find("#### 4.1.2"):rules.find("### 4.2")]
        self.assertTrue(seg, "§4.1.2 が無い")
        self.assertIn("設定を変えて再生成（SCR-001）", seg,
                      "実際に混入した文字列が実例として残っていない（再発の目印）")
        self.assertIn("番地ラベル", seg, "番地ラベルが対象外だと書かれていない")

    def test_verify_mockup_covers_compare_html(self):
        """compare.html は番地を持たず check_file の対象外。
        実際に混入したのはそのファイルなので、ここを見落とすと検査の意味がない。"""
        tool = (ROOT / "tools" / "verify-mockup.py").read_text(encoding="utf-8")
        self.assertIn("def check_dev_ids", tool)
        self.assertRegex(tool, r'compare\.html[\s\S]{0,400}check_dev_ids|check_dev_ids[\s\S]{0,400}compare\.html')


if __name__ == "__main__":
    unittest.main()
