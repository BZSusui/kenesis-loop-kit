#!/usr/bin/env python3
"""
KLK-027 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S9 from
docs/designs/KLK-027.md §9（S群）against セクション見出し・リード文の事前指定
（sectionOptions.{KEY}.heading / .lead）:

  SCR-001 ビルダー   draft-gen/index.html（sectionCopyList/renderSectionCopyRows・collectInput・buildInstruction）
  ブリッジ           draft-gen/bridge.py（sectionOptions ループ内 heading/lead 検証）
  生成規約           DRAFT_RULES.md（§4.2）/ スキル定義 SKILL.md（手順3）
  ゴールデン         tests/fixtures/klk027/index.html + instruction.json
                     （ABOUT=heading+lead / MENU=headingのみ / GALLERY=無指定）

Source of truth = 設計書 §9（S群）。check_klk024 と同型（正規表現・文字列検索・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。K群は smoke_klk027.node.js、D群/M群は wrapper と人間。

Run: python3 tests/site/check_klk027.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import html as html_mod
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FX = os.path.join(ROOT, "tests", "fixtures", "klk027")
IDX = open(os.path.join(FX, "index.html"), encoding="utf-8").read()
INSTR = json.load(open(os.path.join(FX, "instruction.json"), encoding="utf-8"))
SCRSRC = open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
BR = open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def section_block(html, key):
    """pin {KEY}-01 の位置から次の pin（または body 終端）までのブロック文字列。"""
    m = re.search(r'%s-01</span>(.*?)(?:class="pin"|</body>)' % re.escape(key), html, re.S)
    return m.group(1) if m else ""


# S1 SCR-001 UI（sectionCopyList・renderSectionCopyRows・値退避→復元・初期描画）
u_box = 'id="sectionCopyList"' in SCRSRC and 'id="sectionCopyBox"' in SCRSRC
u_fn = "function renderSectionCopyRows()" in SCRSRC
u_keep = re.search(r"var prev = \{\};", SCRSRC) is not None \
    and "prev[row.dataset.secKey] = { heading:" in SCRSRC \
    and "if (prev[key]) { h.value = prev[key].heading || ''; l.value = prev[key].lead || ''; }" in SCRSRC
u_init = "renderSectionCopyRows();   // 初期表示" in SCRSRC \
    and re.search(r"el\.addEventListener\('change', function \(\) \{ renderSectionCopyRows\(\); render\(\); \}\);", SCRSRC) is not None
check("S1 SCR-001 UI (sectionCopyList/renderSectionCopyRows・値退避→復元・チェック変化で再描画＋初期描画)",
      u_box and u_fn and u_keep and u_init,
      f"box={u_box}, fn={u_fn}, 値保持={u_keep}, 再描画/初期={u_init}")

# S2 純ロジック（buildInstruction: 選択セクションのみ・sanitize・指定時のみキー）
p_gate = "const texts = (input.sectionTexts && typeof input.sectionTexts === 'object') ? input.sectionTexts : {};" in SCRSRC
p_loop = "sections.forEach(function (key) {" in SCRSRC
p_heading = re.search(r"sanitizeCopy\(t\.heading, 40\)\.replace\(/\\n/g, ' '\)\.trim\(\)", SCRSRC) is not None
p_lead = "sanitizeCopy(t.lead, 200)" in SCRSRC
p_cond = "if (heading || lead) {" in SCRSRC and "sectionOptions[key] || (sectionOptions[key] = {})" in SCRSRC
check("S2 純ロジック (sectionTexts→選択セクションのみ・heading 1行40字/lead 改行可200字・指定時のみキー出力)",
      p_gate and p_loop and p_heading and p_lead and p_cond,
      f"gate={p_gate}, loop={p_loop}, heading整形={p_heading}, lead整形={p_lead}, 条件付き={p_cond}")

# S3 collectInput（[data-sec-key] 行から収集）
c_ok = "querySelectorAll('#sectionCopyList [data-sec-key]')" in SCRSRC \
    and "sectionTexts[row.dataset.secKey] = { heading: h ? h.value : '', lead: l ? l.value : '' };" in SCRSRC \
    and "sectionTexts: sectionTexts," in SCRSRC
check("S3 collectInput ([data-sec-key] 行から heading/lead を収集し input.sectionTexts へ)",
      c_ok, f"収集={c_ok}")

# S4 DRAFT_RULES §4.2
r_sec = "### 4.2" in RULES and "sectionOptions.{KEY}.heading" in RULES.replace("`", "") \
    or ("### 4.2" in RULES and "heading" in RULES and "lead" in RULES)
r_h2 = "見出し（`.m-sec h2` 等）にそのまま" in RULES
r_lead = "sec-lead" in RULES and "`\\n`→`<br>`" in RULES.replace("​", "") or ("sec-lead" in RULES and "<br>" in RULES)
r_omit = "`.sec-lead` 自体を出力しない" in RULES
r_esc = RULES.count("HTMLエスケープ") >= 2  # §4.1 と §4.2 の双方
r_shared = "全案同じ" in RULES
r_ignore = "`sections` に無い KEY への指定は無視" in RULES
check("S4 DRAFT_RULES §4.2 (h2そのまま・lead→.sec-lead・<br>・無指定は出さない・エスケープ・全案共通・sections外無視)",
      r_sec and r_h2 and r_lead and r_omit and r_esc and r_shared and r_ignore,
      f"§4.2={r_sec}, h2={r_h2}, sec-lead={r_lead}, 無指定省略={r_omit}, esc={r_esc}, 共通={r_shared}, 無視={r_ignore}")

# S5 SKILL 手順3
k_ok = "sectionOptions.{KEY}.heading" in SKILL.replace("`", "") or ("sectionOptions" in SKILL and "sec-lead" in SKILL)
k_ref = "§4.2" in SKILL
check("S5 SKILL 手順3 (セクション文言優先・.sec-lead・§4.2 参照)",
      k_ok and k_ref, f"記述={k_ok}, 参照={k_ref}")

# S6 bridge（heading/lead の存在時のみ検証）
b_heading = 'heading = opt.get("heading")' in BR and "heading が不正です(40字以内・1行・制御文字不可・空不可)" in BR
b_lead = 'lead = opt.get("lead")' in BR and "lead が不正です(200字以内・改行以外の制御文字不可・空不可)" in BR
b_scope = "全セクション共通の任意キー" in BR
check("S6 bridge validate_instruction (heading≤40/1行・lead≤200/改行可 を存在時のみ・全KEY共通)",
      b_heading and b_lead and b_scope, f"heading={b_heading}, lead={b_lead}, 全KEY={b_scope}")

# S7 ゴールデン忠実反映
opts = INSTR.get("sectionOptions", {})
ab = section_block(IDX, "ABOUT")
mn = section_block(IDX, "MENU")
gl = section_block(IDX, "GALLERY")
want_ab_h = html_mod.escape(opts.get("ABOUT", {}).get("heading", ""))
want_ab_l = "<br>".join(html_mod.escape(x) for x in opts.get("ABOUT", {}).get("lead", "").split("\n"))
want_mn_h = html_mod.escape(opts.get("MENU", {}).get("heading", ""))
ab_h = re.search(r"<h2>(.*?)</h2>", ab, re.S)
mn_h = re.search(r"<h2>(.*?)</h2>", mn, re.S)
ab_l = re.search(r'<p class="sec-lead">(.*?)</p>', ab, re.S)
s7_ab = ab_h is not None and ab_h.group(1).strip() == want_ab_h \
    and ab_l is not None and ab_l.group(1).strip() == want_ab_l
# 「.sec-lead が無い」は実要素（<p class="sec-lead"）で判定する（説明コメント内の文字列に反応しない）
s7_mn = mn_h is not None and mn_h.group(1).strip() == want_mn_h and '<p class="sec-lead"' not in mn
s7_gl = '<p class="sec-lead"' not in gl
check("S7 ゴールデン忠実反映 (ABOUT h2/lead 一致・MENU h2一致+lead無し・GALLERY(無指定) lead無し)",
      s7_ab and s7_mn and s7_gl,
      f"ABOUT={s7_ab}, MENU={s7_mn}, GALLERY={s7_gl}")

# S8 ゴールデン健全性＋セキュリティ
pins = set(re.findall(r'class="pin">([A-Z0-9-]+)<', IDX))
want_pins = {"NAV-01", "MV-01", "ABOUT-01", "MENU-01", "GALLERY-01", "CTA-01", "FOOTER-01"}
g_print = "@media print" in IDX
g_atari = 'class="atari"' in IDX and 'class="desc"' in IDX
g_solo = not (re.search(r'<link\b[^>]*rel=["\']?stylesheet', IDX, re.I)
              or re.search(r'<script\b[^>]*\bsrc=', IDX, re.I)
              or re.search(r'fonts\.(googleapis|gstatic)\.com|cdn\.|unpkg\.com|jsdelivr', IDX, re.I)
              or re.search(r'<img\b[^>]*\bsrc=["\']?https?:', IDX, re.I))
_ALLOW = ("www.w3.org", "example.com", "example.org", "example.net")


def _host(u):
    m = re.match(r"https?://([^/\s\"')]+)", u)
    return m.group(1).lower() if m else ""


ext = [u for u in re.findall(r'https?://[^\s"\')（]+', IDX) if _host(u) not in _ALLOW]
secret_re = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
sec = [ln for ln, line in enumerate(IDX.splitlines(), 1) if secret_re.search(line)]
ph = ("プレースホルダ" in IDX or "実在の顧客" in IDX or "サンプル" in IDX)
check("S8 ゴールデン健全性 (番地7種・print・アタリa・依存0・外部URL0・秘密0・PH明記)",
      pins == want_pins and g_print and g_atari and g_solo and (not ext) and (not sec) and ph,
      f"番地={pins == want_pins}, print={g_print}, アタリ={g_atari}, 依存0={g_solo}, 外部URL={ext or 0}, 秘密={sec or 0}, PH={ph}")

# S9 既存回帰（§4.1・CTA検証・§4本則）
r_klk024 = "### 4.1" in RULES and "copy.mvCatch" in RULES
b_cta = "sectionOptions.CTA.purpose" in BR and "sectionOptions.CTA.label" in BR
r_base = "ダミーテキスト禁止" in RULES and "(要検討:" in RULES
check("S9 既存回帰保持 (§4.1 MVコピー・bridge CTA purpose/label 検証・§4 本則が不変)",
      r_klk024 and b_cta and r_base, f"§4.1={r_klk024}, CTA検証={b_cta}, §4本則={r_base}")

# Report
print("=" * 78)
print("KLK-027 static acceptance checks (docs/designs/KLK-027.md §9 S群 を正とする)")
print("対象: draft-gen/index.html・bridge.py / DRAFT_RULES.md・SKILL.md / fixtures/klk027/*")
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
print("K群（smoke_klk027.node.js）: 無指定→従来形 / 選択のみ / 整形(1行化・上限) / CTA併用 / 空→省略・入力非破壊")
print("D群（test_palette_klk027.py）: Quality Gate 全緑（回帰なし）")
print("M群（人間が実機確認）: 入力行の増減追従と値保持 / 指定文言がそのまま出る / variants:3 全案同文言")
sys.exit(1 if failed else 0)
