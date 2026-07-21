#!/usr/bin/env python3
"""
KLK-029 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions N1-N15 from
docs/designs/KLK-029.md §4.6 / §9 against セクション内型プール方式（VOICE/FLOW/STAFF）:

  縦串 生成規約     .claude/skills/draft-generate/templates/DRAFT_RULES.md（§12.1.2 / §14）
  縦串 スキル定義   .claude/skills/draft-generate/SKILL.md（手順3）・.claude/skills/draft-regenerate/SKILL.md（手順3）
  主 golden         tests/fixtures/klk029/{index-a/b/c,compare}.html + instruction.json（1col×top→offset0）
  副 golden         tests/fixtures/klk029b/{index-a/b/c,compare}.html + instruction.json（1col×below-hero→offset3）

Source of truth = 設計書 §4.6（N群）。check_klk021/022/023.py と同型（正規表現・文字列検索・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。modifier()/css_layout_rule()/distinct3() は check_klk023.py から移植。

Run: python3 tests/site/check_klk029.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()
REGEN = open(os.path.join(ROOT, ".claude", "skills", "draft-regenerate", "SKILL.md"), encoding="utf-8").read()

NEW_COLS = {"1col", "2col-full-left", "2col-full-right", "2col-body-left", "2col-body-right", "3col"}
NAV_ENUM = {"top", "below-hero"}
ARCHETYPE_ENUM = {"stack-centered", "split-editorial", "banded-showcase"}

# §12.1.2 型プール（index 0〜4・順序固定）
POOL = {
    "voice": ["voice-cards", "voice-quote-stack", "voice-feature", "voice-two-col", "voice-slider"],
    "flow": ["flow-row", "flow-timeline", "flow-number-card", "flow-arrow-band", "flow-vertical-split"],
    "staff": ["staff-grid", "staff-hscroll", "staff-feature", "staff-list", "staff-two-col"],
}
ALL_MARKERS = [m for sec in ("voice", "flow", "staff") for m in POOL[sec]]

# §12.1.2 オフセット表（data-columns × navPosition → offset・12セル全書き下し）
OFFSET = {
    ("1col", "top"): 0, ("1col", "below-hero"): 3,
    ("2col-full-left", "top"): 1, ("2col-full-left", "below-hero"): 4,
    ("2col-full-right", "top"): 2, ("2col-full-right", "below-hero"): 0,
    ("2col-body-left", "top"): 3, ("2col-body-left", "below-hero"): 1,
    ("2col-body-right", "top"): 4, ("2col-body-right", "below-hero"): 2,
    ("3col", "top"): 0, ("3col", "below-hero"): 3,
}
# §12.1.2 割り当て表（offset → 案A/B/C の pool index・5行）
ASSIGN = {0: (0, 1, 2), 1: (1, 2, 3), 2: (2, 3, 4), 3: (3, 4, 0), 4: (4, 0, 1)}

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def attr(html, name):
    m = re.search(r'%s="([^"]+)"' % re.escape(name), html)
    return m.group(1) if m else None


def modifier(html, base, prefix):
    m = re.search(r'class="%s (%s[a-z-]+)"' % (base, prefix), html)
    return m.group(1) if m else None


def all_pins(html):
    return set(re.findall(r'class="pin">([A-Z0-9-]+)<', html))


def body_pins(html):
    pins = re.findall(r'class="pin">([A-Z0-9-]+)<', html)
    return tuple(sorted(p for p in pins if p not in ("NAV-01", "MV-01", "FOOTER-01")))


def m_main(html):
    m = re.search(r"--m-main\s*:\s*(#[0-9a-fA-F]{3,8})", html)
    return m.group(1).lower() if m else None


def css_layout_rule(html, token):
    """.token を含む CSS セレクタが実レイアウト宣言（grid/flex/order/grid-column 等）を持つか。"""
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


class Golden:
    """1つの golden セット（klk029 or klk029b）を読み込み、派生値を保持する。"""

    def __init__(self, name):
        self.name = name
        fx = os.path.join(ROOT, "tests", "fixtures", name)
        self.A = open(os.path.join(fx, "index-a.html"), encoding="utf-8").read()
        self.B = open(os.path.join(fx, "index-b.html"), encoding="utf-8").read()
        self.C = open(os.path.join(fx, "index-c.html"), encoding="utf-8").read()
        self.COMPARE = open(os.path.join(fx, "compare.html"), encoding="utf-8").read()
        self.INSTR = json.load(open(os.path.join(fx, "instruction.json"), encoding="utf-8"))
        self.goldens = (("a", self.A), ("b", self.B), ("c", self.C))
        self.DC = [attr(h, "data-columns") for _, h in self.goldens]
        self.NAV = [attr(h, "data-nav-position") for _, h in self.goldens]
        self.AR = [attr(h, "data-archetype") for _, h in self.goldens]
        self.MM = [m_main(h) for _, h in self.goldens]
        self.VOICE = [modifier(h, "m-voice", "voice-") for _, h in self.goldens]
        self.FLOW = [modifier(h, "m-flow", "flow-") for _, h in self.goldens]
        self.STAFF = [modifier(h, "m-staff", "staff-") for _, h in self.goldens]
        self.BODY = [body_pins(h) for _, h in self.goldens]
        self.want_body = tuple(sorted(k + "-01" for k in self.INSTR.get("sections", [])))


G = [Golden("klk029"), Golden("klk029b")]


# N1 3案 data-columns 同一・enum内（両 golden とも 1col）
n1 = all(len(set(g.DC)) == 1 and g.DC[0] in NEW_COLS for g in G)
check("N1 data-columns 同一・enum内 (両 golden とも 1col)",
      n1, "; ".join(f"{g.name}:{g.DC}" for g in G))

# N2 本文 sections 集合が3案同一かつ instruction.sections と一致
n2 = all(len(set(g.BODY)) == 1 and g.BODY[0] == g.want_body for g in G)
check("N2 本文 sections 集合が3案同一・instruction.sections と一致 (公平比較)",
      n2, "; ".join(f"{g.name}: 本文={g.BODY[0]} / instr={g.want_body}" for g in G))

# N3 --m-main 相違・data-archetype 相違（既存軸の非回帰確認）
n3 = all(distinct3(g.MM) and distinct3(g.AR) and all(a in ARCHETYPE_ENUM for a in g.AR) for g in G)
check("N3 --m-main 相違・data-archetype 相違[enum3] (既存軸の非回帰)",
      n3, "; ".join(f"{g.name}: main={g.MM} archetype={g.AR}" for g in G))

# N4/N5/N6 VOICE/FLOW/STAFF マーカーが案間 distinct かつ各プール enum(5値)に属する
for sec, key in (("N4 VOICE", "voice"), ("N5 FLOW", "flow"), ("N6 STAFF", "staff")):
    enum = set(POOL[key])
    ok = True
    det = []
    for g in G:
        vals = getattr(g, key.upper())
        d = distinct3(vals) and all(v in enum for v in vals)
        ok = ok and d
        det.append(f"{g.name}:{vals}({'distinct/enum内' if d else 'NG'})")
    check(f"{sec} 型が案間 distinct・プール enum(5型) 内", ok, "; ".join(det))

# N7 各プールマーカーが実 grid/flex/order 宣言を伴う（飾りでない）
n7_ok = True
n7_det = []
for g in G:
    for letter, h in g.goldens:
        for key in ("voice", "flow", "staff"):
            tok = modifier(h, "m-" + key, key + "-")
            r = css_layout_rule(h, tok)
            n7_ok = n7_ok and r
            if not r:
                n7_det.append(f"{g.name}/{letter}/{tok}=NG")
check("N7 各プールマーカーが実レイアウト宣言 grid/flex/order を伴う (飾りでない)",
      n7_ok, "; ".join(n7_det) if n7_det else "全マーカーで実CSS差を確認")

# N8 表整合: 各 golden の (a,b,c) マーカー index が §12.1.2 の (オフセット表→割り当て表) の期待と一致
n8_ok = True
n8_det = []
for g in G:
    dc, nav = g.DC[0], g.NAV[0]
    nav_ok = all(n == nav for n in g.NAV) and nav in NAV_ENUM
    offset = OFFSET.get((dc, nav))
    idxs = ASSIGN.get(offset)
    exp = {"voice": [], "flow": [], "staff": []}
    for i in range(3):
        for key in ("voice", "flow", "staff"):
            exp[key].append(POOL[key][idxs[i]])
    match = (nav_ok and g.VOICE == exp["voice"] and g.FLOW == exp["flow"] and g.STAFF == exp["staff"])
    n8_ok = n8_ok and match
    n8_det.append(f"{g.name}: ({dc}×{nav})→offset{offset}→idx{idxs} 一致={match}")
check("N8 表整合 (オフセット表→割り当て表の期待マーカーと golden が一致・決定性の固定)",
      n8_ok, "; ".join(n8_det))

# N9 プール到達: klk029 と klk029b の union で各プールの5マーカー全てが出現
n9_ok = True
n9_det = []
for key in ("voice", "flow", "staff"):
    seen = set()
    for g in G:
        seen |= set(getattr(g, key.upper()))
    full = set(POOL[key])
    ok = seen >= full
    n9_ok = n9_ok and ok
    n9_det.append(f"{key}: 出現={sorted(seen)} 全5={ok}")
check("N9 プール到達 (2 golden の union で VOICE/FLOW/STAFF 各5マーカー全出現)",
      n9_ok, "; ".join(n9_det))

# N10 各案の健全性: 番地=選択集合+NAV/MV/FOOTER・@media print・アタリa・依存0
n10_ok = True
n10_det = []
for g in G:
    want = set(g.want_body) | {"NAV-01", "MV-01", "FOOTER-01"}
    for letter, h in g.goldens:
        pins = all_pins(h)
        prt = "@media print" in h
        atari = 'class="atari"' in h and 'class="desc"' in h
        solo = no_ext_deps(h)
        ok = (pins == want) and prt and atari and solo
        n10_ok = n10_ok and ok
        if not ok:
            n10_det.append(f"{g.name}/{letter}:番地={pins==want}/print={prt}/アタリ={atari}/依存0={solo}")
check("N10 各案の健全性 (番地=選択集合+NAV/MV/FOOTER・@media print・アタリa方式・外部依存0)",
      n10_ok, "; ".join(n10_det) if n10_det else "両 golden 全6案で健全")

# N11 DRAFT_RULES §12.1.2 文言
r_head = "12.1.2" in RULES
r_terms = all(t in RULES for t in ("型プール", "オフセット表", "割り当て"))
r_markers = [m for m in ALL_MARKERS if m not in RULES]
r_noop = ("no-op" in RULES and "そのセクションが出ない" in RULES)
n11 = r_head and r_terms and not r_markers and r_noop
check("N11 DRAFT_RULES §12.1.2 文言 (型プール・オフセット表・割り当て・15マーカー・未選択no-op)",
      n11, f"§12.1.2={r_head}, 用語={r_terms}, 欠落マーカー={r_markers or 0}, no-op記述={r_noop}")

# N12 SKILL 手順3 文言
k_terms = all(t in SKILL for t in ("オフセット表", "割り当て表", "プール"))
k_markers = [m for m in ALL_MARKERS if m not in SKILL]
n12 = k_terms and not k_markers
check("N12 SKILL 手順3 文言 (プール選択・オフセット表参照・15マーカー列挙)",
      n12, f"用語={k_terms}, 欠落マーカー={k_markers or 0}")

# N13 セキュリティ/依存（全 golden: 外部URL0・秘密0・プレースホルダ明記）
_ALLOW = ("www.w3.org", "example.com", "example.org", "example.net")
secret_re = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)


def _host(u):
    m = re.match(r"https?://([^/\s\"')]+)", u)
    return m.group(1).lower() if m else ""


n13_ok = True
n13_det = []
for g in G:
    for label, txt in (("a", g.A), ("b", g.B), ("c", g.C), ("compare", g.COMPARE)):
        ext = [u for u in re.findall(r'https?://[^\s"\')（]+', txt) if _host(u) not in _ALLOW]
        sec = [ln for ln, line in enumerate(txt.splitlines(), 1) if secret_re.search(line)]
        ph = ("プレースホルダ" in txt or "実在の顧客" in txt or "サンプル" in txt)
        ok = (not ext) and (not sec) and ph
        n13_ok = n13_ok and ok
        if not ok:
            n13_det.append(f"{g.name}/{label}:外部URL={ext or 0}/秘密={sec or 0}/PH={ph}")
check("N13 セキュリティ/依存 (klk029・klk029b 全ゴールデン: 外部URL0・秘密0・プレースホルダ明記)",
      n13_ok, "; ".join(n13_det) if n13_det else "両 golden 全ファイルで安全")

# N14 既存回帰: §12.1.1 の離散マーカーと instruction.sections が残存（additive 確認）
r_1211 = all(t in RULES for t in ("stack-centered", "pat-cards", "img-top"))
r_sections = "instruction.sections" in RULES
n14 = r_1211 and r_sections
check("N14 既存回帰保持 (§12.1.1 stack-centered/pat-cards/img-top・instruction.sections が残存・additive)",
      n14, f"§12.1.1 マーカー={r_1211}, instruction.sections={r_sections}")

# N15 部分再生成整合の文言: DRAFT_RULES §14 と draft-regenerate SKILL に再付与ルール
def _regen_tokens(txt):
    return all(t in txt for t in ("data-columns", "data-nav-position", "letter", "再付与")) \
        and ("VOICE" in txt and "FLOW" in txt and "STAFF" in txt)


r_rules14 = "14. 部分再生成" in RULES and _regen_tokens(RULES)
r_regen = _regen_tokens(REGEN)
n15 = r_rules14 and r_regen
check("N15 部分再生成整合の文言 (DRAFT_RULES §14・draft-regenerate SKILL に VOICE/FLOW/STAFF マーカー再付与)",
      n15, f"DRAFT_RULES §14={r_rules14}, draft-regenerate SKILL={r_regen}")

# Report
print("=" * 78)
print("KLK-029 static acceptance checks (docs/designs/KLK-029.md §4.6 N群 を正とする)")
print("対象: fixtures/klk029・klk029b/{index-a/b/c,compare}.html + instruction.json / DRAFT_RULES.md / SKILL.md ×2")
print("=" * 78)
failed = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print(f"[{status}] {name}")
    print(f"        {detail}")
print("-" * 78)
print(f"{len(results)} checks, {failed} failed")
print()
print("D群（test_palette_klk029.py）: Quality Gate 全緑 / fixtures の git 追跡（D2）")
print("M群（tester 手動・ブラウザ）: 同一指示書で3案の VOICE/FLOW/STAFF が目に見えて違う型で表示される")
sys.exit(1 if failed else 0)
