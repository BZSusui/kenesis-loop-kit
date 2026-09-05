#!/usr/bin/env python3
"""ローカルブリッジ — 設定画面(draft-gen/index.html)のワンクリック生成(KLK-010).

Python標準ライブラリのみ・外部依存ゼロ。127.0.0.1 限定 bind の小さな HTTP サーバで、
ブラウザ「生成」→ 生成指示書POST → ブリッジが `/draft-generate` を `claude -p` でヘッドレス
実行 → 生成物(比較画面/1案)を自動オープン → 結果をブラウザへ返す(第1段階・個人利用向け)。

- 決定論コア(スキーマ検証・案件名安全化・保存先構築・オープン対象選択・コマンド構築)は
  モジュール先頭の純関数として置く(副作用なし・import で bind/実行が起きない)。
- HTTP サーバの起動は `if __name__ == "__main__":` ガード下に隔離する(テスト時 import 安全)。

起動:  python3 draft-gen/bridge.py   (KLK_BRIDGE_PORT で待受ポートを上書き可・既定 8765)

セキュリティ(§4.5):
- bind は 127.0.0.1 固定(0.0.0.0 は使わない)。外部ホストから到達不可。
- ブラウザを信用せず起動前に自前で validate_instruction(多層防御)。
- subprocess は shell=False・list 引数。プロンプトに載る可変値は bridge 生成の jobId パスのみ
  (ユーザー文字列を argv/プロンプトへ直挿ししない=注入対策)。
- 危険な全権限スキップ/全許可モードは決して構築しない(最小権限=acceptEdits のみ)。
"""

import datetime
import ipaddress
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import socket

# ============================================================================
# 定数
# ============================================================================
BRIDGE_HOST = "127.0.0.1"          # ★ 0.0.0.0 禁止(U-8/NFR-004)
DEFAULT_PORT = 8765                # env KLK_BRIDGE_PORT で上書き可(U-4)
# subprocess ハードタイムアウト(KLK-095 で 900→1800 へ)。
#  ★900秒だと**正常な生成が失敗扱いになる**余地があった。実測:
#    3案生成は同じ規模でも 262〜847秒とばらつき、847秒は上限900秒の94%。
#    出荷した見本02 を作ったときの実測がそれ。上限12セクションを置けるようになり余裕がさらに減る。
#  ★上限そのものは残す。`claude -p` が **0%CPU のまま34分無反応**になる事象を実際に観測しており
#    (KLK-079)、無制限にすると画面が永久に「生成中…」のままになる。
#    1800秒は「正常な生成(最長847秒)の2倍以上」かつ「異常な停止を見切れる」線。
BRIDGE_TIMEOUT_SEC = 1800
MAX_BODY_BYTES = 1 << 20           # POST /generate ボディ上限(1 MiB・L-1 多層防御)
UPLOAD_MAX_BODY_BYTES = 8 << 20    # POST /upload ボディ上限(8 MiB・写真向け・KLK-020 §3.3。JSONルートの MAX_BODY_BYTES は据え置き)
CATALOG_UPLOAD_MAX_BODY_BYTES = 8 << 20  # POST /catalog-upload ボディ上限(8 MiB・KLK-063。実績のフルページ・スクリーンショットを見込む。/upload と同値だが用途が違うため別定数で持つ)

# カラム構成 canonical(KLK-006 §4.4 / DRAFT_RULES §8)
CANONICAL_COLUMNS = {
    "1col",
    "2col-full-left",
    "2col-full-right",
    "2col-body-left",
    "2col-body-right",
    "3col",
}
# 旧値エイリアス(KLK-008 §4.2・後方互換・version:1 据え置き)
COLUMN_ALIAS = {
    "2col-sub-left": "2col-body-left",
    "2col-sub-right": "2col-body-right",
}

# セクション選択(KLK-022・§2.1)—本文セクション語彙14種・ヘッダー位置・CTA誘導先
SECTION_KEYS = {
    "NEWS", "ABOUT", "MENU", "PRICE", "GALLERY", "SEARCH", "FLOW",
    "VOICE", "STAFF", "FAQ", "SNS", "ACCESS", "CTA", "CONTACT",
}
NAV_POSITIONS = {"top", "below-hero"}
CTA_PURPOSES = {"contact", "order", "reserve", "document", "signup", "custom"}

# 指定コピー(KLK-024・§4.1)—MVキャッチ/リードの上限文字数（SCR-001 側の切詰めと同値）
COPY_MAX = {"mvCatch": 60, "mvLead": 200}

JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# 部分再生成(KLK-012・REQ-103)—番地/letter/folder の安全パターン
KNOWN_ADDR = {"NAV-01", "MV-01", "ABOUT-01", "MENU-01", "GALLERY-01", "FOOTER-01"}  # 基本6種(DRAFT_RULES §2)
ADDR_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d{2}$")  # 安全文字集合(SECTION-NN 連番拡張も許容・注入不能)
LETTER_RE = re.compile(r"^[a-c]$")               # 複数案の letter(a-c)。単一案は letter 無し

# 型入れ替え(KLK-078/079・第3弾)—番地→型プールの語彙。
# ★正は DRAFT_RULES §12.1.2(VOICE/FLOW/STAFF)と §12.1.3(その他11セクション)の型プール表であり、
#   ここはその写し。**順序も index 0〜5 のまま揃える**(表引きの pool index と対応させるため)。
#   規約側の表を変えたら必ずここも同期させる(乖離は check_klk078 が検出する)。
# NAV/FOOTER/CTA はプールを持たない: NAV/FOOTER は型プール方式の対象外、
#   CTA は §4.4 でボタン数と文字数から整列を自動決定する(選ばせる型が無い)。
SECTION_TYPE_POOLS = {
    "MV": ("full", "split", "band", "overlap", "center-scroll", "panel-band"),
    "ABOUT": ("img-left", "img-right", "img-top", "img-overlap", "img-circle", "img-zigzag"),
    "MENU": ("pat-cards", "pat-list", "pat-zigzag", "price-table", "tab-switch", "feature-large"),
    "GALLERY": ("pat-grid", "pat-wide", "pat-mosaic", "pat-slider", "pat-masonry", "pat-tab-grid"),
    "VOICE": ("voice-cards", "voice-quote-stack", "voice-feature", "voice-two-col", "voice-slider", "voice-zigzag"),
    "FLOW": ("flow-row", "flow-timeline", "flow-number-card", "flow-arrow-band", "flow-vertical-split", "flow-zigzag"),
    "STAFF": ("staff-grid", "staff-hscroll", "staff-feature", "staff-list", "staff-two-col", "staff-zigzag"),
    "NEWS": ("news-list", "news-cards", "news-media", "news-timeline", "news-table", "news-accordion"),
    "PRICE": ("price-table", "price-cards", "price-featured", "price-list", "price-toggle", "price-matrix"),
    "FAQ": ("faq-list", "faq-accordion", "faq-two-col", "faq-cards", "faq-category-tabs", "faq-search"),
    "ACCESS": ("map-side", "map-top", "map-overlay", "map-hours", "map-cards", "map-steps"),
    "CONTACT": ("contact-cta", "contact-form", "contact-split", "contact-methods", "contact-banner", "contact-steps"),
    "SNS": ("sns-grid", "sns-slider", "sns-cards", "sns-masonry", "sns-reels", "sns-feed"),
    "SEARCH": ("search-bar", "search-keywords", "search-filters", "search-sidebar", "search-header", "search-hero"),
}
PIN_RE = re.compile(r'<span class="pin">\s*([A-Z][A-Z0-9]*-\d{2})\s*</span>')

# 実績カタログ(KLK-013・SCR-004・REQ-105/106)—主配色7カテゴリ/安全名/MIME
# 主配色 canonical(KLK-067)。**正は palette/index.html の `const COLORS`**（ムードカラー ジェネレーターの
# 「メインカラーの傾向（カラー）」）であり、name をそのまま・順序も揃えて写している。
# タグ付け(カタログ)と配色生成(パレット)が同じ言葉を話すようにするため。乖離は check_klk067 が検出する。
# 旧「マルチカラー」は palette の「カラフル」へ改名した（同じ概念の別名・単独指定のみの規約は不変）。
CANONICAL_COLORS_ORDER = [
    "レッド",
    "ピンク",
    "オレンジ",
    "イエロー",
    "イエローグリーン",
    "グリーン",
    "ミント・水色",
    "ブルー",
    "ネイビー",
    "パープル",
    "ブラウン",
    "ベージュ",
    "ゴールド",
    "シルバー",
    "モノトーン",
    "カラフル",
]
CANONICAL_COLORS = set(CANONICAL_COLORS_ORDER)
CATALOG_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # id/file の安全文字集合(先頭は英数)
CATALOG_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}  # 配信MIME(GET /catalog/img/)。png変換方式ゆえ webp は保存せず=不変

# 取込許可拡張子(POST /catalog-import 全件列挙 用・配信MIMEとは目的が別・KLK-033)。
# webp は取込時に sips で png へ変換して保存するため、列挙の許可集合にのみ含める(配信MIMEには入れない)。
CATALOG_IMPORT_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


# ============================================================================
# 決定論コア(純関数・副作用なし・import 単体テスト対象=S群)
# ============================================================================
def normalize_columns(v):
    """旧値エイリアスを正規化し、canonical 6値でなければ None を返す。

    (KLK-008 §4.2 / DRAFT_RULES §8・SKILL 手順1 の正規化と同一)。
    """
    if not isinstance(v, str):
        return None
    v = COLUMN_ALIAS.get(v, v)
    return v if v in CANONICAL_COLUMNS else None


def validate_instruction(obj):
    """生成指示書JSONを検証する(KLK-006 §4.4 準拠・ブリッジ側の多層防御・U-8)。

    schema=='design-draft-instruction' / version==1 / 必須(industry.resolved,
    layout.columns(正規化後 canonical), colors.main が有効HEX) を検証。
    返却: (ok: bool, errors: list[str])。ok=False のとき errors に理由を列挙する。
    """
    errors = []
    if not isinstance(obj, dict):
        return False, ["生成指示書がオブジェクトではありません"]

    if obj.get("schema") != "design-draft-instruction":
        errors.append("schema が 'design-draft-instruction' ではありません")
    if obj.get("version") != 1:
        errors.append("version が 1 ではありません(未対応の版です)")

    industry = obj.get("industry")
    resolved = industry.get("resolved") if isinstance(industry, dict) else None
    if not (isinstance(resolved, str) and resolved.strip()):
        errors.append("industry.resolved(業種)が未指定です")

    layout = obj.get("layout")
    columns_raw = layout.get("columns") if isinstance(layout, dict) else None
    if normalize_columns(columns_raw) is None:
        errors.append("layout.columns(カラム構成)が未対応の値です")

    colors = obj.get("colors")
    main = colors.get("main") if isinstance(colors, dict) else None
    if not (isinstance(main, str) and _HEX_RE.match(main)):
        errors.append("colors.main(主色)が有効なHEXではありません")

    # KLK-022 §2.1: ヘッダー位置・本文セクション選択・CTA誘導先。
    # すべて「存在するときのみ」厳格検証する(無指定=後方互換の既定・従来 instruction は分岐に入らない)。
    if isinstance(layout, dict) and "navPosition" in layout:
        if layout.get("navPosition") not in NAV_POSITIONS:
            errors.append("layout.navPosition が未対応の値です(top/below-hero のみ)")

    sections = obj.get("sections")
    if sections is not None:
        if not isinstance(sections, list):
            errors.append("sections が配列ではありません")
        else:
            seen = set()
            for s in sections:
                if s not in SECTION_KEYS:
                    errors.append("sections に未対応のセクションが含まれます: {0}".format(s))
                elif s in seen:
                    errors.append("sections にセクションの重複があります: {0}".format(s))
                else:
                    seen.add(s)

    section_options = obj.get("sectionOptions")
    if section_options is not None:
        if not isinstance(section_options, dict):
            errors.append("sectionOptions がオブジェクトではありません")
        else:
            for key, opt in section_options.items():
                if key not in SECTION_KEYS:
                    errors.append("sectionOptions に未対応のキーがあります: {0}".format(key))
                    continue
                if not isinstance(opt, dict):
                    errors.append("sectionOptions.{0} がオブジェクトではありません".format(key))
                    continue
                if key == "CTA":
                    purpose = opt.get("purpose")
                    if purpose is not None and purpose not in CTA_PURPOSES:
                        errors.append("sectionOptions.CTA.purpose が未対応の値です")
                    label = opt.get("label")
                    if label is not None:
                        if not isinstance(label, str) or len(label) > 40 \
                                or any(ord(ch) < 32 for ch in label):
                            errors.append("sectionOptions.CTA.label が不正です(40字以内・制御文字不可)")
                    # KLK-058 §4.4: CTA マルチボタン。buttons=1〜4個の配列。各要素 {label(必須,40字), purpose?(6種) または href?(相対/#のみ)}。
                    buttons = opt.get("buttons")
                    if buttons is not None:
                        if not isinstance(buttons, list) or not (1 <= len(buttons) <= 4):
                            errors.append("sectionOptions.CTA.buttons は1〜4個の配列である必要があります")
                        else:
                            for b in buttons:
                                if not isinstance(b, dict):
                                    errors.append("sectionOptions.CTA.buttons の要素はオブジェクトである必要があります")
                                    continue
                                b_label = b.get("label")
                                if not isinstance(b_label, str) or not b_label.strip() \
                                        or len(b_label) > 40 or any(ord(ch) < 32 for ch in b_label):
                                    errors.append("sectionOptions.CTA.buttons[].label が不正です(必須・40字以内・制御文字不可)")
                                b_purpose = b.get("purpose")
                                if b_purpose is not None and b_purpose not in CTA_PURPOSES:
                                    errors.append("sectionOptions.CTA.buttons[].purpose が未対応の値です")
                                b_href = b.get("href")
                                if b_href is not None:
                                    if not isinstance(b_href, str) or any(ord(ch) < 32 for ch in b_href) \
                                            or re.match(r'^\s*(?:https?:|//|javascript:|data:|vbscript:)', b_href, re.I):
                                        errors.append("sectionOptions.CTA.buttons[].href が不正です(相対/# のみ・外部URL/危険スキーム不可)")
                # KLK-027 §4.2: 見出し/リードは全セクション共通の任意キー(存在時のみ検証・CTA とも併用可)。
                # heading は1行(制御文字不可)・lead は改行(\n)のみ許可。
                heading = opt.get("heading")
                if heading is not None:
                    if not isinstance(heading, str) or not heading.strip() \
                            or len(heading) > 40 \
                            or any(ord(ch) < 32 for ch in heading):
                        errors.append(
                            "sectionOptions.{0}.heading が不正です(40字以内・1行・制御文字不可・空不可)".format(key))
                lead = opt.get("lead")
                if lead is not None:
                    if not isinstance(lead, str) or not lead.strip() \
                            or len(lead) > 200 \
                            or any(ord(ch) < 32 and ch != "\n" for ch in lead):
                        errors.append(
                            "sectionOptions.{0}.lead が不正です(200字以内・改行以外の制御文字不可・空不可)".format(key))
                # KLK-048 §4.3: 詳細誘導ボタン(opt-in)。moreLink={label(必須,40字,1行), href?(相対/#のみ・外部URL/危険スキーム不可)}。
                more_link = opt.get("moreLink")
                if more_link is not None:
                    if not isinstance(more_link, dict):
                        errors.append("sectionOptions.{0}.moreLink がオブジェクトではありません".format(key))
                    else:
                        ml_label = more_link.get("label")
                        if not isinstance(ml_label, str) or not ml_label.strip() \
                                or len(ml_label) > 40 \
                                or any(ord(ch) < 32 for ch in ml_label):
                            errors.append(
                                "sectionOptions.{0}.moreLink.label が不正です(40字以内・1行・制御文字不可・空不可)".format(key))
                        ml_href = more_link.get("href")
                        if ml_href is not None:
                            if not isinstance(ml_href, str) \
                                    or any(ord(ch) < 32 for ch in ml_href) \
                                    or re.match(r'^\s*(?:https?:|//|javascript:|data:|vbscript:)', ml_href, re.I):
                                errors.append(
                                    "sectionOptions.{0}.moreLink.href が不正です(相対パスまたは # のみ・外部URL/危険スキーム不可)".format(key))

    # KLK-024 §4.1: 指定コピー(MVキャッチ/リード)。「存在するときのみ」厳格検証する(無指定=後方互換・
    # 従来 instruction は分岐に入らない・mvPhoto と同型)。改行(\n)のみ許可し他の制御文字は拒否。
    copy = obj.get("copy")
    if copy is not None:
        if not isinstance(copy, dict):
            errors.append("copy がオブジェクトではありません")
        else:
            for key, val in copy.items():
                if key not in COPY_MAX:
                    errors.append("copy に未対応のキーがあります: {0}".format(key))
                    continue
                if not isinstance(val, str) or not val.strip() \
                        or len(val) > COPY_MAX[key] \
                        or any(ord(ch) < 32 and ch != "\n" for ch in val):
                    errors.append(
                        "copy.{0} が不正です({1}字以内・改行以外の制御文字不可・空不可)".format(
                            key, COPY_MAX[key]))

    # KLK-020 §4.2: MVフリー実写真(REQ-104・案X)の別キー mvPhoto は「存在するときのみ」検証する
    # (standard/従来 instruction は mvPhoto を持たず、この分岐に入らない＝後方互換・等価)。
    # スキル側 basename 限定の一次防御に対する多層防御として、file を安全名(is_safe_catalog_name)に限定し
    # traversal/注入(../ や / \ を含む名)を弾く(mockups/.uploads/ 外を読ませない・R-3)。
    mv = obj.get("mvPhoto")
    if mv is not None:
        if not isinstance(mv, dict) or not is_safe_catalog_name(mv.get("file")):
            errors.append("mvPhoto.file が不正です(安全名のみ)")

    # KLK-034 §12.2/§5.1: 参考準拠の拡張キー。「存在するときのみ」検証する(無指定=後方互換・
    # 旧 instruction は分岐に入らない)。colors は16カテゴリ(1..3件・カラフル単独)、
    # sectionLayouts は shape のみ(object・値が非空文字列。語彙照合は validate_catalog と同方針でしない)。
    refs = obj.get("references")
    if refs is not None and isinstance(refs, dict):
        color_source = refs.get("colorSource")
        if color_source is not None and color_source not in ("reference", "specified"):
            errors.append("references.colorSource が未対応の値です(reference/specified のみ)")
        thumbs = refs.get("thumbnails")
        if isinstance(thumbs, list):
            for i, t in enumerate(thumbs):
                if not isinstance(t, dict):
                    continue  # 形の細部は従来どおりスキル側(ここは拡張キーの多層防御のみ)
                t_colors = t.get("colors")
                if t_colors is not None:
                    if not isinstance(t_colors, list) or not (1 <= len(t_colors) <= 3) \
                            or any(c not in CANONICAL_COLORS for c in t_colors) \
                            or ("カラフル" in t_colors and len(t_colors) > 1):
                        errors.append(
                            "references.thumbnails[{0}].colors が不正です(16カテゴリ・1..3件・カラフル単独)".format(i))
                t_sl = t.get("sectionLayouts")
                if t_sl is not None:
                    if not isinstance(t_sl, dict) \
                            or any(not isinstance(v, str) or not v.strip() for v in t_sl.values()):
                        errors.append(
                            "references.thumbnails[{0}].sectionLayouts が不正です(object・値は非空文字列)".format(i))
                t_source = t.get("source")
                if t_source is not None and t_source not in ("own", "ref"):
                    errors.append(
                        "references.thumbnails[{0}].source が不正です(own/ref のみ)".format(i))

    return (len(errors) == 0), errors


def sanitize_project(name):
    """案件名(meta.project)をパス安全化する(DRAFT_RULES §9 / SKILL 手順4 と同一規則)。

    前後空白除去 → 内部空白を '_' → '/ \\ : * ? " < > |' と制御文字を除去 → 空なら 'untitled'。
    """
    if not isinstance(name, str):
        name = ""
    s = name.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r'[/\\:*?"<>|]', "", s)
    s = "".join(ch for ch in s if ord(ch) >= 32)  # 制御文字除去
    return s if s else "untitled"


def build_folder(date_str, project):
    """'mockups/{YYYY-MM-DD}_{sanitize_project(project)}' を返す(相対・DRAFT_RULES §9)。"""
    return "mockups/{0}_{1}".format(date_str, sanitize_project(project))


def select_open_target(folder, variants):
    """開く対象を決定論的に選ぶ(U-5)。

    variants>=2 → '{folder}/compare.html' / variants==1 → '{folder}/index.html'。
    """
    try:
        n = int(variants)
    except (TypeError, ValueError):
        n = 1
    leaf = "compare.html" if n >= 2 else "index.html"
    return "{0}/{1}".format(folder, leaf)


def build_claude_command(instruction_path, allow_open=False):
    """ヘッドレス実行の claude コマンド(list・shell=False 用)を構築する(U-1/最小権限)。

    ['claude','-p', f'/draft-generate {instruction_path}',
     '--permission-mode','acceptEdits','--output-format','json']
    allow_open=True のとき ['--allowedTools','Bash(open *)'] を追加(版差の保険・依然最小権限)。
    ★ 全権限スキップ/全許可モードのフラグは決して含めない(acceptEdits のみ=最小権限)。
    """
    cmd = [
        "claude",
        "-p",
        "/draft-generate {0}".format(instruction_path),
        "--permission-mode",
        "acceptEdits",
        "--output-format",
        "json",
    ]
    if allow_open:
        cmd += ["--allowedTools", "Bash(open *)"]
    return cmd


def build_open_command(target_path, platform):
    """OS 別のオープンコマンド(list)を構築する(U-5)。

    'darwin'→['open',target] / 'win32'→['cmd','/c','start','',target] / それ以外→['xdg-open',target]。
    """
    if platform == "darwin":
        return ["open", target_path]
    if platform == "win32":
        return ["cmd", "/c", "start", "", target_path]
    return ["xdg-open", target_path]


def is_allowed_origin(origin, host, port):
    """状態変更(POST /generate)の Origin 許可判定(M-SEC-1)。

    None(不在)/"null"(file://) を許可。それ以外は **スキームが http・ポートが一致・
    ホストがループバック** のときだけ許可する。副作用なし・import 単体テスト対象(S群)。

    ★文字列の完全一致をやめた理由(KLK-084): 以前は
      `http://{host}:{port}` と `http://localhost:{port}` の2つとだけ突き合わせていたため、
      ブラウザが `localhost` を IPv6 で解決して `http://[::1]:{port}` を送ってくると
      **同じ端末の同じブリッジなのに 403** になった（実際に踏んだ）。
      ループバックかどうかで判定すれば、綴りが増えても破綻しない。
    """
    if origin is None or origin == "null":
        return True
    if not isinstance(origin, str) or not origin:
        return False
    try:
        u = urllib.parse.urlsplit(origin)
    except ValueError:
        return False
    # Origin は scheme://host[:port] だけ。パス等が付いていたら Origin ではない
    if u.scheme != "http" or u.path or u.query or u.fragment:
        return False
    try:
        if u.port != port:
            return False
    except ValueError:
        return False
    hostname = (u.hostname or "").lower()
    if not hostname:
        return False
    if hostname == "localhost" or hostname == str(host).lower():
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# 部分再生成(KLK-012・REQ-103)決定論コア — 純関数・副作用なし・import 単体テスト対象(S群)
# ---------------------------------------------------------------------------
def is_valid_addr(addr):
    """番地ラベルが安全な文字集合パターンに一致するか(注入対策の門・U-3)。

    ちょうど1回存在するかの本質判定は find_target_section で行う。
    """
    return isinstance(addr, str) and bool(ADDR_RE.match(addr))


def is_valid_letter(letter):
    """letter が a-c か。None/'' は単一案(index.html)を意味し許可(U-4)。"""
    return letter in (None, "") or (isinstance(letter, str) and bool(LETTER_RE.match(letter)))


def is_safe_mockups_folder(folder):
    """folder が mockups/ 配下の相対パスで、パストラバーサルを含まないか(U-5・注入対策)。

    'mockups/' 始まり・絶対パス/バックスラッシュ/'..' セグメント/先頭'/'/空セグメントを拒否。
    """
    if not isinstance(folder, str) or not folder.startswith("mockups/"):
        return False
    if "\\" in folder or folder.startswith("/"):
        return False
    return all(part not in ("..", "") for part in folder.split("/")[1:])


def resolve_target_html(folder, letter):
    """再生成対象HTMLの相対パスを決定論的に返す(U-4/U-5)。

    letter が a-c → '{folder}/index-{letter}.html' / None・'' → '{folder}/index.html'。
    """
    leaf = "index-{0}.html".format(letter) if letter else "index.html"
    return "{0}/{1}".format(folder, leaf)


def find_target_section(html, addr):
    """対象 .sec ブロックの範囲を特定し一意性を検証する(U-3・SPEC §7)。副作用なし。

    返却:
      (start, end)        … <span class="pin">{addr}</span> を含む唯一の .sec の [start, end) 文字範囲。
      (None, "unknown")   … 該当 pin が 0 回(未知の番地)。
      (None, "duplicate") … 該当 pin が 2 回以上(重複)。
    アルゴリズム: pin span の出現回数を数え、1 回のときのみ、その pin より前の最も近い
    <div class="sec ...> を開始点とし、<div>/</div> の入れ子を数えて対応する </div> を終端にする。
    """
    if not isinstance(html, str) or not isinstance(addr, str):
        return (None, "unknown")
    pin_re = re.compile(r'<span class="pin">\s*' + re.escape(addr) + r'\s*</span>')
    pins = list(pin_re.finditer(html))
    if len(pins) == 0:
        return (None, "unknown")
    if len(pins) >= 2:
        return (None, "duplicate")

    pin_pos = pins[0].start()
    # pin より前の最も近い `class="sec"` の**開始タグ**を開始点にする。
    # ★タグ名は div とは限らない(KLK-078): 生成物は <section>/<nav>/<header>/<footer> も使う。
    #   div 決め打ちだった間、それらのページでは全番地が 404 になり
    #   🔄 セクション再生成が丸ごと機能していなかった(見本 01/03 で再現)。
    #   `class="sec-more-btn"` のような別クラスに当たらないよう `sec` の直後は空白か引用符に限る。
    start = None
    tag = None
    for m in re.finditer(r'<([a-z]+)\s[^>]*class="sec[ "]', html):
        if m.start() < pin_pos:
            start, tag = m.start(), m.group(1)
        else:
            break
    if start is None:
        return (None, "unknown")

    # 同じタグ名の入れ子均衡で対応する終端 </tag> を探す
    depth = 0
    end = None
    open_close = re.compile(r"<{0}\b|</{0}>".format(re.escape(tag)))
    for m in open_close.finditer(html, start):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                end = m.end()
                break
        else:
            depth += 1
    if end is None:
        return (None, "unknown")
    return (start, end)


def read_root_palette(html):
    """対象HTMLのルート(.mock)定義から配色5変数の実値を読む(U-2)。

    返却: {'--m-main':..., '--m-nav':..., '--m-accent':..., '--m-bg':..., '--m-text':...}(見つかった分)。
    インライン style="--m-main:...;" 形式・<style> 内 '.mock { --m-*:...; }' 形式の双方に対応する。
    ★ instruction.json ではなく対象HTMLから読む(案B/C の派生配色を正しく維持する)。
    """
    out = {}
    if not isinstance(html, str):
        return out
    for name in ("--m-main", "--m-nav", "--m-accent", "--m-bg", "--m-text"):
        m = re.search(re.escape(name) + r"\s*:\s*([^;}\"'\n]+)", html)
        if m:
            out[name] = m.group(1).strip()
    return out


def pool_for_addr(addr):
    """番地から選べる型プールを返す(KLK-078)。プールを持たない番地・未知の番地は ()。

    番地は `{SECTION}-{NN}` 形式(§2)。連番拡張(ABOUT-02 等)も同じプールを共有する。
    副作用なし・import 単体テスト対象(S群)。
    """
    if not isinstance(addr, str) or not ADDR_RE.match(addr):
        return ()
    return SECTION_TYPE_POOLS.get(addr.rsplit("-", 1)[0], ())


def is_valid_desired_type(addr, desired):
    """desiredType が その番地のプールに載っているか(KLK-078/079・許可リスト判定)。

    ★パターン照合ではなく**集合の所属**で判定する。語彙は有限なので、
      正規表現で「それらしい文字列」を通すより、載っているものだけを通す方が注入面が小さい。
    None/'' は「指定なし」＝有効(従来の表引きへ落ちる)。
    """
    if desired in (None, ""):
        return True
    return isinstance(desired, str) and desired in pool_for_addr(addr)


def list_page_addrs(html):
    """対象HTMLに実在する番地を DOM 順で返す(KLK-078)。重複は最初の1回だけ。

    ★compare.html に番地を焼き込まず**実ファイルから読む**ための関数。
      焼き込むと、セクション構成が指示書ごとに変わる現在の仕様(§2.1)と食い違い、
      「選べるのに 404」「実在するのに選べない」が起きる(見本3点すべてで発生していた)。
    """
    if not isinstance(html, str):
        return []
    out = []
    for m in PIN_RE.finditer(html):
        if m.group(1) not in out:
            out.append(m.group(1))
    return out


def read_section_markers(html, addr):
    """当該セクションに出現するプール語を**すべて**返す(KLK-079)。出現順ではなくプール順。

    find_target_section で範囲を絞ってから、その番地のプール語を**単語境界つき**で探す。
    境界を付けないと `band` が `panel-band` の一部に誤ヒットする。

    ★1つに畳まず全部返すのは、**旧マーカーの外し忘れを検出する**ため(KLK-079)。
      `class="m-gallery pat-grid pat-masonry"` のように2つ残ると CSS が競合して崩れるが、
      「最長一致で1つ返す」実装ではこれを見逃し、後段検証が誤って成功と判定してしまう。
    """
    pool = pool_for_addr(addr)
    if not pool:
        return []
    # find_target_section は成功時 (start, end)・失敗時 (None, 理由) を返す
    start, end = find_target_section(html, addr)
    if start is None:
        return []
    block = html[start:end]
    return [
        t for t in pool
        if re.search(r"(?<![A-Za-z0-9-])" + re.escape(t) + r"(?![A-Za-z0-9-])", block)
    ]


def read_section_marker(html, addr):
    """当該セクションが現在どの型かを返す(KLK-078)。読めなければ None。

    複数該当したときは**最長一致**を採る(表示用。厳密な判定は read_section_markers を使う)。
    """
    hits = read_section_markers(html, addr)
    return max(hits, key=len) if hits else None


# 型入れ替え後の品質検査(KLK-080)—セクション容器のクラス名。番地の接頭辞→容器。
# MV だけ `m-hero`(歴史的経緯)、他は `m-{小文字}` で規則的。
SECTION_CONTAINERS = dict(
    [(k, "m-" + k.lower()) for k in SECTION_TYPE_POOLS if k != "MV"] + [("MV", "m-hero")]
)
# §3.0 で許される比率。これ以外で 1.6 より平たいものは極端な横長とみなす。
ALLOWED_RATIOS = ((4.0, 3.0), (1.0, 1.0), (3.0, 2.0))
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_ATARI_SEL_RE = re.compile(r"\.(?:[a-z0-9-]*atari|thumb|cell|tile)\b")
# §8.1 の対象＝「カード内で画像と本文を左右に並べる」型だけ。
# 2トラックの grid 全般を対象にすると、カード2枚並べ(faq-cards)や日付列(news-timeline)まで
# 誤検出する(実装時に見本で6件出した)。check_klk076 の S6 と同じ範囲。
SIDE_BY_SIDE_MARKERS = (
    "voice-zigzag", "voice-two-col",
    "flow-zigzag", "staff-zigzag",
    "img-left", "img-right", "img-overlap", "img-circle", "img-zigzag",
    "feature-large",
)


def _page_css(html):
    """<style> の中身を連結して返す(コメント除去済み)。副作用なし。"""
    return _CSS_COMMENT_RE.sub("", "\n".join(_STYLE_RE.findall(html or "")))


def _decl(body, prop):
    m = re.search(r"(?:^|;)\s*" + re.escape(prop) + r"\s*:\s*([^;]+)", body)
    return m.group(1).strip() if m else None


def _mobile_spans(css):
    """@media ブロックの範囲(開始,終了)の一覧。モバイル上書きを除外するために使う。"""
    out = []
    for m in re.finditer(r"@media[^{]*\{", css):
        depth, j = 0, m.end() - 1
        while j < len(css):
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append((m.start(), j))
    return out


def _rules_for(css, needles):
    """セレクタに needles のいずれかを含む、@media の外側のルールを返す。"""
    skip = _mobile_spans(css)
    out = []
    for m in _RULE_RE.finditer(css):
        if any(a <= m.start() <= b for a, b in skip):
            continue
        sel = m.group(1).strip()
        if sel.startswith("@"):
            continue
        if any(n in sel for n in needles):
            out.append((sel, m.group(2)))
    return out


def _tile_sizes(block, css, marker):
    """masonry / mosaic のタイル占有セルを返す(クラス指定・:nth-child(N) 指定の両対応)。

    ★生成側は span を **`:nth-child(N)` で書くことがある**(KLK-079 の実機検証で判明)。
      クラス指定しか読めないと**全部 1×1 に見えて**「空きセルあり」と誤検出する。
    """
    spans_cls, spans_nth = {}, {}
    for sel, body in _rules_for(css, [marker]):
        gc = re.sub(r"\s+", "", _decl(body, "grid-column") or "")
        gr = re.sub(r"\s+", "", _decl(body, "grid-row") or "")
        if not (gc.startswith("span") or gr.startswith("span")):
            continue
        sw = int(re.sub(r"\D", "", gc) or 1)
        sh = int(re.sub(r"\D", "", gr) or 1)
        nth = re.search(r":nth-child\(\s*(\d+)\s*\)", sel)
        if nth:
            spans_nth[int(nth.group(1))] = (sw, sh)
        else:
            spans_cls[sel.split(".")[-1].strip()] = (sw, sh)
    tiles = re.findall(r'<div class="atari([^"]*)"', block)
    sizes = []
    for i, cls in enumerate(tiles):
        w = h = 1
        if (i + 1) in spans_nth:
            w, h = spans_nth[i + 1]
        for key, (sw, sh) in spans_cls.items():
            if key and key in cls:
                w, h = max(w, sw), max(h, sh)
        sizes.append((w, h))
    return sizes


def _grid_holes(sizes, cols):
    """dense 配置を模して、矩形に敷き詰めたときの空きセル数を返す。"""
    grid = {}
    for w, h in sizes:
        r = 0
        while True:
            placed = False
            for c in range(max(1, cols - w + 1)):
                if all((r + dr, c + dc) not in grid for dr in range(h) for dc in range(w)):
                    for dr in range(h):
                        for dc in range(w):
                            grid[(r + dr, c + dc)] = 1
                    placed = True
                    break
            if placed:
                break
            r += 1
    if not grid:
        return 0
    rows = max(r for r, _ in grid) + 1
    return sum(1 for r in range(rows) for c in range(cols) if (r, c) not in grid)


def find_quality_warnings(html, addr):
    """対象セクションが横断ルールを守っているかを機械検査する(KLK-080)。副作用なし。

    ★なぜ必要か: KLK-079 の後段検証は「型が変わったか」しか見ていない。
      地図のアタリが 16/7 でも masonry に空白があっても「型にしました」と報告してしまう。
      KLK-072〜076 で4回続けて起きたのは、まさにその手の違反だった。

    返却: 人が読める警告文字列のリスト(空なら問題なし)。**判定できないものは黙る**(fail-open)。
    """
    warnings = []
    pool = pool_for_addr(addr)
    if not pool:
        return warnings
    start, end = find_target_section(html, addr)
    if start is None:
        return warnings
    block = html[start:end]
    css = _page_css(html)
    marker = None
    hits = read_section_markers(html, addr)

    # (0) マーカー衛生 — 同じプールの型が2つ以上
    if len(hits) >= 2:
        warnings.append("{0}: 型マーカーが{1}個あります（{2}）。1つだけにしてください".format(
            addr, len(hits), ", ".join(hits)))
    if hits:
        marker = max(hits, key=len)

    container = SECTION_CONTAINERS.get(addr.rsplit("-", 1)[0])
    # ★CSS の絞り込みは「容器名とマーカー」だけでは足りない(KLK-080 の実装時に判明)。
    #   ACCESS の地図は `.map-atari` で、`m-access` も `map-side` も含まない。
    #   そこで**そのセクションのブロックで実際に使われているクラス名**を needle にする。
    #   構造だけの共通クラスは除く(全セクションに当たって騒がしくなるため)。
    STRUCTURAL = {"sec", "addr", "pin", "reveal", "m-sec", "todo", "sec-head", "en"}
    class_names = set()
    for attr in re.findall(r'class="([^"]*)"', block):
        class_names.update(c for c in attr.split() if c and c not in STRUCTURAL)
    needles = sorted({("." + c) for c in class_names} | {n for n in (container, marker) if n})
    if not needles:
        return warnings

    # (1)(2) §3.0 — 極端な横長比率 / min-height だけのアタリ
    for sel, body in _rules_for(css, needles):
        v = re.sub(r"\s+", "", _decl(body, "aspect-ratio") or "")
        if v and v != "auto":
            m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:/(\d+(?:\.\d+)?))?", v)
            if m:
                w = float(m.group(1))
                h = float(m.group(2)) if m.group(2) else 1.0
                if (w, h) not in ALLOWED_RATIOS and h and w / h > 1.6:
                    warnings.append(
                        "{0}: 極端な横長比率です（{1} に aspect-ratio:{2}）。§3.0 の既定は 4/3".format(
                            addr, sel.strip()[:60], v))
        if (
            _ATARI_SEL_RE.search(sel)
            and "hero-atari" not in sel
            and "hero-media" not in sel
            and _decl(body, "min-height")
            and not _decl(body, "aspect-ratio")
        ):
            warnings.append(
                "{0}: min-height だけで高さを決めています（{1}）。§3.0 は aspect-ratio を求めます".format(
                    addr, sel.strip()[:60]))

    # (3) §12.1.3 — masonry / mosaic の大小混在と充填
    if marker and ("masonry" in marker or "mosaic" in marker):
        cols = None
        for sel, body in _rules_for(css, [marker]):
            gtc = re.sub(r"\s+", "", _decl(body, "grid-template-columns") or "")
            mm = re.match(r"repeat\((\d+),", gtc)
            if mm and sel.strip().endswith(marker):
                cols = int(mm.group(1))
        sizes = _tile_sizes(block, css, marker)
        if cols and sizes:
            if len(set(sizes)) < 2:
                warnings.append(
                    "{0}: タイルが全部同じ大きさです（{1} はベントー型＝大小混在が要件）".format(addr, marker))
            holes = _grid_holes(sizes, cols)
            if holes:
                warnings.append(
                    "{0}: 最終行に空きが {1} セルあります（{2}・§12.1.3 の構成A/B/Cから選んでください）".format(
                        addr, holes, marker))

    # (3.5) §3.0.1 — HERO panel-band の帯がどの幅でも1行に収まるか（KLK-096）
    #   ★auto-fit は列数がパネル数と一致する保証がないため 1200〜1280px で段落ちした
    #     （KLK-081・理恵さんの目視で発覚）。列をアイテム数だけ作る形になっているかを見る。
    if marker == "panel-band":
        for sel, body in _rules_for(css, ["panel-band"]):
            gtc = re.sub(r"\s+", "", _decl(body, "grid-template-columns") or "")
            flow = re.sub(r"\s+", "", _decl(body, "grid-auto-flow") or "")
            if not (gtc or flow):
                continue
            if "auto-fit" in gtc:
                warnings.append(
                    "{0}: panel-band の帯が auto-fit です（{1}）。"
                    "列数がパネル数と一致せず段落ちします。§3.0.1 は grid-auto-flow:column".format(
                        addr, sel.strip()[:50]))
            if _decl(body, "max-height"):
                warnings.append(
                    "{0}: panel-band の帯に max-height が付いています（コマが切れます・§3.0.1）".format(addr))

    # (3.6) §4.3.2/§4.3.3 — SCROLL 誘導が中央下に絶対配置されていないか（KLK-097）
    #   ★中央下に置くと、MV は justify-content:center の縦積みなので
    #     中身（キャッチ＋リード＋ボタン）が増えた時点でボタンと**必ず**重なる。
    #     見本「サンプル和菓子店」案A で発生。縦幅を伸ばすだけでは中身が多い場合に再発するので、
    #     「中央列から出ていること」と「帯が予約されていること」の両方を見る。
    if addr.rsplit("-", 1)[0] == "MV" and re.search(r'class="[^"]*\bscroll-cue\b', block):
        cue = [(sel, body) for sel, body in _rules_for(css, ["scroll-cue"])
               if ".scroll-cue" in sel and " .arrow" not in sel]
        centered = False
        vertical = False
        for sel, body in cue:
            left = re.sub(r"\s+", "", _decl(body, "left") or "")
            tr = re.sub(r"\s+", "", _decl(body, "transform") or "")
            wm = re.sub(r"\s+", "", _decl(body, "writing-mode") or "")
            if left == "50%" or "translateX(-50%)" in tr:
                centered = True
            if wm.startswith("vertical"):
                vertical = True
        if centered:
            warnings.append(
                "{0}: SCROLL 誘導が中央下に絶対配置されています（left:50%/translateX）。"
                "ボタンと重なります。§4.3.2 は左端に縦組み".format(addr))
        elif cue and not vertical:
            warnings.append(
                "{0}: SCROLL 誘導に writing-mode:vertical-rl がありません（§4.3.2 は縦組み）".format(addr))
        # 帯の予約 — 誘導の左端 18px ＋ 幅 約20px ＋ 余白 ＝ 64px 以上
        # ★素の `.m-hero`（型セレクタ無し）にも padding は効く。
        #   marker 一致を要求すると `full` のように素のルールで書く型を素通りする（KLK-097 の実装時に判明）。
        # ★**カスケード後**の値で判定する。生成側は素の `.m-hero` の shorthand を残したまま
        #   後続ルールで `padding-inline:64px` を上書きする書き方をする（実際にそう生成された）。
        #   ルールを1つずつ独立に見ると「30px だ」と誤報し、無視される警告になる。
        hero_pads = []
        for sel, body in _rules_for(css, ["m-hero"]):
            # ★容器そのもののルールだけを見る。`.m-hero .hero-cta` のような**子孫**を拾うと
            #   ボタンの padding:12px 32px を「帯が足りない」と誤報する（KLK-080 の見本で発生）。
            #   誤報は無視される警告を生み、検査そのものを無力にする。
            if not all(re.search(r"\.m-hero(\[[^\]]*\])?\s*$", p.strip())
                       for p in sel.split(",") if p.strip()):
                continue
            pi = _decl(body, "padding-inline") or ""
            pad = _decl(body, "padding") or ""
            val = None
            m = re.search(r"(\d+)px", pi)
            if m:
                val = int(m.group(1))
            elif pad:
                parts = pad.split()
                if len(parts) >= 2:
                    m = re.match(r"(\d+)px", parts[1])
                    if m:
                        val = int(m.group(1))
            if val is not None:
                hero_pads.append((sel, val))
        if hero_pads and hero_pads[-1][1] < 64:
            sel, val = hero_pads[-1]
            warnings.append(
                "{0}: MV の左右 padding が {1}px です（{2}）。"
                "SCROLL 誘導の帯に本文が入り込みます。§4.3.2 は 64px 以上".format(
                    addr, val, sel.strip()[:40]))

    # (4) §8.1 — 狭い本文カラムで「画像＋本文の横並び」になっていないか
    #     ★禁じているのは**カード内の画像と本文の横並び**であって、2トラックの grid 全般ではない。
    #       カードを2枚並べる(`faq-cards`)・日付と本文(`news-timeline`)・番号バッジは対象外。
    #       広く取ると誤検出だらけになる(実装時に見本で6件の誤検出を出した)。
    #     ★HERO/NAV/FOOTER は本文カラムの外にあるので対象外。
    root = re.search(r'data-columns="([^"]*)"', html)
    section = addr.rsplit("-", 1)[0]
    if (
        root
        and root.group(1).startswith(("2col", "3col"))
        and section not in ("MV", "NAV", "FOOTER")
    ):
        for sel, body in _rules_for(css, [m for m in SIDE_BY_SIDE_MARKERS if m in (marker or "")]):
            gtc = _decl(body, "grid-template-columns")
            if not gtc:
                continue
            g = re.sub(r"\s+", "", gtc)
            rep = re.fullmatch(r"repeat\((\d+),.*", g)
            ntracks = int(rep.group(1)) if rep else len(gtc.split())
            if ntracks < 2:
                continue
            px = re.findall(r"(\d+(?:\.\d+)?)px", g)
            if px and all(float(x) <= 100 for x in px) and ntracks == 2:
                continue   # 番号バッジ等の小さな固定幅は「画像と本文の横並び」ではない
            warnings.append(
                "{0}: 狭い本文カラムで画像と本文が横並びです（{1} → {2}）。§8.1 は縦積みを求めます".format(
                    addr, sel.strip()[:50], gtc.strip()[:40]))
    return warnings


# ---------------------------------------------------------------------------
# 見本サイトURLからの配色読み取り(KLK-083・REQ-102)決定論コア — 純関数・副作用なし
#
# ★AI を通さない。CSS の色を数えて並べるだけなので、同じページなら同じ結果になる。
#   生成パイプラインには触れない(配色欄に値が入るだけ)＝生成の決定性を壊さない。
# ★このブリッジが**初めて外へ出る**機能なので、防御は厚くする(is_safe_external_url /
#   is_public_ip)。利用者の端末で動く以上、社内ネットワークを覗く踏み台にしてはならない。
# ---------------------------------------------------------------------------
READ_COLORS_TIMEOUT_SEC = 8         # 1リクエストの上限
READ_COLORS_MAX_BYTES = 2_000_000   # 取得サイズの上限(HTML/CSS 各1本あたり)
READ_COLORS_MAX_CSS = 4             # 追加で取りに行く同一オリジンCSSの本数
READ_COLORS_MAX_REDIRECTS = 3
READ_COLORS_TOP = 8                 # 画面に出すスウォッチ数

_HEX3_RE = re.compile(r"#([0-9a-fA-F]{3})\b")
_HEX6_RE = re.compile(r"#([0-9a-fA-F]{6})\b")
_RGB_RE = re.compile(
    r"rgba?\(\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*(?:[,/][^)]*)?\)", re.I
)
_STYLE_TAG_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
_STYLE_ATTR_RE = re.compile(r'style\s*=\s*"([^"]*)"', re.I)
_LINK_CSS_RE = re.compile(
    r'<link\b[^>]*rel\s*=\s*["\']?stylesheet["\']?[^>]*>', re.I
)
_HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.I)
# CSS のコメントと、色に見えるが色ではないもの(id セレクタ等)を落とすため
_CSS_COMMENT_RE2 = re.compile(r"/\*.*?\*/", re.S)


def is_safe_external_url(url):
    """外向きに取得してよい URL か(構文レベル・KLK-083)。副作用なし。

    許すのはスキームが http と https のときだけ。資格情報つき(`利用者名:合言葉@ホスト`)は拒否する
    (認証情報を第三者へ送る形を作らない)。ホスト名が無いものも拒否。
    ★IP の素性は別途 is_public_ip で見る(名前解決が要るため分けている)。
    """
    if not isinstance(url, str) or len(url) > 2048:
        return False
    try:
        u = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return False
    if u.scheme not in ("http", "https"):
        return False
    if not u.hostname:
        return False
    # 資格情報つき(`利用者名:合言葉@ホスト`)は拒否する。
    # netloc に "@" があれば資格情報を含む形なので、それだけで弾く。
    if "@" in (u.netloc or ""):
        return False
    return True


def is_public_ip(addr):
    """その IP が外部の公開アドレスか(SSRF ガードの本体・KLK-083)。副作用なし。

    ループバック・プライベート・リンクローカル・共有(CGNAT)・予約・マルチキャストを拒否する。
    ★ブリッジは利用者の端末で動くので、ループバックや社内セグメント宛の URL を
      読ませると**社内ネットワークを覗く踏み台**になる。ここが最後の砦。
    """
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return not (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def normalize_color_value(value):
    """CSS の色指定を `#rrggbb`(小文字)へ正規化する(KLK-083)。読めなければ None。

    受けるのは `#rgb` / `#rrggbb` / `rgb()` / `rgba()`。色名は扱わない
    (`red` 等は数が少なく、拾うと `border` の既定値などで誤検出が増えるため)。
    """
    if not isinstance(value, str):
        return None
    t = value.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3})", t)
    if m:
        return "#" + "".join(c * 2 for c in m.group(1))
    m = re.fullmatch(r"#([0-9a-f]{6})", t)
    if m:
        return "#" + m.group(1)
    m = _RGB_RE.fullmatch(t)
    if m:
        vals = [int(m.group(i)) for i in (1, 2, 3)]
        if all(0 <= v <= 255 for v in vals):
            return "#%02x%02x%02x" % tuple(vals)
    return None


def extract_color_values(css_text):
    """CSS/HTML の断片から色を数える(KLK-083)。返却: {hex: 出現回数}。副作用なし。"""
    counts = {}
    if not isinstance(css_text, str):
        return counts
    body = _CSS_COMMENT_RE2.sub("", css_text)
    for m in _HEX6_RE.finditer(body):
        hexv = normalize_color_value("#" + m.group(1))
        if hexv:
            counts[hexv] = counts.get(hexv, 0) + 1
    for m in _HEX3_RE.finditer(body):
        # 6桁として既に数えた分と二重に数えない
        if _HEX6_RE.match(body, m.start()):
            continue
        hexv = normalize_color_value("#" + m.group(1))
        if hexv:
            counts[hexv] = counts.get(hexv, 0) + 1
    for m in _RGB_RE.finditer(body):
        hexv = normalize_color_value(m.group(0))
        if hexv:
            counts[hexv] = counts.get(hexv, 0) + 1
    return counts


def collect_page_colors(html):
    """HTML 本体（<style> と style 属性）から色を数える(KLK-083)。副作用なし。"""
    counts = {}
    if not isinstance(html, str):
        return counts
    for chunk in _STYLE_TAG_RE.findall(html):
        for k, v in extract_color_values(chunk).items():
            counts[k] = counts.get(k, 0) + v
    for chunk in _STYLE_ATTR_RE.findall(html):
        for k, v in extract_color_values(chunk).items():
            counts[k] = counts.get(k, 0) + v
    return counts


def same_origin_css_urls(html, base_url, limit=READ_COLORS_MAX_CSS):
    """HTML から**同一オリジンの**スタイルシートURLを取り出す(KLK-083)。副作用なし。

    ★同一オリジンに限るのは、1つのURL入力で任意のホストへ次々アクセスさせないため。
      現代のサイトは色を外部CSSに置くことが多いので、ここを拾わないとほとんど何も取れない。
    """
    out = []
    if not isinstance(html, str) or not is_safe_external_url(base_url):
        return out
    base = urllib.parse.urlsplit(base_url)
    for tag in _LINK_CSS_RE.findall(html):
        m = _HREF_RE.search(tag)
        if not m:
            continue
        href = urllib.parse.urljoin(base_url, m.group(1).strip())
        if not is_safe_external_url(href):
            continue
        u = urllib.parse.urlsplit(href)
        if (u.scheme, u.hostname, u.port) != (base.scheme, base.hostname, base.port):
            continue
        if href not in out:
            out.append(href)
        if len(out) >= limit:
            break
    return out


def _hsl(hexv):
    """#rrggbb → (h[0-360), s[0-1], l[0-1])。副作用なし。"""
    r, g, b = (int(hexv[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60.0, s, l


def hex_to_category(hexv):
    """hex を主配色16カテゴリ(§5.1・KLK-067)のどれかへ丸める(KLK-083)。副作用なし。

    ★表示用の目安であり、生成には使わない。「この色はブルー系」と分かると
      カタログ語彙（§5.1）と地続きに読めるので添える。
    """
    if not isinstance(hexv, str) or not re.fullmatch(r"#[0-9a-f]{6}", hexv):
        return None
    h, s, l = _hsl(hexv)
    # ★境界は §5.1 の変換表(16カテゴリ→hex)の実測 HSL に合わせてある。
    #   その15色を通すと**全部が自分のカテゴリへ戻る**（check_klk083 X1 が常時検査）。
    #   「カラフル」は単色に対応しないので、ここからは返らない。
    if s < 0.12:                                   # 無彩色
        return "シルバー" if 0.42 <= l < 0.86 else "モノトーン"
    if l >= 0.80 and 15 <= h < 60 and s < 0.60:    # 生成りやクリーム
        return "ベージュ"
    if h < 15 or h >= 345:
        return "レッド"
    if h < 33:
        return "ブラウン" if l < 0.45 else "オレンジ"
    if h < 43:
        return "ベージュ" if s < 0.38 else "ゴールド"
    if h < 60:
        return "イエロー"
    if h < 100:
        return "イエローグリーン"
    if h < 175:
        return "グリーン"
    if h < 197:
        return "ミント・水色"
    if h < 250:
        return "ネイビー" if l < 0.32 else "ブルー"
    if h < 300:
        return "パープル"
    return "ピンク"


def rank_page_colors(counts, top=READ_COLORS_TOP):
    """色を「使われている数」で並べる(KLK-083)。副作用なし。

    同数のときは hex 昇順で決定的にする（同じページなら毎回同じ並び）。
    """
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    total = sum(counts.values()) or 1
    return [
        {
            "hex": hexv,
            "count": n,
            "ratio": round(n / total, 4),
            "category": hex_to_category(hexv),
        }
        for hexv, n in items[:top]
    ]


def suggest_color_roles(ranked):
    """並べた色から メイン/サブ/アクセント/背景 を当てはめる(KLK-083)。副作用なし。

    あくまで**下書き**。人が画面で直す前提の、説明できる単純な規則にする。
      背景  = 明るい色のうち最も多いもの（無ければ最も明るいもの）
      メイン = 彩度のある色のうち最も多いもの
      アクセント = メインと色相が離れていて、最も彩度が高いもの
      サブ  = メインと同系で、メインより暗い/明るいもの
    埋まらない役割は None のまま返す（**適当な色をでっち上げない**）。
    """
    roles = {"main": None, "sub": None, "accent": None, "bg": None}
    if not ranked:
        return roles
    info = [(c["hex"], _hsl(c["hex"]), c["count"]) for c in ranked]

    lights = [x for x in info if x[1][2] >= 0.85]
    roles["bg"] = (lights[0][0] if lights
                   else max(info, key=lambda x: x[1][2])[0])

    chromatic = [x for x in info if x[1][1] >= 0.15 and x[0] != roles["bg"]]
    if chromatic:
        roles["main"] = chromatic[0][0]
    if roles["main"]:
        mh = [x for x in info if x[0] == roles["main"]][0][1][0]
        far = [x for x in chromatic
               if x[0] != roles["main"] and min(abs(x[1][0] - mh), 360 - abs(x[1][0] - mh)) >= 40]
        if far:
            roles["accent"] = max(far, key=lambda x: x[1][1])[0]
        near = [x for x in chromatic
                if x[0] not in (roles["main"], roles["accent"])
                and min(abs(x[1][0] - mh), 360 - abs(x[1][0] - mh)) < 40]
        if near:
            ml = [x for x in info if x[0] == roles["main"]][0][1][2]
            roles["sub"] = max(near, key=lambda x: abs(x[1][2] - ml))[0]
    return roles


def _resolve_public_addrs(host):
    """ホスト名を解決し、**すべての解決先が公開アドレスか**を返す(KLK-083)。

    返却: (ok, 解決したアドレスの一覧)。1つでも内部アドレスがあれば ok=False。
    ★「1つでも」なのは、複数レコードのうち片方だけ内部を指す形で
      ガードをすり抜けさせないため。名前解決に失敗したら ok=False（通さない）。
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False, []
    addrs = sorted({i[4][0] for i in infos})
    if not addrs:
        return False, []
    return all(is_public_ip(a) for a in addrs), addrs


def fetch_text(url, max_bytes=READ_COLORS_MAX_BYTES, timeout=READ_COLORS_TIMEOUT_SEC):
    """外部URLを取得して本文テキストを返す(KLK-083)。返却: (text, error)。

    ★リダイレクトは**自前で追う**。urllib に任せると、公開ホストからループバック宛への
      転送で SSRF ガードをすり抜けられてしまう。各ホップで必ず再検査する。
    """
    seen = 0
    current = url
    while True:
        if not is_safe_external_url(current):
            return None, "たどれない URL です（http と https のみ・資格情報つきは不可）"
        host = urllib.parse.urlsplit(current).hostname
        ok, _addrs = _resolve_public_addrs(host)
        if not ok:
            return None, "外部の公開サイトではないため取得しません（社内・ローカル宛は対象外）"
        req = urllib.request.Request(
            current,
            headers={"User-Agent": "kenesis-loop-kit/1.0 (color reader)",
                     "Accept": "text/html,text/css,*/*"},
            method="GET",
        )
        try:
            opener = urllib.request.build_opener(_NoRedirect())
            with opener.open(req, timeout=timeout) as res:
                status = getattr(res, "status", 200)
                if status in (301, 302, 303, 307, 308):
                    loc = res.headers.get("Location")
                    if not loc or seen >= READ_COLORS_MAX_REDIRECTS:
                        return None, "転送が多すぎます"
                    current = urllib.parse.urljoin(current, loc)
                    seen += 1
                    continue
                raw = res.read(max_bytes + 1)
        except Exception as exc:   # 通信全般(DNS/TLS/タイムアウト/HTTPエラー)
            return None, "取得できませんでした（{0}）".format(type(exc).__name__)
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
        charset = "utf-8"
        try:
            ct = res.headers.get("Content-Type") or ""
            m = re.search(r"charset=([\w-]+)", ct, re.I)
            if m:
                charset = m.group(1)
        except Exception:
            pass
        try:
            return raw.decode(charset, errors="replace"), None
        except LookupError:
            return raw.decode("utf-8", errors="replace"), None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """自動リダイレクトを止める(各ホップを自分で検査するため・KLK-083)。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

    def http_error_301(self, req, fp, code, msg, headers):
        return fp

    http_error_302 = http_error_303 = http_error_307 = http_error_308 = http_error_301


def read_site_colors(url, fetcher=None):
    """URL のページから配色を読み取る(KLK-083)。返却: dict（画面へそのまま返す形）。

    fetcher を差し替えられるようにしてあるのは、**テストで第三者サイトへ出ないため**。
    """
    fetch = fetcher or fetch_text
    html, err = fetch(url)
    if err:
        return {"ok": False, "error": err, "colors": [], "suggestion": {}, "sources": []}
    counts = collect_page_colors(html)
    sources = ["(ページ本体)"]
    for css_url in same_origin_css_urls(html, url):
        css, cerr = fetch(css_url)
        if cerr or not css:
            continue
        add = extract_color_values(css)
        if add:
            sources.append(css_url)
        for k, v in add.items():
            counts[k] = counts.get(k, 0) + v
    ranked = rank_page_colors(counts)
    if not ranked:
        return {
            "ok": False,
            # ★黙って空を返さない。JS で描くサイトは CSS が後から入るので拾えない。
            "error": "このページからは色を読み取れませんでした（表示に JavaScript が必要なサイトなど）。"
                     "スクリーンショットを実績カタログへ取り込む方法もお試しください",
            "colors": [], "suggestion": {}, "sources": sources,
        }
    return {
        "ok": True,
        "error": None,
        "colors": ranked,
        "suggestion": suggest_color_roles(ranked),
        "sources": sources,
    }


def build_regenerate_command(pending_path, allow_open=False):
    """/draft-regenerate のヘッドレス実行コマンド(list・shell=False 用)を構築する(U-5/最小権限)。

    ['claude','-p', f'/draft-regenerate {pending_path}',
     '--permission-mode','acceptEdits','--output-format','json']
    allow_open=True のとき ['--allowedTools','Bash(open *)'] を追加(版差の保険・依然最小権限)。
    ★ 全権限スキップ/全許可モードのフラグは決して含めない(build_claude_command と同一方針)。
    """
    cmd = [
        "claude",
        "-p",
        "/draft-regenerate {0}".format(pending_path),
        "--permission-mode",
        "acceptEdits",
        "--output-format",
        "json",
    ]
    if allow_open:
        cmd += ["--allowedTools", "Bash(open *)"]
    return cmd


# ---------------------------------------------------------------------------
# 実績カタログ(KLK-013・SCR-004)決定論コア — 純関数・副作用なし・import 単体テスト対象(S群)
# ---------------------------------------------------------------------------
def is_safe_catalog_name(name):
    """catalog/img/{name} の name が安全か(パストラバーサル/注入対策・R-5/§4.3)。

    CATALOG_NAME_RE 一致(先頭英数)・'..' 無し・'/' や '\\' を含まず・先頭 '.' でないこと。
    先頭 '.' は CATALOG_NAME_RE(先頭は [A-Za-z0-9])で自動的に拒否される。
    """
    return (
        isinstance(name, str)
        and bool(CATALOG_NAME_RE.match(name))
        and ".." not in name
        and "/" not in name
        and "\\" not in name
    )


def catalog_content_type(name):
    """拡張子から MIME を返す(未知は 'application/octet-stream')。GET /catalog/img/{name} 用。"""
    if not isinstance(name, str):
        return "application/octet-stream"
    _, ext = os.path.splitext(name.lower())
    return CATALOG_MIME.get(ext, "application/octet-stream")


def catalog_import_ext_ok(name):
    """POST /catalog-import 全件列挙の取込許可拡張子か(配信MIMEではなく取込許可集合で判定・KLK-033)。副作用なし。

    webp は取込時に sips で png へ変換して保存するため取込許可集合には含めるが、配信MIME(CATALOG_MIME)
    には含めない(png/jpg のみ配信)。取込列挙と配信は目的が異なるため別集合で切り分ける。
    """
    if not isinstance(name, str):
        return False
    _, ext = os.path.splitext(name.lower())
    return ext in CATALOG_IMPORT_EXTS


def sniff_image_ext(head):
    """先頭バイト列から画像拡張子を判定する(マジックバイト・Content-Type は信用しない・KLK-020 §3.2)。

    JPEG(FF D8 FF)→'.jpg' / PNG(89 50 4E 47 0D 0A 1A 0A)→'.png' / それ以外→None。副作用なし。
    クライアントのファイル名・Content-Type ではなく本体先頭バイトを正とする(保存面をゼロにする一助)。
    """
    if not isinstance(head, (bytes, bytearray)):
        return None
    b = bytes(head)
    if b[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    return None


def sniff_catalog_image_ext(head):
    """カタログ取り込み用のマジックバイト判定(JPEG/PNG/WebP・KLK-063)。副作用なし。

    **`sniff_image_ext` とは別関数**である。理由: `/upload`(MV写真・REQ-104/KLK-020)は仕様上 JPEG/PNG 限定で、
    その挙動は check_klk020 S9/S11 が固定している。カタログ側は `CATALOG_IMPORT_EXTS` が WebP を含み
    (取込時に sips で png へ変換する・KLK-033)、受理集合が異なるため関数を分ける。

    JPEG(FF D8 FF)→'.jpg' / PNG(89 50 4E 47 0D 0A 1A 0A)→'.png' /
    WebP(RIFF + 4バイトのサイズ + WEBP)→'.webp' / それ以外→None。
    クライアントのファイル名・Content-Type ではなく本体先頭バイトを正とする。
    """
    if not isinstance(head, (bytes, bytearray)):
        return None
    b = bytes(head)
    if b[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return ".webp"
    return None


def validate_catalog(obj):
    """カタログJSONを検証する(§4.1・多層防御)。

    schema=='klk-catalog' / version==1 / entries=list / 各 entry の
    id(安全名)・file(安全名)・source∈{own,ref}・colors⊆CANONICAL_COLORS を検証。
    sectionLayouts(任意・KLK-030) は present のとき object かつ各値が非空文字列で
    あることを構造検証する(値の語彙照合は行わない。語彙の正は DRAFT_RULES §12.1.1/§12.1.2)。
    返却: (ok: bool, errors: list[str])。ok=False のとき errors に理由を列挙する。
    """
    errors = []
    if not isinstance(obj, dict):
        return False, ["カタログがオブジェクトではありません"]

    if obj.get("schema") != "klk-catalog":
        errors.append("schema が 'klk-catalog' ではありません")
    if obj.get("version") != 1:
        errors.append("version が 1 ではありません(未対応の版です)")

    entries = obj.get("entries")
    if not isinstance(entries, list):
        errors.append("entries が配列ではありません")
        return (len(errors) == 0), errors

    for i, entry in enumerate(entries):
        where = "entries[{0}]".format(i)
        if not isinstance(entry, dict):
            errors.append("{0} がオブジェクトではありません".format(where))
            continue
        if not is_safe_catalog_name(entry.get("id")):
            errors.append("{0}.id が不正です(安全名のみ)".format(where))
        if not is_safe_catalog_name(entry.get("file")):
            errors.append("{0}.file が不正です(安全名のみ)".format(where))
        if entry.get("source") not in ("own", "ref"):
            errors.append("{0}.source が own|ref ではありません".format(where))
        colors = entry.get("colors")
        if not isinstance(colors, list):
            errors.append("{0}.colors が配列ではありません".format(where))
        else:
            for c in colors:
                if c not in CANONICAL_COLORS:
                    errors.append("{0}.colors に未対応の主配色 '{1}' があります".format(where, c))
            # KLK-016: 件数(第1主配色が必須・最大3件)
            if len(colors) < 1:
                errors.append("{0}.colors は第1主配色が必須です(空配列不可)".format(where))
            elif len(colors) > 3:
                errors.append("{0}.colors は最大3件までです".format(where))
            # KLK-016/067: カラフルは単独指定のみ(具体色と併用不可)
            if "カラフル" in colors and len(colors) != 1:
                errors.append("{0}.colors のカラフルは単独指定のみ可です(他色と併用不可)".format(where))
        # KLK-030: sectionLayouts(任意)。present→shape検証 / absent→OK。
        # 値の語彙の正は DRAFT_RULES §12.1.1/§12.1.2。ここでは語彙照合をしない
        # (bridge.py に語彙表を持つと第3の複製になり STEP B 追従性を損なうため)。品質は M群/人間確認ゲート。
        sl = entry.get("sectionLayouts")
        if sl is not None:
            if not isinstance(sl, dict):
                errors.append("{0}.sectionLayouts はオブジェクト(セクションKEY→型マーカーのmap)ではありません".format(where))
            else:
                for k, v in sl.items():
                    if not isinstance(k, str) or not k:
                        errors.append("{0}.sectionLayouts に非文字列/空のキーがあります".format(where))
                    if not isinstance(v, str) or not v:
                        errors.append("{0}.sectionLayouts['{1}'] の値は非空文字列である必要があります".format(where, k))

    return (len(errors) == 0), errors


PROPOSAL_SCHEMA = "klk-catalog-proposal"   # KLK-064: AI のタグ付け案(登録前)のスキーマ名
PROPOSAL_VERSION = 1
CATALOG_ID_RE = re.compile(r"^cat-(\d{4,})$")   # id は cat-0001 形式(4桁以上のゼロ詰め連番)


def validate_proposal(obj):
    """タグ付け案 proposal.json を検証する(KLK-064・§3.2)。副作用なし。

    AI が書き出した案を**人間へ見せる前**に構造だけ検証する(値の妥当性は人間が画面で判断する)。
    想定: {"schema":"klk-catalog-proposal","version":1,"jobId":"<hex>","items":[{...}]}
    各 item: file(必須・is_safe_catalog_name) / industry・taste・title・note・columns・source は
    あれば文字列 / colors はあれば CANONICAL_COLORS の 1..3 件(カラフルは単独) /
    sectionLayouts はあれば object かつ各値が非空文字列。
    返却: (ok: bool, errors: list[str])。
    """
    errors = []
    if not isinstance(obj, dict):
        return False, ["提案がオブジェクトではありません"]
    if obj.get("schema") != PROPOSAL_SCHEMA:
        errors.append("schema が '{0}' ではありません".format(PROPOSAL_SCHEMA))
    if obj.get("version") != PROPOSAL_VERSION:
        errors.append("version が {0} ではありません".format(PROPOSAL_VERSION))
    items = obj.get("items")
    if not isinstance(items, list):
        errors.append("items が配列ではありません")
        return (len(errors) == 0), errors
    for i, it in enumerate(items):
        errors.extend(_validate_tag_fields(it, i, require_file=True))
    return (len(errors) == 0), errors


def _validate_tag_fields(it, i, require_file):
    """提案/承認に共通するタグ項目の構造検証(KLK-064・validate_proposal と validate_commit_request で共用)。

    副作用なし。返却: errors(list[str])。空なら妥当。
    """
    errors = []
    if not isinstance(it, dict):
        return ["items[{0}] がオブジェクトではありません".format(i)]
    if require_file and not is_safe_catalog_name(it.get("file")):
        errors.append("items[{0}].file が安全なファイル名ではありません".format(i))
    # KLK-066: sourceFile(変換元・任意)。あるときだけ安全名を要求する。
    if it.get("sourceFile") is not None and not is_safe_catalog_name(it.get("sourceFile")):
        errors.append("items[{0}].sourceFile が安全なファイル名ではありません".format(i))
    for key in ("industry", "taste", "title", "note", "columns", "source"):
        if key in it and it[key] is not None and not isinstance(it[key], str):
            errors.append("items[{0}].{1} が文字列ではありません".format(i, key))
    if "source" in it and it.get("source") not in (None, "own", "ref"):
        errors.append("items[{0}].source が own/ref ではありません".format(i))
    cols = it.get("colors")
    if cols is not None:
        if not isinstance(cols, list) or not (1 <= len(cols) <= 3):
            errors.append("items[{0}].colors が 1..3 件の配列ではありません".format(i))
        elif any(c not in CANONICAL_COLORS for c in cols):
            errors.append("items[{0}].colors に許可外の主配色があります".format(i))
        elif "カラフル" in cols and len(cols) > 1:
            errors.append("items[{0}].colors のカラフルは単独指定のみです".format(i))
    sl = it.get("sectionLayouts")
    if sl is not None:
        if not isinstance(sl, dict):
            errors.append("items[{0}].sectionLayouts がオブジェクトではありません".format(i))
        elif any((not isinstance(v, str)) or (not v.strip()) for v in sl.values()):
            errors.append("items[{0}].sectionLayouts の値が非空文字列ではありません".format(i))
    return errors


def validate_commit_request(obj):
    """POST /catalog-commit のボディを検証する(KLK-064・注入対策・§3.3④)。副作用なし。

    想定: {"items":[{file, industry, taste, colors, columns, source, title, note, sectionLayouts}, ...]}
    **人間が画面で承認した内容**なので、登録に必要な最小項目(file / industry / taste / colors)は必須とする。
    返却: (ok: bool, errors: list[str])。
    """
    errors = []
    if not isinstance(obj, dict):
        return False, ["承認内容がオブジェクトではありません"]
    items = obj.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return False, ["登録する画像が選ばれていません"]
    for i, it in enumerate(items):
        errors.extend(_validate_tag_fields(it, i, require_file=True))
        if not isinstance(it, dict):
            continue
        if not (isinstance(it.get("industry"), str) and it["industry"].strip()):
            errors.append("items[{0}].industry(業種)が未指定です".format(i))
        if not (isinstance(it.get("taste"), str) and it["taste"].strip()):
            errors.append("items[{0}].taste(テイスト)が未指定です".format(i))
        if not isinstance(it.get("colors"), list) or not it["colors"]:
            errors.append("items[{0}].colors(主配色)が未指定です".format(i))
    return (len(errors) == 0), errors


def pending_groups(names):
    """.pending/ のファイル名を basename でグループ化する(KLK-066)。副作用なし。

    スキルの webp 変換は `.pending/` 内で**同じ basename** の png を作る(CATALOG_RULES・KLK-033)。
    したがって `pnd-X.webp` と `pnd-X.png` は**同じ画像の2つの表現**であり、
    取り込み待ちの計数・登録時の片付けはこの単位(=グループ)で行う。
    返却: {basename: [name, ...]}（各リストは名前順）。
    """
    groups = {}
    for n in names or []:
        if not isinstance(n, str) or not n:
            continue
        base = os.path.splitext(n)[0]
        groups.setdefault(base, []).append(n)
    for base in groups:
        groups[base].sort()
    return groups


# 代表名の優先順位。**登録に使われる側**（視覚認識できる形式）を先に出す。
_PENDING_PRIORITY = [".png", ".jpg", ".jpeg", ".webp"]


def pending_display_name(group):
    """グループの代表ファイル名を返す(KLK-066)。副作用なし。

    png > jpg/jpeg > webp の順。webp は変換されて初めて視覚認識できるため最後。
    該当拡張子が無ければ名前順の先頭を返す。
    """
    items = sorted(group or [])
    for ext in _PENDING_PRIORITY:
        for n in items:
            if n.lower().endswith(ext):
                return n
    return items[0] if items else None


def iso_now():
    """カタログ用のタイムスタンプ文字列(ISO8601・ローカルタイムゾーン付き・KLK-064)。副作用なし。

    既存 entries の `addedAt` / `generatedAt` は '2026-07-28T10:12:31+09:00' 形式の**文字列**。
    `_now()`(datetime オブジェクト)をそのまま JSON へ入れると TypeError になるため、
    カタログ書き込み用は必ず本関数を使う。
    """
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()


def next_catalog_id(existing_ids, img_names):
    """次のカタログ id(cat-00NN)を決める(KLK-064・採番の責務は bridge 側)。副作用なし。

    **catalog.json の id と catalog/img/ のファイル名の双方**から最大連番を採り、その次を返す
    (片方だけを見ると、登録途中で落ちた場合などに衝突しうる)。既存が無ければ cat-0001。
    """
    nums = []
    for v in list(existing_ids or []) + [os.path.splitext(n or "")[0] for n in (img_names or [])]:
        m = CATALOG_ID_RE.match(str(v))
        if m:
            nums.append(int(m.group(1)))
    return "cat-{0:04d}".format((max(nums) + 1) if nums else 1)


def validate_delete_request(obj):
    """POST /catalog-delete のボディを検証する(KLK-068・注入対策)。副作用なし。

    想定: {"ids": ["cat-0054", ...]}。各 id は is_safe_catalog_name(パストラバーサル対策)。
    返却: (ok: bool, errors: list[str])。
    """
    errors = []
    if not isinstance(obj, dict):
        return False, ["削除指示がオブジェクトではありません"]
    ids = obj.get("ids")
    if not isinstance(ids, list) or len(ids) == 0:
        return False, ["削除する対象が指定されていません"]
    for i, v in enumerate(ids):
        if not is_safe_catalog_name(v):
            errors.append("ids[{0}] が安全な id ではありません".format(i))
    return (len(errors) == 0), errors


def validate_import_request(obj):
    """POST /catalog-import のボディを検証する(注入対策・§4.2)。

    想定: {"files": ["a.jpg", ...]}(.pending 内の対象・各 is_safe_catalog_name)
    または {"all": true}(.pending 全件)。安全でなければ (False, errors)。
    返却: (ok: bool, errors: list[str])。
    """
    errors = []
    if not isinstance(obj, dict):
        return False, ["取り込み指示がオブジェクトではありません"]

    all_flag = obj.get("all")
    files = obj.get("files")

    if all_flag is True:
        # 全件取り込み。files は無視してよい
        return True, []

    if not isinstance(files, list) or len(files) == 0:
        errors.append("files(取り込み対象)が指定されていません")
        return False, errors

    for f in files:
        if not is_safe_catalog_name(f):
            errors.append("files に不正なファイル名があります: {0!r}".format(f))

    return (len(errors) == 0), errors


def build_catalog_import_command(pending_spec_path, allow_open=False):
    """/catalog-import のヘッドレス実行コマンド(list・shell=False 用)を構築する(最小権限・§4.2)。

    ['claude','-p', f'/catalog-import {pending_spec_path}',
     '--permission-mode','acceptEdits','--output-format','json',
     '--allowedTools','Bash(sips *)']
    allow_open=True のとき allowedTools に 'Bash(open *)' を足す(版差の保険・依然最小権限)。
    ★ 全権限スキップ/全許可モードのフラグは決して含めない(build_claude_command と同一方針)。

    **`Bash(sips *)` は必須(KLK-065)**: `--permission-mode acceptEdits` は**ファイル編集しか**
    自動承認せず、Bash コマンドは承認を要求する。webp→png 変換の `sips`(CATALOG_RULES・KLK-033)が
    承認待ちで止まり、**非対話ゆえ誰も答えられず提案が1件も作られない**事故が起きたため、
    この1コマンドだけを明示的に許可する(単一バイナリに限定＝最小権限は維持)。
    """
    cmd = [
        "claude",
        "-p",
        "/catalog-import {0}".format(pending_spec_path),
        "--permission-mode",
        "acceptEdits",
        "--output-format",
        "json",
    ]
    # 取り込みに必要な Bash は sips(webp→png 変換)のみ。allow_open 時は open も足す。
    tools = ["Bash(sips *)"]
    if allow_open:
        tools.append("Bash(open *)")
    cmd += ["--allowedTools", ",".join(tools)]
    return cmd


MTIME_TOLERANCE_SEC = 2.0   # 再生成の mtime 更新判定の許容差(FS の秒切り詰め吸収・KLK-018 U2)


def is_job_success(returncode, artifact_ok):
    """終了コードに依存しない成否判定(KLK-018)。副作用なし・S群 import 対象。

    成果物(artifact_ok=True)があれば returncode を問わず成功。無ければ returncode==0 のときのみ成功。
    ＝「returncode!=0 かつ 成果物なし」だけを失敗とする(成果物ありを優先)。
    timeout・起動失敗は本関数の手前で独立に失敗確定させる(温存)。
    """
    return bool(artifact_ok) or returncode == 0


def repo_root():
    """このファイル(draft-gen/bridge.py)からリポジトリルート(draft-gen の親)を返す。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# 以下はサーバ本体。import では実行されない(__main__ ガード下でのみ起動)。
# ============================================================================
def _run_server(port):
    """127.0.0.1:port で ThreadingHTTPServer を起動する(§4.2/4.3)。"""
    import shutil   # KLK-064: /catalog-commit の画像移動(.pending → catalog/img)に使用
    import threading
    import uuid
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    root = repo_root()
    index_path = os.path.join(root, "draft-gen", "index.html")
    # 配色ジェネレーター(KLK-019・REQ-003)。外部依存ゼロの単一HTMLを固定1ファイル配信
    palette_index_path = os.path.join(root, "palette", "index.html")
    pending_dir = os.path.join(root, "mockups", ".pending")
    # MVフリー実写真(KLK-020・REQ-104)のアップロード先ステージング。mockups/ 除外に内包され自動Git除外
    # (§3.4・.gitignore 変更不要)。保存名はサーバ生成(upl-<uuid>.<ext>)＝traversal 面ゼロ。
    uploads_dir = os.path.join(root, "mockups", ".uploads")
    # 実績カタログ(KLK-013・SCR-004)。catalog/ は Git除外・社外秘(§4.6)
    catalog_html_path = os.path.join(root, "draft-gen", "catalog.html")
    catalog_dir = os.path.join(root, "catalog")
    catalog_json_path = os.path.join(catalog_dir, "catalog.json")
    catalog_img_dir = os.path.join(catalog_dir, "img")
    catalog_pending_dir = os.path.join(catalog_dir, ".pending")
    # KLK-068: 削除した画像の退避先。catalog/ は Git 管理外で復元できないため、
    # 実削除せずここへ移す（自動削除はしない＝人間が判断して消す）。
    catalog_trash_dir = os.path.join(catalog_dir, ".trash")
    _EMPTY_CATALOG = {"schema": "klk-catalog", "version": 1, "entries": []}

    jobs = {}
    jobs_lock = threading.Lock()

    def _now():
        return datetime.datetime.now()

    def _run_job(job_id, pending_path, project, variants, started_at):
        """ワーカースレッド: claude -p を実行し、完了後ブリッジが表示物を開く(§4.3)。"""
        cmd = build_claude_command(pending_path)
        try:
            proc = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=BRIDGE_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = (
                    "生成がタイムアウトしました({0}秒)。設定を見直して再実行してください".format(
                        BRIDGE_TIMEOUT_SEC
                    )
                )
            _cleanup(pending_path)
            return
        except Exception as exc:  # 起動失敗(claude 不在など)
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = "生成の起動に失敗しました: {0}".format(exc)
            _cleanup(pending_path)
            return

        # 保存規約(DRAFT_RULES §9)から表示物パスを決定論的に構築し、ブリッジ自身が開く(U-5)
        # 日付はジョブ開始時刻基準(L-2): 日跨ぎ長時間ジョブでも保存先フォルダがずれない
        # KLK-018: 表示物パス構築を失敗判定の前へ移動し、成果物の存在を主判定にする
        date_str = started_at.strftime("%Y-%m-%d")
        folder = build_folder(date_str, project)
        open_target = select_open_target(folder, variants)
        abs_target = os.path.join(root, open_target)

        # KLK-018: 終了コード単独ではなく成果物(表示物)の存在を優先して判定する
        if not is_job_success(proc.returncode, os.path.exists(abs_target)):
            # 診断はサーバコンソール(stderr)のみ。生JSONはブラウザ(message)に出さない
            print("[bridge] 生成 失敗 exit={0}".format(proc.returncode), file=sys.stderr)
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = "生成できませんでした。もう一度お試しください。解決しない場合は Claude Code（claude）が起動しているかご確認ください"
            _cleanup(pending_path)
            return

        opened = False
        try:
            subprocess.run(
                build_open_command(abs_target, sys.platform),
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
            )
            opened = True
        except Exception:
            opened = False  # 開けなくてもパス表示で無害(グレースフル)

        with jobs_lock:
            jobs[job_id]["state"] = "done"
            jobs[job_id]["folder"] = folder
            jobs[job_id]["openTarget"] = open_target
            jobs[job_id]["message"] = (
                "生成が完了しました。{0} を開きました".format(open_target)
                if opened
                else "生成が完了しました。{0} を開いてください".format(open_target)
            )
        _cleanup(pending_path)

    def _run_regen_job(job_id, pending_path, folder, target, started_at, addr=None, desired=None):
        """ワーカースレッド: /draft-regenerate をヘッドレス実行し、完了後に対象/compare を再オープン(§4.4)。

        既存 _run_job と同型。build_regenerate_command(最小権限・危険フラグ非含有)を shell=False で実行。
        成功時 {folder}/compare.html があれば compare を、無ければ target を build_open_command で開く(U-7)。

        ★型入れ替え(KLK-079)のときは、完了後に**実ファイルを読み直して型が変わったかを確かめる**。
          このリポジトリは「ブリッジが指示 → LLM が生成 → 守ったかは誰も見ていない」形で
          4回失敗している(KLK-064 の登録未到達、KLK-072〜076 の規約無視)。
          同じ形なので、**黙って成功と言わない**。結果は typeApplied で返す。
        """
        cmd = build_regenerate_command(pending_path)
        try:
            proc = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=BRIDGE_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = (
                    "再生成がタイムアウトしました({0}秒)。もう一度お試しください".format(
                        BRIDGE_TIMEOUT_SEC
                    )
                )
            _cleanup(pending_path)
            return
        except Exception as exc:  # 起動失敗(claude 不在など)
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = "再生成の起動に失敗しました: {0}".format(exc)
            _cleanup(pending_path)
            return

        # KLK-018: 上書き方式のため対象の mtime 更新検知を成果物有無の主判定にする(U2)
        abs_regen_target = os.path.join(root, target)
        try:
            artifact_ok = (
                os.path.isfile(abs_regen_target)
                and os.path.getmtime(abs_regen_target) >= started_at.timestamp() - MTIME_TOLERANCE_SEC
            )
        except OSError:
            artifact_ok = False

        if not is_job_success(proc.returncode, artifact_ok):
            # 診断はサーバコンソール(stderr)のみ。生JSONはブラウザ(message)に出さない
            print("[bridge] 再生成 失敗 exit={0}".format(proc.returncode), file=sys.stderr)
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = "再生成できませんでした。もう一度お試しください。解決しない場合は Claude Code（claude）が起動しているかご確認ください"
            _cleanup(pending_path)
            return

        # 上書き(U-4)なので compare.html/index の src は不変 → 対象を再オープンでリロード反映(U-7)
        compare_rel = "{0}/compare.html".format(folder)
        open_target = compare_rel if os.path.exists(os.path.join(root, compare_rel)) else target
        abs_target = os.path.join(root, open_target)
        opened = False
        try:
            subprocess.run(
                build_open_command(abs_target, sys.platform),
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
            )
            opened = True
        except Exception:
            opened = False  # 開けなくてもパス表示で無害(グレースフル)

        # ★型入れ替えの後段検証(KLK-079): 指示した型に実際になったかを実ファイルで確かめる
        type_applied = None
        got = None
        quality = []
        if addr:
            # ★型指定の有無にかかわらず品質は見る(KLK-080)。
            #   「型が変わったか」だけでは、16/7 のアタリも masonry の空白も素通りする。
            try:
                with open(abs_regen_target, encoding="utf-8") as fh:
                    quality = find_quality_warnings(fh.read(), addr)
            except OSError:
                quality = []
            if quality:
                for w in quality:
                    print("[bridge] 規約違反の疑い: {0}".format(w), file=sys.stderr)
        if desired and addr:
            hits = []
            try:
                with open(abs_regen_target, encoding="utf-8") as fh:
                    hits = read_section_markers(fh.read(), addr)
            except OSError:
                hits = []
            # ★「指定の型がちょうど1つ」を要求する(KLK-079)。
            #   旧マーカーを外し忘れて2つ残った状態は CSS が競合して崩れるので、成功にしない。
            type_applied = (hits == [desired])
            got = ", ".join(hits) if hits else None
            if not type_applied:
                print(
                    "[bridge] 型が反映されませんでした addr={0} 指示={1} 実際={2}".format(
                        addr, desired, hits or "(読み取れず)"
                    ),
                    file=sys.stderr,
                )

        if type_applied is False:
            if got and desired in got.split(", "):
                why = "古い型が残っています（現在 {0}）".format(got)
            elif got:
                why = "現在 " + got
            else:
                why = "型を読み取れませんでした"
            base = "再生成は完了しましたが、型は {0} になりませんでした（{1}）。".format(desired, why)
        elif type_applied is True:
            base = "{0} を {1} にしました。".format(addr, desired)
        else:
            base = "再生成が完了しました。"

        if quality:
            base += "規約違反の疑いが {0} 件あります。".format(len(quality))

        with jobs_lock:
            jobs[job_id]["state"] = "done"
            jobs[job_id]["folder"] = folder
            jobs[job_id]["openTarget"] = open_target
            jobs[job_id]["typeApplied"] = type_applied
            jobs[job_id]["warnings"] = quality
            jobs[job_id]["message"] = base + (
                "{0} を開きました".format(open_target)
                if opened
                else "{0} を開いてください".format(open_target)
            )
        _cleanup(pending_path)

    def _run_catalog_import_job(job_id, pending_spec_path, started_at):
        """ワーカースレッド: /catalog-import をヘッドレス実行し、catalog.json の登録件数を反映(§4.3)。

        既存 _run_regen_job と同型。build_catalog_import_command(最小権限・危険フラグ非含有)を
        shell=False で実行。登録の最終確定は /catalog-import スキル内の人間確認を経る(§4.5・M5)。
        成功後 catalog/catalog.json の entries 件数を state="done" のメッセージへ反映する。
        """
        def _count_entries():
            try:
                with open(catalog_json_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                return len(data.get("entries", [])) if isinstance(data, dict) else 0
            except (OSError, ValueError):
                return None

        before = _count_entries()
        cmd = build_catalog_import_command(pending_spec_path)
        try:
            proc = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=BRIDGE_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = (
                    "取り込みがタイムアウトしました({0}秒)。もう一度お試しください".format(
                        BRIDGE_TIMEOUT_SEC
                    )
                )
            _cleanup(pending_spec_path)
            return
        except Exception as exc:  # 起動失敗(claude 不在など)
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = "取り込みの起動に失敗しました: {0}".format(exc)
            _cleanup(pending_spec_path)
            return

        # KLK-064: 成果物の主判定を **proposal.json の生成有無** に変更する。
        # 旧判定は「catalog.json が読める」で、これは常に真になるため成否を区別できなかった
        # （ブリッジ経由は非対話ゆえ登録に到達せず、常に「完了・0件」と報告していた不具合の一因）。
        after = _count_entries()
        proposal_path = os.path.join(
            catalog_pending_dir, os.path.basename(pending_spec_path).replace(".import.json", ".proposal.json")
        )
        proposal_ok = os.path.isfile(proposal_path)
        if not is_job_success(proc.returncode, proposal_ok):
            # 診断はサーバコンソール(stderr)のみ。生JSONはブラウザ(message)に出さない
            print("[bridge] 取り込み 失敗 exit={0}".format(proc.returncode), file=sys.stderr)
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = "取り込みできませんでした。もう一度お試しください。解決しない場合は Claude Code（claude）が起動しているかご確認ください"
            _cleanup(pending_spec_path)
            return

        # KLK-064: この時点では**まだ登録していない**。画面での確認・承認を促す文言にする。
        n_items = 0
        try:
            with open(proposal_path, encoding="utf-8") as fh:
                n_items = len(json.load(fh).get("items", []))
        except (OSError, ValueError):
            n_items = 0
        msg = (
            "{0} 件のタグ付け案ができました。下の一覧で内容を確認・修正し、"
            "「この内容で登録」を押すとカタログに登録されます".format(n_items)
        )
        with jobs_lock:
            jobs[job_id]["state"] = "done"
            jobs[job_id]["message"] = msg
        _cleanup(pending_spec_path)

    def _cleanup(pending_path):
        try:
            if os.path.exists(pending_path):
                os.remove(pending_path)
        except OSError:
            pass

    class Handler(BaseHTTPRequestHandler):
        server_version = "klk-draft-bridge/1"

        def log_message(self, fmt, *args):  # 端末を静かに保つ
            sys.stderr.write("[bridge] " + (fmt % args) + "\n")

        # --- helpers ---------------------------------------------------------
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        # --- routing ---------------------------------------------------------
        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._serve_index()
                return
            if path == "/health":
                self._json(200, {"ok": True, "name": "klk-draft-bridge", "version": 1})
                return
            if path.startswith("/status/"):
                self._status(path[len("/status/"):])
                return
            # 実績カタログ(KLK-013・SCR-004・§4.3)
            if path == "/catalog":
                self._serve_catalog_html()
                return
            if path == "/catalog-proposal":
                self._catalog_proposal()
                return
            if path.startswith("/catalog/pending-img/"):
                self._catalog_pending_img(path[len("/catalog/pending-img/"):])
                return
            if path == "/catalog-pending":
                self._catalog_pending()
                return
            # 型入れ替え(KLK-078)—実ページの番地・現在型・選べる型
            if path == "/sections":
                self._sections()
                return
            if path == "/catalog.json":
                self._serve_catalog_json()
                return
            if path.startswith("/catalog/img/"):
                self._serve_catalog_img(path[len("/catalog/img/"):])
                return
            # 配色ジェネレーター(KLK-019・REQ-003)。ブリッジ配信時 ../palette/index.html は /palette/index.html に解決
            if path in ("/palette", "/palette/", "/palette/index.html"):
                self._serve_palette()
                return
            self._json(404, {"error": "not found"})

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if path == "/generate":
                self._generate()
                return
            if path == "/regenerate":
                self._regenerate()
                return
            # 見本サイトURLからの配色読み取り(KLK-083・REQ-102)
            if path == "/read-colors":
                self._read_colors()
                return
            if path == "/catalog-import":
                self._catalog_import()
                return
            if path == "/catalog-delete":
                self._catalog_delete()
                return
            if path == "/catalog-commit":
                self._catalog_commit()
                return
            if path == "/catalog-upload":
                self._catalog_upload()
                return
            if path == "/upload":
                self._upload()
                return
            self._json(404, {"error": "not found"})

        # --- handlers --------------------------------------------------------
        def _serve_index(self):
            try:
                with open(index_path, "rb") as fh:
                    body = fh.read()
            except OSError:
                self._json(500, {"error": "index.html を読み込めません"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _serve_palette(self):
            """GET /palette[/][index.html] — 配色ジェネレーター palette/index.html を配信
               (KLK-019・REQ-003・_serve_index と同型・固定1ファイル決め打ち)。"""
            try:
                with open(palette_index_path, "rb") as fh:
                    body = fh.read()
            except OSError:
                self._json(500, {"error": "palette/index.html を読み込めません"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        # --- 実績カタログ(KLK-013・SCR-004)handlers --------------------------
        def _serve_catalog_html(self):
            """GET /catalog — SCR-004本体 draft-gen/catalog.html を配信(§4.3・_serve_index と同型)。"""
            try:
                with open(catalog_html_path, "rb") as fh:
                    body = fh.read()
            except OSError:
                self._json(500, {"error": "catalog.html を読み込めません"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _serve_catalog_json(self):
            """GET /catalog.json — catalog/catalog.json を検証し配信(§4.3)。

            不在/読取不能/不正なら空カタログ({schema,version,entries:[]})を 200 で返す
            (画面は空状態表示・機密を漏らさない・グレースフル)。
            """
            try:
                with open(catalog_json_path, encoding="utf-8") as fh:
                    obj = json.load(fh)
            except (OSError, ValueError):
                self._json(200, dict(_EMPTY_CATALOG))
                return
            ok, _errors = validate_catalog(obj)
            self._json(200, obj if ok else dict(_EMPTY_CATALOG))

        def _serve_catalog_img(self, raw_name):
            """GET /catalog/img/{name} — 画像を配信(§4.3・多層防御 R-5)。

            ①URLデコード ②is_safe_catalog_name(文字集合/'..'/'/'/'\\'拒否)→ 不正 400
            ③os.path.realpath で catalog/img/ 配下に収まることを再確認(シンボリックリンク保険)
            ④実在確認(不在 404) ⑤catalog_content_type で Content-Type 設定し 200。
            """
            name = urllib.parse.unquote(raw_name)
            if not is_safe_catalog_name(name):
                self._json(400, {"error": "画像名が不正です"})
                return
            base = os.path.realpath(catalog_img_dir)
            target = os.path.realpath(os.path.join(catalog_img_dir, name))
            if target != base and not target.startswith(base + os.sep):
                self._json(400, {"error": "画像名が不正です"})
                return
            if not os.path.isfile(target):
                self._json(404, {"error": "画像が見つかりません"})
                return
            try:
                with open(target, "rb") as fh:
                    body = fh.read()
            except OSError:
                self._json(500, {"error": "画像を読み込めません"})
                return
            self.send_response(200)
            self.send_header("Content-Type", catalog_content_type(name))
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _catalog_import(self):
            """POST /catalog-import — 画像取り込みをヘッドレス起動(§4.3・_regenerate と同型)。

            防御順: ①Origin(403) ②サイズ上限(413/400) ③JSON(400) ④validate_import_request(400)
            ⑤catalog/.pending/ 内対象の実在確認(404) ⑥jobId 発行→.import.json 出力→worker→202。
            """
            # ① Origin 検証(M-SEC-1): body 読取前に弾く(_generate と同一)
            if not is_allowed_origin(self.headers.get("Origin"), BRIDGE_HOST, port):
                self._json(403, {"error": "許可されていないオリジンです"})
                return
            # ② サイズ上限(L-1): body 読取前に検証(多層防御)
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length < 0:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length > MAX_BODY_BYTES:
                self._json(413, {"error": "リクエストが大きすぎます"})
                return
            raw = self.rfile.read(length) if length else b""
            # ③ JSON パース
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "リクエストJSONを解析できません"})
                return
            # ④ 入力検証(注入対策)
            ok, errors = validate_import_request(obj)
            if not ok:
                self._json(400, {"error": "・".join(errors)})
                return

            # ⑤ catalog/.pending/ 内の対象を確定(実在確認)
            if not os.path.isdir(catalog_pending_dir):
                self._json(404, {"error": "取り込み待ちフォルダ(catalog/.pending/)がありません"})
                return
            if obj.get("all") is True:
                try:
                    names = sorted(
                        n for n in os.listdir(catalog_pending_dir)
                        if is_safe_catalog_name(n)
                        and catalog_import_ext_ok(n)  # 取込許可集合(jpg/jpeg/png/webp)で判定・KLK-033
                    )
                except OSError:
                    names = []
            else:
                names = list(obj["files"])
                missing = [
                    n for n in names
                    if not os.path.isfile(os.path.join(catalog_pending_dir, n))
                ]
                if missing:
                    self._json(404, {"error": "取り込み対象が見つかりません: {0}".format("・".join(missing))})
                    return
            if not names:
                self._json(404, {"error": "取り込み対象の画像がありません(catalog/.pending/ に JPG / PNG / WebP を置いてください)"})
                return

            # ⑥ jobId 発行 → 検証済みジョブ仕様を pending へ書き worker 起動(プロンプトは pending パスのみ)
            job_id = uuid.uuid4().hex
            os.makedirs(catalog_pending_dir, exist_ok=True)
            pending_spec_path = os.path.join(catalog_pending_dir, job_id + ".import.json")
            with open(pending_spec_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "schema": "catalog-import-job",
                        "version": 1,
                        # KLK-064: ブリッジ経由は**提案モード**。スキルは catalog.json を書かず、
                        # タグ付け案を proposalPath へ書き出して終了する（承認は SCR-004 の画面で行う）。
                        "mode": "propose",
                        "files": names,
                        "proposalPath": os.path.join(
                            "catalog", ".pending", job_id + ".proposal.json"
                        ),
                        "jobId": job_id,
                    },
                    fh,
                    ensure_ascii=False,
                    indent=2,
                )

            started_at = _now()
            with jobs_lock:
                jobs[job_id] = {
                    "state": "running",
                    "started_at": started_at,
                    "folder": None,
                    "openTarget": None,
                    "message": "取り込み中…",
                }

            worker = threading.Thread(
                target=_run_catalog_import_job,
                args=(job_id, pending_spec_path, started_at),
                daemon=True,
            )
            worker.start()
            self._json(202, {"jobId": job_id})

        def _upload(self):
            """POST /upload — MVフリー実写真の生バイナリ直POST受信(KLK-020・§4.3・§3.2/3.3/3.4)。

            生バイナリ直POST(multipart/cgi 非使用)。既存POSTと同一防御順:
            ①Origin(403) ②サイズ上限(UPLOAD_MAX_BODY_BYTES 超過→413 / 不正Content-Length→400)
            ③本体読取(空→400) ④マジックバイトで JPEG/PNG 二重検証(非画像→400。Content-Type は信用しない)
            ⑤保存: 保存名はサーバ生成 upl-<uuid>.<ext> で mockups/.uploads/ へ(クライアントのファイル名・
                    Content-Type を保存パスに未使用＝パストラバーサル面ゼロ) ⑥200 JSON で savedName 返却。
            新規経路にサブプロセス起動は無い(画像保存のみ・危険フラグ非含有・localhost限定は既存防御で維持)。
            """
            # ① Origin 検証(M-SEC-1): body 読取前に弾く(_generate と同一)
            if not is_allowed_origin(self.headers.get("Origin"), BRIDGE_HOST, port):
                self._json(403, {"error": "許可されていないオリジンです"})
                return
            # ② サイズ上限: /upload 専用 UPLOAD_MAX_BODY_BYTES(8 MiB)を body 読取前に検証(多層防御)
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length < 0:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length > UPLOAD_MAX_BODY_BYTES:
                self._json(413, {"error": "リクエストが大きすぎます"})
                return
            # ③ 本体読取(生バイナリ)
            raw = self.rfile.read(length) if length else b""
            if not raw:
                self._json(400, {"error": "画像がありません"})
                return
            # ④ 画像判定(マジックバイト・Content-Type は信用しない)
            ext = sniff_image_ext(raw[:16])
            if ext is None:
                self._json(400, {"error": "画像として認識できません(JPEG/PNGのみ)"})
                return
            # ⑤ 保存(保存名はサーバ生成＝安全名・basename・危険文字なし)
            saved_name = "upl-" + uuid.uuid4().hex + ext
            try:
                os.makedirs(uploads_dir, exist_ok=True)
                with open(os.path.join(uploads_dir, saved_name), "wb") as fh:
                    fh.write(raw)
            except OSError:
                self._json(500, {"error": "画像を保存できませんでした"})
                return
            # ⑥ 応答(保存名を返す。instruction.mvPhoto.file に載せる)
            self._json(200, {"savedName": saved_name})

        def _catalog_upload(self):
            """POST /catalog-upload — 実績・見本画像の生バイナリ直POST受信(KLK-063・SCR-004 のD&D/ファイル選択)。

            `_upload`(MV写真・KLK-020)と**同一の6段防御順**を踏襲する(multipart/cgi 非使用):
            ①Origin(403) ②サイズ上限(CATALOG_UPLOAD_MAX_BODY_BYTES 超過→413 / 不正 Content-Length→400)
            ③本体読取(空→400) ④マジックバイトで JPEG/PNG/WebP 三重検証(非画像→400。Content-Type は信用しない)
            ⑤保存: 保存名はサーバ生成 pnd-<uuid>.<ext> で catalog/.pending/ へ(クライアントのファイル名・
                    Content-Type を保存パスに未使用＝パストラバーサル面ゼロ)
            ⑥200 JSON で savedName と取り込み待ち件数を返却。

            保存先は catalog/.pending/ に固定する。**catalog/ の外へは書かない**(REQ-011 / NFR-004 /
            CATALOG_RULES §4)。登録は従来どおり POST /catalog-import → 人間承認後のみ(本経路は保存だけ)。
            """
            # ① Origin 検証(M-SEC-1): body 読取前に弾く(_upload と同一)
            if not is_allowed_origin(self.headers.get("Origin"), BRIDGE_HOST, port):
                self._json(403, {"error": "許可されていないオリジンです"})
                return
            # ② サイズ上限: body 読取前に検証(多層防御)
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length < 0:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length > CATALOG_UPLOAD_MAX_BODY_BYTES:
                self._json(413, {"error": "リクエストが大きすぎます(1枚 8MB まで)"})
                return
            # ③ 本体読取(生バイナリ)
            raw = self.rfile.read(length) if length else b""
            if not raw:
                self._json(400, {"error": "画像がありません"})
                return
            # ④ 画像判定(マジックバイト・Content-Type/拡張子は信用しない)
            ext = sniff_catalog_image_ext(raw[:16])
            if ext is None:
                self._json(400, {"error": "画像として認識できません(JPEG/PNG/WebP のみ)"})
                return
            # ⑤ 保存(保存名はサーバ生成＝安全名・basename・危険文字なし)
            saved_name = "pnd-" + uuid.uuid4().hex + ext
            try:
                os.makedirs(catalog_pending_dir, exist_ok=True)
                with open(os.path.join(catalog_pending_dir, saved_name), "wb") as fh:
                    fh.write(raw)
            except OSError:
                self._json(500, {"error": "画像を保存できませんでした"})
                return
            # ⑥ 応答(保存名＋取り込み待ち件数)
            self._json(200, {"savedName": saved_name, "pendingCount": self._pending_names_count()[1]})

        def _pending_names_count(self):
            """catalog/.pending/ 直下の取り込み対象画像を列挙する(代表名リスト, 件数)。

            ジョブ仕様 *.import.json などの非画像は catalog_import_ext_ok で除外する。
            **KLK-066: 同じ basename の webp/png は同じ画像の2表現なので1件として数える**
            (画像1枚が「2件が取り込み待ち」と表示される混乱を防ぐ)。代表名は登録に使われる側。
            ディレクトリが無い/読めない場合は空を返す(fail-open・ループを止めない)。
            """
            try:
                raw = [
                    n for n in os.listdir(catalog_pending_dir)
                    if catalog_import_ext_ok(n)
                    and os.path.isfile(os.path.join(catalog_pending_dir, n))
                ]
            except OSError:
                raw = []
            groups = pending_groups(raw)
            names = sorted(
                filter(None, (pending_display_name(g) for g in groups.values()))
            )
            return names, len(names)

        def _purge_pending_siblings(self, primary, source_file=None):
            """登録済み画像の「兄弟」を catalog/.pending/ から取り除く(KLK-066)。

            兄弟＝同じ basename のファイル(変換元 webp など)。特定は
            ①提案の sourceFile(あれば) → ②同一 basename の全ファイル の順。
            **catalog_pending_dir 直下に限定**し、catalog/img/ には一切触れない。
            失敗は握りつぶす: 登録は既に確定しており、残骸1つのために巻き戻す方が害が大きい。
            """
            targets = set()
            if source_file and is_safe_catalog_name(source_file):
                targets.add(source_file)
            base = os.path.splitext(primary)[0]
            try:
                for n in os.listdir(catalog_pending_dir):
                    if os.path.splitext(n)[0] == base and catalog_import_ext_ok(n):
                        targets.add(n)
            except OSError:
                pass
            for n in targets:
                if not is_safe_catalog_name(n):
                    continue
                path = os.path.join(catalog_pending_dir, n)
                # 念のため配下確認(パストラバーサル多層防御)
                if os.path.dirname(os.path.abspath(path)) != os.path.abspath(catalog_pending_dir):
                    continue
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError as exc:
                    print("[bridge] 取り込み待ちの片付けに失敗: {0} ({1})".format(n, exc), file=sys.stderr)

        def _purge_proposals(self):
            """catalog/.pending/*.proposal.json を全削除する(KLK-066)。

            提案は「その時点の .pending の写像」であり、登録が済めば必ず陳腐化している。
            除外した画像は .pending に残るので、取り込みを再実行すれば新しい提案が作られる。
            失敗は握りつぶす(登録の成否に影響させない)。
            """
            try:
                for n in os.listdir(catalog_pending_dir):
                    if n.endswith(".proposal.json"):
                        try:
                            os.remove(os.path.join(catalog_pending_dir, n))
                        except OSError as exc:
                            print("[bridge] 提案の片付けに失敗: {0} ({1})".format(n, exc), file=sys.stderr)
            except OSError:
                pass

        def _catalog_pending(self):
            """GET /catalog-pending — 取り込み待ち画像の件数と名前を返す(KLK-063・SCR-004 の件数表示)。

            返すのは catalog/.pending/ 直下の**取り込み対象拡張子のファイル名のみ**。
            アップロード分はサーバ生成名、手動コピー分は利用者自身が置いた名前であり、
            いずれも localhost 限定・Origin 検証済みの本人にしか返らない。画像本体は返さない。
            """
            if not is_allowed_origin(self.headers.get("Origin"), BRIDGE_HOST, port):
                self._json(403, {"error": "許可されていないオリジンです"})
                return
            names, count = self._pending_names_count()
            self._json(200, {"count": count, "names": names})

        def _latest_proposal_path(self):
            """catalog/.pending/*.proposal.json のうち最新(mtime)のパスを返す。無ければ None。"""
            try:
                cands = [
                    os.path.join(catalog_pending_dir, n)
                    for n in os.listdir(catalog_pending_dir)
                    if n.endswith(".proposal.json")
                ]
            except OSError:
                return None
            cands = [c for c in cands if os.path.isfile(c)]
            if not cands:
                return None
            return max(cands, key=lambda p: os.path.getmtime(p))

        def _catalog_proposal(self):
            """GET /catalog-proposal — 最新のタグ付け案を返す(KLK-064・SCR-004 の承認フォーム用)。

            AI が書いた案をそのまま返さず **validate_proposal を通してから**返す(壊れた案で画面が
            崩れるのを防ぐ)。案が無い/壊れている場合は items:[] と理由を返す(ループを止めない)。
            """
            if not is_allowed_origin(self.headers.get("Origin"), BRIDGE_HOST, port):
                self._json(403, {"error": "許可されていないオリジンです"})
                return
            path = self._latest_proposal_path()
            if not path:
                self._json(200, {"items": [], "message": "タグ付け案はまだありません"})
                return
            try:
                with open(path, encoding="utf-8") as fh:
                    obj = json.load(fh)
            except (OSError, ValueError):
                self._json(200, {"items": [], "message": "タグ付け案を読み込めませんでした"})
                return
            ok, errors = validate_proposal(obj)
            if not ok:
                print("[bridge] proposal 検証NG: {0}".format(errors), file=sys.stderr)
                self._json(200, {"items": [], "message": "タグ付け案の形式が不正です"})
                return
            # .pending/ に実在する分だけ返す(取り込み済み/削除済みを除く)
            items = [it for it in obj.get("items", [])
                     if os.path.isfile(os.path.join(catalog_pending_dir, it.get("file", "")))]
            self._json(200, {"items": items})

        def _catalog_pending_img(self, raw_name):
            """GET /catalog/pending-img/{name} — 承認フォームのサムネイル配信(KLK-064)。

            **catalog/.pending/ 直下・安全名・配信許可MIMEのみ**。`catalog/` の外は配信しない。
            既存 _serve_catalog_img と同じ防御(is_safe_catalog_name → 実在確認 → MIME)。
            """
            name = urllib.parse.unquote(raw_name or "")
            if not is_safe_catalog_name(name):
                self._json(400, {"error": "ファイル名が不正です"})
                return
            ctype = catalog_content_type(name)
            if ctype is None:
                self._json(404, {"error": "not found"})
                return
            target = os.path.join(catalog_pending_dir, name)
            if not os.path.isfile(target):
                self._json(404, {"error": "not found"})
                return
            try:
                with open(target, "rb") as fh:
                    body = fh.read()
            except OSError:
                self._json(500, {"error": "画像を読み込めませんでした"})
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _catalog_commit(self):
            """POST /catalog-commit — 人間が画面で承認した分だけを登録する(KLK-064・§3.3)。

            **登録は AI ではなく本メソッド(Python)が決定的に行う**。AI は提案しかしない。
            防御/処理順: ①Origin(403) ②サイズ上限(413/400) ③JSON(400) ④validate_commit_request(400)
            ⑤対象が .pending/ に実在(400) ⑥id 採番 ⑦追記後の全体を validate_catalog(400・**1件も書かない**)
            ⑧画像移動 ⑨catalog.json を一時ファイル→os.replace で原子的に置換 ⑩200。
            ⑨で失敗したら⑧の移動を巻き戻す(all-or-nothing)。書き込み先は catalog/ 配下のみ(REQ-011)。
            """
            # ① Origin
            if not is_allowed_origin(self.headers.get("Origin"), BRIDGE_HOST, port):
                self._json(403, {"error": "許可されていないオリジンです"})
                return
            # ② サイズ上限
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length < 0:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length > MAX_BODY_BYTES:
                self._json(413, {"error": "リクエストが大きすぎます"})
                return
            raw = self.rfile.read(length) if length else b""
            # ③ JSON
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "リクエストJSONを解析できません"})
                return
            # ④ 入力検証
            ok, errors = validate_commit_request(obj)
            if not ok:
                self._json(400, {"error": "承認内容が不正です", "details": errors[:5]})
                return
            items = obj["items"]
            # ⑤ 対象の実在確認
            missing = [it["file"] for it in items
                       if not os.path.isfile(os.path.join(catalog_pending_dir, it["file"]))]
            if missing:
                self._json(400, {"error": "取り込み待ちに見つからない画像があります", "details": missing[:5]})
                return
            # 既存カタログ読み込み(無ければ空から作る)
            try:
                with open(catalog_json_path, encoding="utf-8") as fh:
                    catalog = json.load(fh)
            except (OSError, ValueError):
                catalog = {"schema": "klk-catalog", "version": 1, "entries": []}
            if not isinstance(catalog, dict) or not isinstance(catalog.get("entries"), list):
                self._json(500, {"error": "カタログの形式が不正です。手動で確認してください"})
                return
            try:
                img_names = os.listdir(catalog_img_dir)
            except OSError:
                img_names = []
            # ⑥ id 採番 + エントリ組み立て
            existing_ids = [e.get("id") for e in catalog["entries"] if isinstance(e, dict)]
            planned = []   # (src_path, dst_path, entry)
            for it in items:
                new_id = next_catalog_id(existing_ids, img_names)
                existing_ids.append(new_id)
                ext = os.path.splitext(it["file"])[1].lower()
                fname = new_id + ext
                img_names.append(fname)
                entry = {
                    "id": new_id,
                    "file": fname,
                    "title": (it.get("title") or "").strip() or new_id,
                    "industry": it["industry"].strip(),
                    "taste": it["taste"].strip(),
                    "colors": list(it["colors"]),
                    "source": it.get("source") if it.get("source") in ("own", "ref") else "own",
                    "addedAt": iso_now(),
                }
                if isinstance(it.get("columns"), str) and it["columns"].strip():
                    entry["columns"] = it["columns"].strip()
                if isinstance(it.get("note"), str) and it["note"].strip():
                    entry["note"] = it["note"].strip()
                if isinstance(it.get("sectionLayouts"), dict) and it["sectionLayouts"]:
                    entry["sectionLayouts"] = it["sectionLayouts"]
                planned.append((
                    os.path.join(catalog_pending_dir, it["file"]),
                    os.path.join(catalog_img_dir, fname),
                    entry,
                ))
            # ⑦ 追記後の全体を検証(不正なら1件も書かない)
            merged = dict(catalog)
            merged["entries"] = list(catalog["entries"]) + [e for _, _, e in planned]
            ok, errors = validate_catalog(merged)
            if not ok:
                self._json(400, {"error": "登録内容の検証に失敗したため、1件も登録していません",
                                 "details": errors[:5]})
                return
            # ⑧ 画像移動(失敗したら巻き戻す)
            moved = []
            try:
                os.makedirs(catalog_img_dir, exist_ok=True)
                for src, dst, _e in planned:
                    shutil.move(src, dst)
                    moved.append((src, dst))
            except Exception as exc:   # OSError 以外でも必ず巻き戻す
                for src, dst in reversed(moved):
                    try:
                        shutil.move(dst, src)
                    except OSError:
                        pass
                self._json(500, {"error": "画像を移動できませんでした: {0}".format(exc)})
                return
            # ⑨ catalog.json を原子的に置換(一時ファイル→os.replace)
            merged["generatedAt"] = iso_now()
            tmp = catalog_json_path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(merged, fh, ensure_ascii=False, indent=2)
                os.replace(tmp, catalog_json_path)
            except Exception as exc:   # OSError に限定しない: JSON 直列化不能(TypeError)等でも
                                       # 画像移動を必ず巻き戻す(中途半端な状態を残さない・KLK-064)
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                for src, dst in reversed(moved):   # 画像移動を巻き戻す(all-or-nothing)
                    try:
                        shutil.move(dst, src)
                    except OSError:
                        pass
                self._json(500, {"error": "カタログを保存できませんでした: {0}".format(exc)})
                return
            # ⑩ 片付け(KLK-066・登録が確定してから)。失敗しても登録は有効なので握りつぶす。
            for it, (_src, _dst, _e) in zip(items, planned):
                self._purge_pending_siblings(it["file"], it.get("sourceFile"))
            self._purge_proposals()
            # ⑪ 応答
            self._json(200, {
                "registered": len(planned),
                "total": len(merged["entries"]),
                "ids": [e["id"] for _, _, e in planned],
                "pendingCount": self._pending_names_count()[1],
            })

        def _catalog_delete(self):
            """POST /catalog-delete — カタログから登録を取り消す(KLK-068・_catalog_commit の逆操作)。

            **画像は削除せず catalog/.trash/ へ退避する。** catalog/ は Git 管理外(REQ-011)で
            `git revert` では戻せないため、登録の誤り(消せば直る)と削除の誤り(原本を失う)は
            リスクが非対称。退避なら人間が後から戻せる。自動削除はしない。

            処理順: ①Origin(403) ②サイズ上限(413/400) ③JSON(400) ④validate_delete_request(400)
            ⑤catalog.json 内の実在確認(404・部分欠落でも全体を拒否) ⑥削除後の全体を validate_catalog
            (400・**1件も消さない**) ⑦画像を .trash へ退避 ⑧一時ファイル→os.replace で原子的置換
            ⑨200。⑧で失敗したら⑦を巻き戻す(あらゆる例外で・KLK-064 の教訓)。
            """
            # ① Origin
            if not is_allowed_origin(self.headers.get("Origin"), BRIDGE_HOST, port):
                self._json(403, {"error": "許可されていないオリジンです"})
                return
            # ② サイズ上限
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length < 0:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length > MAX_BODY_BYTES:
                self._json(413, {"error": "リクエストが大きすぎます"})
                return
            raw = self.rfile.read(length) if length else b""
            # ③ JSON
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "リクエストJSONを解析できません"})
                return
            # ④ 入力検証
            ok, errors = validate_delete_request(obj)
            if not ok:
                self._json(400, {"error": "削除指示が不正です", "details": errors[:5]})
                return
            ids = list(dict.fromkeys(obj["ids"]))   # 重複指定を畳む
            # 既存カタログ
            try:
                with open(catalog_json_path, encoding="utf-8") as fh:
                    catalog = json.load(fh)
            except (OSError, ValueError):
                self._json(500, {"error": "カタログを読み込めませんでした"})
                return
            if not isinstance(catalog, dict) or not isinstance(catalog.get("entries"), list):
                self._json(500, {"error": "カタログの形式が不正です。手動で確認してください"})
                return
            # ⑤ 実在確認(部分欠落でも全体を拒否＝何が消えたか曖昧にしない)
            by_id = {e.get("id"): e for e in catalog["entries"] if isinstance(e, dict)}
            missing = [i for i in ids if i not in by_id]
            if missing:
                self._json(404, {"error": "カタログに見つからない項目があります", "details": missing[:5]})
                return
            # ⑥ 削除後の全体を検証(不正なら1件も消さない)
            merged = dict(catalog)
            merged["entries"] = [e for e in catalog["entries"]
                                 if not (isinstance(e, dict) and e.get("id") in ids)]
            ok, errors = validate_catalog(merged)
            if not ok:
                self._json(400, {"error": "削除後の検証に失敗したため、1件も削除していません",
                                 "details": errors[:5]})
                return
            # ⑦ 画像を .trash へ退避(失敗しても続行＝カタログ側の整合を優先。ログのみ)
            moved = []
            try:
                os.makedirs(catalog_trash_dir, exist_ok=True)
            except OSError:
                pass
            for i in ids:
                fname = (by_id[i] or {}).get("file")
                if not (isinstance(fname, str) and is_safe_catalog_name(fname)):
                    continue
                src = os.path.join(catalog_img_dir, fname)
                dst = os.path.join(catalog_trash_dir, fname)
                if os.path.dirname(os.path.abspath(src)) != os.path.abspath(catalog_img_dir):
                    continue   # 配下確認(多層防御)
                try:
                    if os.path.isfile(src):
                        shutil.move(src, dst)
                        moved.append((src, dst))
                except OSError as exc:
                    print("[bridge] 画像の退避に失敗: {0} ({1})".format(fname, exc), file=sys.stderr)
            # ⑧ catalog.json を原子的に置換
            merged["generatedAt"] = iso_now()
            tmp = catalog_json_path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(merged, fh, ensure_ascii=False, indent=2)
                os.replace(tmp, catalog_json_path)
            except Exception as exc:   # OSError に限定しない(KLK-064 の教訓・必ず巻き戻す)
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                for src, dst in reversed(moved):
                    try:
                        shutil.move(dst, src)
                    except OSError:
                        pass
                self._json(500, {"error": "カタログを保存できませんでした: {0}".format(exc)})
                return
            # ⑨ 応答
            self._json(200, {
                "deleted": len(ids),
                "total": len(merged["entries"]),
                "ids": ids,
                "trashDir": "catalog/.trash",
            })

        def _generate(self):
            # ① Origin 検証(M-SEC-1): 状態変更は同一オリジン(+file://)のみ許可。body 読取前に弾く
            if not is_allowed_origin(self.headers.get("Origin"), BRIDGE_HOST, port):
                self._json(403, {"error": "許可されていないオリジンです"})
                return
            # ② サイズ上限(L-1): Content-Length を body 読取前に検証(多層防御)
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length < 0:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length > MAX_BODY_BYTES:
                self._json(413, {"error": "リクエストが大きすぎます"})
                return
            raw = self.rfile.read(length) if length else b""
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "生成指示書JSONを解析できません"})
                return

            ok, errors = validate_instruction(obj)
            if not ok:
                self._json(400, {"error": "・".join(errors)})
                return

            job_id = uuid.uuid4().hex
            os.makedirs(pending_dir, exist_ok=True)
            pending_path = os.path.join(pending_dir, job_id + ".json")
            with open(pending_path, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, ensure_ascii=False, indent=2)

            project = obj.get("meta", {}).get("project", "") if isinstance(obj.get("meta"), dict) else ""
            variants = obj.get("output", {}).get("variants", 1) if isinstance(obj.get("output"), dict) else 1

            started_at = _now()
            with jobs_lock:
                jobs[job_id] = {
                    "state": "running",
                    "started_at": started_at,
                    "folder": None,
                    "openTarget": None,
                    "message": "生成中…",
                }

            worker = threading.Thread(
                target=_run_job,
                args=(job_id, pending_path, project, variants, started_at),
                daemon=True,
            )
            worker.start()
            self._json(202, {"jobId": job_id})

        def _read_colors(self):
            """POST /read-colors — 見本サイトの配色を読み取る(KLK-083・REQ-102)。body={url}。

            防御順: ①Origin(403) ②サイズ上限(413/400) ③JSON(400) ④URL 構文(400)
            ⑤**SSRF ガード**（fetch_text の中で毎ホップ検査・内部宛は 400 相当のエラー文言）
            ⑥取得・抽出 → 200。既存の /upload・/regenerate と同じ防御の並びに合わせている。

            ★このエンドポイントは**外へ出る唯一の口**。読むだけで、取得内容は保存しない
              （画面に色を返すだけ）。生成パイプラインには触れない。
            """
            # ① Origin(M-SEC-1)
            _origin = self.headers.get("Origin")
            if not is_allowed_origin(_origin, BRIDGE_HOST, port):
                # ★受け取った Origin を添える(KLK-084)。「許可されていない」だけでは
                #   利用者も開発者も原因を追えない。相手が自分で送った値なので秘密ではない。
                self._json(403, {"error": "許可されていないオリジンです（受信: {0}／期待: "
                                          "このブリッジと同じ 127.0.0.1:{1} で開いた画面）".format(
                                              str(_origin)[:120], port)})
                return
            # ② サイズ上限(L-1)
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length < 0:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length > MAX_BODY_BYTES:
                self._json(413, {"error": "リクエストが大きすぎます"})
                return
            raw = self.rfile.read(length) if length else b""
            # ③ JSON
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "リクエストJSONを解析できません"})
                return
            if not isinstance(obj, dict):
                self._json(400, {"error": "リクエストがオブジェクトではありません"})
                return
            # ④ URL 構文
            url = obj.get("url")
            if not is_safe_external_url(url):
                self._json(400, {"error": "URL が不正です（http と https のみ・資格情報つきは不可）"})
                return
            # ⑤⑥ 取得と抽出（SSRF ガードは fetch_text が毎ホップ行う）
            result = read_site_colors(url)
            self._json(200 if result.get("ok") else 400, result)

        def _sections(self):
            """GET /sections?folder=&letter= — 実ページの番地・現在の型・選べる型を返す(KLK-078)。

            ★compare.html に番地を焼き込まない**ため**のエンドポイント。
              焼き込むと、セクション構成が指示書ごとに変わる現在の仕様(§2.1)と食い違い、
              「選択肢にあるのに 404」「実在するのに選べない」が起きる(見本3点すべてで発生していた)。

            防御: ①folder(400) ②letter(400) ③対象ファイル不在(404)。既存の純関数を再利用する。
            読むだけ・副作用なし。Origin 検証は行わない(GET・機微情報なし・/catalog.json と同方針)。
            """
            qs = urllib.parse.parse_qs(
                self.path.split("?", 1)[1] if "?" in self.path else ""
            )
            folder = (qs.get("folder") or [None])[0]
            letter = (qs.get("letter") or [""])[0]
            if not is_safe_mockups_folder(folder):
                self._json(400, {"error": "folder が不正です(mockups/ 配下の相対パスのみ)"})
                return
            if not is_valid_letter(letter):
                self._json(400, {"error": "letter が不正です(a-c または未指定)"})
                return
            target = resolve_target_html(folder, letter)
            abs_target = os.path.join(root, target)
            if not os.path.isfile(abs_target):
                self._json(404, {"error": "対象ファイルが見つかりません: {0}".format(target)})
                return
            try:
                with open(abs_target, encoding="utf-8") as fh:
                    html = fh.read()
            except OSError:
                self._json(500, {"error": "対象ファイルを読み込めません"})
                return
            sections = [
                {
                    "addr": addr,
                    "current": read_section_marker(html, addr),
                    "pool": list(pool_for_addr(addr)),
                }
                for addr in list_page_addrs(html)
            ]
            self._json(200, {"letter": letter, "target": target, "sections": sections})

        def _regenerate(self):
            """POST /regenerate — 部分再生成(KLK-012・§4.4)。body={folder, letter, addr}。

            防御順: ①Origin(403) ②サイズ上限(413/400) ③JSON(400) ④folder/letter/addr 検証(400)
            ⑤target 実ファイル不在(404) ⑥find_target_section 一意性(unknown→404/duplicate→400・
            claude 起動前・ファイル無変更) ⑦jobId 発行→.regen.json 書出し→worker 起動→202。
            既存 _generate と同じ防御(is_allowed_origin/MAX_BODY_BYTES)を再利用する。
            """
            # ① Origin 検証(M-SEC-1): body 読取前に弾く(_generate と同一)
            if not is_allowed_origin(self.headers.get("Origin"), BRIDGE_HOST, port):
                self._json(403, {"error": "許可されていないオリジンです"})
                return
            # ② サイズ上限(L-1): body 読取前に検証(多層防御)
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length < 0:
                self._json(400, {"error": "Content-Length ヘッダが不正です"})
                return
            if length > MAX_BODY_BYTES:
                self._json(413, {"error": "リクエストが大きすぎます"})
                return
            raw = self.rfile.read(length) if length else b""
            # ③ JSON パース
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "リクエストJSONを解析できません"})
                return
            if not isinstance(obj, dict):
                self._json(400, {"error": "リクエストがオブジェクトではありません"})
                return

            # ④ folder/letter/addr の検証(注入対策・U-5)
            folder = obj.get("folder")
            letter = obj.get("letter")
            addr = obj.get("addr")
            if not is_safe_mockups_folder(folder):
                self._json(400, {"error": "folder が不正です(mockups/ 配下の相対パスのみ)"})
                return
            if not is_valid_letter(letter):
                self._json(400, {"error": "letter が不正です(a-c または未指定)"})
                return
            if not is_valid_addr(addr):
                self._json(400, {"error": "番地ラベルが不正です"})
                return
            # ⑧ desiredType(KLK-079・型入れ替え)。省略可＝従来の表引きへ落ちる。
            #    ★パターン照合ではなく**その番地のプールに載っているか**で判定する(許可リスト)。
            desired = obj.get("desiredType")
            if desired is not None and not isinstance(desired, str):
                self._json(400, {"error": "desiredType が不正です"})
                return
            if not is_valid_desired_type(addr, desired):
                pool = pool_for_addr(addr)
                self._json(
                    400,
                    {
                        "error": "{0} に指定できない型です: {1}".format(addr, desired),
                        "pool": list(pool),
                    },
                )
                return
            desired = desired or None

            # ⑤ 対象HTMLの実在確認(上書き対象・U-4)
            target = resolve_target_html(folder, letter)
            abs_target = os.path.join(root, target)
            if not os.path.isfile(abs_target):
                self._json(404, {"error": "対象ファイルが見つかりません: {0}".format(target)})
                return

            # ⑥ 対象セクションの一意性(claude 起動前・ファイル無変更・SPEC §7)
            try:
                with open(abs_target, encoding="utf-8") as fh:
                    html = fh.read()
            except OSError:
                self._json(500, {"error": "対象ファイルを読み込めません"})
                return
            span, info = find_target_section(html, addr)
            if span is None and info == "unknown":
                self._json(404, {"error": "番地 {0} が見つかりません".format(addr)})
                return
            if span is None and info == "duplicate":
                self._json(400, {"error": "番地 {0} が重複しています".format(addr)})
                return

            # ⑦ jobId 発行 → 検証済みジョブ仕様を pending へ書き worker 起動(プロンプトは pending パスのみ)
            job_id = uuid.uuid4().hex
            os.makedirs(pending_dir, exist_ok=True)
            pending_path = os.path.join(pending_dir, job_id + ".regen.json")
            spec = {
                "schema": "design-regenerate-job",
                "version": 1,
                "target": target,
                "addr": addr,
            }
            if desired:
                # ★検証済みの語彙だけを書く(可変ユーザー文字列をプロンプト経路に載せない)
                spec["desiredType"] = desired
            with open(pending_path, "w", encoding="utf-8") as fh:
                json.dump(spec, fh, ensure_ascii=False, indent=2)

            started_at = _now()
            with jobs_lock:
                jobs[job_id] = {
                    "state": "running",
                    "started_at": started_at,
                    "folder": folder,
                    "openTarget": None,
                    "message": "再生成中…",
                    "desiredType": desired,
                    "typeApplied": None,   # 型指定なし=None / 適用済み=True / 反映されず=False
                    "warnings": [],        # 規約違反の疑い(KLK-080)
                }

            worker = threading.Thread(
                target=_run_regen_job,
                args=(job_id, pending_path, folder, target, started_at, addr, desired),
                daemon=True,
            )
            worker.start()
            self._json(202, {"jobId": job_id})

        def _status(self, job_id):
            if not JOB_ID_RE.match(job_id):
                self._json(400, {"error": "不正な jobId です"})
                return
            with jobs_lock:
                job = jobs.get(job_id)
                if job is None:
                    self._json(404, {"error": "ジョブが見つかりません"})
                    return
                elapsed = int((_now() - job["started_at"]).total_seconds())
                self._json(
                    200,
                    {
                        "state": job["state"],
                        "elapsedSec": elapsed,
                        "folder": job["folder"],
                        "openTarget": job["openTarget"],
                        "message": job["message"],
                        # 型入れ替え(KLK-079): None=型指定なし / True=適用 / False=反映されず
                        "typeApplied": job.get("typeApplied"),
                        "desiredType": job.get("desiredType"),
                        # 規約違反の疑い(KLK-080)。型が変わっても、これが空でなければ成功と同じ顔をさせない
                        "warnings": job.get("warnings") or [],
                    },
                )

    httpd = ThreadingHTTPServer((BRIDGE_HOST, port), Handler)
    url = "http://{0}:{1}/".format(BRIDGE_HOST, port)
    sys.stderr.write("[bridge] listening on {0} (Ctrl+C で停止)\n".format(url))
    try:
        subprocess.run(build_open_command(url, sys.platform), capture_output=True, timeout=15)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[bridge] 停止しました\n")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    _port = int(os.environ.get("KLK_BRIDGE_PORT") or DEFAULT_PORT)
    _run_server(_port)
