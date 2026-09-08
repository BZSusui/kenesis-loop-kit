#!/usr/bin/env python3
"""
KLK-109 acceptance-condition checker — カタログの語彙とデータの整合（総点検）。

★見つかったこと（2026-09-09 のカタログ部分の点検）
  語彙の数が文書と実装で食い違っていた:
    ・CATALOG_RULES の表に「テイスト語彙(**暫定7種**)」という古い記述（実装は10種）
    ・SKILL に「主配色(16カテゴリ)」と書きながら括弧内の列挙が**7つだけ**
    ・SKILL の別の行に「主配色**7**」

  実データは正しかったので実害は出ていなかったが、**この規約は AI が読む**。
  「16カテゴリから選べ」と言いながら7つしか見せなければ、AI は7つから選ぶ。

★この checker が守っているもの
  **語彙の正が1つであること。** 規約・画面・実データの三者が一致していないと、
  取り込みで付けたタグが画面の選択肢に無く、絞り込みが効かなくなる。
  数はもちろん、**列挙の中身**まで突き合わせる（数だけ合っていても中身が違えば同じ事故が起きる）。

Run: python3 tests/site/check_klk109.py
"""
import importlib.util
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "klk109_bridge", os.path.join(ROOT, "draft-gen", "bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = load_bridge()
CAT_HTML = io.open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()
RULES = io.open(os.path.join(ROOT, ".claude", "skills", "catalog-import",
                             "templates", "CATALOG_RULES.md"), encoding="utf-8").read()
SKILL = io.open(os.path.join(ROOT, ".claude", "skills", "catalog-import",
                             "SKILL.md"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def js_array(src, name):
    m = re.search(name + r"\s*=\s*\[(.*?)\]", src, re.S)
    if not m:
        return None
    return [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()]


# ---------------------------------------------------------------------------
# 語彙の正が1つであること（数だけでなく中身も）
# ---------------------------------------------------------------------------
ind = js_array(CAT_HTML, "CANON_INDUSTRIES")
tas = js_array(CAT_HTML, "CANON_TASTES")
check("A 画面が業種・テイストの語彙を持っている",
      bool(ind) and bool(tas), "業種=%s / テイスト=%s" % (len(ind or []), len(tas or [])))

check("B 主配色の語彙が実装にある（16カテゴリ）",
      hasattr(B, "CANONICAL_COLORS") and len(B.CANONICAL_COLORS) == 16,
      "実装=%d 種" % len(getattr(B, "CANONICAL_COLORS", [])))

check("C カラム構成の語彙が実装にある（6種）",
      hasattr(B, "CANONICAL_COLUMNS") and len(B.CANONICAL_COLUMNS) == 6,
      "実装=%d 種" % len(getattr(B, "CANONICAL_COLUMNS", [])))

# ★画面の語彙が、ひとつ残らず規約に載っているか（中身の照合）
if ind:
    miss = [x for x in ind if x not in RULES]
    check("D ★画面の業種17区分が、ひとつ残らず規約に載っている",
          not miss, "規約に無い=%s" % (miss or "なし"))
if tas:
    miss = [x for x in tas if x not in RULES]
    check("E ★画面のテイストが、ひとつ残らず規約に載っている",
          not miss, "規約に無い=%s" % (miss or "なし"))

# ★語彙は `CANON_*` の配列だけでなく**絞り込みチップ**にも書かれている（KLK-109）。
#   セレクタだけ見ていたため、チップを規約外の語へ書き換える改悪をすり抜けた。
#   画面に出る語彙は**すべて**同じ正から来ていなければならない。
_chips = re.findall(r'<span class="fchip" data-val="([^"]+)"', CAT_HTML)
_SOURCE_KINDS = ("own", "ref")          # 自社実績/収集見本の区分。業種・テイストとは別軸
_chip_terms = [c for c in _chips if c not in _SOURCE_KINDS and c.strip()]
check("D2 ★絞り込みチップの語彙が規約に載っている（%d 個）" % len(_chip_terms),
      all(c in RULES for c in _chip_terms),
      "規約に無い=%s" % ([c for c in _chip_terms if c not in RULES] or "なし"))
check("D3 ★絞り込みチップとセレクタの語彙が一致している（画面内で食い違わない）",
      bool(ind) and bool(tas)
      and all(c in set(ind) | set(tas) for c in _chip_terms),
      "セレクタに無い=%s"
      % ([c for c in _chip_terms if ind and tas and c not in set(ind) | set(tas)] or "なし"))

miss = [x for x in sorted(B.CANONICAL_COLORS) if x not in RULES]
check("F ★主配色16カテゴリが、ひとつ残らず規約に載っている",
      not miss, "規約に無い=%s" % (miss or "なし"))

# ★SKILL が「16カテゴリ」と言いながら少ない数しか列挙していないことを検出する
#   （AI はここを読んで選ぶので、見せた数が実質の語彙になる）
_seg = SKILL[SKILL.find("**主配色**(`colors`)"):]
_seg = _seg[:400]
_listed = [c for c in B.CANONICAL_COLORS if c in _seg]
check("G ★SKILL の主配色の列挙が16カテゴリを網羅している（見せた数が実質の語彙になる）",
      len(_listed) >= 16, "列挙されている=%d / 16" % len(_listed))

# 古い数字が残っていないか
for bad, label in (("暫定7種", "テイスト「暫定7種」"), ("主配色7", "「主配色7」")):
    check("H 古い語彙数の記述が残っていない: %s" % label,
          bad not in RULES and bad not in SKILL,
          "検出=%s" % (bad in RULES or bad in SKILL))

# ---------------------------------------------------------------------------
# 実データの整合（登録されたものが語彙に収まっているか）
# ---------------------------------------------------------------------------
cat_path = os.path.join(ROOT, "catalog", "catalog.json")
if not os.path.isfile(cat_path):
    check("I 実データが語彙に収まっている", True, "catalog.json が無い環境（素通り）")
    check("J 画像とエントリが1対1で対応している", True, "catalog.json が無い環境（素通り）")
else:
    data = json.load(io.open(cat_path, encoding="utf-8"))
    entries = data.get("entries", [])
    out = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        if ind and e.get("industry") and e["industry"] not in ind:
            out.append(("industry", e.get("id"), e["industry"]))
        if tas and e.get("taste") and e["taste"] not in tas:
            out.append(("taste", e.get("id"), e["taste"]))
        cols = e.get("colors")
        for c in (cols if isinstance(cols, list) else []):
            if c not in B.CANONICAL_COLORS:
                out.append(("colors", e.get("id"), c))
        if e.get("columns") and e["columns"] not in B.CANONICAL_COLUMNS:
            out.append(("columns", e.get("id"), e["columns"]))
    check("I ★実データ %d 件が語彙に収まっている（絞り込みが効く）" % len(entries),
          not out, "語彙外=%s" % (out[:4] or "なし"))

    # 画像とエントリの対応（片方だけ在る状態を作らない）
    used = set()
    missing = []
    for e in entries:
        f = e.get("file") or e.get("image")
        if not f:
            missing.append((e.get("id"), "file キー無し"))
            continue
        used.add(os.path.basename(f))
        if not os.path.isfile(os.path.join(ROOT, "catalog", "img", os.path.basename(f))):
            missing.append((e.get("id"), f))
    import glob
    orphan = [os.path.basename(p)
              for p in glob.glob(os.path.join(ROOT, "catalog", "img", "*"))
              if os.path.basename(p) not in used]
    check("J ★画像とエントリが1対1（欠落 %d / 孤児 %d）" % (len(missing), len(orphan)),
          not missing and not orphan,
          "欠落=%s / 孤児=%s" % (missing[:3] or "なし", orphan[:3] or "なし"))

    ids = [e.get("id") for e in entries if isinstance(e, dict)]
    import collections
    dup = [k for k, v in collections.Counter(ids).items() if v > 1]
    check("K ID が重複していない・欠落していない",
          not dup and all(ids), "重複=%s / 欠落=%d" % (dup or "なし", sum(1 for i in ids if not i)))

print("=" * 78)
print("KLK-109 カタログの語彙とデータの整合 チェック")
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
