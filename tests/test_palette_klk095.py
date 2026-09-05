# KLK-095 ブリッジのタイムアウト延長（900→1800秒）を unittest スイートへ束ねる（tester所有）。
#
# ★なぜテストにするか:
#   900秒は「正常な生成」と「異常な停止」を分ける線として短すぎた。
#   実測の最長は 847秒（出荷した見本02 を作ったときの値）で、上限の94%。
#   ここを誰かが「短くしたほうが速く気づける」と考えて戻すと、
#   **正常な生成が失敗扱いになる**という、原因の分かりにくい不具合が復活する。
#   実測値を根拠として残し、下限を割ったら落ちるようにしておく。
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_PATH = ROOT / "draft-gen" / "bridge.py"
SPEC = ROOT / "docs" / "SPEC.md"

# 実測（2026-09-05・3案生成）。この値を超える余裕が要る。
OBSERVED_MAX_SEC = 847


def _load_bridge():
    spec = importlib.util.spec_from_file_location("klk095_bridge", str(BRIDGE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK095Timeout(unittest.TestCase):
    def setUp(self):
        self.bridge = _load_bridge()
        self.src = BRIDGE_PATH.read_text(encoding="utf-8")

    def test_timeout_is_1800(self):
        self.assertEqual(self.bridge.BRIDGE_TIMEOUT_SEC, 1800)

    def test_timeout_has_margin_over_observed_max(self):
        """★実測の最長より十分に長いこと（正常な生成を失敗扱いにしない）。"""
        t = self.bridge.BRIDGE_TIMEOUT_SEC
        self.assertGreaterEqual(
            t, OBSERVED_MAX_SEC * 2,
            "実測の最長 %d秒 に対して余裕が足りない（現在 %d秒）。"
            "正常な生成が「タイムアウトしました」で失敗扱いになる" % (OBSERVED_MAX_SEC, t),
        )

    def test_timeout_is_still_bounded(self):
        """★上限は残すこと（0%CPU のまま34分無反応になる事象を観測済み・KLK-079）。

        無制限にすると画面が永久に「生成中…」のままになる。
        """
        t = self.bridge.BRIDGE_TIMEOUT_SEC
        self.assertIsNotNone(t)
        self.assertLessEqual(t, 3600, "上限が緩すぎる（1時間以上待たせない）")

    def test_rationale_is_recorded_in_code(self):
        """なぜこの値なのかがコードに残っていること（次に触る人が根拠なく戻さないため）。"""
        i = self.src.find("BRIDGE_TIMEOUT_SEC = ")
        head = self.src[max(0, i - 700):i]
        for needle in ("847", "34分", "KLK-095"):
            self.assertIn(needle, head, "タイムアウトの根拠に「%s」が無い" % needle)

    def test_rationale_is_recorded_in_spec(self):
        text = SPEC.read_text(encoding="utf-8")
        i = text.find("| NFR-001 |")
        row = text[i:text.find("\n", i)]
        self.assertIn("1800秒", row)
        self.assertIn("847", row, "SPEC に実測値が無い")

    def test_all_long_jobs_use_the_constant(self):
        """3つの長時間ジョブ（生成・部分再生成・カタログ取込）すべてが同じ定数を使うこと。"""
        self.assertEqual(
            self.src.count("timeout=BRIDGE_TIMEOUT_SEC"), 3,
            "長時間ジョブの一部が定数を使っていない（片方だけ短いままになる）",
        )

    def test_timeout_message_shows_the_number(self):
        """利用者に何秒で切れたかを伝えること（黙って失敗しない）。"""
        self.assertIn("生成がタイムアウトしました({0}秒)", self.src)
        self.assertIn("再生成がタイムアウトしました({0}秒)", self.src)


if __name__ == "__main__":
    unittest.main()
