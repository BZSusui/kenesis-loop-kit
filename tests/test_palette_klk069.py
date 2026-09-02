# KLK-069 README とローカル配布パッケージを unittest スイートへ束ねるラッパー（tester所有）。
# - 静的+実行: tests/site/check_klk069.py（R1-R12。スクリプトを実際に実行して出力を検証する）
# - 追加: README が「できないこと」として挙げた4点が、**実装の現実と一致している**こと。
#   機能を実装したのに README が「できません」と言い続ける退行を検出する。
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk069.py"


class TestKLK069Static(unittest.TestCase):
    """check_klk069.py（README と配布スクリプトのチェック）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=300,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk069.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK069ReadmeMatchesReality(unittest.TestCase):
    """README の「できないこと」が実装の現実と一致していること。

    実装したのに README が「できません」と言い続けるのは、KLK-061 で潰した
    「画面と実装の食い違い」が README 側で再発した状態にあたる。
    """

    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_sample_url_still_unimplemented(self):
        """見本サイトURLが未反映のままか（実装したら README を直す合図）。"""
        skill = (ROOT / ".claude" / "skills" / "draft-generate" / "SKILL.md").read_text(encoding="utf-8")
        rules = (ROOT / ".claude" / "skills" / "draft-generate" / "templates" / "DRAFT_RULES.md").read_text(encoding="utf-8")
        implemented = ("sampleUrls" in skill) or ("sampleUrls" in rules)
        self.assertFalse(
            implemented,
            "見本サイトURLが生成へ反映される実装が入った。README の「できないこと」を更新すること",
        )
        self.assertIn("反映されません", self.readme)

    def test_history_screen_still_unimplemented(self):
        """履歴画面が未実装のままか。"""
        self.assertFalse(
            (ROOT / "draft-gen" / "history.html").exists(),
            "履歴画面が実装された。README の「できないこと」を更新すること",
        )

    def test_webp_conversion_is_macos_only(self):
        """webp 変換が sips（macOS 専用）のままか。"""
        skill = (ROOT / ".claude" / "skills" / "catalog-import" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("sips", skill, "webp 変換の実装が変わった。README の macOS 限定の記述を見直すこと")
        self.assertIn("macOS", self.readme)


if __name__ == "__main__":
    unittest.main()
