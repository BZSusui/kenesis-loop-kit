#!/usr/bin/env python3
"""
KLK-073/074 acceptance-condition checker (static / no browser required).

見本の目視で出た「型の微調整」のうち、規約で解決するものを検証する。

  §8.1   狭い本文カラム（2col-*/3col）での畳み方（カード内の横並び禁止・列数を減らす）
  FLOW   番号枠を正方形に（画像を置く設計なら 4/3）
  HERO   overlap の白背景をキャッチの改行にあわせて可変に
  §4.1.1 AI が文言を書く場合の改行（句点で改行・最大2行・器の幅を内容にあわせる）
  §4.3.1 SCROLL ↓ はクリックできること（同一ページ内アンカー・JS不要）

★この checker が守っているもの:
  いずれも「**器の都合で中身が壊れる**」種類の不具合だった。
  幅が狭いのに横並びのまま／固定幅の器に長いキャッチ／飾りだけのスクロール誘導。
  規約に**判断の分かれ目（カラム構成・行数の上限・飛び先）**を書いて、生成側が迷わないようにする。

Run: python3 tests/site/check_klk073.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def section(start, end=None):
    i = RULES.find(start)
    if i < 0:
        return ""
    j = RULES.find(end, i) if end else RULES.find("\n### ", i + 1)
    return RULES[i:j] if j > i else RULES[i:]


# ---------------------------------------------------------------------------
# §8.1 狭い本文カラムでの畳み方
# ---------------------------------------------------------------------------
SEG81 = section("### 8.1 狭い本文カラムでの畳み方")
check(
    "B1 §8.1 があり、2col-*/3col で本文カラムが狭くなることを説明している",
    bool(SEG81) and "2col-*" in SEG81 and "3col" in SEG81 and "狭くなる" in SEG81,
    "節=%s / 対象の明示=%s" % (bool(SEG81), "2col-*" in SEG81 and "3col" in SEG81),
)
check(
    "B2 カード内の画像＋本文の横並びを禁じ、縦積み（画像が上）を指示している",
    "横並びにしてはならない" in SEG81 and "画像が上" in SEG81,
    "禁止=%s / 縦積みの指示=%s" % ("横並びにしてはならない" in SEG81, "画像が上" in SEG81),
)
check(
    "B3 対象の型が具体的に列挙されている（voice-two-col を含む）",
    "voice-two-col" in SEG81 and SEG81.count("`") >= 12,
    "voice-two-col=%s / 列挙の量=%d" % ("voice-two-col" in SEG81, SEG81.count("`")),
)
check(
    "B4 狭いカラムでも画像比率は 4/3 を維持すると明記（§3.0 との整合）",
    re.search(r"aspect-ratio:\s*4\s*/\s*3", SEG81) is not None and "正方や横長へ変えない" in SEG81,
    "4/3 の維持=%s" % (re.search(r"aspect-ratio:\s*4\s*/\s*3", SEG81) is not None),
)
check(
    "B5 セクション自体の列数も減らす指示がある（3列→2列 等）",
    "repeat(3,1fr)" in SEG81 and "repeat(2,1fr)" in SEG81,
    "列数削減の指示=%s" % ("repeat(3,1fr)" in SEG81 and "repeat(2,1fr)" in SEG81),
)
check(
    "B6 モバイル規律（§8）と独立であることが明記されている（二重適用の混乱防止）",
    "モバイル" in SEG81 and "独立" in SEG81,
    "明記=%s" % ("独立" in SEG81),
)

# ---------------------------------------------------------------------------
# FLOW 番号枠
# ---------------------------------------------------------------------------
_m = re.search(r"`flow-zigzag`（KLK-035・KLK-073調整）.*?(?=\n- \*\*STAFF)", RULES, re.S)
FLOWZ = _m.group(0) if _m else ""
check(
    "B7 flow-zigzag の番号枠を正方形にする指示がある",
    bool(FLOWZ) and re.search(r"aspect-ratio:\s*1\b", FLOWZ) is not None and "正方形" in FLOWZ,
    "正方形の指示=%s" % (bool(FLOWZ) and "正方形" in FLOWZ),
)
check(
    "B8 flow-zigzag で 1fr 1fr が不自然になる理由と、本文を広く取る指示がある",
    bool(FLOWZ) and "不自然に間延び" in FLOWZ and "本文側を広く取る" in FLOWZ,
    "理由=%s / 本文優先=%s"
    % ("不自然に間延び" in FLOWZ, "本文側を広く取る" in FLOWZ),
)
check(
    "B9 番号枠に画像を置く設計なら 4/3 とする分岐が書かれている（理恵さんの条件）",
    bool(FLOWZ) and "背景に画像" in FLOWZ and re.search(r"aspect-ratio:\s*4\s*/\s*3", FLOWZ) is not None,
    "分岐=%s" % (bool(FLOWZ) and "背景に画像" in FLOWZ),
)
check(
    "B10 flow-vertical-split の番号枠も正方形になっている",
    re.search(r"`flow-vertical-split`[^\n]*aspect-ratio:1", RULES) is not None,
    "指示=%s" % (re.search(r"`flow-vertical-split`[^\n]*aspect-ratio:1", RULES) is not None),
)

# ---------------------------------------------------------------------------
# HERO overlap の白背景
# ---------------------------------------------------------------------------
_m = re.search(r"\|\s*3\s*\|\s*`overlap`.*?\n", RULES)
OVL = _m.group(0) if _m else ""
check(
    "B11 HERO overlap の白背景をキャッチにあわせて可変にする指示がある",
    bool(OVL) and "可変にする" in OVL and "max-content" in OVL,
    "可変の指示=%s / 実装例=%s" % ("可変にする" in OVL, "max-content" in OVL),
)
check(
    "B12 固定幅だと二重折り返しになる理由（実例つき）が書かれている",
    bool(OVL) and "二重にかかり" in OVL and "不格好" in OVL,
    "理由=%s" % (bool(OVL) and "二重にかかり" in OVL),
)

# ---------------------------------------------------------------------------
# §4.1.1 改行 / §4.3.1 スクロール誘導
# ---------------------------------------------------------------------------
SEG411 = section("#### 4.1.1 AI が文言を書く場合の改行", "### 4.2")
check(
    "B13 §4.1.1 があり、AI が改行位置を決めて <br> を置くと明記されている",
    bool(SEG411) and "改行位置は AI が決めて" in SEG411 and "自動折り返し任せにしない" in SEG411,
    "節=%s / 明記=%s" % (bool(SEG411), "改行位置は AI が決めて" in SEG411),
)
check(
    "B14 句点での改行と行数上限（キャッチ2行）が書かれている",
    bool(SEG411) and "句点" in SEG411 and "最大2行" in SEG411,
    "句点=%s / 行数上限=%s" % ("句点" in SEG411, "最大2行" in SEG411),
)
SEG431 = section("#### 4.3.1 スクロール誘導", "\n---")
check(
    "B15 §4.3.1 があり、SCROLL ↓ をクリック可能にする指示がある",
    bool(SEG431) and "クリックできること" in SEG431 and "飾りテキストにしない" in SEG431,
    "節=%s / 明記=%s" % (bool(SEG431), "クリックできること" in SEG431),
)
check(
    "B16 実装が同一ページ内アンカー（JS不要）だと明記されている",
    bool(SEG431) and "同一ページ内アンカー" in SEG431 and "JS は使わない" in SEG431,
    "アンカー=%s / JS不要=%s"
    % ("同一ページ内アンカー" in SEG431, "JS は使わない" in SEG431),
)
check(
    "B17 2col-* での飛び先が .m-layout の先頭だと明記されている（サイドバー取り残し防止）",
    bool(SEG431) and ".m-layout" in SEG431 and "取り残され" in SEG431,
    "飛び先=%s / 理由=%s" % (".m-layout" in SEG431, "取り残され" in SEG431),
)
check(
    "B18 対象が SCROLL ↓ を出すすべての型だと明記されている",
    bool(SEG431) and "すべての型" in SEG431,
    "明記=%s" % ("すべての型" in SEG431),
)
check(
    "B19 center-scroll の型定義からも §4.3.1 を参照している",
    re.search(r"`center-scroll`[^\n]*§4\.3\.1", RULES) is not None,
    "参照=%s" % (re.search(r"`center-scroll`[^\n]*§4\.3\.1", RULES) is not None),
)

# ---------------------------------------------------------------------------
# SKILL.md からの参照
# ---------------------------------------------------------------------------
check(
    "B20 SKILL.md が §8.1 / §4.1.1 / §4.3.1 を参照している（生成時の見落とし防止）",
    all(k in SKILL for k in ("§8.1", "§4.1.1", "§4.3.1")),
    "参照=%s" % {k: (k in SKILL) for k in ("§8.1", "§4.1.1", "§4.3.1")},
)

print("=" * 78)
print("KLK-073/074 型ごとの調整（狭カラム畳み・FLOW正方・MV枠可変・改行・SCROLL）静的チェック")
print("対象: DRAFT_RULES §8.1 / FLOW / HERO overlap / §4.1.1 / §4.3.1 / SKILL.md")
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
