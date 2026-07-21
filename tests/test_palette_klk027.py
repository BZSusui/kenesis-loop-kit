# KLK-027 セクション見出し・リード文の事前指定（sectionOptions.{KEY}.heading/.lead）のテストを
# unittest スイートへ束ねるラッパー（tester所有）。
# - S群（静的）: tests/site/check_klk027.py（S1-S9・Python標準のみ・対象＝draft-gen/index.html・bridge.py /
#   DRAFT_RULES.md・SKILL.md / fixtures/klk027/*）
# - K群（動的スモーク）: tests/site/smoke_klk027.node.js（T1-T5: sectionTexts 反映の実挙動・node 無ければ skip）
# - D1（Quality Gate 全緑）はスイート全体の実行そのものが担保する。
#
# M群（/draft-generate 実生成＋ブラウザ実機）は自動化不能のため tester が手動確認しチケットのログへ記録する。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk027.py"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk027.node.js"


class TestKLK027Static(unittest.TestCase):
    """check_klk027.py（設計書 §9 S群 S1-S9）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk027.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK027Smoke(unittest.TestCase):
    """smoke_klk027.node.js（T1-T5: 後方互換・選択限定・整形・CTA併用・空省略/入力非破壊）が全PASSすること。"""

    def test_dynamic_smoke_pass(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "smoke_klk027.node.js failed:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
