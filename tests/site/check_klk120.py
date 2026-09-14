#!/usr/bin/env python3
"""
KLK-120 acceptance-condition checker — 登録済みカタログエントリの編集。

★経緯（2026-09-14・理恵さんの要望）
  「登録後のラフの情報を編集することは可能でしょうか。可能であれば、実装後に当方で
    ホワイト/ブラック（背景トーン）の付与を行いたい」
  取り込み時にしかタグを直せず、登録後は**削除して入れ直す**か `catalog.json` の手編集しか
  なかった。手編集は書き間違えると画面がカタログを丸ごと空として扱う（読み込み時検証）ので危険。
  → 全項目を画面から直せるようにした（A案の簡易版ではなく B案）。

★この checker が守っているもの
  S. サーバ: 純関数の検証（編集してよい項目の allowlist・身元項目の保護）と
     エンドポイントが削除と同じ安全手順を踏むこと
  P. 純関数 apply_entry_updates が元データを壊さず、null でキーを消せること
  U. 画面: ✏ ボタン・モーダル・**差分だけ送る**・保存後の即時反映・注入対策
  T. 妨害注入: id/file/addedAt の変更、未知キー、語彙外を弾く

  実効果（実ブリッジ＋実ブラウザで catalog.json が書き換わること）は
  tests/site/e2e_klk120.node.js が**サンドボックス**で確かめる（実カタログには触らない）。

Run: python3 tests/site/check_klk120.py
"""
import importlib.util
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_SRC = io.open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
CAT = io.open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()
E2E = io.open(os.path.join(ROOT, "tests", "site", "e2e_klk120.node.js"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "bridge_klk120", os.path.join(ROOT, "draft-gen", "bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


b = load_bridge()

# ---------------------------------------------------------------------------
# S. サーバ
# ---------------------------------------------------------------------------
check("S1 編集してよい項目が allowlist で決まっている",
      set(b.EDITABLE_ENTRY_FIELDS) == {"title", "industry", "taste", "colors", "bgTone",
                                       "columns", "note", "source", "tags", "sectionLayouts"},
      "%s" % sorted(b.EDITABLE_ENTRY_FIELDS))

check("S2 身元・来歴の項目は変更できない（id / file / addedAt）",
      set(b.PROTECTED_ENTRY_FIELDS) == {"id", "file", "addedAt"}
      and not (set(b.PROTECTED_ENTRY_FIELDS) & set(b.EDITABLE_ENTRY_FIELDS)),
      "%s" % sorted(b.PROTECTED_ENTRY_FIELDS))

check("S3 POST /catalog-update のルートがある",
      'if path == "/catalog-update":' in BRIDGE_SRC and "def _catalog_update" in BRIDGE_SRC,
      "ルート=%s ハンドラ=%s" % ('if path == "/catalog-update":' in BRIDGE_SRC,
                                "def _catalog_update" in BRIDGE_SRC))

seg = BRIDGE_SRC[BRIDGE_SRC.index("def _catalog_update"):BRIDGE_SRC.index("def _catalog_delete")]
for label, needle in (
    ("Origin 検証", "is_allowed_origin(self.headers.get(\"Origin\")"),
    ("サイズ上限", "MAX_BODY_BYTES"),
    ("入力検証", "validate_update_request(obj)"),
    ("実在確認", "見つからない項目があります"),
    ("更新後の全体検証", "validate_catalog(merged)"),
    ("原子的置換", "os.replace(tmp, catalog_json_path)"),
):
    check("S4 ハンドラが %s を行う（削除と同じ安全手順）" % label, needle in seg,
          "%s=%s" % (label, needle in seg))

check("S5 検証に失敗したら1件も書き換えない",
      "1件も書き換えていません" in seg, "明記=%s" % ("1件も書き換えていません" in seg))

check("S6 画像には触らない（更新は catalog.json のタグ項目だけ）",
      "shutil.move" not in seg and "catalog_img_dir" not in seg,
      "画像操作=%s" % ("shutil.move" in seg or "catalog_img_dir" in seg))

# ---------------------------------------------------------------------------
# P. 純関数
# ---------------------------------------------------------------------------
src_entries = [{"id": "a", "taste": "高級感", "note": "n", "tags": ["x"]}, {"id": "b"}]
out = b.apply_entry_updates(src_entries, [{"id": "a", "fields": {"bgTone": "ライト", "note": None}}])
check("P1 apply_entry_updates が元の一覧を書き換えない（検証に失敗したら戻せる）",
      src_entries == [{"id": "a", "taste": "高級感", "note": "n", "tags": ["x"]}, {"id": "b"}],
      "元=%s" % src_entries)
check("P2 値を当て、None はキーごと消す（未設定に戻せる）",
      out[0].get("bgTone") == "ライト" and "note" not in out[0] and out[0].get("tags") == ["x"],
      "結果=%s" % out[0])
check("P3 対象外のエントリはそのまま", out[1] == {"id": "b"}, "%s" % out[1])

mk = lambda f: {"updates": [{"id": "cat-0001", "fields": f}]}
check("P4 正常な編集指示を受理", b.validate_update_request(mk({"bgTone": "ダーク"}))[0], "")
check("P5 fields が空なら拒否（何も変えない指示を通さない）",
      not b.validate_update_request(mk({}))[0], "")
check("P6 updates が空なら拒否", not b.validate_update_request({"updates": []})[0], "")

dup = {"updates": [{"id": "cat-0001", "fields": {"note": "a"}},
                   {"id": "cat-0001", "fields": {"note": "b"}}]}
check("P7 同じ id を2回指定したら拒否（どちらが効くか曖昧にしない）",
      not b.validate_update_request(dup)[0], "%s" % b.validate_update_request(dup)[1][:1])

# ---------------------------------------------------------------------------
# T. 妨害注入
# ---------------------------------------------------------------------------
for key in b.PROTECTED_ENTRY_FIELDS:
    ok, errs = b.validate_update_request(mk({key: "x"}))
    assert not ok, "妨害注入が効いていない（%s の変更が通った）" % key
    check("T1 妨害注入: %s の変更を拒否" % key,
          not ok and any(key in e for e in errs), "%s" % errs[:1])

ok, errs = b.validate_update_request(mk({"zzz": 1}))
assert not ok, "妨害注入が効いていない（未知キーが通った）"
check("T2 妨害注入: 未知の項目を拒否", not ok and any("未知" in e for e in errs), "%s" % errs[:1])

ok, errs = b.validate_update_request(mk({"bgTone": "グレー"}))
check("T3 妨害注入: 語彙外の値を拒否（取り込みと同じ関数で見る）",
      not ok and any("bgTone" in e for e in errs), "%s" % errs[:1])

ok, _ = b.validate_update_request(mk({"colors": []}))
check("T4 主配色の空配列は編集指示の時点で拒否",
      not ok, "受理=%s" % ok)

ok, errs = b.validate_update_request(mk({"tags": ["a", 1]}))
check("T5 tags は文字列の配列のみ", not ok and any("tags" in e for e in errs), "%s" % errs[:1])

check("T6 id にパストラバーサルを入れたら拒否",
      not b.validate_update_request({"updates": [{"id": "../x", "fields": {"note": "a"}}]})[0], "")

# ---------------------------------------------------------------------------
# U. 画面
# ---------------------------------------------------------------------------
check("U1 カードに ✏ ボタンがある（削除の隣）",
      'class="edit" data-edit-id=' in CAT and "登録内容を編集" in CAT,
      "ボタン=%s" % ('class="edit" data-edit-id=' in CAT))

check("U2 編集モーダルがあり、全項目を出す",
      all(x in CAT for x in ('id="editModalBack"', 'id="editTitle"', 'id="editIndustry"',
                             'id="editTaste"', 'id="editColumns"', 'id="editNote"',
                             'id="editColors"', 'id="editBgTone"', 'id="editSource"')),
      "欠け=%s" % [x for x in ('id="editTitle"', 'id="editColors"', 'id="editBgTone"') if x not in CAT])

check("U3 ★差分だけ送る（触っていない項目を巻き添えで消さない）",
      "function collectEditDiff" in CAT and "updates: [{ id: editing.id, fields: diff }]" in CAT,
      "差分関数=%s" % ("function collectEditDiff" in CAT))

check("U4 ★保存後に手元のデータへも即時反映する（開き直しで古い値と比べない）",
      "function applyDiffLocally" in CAT and "applyDiffLocally(editing.id, diff)" in CAT,
      "即時反映=%s" % ("function applyDiffLocally" in CAT))

check("U5 「（未設定）」を選ぶと null を送る（キーごと消す）",
      re.search(r"out\.bgTone = bg === \"\" \? null : bg", CAT) is not None,
      "null 送出=%s" % (re.search(r"\? null : bg", CAT) is not None))

check("U6 主配色が空のまま保存させない（サーバ拒否の前に画面で止める）",
      "主配色は1つ以上選んでください" in CAT, "")

check("U7 注入対策: 選択肢は textContent で作る（innerHTML に値を混ぜない）",
      "o.textContent = v;" in CAT and "lab.appendChild(document.createTextNode" in CAT,
      "textContent=%s" % ("o.textContent = v;" in CAT))

check("U8 ブリッジ未起動なら保存できないと伝える（黙って失敗しない）",
      "ローカルブリッジが動いていないため保存できません" in CAT, "")

check("U9 画像・id は変えないこと、タグの扱いが画面に明記されている",
      "画像は変更しません" in CAT and "タグ" in CAT, "")

# ---------------------------------------------------------------------------
# G. 導出タグの同期（KLK-121・実ユーザーの指摘）
# ---------------------------------------------------------------------------
old_e = {"id": "a", "taste": "高級感", "colors": ["ブルー"], "columns": "1col",
         "tags": ["ジュエリー", "CADスクール", "高級感", "ブルー", "1カラム"]}
new_e = dict(old_e, colors=["ネイビー"])
synced = b.sync_derived_tags(old_e, new_e)
check("G1 ★主配色を変えると、タグの色も入れ替わる",
      "ネイビー" in synced and "ブルー" not in synced, "%s" % synced)
check("G2 ★手で書いたタグ（業種の略称・自由語）は残る",
      "ジュエリー" in synced and "CADスクール" in synced, "%s" % synced)
check("G3 変わっていない導出値はそのまま（重複しない）",
      synced.count("高級感") == 1 and synced.count("1カラム") == 1, "%s" % synced)

untouched = b.sync_derived_tags(old_e, dict(old_e, bgTone="ダーク"))
check("G4 ★無関係な項目だけ直したときはタグを変えない（勝手に足さない）",
      untouched == old_e["tags"], "%s" % untouched)

check("G5 タグが空のエントリは空のまま（画面の既定表示を壊さない）",
      b.sync_derived_tags({"colors": ["ブルー"]}, {"colors": ["ネイビー"], "tags": []}) == [],
      "")

check("G6 カラム構成のタグ表記が実データと合っている",
      b.columns_tag_label("1col") == "1カラム" and b.columns_tag_label("2col-body-left") == "2カラム"
      and b.columns_tag_label("3col") == "3カラム" and b.columns_tag_label("") is None,
      "1col=%s 2col-body-left=%s" % (b.columns_tag_label("1col"), b.columns_tag_label("2col-body-left")))

check("G7 業種は導出タグに含めない（実データで略称が使われ対応が取れないため）",
      "ジュエリー・時計・貴金属" not in b.derived_tag_values(
          {"industry": "ジュエリー・時計・貴金属", "taste": "高級感"}),
      "%s" % b.derived_tag_values({"industry": "ジュエリー・時計・貴金属", "taste": "高級感"}))

check("G8 保存後に一覧を描き直す（loadCatalog の結果を捨てない）",
      "loadCatalog().then(function (entries) {" in CAT
      and CAT.count("allEntries = entries; updateHeadCount(); renderGrid();") >= 2,
      "描き直し=%d箇所" % CAT.count("allEntries = entries; updateHeadCount(); renderGrid();"))

check("G9 ハンドラが導出タグの同期を通す",
      "sync_derived_tags(old_by_id.get" in BRIDGE_SRC, "")

# ---------------------------------------------------------------------------
# E. 実効果テストの安全性
# ---------------------------------------------------------------------------
check("Z1 実効果テストがサンドボックスで動く（実カタログに触れない）",
      "mkdtempSync" in E2E and "SANDBOX_CATALOG" in E2E
      and "サンドボックスのカタログが配信されていない" in E2E,
      "サンドボックス=%s 取り違え検知=%s" % ("SANDBOX_CATALOG" in E2E,
                                            "サンドボックスのカタログが配信されていない" in E2E))

print("=" * 78)
print("KLK-120 登録済みカタログエントリの編集 チェック")
print("=" * 78)
failed = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print("[%s] %s" % (status, name))
    print("        %s" % detail)
print("-" * 78)
print("%d checks, %d failed" % (len(results), failed))
sys.exit(1 if failed else 0)
