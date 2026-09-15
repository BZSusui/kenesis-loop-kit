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


def checker_ns():
    """checker の関数だけを読み込む（実行すると全チェックが走るため）。

    ★照合語の作り方を**ここで書き直さない**。書き直すと2つの規則ができ、
      片方だけ直したときに検査が静かに食い違う（実際 KLK-131 でそうなりかけた）。
    """
    src = STATIC_CHECKER.read_text(encoding="utf-8")
    cut = src.index("def tracked_files()")
    ns = {"__file__": str(STATIC_CHECKER)}
    exec(compile(src[:cut], str(STATIC_CHECKER), "exec"), ns)
    return ns


def catalog_terms():
    return checker_ns()["catalog_terms"]()


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


class TestKLK108GenericTitles(unittest.TestCase):
    """★「区分の言葉だけでできた名前」を照合から外す（KLK-131）。

    誤検知を放置すると「また鳴っている」と流されるようになり、本物を見逃す。
    ただし**守りは緩めない**。少しでも固有の語が残る名前は従来どおり照合する。
    """

    @classmethod
    def setUpClass(cls):
        cls.ns = checker_ns()
        if not CATALOG.is_file():
            raise unittest.SkipTest("実績カタログが無い環境（catalog/ は Git 管理外）")
        cls.entries = json.loads(CATALOG.read_text(encoding="utf-8")).get("entries", [])
        cls.vocab = cls.ns["generic_vocabulary"](cls.entries)

    def test_vocabulary_comes_from_the_data(self):
        """除外語を直書きしていないこと（この検査自身が漏洩源にならない）。"""
        src = STATIC_CHECKER.read_text(encoding="utf-8")
        self.assertIn("generic_vocabulary(entries)", src)
        # 実データの業種語が語彙に入っている＝データから作られている
        self.assertTrue(any(len(v) >= 2 for v in self.vocab))

    def test_category_only_title_is_skipped(self):
        self.assertTrue(self.ns["is_generic_title"]("クリニックサイト", self.vocab))
        self.assertTrue(self.ns["is_generic_title"]("コーポレートサイト", self.vocab))

    def test_distinctive_title_is_still_checked(self):
        """★ここが本丸。固有の語が入る名前は、外してはならない。"""
        # ★ここに**実在の登録名を書いてはならない**。この検査ファイル自身が
        #   追跡対象であり、書けば漏洩源になる（KLK-108 が正したのがそれ）。
        #   実際、最初ここに実データの名前を書いてしまい、検査に捕まった。
        #   固有の語を含むが実在しない名前で確かめる。
        for t in ("ザッケロ・コーポレートサイト",
                  "架空堂 ジュエリー工房",
                  "ぬるま湯クリニックサイト"):
            with self.subTest(title=t):
                self.assertFalse(self.ns["is_generic_title"](t, self.vocab),
                                 "固有の語を含む名前が照合から外れている: %s" % t)

    def test_real_distinctive_titles_remain_in_terms(self):
        """実データでも、外れるのは区分の言葉だけの名前に限られること。"""
        terms = self.ns["catalog_terms"]()
        titles = [e["title"] for e in self.entries
                  if isinstance(e, dict) and isinstance(e.get("title"), str)
                  and len(e["title"].strip()) >= 4]
        dropped = [t for t in titles if t.strip() not in terms]
        self.assertTrue(all(self.ns["is_generic_title"](t, self.vocab) for t in dropped),
                        "区分の言葉だけではない名前が外れている: %s"
                        % [t for t in dropped if not self.ns["is_generic_title"](t, self.vocab)][:3])
        # 外れすぎていないこと（守りが空にならない）
        self.assertLess(len(dropped), max(3, len(titles) // 20),
                        "外れた件数が多すぎる: %d / %d" % (len(dropped), len(titles)))


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
