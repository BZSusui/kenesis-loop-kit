#!/usr/bin/env python3
"""
KLK-075 acceptance-condition checker (static / no browser required).

KLK-072/073 の規約が**実際には守られなかった**3点と、panel-band の全幅化を検証する。

★この checker が守っているもの:
  **横断ルール（§3.0 比率・§8.1 狭カラム）が、型定義の表現より優先されること。**
  型プールの説明にある「横長」「横帯ワイド」「左右交互」といった語は既存で数が多く、
  後から足した横断ルールより**強く効いてしまう**。実際に規約追加後の再生成で
  `aspect-ratio:16/7` の地図・2カラムで横並びの voice-zigzag・全部1×1の masonry が出た。
  優先関係を明文化し、型定義側の紛らわしい表現も除いた状態を保つ。

Run: python3 tests/site/check_klk075.py
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


def seg(start, end):
    i = RULES.find(start)
    return RULES[i:RULES.find(end, i)] if i >= 0 else ""


SEG30 = seg("### 3.0 アタリ枠の比率", "### 3.1")
SEG81 = seg("### 8.1 狭い本文カラムでの畳み方", "\n## ")

# ---------------------------------------------------------------------------
# 優先関係の明文化
# ---------------------------------------------------------------------------
check(
    "C1 §3.0 が「型定義の表現より優先する」と明記している",
    "型定義の表現より優先する" in SEG30 and "極端な比率を意味しない" in SEG30,
    "優先の明記=%s / 語の否定=%s"
    % ("型定義の表現より優先する" in SEG30, "極端な比率を意味しない" in SEG30),
)
check(
    "C2 §3.0 が実際に負けた3箇所を実例として挙げている（再発の目印）",
    all(k in SEG30 for k in ("map-atari", "pat-wide", "img-top")) and "16/7" in SEG30,
    "実例=%s" % {k: (k in SEG30) for k in ("map-atari", "pat-wide", "img-top")},
)
check(
    "C3 §3.0 が「迷ったら 4/3・型の説明文は例外の根拠にならない」と書いている",
    "判断に迷ったら 4/3" in SEG30 and "例外の根拠にならない" in SEG30,
    "迷ったら4/3=%s / 根拠にならない=%s"
    % ("判断に迷ったら 4/3" in SEG30, "例外の根拠にならない" in SEG30),
)
check(
    "C4 §8.1 が「型定義より優先する」と明記し、左右交互の型も対象だとしている",
    "この規律は型定義より優先する" in SEG81 and "左右交互" in SEG81
    and "voice-zigzag" in SEG81,
    "優先=%s / 左右交互への言及=%s / zigzag=%s"
    % ("この規律は型定義より優先する" in SEG81, "左右交互" in SEG81, "voice-zigzag" in SEG81),
)
check(
    "C5 §8.1 の対象に zigzag 系・ABOUT の左右型・feature-large が入っている",
    all(k in SEG81 for k in ("voice-zigzag", "flow-zigzag", "staff-zigzag",
                             "img-left", "img-overlap", "feature-large")),
    "対象=%s" % {k: (k in SEG81) for k in ("voice-zigzag", "flow-zigzag", "staff-zigzag",
                                          "img-left", "img-overlap", "feature-large")},
)
check(
    "C6 §8.1 が縦積み時に order 反転を外すよう指示している",
    "`order` 反転も、縦積みにしたら不要" in SEG81,
    "指示=%s" % ("`order` 反転も、縦積みにしたら不要" in SEG81),
)

# ---------------------------------------------------------------------------
# 型定義側の紛らわしい表現を除いたか
# ---------------------------------------------------------------------------
_w = re.search(r"\|\s*1\s*\|\s*`pat-wide`.*?\n", RULES)
PATWIDE = _w.group(0) if _w else ""
check(
    "C7 pat-wide の定義から「大判横長」が消え、4/3 の参照が入っている",
    bool(PATWIDE) and "大判横長" not in PATWIDE and "4/3" in PATWIDE
    and "極端に平たくしない" in PATWIDE,
    "旧表現の残存=%s / 4/3=%s" % ("大判横長" in PATWIDE, "4/3" in PATWIDE),
)
_t = re.search(r"\|\s*2\s*\|\s*`img-top`.*?\n", RULES)
IMGTOP = _t.group(0) if _t else ""
check(
    "C8 img-top の定義から「横長画像」が消え、4/3 の参照が入っている",
    bool(IMGTOP) and "横長画像" not in IMGTOP and "4/3" in IMGTOP,
    "旧表現の残存=%s / 4/3=%s" % ("横長画像" in IMGTOP, "4/3" in IMGTOP),
)

# ---------------------------------------------------------------------------
# masonry の具体化
# ---------------------------------------------------------------------------
_m = re.search(r"\|\s*4\s*\|\s*`pat-masonry`.*?\n", RULES)
MASONRY = _m.group(0) if _m else ""
check(
    "C9 masonry が抽象指示ではなく、選べる具体構成（A/B/C）を示している",
    bool(MASONRY) and "(A) 8タイル" in MASONRY and "(B) 6タイル" in MASONRY
    and "(C) 12タイル" in MASONRY,
    "構成の提示=%s" % {k: (k in MASONRY) for k in ("(A) 8タイル", "(B) 6タイル", "(C) 12タイル")},
)
check(
    "C10 masonry が「全部 1×1 はベントーではない」と明記している（実際に起きた失敗）",
    bool(MASONRY) and "全部 1×1 はベントー型ではない" in MASONRY
    and "必ず大小を混在させる" in MASONRY,
    "明記=%s" % ("全部 1×1 はベントー型ではない" in MASONRY),
)

# ---------------------------------------------------------------------------
# panel-band の全幅化
# ---------------------------------------------------------------------------
_p = re.search(r"\|\s*5\s*\|\s*`panel-band`.*?\n", RULES)
PANEL = _p.group(0) if _p else ""
check(
    "C11 panel-band が auto-fit で列数可変になり、max-height を付けない",
    bool(PANEL) and "auto-fit" in PANEL and "minmax(220px,1fr)" in PANEL
    and "`max-height` は付けない" in PANEL,
    "auto-fit=%s / minmax=%s / max-height撤廃=%s"
    % ("auto-fit" in PANEL, "minmax(220px,1fr)" in PANEL, "`max-height` は付けない" in PANEL),
)
check(
    "C12 panel-band が MV の左右いっぱいまで伸びる指示を持つ",
    bool(PANEL) and "左右いっぱいまで伸ばす" in PANEL and "margin-inline" in PANEL,
    "全幅の指示=%s / 実装=%s" % ("左右いっぱいまで伸ばす" in PANEL, "margin-inline" in PANEL),
)
# 「旧実装は … だった」という**経緯の説明**には旧の値が出てよい（むしろ再発防止に役立つ）。
# 検査したいのは**指示部分**に旧実装が残っていないこと。説明部分（「なぜ auto-fit か」以降）を除いて見る。
_j = PANEL.find("**なぜ `auto-fit` か")
PANEL_INSTR = PANEL[:_j] if _j > 0 else PANEL
check(
    "C13 panel-band の**指示部分**に旧実装（repeat(6,1fr) / max-height:150px）が残っていない",
    bool(PANEL_INSTR) and "repeat(6,1fr)" not in PANEL_INSTR
    and "max-height:150px" not in PANEL_INSTR,
    "指示部分の旧列指定=%s / 旧max-height=%s（説明部分の言及は可）"
    % ("repeat(6,1fr)" in PANEL_INSTR, "max-height:150px" in PANEL_INSTR),
)
check(
    "C14 panel-band が 3/2 を維持している（理恵さんの判断・KLK-043）",
    bool(PANEL) and re.search(r"aspect-ratio:\s*3\s*/\s*2", PANEL) is not None,
    "3/2 の維持=%s" % (re.search(r"aspect-ratio:\s*3\s*/\s*2", PANEL) is not None),
)
check(
    "C15 panel-band に余りが出た理由と改善後の数値が記録されている",
    bool(PANEL) and "頭打ち" in PANEL and "余り270px" in PANEL and "224〜237px" in PANEL,
    "原因=%s / 実測=%s" % ("頭打ち" in PANEL, "余り270px" in PANEL),
)

# ---------------------------------------------------------------------------
# SKILL からの参照
# ---------------------------------------------------------------------------
check(
    "C16 SKILL.md が横断ルールの優先を明記している",
    "横断ルールは型定義より優先する" in SKILL and "迷ったら横断ルールに従う" in SKILL,
    "優先の明記=%s" % ("横断ルールは型定義より優先する" in SKILL),
)

print("=" * 78)
print("KLK-075 横断ルールの優先明記・masonry の具体化・panel-band の全幅化 静的チェック")
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
