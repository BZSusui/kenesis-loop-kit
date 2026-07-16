#!/usr/bin/env python3
"""
KLK-024 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S9 from
docs/designs/KLK-024.md §9（S群）against MVキャッチコピー・リード文の事前指定（copy.mvCatch / copy.mvLead）:

  SCR-001 ビルダー   draft-gen/index.html（mvCatch/mvLead textarea・sanitizeCopy・buildInstruction 条件付き copy）
  ブリッジ           draft-gen/bridge.py（validate_instruction: copy 存在時のみ検証・COPY_MAX）
  生成規約           .claude/skills/draft-generate/templates/DRAFT_RULES.md（§4.1）
  スキル定義         .claude/skills/draft-generate/SKILL.md（手順3 仮文言 bullet）
  ゴールデン         tests/fixtures/klk024/index.html + instruction.json（2行キャッチ<br>の忠実反映）

Source of truth = 設計書 §9（S群）。check_klk022/023.py と同型（正規表現・文字列検索・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。K群（動的スモーク）は smoke_klk024.node.js、
D群/M群は tests/test_palette_klk024.py と tester 手動。

Run: python3 tests/site/check_klk024.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import html as html_mod
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FX = os.path.join(ROOT, "tests", "fixtures", "klk024")
IDX = open(os.path.join(FX, "index.html"), encoding="utf-8").read()
INSTR = json.load(open(os.path.join(FX, "instruction.json"), encoding="utf-8"))
SCRSRC = open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
BR = open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def scr_logic_slice():
    a = SCRSRC.find("const COLUMN_KEYS")
    b = SCRSRC.find("function render()")
    return SCRSRC[a:b] if (a >= 0 and b > a) else ""


LOGIC = scr_logic_slice()

# ===========================================================================
# S1 SCR-001 UI（mvCatch/mvLead textarea・任意・注記）
# ===========================================================================
ui_catch = re.search(r'<textarea[^>]*id="mvCatch"', SCRSRC) is not None
ui_lead = re.search(r'<textarea[^>]*id="mvLead"', SCRSRC) is not None
ui_note = ("未入力の場合" in SCRSRC and "全案共通" in SCRSRC)
check("S1 SCR-001 UI (mvCatch/mvLead の textarea・未入力=AI提案/全案共通の注記)",
      ui_catch and ui_lead and ui_note,
      f"mvCatch={ui_catch}, mvLead={ui_lead}, 注記={ui_note}")

# ===========================================================================
# S2 純ロジック（sanitizeCopy が render() 前・buildInstruction が条件付き copy 出力）
# ===========================================================================
p_fn = "function sanitizeCopy" in LOGIC
p_cond = re.search(r"if \(mvCatch \|\| mvLead\) \{\s*\n\s*out\.copy = \{\};", SCRSRC) is not None
p_caps = "sanitizeCopy(input.mvCatch, 60)" in SCRSRC and "sanitizeCopy(input.mvLead, 200)" in SCRSRC
check("S2 純ロジック (sanitizeCopy が render()前・buildInstruction が指定時のみ copy 出力・上限60/200)",
      p_fn and p_cond and p_caps,
      f"sanitizeCopy={p_fn}, 条件付きcopy={p_cond}, 上限={p_caps}")

# ===========================================================================
# S3 DRAFT_RULES §4.1（そのまま反映・\n→<br>・エスケープ・全案共通・無指定はAI提案）
# ===========================================================================
r_sec = "### 4.1" in RULES and "copy.mvCatch" in RULES and "copy.mvLead" in RULES
r_verbatim = "そのまま" in RULES and ("言い換え" in RULES)
r_br = "`<br>` に変換" in RULES or "<br>` に変換" in RULES
r_escape = "HTMLエスケープ" in RULES and ("textContent" in RULES)
r_shared = "全案同じ copy" in RULES or ("copy" in RULES and "全案共通" in RULES)
r_fallback = "無指定" in RULES and "後方互換" in RULES
check("S3 DRAFT_RULES §4.1 (そのまま反映・\\n→<br>・HTMLエスケープ・全案共通・無指定はAI提案/後方互換)",
      r_sec and r_verbatim and r_br and r_escape and r_shared and r_fallback,
      f"§4.1={r_sec}, 忠実={r_verbatim}, <br>変換={r_br}, エスケープ={r_escape}, 全案共通={r_shared}, 後方互換={r_fallback}")

# ===========================================================================
# S4 SKILL 手順3（指定コピー優先）
# ===========================================================================
k_ok = ("copy.mvCatch" in SKILL and "copy.mvLead" in SKILL
        and "そのまま" in SKILL and "<br>" in SKILL and "§4.1" in SKILL)
check("S4 SKILL 手順3 (指定コピー優先・<br>行組保持・§4.1参照)", k_ok, f"記述={k_ok}")

# ===========================================================================
# S5 bridge（copy 存在時のみ検証・未知キー拒否・上限・改行以外の制御文字拒否）
# ===========================================================================
b_const = 'COPY_MAX = {"mvCatch": 60, "mvLead": 200}' in BR
b_gate = 'copy = obj.get("copy")' in BR and "if copy is not None:" in BR
b_unknown = "copy に未対応のキーがあります" in BR
b_ctrl = 'ord(ch) < 32 and ch != "\\n"' in BR
check("S5 bridge validate_instruction (copy 存在時のみ・COPY_MAX 60/200・未知キー拒否・改行以外の制御文字拒否)",
      b_const and b_gate and b_unknown and b_ctrl,
      f"COPY_MAX={b_const}, 存在時のみ={b_gate}, 未知キー={b_unknown}, 制御文字={b_ctrl}")

# ===========================================================================
# S6 ゴールデン忠実反映（catch: エスケープ+改行<br>・lead: そのまま）
# ===========================================================================
copy_in = INSTR.get("copy", {})
want_catch = "<br>".join(html_mod.escape(line) for line in copy_in.get("mvCatch", "").split("\n"))
want_lead = html_mod.escape(copy_in.get("mvLead", ""))
m_catch = re.search(r'<h1 class="catch">(.*?)</h1>', IDX, re.S)
m_lead = re.search(r'<p class="lead">(.*?)</p>', IDX, re.S)
got_catch = m_catch.group(1).strip() if m_catch else ""
got_lead = m_lead.group(1).strip() if m_lead else ""
s6_catch = bool(want_catch) and got_catch == want_catch
s6_lead = bool(want_lead) and got_lead == want_lead
s6_two_lines = "<br>" in got_catch  # 2行キャッチ（改行保持の実例）
check("S6 ゴールデン忠実反映 (instruction.copy が .catch にエスケープ+<br>で一致・.lead に一致・2行組)",
      s6_catch and s6_lead and s6_two_lines,
      f"catch一致={s6_catch}, lead一致={s6_lead}, 2行<br>={s6_two_lines}")

# ===========================================================================
# S7 ゴールデン健全性（番地・print・アタリa・依存0）
# ===========================================================================
pins = set(re.findall(r'class="pin">([A-Z0-9-]+)<', IDX))
want_pins = {"NAV-01", "MV-01", "ABOUT-01", "MENU-01", "GALLERY-01", "FOOTER-01"}
g_print = "@media print" in IDX
g_atari = 'class="atari"' in IDX and 'class="desc"' in IDX
g_solo = not (re.search(r'<link\b[^>]*rel=["\']?stylesheet', IDX, re.I)
              or re.search(r'<script\b[^>]*\bsrc=', IDX, re.I)
              or re.search(r'fonts\.(googleapis|gstatic)\.com|cdn\.|unpkg\.com|jsdelivr', IDX, re.I)
              or re.search(r'<img\b[^>]*\bsrc=["\']?https?:', IDX, re.I))
check("S7 ゴールデン健全性 (番地6種・@media print・アタリa方式・外部依存0)",
      pins == want_pins and g_print and g_atari and g_solo,
      f"番地={pins == want_pins}, print={g_print}, アタリ={g_atari}, 依存0={g_solo}")

# ===========================================================================
# S8 セキュリティ/依存
# ===========================================================================
_ALLOW = ("www.w3.org", "example.com", "example.org", "example.net")


def _host(u):
    m = re.match(r"https?://([^/\s\"')]+)", u)
    return m.group(1).lower() if m else ""


secret_re = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
ext = [u for u in re.findall(r'https?://[^\s"\')（]+', IDX) if _host(u) not in _ALLOW]
sec = [ln for ln, line in enumerate(IDX.splitlines(), 1) if secret_re.search(line)]
ph = ("プレースホルダ" in IDX or "実在の顧客" in IDX or "サンプル" in IDX)
check("S8 セキュリティ/依存 (外部URL0[w3.org/example.*除外]・秘密0・プレースホルダ明記)",
      (not ext) and (not sec) and ph,
      f"外部URL={ext or 0}, 秘密={sec or 0}, PH={ph}")

# ===========================================================================
# S9 既存回帰（§4 本則の保持・additive）
# ===========================================================================
r_base = ("ダミーテキスト禁止" in RULES and "lorem ipsum" in RULES
          and "業種" in RULES and "(要検討:" in RULES)
check("S9 既存回帰保持 (§4 本則: ダミーテキスト禁止・業種/テイストから生成・(要検討:) が残る)",
      r_base, f"§4本則={r_base}")

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-024 static acceptance checks (docs/designs/KLK-024.md §9 S群 を正とする)")
print("対象: draft-gen/index.html・bridge.py / DRAFT_RULES.md・SKILL.md / fixtures/klk024/*")
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
print("K群（smoke_klk024.node.js）: 無指定→copyキーなし / 片方のみ / 整形(\\r\\n正規化・制御文字除去・上限) / 入力非破壊")
print("D群（test_palette_klk024.py）: Quality Gate 全緑（回帰なし）")
print("M群（tester 手動・ブラウザ）: 2行キャッチが指定どおり出る / 未入力はAI提案 / variants:3 で全案同文言")
sys.exit(1 if failed else 0)
