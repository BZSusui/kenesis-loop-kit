#!/usr/bin/env python3
"""
KLK-005 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S12 from
docs/designs/KLK-005.md §9 against palette/index.html.

Source of truth = 設計書 §9（S群）。単一HTML内のJSを正規表現・文字列位置で
静的検証する方式（tests/site/check_klk004.py と同型・tester所有）。
M群（ブラウザ実機の動的挙動: バッジ目視・色覚バッジ・形式切替コピー・退行）は
スコープ外で、tester が手動確認して結果をチケットのログへ記録する。

Run: python3 tests/site/check_klk005.py
Exit code 0 = all static checks pass, 1 = at least one fail.
Python3 標準ライブラリのみ・ネットワーク非使用。palette/ 配下は変更しない。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML_PATH = os.path.join(ROOT, "palette", "index.html")
HTML = open(HTML_PATH, encoding="utf-8").read()

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def js_block(src, marker):
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
CONTRASTBADGE_BLK = js_block(HTML, "function contrastBadge(")
CVDBADGE_BLK = js_block(HTML, "function cvdBadge(")
HEXLIST_BLK = js_block(HTML, "function hexListOf(")
COPYTEXT_BLK = js_block(HTML, "function copyTextOf(")
CSSVARS_BLK = js_block(HTML, "function cssVarsOf(")
PAINT_BLK = js_block(HTML, "function paintOutput()")
RENDER_BLK = js_block(HTML, "function render()")
SYNCURL_BLK = js_block(HTML, "function syncURL(")
RESTORE_BLK = js_block(HTML, "function restoreFromURL()")
RESET_BLK = js_block(HTML, "document.getElementById('reset').addEventListener")
SCHEMES_BLK = HTML[HTML.find("const SCHEMES"):HTML.find("// 色相の平均は円環なので")]
_tones_start = HTML.find("const TONES = [")
TONES_BLK = HTML[_tones_start:HTML.find("];", _tones_start)] if _tones_start >= 0 else ""
# .cbadge CSS ルール定義部（クラス色定義の残存確認用）
_css_start = HTML.find(".cbadge {")
CBADGE_CSS = HTML[_css_start:_css_start + 600] if _css_start >= 0 else ""

# contrastBadge 内の body 構築文と title(tip) 構築文を分離する
_body_m = re.search(r"const body\s*=\s*(.+?);", CONTRASTBADGE_BLK, re.S)
BODY_EXPR = _body_m.group(1) if _body_m else ""
_tip_m = re.search(r"const tip\s*=\s*(.+?);", CONTRASTBADGE_BLK, re.S)
TIP_EXPR = _tip_m.group(1) if _tip_m else ""

# ===========================================================================
# S1 バッジ日常語化（閾値保持＋日常語）
# ===========================================================================
th7 = bool(re.search(r"r\s*>=\s*7", CONTRASTBADGE_BLK))
th45 = bool(re.search(r"r\s*>=\s*4\.5", CONTRASTBADGE_BLK))
th3 = bool(re.search(r"r\s*>=\s*3", CONTRASTBADGE_BLK))
daily_ok = ("読みやすい ◎" in CONTRASTBADGE_BLK
            and "小さい文字は注意 △" in CONTRASTBADGE_BLK
            and "読みにくい ✕" in CONTRASTBADGE_BLK)
check(
    "S1 バッジ日常語化 (閾値7/4.5/3保持, body日常語 読みやすい◎/小さい文字は注意△/読みにくい✕)",
    th7 and th45 and th3 and daily_ok,
    f"r>=7={th7}, r>=4.5={th45}, r>=3={th3}, 日常語3種={daily_ok}",
)

# ===========================================================================
# S2 信号色（クラス再マッピング）
# ===========================================================================
cls_assigns = re.findall(r"cls\s*=\s*'([a-z]+)'", CONTRASTBADGE_BLK)
cls_set = set(cls_assigns)
only3 = cls_set == {"aaa", "lg", "ng"}
# 'aaa' は "aa" を部分文字列に含むため、閉じクォート付きの厳密一致で .aa 割当の不在を確認する
no_aa_assign = re.search(r"cls\s*=\s*'aa'", CONTRASTBADGE_BLK) is None
css_rules = (".cbadge.aaa" in HTML and ".cbadge.lg" in HTML and ".cbadge.ng" in HTML)
check(
    "S2 信号色（クラス再利用） (contrastBadge の cls は aaa/lg/ng のみ・.aa割当なし, CSS aaa/lg/ng残存)",
    only3 and no_aa_assign and css_rules,
    f"cls割当={sorted(cls_set)}(=aaa/lg/ng), .aa割当なし={no_aa_assign}, CSSルール残存={css_rules}",
)

# ===========================================================================
# S3 生数値/等級を title へ集約
# ===========================================================================
body_no_tofixed = "toFixed" not in BODY_EXPR
tip_has_ratio = "コントラスト比" in TIP_EXPR
tip_has_tofixed2 = bool(re.search(r"r\.toFixed\(2\)", TIP_EXPR))
tip_has_grade = "WCAG" in TIP_EXPR and "${grade}" in TIP_EXPR
# grade 変数が AAA/AA/大文字 を取り得ること（title へ差し込まれる正式等級）
grade_vals = ("grade = 'AAA'" in CONTRASTBADGE_BLK
              and "grade = 'AA'" in CONTRASTBADGE_BLK
              and "grade = '大文字のみ'" in CONTRASTBADGE_BLK)
check(
    "S3 生数値/等級を title へ集約 (body に r.toFixed なし, title に コントラスト比/r.toFixed(2)/WCAG等級)",
    body_no_tofixed and tip_has_ratio and tip_has_tofixed2 and tip_has_grade and grade_vals,
    f"body にtoFixedなし={body_no_tofixed}, title コントラスト比={tip_has_ratio}, "
    f"r.toFixed(2)={tip_has_tofixed2}, WCAG+grade={tip_has_grade}, "
    f"grade値 AAA/AA/大文字のみ={grade_vals}",
)

# ===========================================================================
# S4 直し方の一言
# ===========================================================================
# △(3以上)分岐と✕(else)分岐に改善方向の文字列
hint_lg = bool(re.search(r"hint\s*=\s*'文字を濃く'", CONTRASTBADGE_BLK))
hint_ng = bool(re.search(r"hint\s*=\s*'[^']*背景を明るく[^']*'", CONTRASTBADGE_BLK))
# ◎(r>=7 / r>=4.5)分岐の hint は空文字
empty_hints = len(re.findall(r"hint\s*=\s*''", CONTRASTBADGE_BLK))
check(
    "S4 直し方の一言 (△/✕分岐に「文字を濃く」「背景を明るく」, ◎分岐は hint 空)",
    hint_lg and hint_ng and empty_hints >= 2,
    f"△hint 文字を濃く={hint_lg}, ✕hint 背景を明るく含む={hint_ng}, ◎空hint数={empty_hints}(>=2)",
)

# ===========================================================================
# S5 cvdBadge無退行
# ===========================================================================
cvd_aaa = 'class="cbadge aaa"' in CVDBADGE_BLK and "色覚 ✓" in CVDBADGE_BLK
cvd_ng = 'class="cbadge ng"' in CVDBADGE_BLK and "色覚 ⚠" in CVDBADGE_BLK
four_rules = all(f".cbadge.{c}" in HTML for c in ["aaa", "aa", "lg", "ng"])
check(
    "S5 cvdBadge無退行 (cvdBadgeが cbadge aaa(色覚✓)/ng(色覚⚠)継続, CSS 4ルール aaa/aa/lg/ng 残存)",
    cvd_aaa and cvd_ng and four_rules,
    f"色覚✓(aaa)={cvd_aaa}, 色覚⚠(ng)={cvd_ng}, .cbadge4ルール残存={four_rules}",
)

# ===========================================================================
# S6 HEX一覧関数
# ===========================================================================
hexlist_def = "function hexListOf(" in HTML
hexlist_roles = ("ROLE_KEYS" in HEXLIST_BLK and "ROLE_NAMES" in HEXLIST_BLK
                 and "hslToHex" in HEXLIST_BLK)
hexlist_join = "join('\\n')" in HEXLIST_BLK
hexlist_clean = "gradient" not in HEXLIST_BLK and "hsl(" not in HEXLIST_BLK
check(
    "S6 HEX一覧関数 (hexListOf定義, ROLE_KEYS/ROLE_NAMES/hslToHex使用, join改行, グラデ/hsl()非混入)",
    hexlist_def and hexlist_roles and hexlist_join and hexlist_clean,
    f"定義={hexlist_def}, ROLE_*/hslToHex={hexlist_roles}, join改行={hexlist_join}, "
    f"グラデ/hsl非混入={hexlist_clean}",
)

# ===========================================================================
# S7 形式切替UI（再描画対象外）
# ===========================================================================
tools_ui = 'id="outputTools"' in HTML
radio_css = bool(re.search(r'name="copyfmt"\s+value="cssvars"\s+checked', HTML))
radio_hex = bool(re.search(r'name="copyfmt"\s+value="hexlist"', HTML))
# paintOutput ブロック（=#output に流し込むテンプレート）の外にあること
ui_outside_paint = 'id="outputTools"' not in PAINT_BLK and 'name="copyfmt"' not in PAINT_BLK
copyformat_var = bool(re.search(r"let\s+copyFormat\s*=", HTML))
change_listener = ("querySelectorAll('input[name=copyfmt]')" in HTML
                   and "input[name=copyfmt]:checked" in HTML)
check(
    "S7 形式切替UI（再描画対象外） (#outputTools+copyfmt radio が paintOutput 外, let copyFormat, changeリスナー)",
    tools_ui and radio_css and radio_hex and ui_outside_paint and copyformat_var and change_listener,
    f"#outputTools={tools_ui}, cssvars checked={radio_css}, hexlist={radio_hex}, "
    f"paintOutput外={ui_outside_paint}, let copyFormat={copyformat_var}, changeリスナー={change_listener}",
)

# ===========================================================================
# S8 コピー呼び分け＋都度参照
# ===========================================================================
copytext_def = "function copyTextOf(" in HTML
copytext_branch = ("copyFormat === 'hexlist'" in COPYTEXT_BLK
                   and "hexListOf" in COPYTEXT_BLK and "cssVarsOf" in COPYTEXT_BLK)
copy_current = "copyTextOf(currentPatterns[+btn.dataset.p])" in PAINT_BLK
copy_clip = "navigator.clipboard" in PAINT_BLK
copy_label = ("const copyLabel" in PAINT_BLK and "copyFormat === 'hexlist'" in PAINT_BLK
              and "${copyLabel}" in PAINT_BLK)
check(
    "S8 コピー呼び分け＋都度参照 (copyTextOfがcopyFormatで分岐, .css-copyがcopyTextOf(currentPatterns[..])+clipboard, ボタン表記copyLabel連動)",
    copytext_def and copytext_branch and copy_current and copy_clip and copy_label,
    f"copyTextOf定義={copytext_def}, 分岐={copytext_branch}, 都度参照={copy_current}, "
    f"clipboard={copy_clip}, copyLabel連動={copy_label}",
)

# ===========================================================================
# S9 版数
# ===========================================================================
title_ok = bool(re.search(r"<title>[^<]*v1\.2[^<]*</title>", HTML))
h1_ok = bool(re.search(r"<h1>[^<]*<small>v1\.2</small>", HTML))
no_old = "v1.1" not in HTML and "v1.0" not in HTML
check(
    "S9 版数 (<title>にv1.2, <h1> small が v1.2, ファイル内に v1.1/v1.0 が残存しない)",
    title_ok and h1_ok and no_old,
    f"title v1.2={title_ok}, h1 small v1.2={h1_ok}, v1.1/v1.0残存なし={no_old}",
)

# ===========================================================================
# S10 退行防止（構造）
# ===========================================================================
n_schemes = SCHEMES_BLK.count("make: (H, S, L, rng)")
n_tones = len(re.findall(r"\{\s*key:\s*'", TONES_BLK))
n_schemes_kw = SCHEMES_BLK.count("name:")
symbols = ["contrastRatio", "wcagLum", "cvdBadge", "cssVarsOf", "mulberry32",
           "toSameHue", "applyContrast", "clampMetalBand", "metalGrad",
           'id="editor"', "edH", "edS", "edL", "edHex", "edCopy", "edReset",
           "URLSearchParams", "history.replaceState",
           "function syncURL(", "function restoreFromURL()"]
missing = [s for s in symbols if s not in HTML]
scheme_names = ["補色ベース", "類似色ベース", "トーン差ベース",
                "三色配色（トライアド）", "分裂補色", "同系トーン"]
schemes_named = all(n in SCHEMES_BLK for n in scheme_names)
# URL の KNOWN に copyfmt が含まれない
known_m = re.search(r"const KNOWN\s*=\s*\[(.*?)\]", HTML, re.S)
known_body = known_m.group(1) if known_m else ""
no_copyfmt_in_known = "copyfmt" not in known_body and "copyFormat" not in known_body
check(
    "S10 退行防止 (SCHEMES6種・TONES9種・主要シンボル残存・KNOWNにcopyfmt非含有)",
    n_schemes == 6 and n_tones == 9 and schemes_named and not missing and no_copyfmt_in_known,
    f"SCHEMES={n_schemes}(=6), TONES={n_tones}(=9), scheme名6種={schemes_named}, "
    f"欠落シンボル={missing or 'なし'}, KNOWNにcopyfmt無={no_copyfmt_in_known}",
)

# ===========================================================================
# S11 URL非対象（copyFormat を URL に載せない）
# ===========================================================================
sync_clean = "copyfmt" not in SYNCURL_BLK and "copyFormat" not in SYNCURL_BLK
restore_clean = "copyfmt" not in RESTORE_BLK and "copyFormat" not in RESTORE_BLK
# KNOWN が KLK-004 と同一のキー集合（v/c/mv/t/k/base/accent/bg/sh/dm/cvd/seed + URL_SLIDERS）
expected_known = ["'v'", "'c'", "'mv'", "'t'", "'k'", "'base'", "'accent'",
                  "'bg'", "'sh'", "'dm'", "'cvd'", "'seed'"]
known_same = all(k in known_body for k in expected_known) and "...URL_SLIDERS" in known_body
check(
    "S11 URL非対象 (syncURL/restoreFromURL に copyfmt/copyFormat 無, KNOWN が KLK-004 と同一キー集合)",
    sync_clean and restore_clean and known_same,
    f"syncURL clean={sync_clean}, restoreFromURL clean={restore_clean}, KNOWN同一={known_same}",
)

# ===========================================================================
# S12 セキュリティ/依存
# ===========================================================================
ext_urls = [m for m in re.findall(r'https?://[^\s"\')]+', HTML)
            if not m.startswith("http://www.w3.org/")]
secret_re = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
secret_hits = [f"{ln}: {line.strip()[:60]}" for ln, line in enumerate(HTML.splitlines(), 1)
               if secret_re.search(line)]
check(
    "S12 セキュリティ/依存 (外部URL 0件, 秘密情報パターン 0件)",
    not ext_urls and not secret_hits,
    f"外部URL={ext_urls or 0}, 秘密情報={secret_hits or 0}",
)

# ===========================================================================
# S13 cvdバッジ信号色の値不変（退行防止の主眼）
# ---------------------------------------------------------------------------
# cvdBadge は .cbadge.aaa（緑）/ .cbadge.ng（赤）を色として再利用する。S5 は
# ルールの「残存」だけを見るため、色値そのものの書き換え（例: 緑→別色）を検知
# できない。KLK-005 の主旨は可読性バッジの信号色化で cvd の緑/赤を巻き込まない
# ことなので、.cbadge.aaa の緑テキスト色と .cbadge.ng の赤テキスト色の HEX 値が
# KLK-004 と同一で残っていることを明示的に固定する。
# ===========================================================================
aaa_green = re.search(r"\.cbadge\.aaa\s*\{[^}]*color:\s*#157f3d", HTML) is not None
aaa_bg    = re.search(r"\.cbadge\.aaa\s*\{[^}]*background:\s*#e2f5e9", HTML) is not None
ng_red    = re.search(r"\.cbadge\.ng\s*\{[^}]*color:\s*#c22525", HTML) is not None
ng_bg     = re.search(r"\.cbadge\.ng\s*\{[^}]*background:\s*#fde3e3", HTML) is not None
check(
    "S13 cvd信号色の値不変 (.cbadge.aaa 緑 #157f3d / .cbadge.ng 赤 #c22525 の色値が不変)",
    aaa_green and aaa_bg and ng_red and ng_bg,
    f"aaa緑#157f3d={aaa_green}, aaa背景#e2f5e9={aaa_bg}, ng赤#c22525={ng_red}, ng背景#fde3e3={ng_bg}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-005 static acceptance checks (docs/designs/KLK-005.md §9 S群 を正とする)")
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
print("  - M1 バッジ目視（読みやすい◎緑/小さい文字は注意△黄/読みにくい✕赤・title に比率とWCAG等級）")
print("  - M2 色覚バッジ無退行（色覚✓緑/色覚⚠赤 が従来どおり）")
print("  - M3 形式切替コピー（CSS変数/HEX一覧・ボタン表記変化・選択が消えない・微調整反映・空表示で隠れる）")
print("  - M4 退行なし（URL共有に copyfmt 付かず・リセット・トーン・metallic・ダーク/ライト・同系色）")
sys.exit(1 if failed else 0)
