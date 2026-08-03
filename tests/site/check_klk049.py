#!/usr/bin/env python3
"""
KLK-049 acceptance-condition checker (static / no browser required).

SNS セクションのプール化（§12.1.3・3型 sns-grid/sns-slider/sns-cards・mod3・共通カード）の
静的受け入れ条件を検証する。check_klk036/044/048 と同型。

  縦串 生成規約   DRAFT_RULES §12.1.3 SNS プール表(3型)・SNS 割り当て表(mod3)・§2.1 SNS 行・§14 SNS-01
  縦串 スキル     SKILL.md 手順3（SNS プール）
  縦串 ブリッジ   draft-gen/bridge.py validate_instruction（sectionOptions.SNS.moreLink 込み）
  主 golden       tests/fixtures/klk049（1col×top=offset0→(0,1,2)・案A=sns-grid/案B=sns-slider/案C=sns-cards・SNS moreLink デモ）
  既存 golden     tests/fixtures/klk023/034/036（SNS 無し＝影響なし）
  ドリフト検出    本文 SNS プール/割り当て ＝ check_klk034.py の SNS_POOL/SNS_ASSIGN/POOL_1213/ASSIGN_1213（ast）

Python標準のみ・exit 0/1・bridge は import（validate 機能検証）。

Run: python3 tests/site/check_klk049.py
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

EXPECT_N = 6  # SNS プールの型数（KLK-050 で 3→6）
POOL_EXPECT = ["sns-grid", "sns-slider", "sns-cards", "sns-masonry", "sns-reels", "sns-feed"]
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_sns_pool():
    seg = _seg("**SNS プール", "**(2) 割り当て表")
    seen = []
    for m in re.finditer(r'`(sns-[a-z-]+)`', seg):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def parse_sns_assign():
    seg = _seg("**SNS（6型", "**(3) 生成手順")
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


SNS_POOL_RULES = parse_sns_pool()
ASSIGN = parse_sns_assign()
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


C34 = consts({"SNS_POOL", "SNS_ASSIGN"})


def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def attr(html, name):
    m = re.search(r'%s="([^"]+)"' % re.escape(name), html)
    return m.group(1) if m else None


def sns_marker(html):
    m = re.search(r'class="m-sns (sns-[a-z-]+)"', html)
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


K = {l: gread("klk049", "index-%s.html" % l) for l in ("a", "b", "c")}
K50 = {l: gread("klk050", "index-%s.html" % l) for l in ("a", "b", "c")}  # offset3 golden（新型 3,4,5 実演）
INSTR = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk049", "instruction.json"), encoding="utf-8"))

# S1 §12.1.3 SNS プール（6型）＋§2.1 SNS 行が §12.1.3 に言及
s1 = (SNS_POOL_RULES == POOL_EXPECT and "SNS プール" in RULES and "§12.1.3 プール（6型" in RULES)
check("S1 §12.1.3 SNS プール (6型・grid/slider/cards/masonry/reels/feed・§2.1 SNS 行が §12.1.3 プール言及)",
      s1, "pool=%s" % SNS_POOL_RULES)

# S2 SNS 割り当て表 6行・巡回mod6・distinct
s2 = (len(ASSIGN) == 6 and all(ASSIGN[o] == (o % EXPECT_N, (o + 1) % EXPECT_N, (o + 2) % EXPECT_N) for o in ASSIGN)
      and all(len(set(ASSIGN[o])) == 3 for o in ASSIGN))
check("S2 SNS 割り当て表 (6行・巡回mod6・各行distinct)", s2, "assign=%s" % ASSIGN)

# S3 到達可能性 index{0..5}
reach = set()
for off in OFFSET.values():
    reach |= set(ASSIGN[off])
check("S3 到達可能性 (全offsetから SNS index{0..5} 全到達＝新型 masonry/reels/feed 含む)", reach >= set(range(EXPECT_N)), "到達=%s" % sorted(reach))

# S4 ドリフト検出: 本文 = check_klk034 SNS_POOL/SNS_ASSIGN・POOL_1213/ASSIGN_1213 の SNS 参照
d_pool = (SNS_POOL_RULES == list(C34.get("SNS_POOL", [])) == POOL_EXPECT)
d_assign = (C34.get("SNS_ASSIGN") == ASSIGN)
d_p1213 = (dict_name_ref("POOL_1213", "SNS") == "SNS_POOL")
d_a1213 = (dict_name_ref("ASSIGN_1213", "SNS") == "SNS_ASSIGN")
check("S4 ドリフト検出 (本文SNS = check_klk034 SNS_POOL/SNS_ASSIGN・POOL_1213[SNS]=SNS_POOL・ASSIGN_1213[SNS]=SNS_ASSIGN)",
      d_pool and d_assign and d_p1213 and d_a1213,
      "pool=%s assign=%s POOL_1213=%s ASSIGN_1213=%s" % (d_pool, d_assign, d_p1213, d_a1213))

# S5 klk049 表引き: offset0→(0,1,2)・SNS=(sns-grid,sns-slider,sns-cards)
off = OFFSET[("1col", "top")]
idxs = ASSIGN[off]
exp = tuple(SNS_POOL_RULES[i] for i in idxs)
act = tuple(sns_marker(K[l]) for l in ("a", "b", "c"))
s5 = (off == 0 and idxs == (0, 1, 2) and act == exp)
check("S5 klk049 表引き (1col×top→offset0→(0,1,2)・SNS=(sns-grid,sns-slider,sns-cards))",
      s5, "offset=%s idxs=%s 期待%s 実%s" % (off, idxs, exp, act))

# S6 各SNS型の実CSS差＋sns-cards が横並びカード(repeat(3,1fr))
s6_all = all(css_layout_rule(K[l], sns_marker(K[l])) for l in ("a", "b", "c"))
s6_cards = ('grid-template-columns: repeat(3, 1fr)' in K["c"] and 'class="sns-card"' in K["c"])
s6_grid = css_layout_rule(K["a"], "sns-grid")
s6_slider = css_layout_rule(K["b"], "sns-slider") and ("overflow-x" in K["b"])
check("S6 各SNS型の実CSS差 (sns-grid=格子grid・sns-slider=横スクロール・sns-cards=横並び3列カード・飾りでない)",
      s6_all and s6_cards and s6_grid and s6_slider,
      "全案実CSS=%s cards3列=%s grid=%s slider=%s" % (s6_all, s6_cards, s6_grid, s6_slider))

# S7 moreLink opt-in デモ: instruction に SNS.moreLink・全案の SNS 直後に .sec-more（§4.3 併用）
sns_ml = ((INSTR.get("sectionOptions") or {}).get("SNS") or {}).get("moreLink")
s7 = (isinstance(sns_ml, dict) and sns_ml.get("label")
      and all(K[l].count('class="sec-more"') == 1 for l in ("a", "b", "c")))
check("S7 moreLink opt-in デモ (instruction.SNS.moreLink・全案 SNS に .sec-more×1＝§4.3 併用)",
      s7, "SNS.moreLink=%s .sec-more数=%s" % (bool(sns_ml), {l: K[l].count('class=\"sec-more\"') for l in 'abc'}))

# S8 健全性: SNS distinct・番地6種各1・外部URL0・実埋め込み(iframe)なし
WANT = {"NAV-01", "MV-01", "ABOUT-01", "SNS-01", "CTA-01", "FOOTER-01"}
s8 = True
s8_det = []
for l in ("a", "b", "c"):
    h = K[l]
    ok = (all_pins(h) == WANT and not re.search(r'(src|href)="https?:', h)
          and "<iframe" not in h and "@media print" in h
          and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h))
    s8 = s8 and ok
    if not ok:
        s8_det.append("%s: 番地=%s iframe無=%s" % (l, all_pins(h) == WANT, "<iframe" not in h))
check("S8 健全性 (SNS 3案distinct・番地6種各1・外部URL0・実埋め込み(iframe)なし・print・PH)",
      s8 and distinct3(act), "; ".join(s8_det) if s8_det else "3案とも健全・SNS=%s" % (act,))

# S9 bridge: klk049 instruction が通過＋SNS.moreLink の受理/拒否
q9_instr = bridge.validate_instruction(INSTR)[0]
base = {"schema": "design-draft-instruction", "version": 1, "industry": {"resolved": "美容室・エステ・化粧品"},
        "layout": {"columns": "1col"}, "colors": {"main": "#7c6a58"}}
base_ext = json.loads(json.dumps(base)); base_ext["sectionOptions"] = {"SNS": {"moreLink": {"label": "投稿をもっと見る"}}}
bad = json.loads(json.dumps(base)); bad["sectionOptions"] = {"SNS": {"moreLink": {"label": "x", "href": "https://evil.example"}}}
s9 = (q9_instr is True and bridge.validate_instruction(base_ext)[0] is True
      and bridge.validate_instruction(bad)[0] is False)
check("S9 bridge.validate_instruction (klk049 instruction 通過・SNS.moreLink 受理・外部URL href 拒否)",
      s9, "instr=%s 正常moreLink=%s 外部href拒否=%s" % (q9_instr,
          bridge.validate_instruction(base_ext)[0], not bridge.validate_instruction(bad)[0]))

# S10 規約文言: SKILL に SNS プール・§14 に SNS-01
s10 = ("SNS（6型" in SKILL and ".m-sns" in SKILL and "SNS-01" in RULES)
check("S10 規約文言 (SKILL 手順3 に SNS プール・§14 に SNS-01 再付与)", s10,
      "SKILL SNS=%s §14 SNS-01=%s" % ("SNS（3型" in SKILL, "SNS-01" in RULES))

# S11 klk050（offset3）表引き: offset3→(3,4,5)＝案A=sns-masonry/案B=sns-reels/案C=sns-feed＋新型 実CSS差
off3 = OFFSET[("1col", "below-hero")]
idxs3 = ASSIGN[off3]
exp3 = tuple(SNS_POOL_RULES[i] for i in idxs3)
act3 = tuple(sns_marker(K50[l]) for l in ("a", "b", "c"))
s11_map = (off3 == 3 and idxs3 == (3, 4, 5) and act3 == exp3)
s11_masonry = css_layout_rule(K50["a"], "sns-masonry") and ("grid-auto-rows" in K50["a"] or "grid-row" in K50["a"])
s11_reels = css_layout_rule(K50["b"], "sns-reels") and ("overflow-x" in K50["b"])  # KLK-050調整: 正方サムネの横スクロール帯（9:16→正方）
s11_feed = css_layout_rule(K50["c"], "sns-feed") and ('class="sns-post"' in K50["c"]) and ("grid-template-columns" in K50["c"])  # 横並びグリッド
s11_health = all(all_pins(K50[l]) >= {"SNS-01"} and not re.search(r'(src|href)="https?:', K50[l]) and "<iframe" not in K50[l] for l in ("a", "b", "c"))
check("S11 klk050 offset3 表引き (offset3→(3,4,5)=sns-masonry/sns-reels/sns-feed＋新型 実CSS差・実埋め込みなし)",
      s11_map and s11_masonry and s11_reels and s11_feed and s11_health,
      "SNS 期待%s 実%s / masonry=%s reels=%s feed=%s 健全=%s" % (exp3, act3, s11_masonry, s11_reels, s11_feed, s11_health))

# Report
print("=" * 78)
print("KLK-049/050 static acceptance checks (SNS §12.1.3 プール化・6型・mod6・共通カード)")
print("対象: DRAFT_RULES §12.1.3 SNS / SKILL / bridge / fixtures klk049")
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
