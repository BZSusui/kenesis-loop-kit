#!/usr/bin/env python3
"""
KLK-007 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S13 from
docs/designs/KLK-007.md §9.

検証対象（プロダクション成果物・testerは変更しない）:
  - ゴールデンサンプル  tests/fixtures/klk007/sample-draft.html
  - 生成規約Doc         .claude/skills/draft-generate/templates/DRAFT_RULES.md
  - スキル定義          .claude/skills/draft-generate/SKILL.md
  - .gitignore 三者     .gitignore / .gitignore.public / .gitignore.private

Source of truth = 設計書 §9（S群）。正規表現・文字列検索・波括弧均衡ブロック抽出で
静的検証する方式（tests/site/check_klk006.py と同型・tester所有）。生成は非決定的で
mockups/ はGit除外のため、実生成物ではなく DRAFT_RULES 準拠の代表出力（ゴールデン
サンプル）を検証する。D群（git check-ignore）は tests/test_palette_klk007.py が担い、
M群（ブラウザ実機・実生成品質）は tester が手動確認してチケットのログへ記録する。

Run: python3 tests/site/check_klk007.py
Exit code 0 = all static checks pass, 1 = at least one fail.
Python3 標準ライブラリのみ・ネットワーク非使用。プロダクション成果物は変更しない。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAMPLE_PATH = os.path.join(ROOT, "tests", "fixtures", "klk007", "sample-draft.html")
RULES_PATH = os.path.join(
    ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md")
SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md")
GITIGNORE_PATHS = [
    os.path.join(ROOT, ".gitignore"),
    os.path.join(ROOT, ".gitignore.public"),
    os.path.join(ROOT, ".gitignore.private"),
]

HTML = open(SAMPLE_PATH, encoding="utf-8").read()
RULES = open(RULES_PATH, encoding="utf-8").read()
SKILL = open(SKILL_PATH, encoding="utf-8").read()

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


# --- 主要ブロックの抽出 -----------------------------------------------------
SCRIPT_M = re.search(r"<script>(.*?)</script>", HTML, re.S)
SCRIPT = SCRIPT_M.group(1) if SCRIPT_M else ""
PRINT_BLK = css_block(HTML, "@media print")

# ===========================================================================
# S1 単一ファイル・依存ゼロ（NFR-005）
# ===========================================================================
has_link_css = re.search(r'<link\b[^>]*rel=["\']?stylesheet', HTML, re.I) is not None
has_script_src = re.search(r'<script\b[^>]*\bsrc=', HTML, re.I) is not None
has_import = re.search(r'@import\b', HTML, re.I) is not None
has_font_cdn = bool(re.search(
    r'fonts\.(googleapis|gstatic)\.com|cdn\.|unpkg\.com|jsdelivr', HTML, re.I))
has_img_ext = re.search(r'<img\b[^>]*\bsrc=["\']?https?:', HTML, re.I) is not None
has_inline_style = "<style>" in HTML
has_inline_script = re.search(r"<script>\s", HTML) is not None
check(
    "S1 単一ファイル・依存ゼロ (link stylesheet/script src/@import/フォントCDN/外部img 無, インライン<style>+<script>)",
    (not has_link_css) and (not has_script_src) and (not has_import)
    and (not has_font_cdn) and (not has_img_ext)
    and has_inline_style and has_inline_script,
    f"link css={has_link_css}, script src={has_script_src}, @import={has_import}, "
    f"font/CDN={has_font_cdn}, 外部img={has_img_ext}, "
    f"inline<style>={has_inline_style}, inline<script>={has_inline_script}",
)

# ===========================================================================
# S2 配色CSS変数の適用（REQ-005 / U5）
# ===========================================================================
theme_vars = ["--m-main", "--m-nav", "--m-accent", "--m-bg", "--m-text"]
defined = {}
for v in theme_vars:
    defined[v] = re.search(re.escape(v) + r"\s*:\s*[^;]+;", HTML) is not None
all_defined = all(defined.values())
referenced = {}
for v in theme_vars:
    referenced[v] = re.search(r"var\(\s*" + re.escape(v) + r"\s*\)", HTML) is not None
all_referenced = all(referenced.values())
# 直値の主要色散在なし: main/nav/accent/bg の直値HEXは定義（1回）以外に散在しない
scatter = {}
for v in ("--m-main", "--m-nav", "--m-accent", "--m-bg"):
    m = re.search(re.escape(v) + r"\s*:\s*(#[0-9a-fA-F]{3,8})\b", HTML)
    if m:
        hexv = m.group(1)
        scatter[v] = len(re.findall(re.escape(hexv), HTML, re.I))
no_scatter = all(c == 1 for c in scatter.values()) and len(scatter) == 4
check(
    "S2 配色CSS変数 (--m-main/--m-nav/--m-accent/--m-bg/--m-text 定義+var()参照, 主要色の直値散在なし)",
    all_defined and all_referenced and no_scatter,
    f"定義={ {k: v for k, v in defined.items()} }, 参照={ {k: v for k, v in referenced.items()} }, "
    f"直値出現数(定義含む,=1が正)={scatter}",
)

# ===========================================================================
# S3 番地ラベル（REQ-005 / REQ-103基盤）
# ===========================================================================
addr_pins = ["NAV-01", "HERO-01", "ABOUT-01", "MENU-01", "GALLERY-01", "FOOTER-01"]
pin_found = {p: (re.search(r'class="pin">\s*' + re.escape(p), HTML) is not None) for p in addr_pins}
all_pins = all(pin_found.values())
sec_count = len(re.findall(r'class="sec\b', HTML))
addr_in_scope = re.search(r'class="addr"[^>]*>\s*<span class="pin"', HTML) is not None
check(
    "S3 番地ラベル (.addr>.pin が NAV/HERO/ABOUT/MENU/GALLERY/FOOTER-01 6種, 各 .sec 単位)",
    all_pins and sec_count >= 6 and addr_in_scope,
    f"pin検出={ [p for p in addr_pins if pin_found[p]] }, .sec数={sec_count}(>=6), .addr>.pin構造={addr_in_scope}",
)

# ===========================================================================
# S4 アタリ画像 a方式（REQ-006）
# ===========================================================================
has_atari = 'class="atari"' in HTML
atari_colormix = bool(re.search(r"\.atari\s*\{[^}]*color-mix", HTML, re.S))
has_desc = 'class="desc"' in HTML
has_kw = 'class="kw"' in HTML and re.search(r'検索:\s*<b>', HTML) is not None
has_atari_tag = 'class="atari-tag"' in HTML
# kw 無フォールバック: .desc を持つが .kw を持たない .atari ブロックが存在する
kwless = bool(re.search(
    r'<div class="atari">(?:(?!</div>).)*class="desc"(?:(?!</div>).)*</div>', HTML))
kwless_no_kw = False
for blk in re.findall(r'<div class="atari">.*?</div>', HTML):
    if 'class="desc"' in blk and 'class="kw"' not in blk:
        kwless_no_kw = True
        break
check(
    "S4 アタリa方式 (.atari色面color-mix + .desc + .kw(検索:<b>) + HERO .atari-tag, kw無フォールバック有)",
    has_atari and atari_colormix and has_desc and has_kw and has_atari_tag and kwless_no_kw,
    f".atari={has_atari}, color-mix={atari_colormix}, .desc={has_desc}, .kw(検索:<b>)={has_kw}, "
    f".atari-tag={has_atari_tag}, kw無フォールバック={kwless_no_kw}",
)

# ===========================================================================
# S5 仮文言・ダミー禁止（REQ-007）
# ===========================================================================
has_todo = 'class="todo"' in HTML and re.search(r'\(要検討[:：]', HTML) is not None
dummy_patterns = {
    "lorem ipsum": bool(re.search(r"lorem\s+ipsum", HTML, re.I)),
    "サンプルテキスト": "サンプルテキスト" in HTML,
    "テキストテキスト": "テキストテキスト" in HTML,
    "aaa(連続a)": bool(re.search(r"a{3,}", HTML)),
}
dummy_hits = [k for k, v in dummy_patterns.items() if v]
check(
    "S5 仮文言・ダミー禁止 (.todo=(要検討:…) 有, lorem/サンプルテキスト/テキストテキスト/aaa 埋草 0件)",
    has_todo and not dummy_hits,
    f".todo(要検討:)={has_todo}, 埋草ヒット={dummy_hits or 'なし'}",
)

# ===========================================================================
# S6 @media print で補助非表示（REQ-009 / NFR-003）
# ===========================================================================
print_present = PRINT_BLK != ""
print_hides = all(sel in PRINT_BLK for sel in (".addr", ".atari-tag", ".anim-note"))
print_display_none = re.search(r"display\s*:\s*none", PRINT_BLK) is not None
check(
    "S6 @media print 補助非表示 (.addr/.atari-tag/.anim-note に display:none)",
    print_present and print_hides and print_display_none,
    f"@media print有={print_present}, 3セレクタ内包={print_hides}, display:none={print_display_none}",
)

# ===========================================================================
# S7 スクロール出現アニメ（外部依存ゼロ・REQ-005 / U6 / NFR-005）
# ===========================================================================
has_io = "IntersectionObserver" in SCRIPT
reveal_query = re.search(r"querySelectorAll\(\s*['\"]\.reveal['\"]", SCRIPT) is not None
adds_in = re.search(r"classList\.add\(\s*['\"]in['\"]\s*\)", SCRIPT) is not None
fallback = re.search(r"!\s*\(\s*['\"]IntersectionObserver['\"]\s+in\s+window\s*\)", SCRIPT) is not None
reduced_motion = re.search(r"prefers-reduced-motion\s*:\s*reduce", HTML) is not None
script_no_ext = re.search(r"https?://", SCRIPT) is None
check(
    "S7 出現アニメ (IntersectionObserver + .reveal→.in + 非対応時全表示 + reduced-motion無効化, 外部URL無)",
    has_io and reveal_query and adds_in and fallback and reduced_motion and script_no_ext,
    f"IntersectionObserver={has_io}, .reveal取得={reveal_query}, .in付与={adds_in}, "
    f"非対応fallback={fallback}, reduced-motion={reduced_motion}, script外部URL無={script_no_ext}",
)

# ===========================================================================
# S8 カラム構成の反映（REQ-002）
# ===========================================================================
dc_m = re.search(r'data-columns="([^"]+)"', HTML)
dc_val = dc_m.group(1) if dc_m else ""
dc_ok = dc_val in {"1col", "2col-sub-left", "2col-sub-right", "3col"}
check(
    "S8 カラム構成 (生成ルートに data-columns, 値が 1col/2col-sub-left/2col-sub-right/3col)",
    dc_m is not None and dc_ok,
    f"data-columns={dc_val or 'なし'}(サンプルは1col想定)",
)

# ===========================================================================
# S9 レスポンシブ（NFR-002）
# ===========================================================================
responsive = re.search(r"@media[^{]*max-width\s*:\s*640px", HTML) is not None
check(
    "S9 レスポンシブ (@media (max-width:640px) 分岐が存在)",
    responsive,
    f"@media max-width:640px={responsive}",
)

# ===========================================================================
# S10 .gitignore 三者同期（REQ-011 / NFR-004 / F5）
# ===========================================================================
gi_status = {}
for p in GITIGNORE_PATHS:
    try:
        txt = open(p, encoding="utf-8").read()
        gi_status[os.path.basename(p)] = re.search(r"(?m)^\s*mockups/\s*$", txt) is not None
    except OSError:
        gi_status[os.path.basename(p)] = False
all_gi = all(gi_status.values()) and len(gi_status) == 3
check(
    "S10 .gitignore三者同期 (.gitignore/.gitignore.public/.gitignore.private 全てに mockups/ 行)",
    all_gi,
    f"mockups/行={gi_status}",
)

# ===========================================================================
# S11 規約Doc（DRAFT_RULES.md）必須節（方式(c)）
# ===========================================================================
rules_sections = {
    "配色マッピング": "配色マッピング" in RULES,
    "アタリ画像a方式": ("アタリ画像" in RULES and "a方式" in RULES),
    "番地ラベル": "番地ラベル" in RULES,
    "印刷CSS(@media print)": ("@media print" in RULES and ("印刷" in RULES)),
    "出現アニメ": ("出現アニメ" in RULES or "IntersectionObserver" in RULES),
    "カラム構成": "カラム構成" in RULES,
    "保存規約": "保存規約" in RULES,
}
missing_sections = [k for k, v in rules_sections.items() if not v]
check(
    "S11 規約Doc必須節 (DRAFT_RULES.md に 配色マッピング/アタリa方式/番地ラベル/印刷CSS/出現アニメ/カラム構成/保存規約)",
    not missing_sections,
    f"欠落節={missing_sections or 'なし'}",
)

# ===========================================================================
# S12 保存規約の明記（REQ-010 / U4）
# ===========================================================================
save_src = SKILL + "\n" + RULES
path_rule = re.search(r"mockups/\{[^}]*\}_\{[^}]*\}/", save_src) is not None \
    or ("mockups/" in save_src and "案件名" in save_src and "YYYY-MM-DD" in save_src)
names_rule = "index.html" in save_src and "instruction.json" in save_src
safe_rule = ("パス安全化" in save_src) or ("untitled" in save_src)
check(
    "S12 保存規約明記 (SKILL/DRAFT_RULES に mockups/{YYYY-MM-DD}_{案件名}/ + index.html/instruction.json + パス安全化)",
    path_rule and names_rule and safe_rule,
    f"パス規約={path_rule}, ファイル命名={names_rule}, パス安全化={safe_rule}",
)

# ===========================================================================
# S13 セキュリティ/依存（S-SEC・NFR-005 / NFR-004 / REQ-011）
# ===========================================================================
_ALLOW_HOSTS = ("www.w3.org", "example.com", "example.org", "example.net")


def _host(url):
    m = re.match(r"https?://([^/\s\"')]+)", url)
    return m.group(1).lower() if m else ""


ext_urls = [m for m in re.findall(r'https?://[^\s"\')（]+', HTML)
            if _host(m) not in _ALLOW_HOSTS]
secret_re = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
secret_hits = [f"{ln}: {line.strip()[:60]}" for ln, line in enumerate(HTML.splitlines(), 1)
               if secret_re.search(line)]
# プレースホルダである旨の明記（実在案件でないことの証跡）
placeholder_marked = ("実在の顧客" in HTML) or ("プレースホルダ" in HTML) or ("サンプル" in HTML)
check(
    "S13 セキュリティ/依存 (外部URL 0件[w3.org/example.* 除外]・秘密情報 0件・プレースホルダ明記)",
    (not ext_urls) and (not secret_hits) and placeholder_marked,
    f"外部URL={ext_urls or 0}, 秘密情報={secret_hits or 0}, プレースホルダ明記={placeholder_marked}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-007 static acceptance checks (docs/designs/KLK-007.md §9 S群 を正とする)")
print("対象: tests/fixtures/klk007/sample-draft.html / DRAFT_RULES.md / .gitignore x3")
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
print("D群（test_palette_klk007.py で git check-ignore・git不在時skip）:")
print("  - D1 mockups/ のGit除外成立（index.html / instruction.json が exit 0）")
print()
print("M群（環境制約で静的検証外 = tester が /draft-generate 実行 + ブラウザで手動確認）:")
print("  - M1 実生成・保存（mockups/{日付}_{案件名}/ に index.html+instruction.json・variants:3でも1案のみ）")
print("  - M2 表示・配色・カラム反映（Chromeで nav/HERO/セクション・指示書配色・columns・狭幅で崩れない）")
print("  - M3 アタリ・仮文言（a方式・業種/テイストに合う実文言・未定は(要検討:…)）")
print("  - M4 スクロール出現アニメ（フェードイン・視差効果を減らす設定で無効）")
print("  - M5 印刷/PDF品質（A4で番地ラベル/アタリタグ/注記が非表示・レイアウト破綻なし）")
print("  - M6 autofill補完（sub/accent/bg null時に §4.3 補完ルールで欠色/低コントラストにならない）")
sys.exit(1 if failed else 0)
