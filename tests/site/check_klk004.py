#!/usr/bin/env python3
"""
KLK-004 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S12 from
docs/designs/KLK-004.md §9 against palette/index.html.

Source of truth = 設計書 §9（S群）。単一HTML内のJSを正規表現・文字列位置で
静的検証する方式（tests/site/check_klk002.py と同型・tester所有）。
M群（ブラウザ実機の動的挙動: 帯の実測・グラデ描画・URL往復等）はスコープ外で、
tester が手動確認して結果をチケットのログへ記録する。

Run: python3 tests/site/check_klk004.py
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
METALLICS_BLK = js_block(HTML, "const METALLICS = {")
COMPUTEBASE_BLK = js_block(HTML, "function computeBase()")
MAKEPATTERNS_BLK = js_block(HTML, "function makePatterns(")
BUILDCOLORS_BLK = js_block(HTML, "function buildColors()")
BUILDKEYWORDS_BLK = js_block(HTML, "function buildKeywords()")
SUMMARIES_BLK = js_block(HTML, "function updateSummaries()")
PAINT_BLK = js_block(HTML, "function paintOutput()")
CSSVARS_BLK = js_block(HTML, "function cssVarsOf(")
RENDER_BLK = js_block(HTML, "function render()")
RESET_BLK = js_block(HTML, "document.getElementById('reset').addEventListener")
SCHEMES_BLK = HTML[HTML.find("const SCHEMES"):HTML.find("// 色相の平均は円環なので")]
_tones_start = HTML.find("const TONES = [")
TONES_BLK = HTML[_tones_start:HTML.find("];", _tones_start)] if _tones_start >= 0 else ""
GENRE_BLK = js_block(HTML, "'ジャンル（業種）': {")

# ===========================================================================
# S1 metallic定義
# ===========================================================================
gold_def = bool(re.search(r"key:\s*'gold'[^}]*metallic:\s*true", HTML))
silver_def = bool(re.search(r"key:\s*'silver'[^}]*metallic:\s*true", HTML))
variant_keys = ["'yellow'", "'pink'", "'green'", "'cool'", "'warm'", "'gunmetal'"]
variants_ok = all(f"key: {k}" in METALLICS_BLK for k in variant_keys)
n_htol = METALLICS_BLK.count("hTol")
n_ldark = METALLICS_BLK.count("lDark")
n_partners = METALLICS_BLK.count("partners:")
n_accent = len(re.findall(r"accent:\s*\[", METALLICS_BLK))
n_sub = len(re.findall(r"sub:\s*\[", METALLICS_BLK))
band_ok = n_htol == 6 and n_ldark == 6
partners_ok = n_partners == 6 and n_accent == 18 and n_sub == 18
check(
    "S1 metallic定義 (COLORS gold/silver metallic:true, METALLICS 6変種×band×partners3)",
    gold_def and silver_def and variants_ok and band_ok and partners_ok,
    f"gold={gold_def}, silver={silver_def}, 変種6種={variants_ok}, "
    f"hTol×{n_htol}/lDark×{n_ldark}(=6), partners×{n_partners}(=6), "
    f"partner accent×{n_accent}/sub×{n_sub}(=18)",
)

# ===========================================================================
# S2 変種UI
# ===========================================================================
mv_container = 'id="metallicVariant"' in BUILDCOLORS_BLK
mv_radio_tpl = 'name="mv-${mk}"' in BUILDCOLORS_BLK
mv_first_checked = "${i === 0 ? ' checked' : ''}" in BUILDCOLORS_BLK
# 先頭変種（=checked になる変種）が gold=yellow / silver=cool であること
g = METALLICS_BLK
order_gold = 0 <= g.find("key: 'yellow'") < g.find("key: 'pink'") < g.find("key: 'green'")
order_silver = g.find("key: 'green'") < g.find("key: 'cool'") < g.find("key: 'warm'") < g.find("key: 'gunmetal'")
sync_fn = "function syncMetallicUI()" in HTML
reset_mv = ("mv-gold" in RESET_BLK and '"yellow"' in RESET_BLK
            and "mv-silver" in RESET_BLK and '"cool"' in RESET_BLK
            and "syncMetallicUI()" in RESET_BLK)
check(
    "S2 変種UI (#metallicVariant生成, mv-gold=yellow/mv-silver=cool 先頭checked, syncMetallicUI, リセット初期化)",
    mv_container and mv_radio_tpl and mv_first_checked and order_gold and order_silver and sync_fn and reset_mv,
    f"container={mv_container}, radioテンプレート={mv_radio_tpl}, 先頭checked={mv_first_checked}, "
    f"gold順(yellow先頭)={order_gold}, silver順(cool先頭)={order_silver}, "
    f"syncMetallicUI定義={sync_fn}, リセット初期化={reset_mv}",
)

# ===========================================================================
# S3 最終段クランプ
# ===========================================================================
clamp_fn = "function clampMetalBand(" in HTML
pos_contrast = MAKEPATTERNS_BLK.rfind("applyContrast")
pos_clamp = MAKEPATTERNS_BLK.find("clampMetalBand")
clamp_after_contrast = 0 <= pos_contrast < pos_clamp
clamp_on_main = bool(re.search(r"c\.main\s*=\s*clampMetalBand\(c\.main", MAKEPATTERNS_BLK))
check(
    "S3 最終段クランプ (clampMetalBand定義, makePatterns内でapplyContrastより後にmainへ適用)",
    clamp_fn and clamp_after_contrast and clamp_on_main,
    f"定義={clamp_fn}, applyContrast位置={pos_contrast} < clampMetalBand位置={pos_clamp}: "
    f"{clamp_after_contrast}, main限定適用={clamp_on_main}",
)

# ===========================================================================
# S4 金属グラデは表示のみ
# ===========================================================================
grad_fn = "function metalGrad(" in HTML
grad_in_paint = "metalGrad" in PAINT_BLK
grad_in_chips = "metalGrad" in BUILDCOLORS_BLK
no_grad_in_data = ("metalGrad" not in MAKEPATTERNS_BLK
                   and "linear-gradient" not in MAKEPATTERNS_BLK
                   and "metalGrad" not in CSSVARS_BLK
                   and "gradient" not in CSSVARS_BLK)
cssvars_solid = bool(re.search(r"--color-main:\s*\$\{main\}", CSSVARS_BLK)) and "hslToHex" in CSSVARS_BLK
check(
    "S4 金属グラデは表示のみ (metalGradはpaintOutput/buildColors参照, データ経路・CSS変数に混入なし)",
    grad_fn and grad_in_paint and grad_in_chips and no_grad_in_data and cssvars_solid,
    f"定義={grad_fn}, paintOutput参照={grad_in_paint}, チップ見本参照={grad_in_chips}, "
    f"データ経路に混入なし={no_grad_in_data}, cssVarsOf単色hex={cssvars_solid}",
)

# ===========================================================================
# S5 ジャンルradio化
# ===========================================================================
genre_const = "const GENRE_CAT = 'ジャンル（業種）'" in HTML
genre_branch = "GENRE_CAT" in BUILDKEYWORDS_BLK
genre_none = bool(re.search(
    r'<input type="radio" name="kwgenre" value=""\s+checked>', BUILDKEYWORDS_BLK))
genre_radio = 'name="kwgenre" value="${cat}/${k}"' in BUILDKEYWORDS_BLK
other_checkbox = '<input type="checkbox" value="${cat}/${k}">' in BUILDKEYWORDS_BLK
check(
    "S5 ジャンルradio化 (buildKeywordsにジャンル分岐, kwgenre radio+指定なし空値checked, 他カテゴリはcheckbox)",
    genre_const and genre_branch and genre_none and genre_radio and other_checkbox,
    f"GENRE_CAT定義={genre_const}, 分岐={genre_branch}, 指定なしradio={genre_none}, "
    f"ジャンルradio={genre_radio}, 他checkbox維持={other_checkbox}",
)

# ===========================================================================
# S6 空値ガード
# ===========================================================================
empty_guard = "if (!el.value) return" in COMPUTEBASE_BLK
dict_guard = "KEYWORDS[cat] && KEYWORDS[cat][key]" in COMPUTEBASE_BLK
sum_filter = ".filter(el => el.value)" in SUMMARIES_BLK
check(
    "S6 空値ガード (computeBaseの空値+辞書存在の二重ガード, サマリ件数の空値除外)",
    empty_guard and dict_guard and sum_filter,
    f"空値ガード={empty_guard}, 辞書存在チェック={dict_guard}, サマリ空値除外={sum_filter}",
)

# ===========================================================================
# S7 CSS変数コピー
# ===========================================================================
copy_btn = 'class="css-copy" data-p="${pi}"' in PAINT_BLK and "pattern-head" in PAINT_BLK
copy_bind = "querySelectorAll('.css-copy')" in PAINT_BLK
copy_clip = "navigator.clipboard" in PAINT_BLK
# 微調整後の値を都度再計算（KLK-005 で cssVarsOf → copyTextOf に差し替え。都度 currentPatterns 参照は維持）
copy_current = ("cssVarsOf(currentPatterns[+btn.dataset.p])" in PAINT_BLK
                or "copyTextOf(currentPatterns[+btn.dataset.p])" in PAINT_BLK)
root_tpl = all(v in CSSVARS_BLK for v in
               [":root {", "--color-main:", "--color-sub:", "--color-accent:", "--color-bg:"])
check(
    "S7 CSS変数コピー (pattern-headのcss-copyボタン, paintOutput内クリック登録, :rootテンプレート4変数)",
    copy_btn and copy_bind and copy_clip and copy_current and root_tpl,
    f"ボタン={copy_btn}, クリック登録={copy_bind}, clipboard={copy_clip}, "
    f"currentPatternsから再計算={copy_current}, :root4変数={root_tpl}",
)

# ===========================================================================
# S8 URL同期
# ===========================================================================
usp = "URLSearchParams" in HTML
replace_state = "history.replaceState" in HTML
sync_def = "function syncURL(" in HTML
restore_def = "function restoreFromURL()" in HTML
render_calls_sync = "syncURL(" in RENDER_BLK
init_calls_restore = bool(re.search(r"^restoreFromURL\(\);", HTML, re.M))
seed_read = "params.get('seed')" in HTML
seed_write = "p.set('seed'" in HTML
share_btn = bool(re.search(r'<button id="share"[^>]*>URLをコピー</button>', HTML))
share_listener = "document.getElementById('share').addEventListener" in HTML
check(
    "S8 URL同期 (URLSearchParams/replaceState, syncURL/restoreFromURL定義と呼び出し, seed読み書き, #shareボタン)",
    usp and replace_state and sync_def and restore_def and render_calls_sync
    and init_calls_restore and seed_read and seed_write and share_btn and share_listener,
    f"URLSearchParams={usp}, replaceState={replace_state}, syncURL={sync_def}, "
    f"restoreFromURL={restore_def}, render→syncURL={render_calls_sync}, "
    f"初期化→restoreFromURL={init_calls_restore}, seed読={seed_read}/書={seed_write}, "
    f"shareボタン={share_btn}, リスナー={share_listener}",
)

# ===========================================================================
# S9 リセット網羅
# ===========================================================================
reset_items = {
    "ジャンル指定なし": 'input[name=kwgenre][value=""]' in RESET_BLK,
    "変種初期値": "mv-gold" in RESET_BLK and "mv-silver" in RESET_BLK,
    "colorfam": 'input[name=colorfam][value=""]' in RESET_BLK,
    "tone": 'input[name=tone][value=""]' in RESET_BLK,
    "スライダー9本": all(f"'{s}'" in RESET_BLK for s in
                    ["warm", "gender", "formal", "light", "vivid", "muted", "contrast", "age", "season"]),
    "useBase": "useBase.checked = false" in RESET_BLK,
    "useAccent": "useAccent.checked = false" in RESET_BLK,
    "useBg": "useBg.checked = false" in RESET_BLK,
    "sameHue": "sameHue" in RESET_BLK,
    "dispmode": 'input[name=dispmode][value="auto"]' in RESET_BLK,
    "cvd": "cvdCheck" in RESET_BLK,
}
check(
    "S9 リセット網羅 (ジャンル指定なし・変種初期値・colorfam/tone/スライダー/use*/sameHue/dispmode/cvd)",
    all(reset_items.values()),
    ", ".join(f"{k}={v}" for k, v in reset_items.items()),
)

# ===========================================================================
# S10 退行防止（構造）
# ===========================================================================
n_schemes = SCHEMES_BLK.count("make: (H, S, L, rng)")
n_tones = len(re.findall(r"\{\s*key:\s*'", TONES_BLK))
n_genre_items = len(re.findall(r"\bh:\s*-?\d", GENRE_BLK))
symbols = ["mulberry32", "toSameHue", "applyContrast", "contrastBadge", "cvdBadge",
           'id="editor"', "edH", "edS", "edL", "edHex", "edCopy", "edReset",
           'id="sameHue"', 'id="dispmode"', 'id="tones"']
missing = [s for s in symbols if s not in HTML]
check(
    "S10 退行防止 (SCHEMES6種・TONES9種・主要シンボル残存・ジャンル9項目不変)",
    n_schemes == 6 and n_tones == 9 and n_genre_items == 9 and not missing,
    f"SCHEMES={n_schemes}(=6), TONES={n_tones}(=9), ジャンル項目={n_genre_items}(=9), "
    f"欠落シンボル={missing or 'なし'}",
)

# ===========================================================================
# S11 版数
# ===========================================================================
# KLK-005 で v1.2 へ更新。v1.1 以上（>=v1.1）を許容し、v1.0 の残存のみ禁止する
title_ok = bool(re.search(r"<title>[^<]*v1\.[1-9][^<]*</title>", HTML))
no_old = "v1.0" not in HTML
check(
    "S11 版数 (<title>にv1.1以上, ファイル内にv1.0が残存しない)",
    title_ok and no_old,
    f"title v1.1以上={title_ok}, v1.0残存なし={no_old}",
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
# Report
# ===========================================================================
print("=" * 78)
print("KLK-004 static acceptance checks (docs/designs/KLK-004.md §9 S群 を正とする)")
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
print("  - M1 金属帯の実測（HEX→HSL換算で帯内・極端スライダー・ガンメタ×ダーク lDark）")
print("  - M2 グラデ参考表示（表示のみ・HEX/微調整/CSS変数コピーは単色）")
print("  - M3 相性の変化（色味切替でサブ・アクセント傾向が変わる）")
print("  - M4 URL往復（コピー→新規タブで同一3案・生成ごとにseed更新・不正値でも動作）")
print("  - M5 ジャンル単一選択（1つのみ・指定なしへ戻せる・サマリ件数）")
print("  - M6 退行なし（トーン・バッジ・微調整・同系色・表示モード・基準/アクセント/背景・リセット）")
sys.exit(1 if failed else 0)
