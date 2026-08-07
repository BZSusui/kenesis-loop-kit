#!/usr/bin/env python3
"""
KLK-052 acceptance-condition checker (static / no browser required).

PRICE セクションのプール化（§12.1.3・6型・mod6・NEWS/MENU の表/カード/リスト/タブ/強調を流用）の
静的受け入れ条件を検証する。check_klk051（NEWS）と同型。

  縦串 生成規約   DRAFT_RULES §12.1.3 PRICE プール表(6型)・PRICE 割り当て表(mod6)・§2.1 PRICE 行
  縦串 スキル     SKILL.md 手順3（PRICE プール）
  縦串 ブリッジ   draft-gen/bridge.py validate_instruction（sectionOptions.PRICE.moreLink 込み）
  主 golden       tests/fixtures/klk052 （1col×top=offset0→(0,1,2)・案A=price-table/案B=price-cards/案C=price-featured・PRICE moreLink デモ）
  副 golden       tests/fixtures/klk052b（1col×below-hero=offset3→(3,4,5)・案A=price-list/案B=price-toggle/案C=price-matrix）
  ドリフト検出    本文 PRICE プール/割り当て ＝ check_klk034.py の PRICE_POOL/PRICE_ASSIGN/POOL_1213/ASSIGN_1213（ast）

Python標準のみ・exit 0/1・bridge は import（validate 機能検証）。

Run: python3 tests/site/check_klk052.py
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

EXPECT_N = 6  # PRICE プールの型数
POOL_EXPECT = ["price-table", "price-cards", "price-featured", "price-list", "price-toggle", "price-matrix"]
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_price_pool():
    seg = _seg("**PRICE プール", "**(2) 割り当て表")
    seen = []
    for m in re.finditer(r'`(price-[a-z-]+)`', seg):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def parse_price_assign():
    seg = _seg("**PRICE（6型", "**(3) 生成手順")
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


PRICE_POOL_RULES = parse_price_pool()
ASSIGN = parse_price_assign()
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


C34 = consts({"PRICE_POOL", "PRICE_ASSIGN"})


def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def price_marker(html):
    m = re.search(r'class="m-price (price-[a-z-]+)"', html)
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


K = {l: gread("klk052", "index-%s.html" % l) for l in ("a", "b", "c")}
K3 = {l: gread("klk052b", "index-%s.html" % l) for l in ("a", "b", "c")}  # offset3 golden（新型 3,4,5 実演）
INSTR = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk052", "instruction.json"), encoding="utf-8"))

# P1 §12.1.3 PRICE プール（6型）＋§2.1 PRICE 行が §12.1.3 に言及
p1 = (PRICE_POOL_RULES == POOL_EXPECT and "PRICE プール" in RULES and "§12.1.3 プール（6型" in RULES)
check("P1 §12.1.3 PRICE プール (6型・table/cards/featured/list/toggle/matrix・§2.1 PRICE 行が §12.1.3 プール言及)",
      p1, "pool=%s" % PRICE_POOL_RULES)

# P2 PRICE 割り当て表 6行・巡回mod6・distinct
p2 = (len(ASSIGN) == 6 and all(ASSIGN[o] == (o % EXPECT_N, (o + 1) % EXPECT_N, (o + 2) % EXPECT_N) for o in ASSIGN)
      and all(len(set(ASSIGN[o])) == 3 for o in ASSIGN))
check("P2 PRICE 割り当て表 (6行・巡回mod6・各行distinct)", p2, "assign=%s" % ASSIGN)

# P3 到達可能性 index{0..5}
reach = set()
for off in OFFSET.values():
    reach |= set(ASSIGN[off])
check("P3 到達可能性 (全offsetから PRICE index{0..5} 全到達＝新型 featured/toggle/matrix 含む)",
      reach >= set(range(EXPECT_N)), "到達=%s" % sorted(reach))

# P4 ドリフト検出: 本文 = check_klk034 PRICE_POOL/PRICE_ASSIGN・POOL_1213/ASSIGN_1213 の PRICE 参照
d_pool = (PRICE_POOL_RULES == list(C34.get("PRICE_POOL", [])) == POOL_EXPECT)
d_assign = (C34.get("PRICE_ASSIGN") == ASSIGN)
d_p1213 = (dict_name_ref("POOL_1213", "PRICE") == "PRICE_POOL")
d_a1213 = (dict_name_ref("ASSIGN_1213", "PRICE") == "PRICE_ASSIGN")
check("P4 ドリフト検出 (本文PRICE = check_klk034 PRICE_POOL/PRICE_ASSIGN・POOL_1213[PRICE]=PRICE_POOL・ASSIGN_1213[PRICE]=PRICE_ASSIGN)",
      d_pool and d_assign and d_p1213 and d_a1213,
      "pool=%s assign=%s POOL_1213=%s ASSIGN_1213=%s" % (d_pool, d_assign, d_p1213, d_a1213))

# P5 klk052 表引き: offset0→(0,1,2)・PRICE=(price-table,price-cards,price-featured)
off = OFFSET[("1col", "top")]
idxs = ASSIGN[off]
exp = tuple(PRICE_POOL_RULES[i] for i in idxs)
act = tuple(price_marker(K[l]) for l in ("a", "b", "c"))
p5 = (off == 0 and idxs == (0, 1, 2) and act == exp)
check("P5 klk052 表引き (1col×top→offset0→(0,1,2)・PRICE=(price-table,price-cards,price-featured))",
      p5, "offset=%s idxs=%s 期待%s 実%s" % (off, idxs, exp, act))

# P6 各PRICE型の実CSS差＋price-cards が3列カード・price-featured が強調バッジ
p6_all = all(css_layout_rule(K[l], price_marker(K[l])) for l in ("a", "b", "c"))
p6_table = css_layout_rule(K["a"], "price-table") and ('class="phead' in K["a"])
p6_cards = ('grid-template-columns: repeat(3, 1fr)' in K["b"] and 'class="price-card"' in K["b"])
p6_featured = css_layout_rule(K["c"], "price-featured") and ('class="badge"' in K["c"]) and ("featured" in K["c"])
check("P6 各PRICE型の実CSS差 (price-table=表・price-cards=3列カード・price-featured=中央強調バッジ・飾りでない)",
      p6_all and p6_table and p6_cards and p6_featured,
      "全案実CSS=%s table=%s cards3列=%s featured=%s" % (p6_all, p6_table, p6_cards, p6_featured))

# P7 moreLink opt-in デモ: instruction に PRICE.moreLink・全案の PRICE 直後に .sec-more（§4.3 併用）
price_ml = ((INSTR.get("sectionOptions") or {}).get("PRICE") or {}).get("moreLink")
p7 = (isinstance(price_ml, dict) and price_ml.get("label")
      and all(K[l].count('class="sec-more"') == 1 for l in ("a", "b", "c")))
check("P7 moreLink opt-in デモ (instruction.PRICE.moreLink・全案 PRICE に .sec-more×1＝§4.3 併用)",
      p7, "PRICE.moreLink=%s .sec-more数=%s" % (bool(price_ml), {l: K[l].count('class=\"sec-more\"') for l in 'abc'}))

# P8 健全性: PRICE distinct・番地5種各1・外部URL0・実埋め込み(iframe)なし・print・PH
WANT = {"NAV-01", "MV-01", "PRICE-01", "CTA-01", "FOOTER-01"}
p8 = True
p8_det = []
for l in ("a", "b", "c"):
    h = K[l]
    ok = (all_pins(h) == WANT and not re.search(r'(src|href)="https?:', h)
          and "<iframe" not in h and "@media print" in h
          and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h))
    p8 = p8 and ok
    if not ok:
        p8_det.append("%s: 番地=%s iframe無=%s" % (l, all_pins(h) == WANT, "<iframe" not in h))
check("P8 健全性 (PRICE 3案distinct・番地5種各1・外部URL0・実埋め込み(iframe)なし・print・PH)",
      p8 and distinct3(act), "; ".join(p8_det) if p8_det else "3案とも健全・PRICE=%s" % (act,))

# P9 bridge: klk052 instruction が通過＋PRICE.moreLink の受理/拒否
q9_instr = bridge.validate_instruction(INSTR)[0]
base = {"schema": "design-draft-instruction", "version": 1, "industry": {"resolved": "パーソナルジム"},
        "layout": {"columns": "1col"}, "colors": {"main": "#2c5f8a"}}
base_ext = json.loads(json.dumps(base)); base_ext["sectionOptions"] = {"PRICE": {"moreLink": {"label": "料金プランの詳細を見る"}}}
bad = json.loads(json.dumps(base)); bad["sectionOptions"] = {"PRICE": {"moreLink": {"label": "x", "href": "https://evil.example"}}}
p9 = (q9_instr is True and bridge.validate_instruction(base_ext)[0] is True
      and bridge.validate_instruction(bad)[0] is False)
check("P9 bridge.validate_instruction (klk052 instruction 通過・PRICE.moreLink 受理・外部URL href 拒否)",
      p9, "instr=%s 正常moreLink=%s 外部href拒否=%s" % (q9_instr,
          bridge.validate_instruction(base_ext)[0], not bridge.validate_instruction(bad)[0]))

# P10 規約文言: SKILL に PRICE プール・§2.1 に PRICE-01
p10 = ("PRICE（6型" in SKILL and ".m-price" in SKILL and "PRICE-01" in RULES)
check("P10 規約文言 (SKILL 手順3 に PRICE プール・.m-price・§2.1 に PRICE-01)", p10,
      "SKILL PRICE=%s .m-price=%s PRICE-01=%s" % ("PRICE（6型" in SKILL, ".m-price" in SKILL, "PRICE-01" in RULES))

# P11 klk052b（offset3）表引き: offset3→(3,4,5)＝案A=price-list/案B=price-toggle/案C=price-matrix＋新型 実CSS差
off3 = OFFSET[("1col", "below-hero")]
idxs3 = ASSIGN[off3]
exp3 = tuple(PRICE_POOL_RULES[i] for i in idxs3)
act3 = tuple(price_marker(K3[l]) for l in ("a", "b", "c"))
p11_map = (off3 == 3 and idxs3 == (3, 4, 5) and act3 == exp3)
p11_list = css_layout_rule(K3["a"], "price-list")
p11_toggle = css_layout_rule(K3["b"], "price-toggle") and ("pt-panel" in K3["b"])
p11_matrix = css_layout_rule(K3["c"], "price-matrix") and ("grid-template-columns" in K3["c"])
p11_health = all(all_pins(K3[l]) >= {"PRICE-01"} and not re.search(r'(src|href)="https?:', K3[l]) and "<iframe" not in K3[l] for l in ("a", "b", "c"))
check("P11 klk052b offset3 表引き (offset3→(3,4,5)=price-list/price-toggle/price-matrix＋新型 実CSS差・実埋め込みなし)",
      p11_map and p11_list and p11_toggle and p11_matrix and p11_health,
      "PRICE 期待%s 実%s / list=%s toggle=%s matrix=%s 健全=%s" % (exp3, act3, p11_list, p11_toggle, p11_matrix, p11_health))

# Report
print("=" * 78)
print("KLK-052 static acceptance checks (PRICE §12.1.3 プール化・6型・mod6・NEWS/MENU 流用)")
print("対象: DRAFT_RULES §12.1.3 PRICE / SKILL / bridge / fixtures klk052・klk052b")
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
