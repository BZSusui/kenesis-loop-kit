# KLK-076 見本の実物検証チェッカーを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk076.py（R1-R7 = 規約テキスト / S0-S8 = samples の実物）
# - 追加: **同梱した見本と、その instruction.json が食い違っていないこと**を検査する。
#   見本は生成後に mockups/ から samples/ へ手でコピーし data-folder を書き換えている。
#   コピー元を取り違えたり、片方だけ差し替えたりすると「指定と見た目が合わない見本」を
#   配ることになる（見本は「どう指定するとこうなるか」の参考として同梱している）。
import glob
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk076.py"
SAMPLES = ROOT / "samples"


class TestKLK076Static(unittest.TestCase):
    """check_klk076.py（規約テキスト＋samples の実物）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk076.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK076SamplesMatchInstruction(unittest.TestCase):
    """同梱の見本 HTML が、隣の instruction.json の指定どおりであること。"""

    def _dirs(self):
        return sorted(d for d in SAMPLES.glob("*") if d.is_dir())

    def test_columns_and_nav_position_match(self):
        mismatches = []
        checked = 0
        for d in self._dirs():
            ins = d / "instruction.json"
            if not ins.exists():
                mismatches.append("%s: instruction.json が無い" % d.name)
                continue
            layout = json.loads(ins.read_text(encoding="utf-8")).get("layout") or {}
            want_cols = layout.get("columns")
            want_nav = layout.get("navPosition")
            for p in sorted(d.glob("index-*.html")):
                html = p.read_text(encoding="utf-8")
                got_cols = re.search(r'data-columns=["\']?([a-z0-9-]+)', html)
                got_nav = re.search(r'data-nav-position=["\']?([a-z0-9-]+)', html)
                checked += 1
                if want_cols and (not got_cols or got_cols.group(1) != want_cols):
                    mismatches.append(
                        "%s/%s: columns 指定=%s 実物=%s"
                        % (d.name, p.name, want_cols, got_cols and got_cols.group(1))
                    )
                if want_nav and (not got_nav or got_nav.group(1) != want_nav):
                    mismatches.append(
                        "%s/%s: navPosition 指定=%s 実物=%s"
                        % (d.name, p.name, want_nav, got_nav and got_nav.group(1))
                    )
        self.assertTrue(checked >= 9, "見本の index が足りない（%d件）" % checked)
        self.assertFalse(mismatches, "見本と instruction.json が食い違う:\n" + "\n".join(mismatches))

    def test_main_color_matches_instruction(self):
        """instruction.json の colors.main が見本の --m-main に焼き込まれていること。

        案A/B/Cで --m-main は相違する（§12.1 不変条件）ので、
        「3案のいずれかが指定色と一致する」ことを要求する。
        どれとも一致しないなら、別案件のフォルダを取り違えている。
        """
        mismatches = []
        for d in self._dirs():
            ins = d / "instruction.json"
            if not ins.exists():
                continue
            want = ((json.loads(ins.read_text(encoding="utf-8")).get("colors") or {})
                    .get("main") or "").lower()
            if not want:
                continue
            found = []
            for p in sorted(d.glob("index-*.html")):
                m = re.search(r"--m-main\s*:\s*([^;]+)", p.read_text(encoding="utf-8"))
                if m:
                    found.append(m.group(1).strip().lower())
            if want not in found:
                mismatches.append("%s: 指定=%s 実物=%s" % (d.name, want, found))
        self.assertFalse(
            mismatches,
            "instruction.json の主配色が見本のどの案にも入っていない（フォルダ取り違えの疑い）:\n"
            + "\n".join(mismatches),
        )


if __name__ == "__main__":
    unittest.main()
