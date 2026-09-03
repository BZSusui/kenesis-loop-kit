#!/usr/bin/env python3
"""
KLK-072 acceptance-condition checker (static / no browser required).

Verifies A1-A10 from docs/designs/KLK-072.md §4.3 / §9:
画像アタリの比率を 4/3 に統一し、masonry の最終行の空白を塞ぐ規約変更。

  縦串 生成規約  .claude/skills/draft-generate/templates/DRAFT_RULES.md（§3.0 新設ほか）
  縦串 スキル    .claude/skills/draft-generate/SKILL.md（生成手順からの参照）

★この checker が守っているもの:
  アタリの高さを `min-height` だけで決めると、幅がコンテナ任せになり
  **サイドバーでは細長い帯・全幅では潰れる**という比率のばらつきが生まれる。
  §3.0 の既定（4/3）と、**意図して別の形にしている型の例外**の両方を守る。
  例外を失うと、KLK-043 で作り込んだ panel-band のフィルム帯や、正方前提の SNS/STAFF が壊れる。

  なお本 checker は**規約に必要な記述があるか**までを見る。規約が実際に効いたか
  （生成物の比率が 4/3 になるか）は KLK-074 の見本再生成で確認する。

Run: python3 tests/site/check_klk072.py
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


# §3.0 の節を切り出す
_i = RULES.find("### 3.0 アタリ枠の比率")
SEG30 = RULES[_i:RULES.find("### 3.1", _i)] if _i >= 0 else ""

check(
    "A1 DRAFT_RULES に §3.0 があり、既定が aspect-ratio: 4 / 3 と書かれている",
    bool(SEG30) and re.search(r"aspect-ratio:\s*4\s*/\s*3", SEG30) is not None
    and "既定とする" in SEG30,
    "節の検出=%s / 4/3 の記載=%s" % (bool(SEG30), bool(re.search(r"aspect-ratio:\s*4\s*/\s*3", SEG30))),
)
check(
    "A2 「min-height だけで高さを決めてはならない」旨がある",
    "`min-height` だけで高さを決めてはならない" in SEG30 and "横に長細い帯" in SEG30,
    "禁止の明記=%s / 理由の明記=%s"
    % ("`min-height` だけで高さを決めてはならない" in SEG30, "横に長細い帯" in SEG30),
)
exceptions = {
    "正方系": ("STAFF" in SEG30 and "sns-grid" in SEG30 and "img-circle" in SEG30
             and re.search(r"1\s*/\s*1", SEG30) is not None),
    "HERO全面": ("hero-atari" in SEG30 or "全面ビジュアル" in SEG30),
    "panel-band(3/2)": ("panel-band" in SEG30 and re.search(r"3\s*/\s*2", SEG30) is not None),
}
check(
    "A3 例外表に 正方系・HERO全面・panel-band(3/2) の3系統がある",
    all(exceptions.values()),
    "内訳=%s" % exceptions,
)
check(
    "A4 ACCESS の .map-atari が 4/3 の対象だと分かる",
    ".map-atari" in SEG30 and "ACCESS" in SEG30,
    "map-atari の言及=%s / ACCESS の言及=%s" % (".map-atari" in SEG30, "ACCESS" in SEG30),
)
check(
    "A5 map-top の曖昧な「aspect-ratio 横長」が残っていない（4/3 に確定）",
    "`aspect-ratio` 横長" not in RULES
    and re.search(r"map-top[^|]*\|[^|]*aspect-ratio:4/3", RULES) is not None,
    "曖昧記述の残存=%s / 4/3 の確定=%s"
    % ("`aspect-ratio` 横長" in RULES,
       bool(re.search(r"map-top[^|]*\|[^|]*aspect-ratio:4/3", RULES))),
)

# masonry の「手順」— 意図の記述だけでは不足（dense は穴を埋めるだけ、という誤解が事故を生んだ）
_m = re.search(r"\|\s*4\s*\|\s*`pat-masonry`.*?\n", RULES)
MASONRY = _m.group(0) if _m else ""
# KLK-075: 「span 合計を列数の倍数に」という抽象指示では守られず（11タイル全部1×1・最終行に空き）、
# **選べる具体構成(A)(B)(C)** に置き換えた。検査もその契約に合わせる。
check(
    "A6 pat-masonry に最終行を埋める手順がある（KLK-075 で具体構成に変更）",
    bool(MASONRY) and "最終行に空きを作らない" in MASONRY
    and "(A) 8タイル" in MASONRY and "必ず大小を混在させる" in MASONRY,
    "手順の記載=%s / 具体構成の提示=%s"
    % ("最終行に空きを作らない" in MASONRY, "(A) 8タイル" in MASONRY),
)
check(
    "A6b pat-masonry が dense の限界（穴を埋めるだけ）を説明している",
    "既存の穴を後続タイルで埋めるだけ" in MASONRY,
    "説明=%s" % ("既存の穴を後続タイルで埋めるだけ" in MASONRY),
)
_m = re.search(r"\|\s*3\s*\|\s*`sns-masonry`.*?\n", RULES)
SNSM = _m.group(0) if _m else ""
check(
    "A7 sns-masonry にも同じ規律への参照がある",
    bool(SNSM) and "最終行に空きを作らない" in SNSM,
    "参照=%s" % ("最終行に空きを作らない" in SNSM),
)
check(
    "A8 SKILL.md が §3.0 を参照している（生成時の見落とし防止）",
    "§3.0" in SKILL and re.search(r"aspect-ratio:\s*4\s*/\s*3", SKILL) is not None,
    "§3.0 参照=%s / 4/3 の記載=%s"
    % ("§3.0" in SKILL, bool(re.search(r"aspect-ratio:\s*4\s*/\s*3", SKILL))),
)

# ---- 例外の非回帰（既存の作り込みを壊していないか） ----
_m = re.search(r"\|\s*5\s*\|\s*`panel-band`.*?\n", RULES)
PANEL = _m.group(0) if _m else ""
check(
    "A9 HERO panel-band の 3/2 が維持されている（KLK-043 の非回帰）",
    bool(PANEL) and re.search(r"aspect-ratio:\s*3\s*/\s*2", PANEL) is not None,
    "panel-band の 3/2=%s" % bool(re.search(r"aspect-ratio:\s*3\s*/\s*2", PANEL)),
)
squares = {}
for t in ("sns-grid", "sns-reels", "img-circle"):
    _m = re.search(r"\|\s*\d+\s*\|\s*`%s`.*?\n" % re.escape(t), RULES)
    row = _m.group(0) if _m else ""
    squares[t] = bool(re.search(r"aspect-ratio:\s*1\b", row))
check(
    "A10 正方を前提とする型の aspect-ratio:1 が維持されている",
    all(squares.values()),
    "内訳=%s" % squares,
)

print("=" * 78)
print("KLK-072 画像アタリの比率統一（4/3）静的チェック")
print("対象: DRAFT_RULES §3.0・map-top・masonry×2 / SKILL.md")
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
