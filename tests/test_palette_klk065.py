# KLK-065 提案フェーズの承認待ち停止の修正（非対話実行での質問禁止）の
# テストを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的+純関数: tests/site/check_klk065.py（Q1-Q9）
# - 追加: ヘッドレス実行に使う3つのコマンド構築関数が、いずれも危険な全許可フラグを
#   持たないこと（最小権限の横断的な退行検出）。
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk065.py"


class TestKLK065Static(unittest.TestCase):
    """check_klk065.py（非対話規律の静的+純関数チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk065.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK065MinimalPrivilege(unittest.TestCase):
    """ヘッドレス実行の全コマンドが最小権限を保つこと（横断的な退行検出）。

    KLK-065 で allowedTools を初めて既定で付けたため、以後「困ったら全許可」に
    流れる誘惑が生まれる。3つの構築関数すべてを常時検査して歯止めにする。
    """

    DANGEROUS = [
        "--dangerously-skip-permissions",
        "bypassPermissions",
        "--allow-all",
        "--yolo",
    ]

    def _cmds(self):
        sys.path.insert(0, str(ROOT / "draft-gen"))
        import bridge  # noqa: E402
        return {
            "generate": bridge.build_claude_command("mockups/.pending/x.json", allow_open=True),
            "regenerate": bridge.build_regenerate_command("mockups/.pending/x.json", allow_open=True),
            "catalog-import": bridge.build_catalog_import_command("catalog/.pending/x.json", allow_open=True),
        }

    def test_no_dangerous_flags(self):
        for name, cmd in self._cmds().items():
            with self.subTest(command=name):
                joined = " ".join(str(x) for x in cmd)
                for flag in self.DANGEROUS:
                    self.assertNotIn(flag, joined, f"{name} に危険な全許可フラグ {flag} が含まれる")

    def test_permission_mode_is_accept_edits(self):
        for name, cmd in self._cmds().items():
            with self.subTest(command=name):
                self.assertIn("--permission-mode", cmd, f"{name} に --permission-mode が無い")
                self.assertEqual(
                    cmd[cmd.index("--permission-mode") + 1], "acceptEdits",
                    f"{name} の permission-mode が acceptEdits ではない",
                )


if __name__ == "__main__":
    unittest.main()
