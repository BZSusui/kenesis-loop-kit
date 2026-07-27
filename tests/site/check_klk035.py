#!/usr/bin/env python3
"""
KLK-035 acceptance-condition checker (static / no browser required).

セクション型プール拡充 第1弾（VOICE/FLOW/STAFF を各5→6型・新型 *-zigzag を index5 に追加）の
静的受け入れ条件（docs/designs/KLK-035.md §9）を検証する。

  縦串 生成規約   .claude/skills/draft-generate/templates/DRAFT_RULES.md（§12.1.2 の (1)型プール表 (2)オフセット表 (3)割り当て表）
  主 golden       tests/fixtures/klk035/{index-a/b/c,compare}.html + instruction.json（2col-body-right×top=offset4→(4,5,0)・R1）
  既存 golden     tests/fixtures/klk029（offset0={0,1,2}）・klk029b（offset3={3,4,5}・index-c は KLK-035 で index5 へ更新）
  R2 ドリフト検出 DRAFT_RULES 本文の表 ＝ check_klk029.py 定数 ＝ check_klk034.py 定数 の三者一致（ast で安全抽出）

check_klk029.py と同型（正規表現・文字列・Python標準のみ・exit 0/1・ネットワーク非使用）。
★R2: check_klk029/034 は import すると sys.exit する（トップレベル実行）ため import しない。ast で POOL/OFFSET/ASSIGN
  の代入ノードのみ literal_eval して安全に取り出す（実行副作用なし）。DRAFT_RULES 本文は Markdown 表を正規表現でパース。

Run: python3 tests/site/check_klk035.py
Exit code 0 = all pass, 1 = at least one fail.
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()

EXPECT_N = 6
NEW_MARKERS = ("voice-zigzag", "flow-zigzag", "staff-zigzag")
SECTIONS = ("voice", "flow", "staff")

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# DRAFT_RULES §12.1.2 本文の表パース（本文＝型プールの正）
# ---------------------------------------------------------------------------
def _seg(start, end):
    i = RULES.index(start)
    j = RULES.index(end, i)
    return RULES[i:j]


def parse_pool_from_rules():
    seg = _seg("**(1) 型プール", "**(2) オフセット表")
    pool = {}
    for sec in SECTIONS:
        seen = []
        # 型プール表の当該セクション行から `sec-...` マーカーを出現順に拾う（`.m-voice` は prefix 不一致で拾わない）
        for m in re.finditer(r'`(' + sec + r'-[a-z-]+)`', seg):
            if m.group(1) not in seen:
                seen.append(m.group(1))
        pool[sec] = seen
    return pool


def parse_offset_from_rules():
    seg = _seg("**(2) オフセット表", "**(3) 割り当て表")
    off = {}
    for m in re.finditer(r'`(1col|2col-[a-z-]+|3col)`\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|', seg):
        col, top, below = m.group(1), int(m.group(2)), int(m.group(3))
        off[(col, "top")] = top
        off[(col, "below-hero")] = below
    return off


def parse_assign_from_rules():
    seg = _seg("**(3) 割り当て表", "- 全12セルの offset 集合")
    asn = {}
    for m in re.finditer(r'^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|', seg, re.M):
        o, a, b, c = (int(x) for x in m.groups())
        asn[o] = (a, b, c)
    return asn


R_POOL = parse_pool_from_rules()
R_OFFSET = parse_offset_from_rules()
R_ASSIGN = parse_assign_from_rules()


# ---------------------------------------------------------------------------
# checker 定数の安全抽出（ast・実行しない）
# ---------------------------------------------------------------------------
def consts_from(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in ("POOL", "OFFSET", "ASSIGN"):
                    out[t.id] = ast.literal_eval(node.value)
    return out


def norm_pool(pool):
    """POOL のキー大小（029=小文字/034=大文字）を吸収して {小文字sec: [markers]} に正規化。"""
    return {k.lower(): list(v) for k, v in pool.items()}


C29 = consts_from(os.path.join(ROOT, "tests", "site", "check_klk029.py"))
C34 = consts_from(os.path.join(ROOT, "tests", "site", "check_klk034.py"))


# ---------------------------------------------------------------------------
# golden 読み込み・ユーティリティ
# ---------------------------------------------------------------------------
def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def attr(html, name):
    m = re.search(r'%s="([^"]+)"' % re.escape(name), html)
    return m.group(1) if m else None


def modifier(html, base, prefix):
    m = re.search(r'class="%s (%s[a-z-]+)"' % (base, prefix), html)
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
        if re.search(r'grid-template-columns|flex-direction|grid-auto|grid-column|grid-row|order\s*:', m.group(1)):
            return True
    return False


def no_ext_deps(html):
    return not (re.search(r'<link\b[^>]*rel=["\']?stylesheet', html, re.I)
                or re.search(r'<script\b[^>]*\bsrc=', html, re.I)
                or re.search(r'fonts\.(googleapis|gstatic)\.com|cdn\.|unpkg\.com|jsdelivr', html, re.I)
                or re.search(r'<img\b[^>]*\bsrc=["\']?https?:', html, re.I))


def distinct3(vals):
    return len(set(vals)) == 3 and all(v is not None for v in vals)


K35 = {ltr: gread("klk035", "index-%s.html" % ltr) for ltr in ("a", "b", "c")}
K35_COMPARE = gread("klk035", "compare.html")


# ===========================================================================
# E1 本文パース: 各セクション6型・新型 index5・順序
# ===========================================================================
e1_ok = all(len(R_POOL[s]) == EXPECT_N for s in SECTIONS)
e1_new = all(R_POOL[s][5] == "%s-zigzag" % s for s in SECTIONS)
check("E1 DRAFT_RULES 型プール表 (各6型・index5=*-zigzag)",
      e1_ok and e1_new,
      "; ".join("%s=%s" % (s, R_POOL[s]) for s in SECTIONS))

# E2 制約A: 3プール長が等しい（本文パース）
e2 = len({len(R_POOL[s]) for s in SECTIONS}) == 1
check("E2 制約A: VOICE/FLOW/STAFF の型数が等しい（本文パース）", e2,
      "lengths=%s / DRAFT本文に制約明文=%s" % ({s: len(R_POOL[s]) for s in SECTIONS},
                                              "常に等しく N" in RULES))

# E3 到達可能性: オフセット表の値集合 ⊇ {0..5}・割り当て表の全index ⊇ {0..5}
off_vals = set(R_OFFSET.values())
asn_idx = set()
for o, tup in R_ASSIGN.items():
    asn_idx |= set(tup)
e3 = off_vals >= set(range(EXPECT_N)) and asn_idx >= set(range(EXPECT_N)) and len(R_ASSIGN) == EXPECT_N
check("E3 到達可能性 (offset値集合⊇{0..5}・割り当て全index⊇{0..5}・6行)", e3,
      "offset値=%s / assign行数=%d / index集合=%s" % (sorted(off_vals), len(R_ASSIGN), sorted(asn_idx)))

# E4 巡回3窓 distinct: 割り当て各行が3値distinct
e4 = all(len(set(R_ASSIGN[o])) == 3 for o in R_ASSIGN)
check("E4 割り当て各行が3値 distinct（3案で型が重複しない）", e4,
      "; ".join("%d:%s" % (o, R_ASSIGN[o]) for o in sorted(R_ASSIGN)))

# E5 R2 三者一致: DRAFT本文 = check_klk029 定数 = check_klk034 定数
p_rules, p29, p34 = R_POOL, norm_pool(C29.get("POOL", {})), norm_pool(C34.get("POOL", {}))
pool_ok = (p_rules == p29 == p34)
offset_ok = (R_OFFSET == C29.get("OFFSET") == C34.get("OFFSET"))
assign_ok = (R_ASSIGN == C29.get("ASSIGN") == C34.get("ASSIGN"))
e5 = pool_ok and offset_ok and assign_ok
det5 = "POOL一致=%s OFFSET一致=%s ASSIGN一致=%s" % (pool_ok, offset_ok, assign_ok)
if not pool_ok:
    det5 += " | rules=%s 029=%s 034=%s" % (p_rules, p29, p34)
check("E5 R2ドリフト検出: 本文表 = check_klk029定数 = check_klk034定数（三者一致）", e5, det5)

# E6 klk035 表引き: 2col-body-right×top=offset4→(4,5,0) の期待マーカーと golden 一致
off = R_OFFSET[("2col-body-right", "top")]
idxs = R_ASSIGN[off]
exp = {ltr: {} for ltr in ("a", "b", "c")}
for i, ltr in enumerate(("a", "b", "c")):
    for s in SECTIONS:
        exp[ltr][s] = R_POOL[s][idxs[i]]
act = {}
e6_det = []
e6_ok = (off == 4 and idxs == (4, 5, 0))
for ltr in ("a", "b", "c"):
    h = K35[ltr]
    got = {"voice": modifier(h, "m-voice", "voice-"),
           "flow": modifier(h, "m-flow", "flow-"),
           "staff": modifier(h, "m-staff", "staff-")}
    act[ltr] = got
    m = (got == exp[ltr])
    e6_ok = e6_ok and m
    if not m:
        e6_det.append("%s: 期待%s 実%s" % (ltr, exp[ltr], got))
check("E6 klk035 表引き (2col-body-right×top→offset4→(4,5,0)・案A=idx4/案B=idx5新型/案C=idx0)",
      e6_ok, "; ".join(e6_det) if e6_det else "offset=%d idxs=%s 3案とも期待どおり" % (off, idxs))

# E7 新型3つが実 grid/flex/order を伴う（klk035 案B と klk029b/index-c の両方で・飾りでない）
e7_ok = True
e7_det = []
for src_name, html in (("klk035/b", K35["b"]), ("klk029b/c", gread("klk029b", "index-c.html"))):
    for mk in NEW_MARKERS:
        r = css_layout_rule(html, mk)
        e7_ok = e7_ok and r
        if not r:
            e7_det.append("%s/%s=飾り" % (src_name, mk))
check("E7 新型 *-zigzag が実レイアウト宣言 grid/flex/order を伴う (klk035案B・klk029b案C)",
      e7_ok, "; ".join(e7_det) if e7_det else "新型3つ×2ファイルで実CSS差を確認")

# E8 到達可能性の golden 実証: klk029(offset0)∪klk029b(offset3) で各プール6マーカー全出現
e8_ok = True
e8_det = []
for s in SECTIONS:
    seen = set()
    for name in ("klk029", "klk029b"):
        for ltr in ("a", "b", "c"):
            mk = modifier(gread(name, "index-%s.html" % ltr), "m-" + s, s + "-")
            if mk:
                seen.add(mk)
    full = set(R_POOL[s])
    ok = seen >= full
    e8_ok = e8_ok and ok
    e8_det.append("%s: 出現%d/6 %s" % (s, len(seen & full), "OK" if ok else ("欠=%s" % sorted(full - seen))))
check("E8 到達可能性 golden 実証 (klk029∪klk029b で各プール6型全出現・klk029b案C=index5 の反映確認)",
      e8_ok, "; ".join(e8_det))

# E9 klk035 健全性: 番地=選択集合+NAV/MV/FOOTER・@media print・アタリa・依存0・プレースホルダ
WANT_PINS = {"NAV-01", "MV-01", "VOICE-01", "FLOW-01", "STAFF-01", "CTA-01", "FOOTER-01"}
e9_ok = True
e9_det = []
for ltr in ("a", "b", "c"):
    h = K35[ltr]
    pins = all_pins(h)
    ok = (pins == WANT_PINS and "@media print" in h and 'class="atari"' in h and no_ext_deps(h)
          and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h)
          and attr(h, "data-columns") == "2col-body-right")
    e9_ok = e9_ok and ok
    if not ok:
        e9_det.append("%s: 番地=%s print=%s 依存0=%s dc=%s" % (
            ltr, pins == WANT_PINS, "@media print" in h, no_ext_deps(h), attr(h, "data-columns")))
check("E9 klk035 健全性 (番地7種各1・@media print・アタリa・外部依存0・プレースホルダ・2col-body-right)",
      e9_ok, "; ".join(e9_det) if e9_det else "3案とも健全")

# E10 klk035 3案 distinct（--m-main・各型マーカー）＋archetype 3値
e10_mm = distinct3([m_main(K35[l]) for l in ("a", "b", "c")])
e10_ar = distinct3([attr(K35[l], "data-archetype") for l in ("a", "b", "c")])
e10_types = all(distinct3([act[l][s] for l in ("a", "b", "c")]) for s in SECTIONS)
e10 = e10_mm and e10_ar and e10_types
check("E10 klk035 3案 distinct (--m-main・data-archetype・各プール型)",
      e10, "main distinct=%s / archetype distinct=%s / 型 distinct=%s" % (e10_mm, e10_ar, e10_types))

# E11 SKILL/本文の N=6 追随（offset 0〜5・新型マーカーが本文とSKILLに存在）
e11_rules = all(mk in RULES for mk in NEW_MARKERS) and "index 0〜5" in RULES
e11_skill = all(mk in SKILL for mk in NEW_MARKERS) and "offset 0〜5" in SKILL
check("E11 規約追随 (DRAFT_RULES/SKILL に新型3マーカー・offset 0〜5)",
      e11_rules and e11_skill, "RULES=%s SKILL=%s" % (e11_rules, e11_skill))

# Report
print("=" * 78)
print("KLK-035 static acceptance checks (docs/designs/KLK-035.md §9 を正とする)")
print("対象: DRAFT_RULES §12.1.2 本文パース / check_klk029・034 定数(ast) / fixtures klk035・klk029・klk029b")
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
print("D群（test_palette_klk035.py）: Quality Gate 全緑 / fixtures の git 追跡")
print("M群（tester 手動・ブラウザ）: 同一指示書で3案の VOICE/FLOW/STAFF に新型 *-zigzag が見た目で現れる")
sys.exit(1 if failed else 0)
