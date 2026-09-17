# KLK-134 置き場所の前提を案内する（tester所有）。
#
# ★経緯: 2026-09-16 の実使用レビューで、一式が WSL 側（\\wsl.localhost\...）に置かれており
#   起動.bat が失敗した。cmd.exe は「\\」で始まるパスをカレントにできない。
#   表示は「移動できませんでした」だけで、原因にたどり着けなかった。
#   さらに同梱の案内が「共有フォルダに置いても構わない」と書いており、実態と食い違っていた。
#
# ★このテストが守っているもの:
#   - checker 本体が全件PASSすること
#   - ★判定が cd より**前**にあること（順序が逆だと、一般的な失敗としてしか出ない）
#   - 案内が3つの文書すべてに載っていること（受け取る人が見る場所はひとつではない）
#   - 起動.bat が CP932+CRLF のままであること（KLK-132 を壊していない）
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk134.py"
BAT = ROOT / "起動.bat"
GUIDE = ROOT / "はじめにお読みください.txt"
README = ROOT / "README.md"
MANUAL = ROOT / "使い方マニュアル.html"


class TestKLK134StaticChecker(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk134.py 失敗:\n%s" % p.stdout[-2000:])
        self.assertIn(", 0 failed", p.stdout)


class TestBatProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bat = BAT.read_text(encoding="cp932")     # KLK-132: CP932 が正

    def test_probe_runs_before_cd(self):
        """★順序が命。cd が先だと「移動できませんでした」としか出ない。"""
        probe = self.bat.find('if "%KLK_HERE:~0,2%"=="\\\\"')
        cd = self.bat.find('cd /d "%~dp0"')
        self.assertGreaterEqual(probe, 0, "置き場所の判定が無い")
        self.assertGreaterEqual(cd, 0)
        self.assertLess(probe, cd, "判定が cd より後ろにある")

    def test_probe_exits_without_starting_bridge(self):
        """判定に引っかかったら、ブリッジを起動せずに止まること。"""
        probe = self.bat.find('if "%KLK_HERE:~0,2%"=="\\\\"')
        bridge = self.bat.find("draft-gen\\bridge.py")
        block = self.bat[probe:bridge]
        self.assertIn("exit /b 1", block, "判定のあとに終了していない")

    def test_no_nested_parentheses_pitfall(self):
        """★cmd の入れ子括弧＋変数代入は遅延展開が要る。set を括弧の中に入れない。"""
        probe = self.bat.find('if "%KLK_HERE:~0,2%"=="\\\\"')
        end = self.bat.find(":claude_ok")
        block = self.bat[probe:end] if end > probe else self.bat[probe:]
        # 判定ブロックの中で PATH 等を組み立てていないこと（echo と exit だけ）
        self.assertNotIn('set "PATH=', block.split(")")[0])

    def test_encoding_unchanged(self):
        """KLK-132 を壊していない（CP932・CRLF・BOM なし）。"""
        raw = BAT.read_bytes()
        raw.decode("cp932")
        with self.assertRaises(UnicodeDecodeError):
            raw.decode("utf-8")
        self.assertEqual(raw.replace(b"\r\n", b"").count(b"\n"), 0)
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))


class TestDocuments(unittest.TestCase):
    def test_all_three_documents_carry_the_condition(self):
        """受け取る人が見る場所は1つではない。3つとも書かれていること。"""
        for path, enc in ((GUIDE, "utf-8"), (README, "utf-8"), (MANUAL, "utf-8")):
            text = path.read_text(encoding=enc)
            self.assertIn("wsl.localhost", text, "%s に WSL の説明が無い" % path.name)
            self.assertIn("python3 draft-gen/bridge.py", text,
                          "%s に WSL での代替手順が無い" % path.name)

    def test_old_claim_is_gone(self):
        text = GUIDE.read_text(encoding="utf-8")
        self.assertNotIn("社内の共有フォルダに置いても、デスクトップに置いても構いません", text)

    def test_launcher_location_is_top_level(self):
        """KLK-105 で最上位へ移したのに、README とマニュアルは draft-gen を開けと書いていた。"""
        self.assertNotIn("`draft-gen` フォルダの中の起動ファイル",
                         README.read_text(encoding="utf-8"))
        self.assertNotIn("フォルダの中の <code>draft-gen</code> を開きます",
                         MANUAL.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
