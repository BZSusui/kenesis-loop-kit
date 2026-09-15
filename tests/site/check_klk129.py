#!/usr/bin/env python3
"""
KLK-129 acceptance-condition checker — せり出し横長画像の文言側が狭い。

★経緯（2026-09-15・理恵さんが実際に ABOUT を差し替えて発見）
  規約は `grid-template-columns: 1fr 1fr`＝半分ずつと書いていた。
  ところが `1fr` は `minmax(auto, 1fr)` で、**中身の最小幅より小さくならない**。
  画像側のアタリには「検索: children clinic interior」という折り返さない一行があり、
  これが列を押し広げて**文言側だけが削られていた**。
  実測: 全体860px のうち 画像587px / 白背景 273px（半分なら430pxのはず）。
  見出しが2行に割れ、本文も数文字ごとに折り返していた。

★この checker が守っているもの
  R. 規約が「中身に押し広げられない」書き方を指示していること
  N. `1fr 1fr` を復活させていないこと
  S. 見本がその書き方に従っていること
  G. ゴールデン（tests/fixtures/）は触っていないこと（過去の出力の記録なので）

  実際の画像幅・白背景幅は tests/test_palette_klk129.py が実ブラウザで測る。

Run: python3 tests/site/check_klk129.py
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = io.open(os.path.join(
    ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def overlap_rule(src):
    """img-overlap の列指定を取り出す（純粋関数）。見つからなければ None。"""
    m = re.search(r"img-overlap[^{]*\{[^}]*?grid-template-columns:\s*([^;}]+)", src)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# R / N. 規約
# ---------------------------------------------------------------------------
check("R1 img-overlap の節がある", "12.1.3.1" in RULES and "img-overlap" in RULES, "")
check("R2 ★列の書き方を指示している（文言側を先に確保し、画像は残り）",
      "grid-template-columns: minmax(0, 1fr) minmax(0, 480px)" in RULES, "")
check("R3 ★minmax(0,…) が要ることと、外すと戻ることを書いている",
      "minmax(0, ...)` を外すと同じ不具合が戻る" in RULES, "")
check("R4 ★実測値を根拠として残している（書き写しでなく測った数）",
      "273px" in RULES and "587px" in RULES, "")
check("R5 文言側の下限を書いている", "460px 以上" in RULES, "")
check("R6 なぜ割合ではないかを書いている（器の広い案件で画像まで太る）",
      "割合" in RULES and "450→550px" in RULES, "")
check("N1 ★img-overlap の指定に `1fr 1fr` を復活させていない",
      not re.search(r"img-overlap[^|\n]*grid-template-columns:\s*1fr 1fr", RULES), "")
check("N2 他の型の `1fr 1fr` は残っている（この修正で壊していない）",
      "grid-template-columns:1fr 1fr" in RULES.replace(" ", "") or "1fr 1fr" in RULES, "")
check("R7 ★横並びを 900px までにすることと、その実測根拠を書いている",
      "@media (max-width: 900px)" in RULES and "画像側 208px" in RULES, "")
check("R8 ★1列にするだけでは畳めない（grid-column も戻す）ことを書いている",
      "grid-column: 1; grid-row: auto;" in RULES and "暗黙の2列目" in RULES, "")
check("R9 ★画像側に min-width: 0 が要ることを書いている",
      "min-width: 0" in RULES and "min-width:auto" in RULES, "")

check("R10 ★縦積みで min-height を外すことと、その正体を書いている",
      "min-height` を外す" in RULES and "min-height × 4/3" in RULES and "587px" in RULES, "")
check("R11 幅のある表は縮めず器の中でスクロールさせる、と明記している",
      "幅のある表そのものは縮めない" in RULES, "")

check("N3 同じ注意が要る型を挙げている",
      "同じ注意が要る型" in RULES and "map-side" in RULES, "")

# ---------------------------------------------------------------------------
# S. 見本
# ---------------------------------------------------------------------------
bad = []
for p in sorted(glob.glob(os.path.join(ROOT, "samples", "*", "index-*.html"))):
    src = io.open(p, encoding="utf-8").read()
    if "img-overlap" not in src:
        continue
    rule = overlap_rule(src)
    if rule is None:
        continue
    if rule == "1fr":          # 狭カラムの縦積み（KLK-073/075）は対象外
        continue
    if "minmax(0,1fr)" not in rule.replace(" ", "") or "480px" not in rule:
        bad.append("%s → %s" % (os.path.relpath(p, ROOT), rule))
check("S1 ★見本が新しい書き方に従っている（狭カラムの縦積みは対象外）",
      not bad, "違う書き方=%s" % (bad or "なし"))

# ---------------------------------------------------------------------------
# G. ゴールデンは触らない
# ---------------------------------------------------------------------------
golden = []
for p in sorted(glob.glob(os.path.join(ROOT, "tests", "fixtures", "*", "index-*.html"))):
    src = io.open(p, encoding="utf-8").read()
    if "img-overlap" not in src:
        continue
    rule = overlap_rule(src)          # ★「480px がファイルのどこかにある」では広すぎる
    if rule and "480px" in rule:      #   （hero の min-height:480px を拾ってしまった）
        golden.append(os.path.relpath(p, ROOT))
check("G1 ★ゴールデンを書き換えていない（過去の出力の記録なので直さない）",
      not golden, "触ってしまったもの=%s" % (golden or "なし"))

print("=" * 78)
print("KLK-129 せり出し横長画像の文言側の幅 チェック")
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
