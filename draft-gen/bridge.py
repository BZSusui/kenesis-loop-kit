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
import json
import os
import re
import subprocess
import sys
import urllib.parse

# ============================================================================
# 定数
# ============================================================================
BRIDGE_HOST = "127.0.0.1"          # ★ 0.0.0.0 禁止(U-8/NFR-004)
DEFAULT_PORT = 8765                # env KLK_BRIDGE_PORT で上書き可(U-4)
BRIDGE_TIMEOUT_SEC = 900           # subprocess ハードタイムアウト(NFR-001 目安10分に余裕)
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

# 実績カタログ(KLK-013・SCR-004・REQ-105/106)—主配色7カテゴリ/安全名/MIME
CANONICAL_COLORS = {"グリーン", "ブルー", "レッド", "ゴールド", "ピンク", "モノトーン", "マルチカラー"}  # ワイヤー主配色チップ7値(§3.3・KLK-016で「マルチカラー」を追加)
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
    # 旧 instruction は分岐に入らない)。colors は7カテゴリ(1..3件・マルチカラー単独)、
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
                            or ("マルチカラー" in t_colors and len(t_colors) > 1):
                        errors.append(
                            "references.thumbnails[{0}].colors が不正です(7カテゴリ・1..3件・マルチカラー単独)".format(i))
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

    None(不在)/"null"(file://) を許可、http://{host}:{port} と http://localhost:{port}
    を許可、それ以外は False。副作用なし・import 単体テスト対象(S群)。
    許可リスト文字列は format プレースホルダ/ローカルホストで組む(S10 外部URL検査に非抵触)。
    """
    if origin is None or origin == "null":
        return True
    allowed = ("http://{0}:{1}".format(host, port), "http://localhost:{0}".format(port))
    return origin in allowed


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
    # pin より前の最も近い <div class="sec ...> を開始点にする
    start = None
    for m in re.finditer(r'<div\s+class="sec\b', html):
        if m.start() < pin_pos:
            start = m.start()
        else:
            break
    if start is None:
        return (None, "unknown")

    # <div ...>/<div>/</div> の入れ子均衡で対応する終端 </div> を探す
    depth = 0
    end = None
    for m in re.compile(r'<div\b|</div>').finditer(html, start):
        if m.group(0) == "</div>":
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
            # KLK-016: マルチカラーは単独指定のみ(具体色と併用不可)
            if "マルチカラー" in colors and len(colors) != 1:
                errors.append("{0}.colors のマルチカラーは単独指定のみ可です(他色と併用不可)".format(where))
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
    あれば文字列 / colors はあれば CANONICAL_COLORS の 1..3 件(マルチカラーは単独) /
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
        elif "マルチカラー" in cols and len(cols) > 1:
            errors.append("items[{0}].colors のマルチカラーは単独指定のみです".format(i))
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
     '--permission-mode','acceptEdits','--output-format','json']
    allow_open=True のとき ['--allowedTools','Bash(open *)'] を追加(版差の保険・依然最小権限)。
    ★ 全権限スキップ/全許可モードのフラグは決して含めない(build_claude_command と同一方針)。
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
    if allow_open:
        cmd += ["--allowedTools", "Bash(open *)"]
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

    def _run_regen_job(job_id, pending_path, folder, target, started_at):
        """ワーカースレッド: /draft-regenerate をヘッドレス実行し、完了後に対象/compare を再オープン(§4.4)。

        既存 _run_job と同型。build_regenerate_command(最小権限・危険フラグ非含有)を shell=False で実行。
        成功時 {folder}/compare.html があれば compare を、無ければ target を build_open_command で開く(U-7)。
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

        with jobs_lock:
            jobs[job_id]["state"] = "done"
            jobs[job_id]["folder"] = folder
            jobs[job_id]["openTarget"] = open_target
            jobs[job_id]["message"] = (
                "再生成が完了しました。{0} を開きました".format(open_target)
                if opened
                else "再生成が完了しました。{0} を開いてください".format(open_target)
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
            if path == "/catalog-import":
                self._catalog_import()
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
            """catalog/.pending/ 直下の取り込み対象画像を列挙する(名前リスト, 件数)。

            ジョブ仕様 *.import.json などの非画像は catalog_import_ext_ok で除外する。
            ディレクトリが無い/読めない場合は空を返す(fail-open・ループを止めない)。
            """
            try:
                names = sorted(
                    n for n in os.listdir(catalog_pending_dir)
                    if catalog_import_ext_ok(n)
                    and os.path.isfile(os.path.join(catalog_pending_dir, n))
                )
            except OSError:
                names = []
            return names, len(names)

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
            # ⑩ 応答
            self._json(200, {
                "registered": len(planned),
                "total": len(merged["entries"]),
                "ids": [e["id"] for _, _, e in planned],
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
            with open(pending_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "schema": "design-regenerate-job",
                        "version": 1,
                        "target": target,
                        "addr": addr,
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
                    "folder": folder,
                    "openTarget": None,
                    "message": "再生成中…",
                }

            worker = threading.Thread(
                target=_run_regen_job,
                args=(job_id, pending_path, folder, target, started_at),
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
