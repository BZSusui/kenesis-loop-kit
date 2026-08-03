#!/usr/bin/env python3
"""
KLK-044 acceptance-condition checker (static / no browser required).

MENU のプール化（§12.1.3・§12.1.1 から移譲・新型 price-table[044]/tab-switch[045]/feature-large[046]・MENU 6型化・mod6）の
静的受け入れ条件を検証する。check_klk036.py（GALLERY版）/check_klk037.py（HERO/ABOUT版）が雛形。

  縦串 生成規約   .claude/skills/draft-generate/templates/DRAFT_RULES.md（§12.1.3 の MENU プール表6型・MENU専用 mod6 割り当て表）
  主 golden       tests/fixtures/klk044/{index-a/b/c}.html（1col×below-hero=offset3→MENU(3,4,5)・案A=price-table・案B=tab-switch・案C=feature-large）
  既存 golden     tests/fixtures/klk023/034/034b（1col×top=offset0→MENU(0,1,2)＝pat-cards/list/zigzag 不変）
  ドリフト検出    DRAFT_RULES §12.1.3 の MENU プール表・mod6割り当て ＝ check_klk034.py の MENU_POOL/POOL_1213/ASSIGN_1213/MENU_ASSIGN（ast 抽出）

Python標準のみ・exit 0/1・import せず ast。

Run: python3 tests/site/check_klk044.py
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()
REGEN = open(os.path.join(ROOT, ".claude", "skills", "draft-regenerate", "SKILL.md"), encoding="utf-8").read()

EXPECT_N = 6  # KLK-046: MENU を6型化（mod6・自動振り分け上限6に到達・GALLERY mod4 とは別系統）
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# --- DRAFT_RULES §12.1.3 本文パース（MENU プール） ---
def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_menu_pool():
    # MENU プール表: 「**MENU プール（...）...:**」〜「**(2) 割り当て表」。pat-* / price-table / tab-switch / feature-large（バッククォート）
    seg = _seg("**MENU プール", "**SNS プール")  # KLK-049: MENU プール表のみ（SNS プール表の手前で止める）
    seen = []
    for m in re.finditer(r'`(pat-cards|pat-list|pat-zigzag|price-table|tab-switch|feature-large)`', seg):
        v = m.group(1)
        if v not in seen:
            seen.append(v)
    return seen


def parse_menu_assign():
    # MENU は専用の mod6 表（KLK-046・HERO/ABOUT mod6 と同値・GALLERY mod4 とは別系統）。「**MENU（6型」〜「**(3) 生成手順」を読む。
    seg = _seg("**MENU（6型", "**SNS（3型")  # KLK-049: MENU(mod6)表のみ（SNS(mod3)表の手前で止める）
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


MENU_POOL_RULES = parse_menu_pool()
ASSIGN = parse_menu_assign()
OFFSET = parse_offset()


# --- check_klk034.py の定数を ast で抽出（import せず） ---
# POOL_1213/ASSIGN_1213 は値が Name 参照（HERO_POOL 等）なので literal_eval 不可。
# リテラル定数（MENU_POOL/GALLERY_ASSIGN/DEFAULT_1211）だけ literal_eval し、
# Name 参照のマッピング（POOL_1213["MENU"]=MENU_POOL・ASSIGN_1213["MENU"]=GALLERY_ASSIGN）は AST で名前照合する。
C34_SRC = open(os.path.join(ROOT, "tests", "site", "check_klk034.py"), encoding="utf-8").read()
C34_TREE = ast.parse(C34_SRC)


def consts_from(names):
    out = {}
    for node in C34_TREE.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in names:
                    out[t.id] = ast.literal_eval(node.value)
    return out


def dict_name_ref(var, key):
    """トップレベル代入 `var = { ... "key": NAME ... }` の NAME（識別子）を返す（値が Name のとき）。"""
    for node in C34_TREE.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == var for t in node.targets):
            d = node.value
            if isinstance(d, ast.Dict):
                for k, v in zip(d.keys, d.values):
                    if isinstance(k, ast.Constant) and k.value == key and isinstance(v, ast.Name):
                        return v.id
    return None


C34 = consts_from({"MENU_POOL", "MENU_ASSIGN", "DEFAULT_1211"})


# --- golden ユーティリティ ---
def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def attr(html, name):
    m = re.search(r'%s="([^"]+)"' % re.escape(name), html)
    return m.group(1) if m else None


def menu_marker(html):
    """`.m-menu <型>` の型（pat-* / price-table）。price-table は pat- で始まらないので広めに拾う。"""
    m = re.search(r'class="m-menu ([a-z][a-z-]+)"', html)
    return m.group(1) if m else None


def all_pins(html):
    return set(re.findall(r'class="pin">([A-Z0-9-]+)<', html))


def css_layout_rule(html, token):
    if not token:
        return False
    for m in re.finditer(r'\.%s\b[^{}]*\{([^}]*)\}' % re.escape(token), html):
        if re.search(r'grid-template-columns|flex-direction|grid-auto|grid-column|grid-row|order\s*:|flex-wrap|overflow-x', m.group(1)):
            return True
    return False


def no_ext_url(html):
    return not re.search(r'(src|href)=["\']?https?:', html)


def distinct3(vals):
    return len(set(vals)) == 3 and all(v is not None for v in vals)


K44 = {ltr: gread("klk044", "index-%s.html" % ltr) for ltr in ("a", "b", "c")}
POOL_EXPECT = ["pat-cards", "pat-list", "pat-zigzag", "price-table", "tab-switch", "feature-large"]

# ===========================================================================
# P1 本文パース: MENU プール6型・index3=price-table・index4=tab-switch・index5=feature-large
# ===========================================================================
p1 = (MENU_POOL_RULES == POOL_EXPECT)
check("P1 §12.1.3 MENU プール (6型・pat-cards/pat-list/pat-zigzag/price-table/tab-switch/feature-large・index5=feature-large)",
      p1, "MENU=%s" % MENU_POOL_RULES)

# P2 割り当て表 6行・巡回mod6（MENU 専用表・KLK-046・HERO/ABOUT と同値）・distinct
p2 = (len(ASSIGN) == 6 and all(ASSIGN[o] == (o % EXPECT_N, (o + 1) % EXPECT_N, (o + 2) % EXPECT_N) for o in ASSIGN)
      and all(len(set(ASSIGN[o])) == 3 for o in ASSIGN))
check("P2 割り当て表 (MENU専用 mod6・6行・巡回mod6・各行distinct)", p2, "assign=%s" % ASSIGN)

# P3 到達可能性: 全offsetから index{0..5} 全到達（新型 index3=price-table・index4=tab-switch・index5=feature-large 含む）
reach = set()
for off in OFFSET.values():
    reach |= set(ASSIGN[off])
check("P3 到達可能性 (全offsetから index{0..5} 全到達＝price-table(3)/tab-switch(4)/feature-large(5) 含む)",
      reach >= set(range(EXPECT_N)), "到達=%s" % sorted(reach))

# P4 ドリフト検出: 本文MENUプール = check_klk034 の MENU_POOL・POOL_1213[MENU]=MENU_POOL・ASSIGN_1213[MENU]=MENU_ASSIGN(mod6)・DEFAULT_1211からMENU除外
d_pool = (MENU_POOL_RULES == list(C34.get("MENU_POOL", [])) == POOL_EXPECT)
d_pool1213 = (dict_name_ref("POOL_1213", "MENU") == "MENU_POOL")        # POOL_1213["MENU"] は MENU_POOL を指す
d_assign_ref = (dict_name_ref("ASSIGN_1213", "MENU") == "MENU_ASSIGN")  # ASSIGN_1213["MENU"] は MENU_ASSIGN（mod6）
d_assign_tbl = (C34.get("MENU_ASSIGN") == ASSIGN)                       # 本文 MENU mod6 表 = 定数
d1211 = ("MENU" not in (C34.get("DEFAULT_1211") or {}))
check("P4 ドリフト検出 (本文MENUプール = check_klk034 MENU_POOL・POOL_1213[MENU]=MENU_POOL・ASSIGN_1213[MENU]=MENU_ASSIGN(mod6)・DEFAULT_1211からMENU除外)",
      d_pool and d_pool1213 and d_assign_ref and d_assign_tbl and d1211,
      "pool=%s POOL_1213[MENU]=%s ASSIGN_1213[MENU]=%s mod6表一致=%s 1211除外=%s"
      % (d_pool, d_pool1213, d_assign_ref, d_assign_tbl, d1211))

# P5 klk044 表引き: offset3→(3,4,5)・MENU=(price-table,tab-switch,feature-large)
off44 = OFFSET[("1col", "below-hero")]
idxs = ASSIGN[off44]
exp_menu = tuple(MENU_POOL_RULES[i] for i in idxs)
act_menu = tuple(menu_marker(K44[l]) for l in ("a", "b", "c"))
p5 = (off44 == 3 and idxs == (3, 4, 5) and act_menu == exp_menu)
check("P5 klk044 表引き (offset3→(3,4,5)・MENU=(price-table,tab-switch,feature-large))",
      p5, "MENU 期待%s 実%s (offset=%s idxs=%s)" % (exp_menu, act_menu, off44, idxs))

# P6 price-table/tab-switch/feature-large の実CSS差（案A=表形式 grid・案B=tab-switch flex/grid・案C=feature-large grid）＋各案MENUマーカーが実CSSを伴う
p6_pt = css_layout_rule(K44["a"], "price-table") and ("grid-template-columns" in K44["a"])
p6_tab = css_layout_rule(K44["b"], "tab-switch") and (menu_marker(K44["b"]) == "tab-switch")
p6_feat = css_layout_rule(K44["c"], "feature-large") and (menu_marker(K44["c"]) == "feature-large")
p6_all = all(css_layout_rule(K44[l], menu_marker(K44[l])) for l in ("a", "b", "c"))
check("P6 price-table/tab-switch/feature-large 実CSS差 (案A=price-table grid・案B=tab-switch・案C=feature-large grid・全案が実 grid/flex・飾りでない)",
      p6_pt and p6_tab and p6_feat and p6_all,
      "price-table=%s tab-switch=%s feature-large=%s 全案実CSS=%s" % (p6_pt, p6_tab, p6_feat, p6_all))

# P7 既存golden不変（offset0）: klk023/034/034b の MENU が offset0→(pat-cards,pat-list,pat-zigzag) のまま
p7_ok = True
p7_det = []
for name in ("klk023", "klk034", "klk034b"):
    gm = tuple(menu_marker(gread(name, "index-%s.html" % l)) for l in ("a", "b", "c"))
    ok = (gm == ("pat-cards", "pat-list", "pat-zigzag"))
    p7_ok = p7_ok and ok
    p7_det.append("%s: MENU%s%s" % (name, gm, "" if ok else "≠(pat-cards,pat-list,pat-zigzag)"))
check("P7 既存golden不変 (klk023/034/034b の MENU が offset0 の従来値 pat-cards/list/zigzag・§12.1.3移譲で変わらない)",
      p7_ok, "; ".join(p7_det))

# P8 klk044 MENU 3案distinct＋全マーカーがプール語彙
p8_distinct = distinct3(act_menu)
p8_vocab = all(m in POOL_EXPECT for m in act_menu)
check("P8 klk044 MENU 3案distinct・全マーカーが§12.1.3 MENUプール語彙(4型)内",
      p8_distinct and p8_vocab, "MENU=%s distinct=%s 語彙=%s" % (act_menu, p8_distinct, p8_vocab))

# P9 規約文言: §12.1.3 に MENU プール6型・price-table・tab-switch・feature-large・MENU mod6 表・§14 に MENU-01・SKILL
p9_rules = ("MENU プール" in RULES and "price-table" in RULES and "tab-switch" in RULES and "feature-large" in RULES
            and "MENU も §12.1.3" in RULES  # §12.2/§12.1.3(6) の移譲注記
            and "MENU（6型" in RULES         # MENU 専用 mod6 割り当て表の見出し
            and "MENU-01" in RULES)          # §14 再付与対象
p9_skill = ("feature-large" in SKILL and "MENU（6型" in SKILL)
check("P9 規約文言 (§12.1.3 MENUプール6型・price-table・tab-switch・feature-large・MENU mod6表・§14 MENU-01・SKILL)",
      p9_rules and p9_skill,
      "RULES=%s SKILL=%s" % (p9_rules, p9_skill))

# P10 klk044 健全性（MENU distinct・番地6種各1・依存0・print・プレースホルダ明記）
WANT = {"NAV-01", "MV-01", "ABOUT-01", "MENU-01", "GALLERY-01", "CTA-01", "FOOTER-01"}
p10_ok = True
p10_det = []
for l in ("a", "b", "c"):
    h = K44[l]
    pins_ok = all_pins(h) == WANT
    prt = "@media print" in h
    solo = no_ext_url(h)
    ph = ("プレースホルダ" in h or "実在の顧客" in h or "サンプル" in h)
    ok = pins_ok and prt and solo and ph
    p10_ok = p10_ok and ok
    if not ok:
        p10_det.append("%s: 番地=%s print=%s 依存0=%s PH=%s" % (l, pins_ok, prt, solo, ph))
check("P10 klk044 健全性 (番地7種各1・MENU 3案distinct・@media print・外部URL0・プレースホルダ明記)",
      p10_ok and distinct3(act_menu), "; ".join(p10_det) if p10_det else "3案とも健全・MENU=%s" % (act_menu,))

# Report
print("=" * 78)
print("KLK-044/045/046 static acceptance checks (MENU §12.1.3・price-table/tab-switch/feature-large・6型化 mod6)")
print("対象: DRAFT_RULES §12.1.3 MENU / check_klk034 定数(ast) / fixtures klk044・klk023・klk034(b)")
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
print("D群（test_palette_klk044.py）: Quality Gate 全緑 / fixtures の git 追跡")
print("M群（tester 手動・ブラウザ）: MENU で price-table（価格表/料金プラン）が案Aに現れる")
sys.exit(1 if failed else 0)
