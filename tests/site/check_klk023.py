#!/usr/bin/env python3
"""
KLK-023 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S14 from
docs/designs/KLK-023.md §9（S群）against 本文構造の差別化（archetype 深化）:

  縦串③ 生成規約     .claude/skills/draft-generate/templates/DRAFT_RULES.md（§12.1 / §12.1.1）
  縦串③ スキル定義   .claude/skills/draft-generate/SKILL.md（手順3）
  ゴールデン(案別)     tests/fixtures/klk023/index-a.html（stack-centered）
                      tests/fixtures/klk023/index-b.html（split-editorial）
                      tests/fixtures/klk023/index-c.html（banded-showcase）
  ゴールデン(比較ハブ) tests/fixtures/klk023/compare.html
  ゴールデン(入力写し) tests/fixtures/klk023/instruction.json

Source of truth = 設計書 §9（S群）。check_klk021/022.py と同型（正規表現・文字列検索・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。D群/M群は tests/test_palette_klk023.py と tester 手動。

Run: python3 tests/site/check_klk023.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FX = os.path.join(ROOT, "tests", "fixtures", "klk023")
IDXA = open(os.path.join(FX, "index-a.html"), encoding="utf-8").read()
IDXB = open(os.path.join(FX, "index-b.html"), encoding="utf-8").read()
IDXC = open(os.path.join(FX, "index-c.html"), encoding="utf-8").read()
COMPARE = open(os.path.join(FX, "compare.html"), encoding="utf-8").read()
INSTR = json.load(open(os.path.join(FX, "instruction.json"), encoding="utf-8"))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()

NEW_COLS = {"1col", "2col-full-left", "2col-full-right", "2col-body-left", "2col-body-right", "3col"}
ARCHETYPE_ENUM = {"stack-centered", "split-editorial", "banded-showcase"}
HERO_ENUM = {"full", "split", "band", "overlap"}  # KLK-037: HERO は §12.1.3 プール(4型)。1col×top=offset0 は従来の(full,split,band)
MENU_ENUM = {"pat-cards", "pat-list", "pat-zigzag"}
GAL_ENUM = {"pat-grid", "pat-wide", "pat-mosaic", "pat-slider"}  # KLK-036: GALLERY は §12.1.3 プール(4型)。1col×top=offset0 は従来の(grid,wide,mosaic)
ABOUT_ENUM = {"img-left", "img-right", "img-top", "img-overlap"}  # KLK-037: ABOUT は §12.1.3 プール(4型)
GOLDENS = (("a", IDXA), ("b", IDXB), ("c", IDXC))

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def attr(html, name):
    m = re.search(r'%s="([^"]+)"' % re.escape(name), html)
    return m.group(1) if m else None


def modifier(html, base, prefix):
    m = re.search(r'class="%s (%s[a-z-]+)"' % (base, prefix), html)
    return m.group(1) if m else None


def body_pins(html):
    pins = re.findall(r'class="pin">([A-Z0-9-]+)<', html)
    return tuple(sorted(p for p in pins if p not in ("NAV-01", "MV-01", "FOOTER-01")))


def all_pins(html):
    return set(re.findall(r'class="pin">([A-Z0-9-]+)<', html))


def m_main(html):
    m = re.search(r"--m-main\s*:\s*(#[0-9a-fA-F]{3,8})", html)
    return m.group(1).lower() if m else None


def hero_sig(html):
    i = re.search(r'\.m-hero\s*\{', html)
    block = ""
    if i:
        j = html.find("{", i.end() - 1)
        depth = 0
        for k in range(j, len(html)):
            if html[k] == "{":
                depth += 1
            elif html[k] == "}":
                depth -= 1
                if depth == 0:
                    block = html[j:k + 1]
                    break

    def p(name):
        mm = re.search(name + r"\s*:\s*([a-zA-Z-]+)", block)
        return mm.group(1).lower() if mm else ""
    return (p("justify-content"), p("align-items"), p("text-align"))


def css_layout_rule(html, token):
    """.token を含む CSS セレクタが実レイアウト宣言（grid/flex/order/grid-column 等）を持つか。"""
    for m in re.finditer(r'\.%s\b[^{}]*\{([^}]*)\}' % re.escape(token), html):
        if re.search(r'grid-template-columns|flex-direction|grid-auto|grid-column|grid-row|order\s*:', m.group(1)):
            return True
    return False


def no_ext_deps(html):
    return not (re.search(r'<link\b[^>]*rel=["\']?stylesheet', html, re.I)
                or re.search(r'<script\b[^>]*\bsrc=', html, re.I)
                or re.search(r'fonts\.(googleapis|gstatic)\.com|cdn\.|unpkg\.com|jsdelivr', html, re.I)
                or re.search(r'<img\b[^>]*\bsrc=["\']?https?:', html, re.I))


def distinct3(vals):
    return len(set(vals)) == 3 and all(v is not None for v in vals)


DC = [attr(h, "data-columns") for _, h in GOLDENS]
AR = [attr(h, "data-archetype") for _, h in GOLDENS]
SO = [attr(h, "data-section-order") for _, h in GOLDENS]
HE = [attr(h, "data-hero") for _, h in GOLDENS]
MM = [m_main(h) for _, h in GOLDENS]
MENU = [modifier(h, "m-menu", "pat-") for _, h in GOLDENS]
GAL = [modifier(h, "m-gallery", "pat-") for _, h in GOLDENS]
ABOUT = [modifier(h, "m-about", "img-") for _, h in GOLDENS]
BODY = [body_pins(h) for _, h in GOLDENS]

# S1 継承不変: data-columns 同一・--m-main 相違・archetype 相違(enum)
s1 = (len(set(DC)) == 1 and DC[0] in NEW_COLS
      and distinct3(MM) and distinct3(AR) and all(a in ARCHETYPE_ENUM for a in AR))
check("S1 継承不変 (data-columns 同一・--m-main 相違・data-archetype 相違[enum3])",
      s1, f"columns={DC}(同一={len(set(DC))==1}), --m-main={MM}(相違={distinct3(MM)}), archetype={AR}")

# S2 セクション集合の同一(公平比較)・instruction.sections と一致
want_body = tuple(sorted(k + "-01" for k in INSTR.get("sections", [])))
s2 = (len(set(BODY)) == 1 and BODY[0] == want_body)
check("S2 セクション集合の同一 (3案の本文番地集合が同一・instruction.sections と一致＝公平比較)",
      s2, f"本文集合={BODY[0]} (3案同一={len(set(BODY))==1}), instruction.sections={want_body}")

# S3 並び順の相違
s3 = distinct3(SO)
check("S3 並び順の相違 (data-section-order が3案 distinct・本文DOM順が異なる)",
      s3, f"data-section-order={SO}")

# S4 HERO型の相違＋整列シグネチャの相違
sigs = [hero_sig(h) for _, h in GOLDENS]
s4 = distinct3(HE) and all(h in HERO_ENUM for h in HE) and len(set(sigs)) == 3
check("S4 HERO型の相違 (data-hero[full/split/band] distinct・HERO整列シグネチャも distinct)",
      s4, f"data-hero={HE}, 整列={sigs}")

# S5 MENU型の相違
s5 = distinct3(MENU) and all(m in MENU_ENUM for m in MENU)
check("S5 MENU型の相違 (.m-menu 修飾 pat-cards/list/zigzag が distinct)", s5, f"menu={MENU}")

# S6 GALLERY型の相違
s6 = distinct3(GAL) and all(g in GAL_ENUM for g in GAL)
check("S6 GALLERY型の相違 (.m-gallery 修飾が §12.1.3 プール4型内・案間 distinct)", s6, f"gallery={GAL}")

# S7 ABOUT画像配置の相違
s7 = distinct3(ABOUT) and all(a in ABOUT_ENUM for a in ABOUT)
check("S7 ABOUT画像配置の相違 (.m-about 修飾 img-left/right/top が distinct)", s7, f"about={ABOUT}")

# S8 実CSS差: 各修飾が実レイアウト宣言を伴う(飾りでない)
s8_ok = True
s8_detail = []
for (letter, h), mk, gk, ak in zip(GOLDENS, MENU, GAL, ABOUT):
    r = all(css_layout_rule(h, t) for t in (mk, gk, ak) if t)
    s8_ok = s8_ok and r
    s8_detail.append(f"{letter}:{r}")
check("S8 実CSS差 (各 pat-*/img-* 修飾が実レイアウト宣言 grid/flex/order を伴う＝属性だけの飾りでない)",
      s8_ok, "; ".join(s8_detail))

# S9 各案の健全性: 番地(集合+NAV/MV/FOOTER)・print・アタリa・依存0
s9_ok = True
s9_detail = []
for letter, h in GOLDENS:
    pins = all_pins(h)
    want = set(want_body) | {"NAV-01", "MV-01", "FOOTER-01"}
    prt = "@media print" in h
    atari = 'class="atari"' in h and 'class="desc"' in h
    solo = no_ext_deps(h)
    ok = (pins == want) and prt and atari and solo
    s9_ok = s9_ok and ok
    s9_detail.append(f"{letter}:番地={pins==want}/print={prt}/アタリ={atari}/依存0={solo}")
check("S9 各案の健全性 (番地=選択集合+NAV/MV/FOOTER・@media print・アタリa方式・外部依存0)",
      s9_ok, "; ".join(s9_detail))

# S10 DRAFT_RULES §12.1.1
r_bundle = "12.1.1" in RULES and "本文構造" in RULES
r_axes = all(t in RULES for t in ("data-section-order", "data-hero", "pat-cards", "pat-mosaic", "img-top"))
r_fair = ("セクション集合" in RULES and ("全案同一" in RULES or "全案共通" in RULES))
check("S10 DRAFT_RULES §12.1.1 (archetype→本文構造の束・離散マーカー・セクション集合は全案同一)",
      r_bundle and r_axes and r_fair, f"本文構造束={r_bundle}, 軸マーカー={r_axes}, 集合固定={r_fair}")

# S11 SKILL 手順
k_ok = ("data-section-order" in SKILL and "data-hero" in SKILL
        and "pat-" in SKILL and "img-" in SKILL and "本文構造" in SKILL)
check("S11 SKILL 手順 (本文構造を案別に振る手順・並び順/HERO型/MENU/GALLERY/ABOUT の離散マーカー)",
      k_ok, f"手順記述={k_ok}")

# S12 compare.html §13
c_radio = len(re.findall(r'<input[^>]*type="radio"[^>]*name="variant"', COMPARE)) >= 2
c_comb = re.search(r'#\w+:checked\s*~[^{}]*#pane[A-C][^{}]*\{[^}]*display\s*:\s*block', COMPARE, re.S) is not None
c_noscript = re.search(r'<script', COMPARE, re.I) is None
c_iframe = all(re.search(r'<iframe[^>]*src="index-%s\.html"' % L, COMPARE) for L in "abc")
c_full = all(re.search(r'href="index-%s\.html"[^>]*target="_blank"' % L, COMPARE) for L in "abc")
c_noext = re.search(r'<iframe[^>]*src="https?:', COMPARE, re.I) is None
check("S12 compare.html §13準拠 (CSS-only切替・iframe相対index-{letter}・原寸別タブ・外部URL無)",
      c_radio and c_comb and c_noscript and c_iframe and c_full and c_noext,
      f"radio={c_radio}, 結合子={c_comb}, script非依存={c_noscript}, iframe={c_iframe}, 原寸={c_full}, 外部URL無={c_noext}")

# S13 セキュリティ/依存
_ALLOW = ("www.w3.org", "example.com", "example.org", "example.net")


def _host(u):
    m = re.match(r"https?://([^/\s\"')]+)", u)
    return m.group(1).lower() if m else ""


secret_re = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
s13_ok = True
s13_detail = {}
for label, txt in (("a", IDXA), ("b", IDXB), ("c", IDXC), ("compare", COMPARE)):
    ext = [u for u in re.findall(r'https?://[^\s"\')（]+', txt) if _host(u) not in _ALLOW]
    sec = [ln for ln, line in enumerate(txt.splitlines(), 1) if secret_re.search(line)]
    ph = ("プレースホルダ" in txt or "実在の顧客" in txt or "サンプル" in txt)
    ok = (not ext) and (not sec) and ph
    s13_ok = s13_ok and ok
    s13_detail[label] = f"外部URL={ext or 0}/秘密={sec or 0}/PH={ph}"
check("S13 セキュリティ/依存 (klk023 全ゴールデン: 外部URL0・秘密0・プレースホルダ明記)",
      s13_ok, "; ".join(f"{k}: {v}" for k, v in s13_detail.items()))

# S14 既存回帰(KLK-021/022 の記述が残る)
r_klk021 = "stack-centered" in RULES and "split-editorial" in RULES and "banded-showcase" in RULES
r_klk022 = "instruction.sections" in RULES or "§2.1" in RULES
check("S14 既存回帰保持 (KLK-021 archetype 3値・KLK-022 sections の記述が保持・additive)",
      r_klk021 and r_klk022, f"KLK-021 archetype={r_klk021}, KLK-022 sections={r_klk022}")

# Report
print("=" * 78)
print("KLK-023 static acceptance checks (docs/designs/KLK-023.md §9 S群 を正とする)")
print("対象: fixtures/klk023/{index-a/b/c,compare}.html + instruction.json / DRAFT_RULES.md / SKILL.md")
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
print("D群（test_palette_klk023.py）: Quality Gate 全緑 / mockups 生成物の git check-ignore（git不在時skip）")
print("M群（tester 手動・ブラウザ）: 同じセクション集合でも3案の本文構造が目に見えて違う / compare で視認 / 1col・2col両方で差")
sys.exit(1 if failed else 0)
