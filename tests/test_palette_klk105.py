# KLK-105/106 起動を最上位へ／アイコン／セットアップ手順書（tester所有）。
# - 静的＋実パッケージ検査: tests/site/check_klk105.py（A〜Q）
# - 追加: **移動して壊れていないこと**と、**手引きの記述が実装と食い違わないこと**。
import io
import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk105.py"
GUIDE = ROOT / "はじめにお読みください.txt"


class TestKLK105Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(["python3", str(STATIC_CHECKER)],
                              capture_output=True, text=True, cwd=str(ROOT), timeout=300)
        self.assertEqual(proc.returncode, 0,
                         "check_klk105.py failed:\n" + proc.stdout + proc.stderr)


class TestKLK105LauncherStillWorks(unittest.TestCase):
    """最上位へ移して壊れていないこと。

    `cd` を1階層ぶん直す必要があった。直し忘れると**親フォルダへ出てしまい**、
    bridge.py が見つからない。構文と参照を静的に確かめる（実行はしない）。
    """

    def test_bash_syntax_is_valid(self):
        p = subprocess.run(["bash", "-n", str(ROOT / "起動.command")],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_cd_targets_its_own_folder(self):
        cmd = (ROOT / "起動.command").read_text(encoding="utf-8")
        self.assertIn('cd "$(dirname "$0")"', cmd)
        self.assertNotIn('cd "$(dirname "$0")/.."', cmd,
                         "1階層上へ出てしまう（最上位へ移したので `/..` は不要）")

    def test_bat_cd_targets_its_own_folder(self):
        # ★KLK-132: 起動.bat は CP932(Shift_JIS)+CRLF が正。UTF-8 で読むと落ちる
        bat = (ROOT / "起動.bat").read_text(encoding="cp932")
        self.assertIn("%~dp0", bat)
        self.assertNotIn("%~dp0..", bat)

    def test_bridge_path_still_resolves(self):
        """スクリプトが指す bridge.py が、移動後の基準で実在すること。"""
        self.assertTrue((ROOT / "draft-gen" / "bridge.py").is_file())


class TestKLK105GuideMatchesReality(unittest.TestCase):
    """手引きの記述が実装と食い違わないこと。

    セットアップ手順が間違っていると、受け取った人は最初の5分で詰まる。
    そこで嘘をつくのが一番まずい。
    """

    def test_files_it_points_at_exist(self):
        g = GUIDE.read_text(encoding="utf-8")
        for fn in ("起動.command", "起動.bat", "使い方マニュアル.html", "README.md"):
            with self.subTest(fn):
                self.assertIn(fn, g)
                self.assertTrue((ROOT / fn).is_file(), "%s が実在しない" % fn)

    def test_folders_it_points_at_exist(self):
        g = GUIDE.read_text(encoding="utf-8")
        self.assertIn("mockups", g)
        self.assertTrue((ROOT / "mockups").is_dir())

    def test_port_matches_implementation(self):
        g = GUIDE.read_text(encoding="utf-8")
        bridge = (ROOT / "draft-gen" / "bridge.py").read_text(encoding="utf-8")
        m = re.search(r"DEFAULT_PORT\s*=\s*(\d+)", bridge)
        self.assertIsNotNone(m)
        self.assertIn(m.group(1), g, "手引きの既定ポートが実装と違う")
        self.assertIn("KLK_BRIDGE_PORT", bridge,
                      "手引きが案内する環境変数が実装に無い")

    def test_no_developer_ids_leak(self):
        """手引きは受け取った人が読むもの。開発用の番号を出さない（KLK-085 と同じ規律）。"""
        g = GUIDE.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"(?:REQ|KLK|SCR|NFR|OQ)-\d+", g))

    def test_defers_handling_judgement(self):
        self.assertIn("AI利用管理責任者", GUIDE.read_text(encoding="utf-8"))


class TestKLK106IconIsReproducible(unittest.TestCase):
    """アイコンを作り直せること（元データと道具が残っている）。

    元データを捨てると、次に作り直したいとき詰む。
    """

    def test_source_svg_kept(self):
        self.assertTrue((ROOT / "assets" / "icons" / "起動アイコン.svg").is_file())

    def test_tool_kept(self):
        self.assertTrue((ROOT / "tools" / "set-mac-icon.py").is_file())

    def test_tool_records_the_zip_caveat(self):
        """ZIP の注意（ditto でないと消える）を道具自身が持っていること。

        この知見は実測で得たもので、忘れるとアイコンが黙って消える。
        """
        t = (ROOT / "tools" / "set-mac-icon.py").read_text(encoding="utf-8")
        self.assertIn("ditto", t)
        self.assertIn("zip -r", t)

    def test_resource_fork_builder_is_pure(self):
        """リソースフォークの組み立てが副作用なしで、正しい icns を含むこと。"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "klk_seticon", str(ROOT / "tools" / "set-mac-icon.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fake = b"icns" + bytes(120)
        fork = mod.build_resource_fork(fake)
        self.assertGreater(len(fork), 256)
        import struct
        data_off, map_off, data_len, map_len = struct.unpack(">IIII", fork[:16])
        self.assertEqual(data_off, 256)
        self.assertEqual(map_off, 256 + data_len)
        n = struct.unpack(">I", fork[data_off:data_off + 4])[0]
        self.assertEqual(fork[data_off + 4:data_off + 4 + n], fake)


if __name__ == "__main__":
    unittest.main()
