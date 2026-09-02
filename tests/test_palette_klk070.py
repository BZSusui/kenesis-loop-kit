# KLK-070 Windows 対応を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的+hook実行: tests/site/check_klk070.py（W1-W13）
# - 追加: hook が macOS で従来どおり機能していること（|| フォールバックを足したことによる退行検出）。
#   settings.json のコマンドを実際にシェルで実行し、拒否の JSON が返ることを確かめる。
import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk070.py"


class TestKLK070Static(unittest.TestCase):
    """check_klk070.py（Windows 対応の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk070.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK070HookStillWorks(unittest.TestCase):
    """settings.json の hook コマンドを実際にシェルで実行し、拒否が機能することを確認する。

    KLK-070 で `python3 ... || python ...` の形に変えた。左辺が成功する macOS では
    右辺が走らず、拒否の JSON がそのまま返るはずである。ここが壊れると
    「チケットの不変条件が静かに守られなくなる」ため、実行して確かめる。
    """

    def _pre_tool_use_command(self):
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        for group in settings["hooks"]["PreToolUse"]:
            for hook in group["hooks"]:
                return hook["command"]
        return None

    def test_deny_still_returned(self):
        cmd = self._pre_tool_use_command()
        self.assertIsNotNone(cmd, "PreToolUse hook が見つからない")
        # 不正な遷移（新規チケットをいきなり done で作る）を試みる payload
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(ROOT / "tickets" / "active" / "KLK-999_dummy.md"),
                "content": "---\nid: KLK-999\nstatus: done\nretry_counts:\n"
                           "  tester_to_implementer: 0\n  reviewer_to_implementer: 0\n"
                           "  reviewer_to_investigator: 0\n---\n",
            },
            "cwd": str(ROOT),
        }
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(ROOT))
        proc = subprocess.run(["sh", "-c", cmd], input=json.dumps(payload),
                              capture_output=True, text=True, cwd=str(ROOT), timeout=60, env=env)
        self.assertEqual(proc.returncode, 0, "hook は常に exit 0 であるべき（|| の右辺が走らないため）")
        self.assertIn("deny", proc.stdout, "不正な遷移が拒否されていない: " + proc.stdout[:200])

    def test_valid_write_is_allowed(self):
        """正当な書き込みは拒否されないこと（過剰にブロックしていない）。"""
        cmd = self._pre_tool_use_command()
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(ROOT / "docs" / "SPEC.md"), "content": "x"},
            "cwd": str(ROOT),
        }
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(ROOT))
        proc = subprocess.run(["sh", "-c", cmd], input=json.dumps(payload),
                              capture_output=True, text=True, cwd=str(ROOT), timeout=60, env=env)
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("deny", proc.stdout, "チケット外の書き込みまで拒否している")


if __name__ == "__main__":
    unittest.main()
