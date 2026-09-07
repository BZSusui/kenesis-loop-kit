# KLK-104 「案が足りないのに完了と報告する」不具合（tester所有）。
#
# ★背景（自分が招いた回帰）
#   ブリッジは「compare.html が存在するか」で成功を判定していた。
#   KLK-103 で compare.html を**ブリッジ自身が書くようにした**ため、
#   その存在は「スキルが最後まで走った」証拠ではなくなった。
#   結果、3案を頼んで**2案しかできていないのに「生成が完了しました」**と報告した
#   （案C と instruction.json が無かった）。しかも `verify-mockup --strict` は
#   「違反 0 件」と言った。compare.html は実在ファイルだけで組まれるので
#   **見た目は整っており**、ファイル数を数えるだけでは気づけない。
#
#   ★教訓: 成功判定の根拠にしていたものを自分で作るようになったら、判定を作り直す。
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_bridge():
    """テストと同じ読み込み方（sys.path に依存しない）。"""
    spec = importlib.util.spec_from_file_location(
        "klk104_bridge", str(ROOT / "draft-gen" / "bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK104VariantCounting(unittest.TestCase):
    """案の本数を数える純関数。"""

    def setUp(self):
        self.b = load_bridge()
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _touch(self, name):
        io.open(os.path.join(self.d, name), "w", encoding="utf-8").write("<html></html>")

    def test_counts_multi_variants(self):
        for n, names in ((1, ["index-a.html"]),
                         (2, ["index-a.html", "index-b.html"]),
                         (3, ["index-a.html", "index-b.html", "index-c.html"])):
            with self.subTest(n):
                shutil.rmtree(self.d, ignore_errors=True)
                os.makedirs(self.d)
                for x in names:
                    self._touch(x)
                self.assertEqual(self.b.count_variant_files(self.d), n)

    def test_counts_single(self):
        self._touch("index.html")
        self.assertEqual(self.b.count_variant_files(self.d), 1)

    def test_empty_folder_is_zero(self):
        self.assertEqual(self.b.count_variant_files(self.d), 0)

    def test_compare_html_alone_is_not_a_variant(self):
        """★compare.html だけでは成功にしない。これが今回の不具合の核。"""
        self._touch("compare.html")
        self.assertEqual(self.b.count_variant_files(self.d), 0)


class TestKLK104Shortfall(unittest.TestCase):
    """頼んだ数との差を返すこと。"""

    def setUp(self):
        self.b = load_bridge()
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _make(self, n):
        for L in "abc"[:n]:
            io.open(os.path.join(self.d, "index-%s.html" % L), "w",
                    encoding="utf-8").write("<html></html>")

    def test_reports_shortfall(self):
        self._make(2)
        self.assertEqual(self.b.variant_shortfall(self.d, 3), 1,
                         "3案頼んで2案なら1案不足と出るべき")

    def test_no_shortfall_when_complete(self):
        self._make(3)
        self.assertEqual(self.b.variant_shortfall(self.d, 3), 0)

    def test_extra_is_not_negative(self):
        self._make(3)
        self.assertEqual(self.b.variant_shortfall(self.d, 1), 0)

    def test_non_numeric_request_falls_back_to_one(self):
        """数として読めない値は1案扱い（落ちない）。"""
        self._make(1)
        for bad in (None, "x", [], {}, object()):
            with self.subTest(bad):
                self.assertEqual(self.b.variant_shortfall(self.d, bad), 0)

    def test_numeric_request_is_clamped_to_1_3(self):
        """数として読める値は 1〜3 に収める（案は最大3案・§12）。

        範囲外を1案に落とすと「99案頼んだのに1案」を見逃す。
        上限3へ寄せて、足りない分は不足として出す。
        """
        self._make(1)
        self.assertEqual(self.b.variant_shortfall(self.d, 99), 2,
                         "上限3にクランプして不足2と出るべき")
        self.assertEqual(self.b.variant_shortfall(self.d, -5), 0,
                         "下限1にクランプして不足なし")
        self.assertEqual(self.b.variant_shortfall(self.d, "3"), 2,
                         "文字列の数字も読む（指示書が JSON 文字列のことがある）")


class TestKLK104BridgeReportsHonestly(unittest.TestCase):
    """ブリッジが不足を隠さないこと（メッセージの文言まで見る）。"""

    def test_message_branches_on_shortfall(self):
        src = (ROOT / "draft-gen" / "bridge.py").read_text(encoding="utf-8")
        self.assertIn("shortfall == 0", src,
                      "不足の有無でメッセージを分けていない")
        self.assertIn("案しかできませんでした", src,
                      "不足を伝える文言が無い")
        self.assertIn("variantsShortfall", src,
                      "/status に不足を出していない（画面から見えない）")

    def test_success_no_longer_keys_on_compare_html(self):
        """★成功判定が compare.html の存在に戻っていないこと。

        ブリッジ自身が書くファイルを成功の根拠にしてはならない。
        """
        src = (ROOT / "draft-gen" / "bridge.py").read_text(encoding="utf-8")
        self.assertIn("is_job_success(proc.returncode, made > 0)", src,
                      "成功判定が案の本数になっていない")


class TestKLK104VerifyMockupReconciles(unittest.TestCase):
    """verify-mockup が指示書の案数と実際を突き合わせること。"""

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _setup(self, n_files, n_requested):
        src = ROOT / "samples" / "01_カフェ_1カラム"
        for L in "abc"[:n_files]:
            shutil.copy2(src / ("index-%s.html" % L), os.path.join(self.d, "index-%s.html" % L))
        inst = json.loads((src / "instruction.json").read_text(encoding="utf-8"))
        inst["output"]["variants"] = n_requested
        io.open(os.path.join(self.d, "instruction.json"), "w", encoding="utf-8").write(
            json.dumps(inst, ensure_ascii=False))
        subprocess.run(["python3", str(ROOT / "draft-gen" / "make_compare.py"),
                        self.d, "--folder=mockups/dummy"],
                       capture_output=True, cwd=str(ROOT), timeout=60)

    def _run(self):
        return subprocess.run(["python3", str(ROOT / "tools" / "verify-mockup.py"), self.d],
                              capture_output=True, text=True, cwd=str(ROOT), timeout=120)

    def test_detects_missing_variant(self):
        self._setup(2, 3)
        p = self._run()
        self.assertNotEqual(p.returncode, 0, "案不足を見逃した")
        self.assertIn("指示書は3案ですが、実際は2案", p.stdout)

    def test_passes_when_complete(self):
        self._setup(3, 3)
        p = self._run()
        self.assertEqual(p.returncode, 0, "揃っているのに違反と言った:\n" + p.stdout)

    def test_missing_instruction_is_flagged(self):
        """指示書が無いこと自体を伝える（照合できないと黙らない）。"""
        self._setup(3, 3)
        os.remove(os.path.join(self.d, "instruction.json"))
        p = self._run()
        self.assertIn("instruction.json がありません", p.stdout)


if __name__ == "__main__":
    unittest.main()
