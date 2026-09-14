# KLK-116 配色ジェネレーターの配色をモック生成画面へ自動で渡す（tester所有）。
#
# ★経緯: 実ユーザーのフィードバック「CSS変数をコピー→貼り付けの手間が気になる」（2026-09-11）。
#   SCR-001 には貼り付け解析が既にあり、足りなかったのは palette → SCR-001 のタブ間の経路だけ。
#   ブリッジ配信時は同一オリジン（KLK-019）なので BroadcastChannel＋localStorage で渡す。
#
# ★このテストが守っているもの（3層）:
#   1. 静的   tests/site/check_klk116.py  … 仕組みの有無・4定数の値が両画面で一致・貼り付け経路の温存
#   2. 動的   tests/site/smoke_klk116.node.js … 純粋関数の受理/拒否（妨害注入: schema違い・壊れたhex）
#   3. 実効果 tests/site/e2e_klk116.node.js … ブリッジ実起動＋ヘッドレス Chrome で
#             palette の「送る」→ 別タブの SCR-001 に実際に色が入る／保管分は［反映する］で入る
#             （Chrome が無い環境では明示的に SKIP。黙って PASS にはしない）
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk116.py"
SMOKE = ROOT / "tests" / "site" / "smoke_klk116.node.js"
E2E = ROOT / "tests" / "site" / "e2e_klk116.node.js"

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
)


def chrome_path():
    for c in CHROME_CANDIDATES:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


class TestKLK116Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, "check_klk116.py 失敗:\n%s" % p.stdout[-2000:])
        self.assertIn(", 0 failed", p.stdout)
        # 定数の値照合（C2）が実際に走っていること
        self.assertIn("C2 4定数の値が両画面で一致する", p.stdout)


class TestKLK116Smoke(unittest.TestCase):
    def test_pure_functions(self):
        if not shutil.which("node"):
            self.skipTest("node が無い環境")
        p = subprocess.run(["node", str(SMOKE)], capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, "smoke_klk116.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-2000:])
        self.assertIn(", 0 failed", p.stdout)
        # 妨害注入（D2/D3）が走っていること
        self.assertIn("D2 schema が違えば null", p.stdout)
        self.assertIn("D3 壊れた hex は落ち", p.stdout)


class TestKLK116E2E(unittest.TestCase):
    """★実効果: 文字列の有無ではなく「別タブへ実際に届いた」ことを見る。"""

    def test_handoff_reaches_other_tab(self):
        if not shutil.which("node"):
            self.skipTest("node が無い環境")
        ch = chrome_path()
        if not ch:
            self.skipTest("ヘッドレス Chrome が無い環境（実効果テストは SKIP・静的/動的は上で担保）")
        env = dict(os.environ, KLK_E2E_CHROME=ch)
        p = subprocess.run(["node", str(E2E)], capture_output=True, text=True, timeout=300, env=env, cwd=str(ROOT))
        if p.returncode == 3:
            self.skipTest("e2e が環境理由で SKIP: %s" % (p.stdout + p.stderr)[-400:])
        self.assertEqual(p.returncode, 0, "e2e_klk116.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        # 主要3場面が走っていること
        self.assertIn("E1", p.stdout)   # 開いているタブへ即時
        self.assertIn("E2", p.stdout)   # 妨害注入で変わらない
        self.assertIn("E3", p.stdout)   # 保管分を［反映する］


if __name__ == "__main__":
    unittest.main()
