# KLK-063 カタログ画像のアップロードUI（A-3・ドロップゾーンの実働化）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的+純関数: tests/site/check_klk063.py（U1-U14）
# - 追加: catalog/ が Git 除外されたままであること（REQ-011 / NFR-004 の退行検出）。
#   アップロード先が catalog/.pending/ に増えたため、除外が外れると社外秘が公開対象に入る。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk063.py"


class TestKLK063Static(unittest.TestCase):
    """check_klk063.py（アップロードUIの静的+純関数チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk063.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため check-ignore をskip")
class TestKLK063CatalogStaysIgnored(unittest.TestCase):
    """アップロード先 catalog/.pending/ を含む catalog/ が Git 除外のままであること。

    本チケットでブラウザから catalog/.pending/ へ書き込めるようになったため、
    除外が外れると社外秘（実績画像・第三者著作物）が公開対象に入る（REQ-011 / NFR-004）。
    """

    TARGETS = [
        "catalog/catalog.json",
        "catalog/img/cat-0001.png",
        "catalog/.pending/pnd-0123456789abcdef0123456789abcdef.png",
    ]

    def test_catalog_paths_are_ignored(self):
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
                self.assertEqual(
                    proc.returncode, 0,
                    f"catalog 配下が Git 除外されていない（社外秘の流出リスク）: {target}",
                )


if __name__ == "__main__":
    unittest.main()
