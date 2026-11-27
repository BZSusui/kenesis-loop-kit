# KLK-138 配色ジェネレーターの言葉と色の物差し のテストを unittest スイートへ束ねるラッパー
# - 静的チェック: tests/site/check_klk138.py（C1-C6・Python標準のみ）
# - 自己検査＋一致検査: tests/site/smoke_klk138.node.js（T1-T5・判定データがあれば V-M/V-G/V-C/V-E）
# - ベースラインの再現: tests/site/klk138_score.node.js --check（現行版＝指紋が一致する1件を照合。
#   生成側が記録済みのどの版とも違えば SKIP で合格）
# - KLK-140: 過去版の上書き拒否・ラベル必須・Python と Node の指紋の一致
# node が無い環境では後ろ2つを skip する。
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk138.py"
SMOKE = ROOT / "tests" / "site" / "smoke_klk138.node.js"
SCORE = ROOT / "tests" / "site" / "klk138_score.node.js"


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=120)


class TestKLK138Static(unittest.TestCase):
    """check_klk138.py（設計書 §4.8 C1-C6）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = _run(["python3", str(STATIC_CHECKER)])
        self.assertEqual(proc.returncode, 0, "check_klk138.py failed:\n" + proc.stdout + proc.stderr)


@unittest.skipUnless(shutil.which("node"), "node が見つからないため skip")
class TestKLK138Smoke(unittest.TestCase):
    """smoke_klk138.node.js（T1-T5＋人間の判定との一致）が全PASSすること。"""

    def test_smoke_pass(self):
        proc = _run(["node", str(SMOKE)])
        self.assertEqual(proc.returncode, 0, "smoke_klk138.node.js failed:\n" + proc.stdout + proc.stderr)


@unittest.skipUnless(shutil.which("node"), "node が見つからないため skip")
class TestKLK138Baseline(unittest.TestCase):
    """klk138_score.node.js --check で現行版のベースラインが再現できること。"""

    def test_baseline_reproduces(self):
        proc = _run(["node", str(SCORE), "--check"])
        self.assertEqual(proc.returncode, 0, "klk138_score.node.js --check failed:\n" + proc.stdout + proc.stderr)


def _copy_tree_without_data(dst):
    """判定データ（tickets/work/KLK-138・Git除外）を含まない最小の写しを作る（clone 直後相当）。"""
    dst = Path(dst)
    (dst / "palette").mkdir(parents=True)
    shutil.copy2(ROOT / "palette" / "index.html", dst / "palette" / "index.html")
    (dst / "tests" / "site").mkdir(parents=True)
    for p in (ROOT / "tests" / "site").glob("*klk138*"):
        shutil.copy2(p, dst / "tests" / "site" / p.name)
    shutil.copytree(ROOT / "tests" / "fixtures" / "klk138", dst / "tests" / "fixtures" / "klk138")
    build = ROOT / "tools" / "klk138_build_ruler.py"
    if build.exists():  # 配布物には tools/ が入らない（設計 §5）ので、あれば写す
        (dst / "tools").mkdir()
        shutil.copy2(build, dst / "tools" / "klk138_build_ruler.py")
    return dst


@unittest.skipUnless(shutil.which("node"), "node が見つからないため skip")
class TestKLK138Environment(unittest.TestCase):
    """環境の違い（判定データ無し・生成側の変更・壊れた物差し）で設計 §4.8 どおりに振る舞うこと。
    リポジトリ本体のファイルには触れず、一時ディレクトリの写しで確かめる。"""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.root = _copy_tree_without_data(Path(self._tmp.name) / "repo")

    def tearDown(self):
        self._tmp.cleanup()

    def _run_in(self, *cmd):
        return subprocess.run(list(cmd), capture_output=True, text=True, cwd=str(self.root), timeout=120)

    def test_no_judgment_data_skips_and_passes(self):
        """AC6: 判定データが無い環境では一致検査・C6 が SKIP で合格し、rulerValidation は null。"""
        smoke = self._run_in("node", "tests/site/smoke_klk138.node.js")
        self.assertEqual(smoke.returncode, 0, smoke.stdout + smoke.stderr)
        self.assertIn("[SKIP] 判定データが無い", smoke.stdout)
        static = self._run_in("python3", "tests/site/check_klk138.py")
        self.assertEqual(static.returncode, 0, static.stdout + static.stderr)
        self.assertIn("C6 ruler.json と生成スクリプトの出力が一致 [SKIP]", static.stdout)
        check = self._run_in("node", "tests/site/klk138_score.node.js", "--check")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        out = self._run_in("node", "tests/site/klk138_score.node.js", "--json")
        self.assertEqual(out.returncode, 0, out.stderr)
        import json
        data = json.loads(out.stdout)
        self.assertIsNone(data["rulerValidation"])
        self.assertEqual(data["primary"]["overall"]["wordsScored"], 20)

    def test_generator_change_makes_check_skip(self):
        """R-E: 生成側（切り出し範囲）が変わったら --check は SKIP で終了コード 0。"""
        html = self.root / "palette" / "index.html"
        src = html.read_text(encoding="utf-8")
        self.assertIn("const KEYWORDS = {", src)
        html.write_text(src.replace("const KEYWORDS = {", "const KEYWORDS = { /* changed */", 1), encoding="utf-8")
        proc = self._run_in("node", "tests/site/klk138_score.node.js", "--check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[SKIP] 生成側が記録済みのどの版", proc.stdout)

    def test_ruler_change_breaks_check(self):
        """物差しが変わったら --check は不一致（終了コード 1）。黙って通らない。"""
        import json
        p = self.root / "tests" / "fixtures" / "klk138" / "ruler.json"
        r = json.loads(p.read_text(encoding="utf-8"))
        r["words"]["清潔感のある"]["bg"] = "either"
        p.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        proc = self._run_in("node", "tests/site/klk138_score.node.js", "--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    def test_broken_ruler_is_harness_error(self):
        """壊れた ruler.json は採点 CLI がハーネス異常（終了コード 2）、静的チェックが FAIL。"""
        (self.root / "tests" / "fixtures" / "klk138" / "ruler.json").write_text('{"schema": ', encoding="utf-8")
        for args in ([], ["--json"], ["--check"]):
            proc = self._run_in("node", "tests/site/klk138_score.node.js", *args)
            self.assertEqual(proc.returncode, 2, "%s: %s" % (args, proc.stdout + proc.stderr))
        static = self._run_in("python3", "tests/site/check_klk138.py")
        self.assertEqual(static.returncode, 1, static.stdout)

    def test_missing_slice_marker_is_harness_error(self):
        """R-C: 切り出しマーカーが無ければ採点 CLI は終了コード 2。"""
        html = self.root / "palette" / "index.html"
        src = html.read_text(encoding="utf-8")
        html.write_text(src.replace("\nfunction render() {", "\nfunction renderMoved() {", 1), encoding="utf-8")
        proc = self._run_in("node", "tests/site/klk138_score.node.js")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("スライスマーカー", proc.stderr)

    def test_write_baseline_refuses_past_version(self):
        """KLK-140 AC6: --write-baseline --label v1.2 は終了コード 1 で、baseline-v1.2.json を書き換えない。"""
        p = self.root / "tests" / "fixtures" / "klk138" / "baseline-v1.2.json"
        before = p.read_bytes()
        proc = self._run_in("node", "tests/site/klk138_score.node.js", "--write-baseline", "--label", "v1.2")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertEqual(p.read_bytes(), before)

    def test_write_baseline_requires_label(self):
        """KLK-140 AC6: --write-baseline にラベルが無ければ終了コード 2（何も書かない）。"""
        fix = self.root / "tests" / "fixtures" / "klk138"
        before = sorted(f.name for f in fix.iterdir())
        proc = self._run_in("node", "tests/site/klk138_score.node.js", "--write-baseline")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(sorted(f.name for f in fix.iterdir()), before)


@unittest.skipUnless(shutil.which("node"), "node が見つからないため skip")
class TestKLK138Fingerprint(unittest.TestCase):
    """KLK-140 R-5: check_klk138.py --fingerprint と klk138_generator.js の指紋が一致すること。"""

    def test_fingerprint_python_matches_node(self):
        py = _run(["python3", str(STATIC_CHECKER), "--fingerprint"])
        self.assertEqual(py.returncode, 0, py.stdout + py.stderr)
        gen = ROOT / "tests" / "site" / "klk138_generator.js"
        js = _run(["node", "-e", "console.log(require(process.argv[1]).load().fingerprint)", str(gen)])
        self.assertEqual(js.returncode, 0, js.stdout + js.stderr)
        self.assertRegex(py.stdout.strip(), r"^[0-9a-f]{16}$")
        self.assertEqual(py.stdout.strip(), js.stdout.strip())


if __name__ == "__main__":
    unittest.main()
