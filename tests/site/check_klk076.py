#!/usr/bin/env python3
"""
KLK-076 acceptance-condition checker (static / no browser required).

★このチェッカーが他と違うところ:
  既存の check_klkNNN.py は **規約テキストに必要な記述があるか**までしか見ていない
  （check_klk072.py の docstring が自認しているとおり）。
  そのため「規約は正しいのに生成物が違う」を自動検出できず、
  毎回 30 分かけて見本を再生成して目視するしかなかった。

  同梱している見本（samples/）は**生成物の正**であり、配布物そのものでもある。
  ここを機械検査すれば、規約が実際に効いたかを常時見張れる。

  R群 = 規約テキストの検査（従来型）
  S群 = samples/ の実物 HTML の検査（本チケットの本体）

Run: python3 tests/site/check_klk076.py
Exit code 0 = all checks pass, 1 = at least one fail.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(
    os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"),
    encoding="utf-8",
).read()
SAMPLE_DIRS = sorted(
    d for d in glob.glob(os.path.join(ROOT, "samples", "*")) if os.path.isdir(d)
)

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def rel(p):
    return os.path.relpath(p, ROOT)


# ---------------------------------------------------------------------------
# 最小の CSS 走査（依存なし・NFR-005）
# ---------------------------------------------------------------------------
_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def css_of(html):
    """<style> の中身を連結して返す（コメント除去済み）。"""
    return _COMMENT.sub("", "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)))


def iter_rules(css):
    """(selector, body, in_media) を列挙する。@media は1段だけ入れ子を解く。"""
    i = 0
    n = len(css)
    while i < n:
        at = css.find("@media", i)
        brace = css.find("{", i)
        if brace < 0:
            break
        if at >= 0 and at < brace:
            # @media 条件 { ... } を切り出す
            open_b = css.find("{", at)
            depth = 0
            j = open_b
            while j < n:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            cond = css[at:open_b].strip()
            for sel, body, _ in iter_rules(css[open_b + 1:j]):
                yield sel, body, cond
            i = j + 1
            continue
        close_b = css.find("}", brace)
        if close_b < 0:
            break
        sel = css[i:brace].strip()
        body = css[brace + 1:close_b]
        if sel and not sel.startswith("@"):
            yield sel, body, ""
        i = close_b + 1


def decl(body, prop):
    """宣言の値を返す（無ければ None）。"""
    m = re.search(r"(?:^|;)\s*%s\s*:\s*([^;]+)" % re.escape(prop), body)
    return m.group(1).strip() if m else None


def norm(v):
    return re.sub(r"\s+", "", v or "")


def sample_htmls():
    for d in SAMPLE_DIRS:
        for p in sorted(glob.glob(os.path.join(d, "index-*.html"))):
            yield p, open(p, encoding="utf-8").read()


# ===========================================================================
# R群 — 規約テキスト
# ===========================================================================
_i = RULES.find("### 3.0 アタリ枠の比率")
SEG30 = RULES[_i:RULES.find("### 3.1", _i)] if _i >= 0 else ""
_j = RULES.find("#### 3.0.1")
SEG301 = RULES[_j:RULES.find("### 3.1", _j)] if _j >= 0 else ""
_k = RULES.find("#### 4.1.1")
SEG411 = RULES[_k:RULES.find("### 4.2", _k)] if _k >= 0 else ""

check(
    "R1 §3.0 の例外表が panel-band の全幅と max-height 禁止に触れている",
    "帯は MV の左右いっぱいまで伸ばし" in SEG30 and "`max-height` は付けない" in SEG30,
    "全幅=%s / max-height禁止=%s"
    % ("帯は MV の左右いっぱいまで伸ばし" in SEG30, "`max-height` は付けない" in SEG30),
)

check(
    "R2 §3.0.1 が新設されている",
    bool(SEG301) and "panel-band" in SEG301,
    "節あり=%s（%d字）" % (bool(SEG301), len(SEG301)),
)

check(
    "R3 §3.0.1 が守るべき結果を3つ明示している（端一致・auto-fit・max-height 無し）",
    all(
        t in SEG301
        for t in ["MV の左右端と一致", "repeat(auto-fit, minmax(220px, 1fr))", "`max-height` を付けない"]
    ),
    "端一致=%s / auto-fit=%s / max-height=%s"
    % (
        "MV の左右端と一致" in SEG301,
        "repeat(auto-fit, minmax(220px, 1fr))" in SEG301,
        "`max-height` を付けない" in SEG301,
    ),
)

check(
    "R4 §3.0.1 が実装を1つに縛らず2通り（padding 相殺／padding を内側へ）を示している",
    "margin-inline" in SEG301 and "hero-head" in SEG301,
    "A(相殺)=%s / B(内側へ)=%s" % ("margin-inline" in SEG301, "hero-head" in SEG301),
)

check(
    "R5 §3.0.1 が実際に負けた CSS を掲載している（再発の目印）",
    "repeat(6,1fr)" in SEG301 and "max-height:130px" in SEG301,
    "NG例=%s" % ("repeat(6,1fr)" in SEG301 and "max-height:130px" in SEG301),
)

check(
    "R6 §4.1.1 が3案すべてに同じ規律を適用すると明記している",
    "3案すべてに同じ規律を適用する" in SEG411 and "行組も3案で揃える" in SEG411,
    "明記=%s" % ("3案すべてに同じ規律を適用する" in SEG411),
)

check(
    "R7 §4.1.1 が案Aだけ適用された実例と、確認手順を載せている",
    "案Aだけ" in SEG411 and "文末以外に `。` があるのに `<br>` が無い" in SEG411,
    "実例=%s / 手順=%s"
    % ("案Aだけ" in SEG411, "文末以外に `。` があるのに `<br>` が無い" in SEG411),
)

# ===========================================================================
# S群 — samples/ の実物
# ===========================================================================
check(
    "S0 見本が3点そろっている",
    len(SAMPLE_DIRS) >= 3 and all(len(glob.glob(os.path.join(d, "index-*.html"))) == 3 for d in SAMPLE_DIRS),
    "%d フォルダ / %s" % (len(SAMPLE_DIRS), [os.path.basename(d) for d in SAMPLE_DIRS]),
)

# --- S1 極端な横長比率がない -------------------------------------------------
ALLOWED_RATIOS = {(4, 3), (1, 1), (3, 2)}
offenders = []
seen_ratios = set()
for p, html in sample_htmls():
    for sel, body, _m in iter_rules(css_of(html)):
        v = decl(body, "aspect-ratio")
        if not v:
            continue
        v = norm(v)
        if v == "auto":
            continue
        m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:/(\d+(?:\.\d+)?))?", v)
        if not m:
            offenders.append("%s  %s { aspect-ratio:%s }" % (rel(p), sel[:60], v))
            continue
        w = float(m.group(1))
        h = float(m.group(2)) if m.group(2) else 1.0
        seen_ratios.add(v)
        if (w, h) in {(float(a), float(b)) for a, b in ALLOWED_RATIOS}:
            continue
        if w / h > 1.6:
            offenders.append("%s  %s { aspect-ratio:%s }" % (rel(p), sel[:60], v))
check(
    "S1 見本のアタリに極端な横長比率（16/7・16/6 など）が無い",
    not offenders,
    "出現した比率=%s / 違反=%s" % (sorted(seen_ratios), offenders or "なし"),
)

# --- S2 min-height だけで高さを決めたアタリが無い（HERO 全面ビジュアルは例外） ----
ATARI_SEL = re.compile(r"\.(?:[a-z0-9-]*atari|thumb|cell|tile)\b")
offenders = []
for p, html in sample_htmls():
    for sel, body, media in iter_rules(css_of(html)):
        if media:
            continue  # モバイル上書きは対象外
        if not ATARI_SEL.search(sel):
            continue
        if "hero-atari" in sel or "hero-media" in sel:
            continue  # §3.0 例外: HERO の全面ビジュアル
        if decl(body, "min-height") and not decl(body, "aspect-ratio"):
            offenders.append("%s  %s" % (rel(p), sel[:70]))
check(
    "S2 min-height だけで高さを決めたアタリが無い（HERO 全面ビジュアルを除く）",
    not offenders,
    offenders or "なし",
)

# --- S3 catch / lead の句点改行が3案そろっている -----------------------------
offenders = []
checked = 0
for p, html in sample_htmls():
    for cls in ("catch", "lead"):
        m = re.search(r'<[^>]*class="[^"]*\b%s\b[^"]*"[^>]*>(.*?)</' % cls, html, re.S)
        if not m:
            continue
        t = m.group(1).strip()
        checked += 1
        inner = t[:-1] if t.endswith("。") else t
        if "。" in inner and "<br>" not in t:
            offenders.append("%s  .%s = %s" % (rel(p), cls, t[:60]))
check(
    "S3 見本の catch / lead が句点で改行されている（3案とも・§4.1.1）",
    not offenders and checked >= 12,
    "検査%d件 / 違反=%s" % (checked, offenders or "なし"),
)

# --- S4 panel-band の帯が全幅・auto-fit・max-height 無し ----------------------
BAND_PROP = "grid-template-columns"
offenders = []
band_found = 0
for p, html in sample_htmls():
    if not re.search(r'data-hero=["\']?panel-band', html):
        continue
    css = css_of(html)
    hero_pad = None
    band = None
    for sel, body, media in iter_rules(css):
        if media:
            continue
        if "panel-band" not in sel:
            continue
        after = sel.split("panel-band")[-1]
        # `.m-hero[data-hero=panel-band]` 本体（子孫セレクタを含まない）
        if re.fullmatch(r'["\']?\]?\s*', after) and decl(body, "padding"):
            hero_pad = decl(body, "padding")
        # 帯のルール＝1行を作る宣言（KLK-081 で auto-fit から grid-auto-flow:column へ）
        if decl(body, "grid-auto-flow") or (
            decl(body, BAND_PROP) and "repeat" in norm(decl(body, BAND_PROP))
        ):
            band = (sel, body)
    if band is None:
        offenders.append("%s  帯の grid ルールが見つからない" % rel(p))
        continue
    band_found += 1
    sel, body = band
    # ★契約更新（KLK-081）: auto-fit は**列数がパネル数と一致する保証がない**ため段落ちした
    #   （1200〜1280px で 5列に6枚＝5+1 の2行・見本03 案Cで発生）。
    #   要求するのは「どの幅でも1行」＝ grid-auto-flow:column で列をアイテム数だけ作ること。
    flow = norm(decl(body, "grid-auto-flow") or "")
    if flow != "column":
        offenders.append(
            "%s  1行が保証されていない（grid-auto-flow:column でない: %s）"
            % (rel(p), flow or norm(decl(body, BAND_PROP) or ""))
        )
    if "auto-fit" in norm(decl(body, BAND_PROP) or ""):
        offenders.append("%s  auto-fit が残っている（段落ちの原因）" % rel(p))
    if decl(body, "max-height"):
        offenders.append("%s  max-height が付いている: %s" % (rel(p), decl(body, "max-height")))
    # 全幅: hero に左右 padding があるなら margin-inline で相殺していること
    lr = 0
    if hero_pad:
        parts = hero_pad.split()
        side = parts[1] if len(parts) >= 2 else parts[0]
        mm = re.match(r"(\d+(?:\.\d+)?)px", side)
        lr = float(mm.group(1)) if mm else 0
    if lr > 0 and not decl(body, "margin-inline"):
        offenders.append(
            "%s  hero の左右 padding %spx を相殺していない（帯が端に届かない）" % (rel(p), lr)
        )
check(
    "S4 panel-band の帯が MV 全幅・1行保証・max-height 無し（§3.0.1・KLK-081）",
    band_found >= 1 and not offenders,
    "検査%d本 / 違反=%s" % (band_found, offenders or "なし"),
)

# --- S5 masonry / mosaic が大小混在で、グリッドに空きが無い --------------------
def span_of(cls_attr, css_spans, index1):
    """タイル1枚の占有セルを返す。

    ★型は2通りの書き方で来る（KLK-079 の実機検証で判明）:
      (a) タイルにクラスを付ける  `.pat-mosaic .g-big{grid-column:span 2}`
      (b) 位置で指定する          `.pat-masonry .atari:nth-child(1){grid-column:span 2}`
    (b) を読めないと**全部 1×1 に見えてしまい**、正しい構成なのに「空きセルあり」と誤検出する。
    """
    w = h = 1
    for key, (sw, sh) in css_spans.items():
        if key.startswith("nth:"):
            if int(key[4:]) == index1:
                w, h = max(w, sw), max(h, sh)
        elif key and key in cls_attr:
            w, h = max(w, sw), max(h, sh)
    return w, h


offenders = []
grids_found = 0
for p, html in sample_htmls():
    m = re.search(r'class="m-gallery ([a-z-]*(?:masonry|mosaic))"', html)
    if not m:
        continue
    marker = m.group(1)
    css = css_of(html)
    cols = None
    css_spans = {}
    for sel, body, media in iter_rules(css):
        if media or marker not in sel:
            continue
        gtc = norm(decl(body, BAND_PROP) or "")
        mm = re.match(r"repeat\((\d+),", gtc)
        if mm and sel.strip().endswith(marker):
            cols = int(mm.group(1))
        gc = norm(decl(body, "grid-column") or "")
        gr = norm(decl(body, "grid-row") or "")
        if gc.startswith("span") or gr.startswith("span"):
            nth = re.search(r":nth-child\(\s*(\d+)\s*\)", sel)
            if nth:
                key = "nth:%s" % nth.group(1)
            else:
                key = sel.split(".")[-1].strip()
            sw = int(re.sub(r"\D", "", gc) or 1)
            sh = int(re.sub(r"\D", "", gr) or 1)
            css_spans[key] = (sw, sh)
    if not cols:
        offenders.append("%s  列数が読めない（%s）" % (rel(p), marker))
        continue
    start = html.index('class="m-gallery %s"' % marker)
    block = html[start:html.index("</section>", start)]
    tiles = [t.strip() for t in re.findall(r'<div class="atari([^"]*)"', block)]
    if not tiles:
        offenders.append("%s  タイルが読めない" % rel(p))
        continue
    sizes = [span_of(t, css_spans, i + 1) for i, t in enumerate(tiles)]
    if len({s for s in sizes}) < 2:
        offenders.append("%s  全タイルが同サイズ（大小混在でない）: %s" % (rel(p), sizes))
    # dense 配置を模して穴を数える
    grid = {}
    for w, h in sizes:
        r = 0
        placed = False
        while not placed:
            for c in range(cols - w + 1):
                if all((r + dr, c + dc) not in grid for dr in range(h) for dc in range(w)):
                    for dr in range(h):
                        for dc in range(w):
                            grid[(r + dr, c + dc)] = 1
                    placed = True
                    break
            r += 1
    rows = max(r for r, _ in grid) + 1
    holes = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in grid]
    grids_found += 1
    if holes:
        offenders.append("%s  %d行×%d列に空きセル %d 個" % (rel(p), rows, cols, len(holes)))
check(
    "S5 masonry / mosaic が大小混在で、最終行まで空きが無い",
    grids_found >= 1 and not offenders,
    "検査%d本 / 違反=%s" % (grids_found, offenders or "なし"),
)

# --- S6 本文2カラムの見本でカード内が横並びになっていない（§8.1） --------------
ITEM_MARKERS = (
    "voice-zigzag", "voice-two-col", "voice-slider",
    "flow-zigzag", "staff-zigzag",
    "img-left", "img-right", "img-overlap", "img-circle", "img-zigzag",
    "feature-large",
)
TRACK = re.compile(r"(\d+(?:\.\d+)?)(px|fr|%)|repeat\((\d+)\s*,")
offenders = []
two_col_files = 0
for d in SAMPLE_DIRS:
    ins = os.path.join(d, "instruction.json")
    if not os.path.exists(ins):
        continue
    cols = (json.load(open(ins, encoding="utf-8")).get("layout") or {}).get("columns", "")
    if not cols.startswith(("2col", "3col")):
        continue
    for p in sorted(glob.glob(os.path.join(d, "index-*.html"))):
        two_col_files += 1
        html = open(p, encoding="utf-8").read()
        for sel, body, media in iter_rules(css_of(html)):
            if media:
                continue
            if not any(mk in sel for mk in ITEM_MARKERS):
                continue
            gtc = decl(body, BAND_PROP)
            if not gtc:
                continue
            g = norm(gtc)
            rep = re.fullmatch(r"repeat\((\d+),.*", g)
            ntracks = int(rep.group(1)) if rep else len(gtc.split())
            if ntracks < 2:
                continue
            # 番号バッジのような小さな固定幅（<=100px）＋本文は「画像と本文の横並び」ではない
            px = re.findall(r"(\d+(?:\.\d+)?)px", g)
            if px and all(float(x) <= 100 for x in px) and ntracks == 2:
                continue
            offenders.append("%s  %s { %s: %s }" % (rel(p), sel[:60], BAND_PROP, gtc))
check(
    "S6 本文2カラム/3カラムの見本でカード内が横並びになっていない（§8.1）",
    two_col_files >= 1 and not offenders,
    "検査%dファイル / 違反=%s" % (two_col_files, offenders or "なし"),
)

# --- S7 見本が自己完結している（相対参照の欠損・外部URLが無い） -----------------
missing, external = [], []
for d in SAMPLE_DIRS:
    for p in sorted(glob.glob(os.path.join(d, "*.html"))):
        html = open(p, encoding="utf-8").read()
        for u in re.findall(r'(?:src|href)="([^"]+)"', html):
            if u.startswith("#") or u.startswith("data:") or u.startswith("mailto:") or u.startswith("tel:"):
                continue
            if re.match(r"https?://", u):
                if not re.match(r"https?://(localhost|127\.0\.0\.1)(:|/)", u):
                    external.append("%s -> %s" % (rel(p), u))
                continue
            t = os.path.normpath(os.path.join(os.path.dirname(p), u.split("?")[0]))
            if not os.path.exists(t):
                missing.append("%s -> %s" % (rel(p), u))
check(
    "S7 見本が自己完結している（相対参照の欠損なし・外部URLなし＝NFR-005）",
    not missing and not external,
    "欠損=%s / 外部=%s" % (missing or "なし", external or "なし"),
)

# --- S8 data-folder が samples/ を指している（mockups/ のまま同梱しない） --------
offenders = []
for d in SAMPLE_DIRS:
    for p in sorted(glob.glob(os.path.join(d, "*.html"))):
        html = open(p, encoding="utf-8").read()
        for v in re.findall(r'data-folder="([^"]*)"', html):
            if not v.startswith("samples/"):
                offenders.append("%s -> %s" % (rel(p), v))
check(
    "S8 見本の data-folder が samples/ を指している",
    not offenders,
    offenders or "なし",
)

print("=" * 78)
print("KLK-076 見本の実物検証チェッカー（R=規約テキスト / S=samples の実物）")
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
