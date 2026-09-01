#!/usr/bin/env python3
"""
KLK-056 acceptance-condition checker (static / no browser required).

SEARCH セクションのプール化（§12.1.3・6型・mod6・入力は静的アタリ・コンテンツ展開型＋小型窓[header/footer]の混在）の
静的受け入れ条件を検証する。check_klk051〜055 と同型。

  縦串 生成規約   DRAFT_RULES §12.1.3 SEARCH プール表(6型)・SEARCH 割り当て表(mod6)・§2.1 SEARCH 行
  縦串 スキル     SKILL.md 手順3（SEARCH プール）
  縦串 ブリッジ   draft-gen/bridge.py validate_instruction（sectionOptions.SEARCH.moreLink 込み）
  主 golden       tests/fixtures/klk056 （1col×top=offset0→(0,1,2)・案A=search-bar/案B=search-keywords/案C=search-filters・SEARCH moreLink デモ）
  副 golden       tests/fixtures/klk056b（1col×below-hero=offset3→(3,4,5)・案A=search-sidebar/案B=search-header/案C=search-footer）
  ドリフト検出    本文 SEARCH プール/割り当て ＝ check_klk034.py の SEARCH_POOL/SEARCH_ASSIGN/POOL_1213/ASSIGN_1213（ast）

★特記: 入力欄は静的アタリ（<form action> の外部送信・iframe・外部 URL が無いこと＝NFR-005）を検証。

Python標準のみ・exit 0/1・bridge は import（validate 機能検証）。

Run: python3 tests/site/check_klk056.py
"""
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()

sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

EXPECT_N = 6  # SEARCH プールの型数
POOL_EXPECT = ["search-bar", "search-keywords", "search-filters", "search-sidebar", "search-header", "search-hero"]
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_search_pool():
    seg = _seg("**SEARCH プール", "**(2) 割り当て表")
    seen = []
    for m in re.finditer(r'`(search-[a-z-]+)`', seg):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def parse_search_assign():
    seg = _seg("**SEARCH（6型", "**(3) 生成手順")
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


SEARCH_POOL_RULES = parse_search_pool()
ASSIGN = parse_search_assign()
OFFSET = parse_offset()

# --- check_klk034 定数（ast・literal と Name 参照の両方） ---
C34_TREE = ast.parse(open(os.path.join(ROOT, "tests", "site", "check_klk034.py"), encoding="utf-8").read())


def consts(names):
    out = {}
    for node in C34_TREE.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in names:
                    out[t.id] = ast.literal_eval(node.value)
    return out


def dict_name_ref(var, key):
    for node in C34_TREE.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == var for t in node.targets):
            if isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and k.value == key and isinstance(v, ast.Name):
                        return v.id
    return None


C34 = consts({"SEARCH_POOL", "SEARCH_ASSIGN"})


def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def search_marker(html):
    m = re.search(r'class="m-search (search-[a-z-]+)"', html)
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


def static_search_safe(html):
    """入力は静的アタリ: 外部送信する <form action>・iframe・外部 URL が無いこと（NFR-005）。"""
    return (not re.search(r'<form[^>]*action=', html, re.I)
            and "<iframe" not in html
            and not re.search(r'(src|href)="https?:', html))


def distinct3(vals):
    return len(set(vals)) == 3 and all(v is not None for v in vals)


K = {l: gread("klk056", "index-%s.html" % l) for l in ("a", "b", "c")}
K3 = {l: gread("klk056b", "index-%s.html" % l) for l in ("a", "b", "c")}  # offset3 golden（新型 3,4,5 実演）
INSTR = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk056", "instruction.json"), encoding="utf-8"))

# SR1 §12.1.3 SEARCH プール（6型）＋§2.1 SEARCH 行が §12.1.3 に言及＋SKILL/SEARCH-01（規約文言）
sr1 = (SEARCH_POOL_RULES == POOL_EXPECT and "SEARCH プール" in RULES and "§12.1.3 プール（6型" in RULES
       and "SEARCH（6型" in SKILL and ".m-search" in SKILL and "SEARCH-01" in RULES)
check("SR1 §12.1.3 SEARCH プール (6型・bar/keywords/filters/sidebar/header/footer・§2.1 SEARCH 言及・SKILL .m-search・SEARCH-01)",
      sr1, "pool=%s SKILL=%s .m-search=%s" % (SEARCH_POOL_RULES, "SEARCH（6型" in SKILL, ".m-search" in SKILL))

# SR2 SEARCH 割り当て表 6行・巡回mod6・distinct
sr2 = (len(ASSIGN) == 6 and all(ASSIGN[o] == (o % EXPECT_N, (o + 1) % EXPECT_N, (o + 2) % EXPECT_N) for o in ASSIGN)
       and all(len(set(ASSIGN[o])) == 3 for o in ASSIGN))
check("SR2 SEARCH 割り当て表 (6行・巡回mod6・各行distinct)", sr2, "assign=%s" % ASSIGN)

# SR3 到達可能性 index{0..5}
reach = set()
for off in OFFSET.values():
    reach |= set(ASSIGN[off])
check("SR3 到達可能性 (全offsetから SEARCH index{0..5} 全到達＝新型 sidebar/header/footer 含む)",
      reach >= set(range(EXPECT_N)), "到達=%s" % sorted(reach))

# SR4 ドリフト検出: 本文 = check_klk034 SEARCH_POOL/SEARCH_ASSIGN・POOL_1213/ASSIGN_1213 の SEARCH 参照
d_pool = (SEARCH_POOL_RULES == list(C34.get("SEARCH_POOL", [])) == POOL_EXPECT)
d_assign = (C34.get("SEARCH_ASSIGN") == ASSIGN)
d_p1213 = (dict_name_ref("POOL_1213", "SEARCH") == "SEARCH_POOL")
d_a1213 = (dict_name_ref("ASSIGN_1213", "SEARCH") == "SEARCH_ASSIGN")
check("SR4 ドリフト検出 (本文SEARCH = check_klk034 SEARCH_POOL/SEARCH_ASSIGN・POOL_1213[SEARCH]=SEARCH_POOL・ASSIGN_1213[SEARCH]=SEARCH_ASSIGN)",
      d_pool and d_assign and d_p1213 and d_a1213,
      "pool=%s assign=%s POOL_1213=%s ASSIGN_1213=%s" % (d_pool, d_assign, d_p1213, d_a1213))

# SR5 klk056 表引き: offset0→(0,1,2)・SEARCH=(search-bar,search-keywords,search-filters)
off = OFFSET[("1col", "top")]
idxs = ASSIGN[off]
exp = tuple(SEARCH_POOL_RULES[i] for i in idxs)
act = tuple(search_marker(K[l]) for l in ("a", "b", "c"))
sr5 = (off == 0 and idxs == (0, 1, 2) and act == exp)
check("SR5 klk056 表引き (1col×top→offset0→(0,1,2)・SEARCH=(search-bar,search-keywords,search-filters))",
      sr5, "offset=%s idxs=%s 期待%s 実%s" % (off, idxs, exp, act))

# SR6 各SEARCH型の実CSS差＋keywords=チップ群・filters=grid
sr6_all = all(css_layout_rule(K[l], search_marker(K[l])) for l in ("a", "b", "c"))
sr6_bar = css_layout_rule(K["a"], "search-bar") and ('class="s-bar"' in K["a"])
sr6_kw = css_layout_rule(K["b"], "search-keywords") and ('class="kw-chip' in K["b"])
sr6_filters = css_layout_rule(K["c"], "search-filters") and ("grid-template-columns" in K["c"]) and ('class="f-field"' in K["c"]) and ("<details" in K["c"])
check("SR6 各SEARCH型の実CSS差 (search-bar=検索バー・search-keywords=チップ群・search-filters=絞り込みgrid＋details展開・飾りでない)",
      sr6_all and sr6_bar and sr6_kw and sr6_filters,
      "全案実CSS=%s bar=%s keywords=%s filters(details)=%s" % (sr6_all, sr6_bar, sr6_kw, sr6_filters))

# SR7 入力は静的アタリ: 全案に <form action>/iframe/外部URL が無い（NFR-005）
sr7 = all(static_search_safe(K[l]) for l in ("a", "b", "c"))
check("SR7 入力は静的アタリ (全案 <form action>/iframe/外部URL なし＝実送信なし・NFR-005)",
      sr7, "静的安全=%s" % {l: static_search_safe(K[l]) for l in 'abc'})

# SR8 moreLink opt-in デモ: instruction に SEARCH.moreLink・全案の SEARCH 直後に .sec-more（§4.3 併用）
search_ml = ((INSTR.get("sectionOptions") or {}).get("SEARCH") or {}).get("moreLink")
sr8 = (isinstance(search_ml, dict) and search_ml.get("label")
       and all(K[l].count('class="sec-more"') == 1 for l in ("a", "b", "c")))
check("SR8 moreLink opt-in デモ (instruction.SEARCH.moreLink・全案 SEARCH に .sec-more×1＝§4.3 併用)",
      sr8, "SEARCH.moreLink=%s .sec-more数=%s" % (bool(search_ml), {l: K[l].count('class=\"sec-more\"') for l in 'abc'}))

# SR9 健全性: SEARCH distinct・番地4種各1・静的・print・PH
WANT = {"NAV-01", "MV-01", "SEARCH-01", "FOOTER-01"}
sr9 = True
sr9_det = []
for l in ("a", "b", "c"):
    h = K[l]
    ok = (all_pins(h) == WANT and static_search_safe(h) and "@media print" in h
          and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h))
    sr9 = sr9 and ok
    if not ok:
        sr9_det.append("%s: 番地=%s 静的=%s" % (l, all_pins(h) == WANT, static_search_safe(h)))
check("SR9 健全性 (SEARCH 3案distinct・番地4種各1・静的入力・print・PH)",
      sr9 and distinct3(act), "; ".join(sr9_det) if sr9_det else "3案とも健全・SEARCH=%s" % (act,))

# SR10 bridge: klk056 instruction が通過＋SEARCH.moreLink の受理/拒否
q10_instr = bridge.validate_instruction(INSTR)[0]
base = {"schema": "design-draft-instruction", "version": 1, "industry": {"resolved": "雑貨EC"},
        "layout": {"columns": "1col"}, "colors": {"main": "#2c5f8a"}}
base_ext = json.loads(json.dumps(base)); base_ext["sectionOptions"] = {"SEARCH": {"moreLink": {"label": "すべての商品を見る"}}}
bad = json.loads(json.dumps(base)); bad["sectionOptions"] = {"SEARCH": {"moreLink": {"label": "x", "href": "https://evil.example"}}}
sr10 = (q10_instr is True and bridge.validate_instruction(base_ext)[0] is True
        and bridge.validate_instruction(bad)[0] is False)
check("SR10 bridge.validate_instruction (klk056 instruction 通過・SEARCH.moreLink 受理・外部URL href 拒否)",
      sr10, "instr=%s 正常moreLink=%s 外部href拒否=%s" % (q10_instr,
            bridge.validate_instruction(base_ext)[0], not bridge.validate_instruction(bad)[0]))

# SR11 klk056b（offset3）表引き: offset3→(3,4,5)＝案A=search-sidebar/案B=search-header/案C=search-footer＋新型 実CSS差＋静的
off3 = OFFSET[("1col", "below-hero")]
idxs3 = ASSIGN[off3]
exp3 = tuple(SEARCH_POOL_RULES[i] for i in idxs3)
act3 = tuple(search_marker(K3[l]) for l in ("a", "b", "c"))
sr11_map = (off3 == 3 and idxs3 == (3, 4, 5) and act3 == exp3)
sr11_sidebar = css_layout_rule(K3["a"], "search-sidebar") and ('class="filter-nav"' in K3["a"]) and ("result-grid" in K3["a"])
sr11_header = css_layout_rule(K3["b"], "search-header") and ('class="s-input"' in K3["b"])
sr11_hero = css_layout_rule(K3["c"], "search-hero") and ('class="s-input"' in K3["c"])
sr11_health = all(all_pins(K3[l]) >= {"SEARCH-01"} and static_search_safe(K3[l]) for l in ("a", "b", "c"))
check("SR11 klk056b offset3 表引き (offset3→(3,4,5)=search-sidebar/search-header/search-hero＋新型 実CSS差＋静的)",
      sr11_map and sr11_sidebar and sr11_header and sr11_hero and sr11_health,
      "SEARCH 期待%s 実%s / sidebar=%s header=%s hero=%s 健全=%s" % (exp3, act3, sr11_sidebar, sr11_header, sr11_hero, sr11_health))

# Report
print("=" * 78)
print("KLK-056 static acceptance checks (SEARCH §12.1.3 プール化・6型・mod6・入力は静的アタリ・コンテンツ型＋小型窓)")
print("対象: DRAFT_RULES §12.1.3 SEARCH / SKILL / bridge / fixtures klk056・klk056b")
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
