# KLK-132 起動.bat が Windows のバッチとして成立していること（tester所有）。
#
# ★経緯: 2026-09-16 の実使用レビュー（Windows 実機）で「ダブルクリックしても無反応」
#   「'ode' is not recognized」が報告された。原因は 起動.bat が macOS 由来の形
#   （改行 LF のみ・文字コード UTF-8）のままだったこと。日本語 Windows の cmd.exe は
#   CRLF 前提・CP932 既定で読むため、行の区切りと読み取り位置の両方がずれていた。
#   → CP932(Shift_JIS) + CRLF を正とする（docs/designs/KLK-132.md）。
#
# ★このテストが守っているもの:
#   - checker 本体が全件PASSし、実ビルド部（A11）が省略されずに走ること
#   - 不変条件を checker とは**別のコード**でもう一度確かめること（検査の共倒れ防止）
#   - ★妨害注入 — 実際に UTF-8/LF へ戻すと checker が落ちること。
#     「壊れたことを確かめてから」判定し、必ず元に戻す
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk132.py"
BAT = ROOT / "起動.bat"
CMD = ROOT / "起動.command"
ATTR = ROOT / ".gitattributes"


class TestKLK132StaticChecker(unittest.TestCase):
    def test_static_checker_passes(self):
        """checker本体（パッケージ実ビルド込み）が全件PASSする。"""
        p = subprocess.run(["python3", str(STATIC_CHECKER)],
                           capture_output=True, text=True, timeout=900)
        self.assertEqual(p.returncode, 0,
                         "check_klk132.py 失敗:\n%s" % p.stdout[-2000:])
        self.assertIn(", 0 failed", p.stdout)
        # 実ビルド部（A11）と自己検査（A12）が省略されずに走ったことまで確認する
        # （--fast で走ると A11 が無くても "0 failed" になり得るため）
        self.assertIn("A11 ★実ビルドした配布物の 起動.bat がリポジトリのものとバイト一致する",
                      p.stdout)
        self.assertIn("A12 自己検査", p.stdout)


class TestLauncherBytes(unittest.TestCase):
    """不変条件を checker とは別のコードで確かめる（両方が同時に壊れないように）。"""

    @classmethod
    def setUpClass(cls):
        cls.data = BAT.read_bytes()

    def test_decodes_as_cp932(self):
        self.data.decode("cp932")           # 例外が出なければよい

    def test_not_utf8(self):
        # UTF-8 で保存し直す事故を検知できる状態か（日本語を含むので両立しない）
        with self.assertRaises(UnicodeDecodeError):
            self.data.decode("utf-8")

    def test_crlf_only(self):
        self.assertEqual(self.data.replace(b"\r\n", b"").count(b"\n"), 0, "単独の LF が残っている")
        self.assertGreater(self.data.count(b"\r\n"), 0)

    def test_no_bom_and_no_chcp(self):
        self.assertFalse(self.data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"chcp", self.data)

    def test_skeleton_is_ascii(self):
        """骨格（cmd が解釈する制御構造）はすべて ASCII であること。"""
        text = self.data.decode("cp932")
        for token in ("@echo off", "setlocal", "endlocal", 'cd /d "%~dp0"',
                      "draft-gen\\bridge.py", "where claude", "py -3 --version"):
            self.assertIn(token, text)
            self.assertTrue(all(ord(c) < 128 for c in token))

    def test_no_dame_moji(self):
        """2バイト目が 0x5C（\\）になる CP932 文字を含まないこと。"""
        text = self.data.decode("cp932")
        bad = [c for c in set(text)
               if ord(c) > 127 and len(c.encode("cp932")) == 2
               and c.encode("cp932")[1] == 0x5C]
        self.assertEqual(bad, [], "ダメ文字が混ざっている: %s" % bad)

    def test_macos_launcher_untouched(self):
        """macOS 側は UTF-8 + LF のまま（今回の変更に巻き込まれていないこと）。"""
        cmd = CMD.read_bytes()
        cmd.decode("utf-8")
        self.assertNotIn(b"\r\n", cmd)

    def test_gitattributes_protects_eol(self):
        text = ATTR.read_text(encoding="utf-8")
        rule = [l for l in text.split("\n")
                if l.strip() and not l.startswith("#") and "起動.bat" in l]
        self.assertTrue(rule, ".gitattributes に 起動.bat の規則が無い")
        self.assertIn("-text", rule[0])


class TestSabotage(unittest.TestCase):
    """★実際に壊すと checker が落ちること。壊れたことを確かめてから判定し、必ず戻す。"""

    def test_utf8_lf_version_is_rejected(self):
        original = BAT.read_bytes()
        broken = original.decode("cp932").replace("\r\n", "\n").encode("utf-8")
        # 壊れていることを先に確かめる（ここが成り立たないと判定が空になる）
        self.assertNotEqual(broken, original)
        self.assertEqual(broken.replace(b"\r\n", b"").count(b"\n") > 0, True)
        broken.decode("utf-8")              # UTF-8 として読めてしまう＝事故の形
        try:
            BAT.write_bytes(broken)
            p = subprocess.run(["python3", str(STATIC_CHECKER), "--fast"],
                               capture_output=True, text=True, timeout=300)
            self.assertNotEqual(p.returncode, 0, "UTF-8/LF に戻しても checker が通ってしまう")
            self.assertIn("[FAIL] A2", p.stdout)
            self.assertIn("[FAIL] A3", p.stdout)
        finally:
            BAT.write_bytes(original)
        self.assertEqual(BAT.read_bytes(), original, "妨害注入のあと元に戻せていない")


if __name__ == "__main__":
    unittest.main()
