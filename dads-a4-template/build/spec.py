# -*- coding: utf-8 -*-
"""
DADS A4タテ テンプレート — 設計定数（唯一の正）

デジタル庁デザインシステム（DADS）の基本デザイン（カラー／タイポグラフィ／余白／
レイアウト）と、デジタル庁「ダッシュボードイメージ作成ツールキット」(16:9 pptx) の
実測値から導出した、A4タテ（210 x 297mm）用の寸法・書式定数。

出典：デジタル庁デザインシステムウェブサイト https://design.digital.go.jp/dads/
（本ファイルはDADSの規定をA4タテ印刷向けに加工したものです）
"""

# ---------------------------------------------------------------- 単位換算
# 1 CSS px = 0.75 pt = 9525 EMU / 1 mm = 36000 EMU
PX = 0.75 * 12700          # 1 CSS px を EMU で
MM = 36000                 # 1 mm を EMU で
PT = 12700                 # 1 pt を EMU で

def px2mm(v):  return v * 0.75 * 25.4 / 72.0
def mm2px(v):  return v / (0.75 * 25.4 / 72.0)

# ---------------------------------------------------------------- 用紙
PAGE_W_MM = 210.0
PAGE_H_MM = 297.0

# ---------------------------------------------------------------- 余白スケール
# DADS 余白: 基準単位 8 CSS px の倍率スケールを 5 段階に絞る
U = px2mm(8)               # 2.1167 mm  (= 8px = 6pt)
S1 = U * 1                 #  2.117 mm  ( 8px)
S2 = U * 2                 #  4.233 mm  (16px)
S3 = U * 3                 #  6.350 mm  (24px)
S4 = U * 4                 #  8.467 mm  (32px)
S8 = U * 8                 # 16.933 mm  (64px)

# ---------------------------------------------------------------- グリッド
# DADS レイアウト: マージン／カラム／ガター。
#   ガター = 本文文字サイズ(16px)の2倍 = 32px = S4
#   カラム幅 = 本文文字サイズの整数倍 = 16px x 5 = 80px
#   A4タテ幅は 12 カラムには狭いため 6 カラムを採用（DADSはカラム数を規定しない）
COLS      = 6
COL_W     = px2mm(80)      # 21.167 mm
GUTTER    = S4             #  8.467 mm
CONTENT_W = COLS * COL_W + (COLS - 1) * GUTTER      # 169.333 mm
MARGIN_X  = (PAGE_W_MM - CONTENT_W) / 2             #  20.333 mm
LEFT      = MARGIN_X
RIGHT     = PAGE_W_MM - MARGIN_X

def col_x(i):
    """左から i 番目(0起点)のカラム左端 X(mm)"""
    return LEFT + i * (COL_W + GUTTER)

def span_w(n):
    """n カラム分の幅(mm)"""
    return n * COL_W + (n - 1) * GUTTER

HALF_W = span_w(3)         # 80.433 mm  2カラムレイアウトの片側

# ---------------------------------------------------------------- 垂直リズム
MARGIN_T = S8              # 16.933 mm
MARGIN_B = S8              # 16.933 mm

EYEBROW_Y = MARGIN_T                       #  16.933
EYEBROW_H = U * 2.5                        #   5.292
TITLE_Y   = EYEBROW_Y + EYEBROW_H + S1     #  24.342
TITLE_H   = U * 4.5                        #   9.525
RULE_Y    = TITLE_Y + TITLE_H + S2         #  38.100
RULE_H    = 0.5                            # 見出し罫 0.5mm
BODY_TOP  = RULE_Y + RULE_H + S3           #  44.950

FOOT_BOT   = PAGE_H_MM - MARGIN_B          # 280.067
FOOT_H     = U * 2.5                       #   5.292
FOOT_Y     = FOOT_BOT - FOOT_H             # 274.775
FRULE_H    = 0.2                           # フッター罫 0.2mm
FRULE_Y    = FOOT_Y - S1 - FRULE_H         # 272.458
BODY_BOT   = FRULE_Y - S3                  # 266.108
BODY_H     = BODY_BOT - BODY_TOP           # 221.158

# ---------------------------------------------------------------- カラー
# デジタル庁「ダッシュボードイメージ作成ツールキット」のテーマ配色をそのまま採用
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

T = {
    # 名前              DADSトークン        px  bold  行高  字間
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

# ---------------------------------------------------------------- ガイド線
# PowerPoint のガイド位置は 1/8 pt 単位（既定テンプレートの 4:3 中心線 2160/2880 で確認）
def guide_pos(mm):
    return int(round(mm * 72.0 / 25.4 * 8))

# (orient, mm, 説明)
GUIDES = [
    ("vert", LEFT,            "版面 左端"),
    ("vert", LEFT + HALF_W,   "2カラム 左側の右端"),
    ("vert", LEFT + HALF_W + GUTTER, "2カラム 右側の左端"),
    ("vert", RIGHT,           "版面 右端"),
    ("horz", MARGIN_T,        "上マージン（ヘッダー上端）"),
    ("horz", BODY_TOP,        "本文 上端"),
    ("horz", BODY_BOT,        "本文 下端"),
    ("horz", FOOT_BOT,        "下マージン（フッター下端）"),
]

# PowerPoint の既定グリッド間隔 76200 EMU は 2.1167mm ＝ 余白スケールの基準単位と一致する
GRID_EMU = 76200

# ---------------------------------------------------------------- 出典
ATTRIBUTION = "出典：デジタル庁デザインシステムウェブサイト https://design.digital.go.jp/dads/"
ATTRIBUTION_NOTE = "本テンプレートはDADSの規定をA4タテ印刷向けに加工したものであり、デジタル庁が作成したものではありません。"
