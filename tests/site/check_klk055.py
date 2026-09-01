#!/usr/bin/env python3
"""
KLK-055 acceptance-condition checker (static / no browser required).

CONTACT セクションのプール化（§12.1.3・6型・mod6・フォームは静的アタリ）の
静的受け入れ条件を検証する。check_klk051/052/053/054 と同型。

  縦串 生成規約   DRAFT_RULES §12.1.3 CONTACT プール表(6型)・CONTACT 割り当て表(mod6)・§2.1 CONTACT 行
  縦串 スキル     SKILL.md 手順3（CONTACT プール）
  縦串 ブリッジ   draft-gen/bridge.py validate_instruction（sectionOptions.CONTACT.moreLink 込み）
  主 golden       tests/fixtures/klk055 （1col×top=offset0→(0,1,2)・案A=contact-cta/案B=contact-form/案C=contact-split・CONTACT moreLink デモ）
  副 golden       tests/fixtures/klk055b（1col×below-hero=offset3→(3,4,5)・案A=contact-methods/案B=contact-banner/案C=contact-steps）
  ドリフト検出    本文 CONTACT プール/割り当て ＝ check_klk034.py の CONTACT_POOL/CONTACT_ASSIGN/POOL_1213/ASSIGN_1213（ast）

★特記: フォームは静的アタリ（<form action> の外部送信・iframe・外部 URL が無いこと＝NFR-005）を検証。

Python標準のみ・exit 0/1・bridge は import（validate 機能検証）。

Run: python3 tests/site/check_klk055.py
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

EXPECT_N = 6  # CONTACT プールの型数
POOL_EXPECT = ["contact-cta", "contact-form", "contact-split", "contact-methods", "contact-banner", "contact-steps"]
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_contact_pool():
    seg = _seg("**CONTACT プール", "**SEARCH プール")  # KLK-056: SEARCH プール表が後続に入るため end を SEARCH 手前へ
    seen = []
    for m in re.finditer(r'`(contact-[a-z-]+)`', seg):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def parse_contact_assign():
    seg = _seg("**CONTACT（6型", "**SEARCH（6型")  # KLK-056: SEARCH 割り当て表が後続に入るため end を SEARCH 手前へ
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


CONTACT_POOL_RULES = parse_contact_pool()
ASSIGN = parse_contact_assign()
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


C34 = consts({"CONTACT_POOL", "CONTACT_ASSIGN"})


def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def contact_marker(html):
    m = re.search(r'class="m-contact (contact-[a-z-]+)"', html)
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


def static_form_safe(html):
    """フォームは静的アタリ: 外部送信する <form action="http..."> や iframe・外部 URL が無いこと（NFR-005）。"""
    return (not re.search(r'<form[^>]*action=', html, re.I)
            and "<iframe" not in html
            and not re.search(r'(src|href)="https?:', html))


def distinct3(vals):
    return len(set(vals)) == 3 and all(v is not None for v in vals)


K = {l: gread("klk055", "index-%s.html" % l) for l in ("a", "b", "c")}
K3 = {l: gread("klk055b", "index-%s.html" % l) for l in ("a", "b", "c")}  # offset3 golden（新型 3,4,5 実演）
INSTR = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk055", "instruction.json"), encoding="utf-8"))

# C1 §12.1.3 CONTACT プール（6型）＋§2.1 CONTACT 行が §12.1.3 に言及＋SKILL/CONTACT-01（規約文言）
c1 = (CONTACT_POOL_RULES == POOL_EXPECT and "CONTACT プール" in RULES and "§12.1.3 プール（6型" in RULES
      and "CONTACT（6型" in SKILL and ".m-contact" in SKILL and "CONTACT-01" in RULES)
check("C1 §12.1.3 CONTACT プール (6型・cta/form/split/methods/banner/steps・§2.1 CONTACT 言及・SKILL .m-contact・CONTACT-01)",
      c1, "pool=%s SKILL=%s .m-contact=%s" % (CONTACT_POOL_RULES, "CONTACT（6型" in SKILL, ".m-contact" in SKILL))

# C2 CONTACT 割り当て表 6行・巡回mod6・distinct
c2 = (len(ASSIGN) == 6 and all(ASSIGN[o] == (o % EXPECT_N, (o + 1) % EXPECT_N, (o + 2) % EXPECT_N) for o in ASSIGN)
      and all(len(set(ASSIGN[o])) == 3 for o in ASSIGN))
check("C2 CONTACT 割り当て表 (6行・巡回mod6・各行distinct)", c2, "assign=%s" % ASSIGN)

# C3 到達可能性 index{0..5}
reach = set()
for off in OFFSET.values():
    reach |= set(ASSIGN[off])
check("C3 到達可能性 (全offsetから CONTACT index{0..5} 全到達＝新型 methods/banner/steps 含む)",
      reach >= set(range(EXPECT_N)), "到達=%s" % sorted(reach))

# C4 ドリフト検出: 本文 = check_klk034 CONTACT_POOL/CONTACT_ASSIGN・POOL_1213/ASSIGN_1213 の CONTACT 参照
d_pool = (CONTACT_POOL_RULES == list(C34.get("CONTACT_POOL", [])) == POOL_EXPECT)
d_assign = (C34.get("CONTACT_ASSIGN") == ASSIGN)
d_p1213 = (dict_name_ref("POOL_1213", "CONTACT") == "CONTACT_POOL")
d_a1213 = (dict_name_ref("ASSIGN_1213", "CONTACT") == "CONTACT_ASSIGN")
check("C4 ドリフト検出 (本文CONTACT = check_klk034 CONTACT_POOL/CONTACT_ASSIGN・POOL_1213[CONTACT]=CONTACT_POOL・ASSIGN_1213[CONTACT]=CONTACT_ASSIGN)",
      d_pool and d_assign and d_p1213 and d_a1213,
      "pool=%s assign=%s POOL_1213=%s ASSIGN_1213=%s" % (d_pool, d_assign, d_p1213, d_a1213))

# C5 klk055 表引き: offset0→(0,1,2)・CONTACT=(contact-cta,contact-form,contact-split)
off = OFFSET[("1col", "top")]
idxs = ASSIGN[off]
exp = tuple(CONTACT_POOL_RULES[i] for i in idxs)
act = tuple(contact_marker(K[l]) for l in ("a", "b", "c"))
c5 = (off == 0 and idxs == (0, 1, 2) and act == exp)
check("C5 klk055 表引き (1col×top→offset0→(0,1,2)・CONTACT=(contact-cta,contact-form,contact-split))",
      c5, "offset=%s idxs=%s 期待%s 実%s" % (off, idxs, exp, act))

# C6 各CONTACT型の実CSS差＋contact-form/split がフォーム(.c-field)を持つ
c6_all = all(css_layout_rule(K[l], contact_marker(K[l])) for l in ("a", "b", "c"))
c6_cta = css_layout_rule(K["a"], "contact-cta")
c6_form = css_layout_rule(K["b"], "contact-form") and ('class="c-field"' in K["b"])
c6_split = css_layout_rule(K["c"], "contact-split") and ("grid-template-columns" in K["c"]) and ('class="c-field"' in K["c"])
check("C6 各CONTACT型の実CSS差 (contact-cta=誘導・contact-form=縦フォーム(.c-field)・contact-split=2カラム(.c-field)・飾りでない)",
      c6_all and c6_cta and c6_form and c6_split,
      "全案実CSS=%s cta=%s form=%s split=%s" % (c6_all, c6_cta, c6_form, c6_split))

# C7 フォームは静的アタリ: 全案に <form action>/iframe/外部URL が無い（NFR-005）
c7 = all(static_form_safe(K[l]) for l in ("a", "b", "c"))
check("C7 フォームは静的アタリ (全案 <form action>/iframe/外部URL なし＝実送信なし・NFR-005)",
      c7, "静的安全=%s" % {l: static_form_safe(K[l]) for l in 'abc'})

# C8 moreLink opt-in デモ: instruction に CONTACT.moreLink・全案の CONTACT 直後に .sec-more（§4.3 併用）
contact_ml = ((INSTR.get("sectionOptions") or {}).get("CONTACT") or {}).get("moreLink")
c8 = (isinstance(contact_ml, dict) and contact_ml.get("label")
      and all(K[l].count('class="sec-more"') == 1 for l in ("a", "b", "c")))
check("C8 moreLink opt-in デモ (instruction.CONTACT.moreLink・全案 CONTACT に .sec-more×1＝§4.3 併用)",
      c8, "CONTACT.moreLink=%s .sec-more数=%s" % (bool(contact_ml), {l: K[l].count('class=\"sec-more\"') for l in 'abc'}))

# C9 健全性: CONTACT distinct・番地4種各1・print・PH
WANT = {"NAV-01", "MV-01", "CONTACT-01", "FOOTER-01"}
c9 = True
c9_det = []
for l in ("a", "b", "c"):
    h = K[l]
    ok = (all_pins(h) == WANT and static_form_safe(h) and "@media print" in h
          and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h))
    c9 = c9 and ok
    if not ok:
        c9_det.append("%s: 番地=%s 静的=%s" % (l, all_pins(h) == WANT, static_form_safe(h)))
check("C9 健全性 (CONTACT 3案distinct・番地4種各1・静的フォーム・print・PH)",
      c9 and distinct3(act), "; ".join(c9_det) if c9_det else "3案とも健全・CONTACT=%s" % (act,))

# C10 bridge: klk055 instruction が通過＋CONTACT.moreLink の受理/拒否
q10_instr = bridge.validate_instruction(INSTR)[0]
base = {"schema": "design-draft-instruction", "version": 1, "industry": {"resolved": "工務店・住宅"},
        "layout": {"columns": "1col"}, "colors": {"main": "#2c5f8a"}}
base_ext = json.loads(json.dumps(base)); base_ext["sectionOptions"] = {"CONTACT": {"moreLink": {"label": "アクセス・地図を見る"}}}
bad = json.loads(json.dumps(base)); bad["sectionOptions"] = {"CONTACT": {"moreLink": {"label": "x", "href": "https://evil.example"}}}
c10 = (q10_instr is True and bridge.validate_instruction(base_ext)[0] is True
       and bridge.validate_instruction(bad)[0] is False)
check("C10 bridge.validate_instruction (klk055 instruction 通過・CONTACT.moreLink 受理・外部URL href 拒否)",
      c10, "instr=%s 正常moreLink=%s 外部href拒否=%s" % (q10_instr,
           bridge.validate_instruction(base_ext)[0], not bridge.validate_instruction(bad)[0]))

# C11 klk055b（offset3）表引き: offset3→(3,4,5)＝案A=contact-methods/案B=contact-banner/案C=contact-steps＋新型 実CSS差＋静的
off3 = OFFSET[("1col", "below-hero")]
idxs3 = ASSIGN[off3]
exp3 = tuple(CONTACT_POOL_RULES[i] for i in idxs3)
act3 = tuple(contact_marker(K3[l]) for l in ("a", "b", "c"))
c11_map = (off3 == 3 and idxs3 == (3, 4, 5) and act3 == exp3)
c11_methods = css_layout_rule(K3["a"], "contact-methods") and ('class="contact-card"' in K3["a"]) and ("grid-template-columns" in K3["a"])
c11_banner = css_layout_rule(K3["b"], "contact-banner")
c11_steps = css_layout_rule(K3["c"], "contact-steps") and ("route-steps" in K3["c"])
c11_health = all(all_pins(K3[l]) >= {"CONTACT-01"} and static_form_safe(K3[l]) for l in ("a", "b", "c"))
check("C11 klk055b offset3 表引き (offset3→(3,4,5)=contact-methods/contact-banner/contact-steps＋新型 実CSS差＋静的フォーム)",
      c11_map and c11_methods and c11_banner and c11_steps and c11_health,
      "CONTACT 期待%s 実%s / methods=%s banner=%s steps=%s 健全=%s" % (exp3, act3, c11_methods, c11_banner, c11_steps, c11_health))

# Report
print("=" * 78)
print("KLK-055 static acceptance checks (CONTACT §12.1.3 プール化・6型・mod6・フォームは静的アタリ)")
print("対象: DRAFT_RULES §12.1.3 CONTACT / SKILL / bridge / fixtures klk055・klk055b")
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
