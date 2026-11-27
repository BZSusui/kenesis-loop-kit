# KLK-077 カタログ同梱版パッケージ（A）を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk077.py（R1-R8 = 仕掛け / E1-E9 = 実際に組み立てて確認）
# - 追加: **マーカーが欠けたら組み立てが止まること**を検査する。
#   README が「カタログは空です」と案内したまま 345MB の社外秘を配るのが最悪なので、
#   差し替えに失敗したら黙って続けず、中止して配布物を残さないこと（fail-closed）。
#   ★ここだけは fail-open にしない。KLK-064 の「成功したように見えて何もしていない」の再来を防ぐ。
# - R7（個人名の照合）は、照合語ファイルが無くて素通りしたとき skipped として数える（KLK-143）。
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk077.py"
REWRITER = ROOT / "tools" / "readme_for_catalog.py"
SCRIPT = ROOT / "tools" / "make-package.sh"
CATALOG_JSON = ROOT / "catalog" / "catalog.json"
sys.path.insert(0, str(ROOT / "tests" / "site"))
import _private_terms as pt  # noqa: E402


class TestKLK077Static(unittest.TestCase):
    """check_klk077.py（仕掛け＋実際の組み立て）が全PASSすること。"""

    @classmethod
    def setUpClass(cls):
        # checker（実際の組み立て込み）はクラスで1回だけ実行する
        cls.proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=900,
        )
        cls.unverified = [l for l in cls.proc.stdout.splitlines() if l.startswith(pt.UNVERIFIED_MARKER)]

    def test_static_checks_pass(self):
        proc = self.proc
        self.assertEqual(
            proc.returncode, 0,
            "check_klk077.py failed:\n" + proc.stdout + proc.stderr,
        )

    def test_r7_personal_name_checked(self):
        """★R7 の個人名の照合が実際に行われたこと。照合語ファイルが無ければ skipped として見せる（KLK-143）。"""
        has_terms = pt.load_terms() is not None
        if self.unverified:
            self.assertFalse(has_terms, "照合語ファイルがあるのに素通りした: %s" % self.unverified)
            self.skipTest("照合語ファイル .private/personal-terms.txt が無いため R7（個人名の照合）をskip")
        self.assertTrue(has_terms, "照合語ファイルが無いのに素通りの印が出ていない（素通りが見えない）")
        lines = self.proc.stdout.splitlines()
        idx = [i for i, l in enumerate(lines) if l.startswith("[PASS] R7 ")]
        self.assertEqual(len(idx), 1, "R7 が PASS していない:\n" + self.proc.stdout[-2000:])
        self.assertLess(idx[0] + 1, len(lines))
        self.assertEqual(lines[idx[0] + 1].strip(), "個人名=なし")


class TestKLK077FailClosed(unittest.TestCase):
    """差し替えに失敗したら止まること（黙って空前提の README を配らない）。"""

    def _run_rewriter(self, readme_text):
        tmp = Path(tempfile.mkdtemp(prefix="klk077_fc_"))
        try:
            rm = tmp / "README.md"
            rm.write_text(readme_text, encoding="utf-8")
            proc = subprocess.run(
                ["python3", str(REWRITER), str(rm), str(CATALOG_JSON)],
                capture_output=True, text=True, cwd=str(ROOT), timeout=60,
            )
            return proc, rm.read_text(encoding="utf-8")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_marker_is_an_error(self):
        body = (ROOT / "README.md").read_text(encoding="utf-8")
        broken = body.replace("<!-- KLK-077:CATALOG-INTRO:END -->", "")
        proc, after = self._run_rewriter(broken)
        self.assertEqual(
            proc.returncode, 1,
            "マーカーが欠けているのに成功してしまった（空前提の README を配る事故になる）:\n"
            + proc.stdout + proc.stderr,
        )
        self.assertEqual(after, broken, "失敗したのに README を書き換えている")

    def test_intact_readme_is_rewritten(self):
        body = (ROOT / "README.md").read_text(encoding="utf-8")
        proc, after = self._run_rewriter(body)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("実績カタログが入った状態", after)
        self.assertNotIn("カタログが空だと参考が選べない", after)

    def test_build_script_aborts_on_rewrite_failure(self):
        """組み立てスクリプトが、書き換え失敗時に配布物を残さず中止すること。"""
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("rm -rf \"$DEST\"", text, "失敗時に中途半端な配布物を消していない")
        self.assertIn("exit 1", text, "失敗時に中止していない")


if __name__ == "__main__":
    unittest.main()
