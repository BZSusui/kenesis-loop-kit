# KLK-098 使い方マニュアル（HTML）を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的＋実物突き合わせ: tests/site/check_klk098.py（C0-C29）
# - 追加: マニュアルが**配布物の規律**（外部依存ゼロ）と**社外秘の不記載**を守ること、
#   および README との役割分担が崩れていないことを検査する。
import io
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk098.py"
MANUAL = ROOT / "使い方マニュアル.html"
README = ROOT / "README.md"


class TestKLK098Static(unittest.TestCase):
    """check_klk098.py（外部依存ゼロ・社外秘不記載・実物との一致）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk098.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK098SelfContained(unittest.TestCase):
    """マニュアルは生成物と同じ規律（外部依存ゼロ）に従うこと。

    配布先はネットワークが制限された社内環境かもしれない。
    CDN を1本でも足すと、その環境で崩れて表示される。
    """

    def test_no_network_references(self):
        m = MANUAL.read_text(encoding="utf-8")
        for pat, label in (
            (r'<link\b[^>]*\bhref=', "<link href>"),
            (r'<script\b[^>]*\bsrc=', "<script src>"),
            (r"https?://", "外部URL"),
            (r"<(iframe|object|embed)\b", "埋め込み要素"),
        ):
            with self.subTest(label):
                self.assertIsNone(re.search(pat, m, re.I),
                                  "マニュアルに %s がある（外部依存ゼロに違反）" % label)


class TestKLK098NoConfidentialContent(unittest.TestCase):
    """マニュアルはクライアント説明にも使う想定のため、社外秘を載せないこと。

    カタログ（catalog/）は社外秘のご実績を含み、上長承認の条件が
    「社内でのみ使用することを徹底」であるため、実在のエントリを書いてはならない。
    """

    def test_no_catalog_file_references(self):
        m = MANUAL.read_text(encoding="utf-8")
        self.assertNotIn("catalog/img", m)
        self.assertNotIn("catalog.json", m)

    def test_defers_handling_judgement_to_the_responsible_person(self):
        """取り扱いの可否をマニュアルが独断で書かず、確認先を案内していること。"""
        m = MANUAL.read_text(encoding="utf-8")
        self.assertIn("AI利用管理責任者", m)


class TestKLK098DocumentRoles(unittest.TestCase):
    """README とマニュアルの役割分担が崩れていないこと。

    どちらか一方だけを更新すると、受け取った人が読む内容が食い違う
    （README が34件ぶん遅れた KLK-090 と同じ失敗）。
    """

    def test_readme_links_to_manual(self):
        self.assertIn("使い方マニュアル.html", README.read_text(encoding="utf-8"))

    def test_manual_links_back_to_readme(self):
        self.assertGreaterEqual(MANUAL.read_text(encoding="utf-8").count("README.md"), 3)

    def test_manual_is_packaged(self):
        pkg = (ROOT / "tools" / "make-package.sh").read_text(encoding="utf-8")
        self.assertIn("使い方マニュアル.html", pkg,
                      "マニュアルがパッケージに含まれていない")


if __name__ == "__main__":
    unittest.main()
