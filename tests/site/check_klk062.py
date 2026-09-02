#!/usr/bin/env python3
"""
KLK-062 acceptance-condition checker (static / no browser required).

Verifies W1-W13 from docs/designs/KLK-062.md §4.4 / §9:
比較画面の「画面幅プレビュー切替」（REQ-201 の改訂実装・CSS-only）。

  縦串 生成規約  .claude/skills/draft-generate/templates/DRAFT_RULES.md（§13 骨格8）
  縦串 スキル    .claude/skills/draft-generate/SKILL.md（生成手順）
  縦串 UI        draft-gen/index.html（スマホ設定の撤去・output.mobile の廃止）
  縦串 仕様      docs/SPEC.md（REQ-201 の改訂）
  golden         tests/fixtures/klk062/compare-width.html + index-a/b.html
                 （KLK-012 と同じ「変更に関係するファイルだけの絞った構成」）

既存 golden 28件の compare.html は **retrofit しない**（KLK-012 の前例。🔄 を持つのは 23/28 件）。
古い golden は当時の生成物のスナップショットとして正しい。

Run: python3 tests/site/check_klk062.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()
INDEX = open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
SPEC = open(os.path.join(ROOT, "docs", "SPEC.md"), encoding="utf-8").read()

FIX = os.path.join(ROOT, "tests", "fixtures", "klk062")
CMP = open(os.path.join(FIX, "compare-width.html"), encoding="utf-8").read()
IDX_A = open(os.path.join(FIX, "index-a.html"), encoding="utf-8").read()
IDX_B = open(os.path.join(FIX, "index-b.html"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# W1-W2 生成規約・スキル
# ---------------------------------------------------------------------------
_i = RULES.find("画面幅プレビュー切替")
SEG13 = RULES[_i:_i + 2200] if _i >= 0 else ""
check(
    "W1 DRAFT_RULES §13 に幅切替の規約（name=\"vw\"・プリセット3種）がある",
    bool(SEG13) and 'name="vw"' in SEG13 and "375px" in SEG13 and "768px" in SEG13 and "全幅" in SEG13,
    "節の検出=%s / name=vw=%s / 375px=%s / 768px=%s / 全幅=%s"
    % (bool(SEG13), 'name="vw"' in SEG13, "375px" in SEG13, "768px" in SEG13, "全幅" in SEG13),
)
check(
    "W1b 「JS を使わない」「スマホ版を二重生成しない」が規約とスキルの両方に明記されている",
    "追加 JS は使わない" in SEG13 and "二重生成せず" in SEG13 and "二重生成してはならない" in SKILL,
    "DRAFT_RULES: JS不使用=%s / 二重生成せず=%s ｜ SKILL: 二重生成の禁止=%s"
    % ("追加 JS は使わない" in SEG13, "二重生成せず" in SEG13, "二重生成してはならない" in SKILL),
)
check(
    "W2 SKILL.md の生成手順が幅切替に言及している",
    "画面幅プレビュー切替" in SKILL and 'name="vw"' in SKILL,
    "言及=%s / name=vw=%s" % ("画面幅プレビュー切替" in SKILL, 'name="vw"' in SKILL),
)

# ---------------------------------------------------------------------------
# W3-W8 golden（比較ハブ）
# ---------------------------------------------------------------------------
vw_radios = re.findall(r'<input type="radio" name="vw" id="(vw[a-z0-9]+)"[^>]*>', CMP)
vw_checked = re.search(r'<input type="radio" name="vw" id="vwfull"[^>]*\bchecked\b', CMP)
check(
    "W3 golden が name=\"vw\" の隠しラジオを3つ持ち、既定が全幅（vwfull に checked）",
    sorted(vw_radios) == ["vw375", "vw768", "vwfull"] and bool(vw_checked),
    "ラジオ=%s / vwfull checked=%s" % (vw_radios, bool(vw_checked)),
)
css768 = re.search(r"#vw768:checked\s*~\s*\.canvas\s+\.pane\s+iframe\s*\{[^}]*width:\s*768px", CMP)
css375 = re.search(r"#vw375:checked\s*~\s*\.canvas\s+\.pane\s+iframe\s*\{[^}]*width:\s*375px", CMP)
check(
    "W4 golden に CSS-only の幅切替規則（#vw768/#vw375 ~ .canvas .pane iframe）がある",
    bool(css768) and bool(css375),
    "768px規則=%s / 375px規則=%s" % (bool(css768), bool(css375)),
)
_p = CMP.find("@media print")
PRINT_BLK = CMP[_p:_p + 400] if _p >= 0 else ""
check(
    "W5 golden の @media print で .vwseg が隠れる",
    ".vwseg" in PRINT_BLK and "display: none" in PRINT_BLK,
    "print ブロック内 .vwseg=%s" % (".vwseg" in PRINT_BLK),
)
check(
    "W6 golden が幅切替に JS を使っていない（<script> 0件）",
    CMP.count("<script") == 0,
    "<script> 出現=%d" % CMP.count("<script"),
)
var_radios = re.findall(r'<input type="radio" name="variant" id="(r[abc])"[^>]*>', CMP)
var_css = re.search(r"#ra:checked\s*~\s*\.canvas\s+#paneA\s*\{[^}]*display:\s*block", CMP)
check(
    "W7 案切替（name=\"variant\"）が壊れていない（隠しラジオ＋兄弟結合子が健在）",
    len(var_radios) >= 2 and bool(var_css),
    "variant ラジオ=%s / #ra:checked ~ .canvas #paneA=%s" % (var_radios, bool(var_css)),
)
# KLK-071: 空白ゆれに強くする。実際の生成物は "@media (max-width:640px)" とスペース無しで書くため、
# 文字列一致で固定すると golden を実物で置き換えたときに「実物は正しいのに落ちる」ことになる。
_RESPONSIVE = re.compile(r"@media\s*\(\s*max-width\s*:\s*640px\s*\)")
check(
    "W8 iframe 先の golden がレスポンシブ（max-width:640px のメディアクエリ・空白ゆれ許容）",
    bool(_RESPONSIVE.search(IDX_A)) and bool(_RESPONSIVE.search(IDX_B)),
    "index-a=%s / index-b=%s"
    % (bool(_RESPONSIVE.search(IDX_A)), bool(_RESPONSIVE.search(IDX_B))),
)

# ---------------------------------------------------------------------------
# W9-W11 SCR-001
# ---------------------------------------------------------------------------
check(
    "W9 SCR-001 から #mobileOn / #mobileW が撤去されている",
    'id="mobileOn"' not in INDEX and 'id="mobileW"' not in INDEX,
    "mobileOn=%s / mobileW=%s" % ('id="mobileOn"' in INDEX, 'id="mobileW"' in INDEX),
)
# buildInstruction の中に mobile の格納が残っていないこと
_b = INDEX.find("function buildInstruction")
BUILD = INDEX[_b:INDEX.find("\n}", INDEX.find("return out;", _b))] if _b >= 0 else ""
check(
    "W10 SCR-001 の buildInstruction が output.mobile を出力しない",
    bool(BUILD) and not re.search(r"mobile\s*:", BUILD),
    "buildInstruction 内の 'mobile:' 出現=%s" % bool(re.search(r"mobile\s*:", BUILD)),
)
check(
    "W11 SCR-001 に比較画面で表示幅を切り替えられる案内がある",
    "表示幅を切り替え" in INDEX and ("375px" in INDEX or "375" in INDEX),
    "案内=%s" % ("表示幅を切り替え" in INDEX),
)

# ---------------------------------------------------------------------------
# W12 NFR-005 / W13 SPEC
# ---------------------------------------------------------------------------
ext = [u for u in re.findall(r'https?://[^"\'\s)]+', CMP) if "w3.org" not in u]
check(
    "W12 golden の比較ハブに外部URL参照が無い（NFR-005）",
    not ext,
    "外部URL=%s" % (ext or "なし"),
)
row201 = re.search(r"^\|\s*REQ-201\s*\|.*$", SPEC, re.M)
ROW = row201.group(0) if row201 else ""
check(
    "W13 SPEC REQ-201 が比較画面の幅プリセット切替へ改訂されている",
    bool(ROW) and "幅" in ROW and "375px" in ROW and "数値の任意指定は行わない" in ROW,
    "REQ-201 行の長さ=%d / 375px=%s / 数値指定しない旨=%s"
    % (len(ROW), "375px" in ROW, "数値の任意指定は行わない" in ROW),
)

print("=" * 78)
print("KLK-062 比較画面の画面幅プレビュー切替（REQ-201 改訂）静的チェック")
print("対象: DRAFT_RULES §13骨格8 / SKILL / SCR-001 / SPEC / fixtures klk062")
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
