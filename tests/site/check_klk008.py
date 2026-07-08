#!/usr/bin/env python3
"""
KLK-008 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S12 from
docs/designs/KLK-008.md §9（S群）against the vertical pipeline updated for
生成オプション拡張（カラム6系統・生成時アニメ ON/OFF）:

  縦串① UI          draft-gen/index.html
  縦串③ 生成規約     .claude/skills/draft-generate/templates/DRAFT_RULES.md
  縦串③ スキル定義   .claude/skills/draft-generate/SKILL.md
  縦串② 契約の正     docs/designs/KLK-006.md §4.4
  ゴールデン        tests/fixtures/klk008/sample-full-2col.html
                    tests/fixtures/klk008/sample-anim-off.html
  SPEC/ワイヤー      docs/SPEC.md / docs/wireframes/SCR-001-settings.html
  R-A 回帰(集合)     tests/site/check_klk006.py / check_klk007.py

Source of truth = 設計書 §9（S群）。check_klk006/007.py と同型（正規表現・文字列検索・
波括弧均衡ブロック抽出・tester所有・exit 0/1・Python3標準ライブラリのみ・ネットワーク非使用）。
D群（buildInstruction 動的挙動）は smoke_klk006.node.js が、M群（実生成＋ブラウザ実機）は
tester が手動確認してチケットのログへ記録する。プロダクション成果物・ゴールデンは変更しない。

Run: python3 tests/site/check_klk008.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UI_PATH = os.path.join(ROOT, "draft-gen", "index.html")
RULES_PATH = os.path.join(
    ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md")
SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md")
CONTRACT_PATH = os.path.join(ROOT, "docs", "designs", "KLK-006.md")
SPEC_PATH = os.path.join(ROOT, "docs", "SPEC.md")
WIRE_PATH = os.path.join(ROOT, "docs", "wireframes", "SCR-001-settings.html")
FULL_PATH = os.path.join(ROOT, "tests", "fixtures", "klk008", "sample-full-2col.html")
ANIMOFF_PATH = os.path.join(ROOT, "tests", "fixtures", "klk008", "sample-anim-off.html")
CHECK006_PATH = os.path.join(ROOT, "tests", "site", "check_klk006.py")
CHECK007_PATH = os.path.join(ROOT, "tests", "site", "check_klk007.py")

UI = open(UI_PATH, encoding="utf-8").read()
RULES = open(RULES_PATH, encoding="utf-8").read()
SKILL = open(SKILL_PATH, encoding="utf-8").read()
CONTRACT = open(CONTRACT_PATH, encoding="utf-8").read()
SPEC = open(SPEC_PATH, encoding="utf-8").read()
WIRE = open(WIRE_PATH, encoding="utf-8").read()
FULL = open(FULL_PATH, encoding="utf-8").read()
ANIMOFF = open(ANIMOFF_PATH, encoding="utf-8").read()
CHECK006 = open(CHECK006_PATH, encoding="utf-8").read()
CHECK007 = open(CHECK007_PATH, encoding="utf-8").read()

NEW_COLS = {
    "1col", "2col-full-left", "2col-full-right",
    "2col-body-left", "2col-body-right", "3col",
}

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def js_block(src, marker):
    """marker から始まる最初のブレース均衡ブロックを返す（見つからなければ ""）。
    正規表現の量指定子 {6}/{3} 等は自己完結して均衡するため深さ計算に影響しない。"""
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


BUILD_BLK = js_block(UI, "function buildInstruction(")
COLLABEL_BLK = js_block(UI, "function colLabelOf(")

# ===========================================================================
# S1 UIカラム6系統（REQ-002 / U-1）
# ===========================================================================
col_values = set(re.findall(r'<input type="radio" name="col"[^>]*value="([^"]+)"', UI))
col_radios = re.findall(r'<input type="radio" name="col"[^>]*>', UI)
col_no_checked = all("checked" not in r for r in col_radios)
ck_m = re.search(r"const COLUMN_KEYS\s*=\s*\[([^\]]*)\]", UI)
ck_vals = set(re.findall(r"'([^']+)'", ck_m.group(1))) if ck_m else set()
# colLabelOf の6分岐（switch case が6値を網羅）
label_cases = set(re.findall(r"case '([^']+)':", COLLABEL_BLK))
label_ok = NEW_COLS.issubset(label_cases)
check(
    "S1 UIカラム6系統 (name=col ラジオ6値集合一致・COLUMN_KEYS 同6値・colLabelOf 6分岐・初期checked無)",
    col_values == NEW_COLS and ck_vals == NEW_COLS and label_ok and col_no_checked,
    f"radio値={sorted(col_values)}, COLUMN_KEYS={sorted(ck_vals)}, "
    f"colLabelOf網羅={label_ok}({sorted(label_cases)}), 初期checked無={col_no_checked}",
)

# ===========================================================================
# S2 UIアニメトグル＋buildInstruction（REQ-002拡張 / U-3）
# ===========================================================================
anim_toggle_m = re.search(r'<input[^>]*id="animOn"[^>]*>', UI)
anim_toggle_tag = anim_toggle_m.group(0) if anim_toggle_m else ""
anim_default_on = anim_toggle_tag != "" and "checked" in anim_toggle_tag
build_animation = "animation:" in BUILD_BLK
check(
    "S2 UIアニメトグル+buildInstruction (id=animOn の既定ONトグル存在, buildInstruction が animation: キー出力)",
    anim_toggle_m is not None and anim_default_on and build_animation,
    f"animOnトグル={anim_toggle_m is not None}, 既定checked={anim_default_on}, "
    f"buildInstruction.animation={build_animation}",
)

# ===========================================================================
# S3 アニメOFFゴールデン（U-3 / R-D）
# ===========================================================================
ao_dc_m = re.search(r'data-columns="([^"]+)"', ANIMOFF)
ao_dc = ao_dc_m.group(1) if ao_dc_m else ""
ao_dc_ok = ao_dc in NEW_COLS
# .reveal クラスも、.reveal の opacity:0 CSS も、IntersectionObserver も含まない
ao_no_reveal_class = re.search(r'class="[^"]*\breveal\b', ANIMOFF) is None
ao_no_reveal_css = re.search(r"\.reveal\s*\{[^}]*opacity\s*:\s*0", ANIMOFF, re.S) is None
ao_no_io = "IntersectionObserver" not in ANIMOFF
# 非アニメの印刷CSS（.addr 非表示）は含む
ao_print_blk = js_block(ANIMOFF, "@media print")
ao_print_addr = ".addr" in ao_print_blk and re.search(r"display\s*:\s*none", ao_print_blk) is not None
check(
    "S3 アニメOFFゴールデン (data-columns 新6値・.reveal クラス/opacity:0 CSS/IntersectionObserver いずれも無・@media print で .addr 非表示)",
    ao_dc_ok and ao_no_reveal_class and ao_no_reveal_css and ao_no_io and ao_print_addr,
    f"data-columns={ao_dc or 'なし'}(新6値={ao_dc_ok}), .revealクラス無={ao_no_reveal_class}, "
    f".reveal opacity:0 CSS無={ao_no_reveal_css}, IntersectionObserver無={ao_no_io}, print.addr非表示={ao_print_addr}",
)

# ===========================================================================
# S4 全体2カラムゴールデンの骨格（U-1 / R-C）
# ===========================================================================
f_dc_m = re.search(r'data-columns="([^"]+)"', FULL)
f_dc = f_dc_m.group(1) if f_dc_m else ""
f_dc_full = f_dc in {"2col-full-left", "2col-full-right"}
# .m-layout ブロック（開始タグ以降・.mock 閉じまで）に NAV-01 と HERO-01 の pin が内包される
i_layout = FULL.find('class="m-layout"')
i_mock_end = FULL.rfind("</div>")  # .mock の閉じ付近（body 末尾側）
layout_scope = FULL[i_layout:i_mock_end] if i_layout >= 0 else ""
nav_in_layout = re.search(r'class="pin">\s*NAV-01', layout_scope) is not None
hero_in_layout = re.search(r'class="pin">\s*HERO-01', layout_scope) is not None
has_aside = 'class="m-aside"' in FULL
check(
    "S4 全体2カラム骨格 (data-columns=2col-full-*, .m-layout が NAV-01/HERO-01 を内包, .m-aside 存在)",
    f_dc_full and i_layout >= 0 and nav_in_layout and hero_in_layout and has_aside,
    f"data-columns={f_dc or 'なし'}(full={f_dc_full}), NAV内包={nav_in_layout}, "
    f"HERO内包={hero_in_layout}, .m-aside={has_aside}",
)

# ===========================================================================
# S5 新ゴールデン共通の基本構造（sample-full-2col・REQ-005/006/007/009・NFR-002）
# ===========================================================================
theme_vars = ["--m-main", "--m-nav", "--m-accent", "--m-bg", "--m-text"]
vars_defined = all(re.search(re.escape(v) + r"\s*:\s*[^;]+;", FULL) for v in theme_vars)
vars_referenced = all(re.search(r"var\(\s*" + re.escape(v) + r"\s*\)", FULL) for v in theme_vars)
addr_pins = ["NAV-01", "HERO-01", "ABOUT-01", "MENU-01", "GALLERY-01", "FOOTER-01"]
all_pins = all(re.search(r'class="pin">\s*' + re.escape(p), FULL) for p in addr_pins)
atari_ok = ('class="atari"' in FULL and 'class="desc"' in FULL
            and 'class="kw"' in FULL and re.search(r'検索:\s*<b>', FULL) is not None)
# kw 無フォールバック: .desc を持つが .kw を持たない .atari ブロックが存在
kwless = False
for blk in re.findall(r'<div class="atari">.*?</div>', FULL):
    if 'class="desc"' in blk and 'class="kw"' not in blk:
        kwless = True
        break
todo_ok = 'class="todo"' in FULL and re.search(r'\(要検討[:：]', FULL) is not None
responsive_ok = re.search(r"@media[^{]*max-width\s*:\s*640px", FULL) is not None
anim_on_ok = ("IntersectionObserver" in FULL
              and re.search(r'class="[^"]*\breveal\b', FULL) is not None)
check(
    "S5 新ゴールデン基本構造 (配色5変数定義+var参照・番地6種・アタリa方式(kw無フォールバック含む)・.todo・@media640・アニメ)",
    (vars_defined and vars_referenced and all_pins and atari_ok and kwless
     and todo_ok and responsive_ok and anim_on_ok),
    f"5変数定義={vars_defined}, var参照={vars_referenced}, 番地6種={all_pins}, "
    f"アタリa方式={atari_ok}, kw無={kwless}, .todo={todo_ok}, @media640={responsive_ok}, アニメ={anim_on_ok}",
)

# ===========================================================================
# S6 規約 §8 六系統グリッド＋エイリアス（U-1 / U-2 / R-C）
# ===========================================================================
rules_all_cols = all(v in RULES for v in NEW_COLS)
rules_full_includes = ("全体2カラム" in RULES and "NAV/HERO" in RULES and "内包" in RULES)
rules_alias = (("2col-sub-left" in RULES and "2col-body-left" in RULES)
               and ("2col-sub-right" in RULES and "2col-body-right" in RULES)
               and ("エイリアス" in RULES or "正規化" in RULES))
check(
    "S6 規約§8 六系統+エイリアス (DRAFT_RULES に6値グリッド骨格・全体2カラム=NAV/HERO内包・旧2col-sub-*→2col-body-* 正規化)",
    rules_all_cols and rules_full_includes and rules_alias,
    f"6値記述={rules_all_cols}, 全体2カラムNAV/HERO内包={rules_full_includes}, エイリアス正規化={rules_alias}",
)

# ===========================================================================
# S7 規約 §7 アニメON/OFF分岐（U-3）
# ===========================================================================
rules_anim_field = "output.animation" in RULES
rules_anim_off = (re.search(r"output\.animation\s*===\s*false", RULES) is not None
                  and "IntersectionObserver" in RULES
                  and (".reveal" in RULES))
rules_anim_immediate = ("即時全表示" in RULES or "完全表示" in RULES)
rules_anim_default = ("既定" in RULES and "true" in RULES)
check(
    "S7 規約§7 アニメON/OFF分岐 (output.animation===false で .reveal/IntersectionObserver を出さず即時全表示・既定true)",
    rules_anim_field and rules_anim_off and rules_anim_immediate and rules_anim_default,
    f"output.animation記述={rules_anim_field}, false分岐={rules_anim_off}, "
    f"即時全表示={rules_anim_immediate}, 既定true={rules_anim_default}",
)

# ===========================================================================
# S8 受付チェックの正規化・既定補完（U-2 / U-4）
# ===========================================================================
skill_version = (re.search(r"version.{0,6}(が|は).{0,6}1", SKILL) is not None
                 or re.search(r"version[^\n]*1", SKILL) is not None) and "不変" in SKILL
skill_alias = (("2col-sub-left" in SKILL and "2col-body-left" in SKILL)
               and ("2col-sub-right" in SKILL and "2col-body-right" in SKILL)
               and ("正規化" in SKILL))
skill_anim_default = ("output.animation" in SKILL
                      and ("未指定" in SKILL) and "true" in SKILL)
check(
    "S8 受付チェック (SKILL.md に version==1不変・旧2col-sub-*→2col-body-* 正規化・output.animation 未指定時 true 補完)",
    skill_version and skill_alias and skill_anim_default,
    f"version==1不変={skill_version}, カラム正規化={skill_alias}, animation既定補完={skill_anim_default}",
)

# ===========================================================================
# S9 スキーマ契約（KLK-006 §4.4）の更新（U-3 / U-4・契約の正）
# ===========================================================================
# §4.4 のフィールド表: layout.columns 行が新6値、output に animation 行(boolean・既定true)、version は 1
i_sec44 = CONTRACT.find("### 4.4")
sec44 = CONTRACT[i_sec44:] if i_sec44 >= 0 else CONTRACT
col_row_m = re.search(r"`layout\.columns`[^\n]*", sec44)
col_row = col_row_m.group(0) if col_row_m else ""
col_row_ok = all(v in col_row for v in NEW_COLS)
anim_row_m = re.search(r"`output\.animation`[^\n]*", sec44)
anim_row = anim_row_m.group(0) if anim_row_m else ""
anim_row_ok = anim_row != "" and "boolean" in anim_row and "true" in anim_row
version_row_ok = re.search(r"`version`[^\n]*整数\s*`?1`?", sec44) is not None
check(
    "S9 スキーマ契約 (KLK-006 §4.4: layout.columns 新6値・output.animation boolean既定true 行・version 整数1)",
    col_row_ok and anim_row_ok and version_row_ok,
    f"columns6値行={col_row_ok}, animation行={anim_row_ok}, version:1据置={version_row_ok}",
)

# ===========================================================================
# S10 R-A 集合の同期（既存S群更新の確認）（R-A）
# ===========================================================================
# check_klk006.py S11 expected_cols が新6値
c6_expected_m = re.search(r"expected_cols\s*=\s*\{([^}]*)\}", CHECK006)
c6_expected = set(re.findall(r'"([^"]+)"', c6_expected_m.group(1))) if c6_expected_m else set()
c6_cols_ok = c6_expected == NEW_COLS
# check_klk006.py S9 schema_keys に "animation:" が含まれる
c6_schema_m = re.search(r"schema_keys\s*=\s*\[([^\]]*)\]", CHECK006)
c6_schema = c6_schema_m.group(1) if c6_schema_m else ""
c6_anim_ok = '"animation:"' in c6_schema
# check_klk007.py S8 の許容集合が新6値
c7_all_cols = all(v in CHECK007 for v in ("2col-full-left", "2col-full-right",
                                          "2col-body-left", "2col-body-right"))
c7_no_sub = "2col-sub" not in CHECK007
check(
    "S10 R-A集合同期 (check_klk006 S11 expected_cols 新6値・S9 schema_keys に animation:・check_klk007 S8 許容集合 新6値)",
    c6_cols_ok and c6_anim_ok and c7_all_cols and c7_no_sub,
    f"klk006 S11 6値={c6_cols_ok}({sorted(c6_expected)}), klk006 S9 animation={c6_anim_ok}, "
    f"klk007 S8 新6値={c7_all_cols}, klk007 旧値無={c7_no_sub}",
)

# ===========================================================================
# S11 SPEC・ワイヤー更新（REQ-002拡張）
# ===========================================================================
req002_m = re.search(r"\| REQ-002 \|[^\n]*", SPEC)
req002 = req002_m.group(0) if req002_m else ""
spec_six = ("全体2カラム" in req002 and "本文のみ2カラム" in req002
            and "1カラム" in req002 and "3カラム" in req002)
spec_anim = ("アニメーション" in req002 and ("ON/OFF" in req002 or "既定ON" in req002))
wire_cards = len(re.findall(r'<div class="colcard"', WIRE)) == 6
wire_anim = re.search(r"アニメーション", WIRE) is not None and \
    re.search(r'<input type="checkbox"[^>]*checked>[^<]*アニメ', WIRE) is not None
check(
    "S11 SPEC・ワイヤー (REQ-002 が6系統+生成時アニメON/OFF既定ON, ワイヤー .colcard 6枚+アニメトグル)",
    spec_six and spec_anim and wire_cards and wire_anim,
    f"SPEC6系統={spec_six}, SPECアニメ={spec_anim}, colcard6枚={wire_cards}, ワイヤーアニメトグル={wire_anim}",
)

# ===========================================================================
# S12 セキュリティ/依存（S-SEC・NFR-005 / NFR-004 / REQ-011）
# ===========================================================================
_ALLOW_HOSTS = ("www.w3.org", "example.com", "example.org", "example.net")


def _host(url):
    m = re.match(r"https?://([^/\s\"')]+)", url)
    return m.group(1).lower() if m else ""


secret_re = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
sec_detail = {}
sec_ok = True
for label, txt in (("sample-full-2col", FULL), ("sample-anim-off", ANIMOFF)):
    ext_urls = [m for m in re.findall(r'https?://[^\s"\')（]+', txt)
                if _host(m) not in _ALLOW_HOSTS]
    secret_hits = [ln for ln, line in enumerate(txt.splitlines(), 1)
                   if secret_re.search(line)]
    placeholder_marked = ("プレースホルダ" in txt or "実在の顧客" in txt or "サンプル" in txt)
    ok = (not ext_urls) and (not secret_hits) and placeholder_marked
    sec_ok = sec_ok and ok
    sec_detail[label] = f"外部URL={ext_urls or 0}/秘密={secret_hits or 0}/プレースホルダ明記={placeholder_marked}"
check(
    "S12 セキュリティ/依存 (新ゴールデン2ファイル: 外部URL0[w3.org/example.*除外]・秘密情報0・プレースホルダ明記)",
    sec_ok,
    "; ".join(f"{k}: {v}" for k, v in sec_detail.items()),
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-008 static acceptance checks (docs/designs/KLK-008.md §9 S群 を正とする)")
print("対象: draft-gen/index.html / DRAFT_RULES.md / SKILL.md / KLK-006.md §4.4 /")
print("      SPEC / SCR-001 ワイヤー / fixtures/klk008/*.html / check_klk006・007(R-A)")
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
print("D群（smoke_klk006.node.js で動的検証・node不在時skip）:")
print("  - D1 buildInstruction 新enum透過（新6値・COLUMN_KEYS.indexOf>=0・旧値入力を D6/D7 から除去）")
print("  - D2 buildInstruction animation 既定（未指定→boolean true・false 透過）")
print("  - D3 既存 D群回帰（KLK-006 D1-D8 が新仕様で全緑・入力非破壊）")
print()
print("M群（環境制約で静的検証外 = tester が /draft-generate 実行 + ブラウザで手動確認）:")
print("  - M1 UI6系統＋アニメトグル（図解付き単一選択・全体/本文の差が図で分かる・狭幅で崩れない・指示書に反映）")
print("  - M2 全体2カラム生成（2col-full-* でサイドバーが HERO の横に回る全高2カラム）")
print("  - M3 本文のみ2カラム生成（2col-body-* で FV 全幅＋その下だけ2カラム＝税理士事務所ラフ相当）")
print("  - M4 旧値後方互換（旧 2col-sub-right の version:1 JSON が 2col-body-right として再現・受付停止しない）")
print("  - M5 アニメON/OFF反映（true=スクロールでフェードイン / false=初期から全表示・両者とも印刷で番地等非表示）")
sys.exit(1 if failed else 0)
