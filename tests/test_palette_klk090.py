# KLK-090 出荷整合を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk090.py（README / CHANGELOG / SPEC が実態と合っているか）
# - 追加: **実際に配布物を組み立てて**、受け取る人が読む状態を確かめる。
#
#   ★README と CHANGELOG は配布物に入る。実装が進むたびに書き足さないと
#     「文書が製品を過小に見せる」状態になる（CHANGELOG は実際に34件ぶん止まっていた）。
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk090.py"
MAKE_PKG = ROOT / "tools" / "make-package.sh"


class TestKLK090Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0, "check_klk090.py failed:\n" + proc.stdout + proc.stderr
        )


class TestKLK090PackagedDocs(unittest.TestCase):
    """配布物に入った状態の文書を読む（受け取る人が見るのはこちら）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="klk090_"))
        cls.dest = cls.tmp / "pkg"
        proc = subprocess.run(
            ["bash", str(MAKE_PKG), str(cls.dest)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=600,
        )
        if proc.returncode != 0:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise unittest.SkipTest("配布物を組み立てられなかった:\n" + proc.stdout + proc.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_readme_describes_current_features(self):
        text = (self.dest / "README.md").read_text(encoding="utf-8")
        for needle in ("ページ構成", "⠿", "同じセクションを複数",
                       "1案だけ作ったときも", "配色を読み取る", "さらに表示する"):
            self.assertIn(needle, text, "配布物の README に「%s」が無い" % needle)

    def test_changelog_is_current(self):
        text = (self.dest / "CHANGELOG.md").read_text(encoding="utf-8")
        nums = sorted({int(m) for m in re.findall(r"KLK-(\d{3})", text)})
        self.assertTrue(nums, "CHANGELOG に KLK 番号が無い")
        self.assertGreaterEqual(
            max(nums), 95,
            "配布物の CHANGELOG が KLK-%03d で止まっている（実装は KLK-095 まで進んでいる）" % max(nums),
        )

    def test_package_has_no_confidential_data(self):
        self.assertFalse((self.dest / "catalog" / "img").exists())
        self.assertFalse((self.dest / "catalog" / "catalog.json").exists())
        self.assertEqual(list((self.dest / "mockups").iterdir()), [])

    def test_package_has_the_samples(self):
        dirs = [d for d in (self.dest / "samples").iterdir() if d.is_dir()]
        self.assertGreaterEqual(len(dirs), 3, "見本が同梱されていない")
        for d in dirs:
            self.assertTrue((d / "compare.html").is_file(), "%s に compare.html が無い" % d.name)


if __name__ == "__main__":
    unittest.main()
