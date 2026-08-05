#!/usr/bin/env python3
"""
KLK-051 acceptance-condition checker (static / no browser required).

NEWS セクションのプール化（§12.1.3・6型・mod6・「1カード/行を繰り返す」共通項で FAQ/PRICE 流用可）の
静的受け入れ条件を検証する。check_klk049（SNS）と同型。

  縦串 生成規約   DRAFT_RULES §12.1.3 NEWS プール表(6型)・NEWS 割り当て表(mod6)・§2.1 NEWS 行
  縦串 スキル     SKILL.md 手順3（NEWS プール）
  縦串 ブリッジ   draft-gen/bridge.py validate_instruction（sectionOptions.NEWS.moreLink 込み）
  主 golden       tests/fixtures/klk051 （1col×top=offset0→(0,1,2)・案A=news-list/案B=news-cards/案C=news-media・NEWS moreLink デモ）
  副 golden       tests/fixtures/klk051b（1col×below-hero=offset3→(3,4,5)・案A=news-timeline/案B=news-table/案C=news-accordion）
  ドリフト検出    本文 NEWS プール/割り当て ＝ check_klk034.py の NEWS_POOL/NEWS_ASSIGN/POOL_1213/ASSIGN_1213（ast）

Python標準のみ・exit 0/1・bridge は import（validate 機能検証）。

Run: python3 tests/site/check_klk051.py
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

EXPECT_N = 6  # NEWS プールの型数
POOL_EXPECT = ["news-list", "news-cards", "news-media", "news-timeline", "news-table", "news-accordion"]
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_news_pool():
    seg = _seg("**NEWS プール", "**(2) 割り当て表")
    seen = []
    for m in re.finditer(r'`(news-[a-z-]+)`', seg):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def parse_news_assign():
    seg = _seg("**NEWS（6型", "**(3) 生成手順")
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


NEWS_POOL_RULES = parse_news_pool()
ASSIGN = parse_news_assign()
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


C34 = consts({"NEWS_POOL", "NEWS_ASSIGN"})


def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def news_marker(html):
    m = re.search(r'class="m-news (news-[a-z-]+)"', html)
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


K = {l: gread("klk051", "index-%s.html" % l) for l in ("a", "b", "c")}
K3 = {l: gread("klk051b", "index-%s.html" % l) for l in ("a", "b", "c")}  # offset3 golden（新型 3,4,5 実演）
INSTR = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk051", "instruction.json"), encoding="utf-8"))

# N1 §12.1.3 NEWS プール（6型）＋§2.1 NEWS 行が §12.1.3 に言及
n1 = (NEWS_POOL_RULES == POOL_EXPECT and "NEWS プール" in RULES and "§12.1.3 プール（6型" in RULES)
check("N1 §12.1.3 NEWS プール (6型・list/cards/media/timeline/table/accordion・§2.1 NEWS 行が §12.1.3 プール言及)",
      n1, "pool=%s" % NEWS_POOL_RULES)

# N2 NEWS 割り当て表 6行・巡回mod6・distinct
n2 = (len(ASSIGN) == 6 and all(ASSIGN[o] == (o % EXPECT_N, (o + 1) % EXPECT_N, (o + 2) % EXPECT_N) for o in ASSIGN)
      and all(len(set(ASSIGN[o])) == 3 for o in ASSIGN))
check("N2 NEWS 割り当て表 (6行・巡回mod6・各行distinct)", n2, "assign=%s" % ASSIGN)

# N3 到達可能性 index{0..5}
reach = set()
for off in OFFSET.values():
    reach |= set(ASSIGN[off])
check("N3 到達可能性 (全offsetから NEWS index{0..5} 全到達＝新型 timeline/table/accordion 含む)",
      reach >= set(range(EXPECT_N)), "到達=%s" % sorted(reach))

# N4 ドリフト検出: 本文 = check_klk034 NEWS_POOL/NEWS_ASSIGN・POOL_1213/ASSIGN_1213 の NEWS 参照
d_pool = (NEWS_POOL_RULES == list(C34.get("NEWS_POOL", [])) == POOL_EXPECT)
d_assign = (C34.get("NEWS_ASSIGN") == ASSIGN)
d_p1213 = (dict_name_ref("POOL_1213", "NEWS") == "NEWS_POOL")
d_a1213 = (dict_name_ref("ASSIGN_1213", "NEWS") == "NEWS_ASSIGN")
check("N4 ドリフト検出 (本文NEWS = check_klk034 NEWS_POOL/NEWS_ASSIGN・POOL_1213[NEWS]=NEWS_POOL・ASSIGN_1213[NEWS]=NEWS_ASSIGN)",
      d_pool and d_assign and d_p1213 and d_a1213,
      "pool=%s assign=%s POOL_1213=%s ASSIGN_1213=%s" % (d_pool, d_assign, d_p1213, d_a1213))

# N5 klk051 表引き: offset0→(0,1,2)・NEWS=(news-list,news-cards,news-media)
off = OFFSET[("1col", "top")]
idxs = ASSIGN[off]
exp = tuple(NEWS_POOL_RULES[i] for i in idxs)
act = tuple(news_marker(K[l]) for l in ("a", "b", "c"))
n5 = (off == 0 and idxs == (0, 1, 2) and act == exp)
check("N5 klk051 表引き (1col×top→offset0→(0,1,2)・NEWS=(news-list,news-cards,news-media))",
      n5, "offset=%s idxs=%s 期待%s 実%s" % (off, idxs, exp, act))

# N6 各NEWS型の実CSS差＋news-cards が3列カード・news-media が画像左メディア行
n6_all = all(css_layout_rule(K[l], news_marker(K[l])) for l in ("a", "b", "c"))
n6_list = css_layout_rule(K["a"], "news-list")
n6_cards = ('grid-template-columns: repeat(3, 1fr)' in K["b"] and 'class="news-card"' in K["b"])
n6_media = css_layout_rule(K["c"], "news-media") and ('class="mrow"' in K["c"])
check("N6 各NEWS型の実CSS差 (news-list=行リスト・news-cards=3列カード・news-media=画像左メディア行・飾りでない)",
      n6_all and n6_list and n6_cards and n6_media,
      "全案実CSS=%s list=%s cards3列=%s media=%s" % (n6_all, n6_list, n6_cards, n6_media))

# N7 moreLink opt-in デモ: instruction に NEWS.moreLink・全案の NEWS 直後に .sec-more（§4.3 併用）
news_ml = ((INSTR.get("sectionOptions") or {}).get("NEWS") or {}).get("moreLink")
n7 = (isinstance(news_ml, dict) and news_ml.get("label")
      and all(K[l].count('class="sec-more"') == 1 for l in ("a", "b", "c")))
check("N7 moreLink opt-in デモ (instruction.NEWS.moreLink・全案 NEWS に .sec-more×1＝§4.3 併用)",
      n7, "NEWS.moreLink=%s .sec-more数=%s" % (bool(news_ml), {l: K[l].count('class=\"sec-more\"') for l in 'abc'}))

# N8 健全性: NEWS distinct・番地5種各1・外部URL0・実埋め込み(iframe)なし・print・PH
WANT = {"NAV-01", "MV-01", "NEWS-01", "CTA-01", "FOOTER-01"}
n8 = True
n8_det = []
for l in ("a", "b", "c"):
    h = K[l]
    ok = (all_pins(h) == WANT and not re.search(r'(src|href)="https?:', h)
          and "<iframe" not in h and "@media print" in h
          and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h))
    n8 = n8 and ok
    if not ok:
        n8_det.append("%s: 番地=%s iframe無=%s" % (l, all_pins(h) == WANT, "<iframe" not in h))
check("N8 健全性 (NEWS 3案distinct・番地5種各1・外部URL0・実埋め込み(iframe)なし・print・PH)",
      n8 and distinct3(act), "; ".join(n8_det) if n8_det else "3案とも健全・NEWS=%s" % (act,))

# N9 bridge: klk051 instruction が通過＋NEWS.moreLink の受理/拒否
q9_instr = bridge.validate_instruction(INSTR)[0]
base = {"schema": "design-draft-instruction", "version": 1, "industry": {"resolved": "クリニック・医院"},
        "layout": {"columns": "1col"}, "colors": {"main": "#2c5f8a"}}
base_ext = json.loads(json.dumps(base)); base_ext["sectionOptions"] = {"NEWS": {"moreLink": {"label": "お知らせ一覧を見る"}}}
bad = json.loads(json.dumps(base)); bad["sectionOptions"] = {"NEWS": {"moreLink": {"label": "x", "href": "https://evil.example"}}}
n9 = (q9_instr is True and bridge.validate_instruction(base_ext)[0] is True
      and bridge.validate_instruction(bad)[0] is False)
check("N9 bridge.validate_instruction (klk051 instruction 通過・NEWS.moreLink 受理・外部URL href 拒否)",
      n9, "instr=%s 正常moreLink=%s 外部href拒否=%s" % (q9_instr,
          bridge.validate_instruction(base_ext)[0], not bridge.validate_instruction(bad)[0]))

# N10 規約文言: SKILL に NEWS プール・§2.1 に NEWS-01
n10 = ("NEWS（6型" in SKILL and ".m-news" in SKILL and "NEWS-01" in RULES)
check("N10 規約文言 (SKILL 手順3 に NEWS プール・.m-news・§2.1 に NEWS-01)", n10,
      "SKILL NEWS=%s .m-news=%s NEWS-01=%s" % ("NEWS（6型" in SKILL, ".m-news" in SKILL, "NEWS-01" in RULES))

# N11 klk051b（offset3）表引き: offset3→(3,4,5)＝案A=news-timeline/案B=news-table/案C=news-accordion＋新型 実CSS差
off3 = OFFSET[("1col", "below-hero")]
idxs3 = ASSIGN[off3]
exp3 = tuple(NEWS_POOL_RULES[i] for i in idxs3)
act3 = tuple(news_marker(K3[l]) for l in ("a", "b", "c"))
n11_map = (off3 == 3 and idxs3 == (3, 4, 5) and act3 == exp3)
n11_timeline = css_layout_rule(K3["a"], "news-timeline")
n11_table = css_layout_rule(K3["b"], "news-table") and ("grid-template-columns" in K3["b"])
n11_accordion = css_layout_rule(K3["c"], "news-accordion") and ("<details" in K3["c"])
n11_health = all(all_pins(K3[l]) >= {"NEWS-01"} and not re.search(r'(src|href)="https?:', K3[l]) and "<iframe" not in K3[l] for l in ("a", "b", "c"))
check("N11 klk051b offset3 表引き (offset3→(3,4,5)=news-timeline/news-table/news-accordion＋新型 実CSS差・実埋め込みなし)",
      n11_map and n11_timeline and n11_table and n11_accordion and n11_health,
      "NEWS 期待%s 実%s / timeline=%s table=%s accordion=%s 健全=%s" % (exp3, act3, n11_timeline, n11_table, n11_accordion, n11_health))

# Report
print("=" * 78)
print("KLK-051 static acceptance checks (NEWS §12.1.3 プール化・6型・mod6・FAQ/PRICE 流用の土台)")
print("対象: DRAFT_RULES §12.1.3 NEWS / SKILL / bridge / fixtures klk051・klk051b")
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
