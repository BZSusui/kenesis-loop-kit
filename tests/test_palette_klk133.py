# KLK-133 claude を実体で見つける（tester所有）。
#
# ★経緯: 2026-09-16 の実使用レビュー（Windows 実機）で、claude.exe が
#   %USERPROFILE%\.local\bin に実在するのに「見つかりません」で起動が止まった。
#   そのフォルダがユーザー PATH に無かったため。調査で同じ原因系がもう2つ見つかった:
#   起動.command（mac）も PATH しか見ていない／bridge.py は claude.cmd（npm版）を起動できない
#   （Windows の CreateProcess は PATHEXT を見ず .exe しか補わない）。
#
# ★このテストが守っているもの:
#   - checker 本体が全件PASSすること
#   - ★**Windows 実機が使えない期間でも条件を再現できる**こと。解決は純関数で、
#     PATH 探索・実在判定・環境変数・プラットフォームをすべて引数で渡せる
#   - 組み立て（build_*_command）の形を変えていないこと
#   - 起動3箇所すべてが解決を通っていること（1箇所でも素通りすると生成だけ失敗する）
import importlib.util
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk133.py"
BRIDGE = ROOT / "draft-gen" / "bridge.py"

WIN_ENV = {
    "USERPROFILE": "C:\\Users\\tester",
    "APPDATA": "C:\\Users\\tester\\AppData\\Roaming",
    "LOCALAPPDATA": "C:\\Users\\tester\\AppData\\Local",
}
MAC_ENV = {"HOME": "/Users/tester"}
CMD = ["claude", "-p", "/draft-generate x.json"]


def load_bridge():
    spec = importlib.util.spec_from_file_location("klk133_bridge", BRIDGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK133StaticChecker(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk133.py 失敗:\n%s" % p.stdout[-2000:])
        self.assertIn(", 0 failed", p.stdout)


class TestResolveClaudeArgv(unittest.TestCase):
    """★実機が無くても条件を作れること自体が、このチケットの肝。"""

    @classmethod
    def setUpClass(cls):
        cls.b = load_bridge()

    def r(self, **kw):
        kw.setdefault("isfile", lambda p: False)
        return self.b.resolve_claude_argv(CMD, **kw)

    def test_uses_path_hit_as_absolute(self):
        got = self.r(platform="win32", env=WIN_ENV, which=lambda n: "C:\\bin\\claude.exe")
        self.assertEqual(got, ["C:\\bin\\claude.exe"] + CMD[1:])

    def test_finds_installer_location_when_not_on_path(self):
        """レビューで実際に起きた条件（PATH に無いが .local\\bin に在る）。"""
        want = "C:\\Users\\tester\\.local\\bin\\claude.exe"
        got = self.r(platform="win32", env=WIN_ENV, which=lambda n: None,
                     isfile=lambda p: p == want)
        self.assertEqual(got, [want] + CMD[1:])

    def test_npm_cmd_goes_through_cmd_exe(self):
        """★CreateProcess は .cmd を起動できない。cmd /c を挟むこと。"""
        got = self.r(platform="win32", env=WIN_ENV, which=lambda n: "C:\\npm\\claude.cmd")
        self.assertEqual(got[:3], ["cmd", "/c", "C:\\npm\\claude.cmd"])
        self.assertEqual(got[3:], CMD[1:])

    def test_bat_also_goes_through_cmd_exe(self):
        got = self.r(platform="win32", env=WIN_ENV, which=lambda n: "C:\\x\\claude.BAT")
        self.assertEqual(got[:3], ["cmd", "/c", "C:\\x\\claude.BAT"])

    def test_mac_never_uses_cmd_exe(self):
        got = self.r(platform="darwin", env=MAC_ENV, which=lambda n: "/usr/local/bin/claude.cmd")
        self.assertNotEqual(got[0], "cmd")

    def test_unchanged_when_nothing_found(self):
        """見つからないときは変えない（呼び出し側が従来どおり案内を出す）。"""
        self.assertEqual(self.r(platform="win32", env=WIN_ENV, which=lambda n: None), CMD)

    def test_ignores_commands_that_are_not_claude(self):
        got = self.b.resolve_claude_argv(["python3", "-V"], platform="win32", env=WIN_ENV,
                                         which=lambda n: "C:\\bin\\claude.exe",
                                         isfile=lambda p: False)
        self.assertEqual(got, ["python3", "-V"])

    def test_empty_command_is_safe(self):
        self.assertEqual(self.b.resolve_claude_argv([], platform="win32", env={},
                                                    which=lambda n: None,
                                                    isfile=lambda p: False), [])

    def test_candidates_use_platform_separator(self):
        win = self.b.claude_candidates("win32", WIN_ENV)
        mac = self.b.claude_candidates("darwin", MAC_ENV)
        self.assertTrue(all("\\" in c and "/" not in c for c in win), win)
        self.assertTrue(all(c.startswith("/") for c in mac), mac)

    def test_candidates_skip_missing_env(self):
        """環境変数が無い項目は黙って飛ばす（存在しない置き場所を探さない）。"""
        self.assertEqual(self.b.claude_candidates("win32", {}), [])
        only_home = self.b.claude_candidates("darwin", {})
        self.assertTrue(all(not c.startswith("/Users") for c in only_home), only_home)

    def test_arguments_are_preserved(self):
        """引数は1つも落とさない・増やさない（最小権限のフラグが消えると事故になる）。"""
        full = ["claude", "-p", "/draft-generate x.json", "--permission-mode", "acceptEdits",
                "--output-format", "json"]
        got = self.b.resolve_claude_argv(full, platform="win32", env=WIN_ENV,
                                         which=lambda n: "C:\\npm\\claude.cmd",
                                         isfile=lambda p: False)
        self.assertEqual(got[3:], full[1:])


class TestLaunchSites(unittest.TestCase):
    def test_all_three_launch_sites_resolve(self):
        """1箇所でも素通りすると、その機能だけが Windows で失敗する。"""
        src = BRIDGE.read_text(encoding="utf-8")
        for builder in ("build_claude_command", "build_regenerate_command",
                        "build_catalog_import_command"):
            self.assertIn("resolve_claude_argv(%s(" % builder, src,
                          "%s の起動が解決を通っていない" % builder)

    def test_builders_shape_unchanged(self):
        b = load_bridge()
        for cmd in (b.build_claude_command("x.json"),
                    b.build_regenerate_command("x.json"),
                    b.build_catalog_import_command("x.json")):
            self.assertEqual(cmd[:2], ["claude", "-p"])


if __name__ == "__main__":
    unittest.main()
