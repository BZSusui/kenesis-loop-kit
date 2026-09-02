#!/usr/bin/env python3
"""
KLK-006 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S15 from
docs/designs/KLK-006.md §9 against draft-gen/index.html.

Source of truth = 設計書 §9（S群）。単一HTML内のCSS/JSを正規表現・文字列位置・
波括弧均衡ブロック抽出で静的検証する方式（tests/site/check_klk005.py と同型・
tester所有）。M群（ブラウザ実機の表示・操作・配色3方式反映・モーダル等）は
スコープ外で、tester が手動確認して結果をチケットのログへ記録する。

Run: python3 tests/site/check_klk006.py
Exit code 0 = all static checks pass, 1 = at least one fail.
Python3 標準ライブラリのみ・ネットワーク非使用。draft-gen/ 配下は変更しない。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML_PATH = os.path.join(ROOT, "draft-gen", "index.html")
HTML = open(HTML_PATH, encoding="utf-8").read()

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def js_block(src, marker):
    """marker から始まる最初のブレース均衡ブロックを返す（見つからなければ ""）。
    正規表現の量指定子 {6}/{3} は自己完結して均衡するため深さ計算に影響しない。"""
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
NORMALIZE_BLK = js_block(HTML, "function normalizeHex(")
PARSE_BLK = js_block(HTML, "function parsePalette(")
VALIDATE_BLK = js_block(HTML, "function validateRequired(")
BUILD_BLK = js_block(HTML, "function buildInstruction(")
RENDER_BLK = js_block(HTML, "function render()")
GENERATE_BLK = js_block(HTML, "function generate(")

# ===========================================================================
# S1 単一ファイル・依存ゼロ
# ===========================================================================
has_link_css = re.search(r'<link\b[^>]*rel=["\']?stylesheet', HTML, re.I) is not None
has_script_src = re.search(r'<script\b[^>]*\bsrc=', HTML, re.I) is not None
has_import = re.search(r'@import\b', HTML, re.I) is not None
has_font_cdn = bool(re.search(r'fonts\.(googleapis|gstatic)\.com|cdn\.|unpkg\.com|jsdelivr', HTML, re.I))
has_inline_style = "<style>" in HTML
has_inline_script = re.search(r"<script>\s", HTML) is not None
check(
    "S1 単一ファイル・依存ゼロ (link stylesheet/script src/@import/フォントCDN 無, インライン<style>+<script>)",
    (not has_link_css) and (not has_script_src) and (not has_import)
    and (not has_font_cdn) and has_inline_style and has_inline_script,
    f"link css={has_link_css}, script src={has_script_src}, @import={has_import}, "
    f"font/CDN={has_font_cdn}, inline<style>={has_inline_style}, inline<script>={has_inline_script}",
)

# ===========================================================================
# S2 配置・palette起動リンク
# ===========================================================================
rel_link = re.search(r'href="\.\./palette/index\.html"', HTML) is not None
target_blank = bool(re.search(
    r'href="\.\./palette/index\.html"[^>]*target="_blank"'
    r'|target="_blank"[^>]*href="\.\./palette/index\.html"', HTML))
no_parent2 = "../../palette" not in HTML
no_abs_palette = re.search(r'href="https?://[^"]*palette', HTML) is None
check(
    "S2 palette起動リンク (href=\"../palette/index.html\" 相対・target=_blank・../../palette や絶対URLでない)",
    rel_link and target_blank and no_parent2 and no_abs_palette,
    f"相対href={rel_link}, target_blank={target_blank}, ../../palette無={no_parent2}, 絶対palette無={no_abs_palette}",
)

# ===========================================================================
# S3 貼り付けパーサ CSS変数形式（大小非依存）
# ===========================================================================
css_re_present = "--color-(main|sub|accent|bg)" in PARSE_BLK
# CSS変数抽出正規表現に i フラグ（gi / ig）が付く
css_i_flag = bool(re.search(
    r"--color-\(main\|sub\|accent\|bg\)[^;]*?/[a-z]*i", PARSE_BLK))
check(
    "S3 パーサCSS変数形式 (parsePalette に --color-(main|sub|accent|bg) 抽出正規表現・iフラグ)",
    css_re_present and css_i_flag,
    f"--color-(main|sub|accent|bg)={css_re_present}, iフラグ={css_i_flag}",
)

# ===========================================================================
# S4 貼り付けパーサ HEX一覧形式
# ===========================================================================
label_re_present = "メイン|サブ|アクセント|背景" in PARSE_BLK
label_map = ("'メイン'" in PARSE_BLK or "メイン" in PARSE_BLK) and \
            ("'main'" in PARSE_BLK or "main" in PARSE_BLK)
check(
    "S4 パーサHEX一覧形式 (parsePalette が メイン|サブ|アクセント|背景 ラベル→HEX 分岐を持つ)",
    label_re_present and label_map,
    f"ラベル正規表現={label_re_present}, ラベル→role対応={label_map}",
)

# ===========================================================================
# S5 パース失敗の理由表示
# ===========================================================================
parse_error_return = bool(re.search(r"error\s*=\s*'[^']*読み取れませんでした", PARSE_BLK))
matched_empty_branch = "matched.length === 0" in PARSE_BLK or "matched.length == 0" in PARSE_BLK
ui_error_branch = "res.error" in HTML and 'id="pasteError"' in HTML
check(
    "S5 パース失敗の理由表示 (parsePalette が全役割抽出不能時に error 理由文字列, UIに読み取れませんでした表示分岐)",
    parse_error_return and matched_empty_branch and ui_error_branch,
    f"error理由={parse_error_return}, matched0分岐={matched_empty_branch}, UI表示分岐(res.error/pasteError)={ui_error_branch}",
)

# ===========================================================================
# S6 必須3項目バリデーション
# ===========================================================================
push_industry = "missing.push('業種')" in VALIDATE_BLK
push_column = "missing.push('カラム構成')" in VALIDATE_BLK
push_color = "missing.push('配色')" in VALIDATE_BLK
ok_empty = bool(re.search(r"ok:\s*missing\.length\s*===\s*0", VALIDATE_BLK))
# 生成ボタンの活性が ok と連動（render() が v.ok で disabled を切替）
btn_linked = ("validateRequired" in RENDER_BLK and "v.ok" in RENDER_BLK
              and "disabled" in RENDER_BLK)
check(
    "S6 必須3項目バリデーション (validateRequired が 業種/カラム構成/配色 を missing へ・ok=空missing, 生成ボタン活性が ok 連動)",
    push_industry and push_column and push_color and ok_empty and btn_linked,
    f"業種push={push_industry}, カラム構成push={push_column}, 配色push={push_color}, "
    f"ok=len0={ok_empty}, ボタンok連動={btn_linked}",
)

# ===========================================================================
# S7 配色の必須充足=メインのみ
# ===========================================================================
color_gate_main = bool(re.search(
    r"normalizeHex\(\s*input\.colors\s*&&\s*input\.colors\.main\s*\)", VALIDATE_BLK)) \
    or ("normalizeHex(" in VALIDATE_BLK and ".colors.main" in VALIDATE_BLK)
# sub/accent/bg を欠落条件に加えていない（missing.push は 業種/カラム構成/配色 のみ）
pushes = re.findall(r"missing\.push\('([^']+)'\)", VALIDATE_BLK)
no_sub_accent_bg_gate = set(pushes) == {"業種", "カラム構成", "配色"}
check(
    "S7 配色充足=メインのみ (validateRequired の配色判定が normalizeHex(main) 依存・sub/accent/bg を必須にしない)",
    color_gate_main and no_sub_accent_bg_gate,
    f"main判定={color_gate_main}, missing.push集合={sorted(set(pushes))}(=業種/カラム構成/配色)",
)

# ===========================================================================
# S8 未選択初期状態
# ===========================================================================
select_empty_opt = bool(re.search(r'<select id="industrySelect">\s*<option value="">', HTML))
# カラム構成ラジオに初期 checked が無い
col_radios = re.findall(r'<input type="radio" name="col"[^>]*>', HTML)
col_no_checked = all("checked" not in r for r in col_radios)
# メインhex入力が初期空（value属性を持たない or 空）
mainhex_m = re.search(r'<input[^>]*id="hex-main"[^>]*>', HTML)
mainhex_tag = mainhex_m.group(0) if mainhex_m else ""
mainhex_empty = mainhex_tag != "" and not re.search(r'\bvalue="[^"]+"', mainhex_tag)
check(
    "S8 未選択初期状態 (industrySelect 先頭に空option, col ラジオ初期checked無, hex-main に非空value無)",
    select_empty_opt and col_no_checked and mainhex_empty,
    f"空option={select_empty_opt}, col無checked={col_no_checked}(radio {len(col_radios)}件), hex-main初期空={mainhex_empty}",
)

# ===========================================================================
# S9 生成指示書スキーマ
# ===========================================================================
# KLK-062: output.mobile は廃止（スマホ確認は比較画面の幅切替へ移行）。"mobile:" は必須キーから外し、
# 「復活していないこと」を退行検査として別途見る。
schema_keys = [
    "schema:", "version:", "project:", "resolved:", "columns:",
    "taste:", "main:", "autofill:", "thumbnails:", "sampleUrls:",
    "atari:", "variants:", "animation:",
]
missing_keys = [k for k in schema_keys if k not in BUILD_BLK]
removed_keys = [k for k in ("mobile:",) if k in BUILD_BLK]
schema_val = "'design-draft-instruction'" in BUILD_BLK
version_val = bool(re.search(r"version:\s*1\b", BUILD_BLK))
check(
    "S9 生成指示書スキーマ (buildInstruction に schema/version/meta.project/industry.resolved/layout.columns/taste/colors.main/autofill/references.*/atari/output.* キー・mobile は廃止済み)",
    (not missing_keys) and (not removed_keys) and schema_val and version_val,
    f"欠落キー={missing_keys or 'なし'}, 廃止済みなのに残存={removed_keys or 'なし'}, "
    f"schema値={schema_val}, version:1={version_val}",
)

# ===========================================================================
# S10 出力＝クリップボード+画面表示・ファイル保存なし
# ===========================================================================
clipboard_write = "navigator.clipboard" in HTML and "writeText" in HTML
json_stringify = "JSON.stringify(instruction" in HTML or "JSON.stringify(instruction, null, 2)" in HTML
no_create_object_url = "createObjectURL" not in HTML
no_blob = not re.search(r"\bnew\s+Blob\b", HTML)
no_download_attr = re.search(r"<a\b[^>]*\bdownload\b", HTML, re.I) is None and \
    re.search(r"\.download\s*=", HTML) is None
readonly_ta = 'id="resultJson" readonly' in HTML or bool(re.search(r'id="resultJson"[^>]*readonly', HTML))
check(
    "S10 出力=クリップボード+画面表示 (navigator.clipboard.writeText + JSON.stringify, createObjectURL/Blob/download 無, readonly textarea)",
    clipboard_write and json_stringify and no_create_object_url and no_blob and no_download_attr and readonly_ta,
    f"clipboard.writeText={clipboard_write}, JSON.stringify={json_stringify}, createObjectURL無={no_create_object_url}, "
    f"Blob無={no_blob}, download無={no_download_attr}, readonly={readonly_ta}",
)

# ===========================================================================
# S11 カラム構成6系統（R-A: KLK-008 で 4→6値へ拡張）
# ===========================================================================
col_values = set(re.findall(r'<input type="radio" name="col"[^>]*value="([^"]+)"', HTML))
expected_cols = {
    "1col", "2col-full-left", "2col-full-right",
    "2col-body-left", "2col-body-right", "3col",
}
check(
    "S11 カラム構成6系統 (name=col ラジオが 1col/2col-full-left/2col-full-right/2col-body-left/2col-body-right/3col の6値)",
    col_values == expected_cols,
    f"col値={sorted(col_values)}(=1col/2col-full-left/2col-full-right/2col-body-left/2col-body-right/3col)",
)

# ===========================================================================
# S12 各UIの存在
# ===========================================================================
has_industry_select = 'id="industrySelect"' in HTML
has_industry_custom = bool(re.search(r'<input type="text" id="industryCustom"', HTML))
taste_radios = re.findall(r'<input type="radio" name="taste"', HTML)
taste_ok = len(taste_radios) >= 11
atari_values = set(re.findall(r'<input type="radio" name="atari"[^>]*value="([^"]+)"', HTML))
atari_ok = atari_values == {"standard", "free-photo"}
var_values = set(re.findall(r'<input type="radio" name="variants"[^>]*value="([^"]+)"', HTML))
var_ok = var_values == {"1", "3"}
# KLK-062: スマホ同時生成は廃止し比較画面の幅切替へ移行。#mobileW / #mobileOn は撤去され、
# 代わりに「比較画面で表示幅を切り替えられる」案内が置かれる契約になった。
no_mobile_ui = ('id="mobileW"' not in HTML) and ('id="mobileOn"' not in HTML)
has_widthhint = "表示幅を切り替え" in HTML
has_projectname = 'id="projectName"' in HTML
has_sampleurl = 'class="sample-url"' in HTML
check(
    "S12 各UI (業種select+自由入力・テイスト11種・アタリ2種・案数2種・スマホ設定は撤去済み・案件名・見本URL)",
    (has_industry_select and has_industry_custom and taste_ok and atari_ok
     and var_ok and no_mobile_ui and has_widthhint and has_projectname and has_sampleurl),
    f"industrySelect={has_industry_select}, industryCustom={has_industry_custom}, taste={len(taste_radios)}(>=11), "
    f"atari={sorted(atari_values)}, variants={sorted(var_values)}, "
    f"スマホ設定撤去={no_mobile_ui}, 幅切替の案内={has_widthhint}, "
    f"projectName={has_projectname}, sample-url={has_sampleurl}",
)

# ===========================================================================
# S13 実績サムネイル=プレースホルダ
# ===========================================================================
no_img = re.search(r"<img\b", HTML, re.I) is None
placeholder_grad = ".thumb .ph" in HTML and bool(re.search(r"\.ph\s*\{[^}]*linear-gradient", HTML, re.S))
has_thumb_ui = 'class="thumb"' in HTML and "data-id=" in HTML
max3_logic = bool(re.search(r"\.thumb\.selected'?\)?\.length\s*>=\s*3", HTML)) or ">= 3" in HTML
count_label = 'id="thumbCount"' in HTML and "/ 3枚" in HTML
check(
    "S13 実績サムネイル=プレースホルダ (<img>無・CSSグラデ .ph・選択UI・最大3枚ロジック)",
    no_img and placeholder_grad and has_thumb_ui and max3_logic and count_label,
    f"<img>無={no_img}, .phグラデ={placeholder_grad}, thumb選択UI={has_thumb_ui}, 最大3ロジック={max3_logic}, カウント表示={count_label}",
)

# ===========================================================================
# S14 純粋ロジック分離（スライス可能）
# ===========================================================================
i_marker = HTML.find("const COLUMN_KEYS")
i_norm = HTML.find("function normalizeHex(")
i_parse = HTML.find("function parsePalette(")
i_valid = HTML.find("function validateRequired(")
i_build = HTML.find("function buildInstruction(")
i_render = HTML.find("function render()")
order_ok = (0 <= i_marker < i_norm < i_parse < i_valid < i_build < i_render)
marker_present = i_marker >= 0
check(
    "S14 純粋ロジック分離 (const COLUMN_KEYS マーカー先頭・normalizeHex/parsePalette/validateRequired/buildInstruction が render() より前)",
    marker_present and order_ok,
    f"const COLUMN_KEYS={marker_present}, 定義順(marker<normalize<parse<validate<build<render)={order_ok} "
    f"[{i_marker},{i_norm},{i_parse},{i_valid},{i_build},{i_render}]",
)

# ===========================================================================
# S15 セキュリティ/依存（S-SEC）
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
check(
    "S15 セキュリティ/依存 (外部URL 0件[w3.org/example.* 除外]・秘密情報パターン 0件)",
    not ext_urls and not secret_hits,
    f"外部URL={ext_urls or 0}, 秘密情報={secret_hits or 0}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-006 static acceptance checks (docs/designs/KLK-006.md §9 S群 を正とする)")
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
print("M群（環境制約で静的検証外 = tester がブラウザで手動確認）:")
print("  - M1 表示・レイアウト（8セクション+固定フッター・狭幅で崩れない）")
print("  - M2 配色3方式の反映（①swatch↔hex同期 ②メインのみ ③貼付取込・読めない文字列で理由表示）")
print("  - M3 必須バリデーション（不足列挙・生成ボタン非活性→3項目で活性→コピー+表示）")
print("  - M4 実績サムネイル（業種連動・選択2〜3枚・拡大モーダル・実画像なし）")
print("  - M5 生成指示書の中身（案件名/業種resolved/カラム/テイスト/配色4色+autofill/URL/アタリ/案数/スマホ幅・version:1/schema）")
sys.exit(1 if failed else 0)
