#!/usr/bin/env python3
"""
KLK-092 acceptance-condition checker (static / no browser required).

1案生成でも幅切替・🔄 セクション再生成が使えるようにする（機能の同等化）。

★このチェッカーが守っているもの:
  幅切替も 🔄 も **compare.html の上に載っている**。`variants:1` で compare.html を
  作らないと、その2機能が**丸ごと失われる**。理恵さんの実使用で発覚した。
  規約自身が「1案には幅切替が無い」と書いてしまっていたのが根であり、
  **仕様の文章が機能の欠落を正当化していた**。同じことを繰り返さないよう、
  「案数によらず compare.html を出す」を規約・スキル・検査の3点で固定する。

  R群 = 規約 / K群 = スキル / T群 = 検証の道具

Run: python3 tests/site/check_klk092.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = io.open(
    os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"),
    encoding="utf-8",
).read()
SKILL = io.open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"),
                encoding="utf-8").read()
TOOL = io.open(os.path.join(ROOT, "tools", "verify-mockup.py"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def seg(text, start, end):
    i = text.find(start)
    if i < 0:
        return ""
    j = text.find(end, i + len(start))
    return text[i:j if j > 0 else len(text)]


S13 = seg(RULES, "## 13. 比較画面", "\n## 14.")
SSINGLE = seg(RULES, "**単案（`variants:1`）の compare.html（KLK-092）:**", "**依存・安全:**")

# ===========================================================================
# R群 — 規約
# ===========================================================================
check(
    "R1 §13 が「案数によらず compare.html を生成する」と定めている",
    "**`output.variants` の値によらず**" in S13,
    "明記=%s" % ("**`output.variants` の値によらず**" in S13),
)
check(
    "R2 §13 が「1案だからといって機能を落とさない」と理由つきで書いている",
    "1案だからといって機能を落とさない" in S13 and "丸ごと失われる" in S13,
    "理由=%s" % ("丸ごと失われる" in S13),
)
check(
    "R3 単案 compare.html の構造規約がある（何を落とし何を残すかの対応表）",
    bool(SSINGLE) and "案切替に関わる部分だけ" in SSINGLE,
    "節=%s（%d字）" % (bool(SSINGLE), len(SSINGLE)),
)
check(
    "R4 単案でも幅切替と 🔄 を出すと定めている",
    "出す（同じもの）" in SSINGLE and "🔄 セクション再生成" in SSINGLE,
    "幅切替=%s / 🔄=%s" % ("出す（同じもの）" in SSINGLE, "🔄 セクション再生成" in SSINGLE),
)
check(
    "R5 単案では案切替・サムネイルを出さないと定めている",
    "出さない" in SSINGLE and "thumbstrip" in SSINGLE,
    "案切替を落とす=%s" % ("thumbstrip" in SSINGLE),
)
check(
    "R6 ★letter は空文字・data-variants=\"1\" を焼き込むと定めている（404 の落とし穴）",
    'data-variants="1"' in SSINGLE and "必ず空文字を返す" in SSINGLE
    and "404" in SSINGLE,
    "マーカー=%s / 空文字=%s / 404の警告=%s"
    % ('data-variants="1"' in SSINGLE, "必ず空文字を返す" in SSINGLE, "404" in SSINGLE),
)
check(
    "R7 単案の iframe・原寸・印刷が index.html を指すと定めている",
    "`index.html`" in SSINGLE,
    "index.html=%s" % ("`index.html`" in SSINGLE),
)
check(
    "R8 §13 骨格8 の「1案には幅切替が無い」が撤回されている",
    "KLK-092 で撤回" in S13 and "`variants:1` でも幅切替は出す" in S13,
    "撤回=%s" % ("KLK-092 で撤回" in S13),
)
check(
    "R9 §0 と §9 の古い記述（比較ハブなし／compare.html は作らない）が消えている",
    "`variants:1` は比較ハブなし" not in RULES
    and "**`compare.html` は作らない**" not in RULES,
    "§0の残存=%s / §9の残存=%s"
    % ("`variants:1` は比較ハブなし" in RULES, "**`compare.html` は作らない**" in RULES),
)
check(
    "R10 §9 の保存ファイル表で variants:1 に compare.html が載っている",
    "**`compare.html`（単案版・KLK-092）**" in RULES,
    "表=%s" % ("**`compare.html`（単案版・KLK-092）**" in RULES),
)

# ===========================================================================
# K群 — スキル（規約に書いただけでは実行されない）
# ===========================================================================
check(
    "K1 SKILL の成果物一覧で variants:1 に compare.html が載っている",
    "**`compare.html`（KLK-092・単案版）**" in SKILL,
    "成果物=%s" % ("**`compare.html`（KLK-092・単案版）**" in SKILL),
)
check(
    "K2 SKILL が「1案でも機能を落とさない」を明記している",
    "★1案でも機能を落とさない（KLK-092" in SKILL,
    "明記=%s" % ("★1案でも機能を落とさない（KLK-092" in SKILL),
)
check(
    "K3 SKILL が letter 空文字と data-variants を指示している",
    "必ず空文字を返す" in SKILL and 'data-variants="1"' in SKILL,
    "letter=%s / マーカー=%s" % ("必ず空文字を返す" in SKILL, 'data-variants="1"' in SKILL),
)
check(
    "K4 SKILL の保存ファイル節にも単案 compare.html が書かれている",
    "単案版・KLK-092" in SKILL,
    "保存節=%s" % ("単案版・KLK-092" in SKILL),
)
check(
    "K5 SKILL に「compare.html は作らない」が残っていない",
    "`compare.html` は作らない" not in SKILL,
    "残存=%s" % ("`compare.html` は作らない" in SKILL),
)

# ===========================================================================
# T群 — 検証の道具
# ===========================================================================
check(
    "T1 verify-mockup に compare.html の機能同等性チェックがある",
    "def check_compare(" in TOOL and "check_compare(folder)" in TOOL,
    "関数=%s" % ("def check_compare(" in TOOL),
)
check(
    "T2 compare.html が無いことを検出する",
    "compare.html がありません（幅切替と 🔄 セクション再生成が使えない状態）" in TOOL,
    "検出=%s" % ("compare.html がありません" in TOOL),
)
check(
    "T3 幅切替と 🔄 の欠落を検出する（案数によらず）",
    'name="vw"' in TOOL and "vw375" in TOOL and 'id="regen-addr"' in TOOL
    and "/sections?folder=" in TOOL,
    "幅切替=%s / 🔄=%s" % ("vw375" in TOOL, 'id="regen-addr"' in TOOL),
)
check(
    "T4 単案固有の誤り（案切替の残存・data-variants 欠落・index-a.html 参照）を検出する",
    "単案なのに案切替のラジオがあります" in TOOL
    and "JS が letter を誤る" in TOOL
    and "404 になる" in TOOL,
    "3種=%s" % all(t in TOOL for t in ("単案なのに案切替のラジオがあります",
                                       "JS が letter を誤る", "404 になる")),
)

print("=" * 78)
print("KLK-092 1案生成でも機能を同等にする 静的チェック")
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
