#!/usr/bin/env python3
"""
KLK-068 acceptance-condition checker (static + 純関数の実行 / no browser required).

Verifies D1-D13 from docs/designs/KLK-068.md §4.3 / §9:
カタログエントリの削除機能（誤登録・重複の解消）。

  縦串 ブリッジ  draft-gen/bridge.py     （validate_delete_request / POST /catalog-delete）
  縦串 SCR-004   draft-gen/catalog.html  （削除ボタン・確認モーダル）
  縦串 仕様      docs/SPEC.md            （REQ-105）

★この checker が守っているもの:
  **`catalog/` は Git 管理外（REQ-011）＝ `git revert` で戻せない。**
  登録の誤り（消せば直る）と削除の誤り（原本を失う）はリスクが非対称なので、
  画像は実削除せず `catalog/.trash/` へ退避する。D5 がこの前提を守る。

Run: python3 tests/site/check_klk068.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_SRC = open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
CATHTML = open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()
SPEC = open(os.path.join(ROOT, "docs", "SPEC.md"), encoding="utf-8").read()

sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# D1 純関数（実行して検証）
# ---------------------------------------------------------------------------
vd = getattr(bridge, "validate_delete_request", None)
if vd is None:
    check("D1 validate_delete_request が削除指示を検証する", False, "未定義")
else:
    cases = [
        ({"ids": ["cat-0054"]}, True),
        ({"ids": ["cat-0054", "cat-0055"]}, True),
        ({"ids": []}, False),
        ({"ids": "cat-0054"}, False),
        ({"ids": ["../../etc/passwd"]}, False),
        ({"ids": [".hidden"]}, False),
        ({"ids": ["a/b"]}, False),
        ({}, False),
        ("notadict", False),
    ]
    bad = [(c, w, vd(c)[0]) for c, w in cases if vd(c)[0] != w]
    check("D1 validate_delete_request が削除指示を検証する（9ケース）", not bad,
          "不一致=%s" % ([(w, g) for _, w, g in bad] if bad else "全9ケース一致"))

# ---------------------------------------------------------------------------
# D2-D8 ブリッジ
# ---------------------------------------------------------------------------
check(
    "D2 POST /catalog-delete のルーティングがある",
    'path == "/catalog-delete"' in BRIDGE_SRC and "self._catalog_delete()" in BRIDGE_SRC,
    "ルート=%s / 呼び出し=%s"
    % ('path == "/catalog-delete"' in BRIDGE_SRC, "self._catalog_delete()" in BRIDGE_SRC),
)

_i = BRIDGE_SRC.find("def _catalog_delete")
_FULL = BRIDGE_SRC[_i:BRIDGE_SRC.find("def _generate(self)")] if _i >= 0 else ""
_ds = _FULL.find('"""', _FULL.find('"""') + 3)
DBODY = _FULL[_ds + 3:] if _ds > 0 else _FULL

order = [
    ("origin", DBODY.find("is_allowed_origin(")),
    ("size", DBODY.find("> MAX_BODY_BYTES")),
    ("json", DBODY.find("json.loads(")),
    ("validate_delete_request", DBODY.find("validate_delete_request(")),
    ("404-missing", DBODY.find("self._json(404")),
    ("validate_catalog", DBODY.find("validate_catalog(merged)")),
    ("move-to-trash", DBODY.find("shutil.move(src, dst)")),
    ("os.replace", DBODY.find("os.replace(tmp")),
    ("_json(200", DBODY.find("_json(200")),
]
pos = [p for _, p in order]
check(
    "D3 処理順が Origin→サイズ→JSON→検証→実在確認→validate_catalog→退避→置換→200",
    bool(DBODY) and all(p >= 0 for p in pos) and pos == sorted(pos),
    "位置=%s" % ({k: v for k, v in order}),
)
check(
    "D4 validate_catalog を退避より前に通す（不正なら1件も消さない）",
    DBODY.find("validate_catalog(merged)") < DBODY.find("shutil.move(src, dst)")
    and "1件も削除していません" in DBODY,
    "検証が退避より前=%s / all-or-nothing の応答=%s"
    % (DBODY.find("validate_catalog(merged)") < DBODY.find("shutil.move(src, dst)"),
       "1件も削除していません" in DBODY),
)
# ★最重要: 画像を実削除していないこと（os.remove の対象は一時ファイルのみ）
removes = re.findall(r"os\.remove\(([^)]*)\)", DBODY)
check(
    "D5 画像を削除せず catalog/.trash/ へ退避する（os.remove の対象は一時ファイルのみ）",
    "catalog_trash_dir" in DBODY and all("tmp" in r for r in removes),
    "trash_dir 使用=%s / os.remove の対象=%s"
    % ("catalog_trash_dir" in DBODY, removes or "なし"),
)
check(
    "D6 書き込み失敗時にあらゆる例外で退避を巻き戻す",
    "except Exception as exc" in DBODY and "shutil.move(dst, src)" in DBODY,
    "広い例外捕捉=%s / 巻き戻し=%s"
    % ("except Exception as exc" in DBODY, "shutil.move(dst, src)" in DBODY),
)
check(
    "D7 操作対象が catalog/ 配下に限定されている（安全名＋配下確認）",
    "is_safe_catalog_name(fname)" in DBODY
    and "os.path.dirname(os.path.abspath(src)) != os.path.abspath(catalog_img_dir)" in DBODY,
    "安全名=%s / 配下確認=%s"
    % ("is_safe_catalog_name(fname)" in DBODY,
       "os.path.dirname(os.path.abspath(src)) != os.path.abspath(catalog_img_dir)" in DBODY),
)
check(
    "D8 catalog.json の書き込みが原子的（一時ファイル→os.replace）",
    "os.replace(tmp, catalog_json_path)" in DBODY,
    "os.replace=%s" % ("os.replace(tmp, catalog_json_path)" in DBODY),
)
check(
    "D8b catalog_trash_dir が catalog/ 配下に定義されている",
    'catalog_trash_dir = os.path.join(catalog_dir, ".trash")' in BRIDGE_SRC,
    "定義=%s" % ('catalog_trash_dir = os.path.join(catalog_dir, ".trash")' in BRIDGE_SRC),
)

# ---------------------------------------------------------------------------
# D9-D12 SCR-004
# ---------------------------------------------------------------------------
check(
    "D9 SCR-004 に削除ボタンと確認モーダルがある",
    'class="del" data-del-id=' in CATHTML and 'id="delModalBack"' in CATHTML
    and 'id="delConfirm"' in CATHTML,
    "ボタン=%s / モーダル=%s / 実行ボタン=%s"
    % ('class="del" data-del-id=' in CATHTML, 'id="delModalBack"' in CATHTML,
       'id="delConfirm"' in CATHTML),
)
check(
    "D10 確認モーダルが「何を消すか」（サムネ・タイトル・id）を表示する",
    'id="delTarget"' in CATHTML and "data-del-title=" in CATHTML and "data-del-src=" in CATHTML
    and "info.title" in CATHTML and "info.id" in CATHTML,
    "対象表示領域=%s / title=%s / src=%s"
    % ('id="delTarget"' in CATHTML, "data-del-title=" in CATHTML, "data-del-src=" in CATHTML),
)
check(
    "D11 確認モーダルに「.trash へ移動・自動では消えない」旨がある",
    "catalog/.trash/" in CATHTML and "自動では消えません" in CATHTML,
    "退避先=%s / 自動削除しない旨=%s"
    % ("catalog/.trash/" in CATHTML, "自動では消えません" in CATHTML),
)
check(
    "D12 SCR-004 が POST /catalog-delete を呼び、完了後に一覧を再読込する",
    '"/catalog-delete"' in CATHTML
    and re.search(r'catalog-delete[\s\S]{0,1200}loadCatalog\(\)', CATHTML) is not None,
    "エンドポイント=%s / 再読込=%s"
    % ('"/catalog-delete"' in CATHTML,
       re.search(r'catalog-delete[\s\S]{0,1200}loadCatalog\(\)', CATHTML) is not None),
)
ext = [u for u in re.findall(r'https?://[^"\'\s)]+', CATHTML) if "w3.org" not in u]
check("D12b SCR-004 に外部URL参照が無い（NFR-005）", not ext, "外部URL=%s" % (ext or "なし"))

# ---------------------------------------------------------------------------
# D13 SPEC
# ---------------------------------------------------------------------------
row = re.search(r"^\|\s*REQ-105\s*\|.*$", SPEC, re.M)
ROW = row.group(0) if row else ""
check(
    "D13 SPEC REQ-105 に削除機能と .trash 退避方式が明記されている",
    bool(ROW) and "catalog-delete" in ROW and ".trash" in ROW and "復元できない" in ROW,
    "削除=%s / trash=%s / 復元不可の理由=%s"
    % ("catalog-delete" in ROW, ".trash" in ROW, "復元できない" in ROW),
)

print("=" * 78)
print("KLK-068 カタログエントリの削除機能 静的チェック")
print("対象: bridge.py（/catalog-delete・.trash 退避）/ SCR-004（削除UI）/ SPEC REQ-105")
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
