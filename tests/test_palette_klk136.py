# KLK-136 ブリッジの接続先をポート決め打ちにしない（tester所有）。
#
# ★経緯: KLK-132 のフルスイートで e2e_klk127 / e2e_klk128 が落ちた。原因は生成設定画面が
#   接続先を 127.0.0.1:8765 で決め打ちしていたこと。画面自身はブリッジから配信されているのに、
#   稼働確認だけ常に 8765 を叩くため、既定以外のポートでは「非稼働」と判定され、
#   実績カタログもワンクリック生成も無効になっていた。
#   同梱の案内（はじめにお読みください.txt）が KLK_BRIDGE_PORT での起動を勧めているので実害がある。
#   なお、この2本の e2e がこれまで緑だったのは、別途 8765 でブリッジが動いていたからと考えられる
#   （テストが外の常駐プロセスに依存していた）。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk136 … 接続先の決め方・決め打ちの残存・既定ポートの二重管理照合
#   2. ★e2e_klk136 … **実際に空きポートでブリッジを立て、実ブラウザでカタログを読ませる**
#   3. 書き出しの純関数を直接突く（環境変数を実プロセスへ入れない）
import importlib.util
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk136.py"
E2E = ROOT / "tests" / "site" / "e2e_klk136.node.js"
MAKE_COMPARE = ROOT / "draft-gen" / "make_compare.py"

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


def load_make_compare():
    spec = importlib.util.spec_from_file_location("klk136_make_compare", MAKE_COMPARE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK136StaticChecker(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk136.py 失敗:\n%s" % p.stdout[-2000:])
        self.assertIn(", 0 failed", p.stdout)


class TestBridgeOriginFunction(unittest.TestCase):
    """書き出し時のポート決定（純関数）。環境変数は引数で渡し、実プロセスは汚さない。"""

    @classmethod
    def setUpClass(cls):
        cls.mc = load_make_compare()

    def test_default_when_unset(self):
        self.assertEqual(self.mc.bridge_origin({}), "http://127.0.0.1:8765")

    def test_uses_given_port(self):
        self.assertEqual(self.mc.bridge_origin({"KLK_BRIDGE_PORT": "8766"}),
                         "http://127.0.0.1:8766")

    def test_falls_back_on_garbage(self):
        for bad in ("abc", "", "  ", "0", "99999", "-1", "80.5"):
            self.assertEqual(self.mc.bridge_origin({"KLK_BRIDGE_PORT": bad}),
                             "http://127.0.0.1:8765", "壊れた値 %r で既定へ倒れていない" % bad)

    def test_default_matches_bridge(self):
        """★書き写した数字は腐る。bridge.py の既定ポートと一致していること。"""
        src = (ROOT / "draft-gen" / "bridge.py").read_text(encoding="utf-8")
        line = [l for l in src.split("\n") if l.startswith("DEFAULT_PORT = ")]
        self.assertTrue(line, "bridge.py に DEFAULT_PORT が無い")
        self.assertEqual(int(line[0].split("=")[1].split("#")[0].strip()),
                         self.mc.DEFAULT_BRIDGE_PORT)


class TestKLK136E2E(unittest.TestCase):
    """★実効果: 既定以外のポートでブリッジを立て、実ブラウザでカタログが読まれるまで見る。"""

    def test_non_default_port_works_in_browser(self):
        if not shutil.which("node"):
            self.skipTest("node が無い環境")
        ch = chrome_path()
        if not ch:
            self.skipTest("ヘッドレス Chrome が無い環境")
        env = dict(os.environ, KLK_E2E_CHROME=ch)
        p = subprocess.run(["node", str(E2E)], capture_output=True, text=True,
                           timeout=420, env=env, cwd=str(ROOT))
        if p.returncode == 3:
            self.skipTest("e2e が環境理由で SKIP: %s" % (p.stdout + p.stderr)[-300:])
        self.assertEqual(p.returncode, 0,
                         "e2e_klk136.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("E2 ★既定以外のポートで、実績カタログを実際に読み込む", p.stdout)
        self.assertIn("E4 ★8765 を一度も叩いていない", p.stdout)


if __name__ == "__main__":
    unittest.main()
