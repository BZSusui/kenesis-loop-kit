# KLK-135 配布物の設計書がこのシステムのものだけであること（tester所有）。
#
# ★経緯: KLK-132 のフルスイートで check_klk115 P3 が落ちた。make-package.sh が docs/ を
#   ディレクトリごと写すため、別案件（デザインシステム）の設計書 docs/designs/DADS-*.md が
#   配布物へ混ざっていた。チケット番号と docs/designs/ は両案件で共有しているので、
#   相手が設計書を足すたびに再発する。**組み立て時に allowlist で絞る**方式で直した。
#
# ★このテストが守っているもの:
#   - checker 本体が全件PASSし、実ビルド部（B3・B4）が省略されずに走ること
#   - 絞り込みが「消す」ではなく「配布物に出さない」であること（リポジトリ本体は無傷）
#   - KLK-115 の保証（配布物に DADS 語ゼロ）が回復していること
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk135.py"
KLK115_CHECKER = ROOT / "tests" / "site" / "check_klk115.py"
PKG_SH = ROOT / "tools" / "make-package.sh"
DESIGNS = ROOT / "docs" / "designs"


class TestKLK135StaticChecker(unittest.TestCase):
    def test_static_checker_passes(self):
        """checker本体（パッケージ実ビルド込み）が全件PASSする。"""
        p = subprocess.run(["python3", str(STATIC_CHECKER)],
                           capture_output=True, text=True, timeout=900)
        self.assertEqual(p.returncode, 0,
                         "check_klk135.py 失敗:\n%s" % p.stdout[-2000:])
        self.assertIn(", 0 failed", p.stdout)
        # 実ビルド部が省略されずに走ったことまで確認する（--fast だと素通りするため）
        self.assertIn("B3 ★配布物の docs/designs に KLK-* 以外が無い", p.stdout)
        self.assertIn("B4 ★妨害注入: 置いた別案件の設計書が配布物に出ない", p.stdout)


class TestAllowlistShape(unittest.TestCase):
    def test_package_script_uses_allowlist(self):
        src = PKG_SH.read_text(encoding="utf-8")
        self.assertIn("$DEST/docs/designs", src)
        # 残すものを列挙する形（除くものを列挙する形ではない）。
        # 「DADS を除く」だと、次の別案件が来たときにまた漏れる
        self.assertIn("KLK-*.md|README.md|_TEMPLATE.md", src)
        self.assertNotIn("rm -f \"$DEST\"/docs/designs/DADS-", src)

    def test_repository_copy_is_untouched(self):
        """リポジトリ本体からは消さない（外すのは配布物だけ）。"""
        self.assertTrue(DESIGNS.is_dir())
        # 別案件の設計書が在るなら、それはリポジトリに残っていてよい
        others = [p.name for p in DESIGNS.iterdir()
                  if p.suffix == ".md" and not p.name.startswith("KLK-")
                  and p.name not in ("README.md", "_TEMPLATE.md")]
        for name in others:
            self.assertTrue((DESIGNS / name).is_file())

    def test_klk115_guarantee_restored(self):
        """KLK-115 の保証（配布物に DADS 語ゼロ）が回復していること。"""
        p = subprocess.run(["python3", str(KLK115_CHECKER)],
                           capture_output=True, text=True, timeout=900)
        self.assertEqual(p.returncode, 0,
                         "check_klk115.py 失敗:\n%s" % p.stdout[-2000:])
        self.assertIn("[PASS] P3", p.stdout)


if __name__ == "__main__":
    unittest.main()
