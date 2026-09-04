# KLK-087 ページ構成（composition）を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk087.py（R群=設計 / L群=純ロジック / V群=語彙 / U群=UI / D群=正直さ）
# - 動的: tests/site/smoke_klk087.node.js（P群=後方互換 / E群=出力 / N群=正規化 / U群=UI実挙動）
# - 追加: **既存の見本 instruction.json が今のコードでも同じ形で読めること**を確かめる。
#   composition は additive なので、過去の指示書が壊れないことがこの機能の生命線。
import glob
import json
import shutil as _shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk087.py"
DYNAMIC_SMOKE = ROOT / "tests" / "site" / "smoke_klk087.node.js"


class TestKLK087Static(unittest.TestCase):
    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0, "check_klk087.py failed:\n" + proc.stdout + proc.stderr
        )


@unittest.skipUnless(_shutil.which("node"), "node が見つからないため動的スモークをskip")
class TestKLK087Smoke(unittest.TestCase):
    """buildInstruction と構成リスト UI を実際に動かす（後方互換の一致を含む）。"""

    def test_dynamic_smoke_passes(self):
        proc = subprocess.run(
            ["node", str(DYNAMIC_SMOKE)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0, "smoke_klk087.node.js failed:\n" + proc.stdout + proc.stderr
        )


class TestKLK087ExistingInstructionsUnaffected(unittest.TestCase):
    """★既存の指示書（見本に同梱されているもの）が composition 抜きのままであること。

    composition は additive なので、過去の指示書には無いのが正しい。
    ここに composition が現れたら、それは誰かが見本を作り直したということ＝
    見本の作り直しは KLK-089 以降の話なので、意図しない変更を検出できる。
    """

    def test_sample_instructions_have_no_composition(self):
        found = []
        checked = 0
        for p in sorted(glob.glob(str(ROOT / "samples" / "*" / "instruction.json"))):
            data = json.loads(Path(p).read_text(encoding="utf-8"))
            checked += 1
            if "composition" in data:
                found.append(Path(p).parent.name)
            # 既存指示書が持つべきキーは従来どおり
            self.assertIn("sections", data, p)
            self.assertIsInstance(data["sections"], list, p)
        self.assertGreaterEqual(checked, 3, "見本の instruction.json が足りない")
        self.assertFalse(found, "既存の見本に composition が入っている（意図しない作り直し）: %s" % found)

    def test_sections_vocabulary_is_unchanged(self):
        """見本の sections が語彙内であること（語彙を壊していない）。"""
        import re
        index = (ROOT / "draft-gen" / "index.html").read_text(encoding="utf-8")
        m = re.search(r"const SECTION_KEYS\s*=\s*\[(.*?)\];", index, re.S)
        self.assertIsNotNone(m)
        keys = set(re.findall(r"'([A-Z]+)'", m.group(1)))
        self.assertEqual(len(keys), 14, "SECTION_KEYS が14種でない: %s" % sorted(keys))
        for p in sorted(glob.glob(str(ROOT / "samples" / "*" / "instruction.json"))):
            data = json.loads(Path(p).read_text(encoding="utf-8"))
            unknown = [k for k in data.get("sections", []) if k not in keys]
            self.assertFalse(unknown, "%s に語彙外のセクション: %s" % (p, unknown))


if __name__ == "__main__":
    unittest.main()
