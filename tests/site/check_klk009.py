#!/usr/bin/env python3
"""
KLK-009 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S15 from
docs/designs/KLK-009.md §9（S群）against 複数案(最大3案)一括生成＋SCR-002 比較・閲覧画面:

  縦串③ 生成規約     .claude/skills/draft-generate/templates/DRAFT_RULES.md
  縦串③ スキル定義   .claude/skills/draft-generate/SKILL.md
  ゴールデン(比較ハブ) tests/fixtures/klk009/compare.html
                      tests/fixtures/klk009/compare-partial.html
  ゴールデン(案別)     tests/fixtures/klk009/index-a.html / index-b.html / index-c.html
  ゴールデン(入力写し) tests/fixtures/klk009/instruction.json

Source of truth = 設計書 §9（S群）。check_klk007/008.py と同型（正規表現・文字列検索・
波括弧均衡ブロック抽出・tester所有・exit 0/1・Python3標準ライブラリのみ・ネットワーク非使用）。
D群（git check-ignore＋回帰）は tests/test_palette_klk009.py が、M群（実生成＋ブラウザ実機）は
tester が手動確認してチケットのログへ記録する。プロダクション成果物・ゴールデンは変更しない。

Run: python3 tests/site/check_klk009.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FX = os.path.join(ROOT, "tests", "fixtures", "klk009")
COMPARE_PATH = os.path.join(FX, "compare.html")
PARTIAL_PATH = os.path.join(FX, "compare-partial.html")
IDXA_PATH = os.path.join(FX, "index-a.html")
IDXB_PATH = os.path.join(FX, "index-b.html")
IDXC_PATH = os.path.join(FX, "index-c.html")
INSTR_PATH = os.path.join(FX, "instruction.json")
RULES_PATH = os.path.join(
    ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md")
SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md")

COMPARE = open(COMPARE_PATH, encoding="utf-8").read()
PARTIAL = open(PARTIAL_PATH, encoding="utf-8").read()
IDXA = open(IDXA_PATH, encoding="utf-8").read()
IDXB = open(IDXB_PATH, encoding="utf-8").read()
IDXC = open(IDXC_PATH, encoding="utf-8").read()
INSTR = open(INSTR_PATH, encoding="utf-8").read()
RULES = open(RULES_PATH, encoding="utf-8").read()
SKILL = open(SKILL_PATH, encoding="utf-8").read()

SAVE = SKILL + "\n" + RULES  # 縦串規約の合算（保存/フォルダオープン/複数案手順の検証用）

NEW_COLS = {
    "1col", "2col-full-left", "2col-full-right",
    "2col-body-left", "2col-body-right", "3col",
}

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def css_block(src, marker):
    """marker から始まる最初のブレース均衡ブロックを返す（見つからなければ ""）。"""
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


def m_main(html):
    m = re.search(r"--m-main\s*:\s*(#[0-9a-fA-F]{3,8})", html)
    return m.group(1).lower() if m else ""


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


# ===========================================================================
# S1 保存規約（複数案＋後方互換）（REQ-008 / REQ-010 / U-A / U-F / U-H）
# ===========================================================================
s1_v1 = "index.html" in SAVE and ("variants:1" in SAVE or "`1`" in SAVE)
s1_multi = all(v in SAVE for v in ("index-a.html", "index-b.html", "index-c.html")) \
    and "compare.html" in SAVE
s1_instr = "instruction.json" in SAVE
s1_path = (re.search(r"mockups/\{[^}]*\}_\{[^}]*\}/", SAVE) is not None
           or ("mockups/" in SAVE and "案件名" in SAVE))
s1_safe = ("パス安全化" in SAVE) or ("untitled" in SAVE)
check(
    "S1 保存規約 (variants:1→index.html / ≥2→index-a/b/c+compare.html / instruction.json併置 / mockups+パス安全化 残存)",
    s1_v1 and s1_multi and s1_instr and s1_path and s1_safe,
    f"variants:1→index.html={s1_v1}, ≥2→index-a/b/c+compare={s1_multi}, "
    f"instruction.json={s1_instr}, mockupsパス={s1_path}, パス安全化={s1_safe}",
)

# ===========================================================================
# S2 比較画面ゴールデン存在（U-E / U-H）
# ===========================================================================
check(
    "S2 比較画面ゴールデン存在 (tests/fixtures/klk009/compare.html)",
    os.path.isfile(COMPARE_PATH) and COMPARE.strip() != "",
    f"compare.html={os.path.isfile(COMPARE_PATH)}(bytes={len(COMPARE)})",
)

# ===========================================================================
# S3 案切替 CSS-only（REQ-008 / U-B）
# ===========================================================================
c_radios = re.findall(r'<input[^>]*type="radio"[^>]*name="variant"', COMPARE)
c_radio3 = len(c_radios) >= 2  # 3案成功ハブは3つ
# 兄弟結合子 #ra:checked ~ .canvas #paneA { display: block }
c_combinator = re.search(r'#\w+:checked\s*~[^{}]*#pane[A-C][^{}]*\{[^}]*display\s*:\s*block',
                         COMPARE, re.S) is not None \
    or (re.search(r'#\w+:checked\s*~[^{}]*\.canvas', COMPARE) is not None
        and re.search(r'#pane[A-C][^{}]*\{\s*display\s*:\s*block', COMPARE) is not None)
c_no_script = re.search(r'<script', COMPARE, re.I) is None  # 切替が JS 非依存（graceful）
check(
    "S3 案切替CSS-only (隠しラジオ type=radio name=variant 複数・:checked~ 兄弟結合子で #pane 表示・<script>非依存)",
    c_radio3 and c_combinator and c_no_script,
    f"radio(name=variant)={len(c_radios)}, 兄弟結合子display:block={c_combinator}, "
    f"script非依存={c_no_script}",
)

# ===========================================================================
# S4 原寸別タブ直リンク（REQ-008 / U-B / U-H）
# ===========================================================================
s4_ok = True
s4_detail = []
for letter in ("a", "b", "c"):
    m = re.search(r'href="index-%s\.html"[^>]*target="_blank"' % letter, COMPARE)
    s4_detail.append(f"index-{letter}={m is not None}")
    s4_ok = s4_ok and (m is not None)
check(
    "S4 原寸別タブ直リンク (各案 href=\"index-{a,b,c}.html\" + target=\"_blank\" 相対リンク)",
    s4_ok,
    ", ".join(s4_detail),
)

# ===========================================================================
# S5 iframe 相対読込（U-B / U-H / NFR-005）
# ===========================================================================
s5_ok = True
s5_detail = []
for letter in ("a", "b", "c"):
    m = re.search(r'<iframe[^>]*src="index-%s\.html"' % letter, COMPARE)
    s5_detail.append(f"iframe index-{letter}={m is not None}")
    s5_ok = s5_ok and (m is not None)
# iframe src が外部URLでない（相対のみ）
s5_no_ext_iframe = re.search(r'<iframe[^>]*src="https?:', COMPARE, re.I) is None
check(
    "S5 iframe相対読込 (各 .pane が相対 src=\"index-{letter}.html\" で案を読込・外部URLでない)",
    s5_ok and s5_no_ext_iframe,
    ", ".join(s5_detail) + f", iframe外部URL無={s5_no_ext_iframe}",
)

# ===========================================================================
# S6 サムネイル一覧（REQ-008）
# ===========================================================================
s6_vthumb_used = re.search(r'class="vthumb', COMPARE) is not None
s6_ok = ".thumbstrip" in COMPARE and ".vthumb" in COMPARE and s6_vthumb_used
check(
    "S6 サムネイル一覧 (.thumbstrip / .vthumb の案別ミニサムネイル)",
    s6_ok,
    f".thumbstrip={'.thumbstrip' in COMPARE}, .vthumb={'.vthumb' in COMPARE}, "
    f"vthumb使用={s6_vthumb_used}",
)

# ===========================================================================
# S7 一部失敗の焼き込み（REQ-008 失敗時挙動 / U-G）
# ===========================================================================
p_exists = os.path.isfile(PARTIAL_PATH)
p_partial_note = ".partial-note" in PARTIAL and 'class="partial-note"' in PARTIAL
p_success2 = (re.search(r'src="index-a\.html"', PARTIAL) is not None
              and re.search(r'src="index-b\.html"', PARTIAL) is not None)
# 失敗案(index-c.html)を一切参照しない
p_no_failed = "index-c.html" not in PARTIAL
p_radio2 = len(re.findall(r'<input[^>]*type="radio"[^>]*name="variant"', PARTIAL)) == 2
check(
    "S7 一部失敗の焼き込み (compare-partial.html: .partial-note あり・成功2案のみ・失敗案 index-c.html 非参照)",
    p_exists and p_partial_note and p_success2 and p_no_failed and p_radio2,
    f"存在={p_exists}, .partial-note={p_partial_note}, 成功2案iframe={p_success2}, "
    f"index-c.html非参照={p_no_failed}, radio2件={p_radio2}",
)

# ===========================================================================
# S8 比較画面 @media print（REQ-009 / NFR-003）
# ===========================================================================
c_print = css_block(COMPARE, "@media print")
c_print_present = c_print != ""
c_print_hides = (".toolchrome" in c_print or ".toolbar" in c_print) \
    and re.search(r"display\s*:\s*none", c_print) is not None
check(
    "S8 比較画面@media print (compare.html に @media print・toolchrome/toolbar 等を display:none)",
    c_print_present and c_print_hides,
    f"@media print={c_print_present}, chrome非表示(display:none)={c_print_hides}",
)

# ===========================================================================
# S9 案別 standalone の配色バリエーション（U-C / REQ-002/005/006/009）
# ===========================================================================
dc_a, dc_b, dc_c = data_columns(IDXA), data_columns(IDXB), data_columns(IDXC)
dc_same = dc_a and dc_a == dc_b == dc_c and dc_a in NEW_COLS
mm_a, mm_b, mm_c = m_main(IDXA), m_main(IDXB), m_main(IDXC)
mm_distinct = len({mm_a, mm_b, mm_c}) == 3 and all((mm_a, mm_b, mm_c))
# 各案: 番地6種・@media print・アタリa方式(.atari/.desc)・依存ゼロ
per_ok = True
per_detail = []
for label, html in (("a", IDXA), ("b", IDXB), ("c", IDXC)):
    pins = pins_all(html)
    prt = css_block(html, "@media print") != ""
    atari = 'class="atari"' in html and 'class="desc"' in html
    solo = no_ext_deps(html)
    ok = pins and prt and atari and solo
    per_ok = per_ok and ok
    per_detail.append(f"{label}:番地6={pins}/print={prt}/アタリ={atari}/依存0={solo}")
check(
    "S9 案別standalone配色バリエ (index-a/b/c 同一 data-columns・--m-main 案間相違・各案 番地6/print/アタリa/依存0)",
    dc_same and mm_distinct and per_ok,
    f"data-columns={dc_a}/{dc_b}/{dc_c}(同一={dc_same}), "
    f"--m-main={mm_a}/{mm_b}/{mm_c}(相違={mm_distinct}); " + "; ".join(per_detail),
)

# ===========================================================================
# S10 バリエーション規約（DRAFT_RULES §12・U-C）
# ===========================================================================
r_base = "忠実" in RULES  # 案A=指示書忠実
r_deep = "濃色" in RULES or "高級" in RULES  # 案B=濃色/高級方向
r_pop = "明色" in RULES or "ポップ" in RULES  # 案C=明色/ポップ方向
r_col_common = ("全案同一" in RULES or "全案共通" in RULES) and "data-columns" in RULES
r_taste = "副次" in RULES
check(
    "S10 バリエーション規約 (DRAFT_RULES: 案A忠実/案B濃色高級/案C明色ポップ/カラム骨格 全案共通/テイスト副次差)",
    r_base and r_deep and r_pop and r_col_common and r_taste,
    f"案A忠実={r_base}, 案B濃色高級={r_deep}, 案C明色ポップ={r_pop}, "
    f"カラム全案共通={r_col_common}, テイスト副次差={r_taste}",
)

# ===========================================================================
# S11 モバイルファースト（DRAFT_RULES §8・モバイルファースト要望 / NFR-002）
# ===========================================================================
m_backfold = "後ろに畳む" in RULES
m_classes = ".m-aside" in RULES and ".m-main-col" in RULES
m_mobilefirst = "モバイルファースト" in RULES
# 曖昧記述「後ろ（または前）」の排除（全角/半角括弧とも）
m_ambiguous_removed = ("後ろ（または前）" not in RULES) and ("後ろ(または前)" not in RULES)
check(
    "S11 モバイルファースト (§8: .m-aside を .m-main-col 優先で本文の後ろに畳む・モバイルファースト明記・曖昧『後ろ（または前）』排除)",
    m_backfold and m_classes and m_mobilefirst and m_ambiguous_removed,
    f"後ろに畳む={m_backfold}, .m-aside/.m-main-col={m_classes}, モバイルファースト={m_mobilefirst}, "
    f"曖昧記述排除={m_ambiguous_removed}",
)

# ===========================================================================
# S12 フォルダ自動オープン規約（REQ-010残り / U-D / SPEC §7）
# ===========================================================================
f_mac = re.search(r"\bopen '", SAVE) is not None or re.search(r"`open '", SAVE) is not None
f_win = "explorer" in SAVE
f_linux = "xdg-open" in SAVE
f_fallback = "保存先パス" in SAVE
f_browser_no = "ブラウザ単独では不可" in SAVE or ("ブラウザ" in SAVE and "不可" in SAVE)
check(
    "S12 フォルダ自動オープン規約 (open(mac)/explorer(win)/xdg-open(linux)・開けない時パス表示・ブラウザ単独不可)",
    f_mac and f_win and f_linux and f_fallback and f_browser_no,
    f"open(mac)={f_mac}, explorer(win)={f_win}, xdg-open(linux)={f_linux}, "
    f"パス表示={f_fallback}, ブラウザ不可={f_browser_no}",
)

# ===========================================================================
# S13 複数案生成手順（1案限定の反転）（REQ-008 / U-A / Q7）
# ===========================================================================
s13_no_assertion = ("1案のみ" not in SAVE) and ("複数案は別チケット" not in SAVE) \
    and ("1案限定" not in SAVE)
s13_max3 = "最大3案" in SAVE
s13_variants = "output.variants" in SAVE and ("1〜3" in SAVE or "1-3" in SAVE)
check(
    "S13 複数案生成手順 (断定『1案のみ/複数案は別チケット』除去・output.variants に応じ最大3案 手順)",
    s13_no_assertion and s13_max3 and s13_variants,
    f"断定除去={s13_no_assertion}, 最大3案={s13_max3}, output.variants(1〜3)={s13_variants}",
)

# ===========================================================================
# S14 既存回帰の保持（縦串静的）（回帰なし / R-1 / Q7）
# ===========================================================================
# SKILL: version==1不変・カラム正規化・animation未指定true補完（check_klk008 S8 と同趣旨）
sk_version = (re.search(r"version[^\n]*1", SKILL) is not None) and "不変" in SKILL
sk_alias = (("2col-sub-left" in SKILL and "2col-body-left" in SKILL)
            and ("2col-sub-right" in SKILL and "2col-body-right" in SKILL)
            and ("正規化" in SKILL))
sk_anim = ("output.animation" in SKILL and "未指定" in SKILL and "true" in SKILL)
# DRAFT_RULES: 既存必須節（check_klk007 S11 と同趣旨）＋ index.html/instruction.json 保存記述
rules_sections = {
    "配色マッピング": "配色マッピング" in RULES,
    "アタリa方式": ("アタリ画像" in RULES and "a方式" in RULES),
    "番地ラベル": "番地ラベル" in RULES,
    "印刷CSS": ("@media print" in RULES and "印刷" in RULES),
    "出現アニメ": ("出現アニメ" in RULES or "IntersectionObserver" in RULES),
    "カラム構成": "カラム構成" in RULES,
    "保存規約": "保存規約" in RULES,
}
missing = [k for k, v in rules_sections.items() if not v]
rules_save = "index.html" in RULES and "instruction.json" in RULES
check(
    "S14 既存回帰保持 (SKILL: version==1不変/2col-sub→body正規化/animation未指定true・DRAFT_RULES: 既存必須節+index.html/instruction.json)",
    sk_version and sk_alias and sk_anim and not missing and rules_save,
    f"version不変={sk_version}, カラム正規化={sk_alias}, animation既定={sk_anim}, "
    f"必須節欠落={missing or 'なし'}, RULES保存記述={rules_save}",
)

# ===========================================================================
# S15 セキュリティ/依存（S-SEC・NFR-005 / NFR-004 / REQ-011）
# ===========================================================================
_ALLOW_HOSTS = ("www.w3.org", "example.com", "example.org", "example.net")


def _host(url):
    m = re.match(r"https?://([^/\s\"')]+)", url)
    return m.group(1).lower() if m else ""


secret_re = re.compile(
    r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
sec_ok = True
sec_detail = {}
for label, txt in (("compare", COMPARE), ("compare-partial", PARTIAL),
                   ("index-a", IDXA), ("index-b", IDXB), ("index-c", IDXC)):
    ext_urls = [m for m in re.findall(r'https?://[^\s"\')（]+', txt)
                if _host(m) not in _ALLOW_HOSTS]
    secret_hits = [ln for ln, line in enumerate(txt.splitlines(), 1)
                   if secret_re.search(line)]
    placeholder_marked = ("プレースホルダ" in txt or "実在の顧客" in txt or "サンプル" in txt)
    ok = (not ext_urls) and (not secret_hits) and placeholder_marked
    sec_ok = sec_ok and ok
    sec_detail[label] = f"外部URL={ext_urls or 0}/秘密={secret_hits or 0}/PH明記={placeholder_marked}"
check(
    "S15 セキュリティ/依存 (klk009 全ゴールデン5ファイル: 外部URL0[w3.org/example.*除外]・秘密0・プレースホルダ明記)",
    sec_ok,
    "; ".join(f"{k}: {v}" for k, v in sec_detail.items()),
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-009 static acceptance checks (docs/designs/KLK-009.md §9 S群 を正とする)")
print("対象: fixtures/klk009/{compare,compare-partial,index-a/b/c}.html + instruction.json /")
print("      DRAFT_RULES.md / SKILL.md")
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
print("D群（test_palette_klk009.py で git check-ignore・回帰・git不在時skip）:")
print("  - D1 mockups 複数案の Git 除外成立（compare.html / index-a.html / instruction.json が exit 0）")
print("  - D2 Quality Gate 全緑（python3 -m unittest discover -s tests・回帰なし）")
print()
print("M群（環境制約で静的検証外 = tester が /draft-generate 実行 + ブラウザで手動確認）:")
print("  - M1 複数案一括生成・保存（variants:3 → index-a/b/c.html+compare.html+instruction.json）")
print("  - M2 案切替・サムネイル・原寸別タブ（compare.html でA/B/C切替・原寸↗で別タブ原寸表示）")
print("  - M3 配色バリエーション品質（同一カラム/業種/文言・配色方向差・案A が指示書配色に忠実）")
print("  - M4 一部失敗時挙動（成功案のみ表示・.partial-note で失敗通知・失敗案は保存/参照なし・instruction.json保存）")
print("  - M5 印刷/PDF導線（原寸別タブ standalone で番地等 非表示の PDF）")
print("  - M6 フォルダ自動オープン（生成後フォルダが開く / 開けない環境ではパス表示）")
print("  - M7 variants:1 後方互換（従来どおり index.html 単独・compare.html 無し）")
print("  - M8 モバイルファースト（2col-full-* をスマホ幅でメイン先頭・サイドバー本文の後ろ）")
sys.exit(1 if failed else 0)
