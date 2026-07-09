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

# ============================================================================
# 定数
# ============================================================================
BRIDGE_HOST = "127.0.0.1"          # ★ 0.0.0.0 禁止(U-8/NFR-004)
DEFAULT_PORT = 8765                # env KLK_BRIDGE_PORT で上書き可(U-4)
BRIDGE_TIMEOUT_SEC = 900           # subprocess ハードタイムアウト(NFR-001 目安10分に余裕)
MAX_BODY_BYTES = 1 << 20           # POST /generate ボディ上限(1 MiB・L-1 多層防御)

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

JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# 部分再生成(KLK-012・REQ-103)—番地/letter/folder の安全パターン
KNOWN_ADDR = {"NAV-01", "HERO-01", "ABOUT-01", "MENU-01", "GALLERY-01", "FOOTER-01"}  # 基本6種(DRAFT_RULES §2)
ADDR_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d{2}$")  # 安全文字集合(SECTION-NN 連番拡張も許容・注入不能)
LETTER_RE = re.compile(r"^[a-c]$")               # 複数案の letter(a-c)。単一案は letter 無し

# 実績カタログ(KLK-013・SCR-004・REQ-105/106)—主配色6カテゴリ/安全名/MIME
CANONICAL_COLORS = {"グリーン", "ブルー", "レッド", "ゴールド", "ピンク", "モノトーン"}  # ワイヤー主配色チップ6値(§3.3)
CATALOG_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # id/file の安全文字集合(先頭は英数)
CATALOG_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


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


def validate_catalog(obj):
    """カタログJSONを検証する(§4.1・多層防御)。

    schema=='klk-catalog' / version==1 / entries=list / 各 entry の
    id(安全名)・file(安全名)・source∈{own,ref}・colors⊆CANONICAL_COLORS を検証。
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


def repo_root():
    """このファイル(draft-gen/bridge.py)からリポジトリルート(draft-gen の親)を返す。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# 以下はサーバ本体。import では実行されない(__main__ ガード下でのみ起動)。
# ============================================================================
def _run_server(port):
    """127.0.0.1:port で ThreadingHTTPServer を起動する(§4.2/4.3)。"""
    import threading
    import uuid
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    root = repo_root()
    index_path = os.path.join(root, "draft-gen", "index.html")
    pending_dir = os.path.join(root, "mockups", ".pending")

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

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-400:]
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = "生成に失敗しました。{0}".format(tail)
            _cleanup(pending_path)
            return

        # 保存規約(DRAFT_RULES §9)から表示物パスを決定論的に構築し、ブリッジ自身が開く(U-5)
        # 日付はジョブ開始時刻基準(L-2): 日跨ぎ長時間ジョブでも保存先フォルダがずれない
        date_str = started_at.strftime("%Y-%m-%d")
        folder = build_folder(date_str, project)
        open_target = select_open_target(folder, variants)
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

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-400:]
            with jobs_lock:
                jobs[job_id]["state"] = "error"
                jobs[job_id]["message"] = "再生成に失敗しました。{0}".format(tail)
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
            self._json(404, {"error": "not found"})

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if path == "/generate":
                self._generate()
                return
            if path == "/regenerate":
                self._regenerate()
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
