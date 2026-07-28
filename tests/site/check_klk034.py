#!/usr/bin/env python3
"""
KLK-034 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions R群/U群/T群 from
docs/designs/KLK-034.md §4.6 / §9 against 参考準拠生成（案A=カタログ準拠・席替え規則・§5.1/§12.2）:

  縦串 生成規約     .claude/skills/draft-generate/templates/DRAFT_RULES.md（§5.1 / §12.2）
  縦串 スキル定義   .claude/skills/draft-generate/SKILL.md（手順3・してはならないこと）
  縦串 UI/ブリッジ  draft-gen/index.html（トグル・selectedThumbs 拡張）・draft-gen/bridge.py（validate_instruction）
  主 golden         tests/fixtures/klk034/{index-a/b/c,compare}.html + instruction.json
                    （席替え/無衝突/other/省略/プール直採用/プール席替え＋§5.1 ブルー/ゴールド表引き）
  副 golden         tests/fixtures/klk034b/{index-a/b/c,compare}.html + instruction.json
                    （マルチカラー→指定色フォールバック＋HERO=band 参考採用で案C席替え）

Source of truth = 設計書 §4.6。check_klk029.py と同型（正規表現・文字列検索・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。期待値は instruction.json から
§12.2 席替え規則のミラー実装で機械的に導出し、golden の実マーカーと突き合わせる（決定性の固定）。

Run: python3 tests/site/check_klk034.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md"), encoding="utf-8").read()
REGEN = open(os.path.join(ROOT, ".claude", "skills", "draft-regenerate", "SKILL.md"), encoding="utf-8").read()
INDEX = open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()

sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402  (validate_instruction の機能検証 T群に使用)

NEW_COLS = {"1col", "2col-full-left", "2col-full-right", "2col-body-left", "2col-body-right", "3col"}
ARCHETYPE_ENUM = {"stack-centered", "split-editorial", "banded-showcase"}

# §12.1.1 の既定型（席替えの参照表・DRAFT_RULES §12.2 のミラー・MENU のみ。
# GALLERY(KLK-036)・HERO/ABOUT(KLK-037) は §12.1.3 プールへ移譲したため本表から除外）
DEFAULT_1211 = {
    "MENU": ("pat-cards", "pat-list", "pat-zigzag"),
}

# §12.1.3 セクション別独立プール（4型・index0-3）と割り当て（巡回 mod 4・オフセット表は §12.1.2 共有・KLK-036/037）
GALLERY_POOL = ["pat-grid", "pat-wide", "pat-mosaic", "pat-slider"]
HERO_POOL = ["full", "split", "band", "overlap"]
ABOUT_POOL = ["img-left", "img-right", "img-top", "img-overlap"]
POOL_1213 = {"HERO": HERO_POOL, "GALLERY": GALLERY_POOL, "ABOUT": ABOUT_POOL}
GALLERY_ASSIGN = {0: (0, 1, 2), 1: (1, 2, 3), 2: (2, 3, 0), 3: (3, 0, 1), 4: (0, 1, 2), 5: (1, 2, 3)}  # 4型プール共通(mod4)

# §12.1.2 型プール・オフセット表・割り当て表（check_klk029.py と同一ミラー）
POOL = {
    "VOICE": ["voice-cards", "voice-quote-stack", "voice-feature", "voice-two-col", "voice-slider", "voice-zigzag"],
    "FLOW": ["flow-row", "flow-timeline", "flow-number-card", "flow-arrow-band", "flow-vertical-split", "flow-zigzag"],
    "STAFF": ["staff-grid", "staff-hscroll", "staff-feature", "staff-list", "staff-two-col", "staff-zigzag"],
}
OFFSET = {
    ("1col", "top"): 0, ("1col", "below-hero"): 3,
    ("2col-full-left", "top"): 1, ("2col-full-left", "below-hero"): 4,
    ("2col-full-right", "top"): 2, ("2col-full-right", "below-hero"): 0,
    ("2col-body-left", "top"): 3, ("2col-body-left", "below-hero"): 1,
    ("2col-body-right", "top"): 4, ("2col-body-right", "below-hero"): 2,
    ("3col", "top"): 5, ("3col", "below-hero"): 3,
}
ASSIGN = {0: (0, 1, 2), 1: (1, 2, 3), 2: (2, 3, 4), 3: (3, 4, 5), 4: (4, 5, 0), 5: (5, 0, 1)}

# §5.1 7カテゴリ→hex 変換表（DRAFT_RULES §5.1 のミラー・小文字比較）
HEX7 = {
    "グリーン": "#2e7d6b",
    "ブルー": "#2c5f8a",
    "レッド": "#b3402f",
    "ゴールド": "#c6a15b",
    "ピンク": "#e86fa0",
    "モノトーン": "#444850",
}

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def attr(html, name):
    m = re.search(r'%s="([^"]+)"' % re.escape(name), html)
    return m.group(1) if m else None


def modifier(html, base, prefix):
    m = re.search(r'class="%s (%s[a-z-]+)"' % (base, prefix), html)
    return m.group(1) if m else None


def all_pins(html):
    return set(re.findall(r'class="pin">([A-Z0-9-]+)<', html))


def css_var(html, var):
    m = re.search(r"%s\s*:\s*(#[0-9a-fA-F]{3,8})" % re.escape(var), html)
    return m.group(1).lower() if m else None


def css_layout_rule(html, token):
    """.token を含む CSS セレクタが実レイアウト宣言（grid/flex/order 等）を持つか（飾り禁止・N7同型）。"""
    if not token:
        return False
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


def expected_1211(key, ref_v):
    """§12.2 席替え規則のミラー（§12.1.1 系 HERO/MENU/ABOUT）: 参考の値 v から (案A,案B,案C) の期待型を導く。"""
    a, b, c = DEFAULT_1211[key]
    if ref_v is None or ref_v == "other" or ref_v not in (a, b, c):
        return (a, b, c)  # キー省略・other・語彙外は従来のまま
    exp = [ref_v, b, c]
    if ref_v == b:
        exp[1] = a  # 席替え: 案B := 案A既定
    elif ref_v == c:
        exp[2] = a  # 席替え: 案C := 案A既定
    return tuple(exp)


def expected_1213(key, ref_v, gidxs):
    """§12.2 席替え規則のミラー（§12.1.3 系 GALLERY/HERO/ABOUT・KLK-036/037）: 表引き gidxs=(ia,ib,ic) に参考 v を適用。"""
    pool = POOL_1213[key]
    ia, ib, ic = gidxs
    if ref_v is None or ref_v == "other" or ref_v not in pool:
        return (pool[ia], pool[ib], pool[ic])
    r = pool.index(ref_v)
    exp = [pool[r], pool[ib], pool[ic]]
    if r == ib:
        exp[1] = pool[ia]
    elif r == ic:
        exp[2] = pool[ia]
    return tuple(exp)


def expected_pool(key, ref_v, idxs):
    """§12.2 席替え規則（§12.1.2 系）のミラー: 表引き (idxA,idxB,idxC) に参考 v を適用。"""
    pool = POOL[key]
    ia, ib, ic = idxs
    if ref_v is None or ref_v not in pool:
        return (pool[ia], pool[ib], pool[ic])
    r = pool.index(ref_v)
    exp = [pool[r], pool[ib], pool[ic]]
    if r == ib:
        exp[1] = pool[ia]
    elif r == ic:
        exp[2] = pool[ia]
    return tuple(exp)


class Golden:
    """1つの golden セット（klk034 or klk034b）と、instruction からの §12.2/§5.1 期待値を保持する。"""

    def __init__(self, name):
        self.name = name
        fx = os.path.join(ROOT, "tests", "fixtures", name)
        self.A = open(os.path.join(fx, "index-a.html"), encoding="utf-8").read()
        self.B = open(os.path.join(fx, "index-b.html"), encoding="utf-8").read()
        self.C = open(os.path.join(fx, "index-c.html"), encoding="utf-8").read()
        self.COMPARE = open(os.path.join(fx, "compare.html"), encoding="utf-8").read()
        self.INSTR = json.load(open(os.path.join(fx, "instruction.json"), encoding="utf-8"))
        self.goldens = (("a", self.A), ("b", self.B), ("c", self.C))

        refs = self.INSTR.get("references") or {}
        thumbs = refs.get("thumbnails") or []
        self.thumb = thumbs[0] if thumbs else {}
        self.sl = self.thumb.get("sectionLayouts") or {}
        self.ref_colors = self.thumb.get("colors") or []
        self.color_source = refs.get("colorSource")
        # 実効の配色ソース（マルチカラーは指定色フォールバック・§5.1）
        self.effective = "specified" if (
            self.color_source != "reference" or not self.ref_colors
            or self.ref_colors[0] == "マルチカラー") else "reference"

        self.sections = self.INSTR.get("sections", [])
        self.columns = self.INSTR["layout"]["columns"]
        self.nav = self.INSTR["layout"].get("navPosition", "top")
        self.idxs = ASSIGN[OFFSET[(self.columns, self.nav)]]
        self.gallery_idxs = GALLERY_ASSIGN[OFFSET[(self.columns, self.nav)]]  # §12.1.3 GALLERY 用（mod4）

        self.DC = [attr(h, "data-columns") for _, h in self.goldens]
        self.AR = [attr(h, "data-archetype") for _, h in self.goldens]
        self.ORDER = [attr(h, "data-section-order") for _, h in self.goldens]
        self.HERO = [attr(h, "data-hero") for _, h in self.goldens]
        self.MENU = [modifier(h, "m-menu", "pat-") for _, h in self.goldens]
        self.GALLERY = [modifier(h, "m-gallery", "pat-") for _, h in self.goldens]
        self.ABOUT = [modifier(h, "m-about", "img-") for _, h in self.goldens]
        self.VOICE = [modifier(h, "m-voice", "voice-") for _, h in self.goldens]
        self.FLOW = [modifier(h, "m-flow", "flow-") for _, h in self.goldens]
        self.STAFF = [modifier(h, "m-staff", "staff-") for _, h in self.goldens]
        self.REF_ID = [attr(h, "data-ref-id") for _, h in self.goldens]
        self.REF_COLORS = [attr(h, "data-ref-colors") for _, h in self.goldens]
        self.MM = [css_var(h, "--m-main") for _, h in self.goldens]

    def actual(self, key):
        return {"HERO": self.HERO, "MENU": self.MENU, "GALLERY": self.GALLERY, "ABOUT": self.ABOUT,
                "VOICE": self.VOICE, "FLOW": self.FLOW, "STAFF": self.STAFF}[key]


G = [Golden("klk034"), Golden("klk034b")]

# ---------------------------------------------------------------------------
# R群: golden 検証（席替え・表引き・配色・マーカー・不変条件）
# ---------------------------------------------------------------------------

# R1 参考マーカー: 案Aのみ data-ref-id（=thumbnails[0].id）と data-ref-colors（=実効ソース）を持つ
r1_ok = True
r1_det = []
for g in G:
    ok = (g.REF_ID[0] == g.thumb.get("id") and g.REF_COLORS[0] == g.effective
          and g.REF_ID[1] is None and g.REF_ID[2] is None
          and g.REF_COLORS[1] is None and g.REF_COLORS[2] is None)
    r1_ok = r1_ok and ok
    r1_det.append(f"{g.name}: a=({g.REF_ID[0]},{g.REF_COLORS[0]}) b/c無し={g.REF_ID[1] is None and g.REF_ID[2] is None}")
check("R1 参考マーカー (案Aのみ data-ref-id=thumbnails[0].id・data-ref-colors=実効ソース。案B/Cは無し)",
      r1_ok, "; ".join(r1_det))

# R2 §12.1.1 系: HERO/MENU/GALLERY/ABOUT の実マーカーが席替え規則の期待と一致
r2_ok = True
r2_det = []
for g in G:
    for key in ("HERO", "MENU", "GALLERY", "ABOUT"):
        if key != "HERO" and key not in g.sections:
            continue  # sections に無いセクションは出ない（HERO は常設）
        # GALLERY/HERO/ABOUT は §12.1.3 プール基準（KLK-036/037）・MENU のみ §12.1.1 系
        if key in ("HERO", "GALLERY", "ABOUT"):
            exp = expected_1213(key, g.sl.get(key), g.gallery_idxs)
        else:
            exp = expected_1211(key, g.sl.get(key))
        act = tuple(g.actual(key))
        ok = act == exp
        r2_ok = r2_ok and ok
        r2_det.append(f"{g.name}/{key}: 期待{exp} 実{act} {'OK' if ok else 'NG'}")
check("R2 席替え (MENU=§12.1.1系・HERO/GALLERY/ABOUT=§12.1.3系 が §12.2 規則適用後の期待と一致)",
      r2_ok, "; ".join(d for d in r2_det if "NG" in d) or f"{len(r2_det)}軸すべて期待どおり")

# R3 §12.1.2 系: VOICE/FLOW/STAFF の実マーカーが (表引き＋席替え) の期待と一致
r3_ok = True
r3_det = []
for g in G:
    for key in ("VOICE", "FLOW", "STAFF"):
        if key not in g.sections:
            absent = all(v is None for v in g.actual(key))
            r3_ok = r3_ok and absent
            if not absent:
                r3_det.append(f"{g.name}/{key}: sectionsに無いのに出現")
            continue
        exp = expected_pool(key, g.sl.get(key), g.idxs)
        act = tuple(g.actual(key))
        ok = act == exp
        r3_ok = r3_ok and ok
        r3_det.append(f"{g.name}/{key}: 期待{exp} 実{act} {'OK' if ok else 'NG'}")
check("R3 §12.1.2 席替え (VOICE/FLOW/STAFF が表引き＋§12.2 規則適用後の期待と一致・未選択は不出現)",
      r3_ok, "; ".join(d for d in r3_det if "NG" in d or "出現" in d) or f"{len(r3_det)}軸すべて期待どおり")

# R4 3案 distinct の維持（席替えの狙い＝既存不変条件の非破壊）＋各マーカーが実CSSを伴う
r4_ok = True
r4_det = []
for g in G:
    for key in ("HERO", "MENU", "GALLERY", "ABOUT", "VOICE", "FLOW", "STAFF"):
        if key != "HERO" and key not in g.sections:
            continue
        vals = g.actual(key)
        d = distinct3(vals)
        r4_ok = r4_ok and d
        if not d:
            r4_det.append(f"{g.name}/{key}: {vals} が distinct でない")
    for letter, h in g.goldens:
        for base, prefix in (("m-menu", "pat-"), ("m-gallery", "pat-"), ("m-about", "img-"),
                             ("m-voice", "voice-"), ("m-flow", "flow-"), ("m-staff", "staff-")):
            tok = modifier(h, base, prefix)
            if tok and not css_layout_rule(h, tok):
                r4_ok = False
                r4_det.append(f"{g.name}/{letter}/{tok}: 実CSSなし(飾り)")
check("R4 3案 distinct の維持＋各マーカーが実 grid/flex/order を伴う (§12.1.1⑥⑦⑧⑨・§12.1.2 不変条件)",
      r4_ok, "; ".join(r4_det) if r4_det else "全軸 distinct・全マーカー実CSSあり")

# R5 §5.1 配色: 案A --m-main/--m-accent が表引き（klk034）／マルチカラーは指定色のまま（klk034b）
r5_ok = True
r5_det = []
for g in G:
    if g.effective == "reference":
        want_main = HEX7.get(g.ref_colors[0])
        want_accent = HEX7.get(g.ref_colors[1]) if len(g.ref_colors) >= 2 else None
        ok = g.MM[0] == want_main
        acc = css_var(g.A, "--m-accent")
        if want_accent is not None:
            ok = ok and acc == want_accent
        r5_det.append(f"{g.name}: 案A main={g.MM[0]}(期待{want_main}) accent={acc}(期待{want_accent})")
    else:
        want_main = str(g.INSTR["colors"]["main"]).lower()
        ok = g.MM[0] == want_main
        r5_det.append(f"{g.name}: フォールバック 案A main={g.MM[0]}(期待=指定色{want_main})")
    ok = ok and distinct3(g.MM)  # 案間 --m-main 相違は維持
    r5_ok = r5_ok and ok
check("R5 §5.1 配色 (案A=7カテゴリ表引き／マルチカラーは指定色フォールバック。案間 --m-main 相違維持)",
      r5_ok, "; ".join(r5_det))

# R6 既存不変条件: data-columns 同一/enum・archetype distinct/enum・section-order distinct かつ同一集合・番地整合
r6_ok = True
r6_det = []
for g in G:
    dc_ok = len(set(g.DC)) == 1 and g.DC[0] in NEW_COLS
    ar_ok = distinct3(g.AR) and all(a in ARCHETYPE_ENUM for a in g.AR)
    orders = [tuple((o or "").split(",")) for o in g.ORDER]
    od_ok = distinct3(g.ORDER) and len({tuple(sorted(o)) for o in orders}) == 1 \
        and set(orders[0]) == set(g.sections)
    want_pins = {k + "-01" for k in g.sections} | {"NAV-01", "MV-01", "FOOTER-01"}
    pins_ok = all(all_pins(h) == want_pins for _, h in g.goldens)
    ok = dc_ok and ar_ok and od_ok and pins_ok
    r6_ok = r6_ok and ok
    r6_det.append(f"{g.name}: columns={dc_ok} archetype={ar_ok} order={od_ok} 番地={pins_ok}")
check("R6 既存不変条件 (data-columns 同一・archetype distinct・order distinct/同一集合・番地=選択集合+3)",
      r6_ok, "; ".join(r6_det))

# R7 compare.html: 案Aカードに .ref-badge（label+id+着想のみ文言）・外部URL 0
r7_ok = True
r7_det = []
for g in G:
    c = g.COMPARE
    badge = 'class="ref-badge"' in c
    label_ok = (g.thumb.get("label", "") in c) and (g.thumb.get("id", "") in c)
    phrase = "参考は着想のみ・そっくり再現はしません" in c
    ext = no_ext_deps(c)
    ok = badge and label_ok and phrase and ext
    r7_ok = r7_ok and ok
    r7_det.append(f"{g.name}: badge={badge} label/id={label_ok} 文言={phrase} 依存0={ext}")
check("R7 compare.html (.ref-badge＋参考label/id＋「着想のみ」文言・外部依存0)",
      r7_ok, "; ".join(r7_det))

# R8 各案の健全性: @media print・アタリa方式・外部依存0・プレースホルダ明記・秘密0
secret_re = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
r8_ok = True
r8_det = []
for g in G:
    for letter, h in list(g.goldens) + [("compare", g.COMPARE)]:
        prt = "@media print" in h
        atari = ('class="atari"' in h and 'class="desc"' in h) if letter != "compare" else True
        solo = no_ext_deps(h)
        ph = ("プレースホルダ" in h or "実在の顧客" in h or "サンプル" in h)
        sec = [ln for ln, line in enumerate(h.splitlines(), 1) if secret_re.search(line)]
        ok = prt and atari and solo and ph and not sec
        r8_ok = r8_ok and ok
        if not ok:
            r8_det.append(f"{g.name}/{letter}: print={prt} アタリ={atari} 依存0={solo} PH={ph} 秘密={sec or 0}")
check("R8 健全性 (@media print・アタリa方式・外部依存0・プレースホルダ明記・秘密0)",
      r8_ok, "; ".join(r8_det) if r8_det else "両 golden 全8ファイルで健全")

# ---------------------------------------------------------------------------
# U群: SCR-001 (draft-gen/index.html) 静的検査
# ---------------------------------------------------------------------------

# U1 配色トグルUI（refColorRow・name=refColorSource・reference/specified・既定 reference）
u1_row = 'id="refColorRow"' in INDEX
u1_ref = 'name="refColorSource" value="reference" checked' in INDEX
u1_spec = 'name="refColorSource" value="specified"' in INDEX
u1_note = "最初に選択した1件" in INDEX
u1 = u1_row and u1_ref and u1_spec and u1_note
check("U1 SCR-001 配色トグル (refColorRow・reference既定/specified・先頭1件の注記)", u1,
      f"row={u1_row}, radio既定={u1_ref}, specified={u1_spec}, 注記={u1_note}")

# U2 selectedThumbs/cardHtml/loadCatalog の拡張（colors/sectionLayouts/source の伝搬）
u2 = ("data-source=" in INDEX and "data-sl=" in INDEX          # cardHtml が data-* を焼く
      and "dataset.sl" in INDEX and "dataset.source" in INDEX  # selectedThumbs が抽出する
      and "t.sectionLayouts = sl" in INDEX and "t.colors = colors" in INDEX
      and "o.sectionLayouts = t.sectionLayouts" in INDEX)      # buildInstruction が指示書へ写す
check("U2 タグ伝搬 (cardHtml data-source/data-sl → selectedThumbs → buildInstruction)", u2,
      "cardHtml/selectedThumbs/buildInstruction の3点で colors・sectionLayouts・source を伝搬")

# U3 colorSource の付与（サムネ選択時のみ）とトグル表示制御
u3 = ("refs.colorSource" in INDEX and "thumbs.length > 0" in INDEX
      and INDEX.count("refColorRow") >= 2)  # UI定義＋updateThumbCount の表示制御
check("U3 colorSource 付与 (選択時のみ references.colorSource・updateThumbCount で表示制御)", u3,
      f"refs.colorSource={'refs.colorSource' in INDEX}, 表示制御={INDEX.count('refColorRow') >= 2}")

# ---------------------------------------------------------------------------
# T群: 規約文言・ブリッジ検証（機能）
# ---------------------------------------------------------------------------

# T1 DRAFT_RULES: §5.1 表（6hex 全部）・§12.2（席替え・そっくり再現禁止・マーカー2種・ref-badge）
t1_hex = [h for h in ("#2C5F8A", "#B3402F", "#C6A15B", "#E86FA0", "#444850", "#2E7D6B") if h not in RULES]
t1 = ("### 5.1" in RULES and "### 12.2" in RULES and not t1_hex
      and "席替え" in RULES and "そっくり再現" in RULES
      and "data-ref-id" in RULES and "data-ref-colors" in RULES and "ref-badge" in RULES
      and "thumbnails[0]" in RULES)
check("T1 DRAFT_RULES (§5.1 hex表6色・§12.2 席替え/そっくり再現禁止/マーカー/ref-badge/先頭1件)", t1,
      f"§5.1={'### 5.1' in RULES}, §12.2={'### 12.2' in RULES}, 欠落hex={t1_hex or 0}")

# T2 SKILL: 手順3 の参考準拠 bullet ＋ してはならないこと の複製禁止
t2 = ("参考準拠" in SKILL and "§12.2" in SKILL and "thumbnails[0]" in SKILL
      and "そっくり再現" in SKILL and "着想の反映に限る" in SKILL)
check("T2 SKILL.md (手順3 参考準拠・§12.2/§5.1 参照・そっくり再現禁止)", t2,
      f"参考準拠={'参考準拠' in SKILL}, 禁止規律={'着想の反映に限る' in SKILL}")

# T3 bridge.validate_instruction の additive 検証（機能テスト・後方互換含む）
BASE = {
    "schema": "design-draft-instruction", "version": 1,
    "industry": {"resolved": "美容・ヘアサロン"},
    "layout": {"columns": "1col"},
    "colors": {"main": "#2e7d6b"},
}


def _with_refs(refs):
    obj = json.loads(json.dumps(BASE))
    obj["references"] = refs
    return obj


_t = {"id": "cat-9034", "label": "x", "tags": []}
t3_cases = [
    ("旧指示書(references無し)はOK", bridge.validate_instruction(BASE)[0] is True),
    ("正常な拡張キーはOK", bridge.validate_instruction(_with_refs({
        "thumbnails": [dict(_t, colors=["ブルー", "ゴールド"],
                            sectionLayouts={"HERO": "split"}, source="ref")],
        "sampleUrls": [], "colorSource": "reference"}))[0] is True),
    ("colorSource不正はNG", bridge.validate_instruction(_with_refs(
        {"thumbnails": [], "sampleUrls": [], "colorSource": "auto"}))[0] is False),
    ("colors 7カテゴリ外はNG", bridge.validate_instruction(_with_refs(
        {"thumbnails": [dict(_t, colors=["ベージュ"])], "sampleUrls": []}))[0] is False),
    ("マルチカラー併用はNG", bridge.validate_instruction(_with_refs(
        {"thumbnails": [dict(_t, colors=["マルチカラー", "ピンク"])], "sampleUrls": []}))[0] is False),
    ("colors 4件はNG", bridge.validate_instruction(_with_refs(
        {"thumbnails": [dict(_t, colors=["ブルー", "ピンク", "レッド", "ゴールド"])], "sampleUrls": []}))[0] is False),
    ("sectionLayouts 値が空はNG", bridge.validate_instruction(_with_refs(
        {"thumbnails": [dict(_t, sectionLayouts={"HERO": ""})], "sampleUrls": []}))[0] is False),
    ("source 不正はNG", bridge.validate_instruction(_with_refs(
        {"thumbnails": [dict(_t, source="web")], "sampleUrls": []}))[0] is False),
]
t3_fail = [n for n, ok in t3_cases if not ok]
check("T3 bridge.validate_instruction (present時のみ検証・後方互換・不正値拒否の8ケース)",
      not t3_fail, f"失敗ケース={t3_fail or '無し'}")

# T5 部分再生成の参考準拠保持（レビュー指摘 2026-07-26）: DRAFT_RULES §14 と draft-regenerate SKILL の双方に
#    「data-ref-id があるファイルは対象セクションの現行マーカーを保持（表引き既定へ戻さない）」の規則があること
def _keep_tokens(txt):
    return ("data-ref-id" in txt and "現行マーカー" in txt and "参考準拠の保持" in txt
            and "フォールバック" in txt)


t5_rules = _keep_tokens(RULES)
t5_regen = _keep_tokens(REGEN)
t5_xref = "部分再生成（§14）との整合" in RULES  # §12.2 側の相互参照
check("T5 部分再生成の参考準拠保持 (§14・draft-regenerate SKILL に現行マーカー保持規則・§12.2 相互参照)",
      t5_rules and t5_regen and t5_xref,
      f"DRAFT_RULES §14={t5_rules}, draft-regenerate SKILL={t5_regen}, §12.2相互参照={t5_xref}")

# T4 golden の instruction.json 自体が validate_instruction を通る（多層防御との整合）
t4_fail = []
for g in G:
    ok, errs = bridge.validate_instruction(g.INSTR)
    if not ok:
        t4_fail.append(f"{g.name}: {errs}")
check("T4 golden instruction.json が validate_instruction を通過", not t4_fail,
      "; ".join(t4_fail) or "両 instruction とも通過")

# Report
print("=" * 78)
print("KLK-034 static acceptance checks (docs/designs/KLK-034.md §4.6 R/U/T群 を正とする)")
print("対象: fixtures/klk034・klk034b + DRAFT_RULES/SKILL + draft-gen/index.html + bridge.py")
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
print("D群（test_palette_klk034.py）: Quality Gate 全緑 / fixtures の git 追跡")
print("M群（tester 手動・ブラウザ）: SCR-001 でサムネ選択→トグル表示、実生成で案Aが参考準拠になる")
sys.exit(1 if failed else 0)
