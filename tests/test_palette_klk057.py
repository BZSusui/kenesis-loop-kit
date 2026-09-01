# KLK-057 HERO 埋め込み検索窓（§12.1.3(7)・方式B・SEARCH連動・未選択は非生成・一本化）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk057.py（HS1-HS8・DRAFT_RULES§12.1.3(7)／SKILL／check_klk034 HERO_SEARCH_TYPES／golden klk057・klk057b）
# - D群: git check-ignore で golden fixtures が Git 追跡対象であること（git不在時skip）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk057.py"


class TestKLK057Static(unittest.TestCase):
    """check_klk057.py（HERO 埋め込み検索窓の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk057.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため ls-files をskip")
class TestKLK057FixturesTracked(unittest.TestCase):
    """KLK-057 の golden（klk057・klk057b）が Git 追跡対象であることを確認。"""

    TARGETS = [
        "tests/fixtures/klk057/index-a.html",
        "tests/fixtures/klk057/index-b.html",
        "tests/fixtures/klk057/index-c.html",
        "tests/fixtures/klk057/compare.html",
        "tests/fixtures/klk057/instruction.json",
        "tests/fixtures/klk057b/index-a.html",
        "tests/fixtures/klk057b/index-b.html",
        "tests/fixtures/klk057b/index-c.html",
        "tests/fixtures/klk057b/compare.html",
        "tests/fixtures/klk057b/instruction.json",
    ]

    def test_fixtures_not_ignored(self):
        pre = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        if pre.returncode != 0:
            self.skipTest("git リポジトリ外のためskip")
        for target in self.TARGETS:
            with self.subTest(path=target):
                proc = subprocess.run(
                    ["git", "check-ignore", target],
                    capture_output=True, text=True, cwd=str(ROOT), timeout=60,
                )
                self.assertEqual(proc.returncode, 1, f"golden が除外されている: {target}")
                self.assertTrue((ROOT / target).exists(), f"golden が存在しない: {target}")


if __name__ == "__main__":
    unittest.main()
