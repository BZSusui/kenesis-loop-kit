#!/usr/bin/env python3
"""
KLK-054 acceptance-condition checker (static / no browser required).

ACCESS セクションのプール化（§12.1.3・6型・mod6・全型に地図アタリ内包）の
静的受け入れ条件を検証する。check_klk051/052/053 と同型。

  縦串 生成規約   DRAFT_RULES §12.1.3 ACCESS プール表(6型)・ACCESS 割り当て表(mod6)・§2.1 ACCESS 行
  縦串 スキル     SKILL.md 手順3（ACCESS プール）
  縦串 ブリッジ   draft-gen/bridge.py validate_instruction（sectionOptions.ACCESS.moreLink 込み）
  主 golden       tests/fixtures/klk054 （1col×top=offset0→(0,1,2)・案A=map-side/案B=map-top/案C=map-overlay・ACCESS moreLink デモ）
  副 golden       tests/fixtures/klk054b（1col×below-hero=offset3→(3,4,5)・案A=map-hours/案B=map-cards/案C=map-steps）
  ドリフト検出    本文 ACCESS プール/割り当て ＝ check_klk034.py の ACCESS_POOL/ACCESS_ASSIGN/POOL_1213/ASSIGN_1213（ast）

★特記: 全6型に地図アタリ .map-atari を内包し、実地図/実埋め込み（iframe・外部URL）が無いこと（NFR-005）を検証。

Python標準のみ・exit 0/1・bridge は import（validate 機能検証）。

Run: python3 tests/site/check_klk054.py
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

EXPECT_N = 6  # ACCESS プールの型数
POOL_EXPECT = ["map-side", "map-top", "map-overlay", "map-hours", "map-cards", "map-steps"]
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_access_pool():
    seg = _seg("**ACCESS プール", "**(2) 割り当て表")
    seen = []
    for m in re.finditer(r'`(map-[a-z-]+)`', seg):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def parse_access_assign():
    seg = _seg("**ACCESS（6型", "**(3) 生成手順")
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


ACCESS_POOL_RULES = parse_access_pool()
ASSIGN = parse_access_assign()
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


C34 = consts({"ACCESS_POOL", "ACCESS_ASSIGN"})


def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def access_marker(html):
    m = re.search(r'class="m-access (map-[a-z-]+)"', html)
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


K = {l: gread("klk054", "index-%s.html" % l) for l in ("a", "b", "c")}
K3 = {l: gread("klk054b", "index-%s.html" % l) for l in ("a", "b", "c")}  # offset3 golden（新型 3,4,5 実演）
INSTR = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk054", "instruction.json"), encoding="utf-8"))

# A1 §12.1.3 ACCESS プール（6型）＋§2.1 ACCESS 行が §12.1.3 に言及
a1 = (ACCESS_POOL_RULES == POOL_EXPECT and "ACCESS プール" in RULES and "§12.1.3 プール（6型" in RULES)
check("A1 §12.1.3 ACCESS プール (6型・side/top/overlay/hours/cards/steps・§2.1 ACCESS 行が §12.1.3 プール言及)",
      a1, "pool=%s" % ACCESS_POOL_RULES)

# A2 ACCESS 割り当て表 6行・巡回mod6・distinct
a2 = (len(ASSIGN) == 6 and all(ASSIGN[o] == (o % EXPECT_N, (o + 1) % EXPECT_N, (o + 2) % EXPECT_N) for o in ASSIGN)
      and all(len(set(ASSIGN[o])) == 3 for o in ASSIGN))
check("A2 ACCESS 割り当て表 (6行・巡回mod6・各行distinct)", a2, "assign=%s" % ASSIGN)

# A3 到達可能性 index{0..5}
reach = set()
for off in OFFSET.values():
    reach |= set(ASSIGN[off])
check("A3 到達可能性 (全offsetから ACCESS index{0..5} 全到達＝新型 overlay/hours/cards/steps 含む)",
      reach >= set(range(EXPECT_N)), "到達=%s" % sorted(reach))

# A4 ドリフト検出: 本文 = check_klk034 ACCESS_POOL/ACCESS_ASSIGN・POOL_1213/ASSIGN_1213 の ACCESS 参照
d_pool = (ACCESS_POOL_RULES == list(C34.get("ACCESS_POOL", [])) == POOL_EXPECT)
d_assign = (C34.get("ACCESS_ASSIGN") == ASSIGN)
d_p1213 = (dict_name_ref("POOL_1213", "ACCESS") == "ACCESS_POOL")
d_a1213 = (dict_name_ref("ASSIGN_1213", "ACCESS") == "ACCESS_ASSIGN")
check("A4 ドリフト検出 (本文ACCESS = check_klk034 ACCESS_POOL/ACCESS_ASSIGN・POOL_1213[ACCESS]=ACCESS_POOL・ASSIGN_1213[ACCESS]=ACCESS_ASSIGN)",
      d_pool and d_assign and d_p1213 and d_a1213,
      "pool=%s assign=%s POOL_1213=%s ASSIGN_1213=%s" % (d_pool, d_assign, d_p1213, d_a1213))

# A5 klk054 表引き: offset0→(0,1,2)・ACCESS=(map-side,map-top,map-overlay)
off = OFFSET[("1col", "top")]
idxs = ASSIGN[off]
exp = tuple(ACCESS_POOL_RULES[i] for i in idxs)
act = tuple(access_marker(K[l]) for l in ("a", "b", "c"))
a5 = (off == 0 and idxs == (0, 1, 2) and act == exp)
check("A5 klk054 表引き (1col×top→offset0→(0,1,2)・ACCESS=(map-side,map-top,map-overlay))",
      a5, "offset=%s idxs=%s 期待%s 実%s" % (off, idxs, exp, act))

# A6 各ACCESS型の実CSS差＋全型に地図アタリ .map-atari 内包
a6_all = all(css_layout_rule(K[l], access_marker(K[l])) for l in ("a", "b", "c"))
a6_map = all(('class="map-atari"' in K[l]) for l in ("a", "b", "c"))
a6_side = css_layout_rule(K["a"], "map-side") and ("grid-template-columns" in K["a"])
a6_top = css_layout_rule(K["b"], "map-top")
a6_overlay = css_layout_rule(K["c"], "map-overlay")
check("A6 各ACCESS型の実CSS差＋全型に地図アタリ内包 (map-side=2カラム・map-top=上地図・map-overlay=重ね・全案 .map-atari)",
      a6_all and a6_map and a6_side and a6_top and a6_overlay,
      "全案実CSS=%s map-atari全案=%s side=%s top=%s overlay=%s" % (a6_all, a6_map, a6_side, a6_top, a6_overlay))

# A7 moreLink opt-in デモ: instruction に ACCESS.moreLink・全案の ACCESS 直後に .sec-more（§4.3 併用）
access_ml = ((INSTR.get("sectionOptions") or {}).get("ACCESS") or {}).get("moreLink")
a7 = (isinstance(access_ml, dict) and access_ml.get("label")
      and all(K[l].count('class="sec-more"') == 1 for l in ("a", "b", "c")))
check("A7 moreLink opt-in デモ (instruction.ACCESS.moreLink・全案 ACCESS に .sec-more×1＝§4.3 併用)",
      a7, "ACCESS.moreLink=%s .sec-more数=%s" % (bool(access_ml), {l: K[l].count('class=\"sec-more\"') for l in 'abc'}))

# A8 健全性: ACCESS distinct・番地5種各1・外部URL0・実地図/実埋め込み(iframe)なし・print・PH
WANT = {"NAV-01", "MV-01", "ACCESS-01", "CTA-01", "FOOTER-01"}
a8 = True
a8_det = []
for l in ("a", "b", "c"):
    h = K[l]
    # 実埋め込み（実 Google Map 等）は必ず iframe か https URL を伴う。説明文中の「Google Map 想定」表記は許容。
    ok = (all_pins(h) == WANT and not re.search(r'(src|href)="https?:', h)
          and "<iframe" not in h and not re.search(r'(google\.com/maps|maps\.google|googleapis)', h, re.I)
          and "@media print" in h
          and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h))
    a8 = a8 and ok
    if not ok:
        a8_det.append("%s: 番地=%s iframe無=%s https無=%s" % (l, all_pins(h) == WANT, "<iframe" not in h, not re.search(r'(src|href)="https?:', h)))
check("A8 健全性 (ACCESS 3案distinct・番地5種各1・外部URL0・実地図/実埋め込みなし[iframe・実mapURL無]・print・PH)",
      a8 and distinct3(act), "; ".join(a8_det) if a8_det else "3案とも健全・ACCESS=%s" % (act,))

# A9 bridge: klk054 instruction が通過＋ACCESS.moreLink の受理/拒否
q9_instr = bridge.validate_instruction(INSTR)[0]
base = {"schema": "design-draft-instruction", "version": 1, "industry": {"resolved": "カフェ・飲食店"},
        "layout": {"columns": "1col"}, "colors": {"main": "#2c5f8a"}}
base_ext = json.loads(json.dumps(base)); base_ext["sectionOptions"] = {"ACCESS": {"moreLink": {"label": "大きな地図で見る"}}}
bad = json.loads(json.dumps(base)); bad["sectionOptions"] = {"ACCESS": {"moreLink": {"label": "x", "href": "https://evil.example"}}}
a9 = (q9_instr is True and bridge.validate_instruction(base_ext)[0] is True
      and bridge.validate_instruction(bad)[0] is False)
check("A9 bridge.validate_instruction (klk054 instruction 通過・ACCESS.moreLink 受理・外部URL href 拒否)",
      a9, "instr=%s 正常moreLink=%s 外部href拒否=%s" % (q9_instr,
          bridge.validate_instruction(base_ext)[0], not bridge.validate_instruction(bad)[0]))

# A10 規約文言: SKILL に ACCESS プール・§2.1 に ACCESS-01
a10 = ("ACCESS（6型" in SKILL and ".m-access" in SKILL and "ACCESS-01" in RULES)
check("A10 規約文言 (SKILL 手順3 に ACCESS プール・.m-access・§2.1 に ACCESS-01)", a10,
      "SKILL ACCESS=%s .m-access=%s ACCESS-01=%s" % ("ACCESS（6型" in SKILL, ".m-access" in SKILL, "ACCESS-01" in RULES))

# A11 klk054b（offset3）表引き: offset3→(3,4,5)＝案A=map-hours/案B=map-cards/案C=map-steps＋新型 実CSS差＋地図アタリ内包
off3 = OFFSET[("1col", "below-hero")]
idxs3 = ASSIGN[off3]
exp3 = tuple(ACCESS_POOL_RULES[i] for i in idxs3)
act3 = tuple(access_marker(K3[l]) for l in ("a", "b", "c"))
a11_map = (off3 == 3 and idxs3 == (3, 4, 5) and act3 == exp3)
a11_hours = css_layout_rule(K3["a"], "map-hours") and ("hours-table" in K3["a"])
a11_cards = css_layout_rule(K3["b"], "map-cards") and ('class="access-card"' in K3["b"]) and ("grid-template-columns" in K3["b"])
a11_steps = css_layout_rule(K3["c"], "map-steps") and ("route-steps" in K3["c"])
a11_mapatari = all(('class="map-atari"' in K3[l]) for l in ("a", "b", "c"))
a11_health = all(all_pins(K3[l]) >= {"ACCESS-01"} and not re.search(r'(src|href)="https?:', K3[l]) and "<iframe" not in K3[l] and not re.search(r'(google\.com/maps|maps\.google|googleapis)', K3[l], re.I) for l in ("a", "b", "c"))
check("A11 klk054b offset3 表引き (offset3→(3,4,5)=map-hours/map-cards/map-steps＋新型 実CSS差＋全型 .map-atari・実地図/実埋め込みなし)",
      a11_map and a11_hours and a11_cards and a11_steps and a11_mapatari and a11_health,
      "ACCESS 期待%s 実%s / hours=%s cards=%s steps=%s map-atari=%s 健全=%s" % (exp3, act3, a11_hours, a11_cards, a11_steps, a11_mapatari, a11_health))

# Report
print("=" * 78)
print("KLK-054 static acceptance checks (ACCESS §12.1.3 プール化・6型・mod6・全型に地図アタリ内包)")
print("対象: DRAFT_RULES §12.1.3 ACCESS / SKILL / bridge / fixtures klk054・klk054b")
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
