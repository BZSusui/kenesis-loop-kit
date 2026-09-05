#!/usr/bin/env python3
"""
KLK-097 acceptance-condition checker — MV の SCROLL 誘導とボタンの重なり解消。

★この checker が守っているもの:
  **「SCROLL ↓ が中央列の外に出ていること」**。
  旧実装は `.scroll-cue{position:absolute;bottom:18px;left:50%;transform:translateX(-50%)}`
  ＝ 中央列の最下部。MV は `justify-content:center` の縦積みなので、中身
  （キャッチ＋リード＋ボタン）が増えると縦積みが底へ届き、**構造的に必ず重なる**。
  見本「サンプル和菓子店」案A（`full`）で発生（理恵さんの目視で発覚）。

  ここで検査するのは規約の文章だけではない。**生成物の CSS を実測し、
  誘導の帯と本文の帯が数値として重ならないこと**まで見る。
  （規約に書いただけでは効かない、が KLK-072〜076/081 で繰り返された教訓）

Run: python3 tests/site/check_klk097.py
Exit code 0 = all pass, 1 = at least one fail.
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

RULES = io.open(os.path.join(ROOT, ".claude", "skills", "draft-generate",
                             "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
CANON = io.open(os.path.join(ROOT, "docs", "wireframes", "SCR-002-compare.html"),
                encoding="utf-8").read()

# 誘導の幅の見積り: font-size 11px の縦組み ＋ gap 8px ＋ 矢印 ≒ 20px。
# 左端 18px からこの幅を足した 38px より内側に本文が来なければ重ならない。
CUE_LEFT = 18
CUE_WIDTH = 20
MIN_PAD = 64          # §4.3.2 の要求値
MIN_PAD_MOBILE = 40

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def seg(start, end):
    i = RULES.find(start)
    return RULES[i:RULES.find(end, i)] if i >= 0 else ""


SEG432 = seg("#### 4.3.2 スクロール誘導は「画面端に縦組み」で置く", "#### 4.3.3")
SEG433 = seg("#### 4.3.3 MV はファーストビューを覆う縦幅にする", "### 4.4")

# ---------------------------------------------------------------------------
# 規約 — 何を禁じ、何を根拠に禁じたのかが残っているか
# ---------------------------------------------------------------------------
check("C1 §4.3.2 が存在し、中央下への絶対配置を禁じている",
      bool(SEG432) and "中央下に絶対配置してはならない" in SEG432
      and "translateX(-50%)" in SEG432,
      "節=%s / 禁止の明記=%s" % (bool(SEG432), "中央下に絶対配置してはならない" in SEG432))

check("C2 §4.3.2 が「偶然ではなく構造的な必然」だと理由を書いている（再発防止の核）",
      "構造的な必然" in SEG432 and "justify-content:center" in SEG432
      and "縦幅を伸ばすだけでは" in SEG432,
      "必然の明記=%s / 縦幅だけでは不足=%s"
      % ("構造的な必然" in SEG432, "縦幅を伸ばすだけでは" in SEG432))

check("C3 §4.3.2 が右下ではなく左下だと理由つきで指定している（.atari-tag が右下を占有）",
      "atari-tag" in SEG432 and "右下" in SEG432 and "left:18px" in SEG432.replace(" ", ""),
      "atari-tag への言及=%s / 左端の指定=%s"
      % ("atari-tag" in SEG432, "left:18px" in SEG432.replace(" ", "")))

check("C4 §4.3.2 が帯の予約（左右 padding 64px 以上・左右対称）を要求している",
      "64px" in SEG432 and "左右対称" in SEG432 and "padding-inline" in SEG432,
      "64px=%s / 対称の指示=%s" % ("64px" in SEG432, "左右対称" in SEG432))

check("C5 §4.3.2 が縦組み（vertical-rl）と矢印だけ横（horizontal-tb）を指定している",
      "vertical-rl" in SEG432 and "horizontal-tb" in SEG432,
      "vertical-rl=%s / horizontal-tb=%s"
      % ("vertical-rl" in SEG432, "horizontal-tb" in SEG432))

check("C6 §4.3.2 が §4.3.1 のクリック可能性を壊さないと明記している",
      "§4.3.1" in SEG432 and "押せること" in SEG432,
      "§4.3.1 の維持=%s" % ("押せること" in SEG432))

check("C7 §4.3.3 が存在し、対象4型（full/split/band/center-scroll）を名指ししている",
      bool(SEG433) and all(k in SEG433 for k in ("full", "split", "band", "center-scroll")),
      "対象=%s" % {k: (k in SEG433) for k in ("full", "split", "band", "center-scroll")})

check("C8 §4.3.3 が overlap / panel-band を対象外だと理由つきで除いている",
      "overlap" in SEG433 and "panel-band" in SEG433 and "対象外" in SEG433,
      "除外の明記=%s" % ("対象外" in SEG433))

check("C9 §4.3.3 が svh を使い、vh と固定 px のフォールバックを重ねている",
      "svh" in SEG433 and "100vh" in SEG433 and "520px" in SEG433
      and "フォールバック" in SEG433,
      "svh=%s / vh=%s / 下限=%s" % ("svh" in SEG433, "100vh" in SEG433, "520px" in SEG433))

check("C10 §4.3.3 が印刷時に高さを戻すよう指示している",
      "@media print" in SEG433 and "320px" in SEG433,
      "印刷指定=%s" % ("320px" in SEG433))

check("C11 §4.3.3 が「覆うとだけ書いて数値を欠いた」乖離を記録している（同じ失敗の目印）",
      "数値" in SEG433 and ("340" in SEG433 or "360px" in SEG433)
      and "SCR-002-compare.html" in SEG433,
      "乖離の記録=%s / 出所=%s"
      % ("数値" in SEG433, "SCR-002-compare.html" in SEG433))

# ---------------------------------------------------------------------------
# 構造の正 — ここを写して浅い MV になったので、正の側にも印を残す
# ---------------------------------------------------------------------------
check("C12 構造の正 SCR-002 に正しい形の .scroll-cue があり、中央寄せしていない",
      ".scroll-cue" in CANON and "vertical-rl" in CANON
      and "translateX(-50%)" not in CANON.split(".scroll-cue")[1][:400],
      "cue の定義=%s / 縦組み=%s" % (".scroll-cue" in CANON, "vertical-rl" in CANON))

check("C13 構造の正が「ここの min-height を写すな・§4.3.3 に従え」と注意書きしている",
      "§4.3.3" in CANON and "縮小プレビュー" in CANON,
      "注意書き=%s" % ("§4.3.3" in CANON))

# ---------------------------------------------------------------------------
# 検査の実装 — bridge が違反を実際に検出できるか（合成データで陽性・陰性の両方）
# ---------------------------------------------------------------------------
BAD = """<html><head><style>
.m-hero{position:relative;min-height:360px;display:flex;flex-direction:column;
justify-content:center;padding:40px 30px;}
.m-hero .scroll-cue{position:absolute;bottom:18px;left:50%;transform:translateX(-50%);}
</style></head><body>
<div class="sec"><div class="addr"><span class="pin">MV-01</span></div>
<div class="m-hero" data-hero="full"><h1 class="catch">x</h1>
<a class="hero-cta" href="#a">b</a>
<a class="scroll-cue" href="#a">SCROLL <span class="arrow">&#8595;</span></a>
</div></div></body></html>"""

GOOD = """<html><head><style>
.m-hero{position:relative;min-height:max(520px, calc(100svh - 64px));display:flex;
flex-direction:column;justify-content:center;padding:40px 64px;}
.m-hero .scroll-cue{position:absolute;left:18px;bottom:24px;right:auto;transform:none;
writing-mode:vertical-rl;}
.m-hero .scroll-cue .arrow{writing-mode:horizontal-tb;}
</style></head><body>
<div class="sec"><div class="addr"><span class="pin">MV-01</span></div>
<div class="m-hero" data-hero="full"><h1 class="catch">x</h1>
<a class="hero-cta" href="#a">b</a>
<a class="scroll-cue" href="#a">SCROLL <span class="arrow">&#8595;</span></a>
</div></div></body></html>"""

wbad = bridge.find_quality_warnings(BAD, "MV-01")
wgood = bridge.find_quality_warnings(GOOD, "MV-01")
check("C14 bridge が中央下の誘導を検出する（陽性）",
      any("中央下" in w for w in wbad), "警告=%s" % wbad)
check("C15 bridge が帯の予約不足（padding 30px）を検出する（陽性）",
      any("padding" in w for w in wbad), "警告=%s" % wbad)
check("C16 bridge が正しい形を誤検出しない（陰性・偽陽性は無視される警告を生む）",
      not wgood, "警告=%s" % wgood)

# ---------------------------------------------------------------------------
# 生成物の実測 — 規約でも合成データでもなく、実在するページの CSS を測る
# ---------------------------------------------------------------------------
def page_css(h):
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", h, re.S))


def decl(body, prop):
    m = re.search(r"(?<![-\w])" + prop + r"\s*:\s*([^;]+)", body)
    return m.group(1).strip() if m else None


targets = []
for f in sorted(glob.glob(os.path.join(ROOT, "samples", "*", "index-*.html"))
                + glob.glob(os.path.join(ROOT, "mockups", "*", "index-*.html"))):
    h = io.open(f, encoding="utf-8").read()
    if "scroll-cue" in h:
        targets.append((os.path.relpath(f, ROOT), h))

check("C17 SCROLL 誘導を持つ生成物が実在する（検査が空振りしていない）",
      len(targets) >= 3, "対象 %d 件" % len(targets))

bad_center, bad_pad, bad_arrow, bad_h, bad_print, bad_anchor, bad_mobile = [], [], [], [], [], [], []
for rel, h in targets:
    css = page_css(h)
    cue_bodies = [m.group(2) for m in re.finditer(r"([^{}]*\.scroll-cue\s*)\{([^}]*)\}", css)
                  if ".arrow" not in m.group(1)]
    # ① 中央列に戻っていないか
    for b in cue_bodies:
        if (decl(b, "left") or "").strip() == "50%" or "translateX(-50%)" in (decl(b, "transform") or ""):
            bad_center.append(rel)
    # ② 縦組みと矢印
    if not any("vertical" in (decl(b, "writing-mode") or "") for b in cue_bodies):
        bad_arrow.append(rel + "（縦組みなし）")
    if "horizontal-tb" not in css:
        bad_arrow.append(rel + "（矢印が横向きでない）")
    # ③ ★幾何の実測 — 本文の左端が誘導の右端より内側にあるか
    pads = []
    for m in re.finditer(r"([^{}]*\.m-hero(?:\[[^\]]*\])?\s*)\{([^}]*)\}", css):
        b = m.group(2)
        v = decl(b, "padding-inline")
        if v is None:
            p = decl(b, "padding")
            if p and len(p.split()) >= 2:
                v = p.split()[1]
        if v and re.match(r"^\d+px$", v.strip()):
            pads.append((m.group(1).strip(), int(v.strip()[:-2]), m.start()))
    mobile_spans = [(mm.start(), mm.end()) for mm in
                    re.finditer(r"@media[^{]*max-width[^{]*\{(?:[^{}]|\{[^}]*\})*\}", css)]
    # ★カスケード後の値で測る。生成側は素の `.m-hero` の shorthand を残したまま
    #   後続ルールで `padding-inline:64px` を上書きする（実際にそう生成された）。
    #   1ルールずつ独立に見ると誤報になり、無視される警告を生む。
    for scope, floor in ((False, MIN_PAD), (True, MIN_PAD_MOBILE)):
        vals = [(sel, v) for sel, v, pos in pads
                if any(a <= pos <= b for a, b in mobile_spans) is scope]
        if not vals:
            continue
        sel, v = vals[-1]          # 同一詳細度なら後勝ち
        where = "モバイル" if scope else "デスクトップ"
        if v < floor:
            bad_pad.append("%s %s %s=%dpx(<%d)" % (rel, where, sel[:26], v, floor))
        elif v < CUE_LEFT + CUE_WIDTH:
            bad_pad.append("%s %s %s=%dpx は誘導の右端 %dpx に届かない"
                           % (rel, where, sel[:26], v, CUE_LEFT + CUE_WIDTH))
    if not pads:
        bad_pad.append(rel + "（MV に左右 padding の指定がない＝帯を予約できていない）")
    if not any(a <= pos <= b for _, _, pos in pads for a, b in mobile_spans):
        bad_mobile.append(rel)
    # ④ ファーストビュー高さ
    hero_out = [m.group(2) for m in re.finditer(r"([^{}]*\.m-hero(?:\[[^\]]*\])?\s*)\{([^}]*)\}", css)
                if not any(a <= m.start() <= b for a, b in mobile_spans)]
    if not any("svh" in (b or "") for b in hero_out):
        bad_h.append(rel + "（svh なし）")
    if not any("100vh" in (b or "") for b in hero_out):
        bad_h.append(rel + "（vh フォールバックなし）")
    # ⑤ 印刷
    if "min-height: 320px" not in css and "min-height:320px" not in css:
        bad_print.append(rel)
    # ⑥ §4.3.1 のアンカーを壊していないか
    for m in re.finditer(r'<a[^>]*class="[^"]*\bscroll-cue\b[^"]*"[^>]*>', h):
        href = re.search(r'href="([^"]*)"', m.group(0))
        if not href or not href.group(1).startswith("#") or href.group(1) == "#":
            bad_anchor.append(rel + " " + m.group(0)[:60])

check("C18 生成物の誘導が中央列に戻っていない", not bad_center, "違反=%s" % (bad_center or "なし"))
check("C19 生成物の誘導が縦組みで、矢印だけ下向きを保つ", not bad_arrow, "違反=%s" % (bad_arrow or "なし"))
check("C20 ★幾何の実測 — 本文の帯が誘導の帯（左端18px+幅20px）に入り込まない",
      not bad_pad, "違反=%s" % (bad_pad or "なし"))
check("C21 モバイルでも帯を予約している", not bad_mobile, "帯なし=%s" % (bad_mobile or "なし"))
check("C22 MV がファーストビュー高さ（svh＋vh フォールバック）を持つ", not bad_h, "違反=%s" % (bad_h or "なし"))
check("C23 印刷時に MV の高さを戻している", not bad_print, "違反=%s" % (bad_print or "なし"))
check("C24 §4.3.1 のページ内アンカーが維持されている", not bad_anchor, "違反=%s" % (bad_anchor or "なし"))

print("=" * 78)
print("KLK-097 MV の SCROLL 誘導とボタンの重なり解消 チェック")
print("=" * 78)
failed = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print("[%s] %s" % (status, name))
    print("        %s" % detail)
print("-" * 78)
print("%d checks, %d failed" % (len(results), failed))
sys.exit(1 if failed else 0)
