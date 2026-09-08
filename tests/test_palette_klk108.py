# KLK-108 社外秘が配布物へ漏れないこと（tester所有・総点検で発見）。
#
# ★見つかったこと
#   docs/designs/KLK-017.md に実在の顧客名が3件あり、docs/ は make-package.sh が
#   丸ごと同梱するため、**カタログ非同梱のパッケージBにも漏れていた**。
#   さらに漏洩を見張る check_klk017.py が照合語を直書きしており、
#   **その検査ファイル自身が漏洩源**だった。
#
#   ★教訓: 秘密を見張る仕組みが自分で秘密を持つと、守るほど漏れる。
#           照合語は実データ（Git 除外）から実行時に読む。
import io
import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk108.py"
CATALOG = ROOT / "catalog" / "catalog.json"


def catalog_terms():
    if not CATALOG.is_file():
        return None
    try:
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
    except ValueError:
        return None
    out = set()
    for e in data.get("entries", []):
        if not isinstance(e, dict):
            continue
        for k in ("title", "client", "name", "note", "memo"):
            v = e.get(k)
            if isinstance(v, str) and len(v.strip()) >= 4:
                out.add(v.strip())
    return out


class TestKLK108Static(unittest.TestCase):
    def test_static_checks_pass(self):
        p = subprocess.run(["python3", str(STATIC_CHECKER)],
                           capture_output=True, text=True, cwd=str(ROOT), timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk108.py failed:\n" + p.stdout + p.stderr)


class TestKLK108NoSecretsInTrackedFiles(unittest.TestCase):
    """Git 追跡ファイルに社外秘が無いこと。"""

    def test_no_catalog_titles_in_tracked_files(self):
        terms = catalog_terms()
        if terms is None:
            self.skipTest("catalog.json が無い環境")
        files = [f for f in subprocess.run(
            ["git", "ls-files", "-z"], capture_output=True, text=True,
            cwd=str(ROOT)).stdout.split("\0") if f]
        self.assertGreater(len(files), 50, "追跡ファイルを列挙できていない")
        leaks = []
        for f in files:
            p = ROOT / f
            if not p.is_file() or f.startswith("catalog/"):
                continue
            try:
                h = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for t in terms:
                if t in h:
                    leaks.append("%s ← %s" % (f, t[:30]))
        self.assertFalse(leaks, "社外秘が追跡ファイルに出ている:\n" + "\n".join(leaks[:6]))


class TestKLK108CheckerHoldsNoSecrets(unittest.TestCase):
    """★漏洩を見張る検査が、自分で秘密を持たないこと。"""

    def test_no_hardcoded_secret_list(self):
        s = (ROOT / "tests" / "site" / "check_klk017.py").read_text(encoding="utf-8")
        self.assertNotIn("SECRET_TITLES = [", s,
                         "照合語を直書きしている（この検査ファイル自身が漏洩源になる）")

    def test_reads_from_real_data_at_runtime(self):
        s = (ROOT / "tests" / "site" / "check_klk017.py").read_text(encoding="utf-8")
        self.assertIn("catalog.json", s)
        self.assertIn("def _catalog_titles", s)

    def test_degrades_gracefully_without_catalog(self):
        """カタログが無い環境（clone 直後・配布先）で落ちないこと。"""
        s = (ROOT / "tests" / "site" / "check_klk017.py").read_text(encoding="utf-8")
        self.assertIn("照合不能", s)

    def test_checks_all_titles_not_a_fixed_few(self):
        """直書き8語より広く、いま登録されている全件を見ること。

        カタログを増やしても検査を直さなくてよい形になっているか。
        """
        p = subprocess.run(["python3", str(ROOT / "tests" / "site" / "check_klk017.py")],
                           capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        terms = catalog_terms()
        if terms is None:
            self.skipTest("catalog.json が無い環境")
        self.assertIn("照合 ", p.stdout, "照合件数を報告していない")


class TestKLK108DesignDocRecordsTheRule(unittest.TestCase):
    """また書かれないよう、設計書に理由が残っていること。"""

    def test_rule_is_written_down(self):
        s = (ROOT / "docs" / "designs" / "KLK-017.md").read_text(encoding="utf-8")
        self.assertIn("実在の案件名は書かない", s)
        self.assertIn("パッケージ", s, "なぜ駄目なのか（配布物に入る）が書かれていない")


if __name__ == "__main__":
    unittest.main()
