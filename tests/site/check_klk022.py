#!/usr/bin/env python3
"""
KLK-022 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S11 from
docs/designs/KLK-022.md §9（S群）against セクション選択機能（本文コンテンツの選択と反映）:

  SCR-001 ビルダー   draft-gen/index.html（UIコントロール・純ロジック定数・buildInstruction）
  ブリッジ           draft-gen/bridge.py（validate_instruction の新フィールド検証）
  生成規約           .claude/skills/draft-generate/templates/DRAFT_RULES.md（§2 / §2.1）
  スキル定義         .claude/skills/draft-generate/SKILL.md（手順3）
  ゴールデン(1col)    tests/fixtures/klk022/index-1col.html + instruction-1col.json
  ゴールデン(2col)    tests/fixtures/klk022/index-2col.html + instruction-2col.json

Source of truth = 設計書 §9（S群）。check_klk009/021.py と同型（正規表現・文字列検索・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。D群（Quality Gate＋動的スモーク＋git check-ignore）は
tests/test_palette_klk022.py が、M群（実生成＋ブラウザ実機）は tester が手動確認する。成果物・ゴールデンは変更しない。

Run: python3 tests/site/check_klk022.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FX = os.path.join(ROOT, "tests", "fixtures", "klk022")
IDX1_PATH = os.path.join(FX, "index-1col.html")
IDX2_PATH = os.path.join(FX, "index-2col.html")
INSTR1_PATH = os.path.join(FX, "instruction-1col.json")
INSTR2_PATH = os.path.join(FX, "instruction-2col.json")
SCR = os.path.join(ROOT, "draft-gen", "index.html")
BRIDGE = os.path.join(ROOT, "draft-gen", "bridge.py")
RULES_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md")
SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md")

IDX1 = open(IDX1_PATH, encoding="utf-8").read()
IDX2 = open(IDX2_PATH, encoding="utf-8").read()
INSTR1 = json.load(open(INSTR1_PATH, encoding="utf-8"))
INSTR2 = json.load(open(INSTR2_PATH, encoding="utf-8"))
SCRSRC = open(SCR, encoding="utf-8").read()
BR = open(BRIDGE, encoding="utf-8").read()
RULES = open(RULES_PATH, encoding="utf-8").read()
SKILL = open(SKILL_PATH, encoding="utf-8").read()

SECTION_KEYS = ["NEWS", "ABOUT", "MENU", "PRICE", "GALLERY", "SEARCH", "FLOW",
                "VOICE", "STAFF", "FAQ", "SNS", "ACCESS", "CTA", "CONTACT"]
NAV_POSITIONS = ["top", "below-hero"]
CTA_PURPOSES = ["contact", "order", "reserve", "document", "signup", "custom"]
CTA_DEFAULT_LABEL = {
    "contact": "お問い合わせはこちら", "order": "ご注文はこちら", "reserve": "ご予約はこちら",
    "document": "資料を請求する", "signup": "友だち追加・会員登録",
}

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def pins_in_order(html):
    return re.findall(r'class="pin">([A-Z0-9-]+)<', html)


def scr_logic_slice():
    """SCR-001 の純ロジック領域（const COLUMN_KEYS 〜 function render() 直前）。"""
    a = SCRSRC.find("const COLUMN_KEYS")
    b = SCRSRC.find("function render()")
    return SCRSRC[a:b] if (a >= 0 and b > a) else ""


LOGIC = scr_logic_slice()

# ===========================================================================
# S1 SCR-001 UI コントロール（ヘッダー位置・14セクション・CTA目的）
# ===========================================================================
nav_radio = (re.search(r'name="navPosition"[^>]*value="top"', SCRSRC) is not None
             and re.search(r'name="navPosition"[^>]*value="below-hero"', SCRSRC) is not None)
sec_boxes = [k for k in SECTION_KEYS
             if re.search(r'name="section"[^>]*value="%s"' % k, SCRSRC) is not None]
cta_ui = ('id="ctaPurpose"' in SCRSRC) and ('id="ctaLabel"' in SCRSRC)
cta_opts = all(('value="%s"' % p) in SCRSRC for p in CTA_PURPOSES)
# ★契約更新（KLK-087）: 本文セクションの選び方が **チェックボックス14個 → ページ構成リスト**
#   へ変わった（同じセクションを複数置けるようになったため、チェックボックスでは表せない）。
#   守りたい能力は「**14種すべてを本文に入れられること**」で、そこは変わらない。
#   いまは #compAddBtns が SECTION_KEYS から追加ボタンを作るので、
#   検査対象を「14種の語彙が純ロジックにあり、リストUIがそれを描く」ことへ移す。
comp_ui = ('id="compList"' in SCRSRC) and ('id="compAddBtns"' in SCRSRC)
comp_render = ('function renderComposition' in SCRSRC) and ("SECTION_KEYS.forEach" in SCRSRC)
check(
    "S1 SCR-001 UI (navPosition ラジオ・本文14種を置けるページ構成リスト・CTA目的select+自由入力)",
    nav_radio and comp_ui and comp_render and cta_ui and cta_opts,
    f"navラジオ={nav_radio}, 構成リストUI={comp_ui}, 14種から追加={comp_render}, "
    f"CTA目的UI={cta_ui}, CTA目的値6={cta_opts}",
)

# ===========================================================================
# S2 純ロジック定数（render() 前・スモークが slice する領域）
# ===========================================================================
c_section = re.search(r"const SECTION_KEYS\s*=\s*\[([^\]]*)\]", LOGIC)
c_section_n = len(re.findall(r"'[A-Z]+'", c_section.group(1))) if c_section else 0
c_nav = "const NAV_POSITIONS" in LOGIC and "'top'" in LOGIC and "'below-hero'" in LOGIC
c_cta = "const CTA_PURPOSES" in LOGIC and all(("'%s'" % p) in LOGIC for p in CTA_PURPOSES)
c_norm = "function normalizeSections" in LOGIC
check(
    "S2 純ロジック定数 (SECTION_KEYS14/NAV_POSITIONS2/CTA_PURPOSES6/normalizeSections が render() 前)",
    c_section_n == 14 and c_nav and c_cta and c_norm,
    f"SECTION_KEYS={c_section_n}, NAV_POSITIONS={c_nav}, CTA_PURPOSES={c_cta}, normalizeSections={c_norm}",
)

# ===========================================================================
# S3 buildInstruction 出力（source に navPosition/sections/sectionOptions と既定補完）
# ===========================================================================
b_layout = re.search(r"layout:\s*\{\s*columns:\s*columns,\s*navPosition:\s*navPosition", SCRSRC) is not None
b_sections = re.search(r"\bsections:\s*sections\b", SCRSRC) is not None
b_options = re.search(r"\bsectionOptions:\s*sectionOptions\b", SCRSRC) is not None
b_navdef = "'top'" in LOGIC and "NAV_POSITIONS.indexOf(input.navPosition)" in LOGIC
b_secdef = "SECTIONS_DEFAULT" in LOGIC and "['ABOUT', 'MENU', 'GALLERY']" in LOGIC
check(
    "S3 buildInstruction出力 (layout.navPosition/sections/sectionOptions・既定 top/[ABOUT,MENU,GALLERY])",
    b_layout and b_sections and b_options and b_navdef and b_secdef,
    f"layout.navPosition={b_layout}, sections={b_sections}, sectionOptions={b_options}, nav既定={b_navdef}, sections既定={b_secdef}",
)

# ===========================================================================
# S4 canonical整形の実装（normalizeSections が SECTION_KEYS順にフィルタ・重複除去）
# ===========================================================================
s4 = ("SECTION_KEYS.filter" in LOGIC) and ("SECTION_KEYS.indexOf(s) >= 0" in LOGIC)
check(
    "S4 canonical整形 (normalizeSections が SECTION_KEYS順フィルタ・未対応除去・重複除去)",
    s4,
    f"canonical filter/dedupe 実装={s4}",
)

# ===========================================================================
# S5 DRAFT_RULES §2.1（MV/FOOTER必須+選択セクション/navPosition/14語彙/CTA目的）
# ===========================================================================
r_must = ("MV-01" in RULES and "FOOTER-01" in RULES
          and ("常時必須" in RULES or "常時" in RULES) and "instruction.sections" in RULES)
r_nav = "navPosition" in RULES and "top" in RULES and "below-hero" in RULES
r_vocab = sum(1 for k in SECTION_KEYS if ("`%s-01`" % k) in RULES) >= 14
r_cta = "sectionOptions" in RULES and all(("`%s`" % p) in RULES for p in CTA_PURPOSES)
r_embed = ("実埋め込み" in RULES or "実埋込" in RULES) and "アタリ" in RULES
check(
    "S5 DRAFT_RULES §2.1 (MV/FOOTER必須+sections/navPosition/14番地語彙/CTA目的/SNS地図はアタリ)",
    r_must and r_nav and r_vocab and r_cta and r_embed,
    f"必須+sections={r_must}, navPosition={r_nav}, 14番地={r_vocab}, CTA目的={r_cta}, 埋込制約={r_embed}",
)

# ===========================================================================
# S6 SKILL 手順（選択セクションのみ・ヘッダー位置・CTA目的の反映）
# ===========================================================================
k_sections = "instruction.sections" in SKILL and ("選ばれたセクション" in SKILL or "選択されたセクション" in SKILL)
k_nav = "navPosition" in SKILL and "below-hero" in SKILL
k_cta = "sectionOptions" in SKILL and "purpose" in SKILL
check(
    "S6 SKILL 手順 (選択セクションのみ生成・navPosition反映・CTA目的反映)",
    k_sections and k_nav and k_cta,
    f"選択セクション={k_sections}, navPosition={k_nav}, CTA目的={k_cta}",
)

# ===========================================================================
# S7 bridge.py validate_instruction（新フィールドを存在時のみ検証）
# ===========================================================================
v_const = ("SECTION_KEYS" in BR and "NAV_POSITIONS" in BR and "CTA_PURPOSES" in BR)
v_nav = 'if isinstance(layout, dict) and "navPosition" in layout' in BR
v_sections = 'sections = obj.get("sections")' in BR and "未対応のセクション" in BR and "重複" in BR
v_options = 'section_options = obj.get("sectionOptions")' in BR and "sectionOptions.CTA.purpose" in BR
v_backcompat = "存在するときのみ" in BR or "存在時のみ" in BR
check(
    "S7 bridge validate_instruction (navPosition/sections/sectionOptions を存在時のみ厳格検証・後方互換)",
    v_const and v_nav and v_sections and v_options and v_backcompat,
    f"定数={v_const}, navPosition検証={v_nav}, sections検証={v_sections}, options検証={v_options}, 後方互換注記={v_backcompat}",
)

# ===========================================================================
# S8 ゴールデン: 選択セクションの番地のみを反映（非選択は不在・MV/NAV/FOOTER在）
# ===========================================================================


def expected_pins(instr):
    body = [k + "-01" for k in SECTION_KEYS if k in instr.get("sections", [])]
    return set(["NAV-01", "MV-01", "FOOTER-01"] + body)


s8_ok = True
s8_detail = []
for name, html, instr in (("1col", IDX1, INSTR1), ("2col", IDX2, INSTR2)):
    pins = set(pins_in_order(html))
    exp = expected_pins(instr)
    # 非選択セクションの番地が漏れていないこと（14語彙のうち sections 外は不在）
    leaked = [k + "-01" for k in SECTION_KEYS
              if k not in instr.get("sections", []) and (k + "-01") in pins]
    ok = (pins == exp) and not leaked
    s8_ok = s8_ok and ok
    s8_detail.append(f"{name}: 一致={pins == exp} 漏れ={leaked or 0}")
check(
    "S8 ゴールデン選択反映 (index の番地集合 == NAV/MV/FOOTER + instruction.sections・非選択の番地なし)",
    s8_ok,
    "; ".join(s8_detail),
)

# ===========================================================================
# S9 ヘッダー位置＆CTA文言の反映
# ===========================================================================
# nav position: top → NAV 番地が MV より前 / below-hero → 後
s9_nav_ok = True
s9_nav_detail = []
for name, html, instr in (("1col", IDX1, INSTR1), ("2col", IDX2, INSTR2)):
    order = pins_in_order(html)
    nav_i = order.index("NAV-01") if "NAV-01" in order else -1
    mv_i = order.index("MV-01") if "MV-01" in order else -1
    want = instr.get("layout", {}).get("navPosition", "top")
    ok = (nav_i < mv_i) if want == "top" else (nav_i > mv_i)
    s9_nav_ok = s9_nav_ok and ok
    s9_nav_detail.append(f"{name}:{want}(NAV@{nav_i}/MV@{mv_i})={ok}")
# CTA 文言: 1col は purpose=reserve → ラベルが CTA-01 セクション内に出る
cta_opt = INSTR1.get("sectionOptions", {}).get("CTA", {})
cta_label = cta_opt.get("label") or CTA_DEFAULT_LABEL.get(cta_opt.get("purpose", "contact"), "")
# CTA-01 の .sec ブロック（次の pin まで）にラベルがあるか
m = re.search(r'CTA-01</span>(.*?)(?:class="pin"|</body>)', IDX1, re.S)
cta_ok = bool(cta_label) and (m is not None) and (cta_label in m.group(1))
check(
    "S9 ヘッダー位置＆CTA文言 (navPosition で NAV/MV の順が一致・CTAボタン文言が目的ラベルと一致)",
    s9_nav_ok and cta_ok,
    f"nav順: {', '.join(s9_nav_detail)}; CTAラベル='{cta_label}' 反映={cta_ok}",
)

# ===========================================================================
# S10 セキュリティ/依存（外部URL0・秘密0・プレースホルダ明記・実埋込/実地図なし）
# ===========================================================================
_ALLOW_HOSTS = ("www.w3.org", "example.com", "example.org", "example.net")


def _host(url):
    mm = re.match(r"https?://([^/\s\"')]+)", url)
    return mm.group(1).lower() if mm else ""


secret_re = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
embed_re = re.compile(r"<iframe|<script[^>]*\bsrc=|googleapis|gstatic|<img[^>]*\bsrc=[\"']?https?:", re.I)
s10_ok = True
s10_detail = {}
for label, txt in (("1col", IDX1), ("2col", IDX2)):
    ext = [u for u in re.findall(r'https?://[^\s"\')（]+', txt) if _host(u) not in _ALLOW_HOSTS]
    secret = [ln for ln, line in enumerate(txt.splitlines(), 1) if secret_re.search(line)]
    ph = ("プレースホルダ" in txt or "実在の顧客" in txt or "サンプル" in txt)
    embed = embed_re.search(txt) is not None  # 実埋め込み/外部スクリプト/実地図なし
    ok = (not ext) and (not secret) and ph and (not embed)
    s10_ok = s10_ok and ok
    s10_detail[label] = f"外部URL={ext or 0}/秘密={secret or 0}/PH={ph}/実埋込={embed}"
check(
    "S10 セキュリティ/依存 (klk022 両ゴールデン: 外部URL0・秘密0・プレースホルダ明記・実埋込/実地図なし)",
    s10_ok,
    "; ".join(f"{k}: {v}" for k, v in s10_detail.items()),
)

# ===========================================================================
# S11 既存回帰の保持（DRAFT_RULES 基本6番地・§2 の記述が残る / version:1 据置）
# ===========================================================================
r_base6 = all((("`%s`" % p) in RULES) for p in ("NAV-01", "MV-01", "ABOUT-01", "MENU-01", "GALLERY-01", "FOOTER-01"))
r_ver = ("version" in SCRSRC and "version: 1" in SCRSRC) and ('obj.get("version") != 1' in BR)
check(
    "S11 既存回帰保持 (基本6番地の記述が残る・SCR-001/bridge の version:1 据置)",
    r_base6 and r_ver,
    f"基本6番地={r_base6}, version:1据置={r_ver}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-022 static acceptance checks (docs/designs/KLK-022.md §9 S群 を正とする)")
print("対象: draft-gen/index.html・bridge.py / DRAFT_RULES.md・SKILL.md / fixtures/klk022/*")
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
print("D群（test_palette_klk022.py）: 動的スモーク smoke_klk022.node.js（buildInstruction実挙動・node無ければskip）/")
print("  Quality Gate 全緑 / mockups 生成物の git check-ignore（git不在時skip）")
print("M群（tester 手動・ブラウザ）: 実生成で選択セクションのみ反映 / MV下でナビが下 / CTA目的で文言変化 / 無選択で後方互換")
sys.exit(1 if failed else 0)
