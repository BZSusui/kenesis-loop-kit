# KLK-072 画像アタリの比率統一（4/3）を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的: tests/site/check_klk072.py（A1-A10）
# - 追加: 規約が自己矛盾していないこと。§3.0 が「4/3 を既定」と言いながら、
#   個別の型定義が理由なく別の比率を書いていたら、生成側はどちらに従うか分からなくなる。
#   例外表に載っている型だけが 4/3 以外を書いてよい、という不変条件を検査する。
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk072.py"
RULES_PATH = ROOT / ".claude" / "skills" / "draft-generate" / "templates" / "DRAFT_RULES.md"


class TestKLK072Static(unittest.TestCase):
    """check_klk072.py（比率統一の静的チェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk072.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK072NoContradictoryRatios(unittest.TestCase):
    """規約が比率について自己矛盾していないこと。

    §3.0 が「4/3 を既定」と定めたので、個別の型定義が別の比率を書いてよいのは
    **例外表に載っている型だけ**である。ここが崩れると、生成側がどちらに従えばよいか
    分からなくなり、型ごとに見え方がばらつく（KLK-072 で直した問題の再発）。
    """

    # 例外として別比率を書いてよい型（§3.0 の表と対応）
    ALLOWED_NON_43 = {"panel-band", "sns-grid", "sns-reels", "img-circle", "staff-", "map-side"}

    def test_only_listed_exceptions_use_other_ratios(self):
        text = RULES_PATH.read_text(encoding="utf-8")
        # §3.0 の節自体は説明文なので対象外にする
        i = text.find("### 3.0 アタリ枠の比率")
        j = text.find("### 3.1", i)
        body = text[:i] + text[j:] if i >= 0 and j > i else text

        offenders = []
        for line in body.splitlines():
            for m in re.finditer(r"aspect-ratio:\s*(\d+)\s*/\s*(\d+)", line):
                w, h = m.group(1), m.group(2)
                if (w, h) == ("4", "3"):
                    continue
                if (w, h) == ("1", "1") or w == h:
                    continue  # 正方は例外表の系統
                if any(k in line for k in self.ALLOWED_NON_43):
                    continue
                offenders.append(line.strip()[:120])
        self.assertFalse(
            offenders,
            "例外表に無い型が 4/3 以外の比率を指定している:\n" + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
