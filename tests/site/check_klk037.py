#!/usr/bin/env python3
"""
KLK-037 acceptance-condition checker (static / no browser required).

HERO/ABOUT のプール化（§12.1.3・GALLERY と同機構へ移譲・新型 overlap/img-overlap 追加）の
静的受け入れ条件（docs/designs/KLK-037.md §9）を検証する。check_klk036.py（GALLERY版）が雛形。

  縦串 生成規約   .claude/skills/draft-generate/templates/DRAFT_RULES.md（§12.1.3 の HERO/ABOUT プール表・割り当て表）
  主 golden       tests/fixtures/klk036/{index-a/b/c}.html（1col×below-hero=offset3→(3,0,1)・案A=overlap/img-overlap）
  既存 golden     tests/fixtures/klk023/034/034b（1col×top=offset0→(0,1,2)＝HERO/ABOUT マーカー不変を確認）
  ドリフト検出    DRAFT_RULES §12.1.3 本文の HERO/ABOUT プール表・割り当て表 ＝ check_klk034.py の HERO_POOL/ABOUT_POOL/GALLERY_ASSIGN（ast 抽出）

★HERO 固有: overlap の整列シグネチャ(justify/align/text)が既存3型と非重複＝4型で全 distinct を機械検証（GALLERY版に無い H群固有チェック）。
Python標準のみ・exit 0/1・import せず ast。

Run: python3 tests/site/check_klk037.py
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()
REGEN = open(os.path.join(ROOT, ".claude", "skills", "draft-regenerate", "SKILL.md"), encoding="utf-8").read()

EXPECT_N = 6  # KLK-040: HERO/ABOUT を6型化
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# --- DRAFT_RULES §12.1.3 本文パース（HERO/ABOUT プール） ---
def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_pool(header_marker, end_marker, prefix_re):
    seg = _seg(header_marker, end_marker)
    seen = []
    for m in re.finditer(r'`(' + prefix_re + r')`', seg):
        v = m.group(1)
        if v not in seen:
            seen.append(v)
    return seen


# HERO プール表: 「**HERO プール（...）...:**」〜「**ABOUT プール」。data-hero 値は full/split/band/overlap（バッククォート）
HERO_POOL_RULES = parse_pool("**HERO プール", "**ABOUT プール", r"full|split|band|overlap|center-scroll|panel-band")
# ABOUT プール表: 「**ABOUT プール」〜「**(2) 割り当て表」。img-*
ABOUT_POOL_RULES = parse_pool("**ABOUT プール", "**(2) 割り当て表", r"img-[a-z-]+")


def parse_assign():
    # KLK-040: 割り当ては型数別2表。HERO/ABOUT 用の mod6 表を読む。
    seg = _seg("**HERO/ABOUT（6型", "- **offset0")
    asn = {}
    for m in re.finditer(r'^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|', seg, re.M):
        o, a, b, c = (int(x) for x in m.groups())
        asn[o] = (a, b, c)
    return asn


def parse_offset():
    seg = _seg("**(2) オフセット表", "**(3) 割り当て表")
    off = {}
    for m in re.finditer(r'`(1col|2col-[a-z-]+|3col)`\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|', seg):
        off[(m.group(1), "top")] = int(m.group(2))
        off[(m.group(1), "below-hero")] = int(m.group(3))
    return off


ASSIGN = parse_assign()
OFFSET = parse_offset()


# --- check_klk034.py の定数を ast で抽出（import せず） ---
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
                  {"HERO_POOL", "ABOUT_POOL", "GALLERY_ASSIGN", "POOL6_ASSIGN", "DEFAULT_1211"})


# --- golden ユーティリティ ---
def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def attr(html, name):
    m = re.search(r'%s="([^"]+)"' % re.escape(name), html)
    return m.group(1) if m else None


def about_marker(html):
    m = re.search(r'class="m-about (img-[a-z-]+)"', html)
    return m.group(1) if m else None


def all_pins(html):
    return set(re.findall(r'class="pin">([A-Z0-9-]+)<', html))


def hero_sig(html):
    """最初の .m-hero {...} 基底ブロックの (justify-content, align-items, text-align)。check_klk021/023 と同型。"""
    i = re.search(r'\.m-hero\s*\{', html)
    block = ""
    if i:
        j = html.find("{", i.end() - 1)
        depth = 0
        for k in range(j, len(html)):
            if html[k] == "{":
                depth += 1
            elif html[k] == "}":
                depth -= 1
                if depth == 0:
                    block = html[j:k + 1]
                    break

    def p(name):
        mm = re.search(name + r"\s*:\s*([a-zA-Z-]+)", block)
        return mm.group(1).lower() if mm else ""
    return (p("justify-content"), p("align-items"), p("text-align"))


def css_layout_rule(html, token):
    if not token:
        return False
    for m in re.finditer(r'\.%s\b[^{}]*\{([^}]*)\}' % re.escape(token), html):
        if re.search(r'grid-template-columns|flex-direction|grid-auto|grid-column|grid-row|order\s*:|flex-wrap|overflow-x', m.group(1)):
            return True
    return False


def hero_base_block(html):
    """最初の .m-hero {...} 基底ブロック本文を返す（hero_sig と同じ抽出）。HERO overlap は案別ファイルで基底に grid を書く。"""
    i = re.search(r'\.m-hero\s*\{', html)
    if not i:
        return ""
    j = html.find("{", i.end() - 1)
    depth = 0
    for k in range(j, len(html)):
        if html[k] == "{":
            depth += 1
        elif html[k] == "}":
            depth -= 1
            if depth == 0:
                return html[j:k + 1]
    return ""


def distinct3(vals):
    return len(set(vals)) == 3 and all(v is not None for v in vals)


K36 = {ltr: gread("klk036", "index-%s.html" % ltr) for ltr in ("a", "b", "c")}

# 期待整列シグネチャ（DRAFT_RULES §12.1.3 HERO プール記載のミラー）
HERO_SIG = {
    "full": ("center", "center", "center"),
    "split": ("space-between", "center", "left"),
    "band": ("flex-end", "flex-start", "left"),
    "overlap": ("flex-start", "center", "left"),
    "center-scroll": ("space-between", "center", "center"),
    "panel-band": ("flex-end", "center", "center"),
}


# ===========================================================================
# H1 本文パース: HERO プール4型・index3=overlap / ABOUT プール4型・index3=img-overlap
# ===========================================================================
h1 = (HERO_POOL_RULES == ["full", "split", "band", "overlap", "center-scroll", "panel-band"]
      and ABOUT_POOL_RULES == ["img-left", "img-right", "img-top", "img-overlap", "img-circle", "img-zigzag"])
check("H1 §12.1.3 HERO/ABOUT プール (各6型・HERO index4/5=center-scroll/panel-band・ABOUT index4/5=img-circle/img-zigzag)",
      h1, "HERO=%s ABOUT=%s" % (HERO_POOL_RULES, ABOUT_POOL_RULES))

# H2 割り当て表 6行・巡回mod6（HERO/ABOUT・KLK-040）・distinct
h2 = (len(ASSIGN) == 6 and all(ASSIGN[o] == (o % EXPECT_N, (o + 1) % EXPECT_N, (o + 2) % EXPECT_N) for o in ASSIGN)
      and all(len(set(ASSIGN[o])) == 3 for o in ASSIGN))
check("H2 割り当て表 (HERO/ABOUT用・6行・巡回mod6・各行distinct)", h2, "assign=%s" % ASSIGN)

# H3 到達可能性: 全offsetから index{0..5} 到達（新型 index3/4/5 含む）
reach = set()
for off in OFFSET.values():
    reach |= set(ASSIGN[off])
check("H3 到達可能性 (全offsetから index{0..5} 全到達＝overlap/center-scroll/panel-band 等含む)",
      reach >= set(range(EXPECT_N)), "到達=%s" % sorted(reach))

# H4 ドリフト検出: 本文 §12.1.3 プール = check_klk034 の HERO_POOL/ABOUT_POOL・mod6割り当て(POOL6_ASSIGN)・DEFAULT_1211からHERO/ABOUT除外
d_hero = (HERO_POOL_RULES == list(C34.get("HERO_POOL", [])))
d_about = (ABOUT_POOL_RULES == list(C34.get("ABOUT_POOL", [])))
d_assign = (ASSIGN == C34.get("POOL6_ASSIGN"))
d1211 = ("HERO" not in (C34.get("DEFAULT_1211") or {})) and ("ABOUT" not in (C34.get("DEFAULT_1211") or {}))
check("H4 ドリフト検出 (本文HERO/ABOUTプール = check_klk034 定数・mod6割り当て一致・DEFAULT_1211からHERO/ABOUT除外)",
      d_hero and d_about and d_assign and d1211,
      "HERO=%s ABOUT=%s assign=%s 1211除外=%s" % (d_hero, d_about, d_assign, d1211))

# H5 klk036 表引き: offset3→(3,4,5)・HERO=(overlap,center-scroll,panel-band)・ABOUT=(img-overlap,img-circle,img-zigzag)
off36 = OFFSET[("1col", "below-hero")]
idxs = ASSIGN[off36]
exp_hero = tuple(HERO_POOL_RULES[i] for i in idxs)
exp_about = tuple(ABOUT_POOL_RULES[i] for i in idxs)
act_hero = tuple(attr(K36[l], "data-hero") for l in ("a", "b", "c"))
act_about = tuple(about_marker(K36[l]) for l in ("a", "b", "c"))
h5 = (off36 == 3 and idxs == (3, 4, 5) and act_hero == exp_hero and act_about == exp_about)
check("H5 klk036 表引き (offset3→(3,4,5)・HERO=(overlap,center-scroll,panel-band)・ABOUT=(img-overlap,img-circle,img-zigzag))",
      h5, "HERO 期待%s 実%s / ABOUT 期待%s 実%s" % (exp_hero, act_hero, exp_about, act_about))

# H6 【HERO固有】整列シグネチャが6型で全distinct（新2型が既存4型と非重複）＋klk036の各案が型に対応
sig_all = list(HERO_SIG.values())
h6_pool_distinct = len(set(sig_all)) == EXPECT_N
h6_klk036 = True
h6_det = []
for l, t in zip(("a", "b", "c"), act_hero):
    sig = hero_sig(K36[l])
    want = HERO_SIG.get(t)
    ok = (sig == want)
    h6_klk036 = h6_klk036 and ok
    h6_det.append("%s(%s):%s%s" % (l, t, sig, "" if ok else "≠%s" % (want,)))
h6_klk036_distinct = distinct3([hero_sig(K36[l]) for l in ("a", "b", "c")])
check("H6 HERO整列シグネチャ (6型で全distinct＝新2型が既存と非重複・klk036各案が型に対応・3案distinct)",
      h6_pool_distinct and h6_klk036 and h6_klk036_distinct,
      "4型distinct=%s / klk036=%s / 3案distinct=%s" % (h6_pool_distinct, "; ".join(h6_det), h6_klk036_distinct))

# H7 overlap/img-overlap の実CSS差（grid実装・案A klk036）
#   HERO overlap は案別ファイルで `.m-hero` 基底に grid を書く（型別クラスを使わない＝hero_sig と同じ流儀）ので基底ブロックで検査。
#   ABOUT img-overlap は `.m-about.img-overlap` セレクタなので css_layout_rule で検査。
h7_hero = ("grid-template-columns" in hero_base_block(K36["a"])) and ("transform" in K36["a"]) \
    and (attr(K36["a"], "data-hero") == "overlap")
h7_about = css_layout_rule(K36["a"], "img-overlap") and ("transform" in K36["a"])
check("H7 overlap/img-overlap 実CSS差 (HERO=基底grid+transform重ね・ABOUT=.img-overlap grid+transform・飾りでない)",
      h7_hero and h7_about, "HERO overlap(基底grid)=%s / ABOUT img-overlap=%s" % (h7_hero, h7_about))

# H8 既存golden不変（offset0）: klk023/034/034b の HERO/ABOUT が offset0 プール席替え後の値のまま
#   klk023: 参考なし→(full,split,band)/(img-left,img-right,img-top)
#   klk034: refHERO=split→(split,full,band) / klk034b: refHERO=band→(band,split,full)。ABOUTは指定なし→(img-left,img-right,img-top)
h8_ok = True
h8_det = []
exp_map = {
    "klk023": (("full", "split", "band"), ("img-left", "img-right", "img-top")),
    "klk034": (("split", "full", "band"), ("img-left", "img-right", "img-top")),
    "klk034b": (("band", "split", "full"), ("img-left", "img-right", "img-top")),
}
for name, (eh, ea) in exp_map.items():
    gh = tuple(attr(gread(name, "index-%s.html" % l), "data-hero") for l in ("a", "b", "c"))
    ga = tuple(about_marker(gread(name, "index-%s.html" % l)) for l in ("a", "b", "c"))
    ok = (gh == eh and ga == ea)
    h8_ok = h8_ok and ok
    h8_det.append("%s: HERO%s%s ABOUT%s%s" % (name, gh, "" if gh == eh else "≠%s" % (eh,), ga, "" if ga == ea else "≠%s" % (ea,)))
check("H8 既存golden不変 (klk023/034/034b の HERO/ABOUT が offset0 の従来値・§12.1.3移譲で変わらない)",
      h8_ok, "; ".join(h8_det))

# H9 規約文言: §12.1.3 に HERO/ABOUT プール・overlap・§12.2 既定型表は空(KLK-044でMENUも§12.1.3へ)・§14 に MV-01/ABOUT-01・SKILL
h9_rules = ("overlap" in RULES and "img-overlap" in RULES
            and "HERO プール" in RULES and "ABOUT プール" in RULES
            and "MENU プール" in RULES  # KLK-044: MENU も §12.1.3 プールへ移譲
            and "MV-01" in RULES and "ABOUT-01" in RULES)  # §14 再付与対象
h9_skill = ("overlap" in SKILL and "img-overlap" in SKILL)
h9_regen = ("MV-01" in REGEN and "ABOUT-01" in REGEN and "§12.1.3" in REGEN)
check("H9 規約文言 (§12.1.3 HERO/ABOUTプール・overlap・§12.2 MENUのみ・§14 MV-01/ABOUT-01・SKILL×2)",
      h9_rules and h9_skill and h9_regen,
      "RULES=%s SKILL=%s REGEN=%s" % (h9_rules, h9_skill, h9_regen))

# H10 klk036 健全性（HERO/ABOUT distinct・番地・依存0）
WANT = {"NAV-01", "MV-01", "ABOUT-01", "GALLERY-01", "CTA-01", "FOOTER-01"}
h10 = (distinct3(act_hero) and distinct3(act_about)
       and all(all_pins(K36[l]) == WANT for l in ("a", "b", "c"))
       and not any(re.search(r'(src|href)=["\']?https?:', K36[l]) for l in ("a", "b", "c")))
check("H10 klk036 健全性 (HERO/ABOUT 3案distinct・番地6種各1・外部URL0)",
      h10, "HERO=%s ABOUT=%s" % (act_hero, act_about))

# Report
print("=" * 78)
print("KLK-037 static acceptance checks (docs/designs/KLK-037.md §9 を正とする)")
print("対象: DRAFT_RULES §12.1.3 HERO/ABOUT / check_klk034 定数(ast) / fixtures klk036・klk023・klk034(b)")
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
print("D群（test_palette_klk037.py）: Quality Gate 全緑 / fixtures の git 追跡")
print("M群（tester 手動・ブラウザ）: HERO/ABOUT で overlap（せり出し画像＋白背景文言の重なり）が案Aに現れる")
sys.exit(1 if failed else 0)
