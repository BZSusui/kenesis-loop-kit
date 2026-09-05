# KLK-097 MV の SCROLL 誘導とボタンの重なり解消を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的＋実測: tests/site/check_klk097.py（C1-C24）
# - 追加: 規約・構造の正・検査の3者が**同じ数値**を言っていることを確かめる。
#   KLK-097 の原因は「§3.0 が『画面を覆う』とだけ書き、数値が構造の正の 340px に
#   引きずられていた」こと。数値が3箇所でズレたら同じ乖離が再発する。
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk097.py"
RULES = ROOT / ".claude" / "skills" / "draft-generate" / "templates" / "DRAFT_RULES.md"
BRIDGE = ROOT / "draft-gen" / "bridge.py"


class TestKLK097Static(unittest.TestCase):
    """check_klk097.py（規約・構造の正・bridge の検出・生成物の実測）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk097.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK097NumbersAgree(unittest.TestCase):
    """帯の幅 64px が、規約と検査で一致していること。

    片方だけ変えると「規約は 80px を要求しているのに検査は 64px で通す」という
    静かな不一致が生まれ、規約が実効性を失う（KLK-074/075 で繰り返した失敗）。
    """

    def test_reserved_strip_width_is_consistent(self):
        rules = RULES.read_text(encoding="utf-8")
        bridge = BRIDGE.read_text(encoding="utf-8")
        seg = rules[rules.find("#### 4.3.2"):rules.find("#### 4.3.3")]
        self.assertIn("padding-inline:64px", seg.replace(" ", ""),
                      "§4.3.2 が帯の幅を 64px と書いていない")
        self.assertRegex(bridge, r"hero_pads\[-1\]\[1\]\s*<\s*64",
                         "bridge の検査が 64px を境にしていない（規約と不一致）")
        self.assertIn("hero_pads", bridge,
                      "bridge の padding 検査がカスケード後の値を見ていない"
                      "（1ルールずつ独立に見ると誤報になる）")

    def test_cue_is_never_recentred(self):
        """規約が中央寄せの2つの書き方（left:50% と translateX）を**両方**禁じていること。

        片方だけ禁じても、もう片方で同じ重なりが再現する。
        """
        rules = RULES.read_text(encoding="utf-8")
        seg = rules[rules.find("#### 4.3.2"):rules.find("#### 4.3.3")]
        self.assertIn("left:50%", seg.replace(" ", ""))
        self.assertIn("translateX(-50%)", seg)


class TestKLK097DoesNotBreakClickability(unittest.TestCase):
    """§4.3.1（押せること）が §4.3.2 の見た目変更で失われていないこと。"""

    def test_431_still_requires_anchor(self):
        rules = RULES.read_text(encoding="utf-8")
        seg = rules[rules.find("#### 4.3.1"):rules.find("#### 4.3.2")]
        self.assertIn("同一ページ内アンカー", seg)
        self.assertIn("JS は使わない", seg)


if __name__ == "__main__":
    unittest.main()
