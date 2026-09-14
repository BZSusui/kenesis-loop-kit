# KLK-120 登録済みカタログエントリの編集（tester所有）。
#
# ★経緯: 理恵さんの要望（2026-09-14）
#   「登録後のラフの情報を編集することは可能でしょうか。可能であれば、実装後に当方で
#     ホワイト/ブラック（背景トーン）の付与を行いたい」
#   取り込み時にしか直せず、登録後は削除して入れ直すか catalog.json の手編集しかなかった。
#   手編集は書き間違えると画面がカタログを丸ごと空として扱う（読み込み時検証）ので危険。
#
# ★このテストが守っているもの:
#   1. 静的 check_klk120.py … allowlist・安全手順・画面の作り・妨害注入
#   2. ここ … 純関数を直接突く（元データを壊さない・null で消す・差分の意味）
#   3. 実効果 e2e_klk120.node.js … 実ブリッジ＋実ブラウザで catalog.json が書き換わること。
#      ★**サンドボックス**で動く。社外秘の実カタログ(167件)には触れない
import importlib.util
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tests" / "site" / "check_klk120.py"
E2E = ROOT / "tests" / "site" / "e2e_klk120.node.js"

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
)


def chrome_path():
    for c in CHROME_CANDIDATES:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def load_bridge():
    spec = importlib.util.spec_from_file_location("bridge_klk120_t", ROOT / "draft-gen" / "bridge.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKLK120Static(unittest.TestCase):
    def test_static_checker_passes(self):
        p = subprocess.run(["python3", str(STATIC)], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, "check_klk120.py 失敗:\n%s" % p.stdout[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("U3 ★差分だけ送る", p.stdout)


class TestApplyEntryUpdates(unittest.TestCase):
    """適用の純関数。元を壊さないこと・null で消せることが肝。"""

    @classmethod
    def setUpClass(cls):
        cls.b = load_bridge()

    def test_does_not_mutate_input(self):
        src = [{"id": "a", "note": "n", "tags": ["x"]}]
        snapshot = json.loads(json.dumps(src))
        self.b.apply_entry_updates(src, [{"id": "a", "fields": {"note": "m"}}])
        self.assertEqual(src, snapshot, "元の一覧を書き換えている（検証失敗時に戻せない）")

    def test_sets_and_deletes(self):
        out = self.b.apply_entry_updates(
            [{"id": "a", "note": "n", "taste": "高級感"}],
            [{"id": "a", "fields": {"bgTone": "ライト", "note": None}}])
        self.assertEqual(out[0].get("bgTone"), "ライト")
        self.assertNotIn("note", out[0], "None でキーが消えていない")
        self.assertEqual(out[0].get("taste"), "高級感", "触っていない項目が消えた")

    def test_untouched_entries_are_identical(self):
        other = {"id": "b", "note": "keep"}
        out = self.b.apply_entry_updates([{"id": "a"}, other], [{"id": "a", "fields": {"note": "x"}}])
        self.assertEqual(out[1], other)

    def test_unknown_id_is_ignored(self):
        src = [{"id": "a"}]
        out = self.b.apply_entry_updates(src, [{"id": "zzz", "fields": {"note": "x"}}])
        self.assertEqual(out, src)


class TestValidateUpdateRequest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load_bridge()

    def _mk(self, fields, eid="cat-0001"):
        return {"updates": [{"id": eid, "fields": fields}]}

    def test_accepts_editable_fields(self):
        for f in ({"title": "x"}, {"taste": "高級感"}, {"colors": ["ブルー"]},
                  {"bgTone": "ダーク"}, {"note": "m"}, {"source": "ref"},
                  {"tags": ["a", "b"]}, {"columns": "1col"},
                  {"sectionLayouts": {"HERO": "split"}}):
            with self.subTest(f=f):
                ok, errs = self.b.validate_update_request(self._mk(f))
                self.assertTrue(ok, "%s が拒否された: %s" % (f, errs))

    def test_rejects_protected_fields(self):
        for key in self.b.PROTECTED_ENTRY_FIELDS:
            with self.subTest(key=key):
                ok, errs = self.b.validate_update_request(self._mk({key: "x"}))
                self.assertFalse(ok, "%s の変更が通った" % key)
                self.assertTrue(any(key in e for e in errs), errs)

    def test_rejects_unknown_field(self):
        ok, errs = self.b.validate_update_request(self._mk({"__proto__": "x"}))
        self.assertFalse(ok, "未知キーが通った")

    def test_rejects_empty_and_malformed(self):
        for bad in ({}, {"updates": []}, {"updates": [{"id": "cat-0001"}]},
                    {"updates": [{"id": "cat-0001", "fields": {}}]},
                    {"updates": [{"id": "../x", "fields": {"note": "a"}}]},
                    {"updates": "x"}, "x"):
            with self.subTest(bad=bad):
                self.assertFalse(self.b.validate_update_request(bad)[0], "%r が通った" % (bad,))

    def test_rejects_duplicate_ids(self):
        req = {"updates": [{"id": "cat-0001", "fields": {"note": "a"}},
                           {"id": "cat-0001", "fields": {"note": "b"}}]}
        self.assertFalse(self.b.validate_update_request(req)[0])

    def test_vocabulary_shared_with_import(self):
        # 語彙の検証は取り込みと同じ関数を使う＝二重に書かない
        self.assertFalse(self.b.validate_update_request(self._mk({"bgTone": "グレー"}))[0])
        self.assertFalse(self.b.validate_update_request(self._mk({"colors": ["未知色"]}))[0])
        self.assertFalse(self.b.validate_update_request(self._mk({"source": "xxx"}))[0])
        # カラフルの単独指定も引き継がれる
        self.assertFalse(self.b.validate_update_request(self._mk({"colors": ["カラフル", "ブルー"]}))[0])


class TestSyncDerivedTags(unittest.TestCase):
    """KLK-121: 導出タグ（テイスト/主配色/カラム構成）が編集に追随すること。

    実ユーザーの指摘（2026-09-14）:
      「カラーを変更しても、カタログ一覧のタグが編集前のままで反映されない」
    """

    @classmethod
    def setUpClass(cls):
        cls.b = load_bridge()

    def _old(self):
        return {"id": "a", "taste": "高級感", "colors": ["ブルー"], "columns": "1col",
                "tags": ["ジュエリー", "CADスクール", "高級感", "ブルー", "1カラム"]}

    def test_color_change_swaps_tag(self):
        o = self._old()
        out = self.b.sync_derived_tags(o, dict(o, colors=["ネイビー"]))
        self.assertIn("ネイビー", out)
        self.assertNotIn("ブルー", out)

    def test_handwritten_tags_survive(self):
        o = self._old()
        out = self.b.sync_derived_tags(o, dict(o, colors=["ネイビー"]))
        self.assertIn("ジュエリー", out, "業種の略称が消えた")
        self.assertIn("CADスクール", out, "手で書いたタグが消えた")

    def test_unrelated_change_leaves_tags_alone(self):
        # 背景トーンだけ直したのに色タグが増える、といったことが起きない
        o = self._old()
        self.assertEqual(self.b.sync_derived_tags(o, dict(o, bgTone="ダーク")), o["tags"])

    def test_taste_and_columns_follow(self):
        o = self._old()
        out = self.b.sync_derived_tags(o, dict(o, taste="シンプル", columns="2col-full-left"))
        self.assertIn("シンプル", out)
        self.assertNotIn("高級感", out)
        self.assertIn("2カラム", out)
        self.assertNotIn("1カラム", out)

    def test_adding_a_color_appends(self):
        o = self._old()
        out = self.b.sync_derived_tags(o, dict(o, colors=["ブルー", "ゴールド"]))
        self.assertIn("ブルー", out)
        self.assertIn("ゴールド", out)

    def test_empty_tags_stay_empty(self):
        # tags が空なら画面は industry/taste/colors から作って出す。中途半端に入れない
        self.assertEqual(
            self.b.sync_derived_tags({"colors": ["ブルー"]}, {"colors": ["ネイビー"], "tags": []}), [])
        self.assertEqual(
            self.b.sync_derived_tags({"colors": ["ブルー"]}, {"colors": ["ネイビー"]}), [])

    def test_no_duplicates(self):
        o = self._old()
        out = self.b.sync_derived_tags(o, dict(o, colors=["ブルー"]))
        self.assertEqual(len(out), len(set(out)), "重複が生まれた: %s" % out)

    def test_industry_is_not_derived(self):
        # 実データでは業種が略称でタグに入る（53件中21件しか一致しない）。
        # 推測で消すと手書きタグを壊すので、導出値に含めない
        vals = self.b.derived_tag_values({"industry": "ジュエリー・時計・貴金属", "taste": "高級感"})
        self.assertNotIn("ジュエリー・時計・貴金属", vals)
        self.assertIn("高級感", vals)

    def test_columns_label(self):
        for col, want in (("1col", "1カラム"), ("2col-body-left", "2カラム"),
                          ("2col-full-right", "2カラム"), ("3col", "3カラム")):
            with self.subTest(col=col):
                self.assertEqual(self.b.columns_tag_label(col), want)
        for bad in ("", None, "xcol", 1):
            with self.subTest(bad=bad):
                self.assertIsNone(self.b.columns_tag_label(bad))


class TestKLK120E2E(unittest.TestCase):
    """★実効果: 実ブリッジ＋実ブラウザ。サンドボックスなので実カタログは無傷。"""

    def test_edit_reaches_catalog_json(self):
        if not shutil.which("node"):
            self.skipTest("node が無い環境")
        if not chrome_path():
            self.skipTest("ヘッドレス Chrome が無い環境")
        real = ROOT / "catalog" / "catalog.json"
        before = real.read_bytes() if real.is_file() else None
        env = dict(os.environ, KLK_E2E_CHROME=chrome_path())
        p = subprocess.run(["node", str(E2E)], capture_output=True, text=True,
                           timeout=600, env=env, cwd=str(ROOT))
        if p.returncode == 3:
            self.skipTest("e2e が環境理由で SKIP: %s" % (p.stdout + p.stderr)[-300:])
        self.assertEqual(p.returncode, 0, "e2e_klk120.node.js 失敗:\n%s" % (p.stdout + p.stderr)[-3000:])
        self.assertIn(", 0 failed", p.stdout)
        self.assertIn("E4 ★保存が成功し、catalog.json に実際に書かれる", p.stdout)
        self.assertIn("E9 ★主配色を変えるとタグも入れ替わり", p.stdout)
        # ★実カタログを触っていないことを、テスト側でも確かめる
        if before is not None:
            self.assertEqual(real.read_bytes(), before,
                             "実カタログ(社外秘)が書き換わった。サンドボックスが効いていない")


if __name__ == "__main__":
    unittest.main()
