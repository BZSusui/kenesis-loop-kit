#!/usr/bin/env python3
"""
KLK-057 acceptance-condition checker (static / no browser required).

HERO 埋め込み検索窓（§12.1.3(7)・方式B・SEARCH 連動・未選択は非生成・HERO一本化）の
静的受け入れ条件を検証する。

  縦串 生成規約   DRAFT_RULES §12.1.3(7) HERO 埋め込み検索窓・§2.1 SEARCH 行の注記
  縦串 スキル     SKILL.md 手順3（HERO 埋め込み検索窓）
  縦串 ブリッジ   draft-gen/bridge.py validate_instruction（instruction 通過）
  主 golden       tests/fixtures/klk057 （埋め込みON: full/center-scroll/overlap に .hero-search・SEARCH-01 なし）
  副 golden       tests/fixtures/klk057b（案A=panel-band 埋め込み／案B=SEARCH未選択で非生成／案C=split でフォールバック SEARCH-01）
  ドリフト検出    対応4型 ＝ check_klk034.py の HERO_SEARCH_TYPES（ast）／本文の型名列挙と一致

★特記: 検索窓は静的アタリ（<form action>/iframe/外部URL なし＝NFR-005）を検証。

Python標準のみ・exit 0/1・bridge は import。

Run: python3 tests/site/check_klk057.py
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

TYPES_EXPECT = ["full", "center-scroll", "overlap", "panel-band"]
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def gread(name, leaf):
    return open(os.path.join(ROOT, "tests", "fixtures", name, leaf), encoding="utf-8").read()


def all_pins(html):
    return set(re.findall(r'class="pin">([A-Z0-9-]+)<', html))


def hero_type(html):
    m = re.search(r'data-hero="([a-z-]+)"', html)
    return m.group(1) if m else None


def has_embed(html):
    return ('data-hero-search="on"' in html) and ('class="hero-search"' in html)


def static_safe(html):
    return (not re.search(r'<form[^>]*action=', html, re.I)
            and "<iframe" not in html
            and not re.search(r'(src|href)="https?:', html))


# --- check_klk034 定数（ast） ---
C34_TREE = ast.parse(open(os.path.join(ROOT, "tests", "site", "check_klk034.py"), encoding="utf-8").read())


def const(name):
    for node in C34_TREE.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    return None


K = {l: gread("klk057", "index-%s.html" % l) for l in ("a", "b", "c")}
K2 = {l: gread("klk057b", "index-%s.html" % l) for l in ("a", "b", "c")}
INSTR = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk057", "instruction.json"), encoding="utf-8"))
INSTR2 = json.load(open(os.path.join(ROOT, "tests", "fixtures", "klk057b", "instruction.json"), encoding="utf-8"))

# HS1 規約: §12.1.3(7) 節＋対応4型の明記＋§2.1 注記＋SKILL 記述
hs1 = ("(7) HERO / NAV 埋め込み検索窓" in RULES and "data-hero-search" in RULES and "data-nav-search" in RULES
       and "hero-search" in RULES and "nav-search" in RULES
       and all(t in RULES for t in TYPES_EXPECT)
       and "HERO / NAV 埋め込み検索窓" in SKILL and "data-hero-search" in SKILL and "data-nav-search" in SKILL and "KLK-057" in RULES)
check("HS1 規約 (§12.1.3(7) HERO/NAV 埋め込み検索窓・対応4型明記・.hero-search/.nav-search・§2.1注記・SKILL 記述)",
      hs1, "節=%s 4型=%s nav-search=%s SKILL=%s" % ("(7) HERO / NAV 埋め込み検索窓" in RULES, all(t in RULES for t in TYPES_EXPECT), "data-nav-search" in RULES, "HERO / NAV 埋め込み検索窓" in SKILL))

# HS2 ドリフト検出: check_klk034 HERO_SEARCH_TYPES == 期待4型
c34 = const("HERO_SEARCH_TYPES")
check("HS2 ドリフト検出 (check_klk034 HERO_SEARCH_TYPES == [full,center-scroll,overlap,panel-band])",
      c34 == TYPES_EXPECT, "HERO_SEARCH_TYPES=%s" % c34)

# HS3 klk057（埋め込みON）: 3案とも .hero-search 埋め込み・対応型・SEARCH-01 番地なし・静的
hs3 = True
hs3_det = []
for l in ("a", "b", "c"):
    h = K[l]
    ok = (has_embed(h) and hero_type(h) in TYPES_EXPECT and "SEARCH-01" not in all_pins(h) and static_safe(h))
    hs3 = hs3 and ok
    hs3_det.append("%s:hero=%s embed=%s SEARCH-01無=%s" % (l, hero_type(h), has_embed(h), "SEARCH-01" not in all_pins(h)))
check("HS3 klk057 埋め込みON (full/center-scroll/overlap に .hero-search・SEARCH-01 番地なし＝一本化・静的)",
      hs3, "; ".join(hs3_det))

# HS4 対応3型が実際に full/center-scroll/overlap で distinct
types057 = [hero_type(K[l]) for l in ("a", "b", "c")]
check("HS4 klk057 の HERO 型が full/center-scroll/overlap（対応型・distinct）",
      set(types057) == {"full", "center-scroll", "overlap"}, "types=%s" % types057)

# HS5 klk057b 案A: panel-band ＋ 埋め込み（対応4型の残り）・SEARCH-01 なし
hs5 = (hero_type(K2["a"]) == "panel-band" and has_embed(K2["a"]) and "SEARCH-01" not in all_pins(K2["a"]) and static_safe(K2["a"]))
check("HS5 klk057b 案A (HERO=panel-band ＋ 埋め込み検索窓・SEARCH-01 なし)",
      hs5, "hero=%s embed=%s SEARCH-01無=%s" % (hero_type(K2["a"]), has_embed(K2["a"]), "SEARCH-01" not in all_pins(K2["a"])))

# HS6 klk057b 案B: SEARCH 未選択 → 検索窓を非生成（.hero-search なし・data-hero-search なし）・SEARCH-01 も無し
b = K2["b"]
hs6 = (not has_embed(b) and 'class="hero-search"' not in b and "data-hero-search" not in b
       and "SEARCH-01" not in all_pins(b) and static_safe(b))
check("HS6 klk057b 案B (SEARCH 未選択 → HERO に検索窓を出さない[非生成]・SEARCH-01 も無し)",
      hs6, "embed無=%s hero-search無=%s SEARCH-01無=%s" % (not has_embed(b), 'class="hero-search"' not in b, "SEARCH-01" not in all_pins(b)))

# HS7 klk057b 案C: split(非対応) → HERO には埋め込まず、NAV-01 に .nav-search 埋め込み（配置優先②）・独立 SEARCH-01 なし
c = K2["c"]
hs7 = (hero_type(c) == "split" and 'class="hero-search"' not in c and "data-hero-search" not in c
       and 'data-nav-search="on"' in c and 'class="nav-search"' in c
       and "SEARCH-01" not in all_pins(c) and static_safe(c))
check("HS7 klk057b 案C (HERO=split[非対応] → NAV-01 に .nav-search 埋め込み・独立 SEARCH-01 なし・静的)",
      hs7, "hero=%s nav-search=%s SEARCH-01無=%s" % (hero_type(c), 'class="nav-search"' in c, "SEARCH-01" not in all_pins(c)))

# HS8 出力に仕組みの説明文を含めない（デモ用「非生成/フォールバック」キャプションが本文に無い）
cap_b = "SEARCH 未選択のため、この HERO には検索窓を出力していません" not in K2["b"]
cap_c = "HERO=split は埋め込み非対応のため" not in K2["c"]
check("HS8 出力清潔性 (仕組み説明のキャプション『非生成/フォールバック』が生成物本文に無い)",
      cap_b and cap_c, "b=%s c=%s" % (cap_b, cap_c))

# HS9 健全性＋bridge: 全golden 静的・番地整合・print・PH／instruction が通過
allg = list(K.values()) + list(K2.values())
health = all(("@media print" in h and static_safe(h)
              and ("プレースホルダ" in h or "サンプル" in h or "実在の顧客" in h)
              and {"NAV-01", "MV-01", "FOOTER-01"} <= all_pins(h)) for h in allg)
brz = (bridge.validate_instruction(INSTR)[0] is True and bridge.validate_instruction(INSTR2)[0] is True)
check("HS9 健全性＋bridge (全golden 静的・print・PH・番地整合／klk057・klk057b instruction が通過)",
      health and brz, "health=%s bridge=%s" % (health, brz))

# Report
print("=" * 78)
print("KLK-057 static acceptance checks (HERO 埋め込み検索窓・§12.1.3(7)・方式B)")
print("対象: DRAFT_RULES §12.1.3(7) / SKILL / bridge / fixtures klk057・klk057b")
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
