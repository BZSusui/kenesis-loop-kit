#!/usr/bin/env python3
"""
KLK-021 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S11 from
docs/designs/KLK-021.md §9（S群）against 複数案のレイアウト差別化（data-archetype で配色とレイアウトを両振り）:

  縦串③ 生成規約     .claude/skills/draft-generate/templates/DRAFT_RULES.md（§12 / §12.1）
  縦串③ スキル定義   .claude/skills/draft-generate/SKILL.md（手順3）
  ゴールデン(案別)     tests/fixtures/klk021/index-a.html（stack-centered）
                      tests/fixtures/klk021/index-b.html（split-editorial）
                      tests/fixtures/klk021/index-c.html（banded-showcase）
  ゴールデン(比較ハブ) tests/fixtures/klk021/compare.html
  ゴールデン(入力写し) tests/fixtures/klk021/instruction.json

Source of truth = 設計書 §9（S群）。check_klk009.py と同型（正規表現・文字列検索・波括弧均衡ブロック抽出・
tester所有・exit 0/1・Python3標準ライブラリのみ・ネットワーク非使用）。D群（Quality Gate＋git check-ignore）は
tests/test_palette_klk021.py が、M群（実生成＋ブラウザ実機）は tester が手動確認してチケットのログへ記録する。
プロダクション成果物・ゴールデンは変更しない。

Run: python3 tests/site/check_klk021.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FX = os.path.join(ROOT, "tests", "fixtures", "klk021")
IDXA_PATH = os.path.join(FX, "index-a.html")
IDXB_PATH = os.path.join(FX, "index-b.html")
IDXC_PATH = os.path.join(FX, "index-c.html")
COMPARE_PATH = os.path.join(FX, "compare.html")
INSTR_PATH = os.path.join(FX, "instruction.json")
RULES_PATH = os.path.join(
    ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md")
SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md")

IDXA = open(IDXA_PATH, encoding="utf-8").read()
IDXB = open(IDXB_PATH, encoding="utf-8").read()
IDXC = open(IDXC_PATH, encoding="utf-8").read()
COMPARE = open(COMPARE_PATH, encoding="utf-8").read()
INSTR = open(INSTR_PATH, encoding="utf-8").read()
RULES = open(RULES_PATH, encoding="utf-8").read()
SKILL = open(SKILL_PATH, encoding="utf-8").read()

# §8 canonical カラム enum（6系統・全案同一を検証する対象集合）
NEW_COLS = {
    "1col", "2col-full-left", "2col-full-right",
    "2col-body-left", "2col-body-right", "3col",
}
# §12.1 レイアウト原型 enum（3値・案間相違を検証する対象集合）
ARCHETYPE_ENUM = {"stack-centered", "split-editorial", "banded-showcase"}

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def brace_block(src, sel_regex):
    """sel_regex（セレクタ）に一致した直後のブレース均衡ブロックを返す（無ければ ""）。"""
    m = re.search(sel_regex, src)
    if not m:
        return ""
    j = src.find("{", m.end() - 1)
    if j < 0:
        return ""
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j:k + 1]
    return src[j:]


def css_block(src, marker):
    i = src.find(marker)
    if i < 0:
        return ""
    j = src.find("{", i)
    if j < 0:
        return ""
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
    return src[i:]


def data_columns(html):
    m = re.search(r'data-columns="([^"]+)"', html)
    return m.group(1) if m else ""


def data_archetype(html):
    m = re.search(r'data-archetype="([^"]+)"', html)
    return m.group(1) if m else ""


def m_main(html):
    m = re.search(r"--m-main\s*:\s*(#[0-9a-fA-F]{3,8})", html)
    return m.group(1).lower() if m else ""


def hero_sig(html):
    """.m-hero セレクタ本体ブロックの整列シグネチャ (justify-content, align-items, text-align)。"""
    block = brace_block(html, r'\.m-hero\s*\{')

    def prop(name):
        mm = re.search(name + r"\s*:\s*([a-zA-Z-]+)", block)
        return mm.group(1).lower() if mm else ""
    return (prop("justify-content"), prop("align-items"), prop("text-align"))


def pins_all(html):
    pins = ["NAV-01", "MV-01", "ABOUT-01", "MENU-01", "GALLERY-01", "FOOTER-01"]
    return all(re.search(r'class="pin">\s*' + re.escape(p), html) for p in pins)


def no_ext_deps(html):
    has_link_css = re.search(r'<link\b[^>]*rel=["\']?stylesheet', html, re.I) is not None
    has_script_src = re.search(r'<script\b[^>]*\bsrc=', html, re.I) is not None
    has_font_cdn = bool(re.search(
        r'fonts\.(googleapis|gstatic)\.com|cdn\.|unpkg\.com|jsdelivr', html, re.I))
    has_img_ext = re.search(r'<img\b[^>]*\bsrc=["\']?https?:', html, re.I) is not None
    return not (has_link_css or has_script_src or has_font_cdn or has_img_ext)


DC_A, DC_B, DC_C = data_columns(IDXA), data_columns(IDXB), data_columns(IDXC)
AR_A, AR_B, AR_C = data_archetype(IDXA), data_archetype(IDXB), data_archetype(IDXC)
MM_A, MM_B, MM_C = m_main(IDXA), m_main(IDXB), m_main(IDXC)

# ===========================================================================
# S1 archetype 属性契約（KLK-021 §4）
# ===========================================================================
s1_cols = all(dc in NEW_COLS for dc in (DC_A, DC_B, DC_C))
s1_arch = all(ar != "" for ar in (AR_A, AR_B, AR_C))
check(
    "S1 archetype属性契約 (各案ルートに data-columns[enum6]＋data-archetype が付く)",
    s1_cols and s1_arch,
    f"data-columns={DC_A}/{DC_B}/{DC_C}(enum6={s1_cols}), "
    f"data-archetype={AR_A}/{AR_B}/{AR_C}(存在={s1_arch})",
)

# ===========================================================================
# S2 archetype enum & 案間相違（設計書 §9 S2・--m-main distinct と同型）
# ===========================================================================
s2_in_enum = all(ar in ARCHETYPE_ENUM for ar in (AR_A, AR_B, AR_C))
s2_distinct = len({AR_A, AR_B, AR_C}) == 3 and all((AR_A, AR_B, AR_C))
check(
    "S2 archetype enum&相違 (3案の data-archetype が enum3値のいずれか・3値 distinct)",
    s2_in_enum and s2_distinct,
    f"enum={ARCHETYPE_ENUM}, 値={AR_A}/{AR_B}/{AR_C}, enum内={s2_in_enum}, distinct={s2_distinct}",
)

# ===========================================================================
# S3 カラム数固定の維持（設計書 §9 S3・列数固定）
# ===========================================================================
s3_same = bool(DC_A) and DC_A == DC_B == DC_C and DC_A in NEW_COLS
check(
    "S3 カラム数固定 (3案の data-columns が同一・enum6値のいずれか)",
    s3_same,
    f"data-columns={DC_A}/{DC_B}/{DC_C}(同一={s3_same})",
)

# ===========================================================================
# S4 配色の両振り維持（設計書 §9 S4・--m-main 相違）
# ===========================================================================
s4_distinct = len({MM_A, MM_B, MM_C}) == 3 and all((MM_A, MM_B, MM_C))
check(
    "S4 配色の両振り維持 (3案の --m-main が相違＝配色＋レイアウト両振り)",
    s4_distinct,
    f"--m-main={MM_A}/{MM_B}/{MM_C}(相違={s4_distinct})",
)

# ===========================================================================
# S5 archetype の実CSS差（設計書 §9 S5・HERO整列シグネチャの案間相違）
# ===========================================================================
sig_a, sig_b, sig_c = hero_sig(IDXA), hero_sig(IDXB), hero_sig(IDXC)
s5_complete = all(all(sig) for sig in (sig_a, sig_b, sig_c))
s5_distinct = len({sig_a, sig_b, sig_c}) == 3
check(
    "S5 archetypeの実CSS差 (.m-hero の justify-content/align-items/text-align が案間で相違・飾りでない)",
    s5_complete and s5_distinct,
    f"HERO整列 a={sig_a} b={sig_b} c={sig_c}(揃い={s5_complete}, 相違={s5_distinct})",
)

# ===========================================================================
# S6 各案の基本健全性（設計書 §9 S6・番地6/print/アタリa/依存0）
# ===========================================================================
s6_ok = True
s6_detail = []
for label, html in (("a", IDXA), ("b", IDXB), ("c", IDXC)):
    pins = pins_all(html)
    prt = css_block(html, "@media print") != ""
    atari = 'class="atari"' in html and 'class="desc"' in html
    solo = no_ext_deps(html)
    ok = pins and prt and atari and solo
    s6_ok = s6_ok and ok
    s6_detail.append(f"{label}:番地6={pins}/print={prt}/アタリ={atari}/依存0={solo}")
check(
    "S6 各案の基本健全性 (index-a/b/c: 番地6種・@media print・アタリa方式・外部依存0)",
    s6_ok,
    "; ".join(s6_detail),
)

# ===========================================================================
# S7 DRAFT_RULES §12 改訂（設計書 §9 S7）
# ===========================================================================
s7_archetype = "data-archetype" in RULES
s7_enum = all(v in RULES for v in ARCHETYPE_ENUM)
s7_cols_common = ("全案" in RULES) and ("data-columns" in RULES) and ("固定" in RULES or "同一" in RULES)
s7_arch_distinct = ("案間" in RULES) and ("相違" in RULES)
s7_two_axis = ("配色" in RULES) and ("レイアウト" in RULES) and ("両振り" in RULES)
check(
    "S7 DRAFT_RULES §12改訂 (data-archetype/enum3値/全案data-columns固定/案間archetype相違/配色+レイアウト両振り)",
    s7_archetype and s7_enum and s7_cols_common and s7_arch_distinct and s7_two_axis,
    f"data-archetype={s7_archetype}, enum3値={s7_enum}, カラム固定={s7_cols_common}, "
    f"案間相違={s7_arch_distinct}, 両振り={s7_two_axis}",
)

# ===========================================================================
# S8 SKILL 手順3 改訂（設計書 §9 S8）
# ===========================================================================
s8_archetype = "data-archetype" in SKILL
s8_enum = all(v in SKILL for v in ARCHETYPE_ENUM)
s8_assign = ("案A" in SKILL and "案B" in SKILL and "案C" in SKILL) or \
    re.search(r"a=stack-centered", SKILL) is not None
check(
    "S8 SKILL 手順3改訂 (案別 data-archetype 付与手順・enum3値・案A/B/C 割当)",
    s8_archetype and s8_enum and s8_assign,
    f"data-archetype={s8_archetype}, enum3値={s8_enum}, 案A/B/C割当={s8_assign}",
)

# ===========================================================================
# S9 compare.html §13 準拠（設計書 §9 S9）
# ===========================================================================
c_radios = re.findall(r'<input[^>]*type="radio"[^>]*name="variant"', COMPARE)
c_radio3 = len(c_radios) >= 2
c_combinator = re.search(r'#\w+:checked\s*~[^{}]*#pane[A-C][^{}]*\{[^}]*display\s*:\s*block',
                         COMPARE, re.S) is not None \
    or (re.search(r'#\w+:checked\s*~[^{}]*\.canvas', COMPARE) is not None
        and re.search(r'#pane[A-C][^{}]*\{\s*display\s*:\s*block', COMPARE) is not None)
c_no_script = re.search(r'<script', COMPARE, re.I) is None
c_iframe = all(re.search(r'<iframe[^>]*src="index-%s\.html"' % L, COMPARE) for L in ("a", "b", "c"))
c_full = all(re.search(r'href="index-%s\.html"[^>]*target="_blank"' % L, COMPARE) for L in ("a", "b", "c"))
c_no_ext_iframe = re.search(r'<iframe[^>]*src="https?:', COMPARE, re.I) is None
check(
    "S9 compare.html §13準拠 (案切替CSS-only・iframe相対index-{letter}・原寸別タブ・外部iframe URL無)",
    c_radio3 and c_combinator and c_no_script and c_iframe and c_full and c_no_ext_iframe,
    f"radio(name=variant)={len(c_radios)}, 兄弟結合子={c_combinator}, script非依存={c_no_script}, "
    f"iframe相対={c_iframe}, 原寸別タブ={c_full}, iframe外部URL無={c_no_ext_iframe}",
)

# ===========================================================================
# S10 セキュリティ/依存（設計書 §9 S10・NFR-005 / NFR-004 / REQ-011）
# ===========================================================================
_ALLOW_HOSTS = ("www.w3.org", "example.com", "example.org", "example.net")


def _host(url):
    m = re.match(r"https?://([^/\s\"')]+)", url)
    return m.group(1).lower() if m else ""


secret_re = re.compile(
    r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
sec_ok = True
sec_detail = {}
for label, txt in (("index-a", IDXA), ("index-b", IDXB), ("index-c", IDXC), ("compare", COMPARE)):
    ext_urls = [m for m in re.findall(r'https?://[^\s"\')（]+', txt)
                if _host(m) not in _ALLOW_HOSTS]
    secret_hits = [ln for ln, line in enumerate(txt.splitlines(), 1)
                   if secret_re.search(line)]
    placeholder_marked = ("プレースホルダ" in txt or "実在の顧客" in txt or "サンプル" in txt)
    ok = (not ext_urls) and (not secret_hits) and placeholder_marked
    sec_ok = sec_ok and ok
    sec_detail[label] = f"外部URL={ext_urls or 0}/秘密={secret_hits or 0}/PH明記={placeholder_marked}"
check(
    "S10 セキュリティ/依存 (klk021 4ゴールデン: 外部URL0[w3.org/example.*除外]・秘密0・プレースホルダ明記)",
    sec_ok,
    "; ".join(f"{k}: {v}" for k, v in sec_detail.items()),
)

# ===========================================================================
# S11 既存回帰の保持（設計書 §9 S11・klk009 複数案規約が不変で残る）
# ===========================================================================
r_base = "忠実" in RULES        # 案A=指示書忠実
r_deep = "濃色" in RULES or "高級" in RULES   # 案B=濃色/高級
r_pop = "明色" in RULES or "ポップ" in RULES  # 案C=明色/ポップ
r_col_common = ("全案同一" in RULES or "全案共通" in RULES) and "data-columns" in RULES
check(
    "S11 既存回帰の保持 (DRAFT_RULES: 案A忠実/案B濃色高級/案C明色ポップ/カラム骨格 全案共通 が不変)",
    r_base and r_deep and r_pop and r_col_common,
    f"案A忠実={r_base}, 案B濃色高級={r_deep}, 案C明色ポップ={r_pop}, カラム全案共通={r_col_common}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-021 static acceptance checks (docs/designs/KLK-021.md §9 S群 を正とする)")
print("対象: fixtures/klk021/{index-a/b/c,compare}.html + instruction.json / DRAFT_RULES.md / SKILL.md")
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
print("D群（test_palette_klk021.py で Quality Gate 全緑・git check-ignore・git不在時skip）:")
print("  - D1 Quality Gate 全緑（python3 -m unittest discover -s tests・回帰なし）")
print("  - D2 mockups 複数案の Git 除外成立（compare.html / index-a.html / instruction.json が exit 0）")
print()
print("M群（環境制約で静的検証外 = tester が /draft-generate 実行 + ブラウザで手動確認）:")
print("  - M1 variants:3 実生成で3案が配色かつレイアウト（archetype）で見分けられる（同一カラムでも構成が違う）")
print("  - M2 compare.html で A/B/C 切替時にレイアウトの違いが視認できる")
print("  - M3 variants:1 後方互換（archetype 既定 stack-centered で従来どおり index.html 単独）")
sys.exit(1 if failed else 0)
