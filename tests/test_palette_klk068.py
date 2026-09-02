# KLK-068 カタログエントリの削除機能を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的+純関数: tests/site/check_klk068.py（D1-D13）
# - 追加: catalog/ 配下（.trash を含む）が Git 除外のままであること。
#   削除で退避した実績画像が公開対象に入ると社外秘の流出になる（REQ-011 / NFR-004）。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk068.py"


class TestKLK068Static(unittest.TestCase):
    """check_klk068.py（削除機能の静的+純関数チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk068.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため check-ignore をskip")
class TestKLK068TrashStaysIgnored(unittest.TestCase):
    """退避先 catalog/.trash/ が Git 除外のままであること。

    削除した実績画像は .trash へ移る。ここが追跡対象になると、
    「消したはずの社外秘」がリポジトリに残る（REQ-011 / NFR-004）。
    """

    TARGETS = [
        "catalog/.trash/cat-0001.png",
        "catalog/.trash/anything.jpg",
    ]

    def test_trash_is_ignored(self):
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
                    f"退避先が Git 除外されていない（社外秘の流出リスク）: {target}",
                )


if __name__ == "__main__":
    unittest.main()
