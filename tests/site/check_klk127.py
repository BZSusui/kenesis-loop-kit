#!/usr/bin/env python3
"""
KLK-127 acceptance-condition checker — 業種の自由入力が一覧選択を打ち消して参考素材が絞れない。

★経緯
  業種欄が「一覧から選ぶ」「**または**自由入力」という建て付けで、
  `currentIndustry()` が `自由入力 || 一覧選択` を返していた。
  カタログの industry は17区分の canonical 値なので、自由入力の任意文字列は
  照合に掛からず0件 → 全件フォールバックへ落ちる。
  理恵さんが「クリニック・病院・介護リハビリ」を選んで
  「小児科・アレルギー科のクリニック」と書き足したところ、
  3件に絞れるはずが167件すべて（食品・美容・教育…）が並んだ。

★この checker が守っているもの
  K. ★絞り込みのキーは一覧選択が優先されること（ここが逆だと不具合が戻る）
  G. ★生成指示書の業種は従来どおり自由入力が優先されること（出力を変えない）
  C. チップは「実際に絞った側」が書くこと（入力から別に組み立てない）
  W. 画面の言葉が「両方使える」ことを伝えていること

  実際に描かれるサムネイルの枚数と業種は tests/test_palette_klk127.py が実ブラウザで見る。

Run: python3 tests/site/check_klk127.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INDEX = io.open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def body_of(src, name):
    """`function name(...) { ... }` の中身を返す（純粋関数・波括弧の対応を数える）。"""
    m = re.search(r"function\s+%s\s*\([^)]*\)\s*\{" % re.escape(name), src)
    if not m:
        return None
    i = m.end() - 1
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i + 1:j]
    return None


CUR = body_of(INDEX, "currentIndustry")
ISC = body_of(INDEX, "isCustomIndustry")
FIL = body_of(INDEX, "applyThumbFilter")
REN = body_of(INDEX, "render")
BLD = body_of(INDEX, "buildInstruction")

# ---------------------------------------------------------------------------
# K. 絞り込みのキー
# ---------------------------------------------------------------------------
check("K0 関数を読み取れる",
      all(x is not None for x in (CUR, ISC, FIL, REN, BLD)),
      "currentIndustry=%s isCustomIndustry=%s applyThumbFilter=%s render=%s buildInstruction=%s"
      % tuple(x is not None for x in (CUR, ISC, FIL, REN, BLD)))

if CUR:
    # 「一覧選択を先に読む」ことを、出現位置で見る（|| の左右を文字列で決め打ちしない）
    p = CUR.find("industrySelect")
    c = CUR.find("industryCustom")
    check("K1 ★絞り込みのキーは一覧選択を先に見る（ここが逆だと不具合が戻る）",
          p >= 0 and c >= 0 and p < c,
          "industrySelect の位置=%d / industryCustom の位置=%d" % (p, c))

if ISC:
    check("K2 自由入力をキーにするのは一覧が未選択のときだけ",
          "!" in ISC and "industrySelect" in ISC and "industryCustom" in ISC,
          "一覧の未選択を見ている=%s" % ("industrySelect" in ISC))

check("K3 照合の分岐は従来どおり（canonical は完全一致・自由入力は前方一致）",
      "matchesIndustry(e, key, isCustom)" in INDEX
      and "return a === key;" in INDEX
      and "a.indexOf(key) === 0 || key.indexOf(a) === 0" in INDEX, "")

# ---------------------------------------------------------------------------
# G. 生成指示書は変えない
# ---------------------------------------------------------------------------
if BLD:
    check("G1 ★生成指示書の業種は従来どおり自由入力が優先（出力を変えない）",
          "const resolved = custom || preset;" in BLD,
          "resolved = custom || preset")
    check("G2 業種は preset/custom/resolved の3つを載せる（形を変えない）",
          "industry: { preset: preset, custom: custom, resolved: resolved }" in BLD, "")

# ---------------------------------------------------------------------------
# C. チップ
# ---------------------------------------------------------------------------
if REN:
    check("C1 ★チップを render() が書かない（入力から別に組み立てない）",
          "industryChip" not in REN, "render() 内の industryChip=%s" % ("あり" if "industryChip" in REN else "なし"))

if FIL:
    n = len(re.findall(r"setIndustryChip\(", FIL))
    check("C2 ★チップは絞り込みの分岐ごとに書く（結果と食い違わせない）",
          n >= 6, "setIndustryChip の呼び出し=%d 箇所" % n)
    check("C3 全件へ落ちたらチップもそう言う",
          "すべての実績を表示中" in FIL, "")
    check("C4 業種未選択のときは「選ぶと絞られる」と伝える",
          "業種を選ぶと" in FIL, "")

check("C5 カタログ未接続のときチップが「表示中」と言わない",
      "実績カタログに未接続" in INDEX, "")

check("C6 動的値は textContent（innerHTML を導入していない）",
      ".innerHTML" not in INDEX, "innerHTML=%s" % (".innerHTML" in INDEX))

# ---------------------------------------------------------------------------
# W. 画面の言葉
# ---------------------------------------------------------------------------
check("W1 欄のラベルが「または」でなくなっている（打ち消す建て付けをやめた）",
      "または自由入力" not in INDEX and "くわしい業種（任意）" in INDEX, "")

check("W2 両方使えることと、絞り込みに使うのは一覧であることを書いている",
      "両方お使いいただけます" in INDEX
      and "参考にする素材の絞り込みには「一覧から選ぶ」を使います" in INDEX, "")

print("=" * 78)
print("KLK-127 業種の絞り込みキーとチップの整合 チェック")
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
