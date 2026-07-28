#!/usr/bin/env python3
"""
KLK-036 acceptance-condition checker (static / no browser required).

GALLERY プール化（§12.1.3・GALLERY を archetype 固定から「単セクション独立プール」へ移行・pat-slider 追加）の
静的受け入れ条件（docs/designs/KLK-036.md §9）を検証する。

  縦串 生成規約   .claude/skills/draft-generate/templates/DRAFT_RULES.md（§12.1.3 の GALLERY プール表・割り当て表）
  主 golden       tests/fixtures/klk036/{index-a/b/c,compare}.html + instruction.json（1col×below-hero=offset3→(3,0,1)・案A=pat-slider）
  既存 golden     tests/fixtures/klk023・klk034・klk034b（1col×top=offset0→(0,1,2)＝GALLERYマーカー不変を確認）
  ドリフト検出    DRAFT_RULES §12.1.3 本文の GALLERY プール表・割り当て表 ＝ check_klk034.py の GALLERY_POOL/GALLERY_ASSIGN（ast 抽出）

check_klk035.py と同型（正規表現・文字列・Python標準のみ・exit 0/1・ネットワーク非使用・実行副作用を避けるため import せず ast）。

Run: python3 tests/site/check_klk036.py
Exit code 0 = all pass, 1 = at least one fail.
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()

EXPECT_N = 4  # GALLERY プールの型数
NEW_MARKER = "pat-slider"

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# DRAFT_RULES §12.1.3 本文パース（GALLERY プールの正）
# ---------------------------------------------------------------------------
def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_gallery_pool():
    # §12.1.3 (1) GALLERY プール表から `pat-...` マーカーを出現順（index順）に
    # KLK-037 で §12.1.3 (1) は「セクション別型プール（GALLERY/HERO/ABOUT）」に一般化・GALLERY プールは "**GALLERY プール" 節
    seg = _seg("**GALLERY プール", "**HERO プール")
    seen = []
    for m in re.finditer(r'`(pat-[a-z-]+)`', seg):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def parse_gallery_assign():
    # KLK-040 で (2) が型数別2表（GALLERY mod4 ＋ HERO/ABOUT mod6）に。GALLERY(mod4)表だけを読む。
    seg = _seg("**GALLERY（4型", "**HERO/ABOUT（6型")
    asn = {}
    for m in re.finditer(r'^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|', seg, re.M):
        o, a, b, c = (int(x) for x in m.groups())
        asn[o] = (a, b, c)
    return asn


G_POOL = parse_gallery_pool()
G_ASSIGN = parse_gallery_assign()

# §12.1.2 オフセット表（GALLERY と共有）を DRAFT_RULES から取得
def parse_offset():
    seg = _seg("**(2) オフセット表", "**(3) 割り当て表")
    off = {}
    for m in re.finditer(r'`(1col|2col-[a-z-]+|3col)`\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|', seg):
        off[(m.group(1), "top")] = int(m.group(2))
        off[(m.group(1), "below-hero")] = int(m.group(3))
    return off


OFFSET = parse_offset()


# ---------------------------------------------------------------------------
# check_klk034.py の GALLERY_POOL / GALLERY_ASSIGN を ast で安全抽出（import せず）
# ---------------------------------------------------------------------------
def consts_from(path, names):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in names:
                    out[t.id] = ast.literal_eval(node.value)
    return out


C34 = consts_from(os.path.join(ROOT, "tests", "site", "check_klk034.py"),
                  {"GALLERY_POOL", "GALLERY_ASSIGN", "DEFAULT_1211"})


# ---------------------------------------------------------------------------
# golden ユーティリティ
# ---------------------------------------------------------------------------
def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def attr(html, name):
    m = re.search(r'%s="([^"]+)"' % re.escape(name), html)
    return m.group(1) if m else None


def gallery_marker(html):
    m = re.search(r'class="m-gallery (pat-[a-z-]+)"', html)
    return m.group(1) if m else None


def all_pins(html):
    return set(re.findall(r'class="pin">([A-Z0-9-]+)<', html))


def m_main(html):
    m = re.search(r"--m-main\s*:\s*(#[0-9a-fA-F]{3,8})", html)
    return m.group(1).lower() if m else None


def css_layout_rule(html, token):
    if not token:
        return False
    for m in re.finditer(r'\.%s\b[^{}]*\{([^}]*)\}' % re.escape(token), html):
        if re.search(r'grid-template-columns|flex-direction|grid-auto|grid-column|grid-row|order\s*:|flex-wrap|overflow-x', m.group(1)):
            return True
    return False


def no_ext_deps(html):
    return not (re.search(r'<link\b[^>]*rel=["\']?stylesheet', html, re.I)
                or re.search(r'<script\b[^>]*\bsrc=', html, re.I)
                or re.search(r'fonts\.(googleapis|gstatic)\.com|cdn\.|unpkg\.com|jsdelivr', html, re.I)
                or re.search(r'<img\b[^>]*\bsrc=["\']?https?:', html, re.I))


def distinct3(vals):
    return len(set(vals)) == 3 and all(v is not None for v in vals)


K36 = {ltr: gread("klk036", "index-%s.html" % ltr) for ltr in ("a", "b", "c")}
K36_COMPARE = gread("klk036", "compare.html")


# ===========================================================================
# G1 本文パース: GALLERY プール4型・index3=pat-slider・順序
# ===========================================================================
g1 = (len(G_POOL) == EXPECT_N and G_POOL[0] == "pat-grid" and G_POOL[3] == NEW_MARKER)
check("G1 §12.1.3 GALLERY プール (4型・index0=pat-grid・index3=pat-slider)", g1, "pool=%s" % G_POOL)

# G2 割り当て表: 6行・巡回 mod4・各行3値distinct
g2_rows = (len(G_ASSIGN) == 6)
g2_cyc = all(G_ASSIGN[o] == (o % 4, (o + 1) % 4, (o + 2) % 4) for o in G_ASSIGN)
g2_dist = all(len(set(G_ASSIGN[o])) == 3 for o in G_ASSIGN)
check("G2 GALLERY 割り当て表 (6行・巡回(o,o+1,o+2)mod4・各行3値distinct)",
      g2_rows and g2_cyc and g2_dist, "assign=%s" % G_ASSIGN)

# G3 到達可能性: オフセット表の値集合から全 index{0..3} に到達（案A index=offset%4）
reach = set()
for (col, nav), off in OFFSET.items():
    reach.add(G_ASSIGN[off][0])
    reach.add(G_ASSIGN[off][1])
    reach.add(G_ASSIGN[off][2])
check("G3 到達可能性 (オフセット表の全offsetから GALLERY index{0..3} 全到達＝pat-slider含む)",
      reach >= set(range(EXPECT_N)), "到達index=%s" % sorted(reach))

# G4 ドリフト検出: 本文 §12.1.3 の GALLERY プール/割り当て ＝ check_klk034 の GALLERY_POOL/GALLERY_ASSIGN
d_pool = (G_POOL == list(C34.get("GALLERY_POOL", [])))
d_assign = (G_ASSIGN == C34.get("GALLERY_ASSIGN"))
d_no_gallery_in_1211 = ("GALLERY" not in (C34.get("DEFAULT_1211") or {}))
check("G4 ドリフト検出 (本文§12.1.3 = check_klk034 GALLERY_POOL/ASSIGN・DEFAULT_1211からGALLERY除外)",
      d_pool and d_assign and d_no_gallery_in_1211,
      "pool一致=%s assign一致=%s 1211からGALLERY除外=%s" % (d_pool, d_assign, d_no_gallery_in_1211))

# G5 klk036 表引き: 1col×below-hero=offset3→(3,0,1)＝案A=pat-slider/案B=pat-grid/案C=pat-wide
off36 = OFFSET[("1col", "below-hero")]
idxs36 = G_ASSIGN[off36]
exp36 = tuple(G_POOL[i] for i in idxs36)
act36 = tuple(gallery_marker(K36[l]) for l in ("a", "b", "c"))
g5 = (off36 == 3 and idxs36 == (3, 0, 1) and act36 == exp36)
check("G5 klk036 表引き (1col×below-hero→offset3→(3,0,1)・案A=pat-slider/案B=pat-grid/案C=pat-wide)",
      g5, "offset=%d idxs=%s 期待%s 実%s" % (off36, idxs36, exp36, act36))

# G6 pat-slider の実CSS差 (flex-wrap:nowrap;overflow-x:auto 系の横スクロール) が案A に存在
g6 = css_layout_rule(K36["a"], "pat-slider") and \
    ("flex-wrap" in K36["a"] and "overflow-x" in K36["a"])
check("G6 pat-slider 実CSS差 (横スクロール flex-wrap:nowrap/overflow-x:auto を伴う・飾りでない)",
      g6, "css_layout_rule=%s flex-wrap/overflow-x=%s" % (
          css_layout_rule(K36["a"], "pat-slider"), "flex-wrap" in K36["a"] and "overflow-x" in K36["a"]))

# G7 既存 golden 不変 (klk023/034/034b の 1col×top=offset0→GALLERY=(pat-grid,pat-wide,pat-mosaic))
g7_ok = True
g7_det = []
for name in ("klk023", "klk034", "klk034b"):
    got = tuple(gallery_marker(gread(name, "index-%s.html" % l)) for l in ("a", "b", "c"))
    exp = ("pat-grid", "pat-wide", "pat-mosaic")
    ok = (got == exp)
    g7_ok = g7_ok and ok
    g7_det.append("%s: %s %s" % (name, got, "OK" if ok else "NG"))
check("G7 既存golden不変 (klk023/034/034b の GALLERY=offset0=(pat-grid,pat-wide,pat-mosaic))",
      g7_ok, "; ".join(g7_det))

# G8 klk036 健全性: 番地6種各1・@media print・アタリa・外部依存0・プレースホルダ・archetype distinct・GALLERY distinct
WANT = {"NAV-01", "MV-01", "ABOUT-01", "GALLERY-01", "CTA-01", "FOOTER-01"}
g8_ok = True
g8_det = []
for l in ("a", "b", "c"):
    h = K36[l]
    ok = (all_pins(h) == WANT and "@media print" in h and 'class="atari"' in h and no_ext_deps(h)
          and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h)
          and attr(h, "data-columns") == "1col" and attr(h, "data-nav-position") == "below-hero")
    g8_ok = g8_ok and ok
    if not ok:
        g8_det.append("%s: 番地=%s print=%s 依存0=%s" % (l, all_pins(h) == WANT, "@media print" in h, no_ext_deps(h)))
g8_ok = g8_ok and distinct3([attr(K36[l], "data-archetype") for l in ("a", "b", "c")]) \
    and distinct3([gallery_marker(K36[l]) for l in ("a", "b", "c")]) \
    and distinct3([m_main(K36[l]) for l in ("a", "b", "c")])
check("G8 klk036 健全性 (番地6種各1・print・アタリa・依存0・PH・1col/below-hero・archetype/GALLERY/main distinct)",
      g8_ok, "; ".join(g8_det) if g8_det else "3案とも健全・distinct")

# G9 ABOUT は §12.1.3 プールへ移譲済み（KLK-037/040）。ABOUT の型数・表引きの詳細は check_klk037 が担当（GALLERY版の本チェッカは
#   ABOUT の具体値に依存しない＝mod4/mod6 の変更に非依存）。ここでは klk036 の ABOUT が案間distinct・img-* 語彙内であることのみ確認。
abt = [re.search(r'class="m-about (img-[a-z-]+)"', K36[l]) for l in ("a", "b", "c")]
abt = [m.group(1) if m else None for m in abt]
g9 = distinct3(abt) and all(a and a.startswith("img-") for a in abt)
check("G9 ABOUT §12.1.3 プール移譲済み (klk036 の ABOUT が案間distinct・img-*語彙。詳細な表引きは check_klk037)",
      g9, "about=%s" % abt)

# G10 規約文言: §12.1.3 見出し・pat-slider・SKILL 追記・§12.2/§14 の §12.1.3 対応（KLK-037で GALLERY→GALLERY/HERO/ABOUT に一般化済み）
g10_rules = ("#### 12.1.3" in RULES and "pat-slider" in RULES
             and "本表から除外" in RULES)  # §12.2 席替え表からの §12.1.3 移譲注記
g10_skill = ("§12.1.3" in SKILL and "pat-slider" in SKILL)
g10_regen = ("GALLERY-01" in RULES and "§12.1.3 の割り当て表" in RULES)  # §14 再付与に §12.1.3
check("G10 規約文言 (§12.1.3新設・pat-slider・移譲注記・§12.2本表から除外・§14再付与・SKILL)",
      g10_rules and g10_skill and g10_regen,
      "RULES=%s SKILL=%s §14=%s" % (g10_rules, g10_skill, g10_regen))

# Report
print("=" * 78)
print("KLK-036 static acceptance checks (docs/designs/KLK-036.md §9 を正とする)")
print("対象: DRAFT_RULES §12.1.3 本文パース / check_klk034 GALLERY定数(ast) / fixtures klk036・klk023・klk034(b)")
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
print()
print("D群（test_palette_klk036.py）: Quality Gate 全緑 / fixtures の git 追跡")
print("M群（tester 手動・ブラウザ）: GALLERY 選択時に案A で横スライダー(pat-slider)が見た目に現れる")
sys.exit(1 if failed else 0)
