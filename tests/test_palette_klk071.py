# KLK-071 見本となる生成ページの同梱を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk071.py（S1-S12）
# - 追加: 見本と mockups の**役割の線引き**が保たれていること。
#   samples/ は配布物（追跡・ダミー名・機密なし）、mockups/ は利用者の作業場（除外・案件名を含む）。
#   ここが崩れると「見本が配布物に入らない」か「実在の案件名が配られる」のどちらかが起きる。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk071.py"
SAMPLES = ROOT / "samples"


class TestKLK071Static(unittest.TestCase):
    """check_klk071.py（見本の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk071.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("git"), "git が見つからないため check-ignore をskip")
class TestKLK071SamplesVsMockups(unittest.TestCase):
    """samples/ は追跡され、mockups/ は除外されたままであること（役割の線引き）。"""

    def _ignored(self, rel):
        proc = subprocess.run(
            ["git", "check-ignore", rel],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60,
        )
        return proc.returncode == 0

    def test_samples_tracked(self):
        self.assertTrue(SAMPLES.is_dir(), "samples/ が無い")
        self.assertFalse(
            self._ignored("samples/README.md"),
            "samples/ が Git 除外されている（配布物に入らない）",
        )

    def test_mockups_still_ignored(self):
        self.assertTrue(
            self._ignored("mockups/2026-01-01_x/compare.html"),
            "mockups/ の除外が外れている（案件名を含む生成物が追跡対象になる）",
        )


if __name__ == "__main__":
    unittest.main()
