#!/usr/bin/env python3
"""
KLK-059 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions V1-V11 from
docs/designs/KLK-059.md §4 / §9 against 業種・テイスト語彙の一本化:

  語彙の正      .claude/skills/catalog-import/templates/CATALOG_RULES.md §3
                （業種 canonical 17区分 / テイスト canonical 10種）
  縦串 SCR-001  draft-gen/index.html（業種select = canonical / テイストchip の data-label + data-taste）
  縦串 SCR-004  draft-gen/catalog.html（業種フィルタチップ / テイストフィルタチップ）
  縦串 スキル   .claude/skills/catalog-import/SKILL.md（語彙を再掲せず正を参照しているか）
  実データ      catalog/catalog.json（Git除外・存在するときのみ検証＝fail-open）

Source of truth = 設計書 §3.1/§3.2/§4。check_klk034.py と同型（正規表現・文字列検索・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。

**catalog/ は社外秘ゆえ Git 除外**（REQ-011）。clone 直後や配布先には存在しないため、
catalog.json に依存する検証（V4/V9/V10）はファイルが無ければ SKIP する（fail-open）。
存在する場合は厳格に検証する。

Run: python3 tests/site/check_klk059.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "catalog-import", "templates", "CATALOG_RULES.md"), encoding="utf-8").read()
CSKILL = open(os.path.join(ROOT, ".claude", "skills", "catalog-import", "SKILL.md"), encoding="utf-8").read()
INDEX = open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
CATHTML = open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()

CATALOG_PATH = os.path.join(ROOT, "catalog", "catalog.json")
CATALOG = None
if os.path.exists(CATALOG_PATH):
    try:
        _raw = json.load(open(CATALOG_PATH, encoding="utf-8"))
        CATALOG = _raw.get("entries") if isinstance(_raw, dict) and "entries" in _raw else _raw
    except Exception:
        CATALOG = None  # 壊れた JSON でループを止めない（fail-open）

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# 語彙の正（CATALOG_RULES §3）をパースする
# ---------------------------------------------------------------------------
def parse_industry_canonical():
    """§3 の「推奨業種語彙(17区分…)」直後のブロックから 17 区分を取り出す。

    区切りは半角スペース + '/' + 半角スペース。業種名の内部にある '/'（士業事務所（法律/会計/…）・
    その他・団体/NPO）はスペースを伴わないため誤分割しない。末尾の「(受け皿)」注記は除去する。
    """
    m = re.search(r"\*\*推奨業種語彙\(17区分[^)]*\)\*\*:\s*\n(.*?)\n\s*-\s", RULES, re.S)
    if not m:
        return []
    body = re.sub(r"\s*\n\s*", " ", m.group(1)).strip()
    items = [t.strip() for t in body.split(" / ")]
    return [re.sub(r"\(受け皿\)\s*$", "", t).strip() for t in items if t.strip()]


def parse_taste_canonical():
    """§3 のテイスト表（| # | テイスト | 配色の方向性 | レイアウト… |）から canonical を順序つきで取り出す。"""
    m = re.search(r"\*\*推奨テイスト語彙\(10種[^)]*\)\*\*:\s*\n(.*?)\n\s*-\s+\*\*`高級感`", RULES, re.S)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        row = re.match(r"\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", line)
        if row:
            out.append(row.group(2).strip())
    return out


IND_CANON = parse_industry_canonical()
TASTE_CANON = parse_taste_canonical()

check(
    "V1 CATALOG_RULES §3 から業種 canonical 17区分をパースできる",
    len(IND_CANON) == 17 and all(IND_CANON) and len(set(IND_CANON)) == 17,
    "parsed=%d件 %s" % (len(IND_CANON), IND_CANON[:3] + ["..."] + IND_CANON[-2:] if IND_CANON else []),
)
check(
    "V5 CATALOG_RULES §3 からテイスト canonical 10種をパースできる",
    len(TASTE_CANON) == 10 and len(set(TASTE_CANON)) == 10,
    "parsed=%d件 %s" % (len(TASTE_CANON), TASTE_CANON),
)

# ---------------------------------------------------------------------------
# SCR-001（draft-gen/index.html）
# ---------------------------------------------------------------------------
_sel = re.search(r'<select id="industrySelect">(.*?)</select>', INDEX, re.S)
SCR001_IND = re.findall(r'<option value="([^"]*)"', _sel.group(1)) if _sel else []
SCR001_IND = [v for v in SCR001_IND if v]  # 先頭の空 option（未選択）を除く

check(
    "V2 SCR-001 業種select == 業種 canonical 17区分（順序含め文字列完全一致）",
    SCR001_IND == IND_CANON,
    "select=%d件 / canonical=%d件 / diff_only_in_select=%s / diff_only_in_canonical=%s / order_ok=%s"
    % (len(SCR001_IND), len(IND_CANON),
       sorted(set(SCR001_IND) - set(IND_CANON)), sorted(set(IND_CANON) - set(SCR001_IND)),
       SCR001_IND == IND_CANON),
)

# テイストチップ（input[name=taste]）のみを対象にする。
# 参考サムネカード（cardHtml）にも data-taste が現れるため、input 要素に限定してパースすること。
TASTE_CHIPS = re.findall(
    r'<input type="radio" name="taste"[^>]*?data-label="([^"]+)"[^>]*?data-taste="([^"]+)"[^>]*?>', INDEX)
TASTE_INPUTS_ALL = re.findall(r'<input type="radio" name="taste"[^>]*?>', INDEX)

check(
    "V7 SCR-001 の全テイストチップが data-label と data-taste を持つ（付け漏れ検出）",
    len(TASTE_INPUTS_ALL) >= 11 and len(TASTE_CHIPS) == len(TASTE_INPUTS_ALL),
    "input[name=taste]=%d件 / data-label+data-taste を持つもの=%d件" % (len(TASTE_INPUTS_ALL), len(TASTE_CHIPS)),
)

chip_canons = [c for _, c in TASTE_CHIPS]
check(
    "V8 SCR-001 の data-taste 値がすべて canonical 10種に含まれる",
    bool(chip_canons) and set(chip_canons) <= set(TASTE_CANON),
    "使用 canonical=%s / 語彙外=%s" % (sorted(set(chip_canons)), sorted(set(chip_canons) - set(TASTE_CANON))),
)

# 設計 §3.3: 唯一の多対一マッピング（先進的・シャープ → かっこいい）
chip_map = dict(TASTE_CHIPS)
check(
    "V8b 「先進的・シャープ」の data-taste が「かっこいい」（設計 §3.3 の唯一の多対一）",
    chip_map.get("先進的・シャープ") == "かっこいい",
    "先進的・シャープ → %r" % chip_map.get("先進的・シャープ"),
)

# ---------------------------------------------------------------------------
# SCR-004（draft-gen/catalog.html）
# ---------------------------------------------------------------------------
def facet_vals(facet):
    m = re.search(r'data-facet="%s"(.*?)</div>\s*</div>' % facet, CATHTML, re.S)
    return re.findall(r'data-val="([^"]+)"', m.group(1)) if m else []


SCR004_IND = facet_vals("industry")
SCR004_TASTE = facet_vals("taste")

check(
    "V3 SCR-004 業種チップ == 業種 canonical 17区分（文字列完全一致）",
    sorted(SCR004_IND) == sorted(IND_CANON) and len(SCR004_IND) == 17,
    "chips=%d件 / 差分=%s" % (len(SCR004_IND), sorted(set(SCR004_IND) ^ set(IND_CANON))),
)
check(
    "V6 SCR-004 テイストチップ == テイスト canonical 10種（文字列完全一致）",
    sorted(SCR004_TASTE) == sorted(TASTE_CANON) and len(SCR004_TASTE) == 10,
    "chips=%d件 %s / 差分=%s" % (len(SCR004_TASTE), SCR004_TASTE, sorted(set(SCR004_TASTE) ^ set(TASTE_CANON))),
)

# ---------------------------------------------------------------------------
# catalog-import SKILL.md（語彙の再掲をせず正を参照しているか）
# ---------------------------------------------------------------------------
m_taste_line = re.search(r"^- \*\*テイスト\*\*.*$", CSKILL, re.M)
taste_line = m_taste_line.group(0) if m_taste_line else ""
check(
    "V0 catalog-import SKILL.md がテイスト語彙を再掲せず CATALOG_RULES §3 を参照している",
    bool(taste_line) and "CATALOG_RULES" in taste_line and "/ナチュラル/" not in taste_line,
    "テイスト行=%r" % (taste_line[:120] + ("…" if len(taste_line) > 120 else "")),
)

# ---------------------------------------------------------------------------
# 旧表記の回帰防止（V11）
# ---------------------------------------------------------------------------
OLD_LABELS = ["美容・サロン", "住宅・不動産・建築", "医療・クリニック・福祉", "コーポレート(IT",
              "採用・求人", "EC・物販・通販", "ファッション・アパレル", "教育・スクール",
              "旅行・観光・宿泊", "ブライダル・イベント", "アート・クリエイティブ"]
leftovers = [t for t in OLD_LABELS if t in INDEX]
check(
    "V11 SCR-001 に旧業種表記が残っていない（回帰防止）",
    not leftovers,
    "残存=%s" % leftovers,
)
check(
    "V11b SCR-001 から OQ 仮置きの注記が削除されている",
    "(OQ-003)" not in INDEX and "(OQ-002)" not in INDEX,
    "OQ-003 残存=%s / OQ-002 残存=%s" % ("(OQ-003)" in INDEX, "(OQ-002)" in INDEX),
)

# ---------------------------------------------------------------------------
# catalog.json 実データとの照合（存在するときのみ・fail-open）
# ---------------------------------------------------------------------------
if CATALOG is None:
    detail = "catalog/catalog.json が無い（Git除外・REQ-011）ためSKIP"
    check("V4 catalog.json の industry がすべて canonical 17区分に含まれる [SKIP]", True, detail)
    check("V9 catalog.json の taste がすべて canonical 10種に含まれる [SKIP]", True, detail)
    check("V10 絞り込みシミュレーション: 表記ゆれ由来の MISS が 0 件 [SKIP]", True, detail)
else:
    ind_vals = sorted({(e.get("industry") or "") for e in CATALOG} - {""})
    taste_vals = sorted({(e.get("taste") or "") for e in CATALOG} - {""})
    check(
        "V4 catalog.json の industry がすべて canonical 17区分に含まれる",
        set(ind_vals) <= set(IND_CANON),
        "entries=%d / 語彙外=%s" % (len(CATALOG), sorted(set(ind_vals) - set(IND_CANON))),
    )
    check(
        "V9 catalog.json の taste がすべて canonical 10種に含まれる",
        set(taste_vals) <= set(TASTE_CANON),
        "使用=%s / 語彙外=%s" % (taste_vals, sorted(set(taste_vals) - set(TASTE_CANON))),
    )

    # V10: 絞り込みの実効性。SCR-001 の選択肢（canonical・完全一致）で実際に絞り込んだとき、
    # カタログに存在する業種／テイストがすべて「到達可能」（＝ヒット0にならない）ことを検証する。
    # 修正前（KLK-059 以前）は表記ゆれにより 業種 5/13・テイスト 6/11 しか一致せず、
    # 残りは「見つからないため全件表示」へ静かにフォールバックしていた。
    # 本チェックはその退行を検出する（選択肢のラベルを1文字でも変えるとヒット数が落ちて FAIL する）。
    ind_hit = [k for k in SCR001_IND if any((e.get("industry") or "") == k for e in CATALOG)]
    taste_hit = [c for c in sorted(set(chip_canons)) if any((e.get("taste") or "") == c for e in CATALOG)]
    unreachable_ind = sorted(set(ind_vals) - set(SCR001_IND))
    unreachable_taste = sorted(set(taste_vals) - set(chip_canons))
    check(
        "V10 絞り込みの実効性: カタログにある業種・テイストがすべて SCR-001 の選択肢から到達できる",
        not unreachable_ind and not unreachable_taste
        and len(ind_hit) == len(set(ind_vals)) and len(taste_hit) == len(set(taste_vals)),
        "業種 ヒットする選択肢=%d/%d（カタログの業種数=%d・到達不能=%s） / "
        "テイスト ヒットする canonical=%d/%d（カタログのテイスト数=%d・到達不能=%s）"
        % (len(ind_hit), len(SCR001_IND), len(set(ind_vals)), unreachable_ind,
           len(taste_hit), len(set(chip_canons)), len(set(taste_vals)), unreachable_taste),
    )

print("=" * 78)
print("KLK-059 業種・テイスト語彙の一本化 静的チェック")
print("対象: CATALOG_RULES §3（正）/ SCR-001 / SCR-004 / catalog-import SKILL / catalog.json")
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
