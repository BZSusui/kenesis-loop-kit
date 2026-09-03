# KLK-077 カタログ同梱版パッケージ（A）を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk077.py（R1-R8 = 仕掛け / E1-E9 = 実際に組み立てて確認）
# - 追加: **マーカーが欠けたら組み立てが止まること**を検査する。
#   README が「カタログは空です」と案内したまま 345MB の社外秘を配るのが最悪なので、
#   差し替えに失敗したら黙って続けず、中止して配布物を残さないこと（fail-closed）。
#   ★ここだけは fail-open にしない。KLK-064 の「成功したように見えて何もしていない」の再来を防ぐ。
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk077.py"
REWRITER = ROOT / "tools" / "readme_for_catalog.py"
SCRIPT = ROOT / "tools" / "make-package.sh"
CATALOG_JSON = ROOT / "catalog" / "catalog.json"


class TestKLK077Static(unittest.TestCase):
    """check_klk077.py（仕掛け＋実際の組み立て）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=900,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk077.py failed:\n" + proc.stdout + proc.stderr,
        )


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
