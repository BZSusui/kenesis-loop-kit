# -*- coding: utf-8 -*-
"""
DADS A4/B5タテ テンプレート — 設計定数（唯一の正）

デジタル庁デザインシステム（DADS）の基本デザイン（カラー／タイポグラフィ／余白／
レイアウト）と、デジタル庁「ダッシュボードイメージ作成ツールキット」(16:9 pptx) の
実測値から導出した、印刷用テンプレートの寸法・書式定数。

判型ごとの違いは PROFILES に集約し、load(名前) が定数一式を返す（DADS-002）。
プロファイル依存の値はモジュール直下に置かない。用途を誤って A4 固定の値を掴むのを防ぐため。

    import spec
    S = spec.load("b5")     # -> SimpleNamespace(PAGE_W_MM=182.0, COL_W=..., T={...}, ...)

出典：デジタル庁デザインシステムウェブサイト https://design.digital.go.jp/dads/
（本ファイルはDADSの規定をA4・B5タテ印刷向けに加工したものです）
"""
from types import SimpleNamespace

# ---------------------------------------------------------------- 単位換算
# 1 CSS px = 0.75 pt = 9525 EMU / 1 mm = 36000 EMU
PX = 0.75 * 12700          # 1 CSS px を EMU で
MM = 36000                 # 1 mm を EMU で
PT = 12700                 # 1 pt を EMU で

def px2mm(v):  return v * 0.75 * 25.4 / 72.0
def mm2px(v):  return v / (0.75 * 25.4 / 72.0)

# ---------------------------------------------------------------- カラー
# デジタル庁「ダッシュボードイメージ作成ツールキット」のテーマ配色をそのまま採用
# （DADSのMarkdownにHEX値の定義は無い。色の出所はツールキットのテーマである）
PRIMARY   = "0C21BA"   # プライマリー
SECONDARY = "2E4EE7"   # セカンダリー
TERTIARY  = "4F7AE9"   # ターシャリー
ACCENT_4  = "99B0EC"
ACCENT_5  = "CFDCF0"
BG_TINT   = "F7F8FB"   # バックグラウンド（淡）
BG_TINT2  = "F7F9FC"
TEXT      = "000000"   # 本文・見出し
TEXT_SUB  = "626264"   # 補助テキスト・罫線
WHITE     = "FFFFFF"

# ---------------------------------------------------------------- ガイド線
# PowerPoint のガイド位置は 1/8 pt 単位（既定テンプレートの 4:3 中心線 2160/2880 で確認）
def guide_pos(mm):
    return int(round(mm * 72.0 / 25.4 * 8))

# PowerPoint の既定グリッド間隔 76200 EMU は 2.1167mm ＝ 余白スケールの基準単位と一致する
GRID_EMU = 76200

# ---------------------------------------------------------------- 出典
ATTRIBUTION = "出典：デジタル庁デザインシステムウェブサイト https://design.digital.go.jp/dads/"

# ---------------------------------------------------------------- タイポグラフィ
# DADS テキストスタイル(CSS px) -> pt (1px = 0.75pt)。
# 行高は spcPts（1/100pt）で CSS の line-height と厳密に一致させる。
# 字間 spc は 1/100pt（DADS の letter-spacing % をptへ換算）。
def style(px, bold, lh_pct, ls_pct):
    pt = px * 0.75
    return {
        "sz":   int(round(pt * 100)),                   # 1/100 pt
        "b":    bold,
        "lnPts": int(round(pt * lh_pct / 100 * 100)),   # 1/100 pt
        "spc":  int(round(pt * ls_pct / 100 * 100)),    # 1/100 pt
        "pt":   pt, "px": px, "lh": lh_pct, "ls": ls_pct,
    }


def _typography(base_px):
    """本文の基準サイズ(CSS px)からテキストスタイル一式を作る。

    使用するサイズは DADS のテキストスタイル表に実在するものに限る。
    Display 48/57/64、Standard 16/17/18/20/22/24/26/28/32/36/45、Dense 14/16/17。
    """
    if base_px == 16:
        # 名前              DADSトークン        px  bold  行高  字間
        return {
            "cover_title": style(48, True,  140, 0),   # Dsp-48B-140  36pt
            "cover_sub":   style(20, False, 150, 2),   # Std-20N-150  15pt
            "cover_meta":  style(16, False, 170, 2),   # Std-16N-170  12pt
            "section_no":  style(20, True,  150, 2),   # Std-20B-150  15pt
            "section_ttl": style(32, True,  150, 1),   # Std-32B-150  24pt
            "page_title":  style(24, True,  150, 2),   # Std-24B-150  18pt
            "h2":          style(20, True,  150, 2),   # Std-20B-150  15pt
            "h3":          style(16, True,  170, 2),   # Std-16B-170  12pt
            "body":        style(16, False, 170, 2),   # Std-16N-170  12pt
            "dense":       style(14, False, 130, 0),   # Dns-14N-130  10.5pt
            "dense_b":     style(14, True,  130, 0),   # Dns-14B-130  10.5pt
            "note":        style(14, False, 130, 0),   # Dns-14N-130  10.5pt
            "label":       style(14, True,  100, 2),   # Oln-14B-100  10.5pt
            "kpi_num":     style(32, True,  150, 1),   # Std-32B-150  24pt
        }
    if base_px == 14:
        # B5コンパクト用。本文が14pxになるため見出しを1段ずつ下げる。
        # 補助テキスト(dense/note/label)は14pxのまま据え置く
        # （DADSは14px未満を原則許容しないため）。本文と同サイズになるので、
        # 階層は色(TEXT_SUB)・ウェイト・行高(130%)で担保する。
        return {
            "cover_title": style(36, True,  140, 1),   # Std-36B-140  27pt
            "cover_sub":   style(18, False, 160, 2),   # Std-18N-160  13.5pt
            "cover_meta":  style(14, False, 130, 0),   # Dns-14N-130  10.5pt
            "section_no":  style(18, True,  160, 2),   # Std-18B-160  13.5pt
            "section_ttl": style(28, True,  150, 1),   # Std-28B-150  21pt
            "page_title":  style(20, True,  150, 2),   # Std-20B-150  15pt
            "h2":          style(18, True,  160, 2),   # Std-18B-160  13.5pt
            "h3":          style(16, True,  170, 2),   # Std-16B-170  12pt
            "body":        style(14, False, 170, 2),   # 14px・行高170%（後述の注記を参照）10.5pt
            "dense":       style(14, False, 130, 0),   # Dns-14N-130  10.5pt
            "dense_b":     style(14, True,  130, 0),   # Dns-14B-130  10.5pt
            "note":        style(14, False, 130, 0),   # Dns-14N-130  10.5pt
            "label":       style(14, True,  100, 2),   # Oln-14B-100  10.5pt
            "kpi_num":     style(28, True,  150, 1),   # Std-28B-150  21pt
        }
    raise ValueError(f"未対応の本文サイズです: {base_px}px（16 または 14）")


# ---------------------------------------------------------------- プロファイル
# 入力はこの4項目だけ。カラム幅・ガター・マージン・垂直リズムはすべて導出する。
#   BASE_PX  : 本文の文字サイズ(CSS px)
#   COL_MULT : カラム幅が本文文字サイズの何倍か（DADS: カラム幅は本文の整数倍）
#   MARGIN_U : 上下マージンが余白基準単位 U の何倍か
PROFILES = {
    "a4": dict(
        PAGE_W_MM=210.0, PAGE_H_MM=297.0, BASE_PX=16, COL_MULT=5, MARGIN_U=8,
        PAPER_NAME="A4タテ", LABEL="標準",
    ),
    "b5": dict(
        PAGE_W_MM=182.0, PAGE_H_MM=257.0, BASE_PX=16, COL_MULT=4, MARGIN_U=7,
        PAPER_NAME="B5タテ", LABEL="標準",
    ),
    "b5-compact": dict(
        PAGE_W_MM=182.0, PAGE_H_MM=257.0, BASE_PX=14, COL_MULT=5, MARGIN_U=7,
        PAPER_NAME="B5タテ", LABEL="コンパクト",
    ),
}

DEFAULT_PROFILE = "a4"


def load(name=DEFAULT_PROFILE):
    """プロファイル名から定数一式を持つ SimpleNamespace を返す。"""
    if name not in PROFILES:
        raise ValueError(
            f"未知のプロファイルです: {name!r}（指定できるのは {', '.join(PROFILES)}）")
    p = PROFILES[name]
    PAGE_W_MM = p["PAGE_W_MM"]
    PAGE_H_MM = p["PAGE_H_MM"]
    BASE_PX   = p["BASE_PX"]
    COL_MULT  = p["COL_MULT"]

    # ------------------------------------------------------------ 余白スケール
    # DADS 余白: 基準単位 8 CSS px の倍率スケールを 5 段階に絞る
    U  = px2mm(8)              # 2.1167 mm  (= 8px = 6pt)
    S1 = U * 1                 #  2.117 mm  ( 8px)
    S2 = U * 2                 #  4.233 mm  (16px)
    S3 = U * 3                 #  6.350 mm  (24px)
    S4 = U * 4                 #  8.467 mm  (32px)
    S8 = U * 8                 # 16.933 mm  (64px)

    # ------------------------------------------------------------ グリッド
    # DADS レイアウト: マージン／カラム／ガター。
    #   ガター   = 本文文字サイズの2倍
    #   カラム幅 = 本文文字サイズの整数倍（COL_MULT 倍）
    #   マージンは残差として決まる（A4タテ幅は12カラムには狭いため6カラム。DADSはカラム数を規定しない）
    COLS      = 6
    COL_W     = px2mm(BASE_PX * COL_MULT)
    GUTTER    = px2mm(BASE_PX * 2)
    CONTENT_W = COLS * COL_W + (COLS - 1) * GUTTER
    MARGIN_X  = (PAGE_W_MM - CONTENT_W) / 2
    LEFT      = MARGIN_X
    RIGHT     = PAGE_W_MM - MARGIN_X

    def col_x(i):
        """左から i 番目(0起点)のカラム左端 X(mm)"""
        return LEFT + i * (COL_W + GUTTER)

    def span_w(n):
        """n カラム分の幅(mm)"""
        return n * COL_W + (n - 1) * GUTTER

    HALF_W = span_w(3)         # 2カラムレイアウトの片側

    # ------------------------------------------------------------ 垂直リズム
    MARGIN_T = U * p["MARGIN_U"]
    MARGIN_B = U * p["MARGIN_U"]

    EYEBROW_Y = MARGIN_T
    EYEBROW_H = U * 2.5
    TITLE_Y   = EYEBROW_Y + EYEBROW_H + S1
    TITLE_H   = U * 4.5
    RULE_Y    = TITLE_Y + TITLE_H + S2
    RULE_H    = 0.5                            # 見出し罫 0.5mm
    BODY_TOP  = RULE_Y + RULE_H + S3

    FOOT_BOT  = PAGE_H_MM - MARGIN_B
    FOOT_H    = U * 2.5
    FOOT_Y    = FOOT_BOT - FOOT_H
    FRULE_H   = 0.2                            # フッター罫 0.2mm
    FRULE_Y   = FOOT_Y - S1 - FRULE_H
    BODY_BOT  = FRULE_Y - S3
    BODY_H    = BODY_BOT - BODY_TOP

    T = _typography(BASE_PX)

    # ------------------------------------------------------------ ガイド線
    GUIDES = [
        ("vert", LEFT,                   "版面 左端"),
        ("vert", LEFT + HALF_W,          "2カラム 左側の右端"),
        ("vert", LEFT + HALF_W + GUTTER, "2カラム 右側の左端"),
        ("vert", RIGHT,                  "版面 右端"),
        ("horz", MARGIN_T,               "上マージン（ヘッダー上端）"),
        ("horz", BODY_TOP,               "本文 上端"),
        ("horz", BODY_BOT,               "本文 下端"),
        ("horz", FOOT_BOT,               "下マージン（フッター下端）"),
    ]

    ATTRIBUTION_NOTE = (
        f"本テンプレートはDADSの規定を{p['PAPER_NAME']}印刷向けに加工したものであり、"
        "デジタル庁が作成したものではありません。")

    ns = dict(
        PROFILE=name, PAPER_NAME=p["PAPER_NAME"], LABEL=p["LABEL"],
        BASE_PX=BASE_PX, COL_MULT=COL_MULT,
        PAGE_W_MM=PAGE_W_MM, PAGE_H_MM=PAGE_H_MM,
        PX=PX, MM=MM, PT=PT, px2mm=px2mm, mm2px=mm2px,
        U=U, S1=S1, S2=S2, S3=S3, S4=S4, S8=S8,
        COLS=COLS, COL_W=COL_W, GUTTER=GUTTER, CONTENT_W=CONTENT_W,
        MARGIN_X=MARGIN_X, LEFT=LEFT, RIGHT=RIGHT,
        col_x=col_x, span_w=span_w, HALF_W=HALF_W,
        MARGIN_T=MARGIN_T, MARGIN_B=MARGIN_B,
        EYEBROW_Y=EYEBROW_Y, EYEBROW_H=EYEBROW_H,
        TITLE_Y=TITLE_Y, TITLE_H=TITLE_H,
        RULE_Y=RULE_Y, RULE_H=RULE_H, BODY_TOP=BODY_TOP,
        FOOT_BOT=FOOT_BOT, FOOT_H=FOOT_H, FOOT_Y=FOOT_Y,
        FRULE_H=FRULE_H, FRULE_Y=FRULE_Y, BODY_BOT=BODY_BOT, BODY_H=BODY_H,
        PRIMARY=PRIMARY, SECONDARY=SECONDARY, TERTIARY=TERTIARY,
        ACCENT_4=ACCENT_4, ACCENT_5=ACCENT_5,
        BG_TINT=BG_TINT, BG_TINT2=BG_TINT2,
        TEXT=TEXT, TEXT_SUB=TEXT_SUB, WHITE=WHITE,
        T=T, style=style,
        guide_pos=guide_pos, GUIDES=GUIDES, GRID_EMU=GRID_EMU,
        ATTRIBUTION=ATTRIBUTION, ATTRIBUTION_NOTE=ATTRIBUTION_NOTE,
    )
    return SimpleNamespace(**ns)
