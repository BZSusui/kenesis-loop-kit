# KLK-024 MVキャッチコピー・リード文の事前指定（copy.mvCatch/mvLead）のテストを unittest スイートへ
# 束ねるラッパー（tester所有）。
# - S群（静的）: tests/site/check_klk024.py（S1-S9・Python標準のみ・対象＝draft-gen/index.html・bridge.py /
#   DRAFT_RULES.md・SKILL.md / fixtures/klk024/*）
# - K群（動的スモーク）: tests/site/smoke_klk024.node.js（C1-C6: sanitizeCopy/条件付き copy の実挙動・
#   Node.js が無い環境では skip）
# - D1（Quality Gate 全緑）はスイート全体の実行そのものが担保する。
#
# M群（/draft-generate 実生成＋ブラウザ実機）は自動化不能のため tester が手動確認しチケットのログへ記録する。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk024.py"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk024.node.js"


class TestKLK024Static(unittest.TestCase):
    """check_klk024.py（設計書 §9 S群 S1-S9）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk024.py failed:\n" + proc.stdout + proc.stderr,
        )


@unittest.skipUnless(shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK024Smoke(unittest.TestCase):
    """smoke_klk024.node.js（C1-C6: 後方互換・片方指定・整形・上限・純関数・入力非破壊）が全PASSすること。"""

    def test_dynamic_smoke_pass(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "smoke_klk024.node.js failed:\n" + proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
