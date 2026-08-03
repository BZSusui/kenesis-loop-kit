#!/usr/bin/env python3
"""
KLK-048 acceptance-condition checker (static / no browser required).

詳細ページ誘導ボタンの横展開（§4.3・opt-in `sectionOptions.{KEY}.moreLink`・共通 `.sec-more`／`.sec-more-btn`）の
静的受け入れ条件を検証する。

  縦串 生成規約   DRAFT_RULES §4.3（.sec-more 規約・opt-in moreLink・十分な上余白・外部URL禁止）＋ feature-large が .sec-more 使用
  縦串 スキル     SKILL.md 手順3（moreLink 反映）
  縦串 ブリッジ   draft-gen/bridge.py validate_instruction（moreLink の label/href 検証）
  主 golden       tests/fixtures/klk044（案C feature-large=.sec-more 常設・GALLERY=opt-in moreLink で全案 .sec-more・instruction に sectionOptions.GALLERY.moreLink）
  既存 golden     tests/fixtures/klk023/034/036（moreLink 無し＝.sec-more を出さない・opt-in 不変）

Python標準のみ・exit 0/1。bridge は機能検証のため import する（check_klk034 と同型）。

Run: python3 tests/site/check_klk048.py
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

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def count(html, needle):
    return html.count(needle)


K44 = {l: gread("klk044", "index-%s.html" % l) for l in ("a", "b", "c")}
K44_INSTR = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk044", "instruction.json"), encoding="utf-8"))

# ---------------------------------------------------------------------------
# Q1 §4.3 規約文言: .sec-more/.sec-more-btn・opt-in moreLink・十分な上余白・外部URL禁止・既定OFF
# ---------------------------------------------------------------------------
q1 = ("### 4.3" in RULES and ".sec-more" in RULES and ".sec-more-btn" in RULES
      and "moreLink" in RULES and "opt-in" in RULES
      and "margin-top:40px" in RULES.replace(" ", "")
      and "外部" in RULES and "既定OFF" in RULES)
check("Q1 §4.3 規約 (.sec-more/.sec-more-btn・opt-in moreLink・上余白 margin-top:40px・外部URL禁止・既定OFF)",
      q1, "§4.3=%s .sec-more=%s moreLink=%s" % ("### 4.3" in RULES, ".sec-more-btn" in RULES, "moreLink" in RULES))

# Q2 SKILL 手順3 に moreLink 反映
q2 = ("moreLink" in SKILL and ".sec-more" in SKILL)
check("Q2 SKILL 手順3 (moreLink→.sec-more の反映ルール)", q2, "moreLink=%s .sec-more=%s" % ("moreLink" in SKILL, ".sec-more" in SKILL))

# Q3 feature-large が共通 .sec-more を使う（規約・golden とも）・旧 .feat-more は撤去
q3_rules = (".sec-more" in RULES and "feature-large" in RULES)
q3_no_featmore = all("feat-more" not in K44[l] for l in ("a", "b", "c"))  # 旧クラス全廃
q3_fl = ('class="sec-more"' in K44["c"])  # 案C feature-large が .sec-more を持つ
check("Q3 feature-large が .sec-more に統一 (規約参照・golden klk044 に .feat-more 残存なし・案C に .sec-more)",
      q3_rules and q3_no_featmore and q3_fl,
      "規約=%s feat-more撤去=%s 案C.sec-more=%s" % (q3_rules, q3_no_featmore, q3_fl))

# Q4 opt-in デモ: instruction に GALLERY.moreLink・全案の GALLERY に .sec-more・案C は2つ(GALLERY+feature-large)
gal_ml = ((K44_INSTR.get("sectionOptions") or {}).get("GALLERY") or {}).get("moreLink")
counts = {l: count(K44[l], 'class="sec-more"') for l in ("a", "b", "c")}
q4 = (isinstance(gal_ml, dict) and gal_ml.get("label")
      and counts["a"] == 1 and counts["b"] == 1 and counts["c"] == 2)
check("Q4 opt-in デモ (instruction.GALLERY.moreLink・案A/B=.sec-more×1(GALLERY)・案C=×2(GALLERY+feature-large))",
      q4, "GALLERY.moreLink=%s counts=%s" % (bool(gal_ml), counts))

# Q5 .sec-more-btn がテーマ追従(var(--m-main))・十分な上余白(margin-top:40px)・全案に規約CSSあり
q5 = True
q5_det = []
for l in ("a", "b", "c"):
    h = K44[l]
    has_css = (".sec-more-btn" in h and "var(--m-main)" in h)
    gap = re.search(r'\.sec-more\s*\{[^}]*margin-top:\s*40px', h)
    ok = has_css and bool(gap)
    q5 = q5 and ok
    if not ok:
        q5_det.append("%s: css=%s 余白40px=%s" % (l, has_css, bool(gap)))
check("Q5 .sec-more-btn テーマ追従(var(--m-main))＋上余白 margin-top:40px（全案）",
      q5, "; ".join(q5_det) if q5_det else "3案とも規約CSSあり・余白40px")

# Q6 外部URL禁止: .sec-more-btn の href が # または相対（http(s)/javascript/data なし）
q6 = True
q6_det = []
for l in ("a", "b", "c"):
    hrefs = re.findall(r'class="sec-more-btn"\s+href="([^"]*)"', K44[l])
    bad = [h for h in hrefs if re.match(r'\s*(?:https?:|//|javascript:|data:|vbscript:)', h, re.I)]
    if bad:
        q6 = False
        q6_det.append("%s: %s" % (l, bad))
check("Q6 .sec-more-btn の href が相対/# のみ（外部URL・危険スキーム 0）",
      q6, "; ".join(q6_det) if q6_det else "全案 href は # または相対")

# Q7 既存 golden 不変（moreLink 無し＝.sec-more を出さない・opt-in）
q7 = True
q7_det = []
for name in ("klk023", "klk034", "klk036"):
    for l in ("a", "b", "c"):
        h = gread(name, "index-%s.html" % l)
        n = count(h, 'class="sec-more"')
        if n != 0:
            q7 = False
            q7_det.append("%s/%s: .sec-more=%d" % (name, l, n))
check("Q7 既存golden不変 (klk023/034/036 は moreLink 無し＝.sec-more を出さない・opt-in)",
      q7, "; ".join(q7_det) if q7_det else "既存 golden に .sec-more 0（opt-in 維持）")

# Q8 bridge.validate_instruction: moreLink の受理/拒否
BASE = {
    "schema": "design-draft-instruction", "version": 1,
    "industry": {"resolved": "美容室・エステ・化粧品"},
    "layout": {"columns": "1col"}, "colors": {"main": "#2c5f8a"},
}


def _with_so(so):
    o = json.loads(json.dumps(BASE))
    o["sectionOptions"] = so
    return o


q8_cases = [
    ("正常な moreLink はOK", bridge.validate_instruction(_with_so({"GALLERY": {"moreLink": {"label": "一覧を見る"}}}))[0] is True),
    ("href 相対はOK", bridge.validate_instruction(_with_so({"NEWS": {"moreLink": {"label": "お知らせ一覧", "href": "news/"}}}))[0] is True),
    ("href '#' はOK", bridge.validate_instruction(_with_so({"MENU": {"moreLink": {"label": "料金一覧", "href": "#"}}}))[0] is True),
    ("外部URL href はNG", bridge.validate_instruction(_with_so({"GALLERY": {"moreLink": {"label": "x", "href": "https://evil.example.com"}}}))[0] is False),
    ("javascript: href はNG", bridge.validate_instruction(_with_so({"GALLERY": {"moreLink": {"label": "x", "href": "javascript:alert(1)"}}}))[0] is False),
    ("label 空はNG", bridge.validate_instruction(_with_so({"GALLERY": {"moreLink": {"label": "  "}}}))[0] is False),
    ("label 過長(41字)はNG", bridge.validate_instruction(_with_so({"GALLERY": {"moreLink": {"label": "あ" * 41}}}))[0] is False),
    ("moreLink 非オブジェクトはNG", bridge.validate_instruction(_with_so({"GALLERY": {"moreLink": "x"}}))[0] is False),
    ("moreLink 無しの sectionOptions は従来どおりOK", bridge.validate_instruction(_with_so({"CTA": {"purpose": "contact"}}))[0] is True),
]
q8_fail = [n for n, ok in q8_cases if not ok]
check("Q8 bridge.validate_instruction (moreLink label/href の受理・外部URL/危険スキーム/過長/空/型 の拒否)",
      not q8_fail, "失敗ケース=%s" % (q8_fail or "無し"))

# Q9 klk044 instruction.json 自体が validate_instruction を通る
q9_ok, q9_errs = bridge.validate_instruction(K44_INSTR)
check("Q9 klk044 instruction.json が validate_instruction を通過（GALLERY.moreLink 込み）",
      q9_ok, "; ".join(q9_errs) if not q9_ok else "通過")

# Q10 健全性: klk044 各案 外部URL0・.sec-more-btn は <a>（アクセシブル導線）
q10 = True
q10_det = []
for l in ("a", "b", "c"):
    h = K44[l]
    ext = re.search(r'(src|href)="https?:', h)
    a_btn = ('<a class="sec-more-btn"' in h)
    ok = (ext is None) and a_btn
    q10 = q10 and ok
    if not ok:
        q10_det.append("%s: 外部URL=%s <a>ボタン=%s" % (l, ext is not None, a_btn))
check("Q10 健全性 (klk044 外部URL0・.sec-more-btn は <a> リンク)",
      q10, "; ".join(q10_det) if q10_det else "3案とも健全")

# Report
print("=" * 78)
print("KLK-048 static acceptance checks (詳細誘導ボタン横展開・opt-in moreLink・共通 .sec-more)")
print("対象: DRAFT_RULES §4.3 / SKILL / bridge.validate_instruction / fixtures klk044・klk023/034/036")
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
print("D群（test_palette_klk048.py）: Quality Gate 全緑 / fixtures の git 追跡")
print("M群（tester 手動・ブラウザ）: moreLink 指定セクションに「一覧を見る」ボタンが十分な余白で出る")
sys.exit(1 if failed else 0)
