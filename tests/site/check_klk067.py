#!/usr/bin/env python3
"""
KLK-067 acceptance-condition checker (static + 純関数の実行 / no browser required).

Verifies K1-K11 from docs/designs/KLK-067.md §4.5 / §9:
主配色 canonical を **ムードカラー ジェネレーター（palette/index.html の const COLORS）準拠の16種**へ拡張。

  語彙の正      palette/index.html の `const COLORS`（name・順序）
  縦串 ブリッジ  draft-gen/bridge.py     （CANONICAL_COLORS / CANONICAL_COLORS_ORDER）
  縦串 SCR-004   draft-gen/catalog.html  （フィルタチップ・承認フォーム）
  縦串 SCR-001   draft-gen/index.html    （参考サムネの colors 軽検証）
  縦串 生成規約  DRAFT_RULES §5.1        （16カテゴリ→hex 変換表）
  実データ      catalog/catalog.json     （Git除外・存在するときのみ）

★この checker が守っているもの:
  カタログのタグ付け（主配色）と配色生成（パレット）が**同じ言葉を話す**こと。
  片方だけ語彙が増えると、絞り込みも参考準拠の表引きも静かに外れる。

Run: python3 tests/site/check_klk067.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PALETTE = open(os.path.join(ROOT, "palette", "index.html"), encoding="utf-8").read()
CATHTML = open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()
INDEX = open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()

sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

CATALOG_PATH = os.path.join(ROOT, "catalog", "catalog.json")

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# K1 語彙の正（palette の const COLORS）
# ---------------------------------------------------------------------------
_i = PALETTE.find("const COLORS = [")
_seg = PALETTE[_i:PALETTE.find("];", _i)] if _i >= 0 else ""
PAL_NAMES = re.findall(r"name:\s*'([^']+)'", _seg)
check(
    "K1 palette/index.html の const COLORS から16の name をパースできる（語彙の正）",
    len(PAL_NAMES) == 16 and len(set(PAL_NAMES)) == 16,
    "parsed=%d件 %s" % (len(PAL_NAMES), PAL_NAMES),
)

# ---------------------------------------------------------------------------
# K2-K3 ブリッジ（純関数を実行）
# ---------------------------------------------------------------------------
cc = getattr(bridge, "CANONICAL_COLORS", None)
order = getattr(bridge, "CANONICAL_COLORS_ORDER", None)
check(
    "K2 bridge.CANONICAL_COLORS が palette の16種と集合として一致する",
    isinstance(cc, (set, frozenset)) and set(cc) == set(PAL_NAMES),
    "型=%s / 差分=%s" % (type(cc).__name__, sorted(set(cc or []) ^ set(PAL_NAMES))),
)
check(
    "K3 bridge.CANONICAL_COLORS_ORDER が palette と順序も一致する",
    isinstance(order, list) and order == PAL_NAMES,
    "order=%s" % (order if order != PAL_NAMES else "一致"),
)

# ---------------------------------------------------------------------------
# K4-K6 UI の語彙
# ---------------------------------------------------------------------------
_m = re.search(r'data-facet="colors"(.*?)</div>\s*</div>', CATHTML, re.S)
CHIPS = re.findall(r'data-val="([^"]+)"', _m.group(1)) if _m else []
check(
    "K4 SCR-004 のフィルタチップが16色・palette と順序も一致する",
    CHIPS == PAL_NAMES,
    "chips=%d件 / 一致=%s / 差分=%s" % (len(CHIPS), CHIPS == PAL_NAMES, sorted(set(CHIPS) ^ set(PAL_NAMES))),
)
_m = re.search(r"var CANONICAL_COLORS = \[(.*?)\];", CATHTML, re.S)
CAT_JS = re.findall(r'"([^"]+)"', _m.group(1)) if _m else []
check(
    "K5 SCR-004 の承認フォームが同じ16色を使う（CANONICAL_COLORS 由来）",
    CAT_JS == PAL_NAMES and "CANONICAL_COLORS.map" in CATHTML,
    "JS定義=%d件 一致=%s / フォームが参照=%s"
    % (len(CAT_JS), CAT_JS == PAL_NAMES, "CANONICAL_COLORS.map" in CATHTML),
)
_m = re.search(r"const CANONICAL_COLORS = \[(.*?)\];", INDEX, re.S)
IDX_JS = re.findall(r"'([^']+)'", _m.group(1)) if _m else []
check(
    "K6 SCR-001 の CANONICAL_COLORS も16種で一致する",
    IDX_JS == PAL_NAMES,
    "定義=%d件 一致=%s" % (len(IDX_JS), IDX_JS == PAL_NAMES),
)

# ---------------------------------------------------------------------------
# K7-K8 DRAFT_RULES §5.1 の変換表
# ---------------------------------------------------------------------------
_i = RULES.find("### 5.1 参考配色の16カテゴリ")
SEG51 = RULES[_i:RULES.find("\n---", _i)] if _i >= 0 else ""
TBL = dict(re.findall(r"^\|\s*([^|]+?)\s*\|\s*`(#[0-9A-Fa-f]{6})`\s*\|", SEG51, re.M))
check(
    "K7 §5.1 の変換表が15色の hex を持ち、カラフルは表引きしない",
    len(TBL) == 15 and set(TBL.keys()) == set(PAL_NAMES) - {"カラフル"}
    and "| カラフル | （表引きしない）" in SEG51,
    "hex定義=%d色 / 差分=%s / カラフル行=%s"
    % (len(TBL), sorted(set(TBL.keys()) ^ (set(PAL_NAMES) - {"カラフル"})),
       "| カラフル | （表引きしない）" in SEG51),
)
LEGACY_HEX = {"グリーン": "#2E7D6B", "ブルー": "#2C5F8A", "レッド": "#B3402F",
              "ゴールド": "#C6A15B", "ピンク": "#E86FA0", "モノトーン": "#444850"}
drift = {k: (v, TBL.get(k)) for k, v in LEGACY_HEX.items() if TBL.get(k) != v}
check(
    "K8 §5.1 の既存6色の hex が変わっていない（golden klk034 の後方互換）",
    not drift,
    "ドリフト=%s" % (drift or "なし"),
)

# ---------------------------------------------------------------------------
# K9 旧名の一掃（過去の設計書は対象外＝当時の記録）
# ---------------------------------------------------------------------------
LEGACY = "マルチカラー"
targets = []
for rel in ["draft-gen/bridge.py", "draft-gen/catalog.html", "draft-gen/index.html",
            ".claude/skills/catalog-import/SKILL.md",
            ".claude/skills/draft-generate/SKILL.md",
            ".claude/skills/draft-generate/templates/DRAFT_RULES.md",
            "docs/wireframes/SCR-004-catalog.html",
            "tests/fixtures/klk034b/instruction.json"]:
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        continue
    body = open(path, encoding="utf-8").read()
    # 改名の経緯を説明するコメント行は許容する（「旧「マルチカラー」」の形）
    hits = [ln for ln in body.splitlines()
            if LEGACY in ln and "旧「マルチカラー」" not in ln and "旧" + LEGACY not in ln]
    if hits:
        targets.append((rel, len(hits)))
check(
    "K9 実装・規約・golden から旧名「マルチカラー」が消えている（説明コメントは可）",
    not targets,
    "残存=%s" % (targets or "なし"),
)

# ---------------------------------------------------------------------------
# K10 カラフルの単独指定ルール（純関数を実行）
# ---------------------------------------------------------------------------
base = {"file": "pnd-a.png", "industry": "x", "taste": "y"}
vp, vcr = bridge.validate_proposal, bridge.validate_commit_request


def prop(colors):
    return {"schema": "klk-catalog-proposal", "version": 1,
            "items": [dict(base, colors=colors)]}


ok = (vp(prop(["カラフル"]))[0] is True
      and vp(prop(["カラフル", "ブルー"]))[0] is False
      and vp(prop(["ブルー", "ネイビー", "シルバー"]))[0] is True     # 新色3件は可
      and vp(prop(["ブルー", "ネイビー", "シルバー", "ゴールド"]))[0] is False  # 4件は不可
      and vcr({"items": [dict(base, colors=["カラフル", "ブルー"])]})[0] is False)
check(
    "K10 カラフルの単独指定・最大3件のルールが16色でも維持されている",
    ok,
    "単独OK=%s / 併用NG=%s / 新色3件OK=%s / 4件NG=%s"
    % (vp(prop(["カラフル"]))[0], vp(prop(["カラフル", "ブルー"]))[0],
       vp(prop(["ブルー", "ネイビー", "シルバー"]))[0],
       vp(prop(["ブルー", "ネイビー", "シルバー", "ゴールド"]))[0]),
)

# ---------------------------------------------------------------------------
# K11 実データ（存在するときのみ・Git除外）
# ---------------------------------------------------------------------------
if not os.path.exists(CATALOG_PATH):
    check("K11 catalog.json に旧名が残っていない [SKIP]", True,
          "catalog/catalog.json が無い（Git除外・REQ-011）")
else:
    try:
        entries = json.load(open(CATALOG_PATH, encoding="utf-8")).get("entries", [])
    except (OSError, ValueError):
        entries = []
    used = set()
    for e in entries:
        used.update(e.get("colors") or [])
    check(
        "K11 catalog.json の colors が16カテゴリ内で、旧名が残っていない",
        LEGACY not in used and used <= set(PAL_NAMES),
        "使用=%s / 語彙外=%s" % (sorted(used), sorted(used - set(PAL_NAMES))),
    )

print("=" * 78)
print("KLK-067 主配色をムードカラー ジェネレーター準拠の16種へ 静的チェック")
print("対象: palette（正）/ bridge / SCR-004 / SCR-001 / DRAFT_RULES §5.1 / catalog.json")
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
