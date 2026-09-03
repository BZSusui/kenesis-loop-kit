# KLK-075 横断ルールの優先明記・masonry の具体化・panel-band の全幅化を
# unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk075.py（C1-C16）
# - 追加: **型定義に極端な横長比率が書かれていないこと**を実データで検査する。
#   KLK-072 で §3.0 を足しても、型定義側の「横長」表現に負けて aspect-ratio:16/7 等が
#   生成された。規約側に極端な比率が残っていると同じことが起きるため、常時見張る。
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk075.py"
RULES = ROOT / ".claude" / "skills" / "draft-generate" / "templates" / "DRAFT_RULES.md"


class TestKLK075Static(unittest.TestCase):
    """check_klk075.py（優先関係と panel-band の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk075.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK075NoExtremeRatiosInRules(unittest.TestCase):
    """規約に極端な横長比率が書かれていないこと。

    §3.0（4/3）を足しても、型定義に 16/9 のような比率が例示されていると
    生成側はそれを根拠にしてしまう（実際に 16/6・16/7 が生成された）。
    許すのは 4/3・1/1・3/2（panel-band）だけ。
    """

    ALLOWED = {("4", "3"), ("1", "1"), ("3", "2")}

    def test_no_extreme_wide_ratios(self):
        text = RULES.read_text(encoding="utf-8")
        offenders = []
        for line in text.splitlines():
            # 「実際に生成された悪い例」を挙げている説明行は対象外（再発防止に必要）
            if "あるべき" in line or "生成された CSS" in line or "`4/3`" in line and "|" in line and "16/" in line:
                continue
            if "16/7" in line and ("map-atari" in line or "img-top" in line):
                continue  # §3.0 の悪い例テーブル
            if "16/6" in line and "pat-wide" in line:
                continue  # 同上
            for m in re.finditer(r"aspect-ratio:\s*(\d+)\s*/\s*(\d+)", line):
                pair = (m.group(1), m.group(2))
                if pair in self.ALLOWED:
                    continue
                w, h = int(pair[0]), int(pair[1])
                if w / h > 1.6:   # 3/2=1.5 までは許容。それより平たいものは禁止
                    offenders.append(line.strip()[:130])
        self.assertFalse(
            offenders,
            "規約に極端な横長比率が書かれている（生成側の根拠になる）:\n" + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
