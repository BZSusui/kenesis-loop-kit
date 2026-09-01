#!/usr/bin/env python3
"""
KLK-058 acceptance-condition checker (static / no browser required).

CTA マルチボタンと自動整列（§4.4・buttons 1〜4・文字数で single/row/stack/grid2/two-plus-one を選択）の
静的受け入れ条件を検証する。CTA は6型プールではなく content-driven 整列。

  縦串 生成規約   DRAFT_RULES §4.4 CTA マルチボタン・§2.1 CTA 行の注記
  縦串 スキル     SKILL.md 手順3（CTA マルチボタン整列）
  縦串 ブリッジ   draft-gen/bridge.py validate_instruction（sectionOptions.CTA.buttons 検証）
  主 golden       tests/fixtures/klk058 （row(2)/row(3)/two-plus-one）
  副 golden       tests/fixtures/klk058b（grid2(4)/single(1)/stack(2長文)）

★特記: ボタンは静的アタリ（href=#・<form action>/外部URL/iframe なし＝NFR-005）。

Python標準のみ・exit 0/1・bridge は import。

Run: python3 tests/site/check_klk058.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()

sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

MARKERS = ["single", "row", "stack", "grid2", "two-plus-one"]
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def all_pins(html):
    return set(re.findall(r'class="pin">([A-Z0-9-]+)<', html))


def cta_marker(html):
    m = re.search(r'class="cta-btns ([a-z0-9-]+)"', html)
    return m.group(1) if m else None


def btn_count(html):
    return len(re.findall(r'class="cta-btn[ "]', html))


def css_layout_rule(html, token):
    for m in re.finditer(r'\.%s\b[^{}]*\{([^}]*)\}' % re.escape(token), html):
        if re.search(r'grid-template-columns|flex-direction|grid-auto|grid-column|grid-row|order\s*:|flex-wrap|overflow-x', m.group(1)):
            return True
    return False


def static_safe(html):
    return (not re.search(r'<form[^>]*action=', html, re.I)
            and "<iframe" not in html
            and not re.search(r'(src|href)="https?:', html))


K = {l: gread("klk058", "index-%s.html" % l) for l in ("a", "b", "c")}
K2 = {l: gread("klk058b", "index-%s.html" % l) for l in ("a", "b", "c")}
INSTR = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk058", "instruction.json"), encoding="utf-8"))
INSTR2 = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk058b", "instruction.json"), encoding="utf-8"))

# CB1 規約: §4.4 節・整列マーカー5種・buttons 1〜4・wide 全幅・§2.1 注記・SKILL 記述
rules_nospace = re.sub(r"\s+", "", RULES)
cb1 = ("### 4.4 CTA マルチボタン" in RULES and "buttons" in RULES
       and all(m in RULES for m in MARKERS) and "grid-column:1/-1" in rules_nospace and "1〜4" in RULES
       and "CTA マルチボタン" in SKILL and "cta-btns" in SKILL and "KLK-058" in RULES)
check("CB1 規約 (§4.4・整列5種[single/row/stack/grid2/two-plus-one]・buttons1〜4・wide全幅・§2.1注記・SKILL)",
      cb1, "§4.4=%s 5種=%s wide=%s SKILL=%s" % ("### 4.4 CTA マルチボタン" in RULES, all(m in RULES for m in MARKERS), "grid-column:1/-1" in rules_nospace, "CTA マルチボタン" in SKILL))

# CB2 bridge: buttons の受理/拒否
base = {"schema": "design-draft-instruction", "version": 1, "industry": {"resolved": "スクール"},
        "layout": {"columns": "1col"}, "colors": {"main": "#2c5f8a"}}


def with_cta(cta):
    o = json.loads(json.dumps(base)); o["sectionOptions"] = {"CTA": cta}; return o


cb2_cases = [
    ("1〜4個の正常配列OK", bridge.validate_instruction(with_cta({"buttons": [{"label": "資料請求", "purpose": "document"}, {"label": "無料体験"}]}))[0] is True),
    ("href 相対OK", bridge.validate_instruction(with_cta({"buttons": [{"label": "詳細", "href": "#detail"}]}))[0] is True),
    ("0個はNG", bridge.validate_instruction(with_cta({"buttons": []}))[0] is False),
    ("5個はNG", bridge.validate_instruction(with_cta({"buttons": [{"label": "a"}, {"label": "b"}, {"label": "c"}, {"label": "d"}, {"label": "e"}]}))[0] is False),
    ("label 空はNG", bridge.validate_instruction(with_cta({"buttons": [{"label": ""}]}))[0] is False),
    ("label 40字超はNG", bridge.validate_instruction(with_cta({"buttons": [{"label": "あ" * 41}]}))[0] is False),
    ("purpose 不正はNG", bridge.validate_instruction(with_cta({"buttons": [{"label": "x", "purpose": "buy"}]}))[0] is False),
    ("href 外部URLはNG", bridge.validate_instruction(with_cta({"buttons": [{"label": "x", "href": "https://evil.example"}]}))[0] is False),
    ("配列でない buttons はNG", bridge.validate_instruction(with_cta({"buttons": {"label": "x"}}))[0] is False),
    ("従来 purpose/label 単一は後方互換OK", bridge.validate_instruction(with_cta({"purpose": "contact", "label": "お問い合わせ"}))[0] is True),
]
cb2_fail = [n for n, ok in cb2_cases if not ok]
check("CB2 bridge.validate_instruction (buttons 1〜4・label40字・purpose enum・href相対 の受理/拒否＋後方互換)",
      not cb2_fail, "失敗=%s" % (cb2_fail or "無し"))

# CB3 klk058 表引き: 案A=row(2)・案B=row(3)・案C=two-plus-one(3)・各静的
exp = {"a": ("row", 2), "b": ("row", 3), "c": ("two-plus-one", 3)}
cb3 = True
cb3_det = []
for l in ("a", "b", "c"):
    mk, n = cta_marker(K[l]), btn_count(K[l])
    ok = (mk == exp[l][0] and n == exp[l][1] and css_layout_rule(K[l], "cta-btns") and static_safe(K[l]))
    cb3 = cb3 and ok
    cb3_det.append("%s:marker=%s btn=%d" % (l, mk, n))
check("CB3 klk058 (案A=row×2・案B=row×3・案C=two-plus-one×3・実CSS・静的)", cb3, "; ".join(cb3_det))

# CB4 two-plus-one: 長文ボタンに wide（grid-column:1/-1）＋ CSS 定義
c = K["c"]
cb4 = ('class="cta-btn wide"' in c and re.search(r'\.two-plus-one\s+\.wide\s*\{[^}]*grid-column:\s*1\s*/\s*-1', c))
check("CB4 two-plus-one 全幅 (長文ボタン .cta-btn.wide＋.two-plus-one .wide{grid-column:1/-1})",
      cb4, "wide=%s CSS=%s" % ('class="cta-btn wide"' in c, bool(re.search(r'grid-column:\s*1\s*/\s*-1', c))))

# CB5 klk058b 表引き: 案A=grid2(4)・案B=single(1)・案C=stack(2)・各静的
exp2 = {"a": ("grid2", 4), "b": ("single", 1), "c": ("stack", 2)}
cb5 = True
cb5_det = []
for l in ("a", "b", "c"):
    mk, n = cta_marker(K2[l]), btn_count(K2[l])
    ok = (mk == exp2[l][0] and n == exp2[l][1] and css_layout_rule(K2[l], "cta-btns") and static_safe(K2[l]))
    cb5 = cb5 and ok
    cb5_det.append("%s:marker=%s btn=%d" % (l, mk, n))
check("CB5 klk058b (案A=grid2×4・案B=single×1・案C=stack×2・実CSS・静的)", cb5, "; ".join(cb5_det))

# CB6 grid2 が 2×2（grid-template-columns:1fr 1fr）
cb6 = bool(re.search(r'\.grid2\s*\{[^}]*grid-template-columns:\s*1fr\s+1fr', K2["a"]))
check("CB6 grid2 は 2×2 (grid-template-columns:1fr 1fr)", cb6, "grid2 CSS=%s" % cb6)

# CB7 マーカー網羅: 6golden で single/row/stack/grid2/two-plus-one が出そろう
seen = {cta_marker(K[l]) for l in "abc"} | {cta_marker(K2[l]) for l in "abc"}
cb7 = set(MARKERS) <= seen
check("CB7 整列マーカー網羅 (single/row/stack/grid2/two-plus-one が golden に出そろう)", cb7, "出現=%s" % sorted(seen))

# CB8 健全性＋bridge: 全golden 静的・番地(NAV/MV/CTA/FOOTER)・print・PH／instruction 通過
allg = list(K.values()) + list(K2.values())
WANT = {"NAV-01", "MV-01", "CTA-01", "FOOTER-01"}
health = all((all_pins(h) == WANT and static_safe(h) and "@media print" in h
              and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h)) for h in allg)
brz = (bridge.validate_instruction(INSTR)[0] is True and bridge.validate_instruction(INSTR2)[0] is True)
check("CB8 健全性＋bridge (全golden 静的・番地4種・print・PH／klk058・klk058b instruction 通過)",
      health and brz, "health=%s bridge=%s" % (health, brz))

# Report
print("=" * 78)
print("KLK-058 static acceptance checks (CTA マルチボタンと自動整列・§4.4)")
print("対象: DRAFT_RULES §4.4 / SKILL / bridge / fixtures klk058・klk058b")
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
