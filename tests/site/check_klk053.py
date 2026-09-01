#!/usr/bin/env python3
"""
KLK-053 acceptance-condition checker (static / no browser required).

FAQ セクションのプール化（§12.1.3・6型・mod6・NEWS/MENU/PRICE の accordion/card/list/tab を流用）の
静的受け入れ条件を検証する。check_klk051/052 と同型。

  縦串 生成規約   DRAFT_RULES §12.1.3 FAQ プール表(6型)・FAQ 割り当て表(mod6)・§2.1 FAQ 行
  縦串 スキル     SKILL.md 手順3（FAQ プール）
  縦串 ブリッジ   draft-gen/bridge.py validate_instruction（sectionOptions.FAQ.moreLink 込み）
  主 golden       tests/fixtures/klk053 （1col×top=offset0→(0,1,2)・案A=faq-list/案B=faq-accordion/案C=faq-two-col・FAQ moreLink デモ）
  副 golden       tests/fixtures/klk053b（1col×below-hero=offset3→(3,4,5)・案A=faq-cards/案B=faq-category-tabs/案C=faq-search）
  ドリフト検出    本文 FAQ プール/割り当て ＝ check_klk034.py の FAQ_POOL/FAQ_ASSIGN/POOL_1213/ASSIGN_1213（ast）

Python標準のみ・exit 0/1・bridge は import（validate 機能検証）。

Run: python3 tests/site/check_klk053.py
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

EXPECT_N = 6  # FAQ プールの型数
POOL_EXPECT = ["faq-list", "faq-accordion", "faq-two-col", "faq-cards", "faq-category-tabs", "faq-search"]
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_faq_pool():
    seg = _seg("**FAQ プール", "**(2) 割り当て表")
    seen = []
    for m in re.finditer(r'`(faq-[a-z-]+)`', seg):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def parse_faq_assign():
    seg = _seg("**FAQ（6型", "**(3) 生成手順")
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


FAQ_POOL_RULES = parse_faq_pool()
ASSIGN = parse_faq_assign()
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


C34 = consts({"FAQ_POOL", "FAQ_ASSIGN"})


def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def faq_marker(html):
    m = re.search(r'class="m-faq (faq-[a-z-]+)"', html)
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


def distinct3(vals):
    return len(set(vals)) == 3 and all(v is not None for v in vals)


K = {l: gread("klk053", "index-%s.html" % l) for l in ("a", "b", "c")}
K3 = {l: gread("klk053b", "index-%s.html" % l) for l in ("a", "b", "c")}  # offset3 golden（新型 3,4,5 実演）
INSTR = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk053", "instruction.json"), encoding="utf-8"))

# F1 §12.1.3 FAQ プール（6型）＋§2.1 FAQ 行が §12.1.3 に言及
f1 = (FAQ_POOL_RULES == POOL_EXPECT and "FAQ プール" in RULES and "§12.1.3 プール（6型" in RULES)
check("F1 §12.1.3 FAQ プール (6型・list/accordion/two-col/cards/category-tabs/search・§2.1 FAQ 行が §12.1.3 プール言及)",
      f1, "pool=%s" % FAQ_POOL_RULES)

# F2 FAQ 割り当て表 6行・巡回mod6・distinct
f2 = (len(ASSIGN) == 6 and all(ASSIGN[o] == (o % EXPECT_N, (o + 1) % EXPECT_N, (o + 2) % EXPECT_N) for o in ASSIGN)
      and all(len(set(ASSIGN[o])) == 3 for o in ASSIGN))
check("F2 FAQ 割り当て表 (6行・巡回mod6・各行distinct)", f2, "assign=%s" % ASSIGN)

# F3 到達可能性 index{0..5}
reach = set()
for off in OFFSET.values():
    reach |= set(ASSIGN[off])
check("F3 到達可能性 (全offsetから FAQ index{0..5} 全到達＝新型 cards/category-tabs/search 含む)",
      reach >= set(range(EXPECT_N)), "到達=%s" % sorted(reach))

# F4 ドリフト検出: 本文 = check_klk034 FAQ_POOL/FAQ_ASSIGN・POOL_1213/ASSIGN_1213 の FAQ 参照
d_pool = (FAQ_POOL_RULES == list(C34.get("FAQ_POOL", [])) == POOL_EXPECT)
d_assign = (C34.get("FAQ_ASSIGN") == ASSIGN)
d_p1213 = (dict_name_ref("POOL_1213", "FAQ") == "FAQ_POOL")
d_a1213 = (dict_name_ref("ASSIGN_1213", "FAQ") == "FAQ_ASSIGN")
check("F4 ドリフト検出 (本文FAQ = check_klk034 FAQ_POOL/FAQ_ASSIGN・POOL_1213[FAQ]=FAQ_POOL・ASSIGN_1213[FAQ]=FAQ_ASSIGN)",
      d_pool and d_assign and d_p1213 and d_a1213,
      "pool=%s assign=%s POOL_1213=%s ASSIGN_1213=%s" % (d_pool, d_assign, d_p1213, d_a1213))

# F5 klk053 表引き: offset0→(0,1,2)・FAQ=(faq-list,faq-accordion,faq-two-col)
off = OFFSET[("1col", "top")]
idxs = ASSIGN[off]
exp = tuple(FAQ_POOL_RULES[i] for i in idxs)
act = tuple(faq_marker(K[l]) for l in ("a", "b", "c"))
f5 = (off == 0 and idxs == (0, 1, 2) and act == exp)
check("F5 klk053 表引き (1col×top→offset0→(0,1,2)・FAQ=(faq-list,faq-accordion,faq-two-col))",
      f5, "offset=%s idxs=%s 期待%s 実%s" % (off, idxs, exp, act))

# F6 各FAQ型の実CSS差＋faq-accordion が details・faq-two-col が2カラム
f6_all = all(css_layout_rule(K[l], faq_marker(K[l])) for l in ("a", "b", "c"))
f6_list = css_layout_rule(K["a"], "faq-list") and ('class="bq"' in K["a"])
f6_acc = css_layout_rule(K["b"], "faq-accordion") and ("<details" in K["b"])
f6_two = css_layout_rule(K["c"], "faq-two-col") and ("grid-template-columns" in K["c"]) and ("<details" in K["c"])
check("F6 各FAQ型の実CSS差 (faq-list=Q/A縦積み・faq-accordion=details開閉・faq-two-col=2カラム開閉・飾りでない)",
      f6_all and f6_list and f6_acc and f6_two,
      "全案実CSS=%s list=%s accordion=%s two-col=%s" % (f6_all, f6_list, f6_acc, f6_two))

# F7 moreLink opt-in デモ: instruction に FAQ.moreLink・全案の FAQ 直後に .sec-more（§4.3 併用）
faq_ml = ((INSTR.get("sectionOptions") or {}).get("FAQ") or {}).get("moreLink")
f7 = (isinstance(faq_ml, dict) and faq_ml.get("label")
      and all(K[l].count('class="sec-more"') == 1 for l in ("a", "b", "c")))
check("F7 moreLink opt-in デモ (instruction.FAQ.moreLink・全案 FAQ に .sec-more×1＝§4.3 併用)",
      f7, "FAQ.moreLink=%s .sec-more数=%s" % (bool(faq_ml), {l: K[l].count('class=\"sec-more\"') for l in 'abc'}))

# F8 健全性: FAQ distinct・番地5種各1・外部URL0・実埋め込み(iframe)なし・print・PH
WANT = {"NAV-01", "MV-01", "FAQ-01", "CTA-01", "FOOTER-01"}
f8 = True
f8_det = []
for l in ("a", "b", "c"):
    h = K[l]
    ok = (all_pins(h) == WANT and not re.search(r'(src|href)="https?:', h)
          and "<iframe" not in h and "@media print" in h
          and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h))
    f8 = f8 and ok
    if not ok:
        f8_det.append("%s: 番地=%s iframe無=%s" % (l, all_pins(h) == WANT, "<iframe" not in h))
check("F8 健全性 (FAQ 3案distinct・番地5種各1・外部URL0・実埋め込み(iframe)なし・print・PH)",
      f8 and distinct3(act), "; ".join(f8_det) if f8_det else "3案とも健全・FAQ=%s" % (act,))

# F9 bridge: klk053 instruction が通過＋FAQ.moreLink の受理/拒否
q9_instr = bridge.validate_instruction(INSTR)[0]
base = {"schema": "design-draft-instruction", "version": 1, "industry": {"resolved": "オンライン英会話"},
        "layout": {"columns": "1col"}, "colors": {"main": "#2c5f8a"}}
base_ext = json.loads(json.dumps(base)); base_ext["sectionOptions"] = {"FAQ": {"moreLink": {"label": "よくある質問をもっと見る"}}}
bad = json.loads(json.dumps(base)); bad["sectionOptions"] = {"FAQ": {"moreLink": {"label": "x", "href": "https://evil.example"}}}
f9 = (q9_instr is True and bridge.validate_instruction(base_ext)[0] is True
      and bridge.validate_instruction(bad)[0] is False)
check("F9 bridge.validate_instruction (klk053 instruction 通過・FAQ.moreLink 受理・外部URL href 拒否)",
      f9, "instr=%s 正常moreLink=%s 外部href拒否=%s" % (q9_instr,
          bridge.validate_instruction(base_ext)[0], not bridge.validate_instruction(bad)[0]))

# F10 規約文言: SKILL に FAQ プール・§2.1 に FAQ-01
f10 = ("FAQ（6型" in SKILL and ".m-faq" in SKILL and "FAQ-01" in RULES)
check("F10 規約文言 (SKILL 手順3 に FAQ プール・.m-faq・§2.1 に FAQ-01)", f10,
      "SKILL FAQ=%s .m-faq=%s FAQ-01=%s" % ("FAQ（6型" in SKILL, ".m-faq" in SKILL, "FAQ-01" in RULES))

# F11 klk053b（offset3）表引き: offset3→(3,4,5)＝案A=faq-cards/案B=faq-category-tabs/案C=faq-search＋新型 実CSS差
off3 = OFFSET[("1col", "below-hero")]
idxs3 = ASSIGN[off3]
exp3 = tuple(FAQ_POOL_RULES[i] for i in idxs3)
act3 = tuple(faq_marker(K3[l]) for l in ("a", "b", "c"))
f11_map = (off3 == 3 and idxs3 == (3, 4, 5) and act3 == exp3)
f11_cards = css_layout_rule(K3["a"], "faq-cards") and ('class="faq-card"' in K3["a"]) and ("grid-template-columns" in K3["a"])
f11_tabs = css_layout_rule(K3["b"], "faq-category-tabs") and ("ft-panel" in K3["b"])
f11_search = css_layout_rule(K3["c"], "faq-search") and ("faq-searchbar" in K3["c"]) and ("<details" in K3["c"])
f11_health = all(all_pins(K3[l]) >= {"FAQ-01"} and not re.search(r'(src|href)="https?:', K3[l]) and "<iframe" not in K3[l] for l in ("a", "b", "c"))
check("F11 klk053b offset3 表引き (offset3→(3,4,5)=faq-cards/faq-category-tabs/faq-search＋新型 実CSS差・実埋め込みなし)",
      f11_map and f11_cards and f11_tabs and f11_search and f11_health,
      "FAQ 期待%s 実%s / cards=%s tabs=%s search=%s 健全=%s" % (exp3, act3, f11_cards, f11_tabs, f11_search, f11_health))

# Report
print("=" * 78)
print("KLK-053 static acceptance checks (FAQ §12.1.3 プール化・6型・mod6・NEWS/MENU/PRICE 流用)")
print("対象: DRAFT_RULES §12.1.3 FAQ / SKILL / bridge / fixtures klk053・klk053b")
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
