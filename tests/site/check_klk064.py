#!/usr/bin/env python3
"""
KLK-064 acceptance-condition checker (static + 純関数の実行 / no browser required).

Verifies P1-P16 from docs/designs/KLK-064.md §4.4 / §9:
カタログ取り込みを「AI=提案 / 人間=画面で承認 / Python=決定的な登録」の3者分業へ作り替えた変更。

  縦串 ブリッジ  draft-gen/bridge.py     （純関数3件・/catalog-proposal・/catalog-commit・成功判定）
  縦串 SCR-004   draft-gen/catalog.html  （承認フォーム・完了モーダル・canonical 語彙）
  縦串 スキル    catalog-import/SKILL.md （提案モード）
  縦串 仕様      docs/SPEC.md            （REQ-106）

★背景（この checker が守っているもの）:
  旧方式は bridge が `claude -p`（非対話）を起動していたが、catalog-import の必須確認ゲートは
  対話を前提としていたため、**一度も登録に到達していなかった**（"完了" と表示しながら 0 件）。
  P9 はその再発（成功判定が常に真になる状態）を検出する。

Run: python3 tests/site/check_klk064.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_SRC = open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
CATHTML = open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "catalog-import", "SKILL.md"), encoding="utf-8").read()
RULES = open(os.path.join(ROOT, ".claude", "skills", "catalog-import", "templates", "CATALOG_RULES.md"), encoding="utf-8").read()
SPEC = open(os.path.join(ROOT, "docs", "SPEC.md"), encoding="utf-8").read()

sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


OK_ITEM = {"file": "pnd-a.jpg", "industry": "飲食店・カフェ・食関連", "taste": "ナチュラル",
           "colors": ["グリーン"], "source": "own"}

# ---------------------------------------------------------------------------
# P1-P3 純関数（実行して検証）
# ---------------------------------------------------------------------------
vp = getattr(bridge, "validate_proposal", None)
if vp is None:
    check("P1 validate_proposal が提案の正常/異常を判定する", False, "validate_proposal が未定義")
else:
    good = {"schema": "klk-catalog-proposal", "version": 1, "jobId": "ab", "items": [dict(OK_ITEM)]}
    cases = [
        (good, True),
        (dict(good, schema="wrong"), False),
        (dict(good, version=2), False),
        (dict(good, items="notalist"), False),
        (dict(good, items=[dict(OK_ITEM, file="../x.jpg")]), False),
        (dict(good, items=[dict(OK_ITEM, colors=["虹色"])]), False),
        (dict(good, items=[dict(OK_ITEM, colors=["マルチカラー", "ブルー"])]), False),
        (dict(good, items=[dict(OK_ITEM, sectionLayouts={"HERO": ""})]), False),
        ("notadict", False),
    ]
    bad = [(c, want, vp(c)[0]) for c, want in cases if vp(c)[0] != want]
    check("P1 validate_proposal が提案の正常/異常を判定する（9ケース）", not bad,
          "不一致=%d件" % len(bad) if bad else "全9ケース一致")

vc = getattr(bridge, "validate_commit_request", None)
if vc is None:
    check("P2 validate_commit_request が不正な承認内容を弾く", False, "未定義")
else:
    cases = [
        ({"items": [dict(OK_ITEM)]}, True),
        ({"items": []}, False),                                              # 空
        ({"items": [dict(OK_ITEM, file="../../etc/passwd")]}, False),        # traversal
        ({"items": [dict(OK_ITEM, colors=["虹色"])]}, False),                 # 語彙外
        ({"items": [dict(OK_ITEM, source="admin")]}, False),                 # 不正 source
        ({"items": [dict(OK_ITEM, industry="")]}, False),                    # 業種未指定
        ({"items": [dict(OK_ITEM, taste="")]}, False),                       # テイスト未指定
        ({"items": [{k: v for k, v in OK_ITEM.items() if k != "colors"}]}, False),  # 主配色なし
    ]
    bad = [(c, want, vc(c)[0]) for c, want in cases if vc(c)[0] != want]
    check("P2 validate_commit_request が不正な承認内容を弾く（8ケース）", not bad,
          "不一致=%s" % ([(w, g) for _, w, g in bad] if bad else "全8ケース一致"))

nid = getattr(bridge, "next_catalog_id", None)
if nid is None:
    check("P3 next_catalog_id が catalog.json と img/ の双方から最大+1 を返す", False, "未定義")
else:
    ok = (nid([], []) == "cat-0001"
          and nid(["cat-0053"], []) == "cat-0054"
          and nid([], ["cat-0012.png"]) == "cat-0013"
          and nid(["cat-0053"], ["cat-0060.png"]) == "cat-0061"   # 双方を見る（img の方が大きい）
          and nid(["bogus", None], []) == "cat-0001")             # 不正値は無視
    check("P3 next_catalog_id が catalog.json と img/ の双方から最大+1 を返す（5ケース）", ok,
          "空=%s / json=%s / img=%s / 双方=%s"
          % (nid([], []), nid(["cat-0053"], []), nid([], ["cat-0012.png"]), nid(["cat-0053"], ["cat-0060.png"])))

# ---------------------------------------------------------------------------
# P4-P9 ブリッジ（防御順・検証・書き込み先・原子性・エンドポイント・成功判定）
# ---------------------------------------------------------------------------
_i = BRIDGE_SRC.find("def _catalog_commit")
_FULL = BRIDGE_SRC[_i:BRIDGE_SRC.find("def _generate(self)")] if _i >= 0 else ""
_ds = _FULL.find('"""', _FULL.find('"""') + 3)
CBODY = _FULL[_ds + 3:] if _ds > 0 else _FULL   # docstring を除いた本体

order = [
    ("origin", CBODY.find("is_allowed_origin(")),
    ("size", CBODY.find("> MAX_BODY_BYTES")),
    ("json", CBODY.find("json.loads(")),
    ("validate_commit_request", CBODY.find("validate_commit_request(")),
    ("next_catalog_id", CBODY.find("next_catalog_id(")),
    ("validate_catalog", CBODY.find("validate_catalog(merged)")),
    ("move", CBODY.find("shutil.move(src, dst)")),
    ("os.replace", CBODY.find("os.replace(tmp")),
    ("_json(200", CBODY.find("_json(200")),
]
pos = [p for _, p in order]
check(
    "P4 _catalog_commit の順序が Origin→サイズ→JSON→検証→採番→validate_catalog→移動→置換→200",
    bool(CBODY) and all(p >= 0 for p in pos) and pos == sorted(pos),
    "位置=%s" % ({k: v for k, v in order}),
)
check(
    "P5 validate_catalog を通してから書き込む（不正なら1件も書かない）",
    "validate_catalog(merged)" in CBODY
    and CBODY.find("validate_catalog(merged)") < CBODY.find("shutil.move(src, dst)")
    and "1件も登録していません" in CBODY,
    "検証が移動より前=%s / all-or-nothing の応答=%s"
    % (CBODY.find("validate_catalog(merged)") < CBODY.find("shutil.move(src, dst)"),
       "1件も登録していません" in CBODY),
)
writes_outside = re.findall(r'open\(\s*(?!tmp\b)([A-Za-z_][A-Za-z0-9_]*)\s*,\s*"w"', CBODY)
check(
    "P6 書き込み先が catalog 配下のみ（catalog_json_path / catalog_img_dir・REQ-011）",
    "catalog_img_dir" in CBODY and "catalog_json_path" in CBODY and not writes_outside,
    "img_dir=%s / json_path=%s / 想定外の書き込み先=%s"
    % ("catalog_img_dir" in CBODY, "catalog_json_path" in CBODY, writes_outside or "なし"),
)
check(
    "P7 catalog.json の書き込みが原子的（一時ファイル→os.replace）＋失敗時に画像移動を巻き戻す",
    "os.replace(tmp, catalog_json_path)" in CBODY
    and "except Exception as exc" in CBODY
    and CBODY.count("shutil.move(dst, src)") >= 2,
    "os.replace=%s / 広い例外捕捉=%s / 巻き戻し箇所=%d"
    % ("os.replace(tmp, catalog_json_path)" in CBODY, "except Exception as exc" in CBODY,
       CBODY.count("shutil.move(dst, src)")),
)
check(
    "P8 GET /catalog-proposal と GET /catalog/pending-img/ がある（後者は安全名チェックつき）",
    'path == "/catalog-proposal"' in BRIDGE_SRC
    and 'path.startswith("/catalog/pending-img/")' in BRIDGE_SRC
    and "def _catalog_pending_img" in BRIDGE_SRC
    and "is_safe_catalog_name(name)" in BRIDGE_SRC,
    "proposal=%s / pending-img=%s / 安全名=%s"
    % ('path == "/catalog-proposal"' in BRIDGE_SRC,
       'path.startswith("/catalog/pending-img/")' in BRIDGE_SRC,
       "is_safe_catalog_name(name)" in BRIDGE_SRC),
)
check(
    "P9 ジョブの成功判定が proposal.json の生成有無になっている（常に真だった旧判定の再発防止）",
    "proposal_ok = os.path.isfile(proposal_path)" in BRIDGE_SRC
    and "is_job_success(proc.returncode, proposal_ok)" in BRIDGE_SRC
    and "is_job_success(proc.returncode, after is not None)" not in BRIDGE_SRC,
    "proposal_ok 判定=%s / 旧判定の残存=%s"
    % ("is_job_success(proc.returncode, proposal_ok)" in BRIDGE_SRC,
       "is_job_success(proc.returncode, after is not None)" in BRIDGE_SRC),
)
check(
    "P9b ジョブ仕様に mode:'propose' と proposalPath が入り、スキルが提案モードを持つ",
    '"mode": "propose"' in BRIDGE_SRC and '"proposalPath"' in BRIDGE_SRC
    and "提案モード" in SKILL and "klk-catalog-proposal" in SKILL
    and "人間確認ゲートは2形態" in RULES,
    "bridge mode=%s / SKILL 提案モード=%s / RULES 2形態=%s"
    % ('"mode": "propose"' in BRIDGE_SRC, "提案モード" in SKILL, "人間確認ゲートは2形態" in RULES),
)

# ---------------------------------------------------------------------------
# P10-P15 SCR-004
# ---------------------------------------------------------------------------
check(
    "P10 SCR-004 に提案の編集フォームがある（業種/テイスト/主配色/カラム/own-ref/除外）",
    all(x in CATHTML for x in ('data-f="industry"', 'data-f="taste"', 'data-color=',
                               'data-f="columns"', 'data-f="source"', 'data-f="_excluded"')),
    "industry=%s taste=%s colors=%s columns=%s source=%s 除外=%s" % (
        'data-f="industry"' in CATHTML, 'data-f="taste"' in CATHTML, "data-color=" in CATHTML,
        'data-f="columns"' in CATHTML, 'data-f="source"' in CATHTML, 'data-f="_excluded"' in CATHTML,
    ),
)
_m = re.search(r"var CANON_INDUSTRIES = \[(.*?)\];", CATHTML, re.S)
inds = re.findall(r'"([^"]+)"', _m.group(1)) if _m else []
_m = re.search(r"var CANON_TASTES = \[(.*?)\];", CATHTML, re.S)
tastes = re.findall(r'"([^"]+)"', _m.group(1)) if _m else []
rules_inds = []
_m = re.search(r"\*\*推奨業種語彙\(17区分[^)]*\)\*\*:\s*\n(.*?)\n\s*-\s", RULES, re.S)
if _m:
    body = re.sub(r"\s*\n\s*", " ", _m.group(1)).strip()
    rules_inds = [re.sub(r"\(受け皿\)\s*$", "", t).strip() for t in body.split(" / ") if t.strip()]
rules_tastes = []
_m = re.search(r"\*\*推奨テイスト語彙\(10種[^)]*\)\*\*:\s*\n(.*?)\n\s*-\s+\*\*`高級感`", RULES, re.S)
if _m:
    for line in _m.group(1).splitlines():
        row = re.match(r"\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", line)
        if row:
            rules_tastes.append(row.group(2).strip())
check(
    "P11 SCR-004 の語彙が CATALOG_RULES §3 の canonical と一致する（業種17・テイスト10）",
    inds == rules_inds and tastes == rules_tastes and len(inds) == 17 and len(tastes) == 10,
    "業種 UI=%d/正=%d 一致=%s ｜ テイスト UI=%d/正=%d 一致=%s"
    % (len(inds), len(rules_inds), inds == rules_inds, len(tastes), len(rules_tastes), tastes == rules_tastes),
)
check(
    "P12 SCR-004 に「この内容で登録」があり POST /catalog-commit を呼ぶ",
    "この内容で登録" in CATHTML and '"/catalog-commit"' in CATHTML,
    "ボタン=%s / エンドポイント=%s" % ("この内容で登録" in CATHTML, '"/catalog-commit"' in CATHTML),
)
check(
    "P13 アップロード完了モーダルがあり、閉じる手段（×・背景・Esc）と次アクションのボタンを持つ",
    'id="upModalBack"' in CATHTML and 'id="upModalClose"' in CATHTML
    and '"Escape"' in CATHTML and "if (e.target === this) closeUploadModal();" in CATHTML
    and 'id="upModalGo"' in CATHTML and "openUploadModal(okCount" in CATHTML,
    "モーダル=%s / ×=%s / Esc=%s / 背景=%s / 次アクション=%s / 呼び出し=%s"
    % ('id="upModalBack"' in CATHTML, 'id="upModalClose"' in CATHTML, '"Escape"' in CATHTML,
       "if (e.target === this) closeUploadModal();" in CATHTML, 'id="upModalGo"' in CATHTML,
       "openUploadModal(okCount" in CATHTML),
)
check(
    "P14 .autotag の文言が「この画面で確認・修正して登録」の実態に合っている（KLK-061 から更新）",
    "この画面で確認・修正してから登録します" in CATHTML
    and "この画面には表示されません" not in CATHTML
    and "承認前に確定しません" in CATHTML,
    "新文言=%s / 旧文言の残存=%s / 保証の維持=%s"
    % ("この画面で確認・修正してから登録します" in CATHTML,
       "この画面には表示されません" in CATHTML, "承認前に確定しません" in CATHTML),
)
ext = [u for u in re.findall(r'https?://[^"\'\s)]+', CATHTML) if "w3.org" not in u]
check("P15 SCR-004 に外部URL参照が無い（NFR-005）", not ext, "外部URL=%s" % (ext or "なし"))

# ---------------------------------------------------------------------------
# P16 SPEC
# ---------------------------------------------------------------------------
row = re.search(r"^\|\s*REQ-106\s*\|.*$", SPEC, re.M)
ROW = row.group(0) if row else ""
check(
    "P16 SPEC REQ-106 に2段階方式と旧不具合の記録がある",
    bool(ROW) and "2段階" in ROW and "proposal.json" in ROW and "一度も登録に到達していなかった" in ROW,
    "2段階=%s / proposal=%s / 不具合の記録=%s"
    % ("2段階" in ROW, "proposal.json" in ROW, "一度も登録に到達していなかった" in ROW),
)

print("=" * 78)
print("KLK-064 カタログ取り込みの画面承認化（提案→承認→登録）静的チェック")
print("対象: bridge.py（純関数・commit・成功判定）/ SCR-004 / SKILL / CATALOG_RULES / SPEC")
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
