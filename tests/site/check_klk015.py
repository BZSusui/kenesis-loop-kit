#!/usr/bin/env python3
"""
KLK-015 acceptance-condition checker (static / core / no browser・no network).

Verifies the statically-checkable acceptance conditions S1-S7 from
docs/designs/KLK-015.md §9（S群）against 番地ラベル HERO-01 → MV-01
（人間向け名称「メインビジュアル」）へのリネーム:

  生成規約(静的検査)      .claude/skills/draft-generate/templates/DRAFT_RULES.md
  生成スキル(静的検査)    .claude/skills/draft-generate/SKILL.md
  再生成スキル(静的検査)  .claude/skills/draft-regenerate/SKILL.md
  ブリッジ(純関数 import) draft-gen/bridge.py
  ゴールデン9件(静的検査) tests/fixtures/klk007|008|009|012/*.html

Source of truth = 設計書 KLK-015 §9（S群 S1-S7）。check_klk012 と同型（import 単体＋
正規表現・文字列検索・tester所有・exit 0/1・Python3標準ライブラリのみ・ネットワーク非使用）。
bridge.py は `if __name__ == "__main__"` ガードでサーバ起動を隔離しているため import で
副作用（bind/実行）は起きない。

**検出ルール（§3.1）**: 番地ラベルの機械検査対象は **リテラル `HERO-01`（大文字・
ハイフン・2桁）トークンのみ**。CSSクラス `.m-hero`/`.hero-cta`（②）と素の「HERO」
（③一般語・「NAV/HERO」等）は `HERO-01` を部分文字列として含まないため自動的に検査対象外。

D群（discover 回帰全緑）は tests/test_palette_klk015.py が、M群（実生成＋compare.html＋
任意の再生成＋SPEC/ワイヤー目視）は tester/人間が手動確認しチケットのログへ記録する。
プロダクション成果物（DRAFT_RULES / SKILL×2 / bridge.py / ゴールデン）は変更しない。

Run: python3 tests/site/check_klk015.py
Exit code 0 = all static/core checks pass, 1 = at least one fail.
"""
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_PATH = os.path.join(ROOT, "draft-gen", "bridge.py")
DRAFT_RULES_PATH = os.path.join(
    ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md")
GEN_SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md")
REGEN_SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-regenerate", "SKILL.md")

FIX = os.path.join(ROOT, "tests", "fixtures")
# ゴールデン9件（§4.1）: 8件は pin、compare-regen.html は option。
GOLDEN_PIN = [
    os.path.join(FIX, "klk007", "sample-draft.html"),
    os.path.join(FIX, "klk008", "sample-anim-off.html"),
    os.path.join(FIX, "klk008", "sample-full-2col.html"),
    os.path.join(FIX, "klk009", "index-a.html"),
    os.path.join(FIX, "klk009", "index-b.html"),
    os.path.join(FIX, "klk009", "index-c.html"),
    os.path.join(FIX, "klk012", "index-a-before.html"),
    os.path.join(FIX, "klk012", "index-a-after.html"),
]
GOLDEN_OPTION = os.path.join(FIX, "klk012", "compare-regen.html")
SAMPLE_FULL_2COL = os.path.join(FIX, "klk008", "sample-full-2col.html")

DRAFT_RULES = open(DRAFT_RULES_PATH, encoding="utf-8").read()
GEN_SKILL = open(GEN_SKILL_PATH, encoding="utf-8").read()
REGEN_SKILL = open(REGEN_SKILL_PATH, encoding="utf-8").read()

# bridge.py を import（__main__ ガードで副作用なし＝サーバは起動しない）。
_spec = importlib.util.spec_from_file_location("klk015_bridge", BRIDGE_PATH)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)

# リテラル番地ラベル HERO-01 トークン（2桁固定・末尾を数字境界で締める）。
HERO01_RE = re.compile(r"HERO-01(?!\d)")


def _read(path):
    return open(path, encoding="utf-8").read()


def _hero01_count(txt):
    return len(HERO01_RE.findall(txt))


results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ===========================================================================
# S1 番地表（§2）が MV-01（確定リネーム仕様 §3.0）
# ===========================================================================
s1_new = re.search(r"\|\s*`?MV-01`?\s*\|\s*メインビジュアル\s*\|", DRAFT_RULES) is not None
s1_old_row = re.search(r"\|\s*`?HERO-01`?\s*\|", DRAFT_RULES) is not None
s1 = s1_new and not s1_old_row
check(
    "S1 番地表§2が MV-01 (DRAFT_RULES §2 に `| MV-01 | メインビジュアル |` が存在し `| HERO-01 |` 行が非存在)",
    s1,
    f"MV-01行存在={s1_new}, HERO-01行残存={s1_old_row}",
)

# ===========================================================================
# S2 生成例 pin（§2）が MV-01（§3.0）
# ===========================================================================
s2_new = '<span class="pin">MV-01</span>' in DRAFT_RULES
s2_old = '<span class="pin">HERO-01</span>' in DRAFT_RULES
s2 = s2_new and not s2_old
check(
    "S2 生成例pin §2が MV-01 (DRAFT_RULES 生成例に <span class=\"pin\">MV-01</span> があり pin として HERO-01 が無い)",
    s2,
    f"pin MV-01存在={s2_new}, pin HERO-01残存={s2_old}",
)

# ===========================================================================
# S3 §13 option 列挙が MV-01（§3.0 / U2）
# ===========================================================================
s3_seq = re.search(
    r"`NAV-01`\s*/\s*`MV-01`\s*/\s*`ABOUT-01`\s*/\s*`MENU-01`"
    r"\s*/\s*`GALLERY-01`\s*/\s*`FOOTER-01`", DRAFT_RULES) is not None
s3_old = "`HERO-01`" in DRAFT_RULES
s3 = s3_seq and not s3_old
check(
    "S3 §13 option列挙が MV-01 (DRAFT_RULES §13 番地 select 列挙が `NAV-01`/`MV-01`/… を含み `HERO-01` を含まない)",
    s3,
    f"MV-01列挙={s3_seq}, `HERO-01`残存={s3_old}",
)

# ===========================================================================
# S4 生成規約・スキルに番地ラベル HERO-01 非残存（②③除外）（U1 / §3.1）
# ===========================================================================
scan = {
    "DRAFT_RULES.md": DRAFT_RULES,
    "draft-generate/SKILL.md": GEN_SKILL,
    "draft-regenerate/SKILL.md": REGEN_SKILL,
}
s4_counts = {n: _hero01_count(t) for n, t in scan.items()}
s4 = all(c == 0 for c in s4_counts.values())
check(
    "S4 生成規約・スキルに番地ラベル HERO-01 非残存 (DRAFT_RULES / draft-generate SKILL / draft-regenerate SKILL に "
    "リテラル HERO-01 が 0 件・②.m-hero/③『NAV/HERO』等 素のHEROは検出対象外)",
    s4,
    f"HERO-01件数={s4_counts}",
)

# ===========================================================================
# S5 ADDR_RE が MV-01 を受理・KNOWN_ADDR 整合（U5 / 受け入れ条件⑤）
# ===========================================================================
va = bridge.is_valid_addr
s5_mv = va("MV-01") is True
s5_hero_still = va("HERO-01") is True     # パターン不変の証跡（旧ラベルも依然受理）
s5_bad = va("MV-1") is False and va("mv-01") is False
known = getattr(bridge, "KNOWN_ADDR", set())
s5_known = ("MV-01" in known) and ("HERO-01" not in known)
s5 = s5_mv and s5_hero_still and s5_bad and s5_known
check(
    "S5 ADDR_RE が MV-01 受理・KNOWN_ADDR整合 (is_valid_addr(MV-01)=True・パターン不変で is_valid_addr(HERO-01)=True・"
    "MV-1/mv-01=False・KNOWN_ADDR に MV-01 有 HERO-01 無)",
    s5,
    f"MV-01受理={s5_mv}, HERO-01も受理(不変)={s5_hero_still}, MV-1/mv-01拒否={s5_bad}, "
    f"KNOWN_ADDR整合={s5_known}(KNOWN_ADDR={sorted(known)})",
)

# ===========================================================================
# S6 ゴールデン9件が MV-01・HERO-01 非残存（§3.0 / §4.1）
# ===========================================================================
s6_detail = {}
s6 = True
for path in GOLDEN_PIN:
    name = os.path.relpath(path, FIX)
    txt = _read(path)
    hero = _hero01_count(txt)
    pin_mv = '<span class="pin">MV-01</span>' in txt
    ok = (hero == 0) and pin_mv
    s6 = s6 and ok
    s6_detail[name] = f"HERO-01={hero}/pin MV-01={pin_mv}"
# compare-regen.html は option 要素で確定文字列
opt_txt = _read(GOLDEN_OPTION)
opt_hero = _hero01_count(opt_txt)
opt_mv = ('<option value="MV-01" selected>MV-01（メインビジュアル）</option>' in opt_txt)
s6_opt = (opt_hero == 0) and opt_mv
s6 = s6 and s6_opt
s6_detail["klk012/compare-regen.html"] = f"HERO-01={opt_hero}/option MV-01（メインビジュアル）={opt_mv}"
check(
    "S6 ゴールデン9件が MV-01・HERO-01非残存 (klk007/008/009/012 の8件は pin MV-01・HERO-01 0件、"
    "compare-regen.html は <option value=\"MV-01\" selected>MV-01（メインビジュアル）</option>)",
    s6,
    "; ".join(f"{k}: {v}" for k, v in s6_detail.items()),
)

# ===========================================================================
# S7 回帰保護（③②の温存を静的確認）（U1 / §3.2 / R2 / R3）
# ===========================================================================
s7_navhero = "NAV/HERO" in DRAFT_RULES            # check_klk008:193 保護（③一般語）
full2col = _read(SAMPLE_FULL_2COL)
s7_mhero = "m-hero" in full2col                   # check_klk012:165 保護（②CSSクラス）
s7 = s7_navhero and s7_mhero
check(
    "S7 回帰保護 (DRAFT_RULES に一般語 『NAV/HERO』 残存[check_klk008:193保護]・"
    "klk008/sample-full-2col.html に CSSクラス m-hero 残存[check_klk012:165保護])",
    s7,
    f"NAV/HERO残存={s7_navhero}, m-hero残存={s7_mhero}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-015 static/core acceptance checks (docs/designs/KLK-015.md §9 S群 S1-S7 を正とする)")
print("対象: DRAFT_RULES.md / draft-generate SKILL / draft-regenerate SKILL /")
print("      draft-gen/bridge.py(import 純関数) / tests/fixtures/klk007|008|009|012/*.html(ゴールデン9件)")
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
print("D群（test_palette_klk015.py で束ねる）:")
print("  - D1 Quality Gate 全緑（python3 -m unittest discover -s tests・KLK-006〜014 回帰なし）")
print("  - D2 check_klk015.py が exit 0（S群全項目通過）")
print()
print("M群（環境制約で静的検証外 = tester/人間が実機で手動確認しチケットのログへ記録）:")
print("  - M1 /draft-generate 新規生成 → 各案の当該セクション pin が MV-01（HERO-01 が出ない）")
print("  - M2 compare.html の🔄再生成 select に『MV-01（メインビジュアル）』・その番地で部分再生成が起動/再表示")
print("  - M3 既存 HERO-01 ラフを /draft-regenerate で MV-01 として作り直せる（ADDR_RE 両ラベル受理・任意）")
print("  - M4 docs/SPEC.md 例示・docs/wireframes/SCR-002-compare.html の pin が MV-01 に整合（目視）")
sys.exit(1 if failed else 0)
