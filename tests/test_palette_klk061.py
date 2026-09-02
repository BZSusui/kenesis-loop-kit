# KLK-061 UI文言を実態へ揃え、SPEC を現状に追従させる（A-1 / A-4 / SCR-003）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk061.py（H1-H9・未対応の明示／旧文言の不在／SPEC の実装状況記載）
# - 追加: 文言変更が JS を壊していないこと（生成指示書へ sampleUrls を載せる実装の維持）を
#         checker 側 H3 で担保しているため、ここではラッパーの成立のみを見る。
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk061.py"


class TestKLK061Static(unittest.TestCase):
    """check_klk061.py（画面・仕様と実装の一致チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk061.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK061SpecHasNoStaleOpenQuestions(unittest.TestCase):
    """SPEC の未決事項が「未決定」のまま放置されていないこと。

    KLK-059 で OQ-002 / OQ-003 を確定させた。残る OQ-001（第2段階＝部内展開の方式）は
    パッケージ化そのものが答えになるため、パッケージ化チケット群で更新する。
    ここでは「確定済みの OQ が未決定へ戻る」退行だけを検出する。
    """

    SPEC = ROOT / "docs" / "SPEC.md"

    def test_oq002_and_oq003_are_settled(self):
        text = self.SPEC.read_text(encoding="utf-8")
        for oq in ("OQ-002", "OQ-003"):
            row = [ln for ln in text.splitlines() if ln.startswith("| %s " % oq)]
            self.assertTrue(row, f"{oq} の行が見つからない")
            self.assertIn("確定", row[0], f"{oq} が確定状態でない: {row[0][:80]}")


if __name__ == "__main__":
    unittest.main()
