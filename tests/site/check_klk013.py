#!/usr/bin/env python3
"""
KLK-013 acceptance-condition checker (static / core / no browser・no network).

Verifies the statically-checkable acceptance conditions S1-S15 from
docs/designs/KLK-013.md §9（S群）against 実績カタログ（SCR-004・REQ-105/106）:

  SCR-004本体(静的シェル・静的検査)            draft-gen/catalog.html
  ブリッジ本体(純関数 import + ソース静的検査)  draft-gen/bridge.py
  取り込みスキル(静的検査)                      .claude/skills/catalog-import/SKILL.md
  カタログ規約(静的検査)                        .claude/skills/catalog-import/templates/CATALOG_RULES.md
  ダミーゴールデン(validate_catalog 受理/reject) tests/fixtures/klk013/catalog.sample.json
  .gitignore 3ファイル同期(静的検査)            .gitignore / .gitignore.public / .gitignore.private

Source of truth = 設計書 KLK-013 §9（S群 S1-S15）。S番号は S1 から開始する独立ファイル
（check_klk009〜012 と同型: import 単体＋正規表現・文字列検索・tester所有・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。bridge.py は `if __name__ == "__main__"`
ガードでサーバ起動を隔離しているため import で副作用（bind/実行）は起きない。D群（discover
回帰・git check-ignore）は tests/test_palette_klk013.py が、M群（実 /catalog-import ＋ブラウザ
実機の取り込み品質）は tester が確認しチケットのログへ記録する。プロダクション成果物
（catalog.html / bridge.py / SKILL / CATALOG_RULES / ゴールデン）は変更しない。

Run: python3 tests/site/check_klk013.py
Exit code 0 = all static/core checks pass, 1 = at least one fail.
"""
import copy
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOG_HTML_PATH = os.path.join(ROOT, "draft-gen", "catalog.html")
BRIDGE_PATH = os.path.join(ROOT, "draft-gen", "bridge.py")
SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "catalog-import", "SKILL.md")
RULES_PATH = os.path.join(
    ROOT, ".claude", "skills", "catalog-import", "templates", "CATALOG_RULES.md")
SAMPLE_PATH = os.path.join(ROOT, "tests", "fixtures", "klk013", "catalog.sample.json")
GITIGNORE_PATHS = {
    ".gitignore": os.path.join(ROOT, ".gitignore"),
    ".gitignore.public": os.path.join(ROOT, ".gitignore.public"),
    ".gitignore.private": os.path.join(ROOT, ".gitignore.private"),
}

CATALOG_HTML = open(CATALOG_HTML_PATH, encoding="utf-8").read()
BRIDGE_SRC = open(BRIDGE_PATH, encoding="utf-8").read()
SKILL = open(SKILL_PATH, encoding="utf-8").read()
RULES = open(RULES_PATH, encoding="utf-8").read()
SAMPLE_RAW = open(SAMPLE_PATH, encoding="utf-8").read()
SAMPLE = json.loads(SAMPLE_RAW)

# bridge.py を import（__main__ ガードで副作用なし＝サーバは起動しない）。
_spec = importlib.util.spec_from_file_location("klk013_bridge", BRIDGE_PATH)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# 危険フラグ（決して含めてはならない・最小権限）。
DANGER_FLAGS = ("--dangerously-skip-permissions", "bypassPermissions")

# 外部URL検査で除外するホスト（ローカル/プレースホルダ/ドキュメント慣用）。
_ALLOW_HOSTS = ("www.w3.org", "example.com", "example.org", "example.net")
_LOCAL_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0")

# 主配色7カテゴリ（ワイヤー主配色チップ・§3.3・KLK-016で「マルチカラー」を追加）。
COLOR7 = ("グリーン", "ブルー", "レッド", "ゴールド", "ピンク", "モノトーン", "マルチカラー")


def _host(url):
    m = re.match(r"https?://([^/\s\"')（]+)", url)
    return m.group(1).lower() if m else ""


def _external_urls(txt):
    """外部URL（ローカル・プレースホルダ・許可ホストを除く）を列挙する（check_klk012 同配慮）。"""
    out = []
    for m in re.findall(r'https?://[^\s"\')（]+', txt):
        host = _host(m)
        noport = host.split(":", 1)[0]
        if noport in _LOCAL_HOSTS or noport in _ALLOW_HOSTS:
            continue
        if not host:
            continue
        if "{" in host or "%" in host:  # format プレースホルダ
            continue
        out.append(m)
    return out


_SECRET_RE = re.compile(
    r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)


def _secret_hits(txt):
    return [ln for ln, line in enumerate(txt.splitlines(), 1)
            if _SECRET_RE.search(line)]


# ===========================================================================
# S1 単一ファイル・依存ゼロ（catalog.html・NFR-005）
# ===========================================================================
s1_no_extcss = not re.search(r'<link\b[^>]*rel\s*=\s*["\']?stylesheet', CATALOG_HTML, re.I)
s1_no_extscript = not re.search(r'<script\b[^>]*\bsrc\s*=', CATALOG_HTML, re.I)
s1_no_import = "@import" not in CATALOG_HTML
s1_no_font_link = not re.search(r'fonts\.(googleapis|gstatic)\.com', CATALOG_HTML, re.I)
s1_has_inline = ("<style>" in CATALOG_HTML and "<script>" in CATALOG_HTML)
s1_ext = _external_urls(CATALOG_HTML)
s1 = (s1_no_extcss and s1_no_extscript and s1_no_import and s1_no_font_link
      and s1_has_inline and not s1_ext)
check(
    "S1 単一ファイル・依存ゼロ (catalog.html: <link rel=stylesheet>/<script src>/@import/Webフォント/外部URL 無し・インライン<style>/<script>のみ)",
    s1,
    f"外部CSS無={s1_no_extcss}, 外部script無={s1_no_extscript}, @import無={s1_no_import}, "
    f"Webフォント無={s1_no_font_link}, インライン有={s1_has_inline}, 外部URL={s1_ext or 0}",
)

# ===========================================================================
# S2 SCR-004 構造（ワイヤー準拠・REQ-105/106）
# ===========================================================================
s2_filters = "class=\"filters\"" in CATALOG_HTML
s2_facets = all(f'data-facet="{f}"' in CATALOG_HTML for f in ("industry", "taste", "colors", "source"))
s2_grid = re.search(r'class="grid"', CATALOG_HTML) is not None
s2_item = ".item" in CATALOG_HTML and re.search(r'class="item"', CATALOG_HTML) is not None
s2_src = (".src.own" in CATALOG_HTML and ".src.ref" in CATALOG_HTML
          and 'src own' in CATALOG_HTML.replace('"', ' ').replace("+", " ") or
          ("src ' + srcClass" in CATALOG_HTML))
# own/ref バッジは CSS 定義（.src.own/.src.ref）＋描画（srcClass）で担保
s2_src = (".src.own" in CATALOG_HTML and ".src.ref" in CATALOG_HTML
          and 'srcClass' in CATALOG_HTML)
s2_modal = ".modal-toggle:checked" in CATALOG_HTML and "modal-toggle" in CATALOG_HTML
s2_uploader = 'class="uploader" id="add"' in CATALOG_HTML
s2_dropzone = "dropzone" in CATALOG_HTML
s2_autotag = "autotag" in CATALOG_HTML
s2 = (s2_filters and s2_facets and s2_grid and s2_item and s2_src and s2_modal
      and s2_uploader and s2_dropzone and s2_autotag)
check(
    "S2 SCR-004 構造 (.filters[業種/テイスト/主配色/種別の4 data-facet]・.grid・.item・.src.own/.src.ref・CSS-only .modal-toggle:checked・.uploader#add の .dropzone＋.autotag)",
    s2,
    f".filters={s2_filters}, 4facet={s2_facets}, .grid={s2_grid}, .item={s2_item}, "
    f"own/refバッジ={s2_src}, CSS-onlyモーダル={s2_modal}, uploader#add={s2_uploader}, "
    f"dropzone={s2_dropzone}, autotag={s2_autotag}",
)

# ===========================================================================
# S3 主配色7カテゴリ（スウォッチ付きチップ・REQ-105/§3.3・KLK-016）
# ===========================================================================
s3_all7 = all(f'data-val="{c}"' in CATALOG_HTML for c in COLOR7)
s3_swatch = 'class="sw"' in CATALOG_HTML and "fchip color" in CATALOG_HTML
# フィルタ主配色行にちょうど7カテゴリのカラーチップ
color_chip_vals = re.findall(r'class="fchip color"[^>]*data-val="([^"]+)"', CATALOG_HTML)
s3_exactly7 = set(color_chip_vals) == set(COLOR7) and len(color_chip_vals) == 7
s3 = s3_all7 and s3_swatch and s3_exactly7
check(
    "S3 主配色7カテゴリ (グリーン/ブルー/レッド/ゴールド/ピンク/モノトーン/マルチカラーがスウォッチ付きチップ .fchip.color .sw としてちょうど7件)",
    s3,
    f"7カテゴリ存在={s3_all7}, スウォッチ={s3_swatch}, カラーチップ7件={s3_exactly7}({color_chip_vals})",
)

# ===========================================================================
# S4 絞り込みロジック（filterEntries AND フィルタ＋/catalog.json 描画・REQ-105）
# ===========================================================================
s4_fn = "function filterEntries" in CATALOG_HTML
s4_facets = all(k in CATALOG_HTML for k in ("s.industry", "s.taste", "s.colors", "s.source", "keyword"))
s4_and = "return false" in CATALOG_HTML  # 各ファセット不一致で除外＝AND 合成
s4_fetch = "fetch(\"/catalog.json\")" in CATALOG_HTML or "fetch('/catalog.json')" in CATALOG_HTML
s4_render = "renderGrid" in CATALOG_HTML
# sel に source[] が初期化されていること（KLK-033・無いと wireFilters の sel[facet] が undefined で throw）
s4_sel_source = re.search(r'var sel\s*=\s*\{[^}]*\bsource\s*:\s*\[\]', CATALOG_HTML) is not None
s4 = s4_fn and s4_facets and s4_and and s4_fetch and s4_render and s4_sel_source
check(
    "S4 絞り込みロジック (filterEntries: 業種×テイスト×配色×種別×keyword の AND フィルタ・sel.source[] 初期化・fetch('/catalog.json')→renderGrid)",
    s4,
    f"filterEntries={s4_fn}, 5ファセット(source含む)={s4_facets}, AND(除外)={s4_and}, "
    f"/catalog.json fetch={s4_fetch}, renderGrid={s4_render}, sel.source初期化={s4_sel_source}",
)

# ===========================================================================
# S5 JSON読込ハイブリッド＋フォールバック（/health プローブ・空状態＋起動案内・U-A/NFR-005）
# ===========================================================================
s5_probe = "probeHealth" in CATALOG_HTML and "fetch(\"/health\"" in CATALOG_HTML
s5_abort = "AbortController" in CATALOG_HTML
s5_sameorigin = ("fetch(\"/catalog.json\")" in CATALOG_HTML
                 or "fetch('/catalog.json')" in CATALOG_HTML)
s5_fallback = ("未起動" in CATALOG_HTML
               and "python3 draft-gen/bridge.py" in CATALOG_HTML)
s5_graceful = ".catch(" in CATALOG_HTML and "setBridgeState" in CATALOG_HTML
# file:// では即 false に倒す（fetch を投げない＝壊れない）
s5_file = 'location.protocol === "file:"' in CATALOG_HTML
s5 = s5_probe and s5_abort and s5_sameorigin and s5_fallback and s5_graceful and s5_file
check(
    "S5 JSON読込ハイブリッド＋フォールバック (/health プローブ[AbortController]・同一オリジン /catalog.json fetch・health失敗時 空状態＋起動案内[python3 draft-gen/bridge.py]・.catch で壊れない・file:// は即フォールバック)",
    s5,
    f"probeHealth={s5_probe}, AbortController={s5_abort}, /catalog.json={s5_sameorigin}, "
    f"起動案内={s5_fallback}, graceful={s5_graceful}, file://分岐={s5_file}",
)

# ===========================================================================
# S6 カタログJSONスキーマ検証（validate_catalog・正当受理＋各異常 reject・U-B/§4.1）
# ===========================================================================
vc = bridge.validate_catalog
ok_sample, _ = vc(SAMPLE)              # ダミーゴールデンは正当受理
# schema 不一致
bad_schema = copy.deepcopy(SAMPLE); bad_schema["schema"] = "other"
r_schema = vc(bad_schema)[0] is False
# version != 1
bad_ver = copy.deepcopy(SAMPLE); bad_ver["version"] = 2
r_ver = vc(bad_ver)[0] is False
# entries が list でない
bad_entries = copy.deepcopy(SAMPLE); bad_entries["entries"] = {}
r_entries = vc(bad_entries)[0] is False
# id 欠落
bad_id = copy.deepcopy(SAMPLE); del bad_id["entries"][0]["id"]
r_id = vc(bad_id)[0] is False
# file 不正（traversal）
bad_file = copy.deepcopy(SAMPLE); bad_file["entries"][0]["file"] = "../etc/passwd"
r_file = vc(bad_file)[0] is False
# source ∉ {own,ref}
bad_src = copy.deepcopy(SAMPLE); bad_src["entries"][0]["source"] = "external"
r_src = vc(bad_src)[0] is False
# colors ∉ 7集合
bad_col = copy.deepcopy(SAMPLE); bad_col["entries"][0]["colors"] = ["ベージュ"]
r_col = vc(bad_col)[0] is False
# 非オブジェクト
r_nonobj = vc([])[0] is False and vc(None)[0] is False
s6 = (ok_sample and r_schema and r_ver and r_entries and r_id and r_file
      and r_src and r_col and r_nonobj)
check(
    "S6 カタログJSONスキーマ検証 (validate_catalog: sample.json 受理; schema不一致/version≠1/entries非list/id欠落/file traversal/source∉{own,ref}/colors∉7集合/非オブジェクト を reject)",
    s6,
    f"sample受理={ok_sample}, schema異常={r_schema}, version異常={r_ver}, entries非list={r_entries}, "
    f"id欠落={r_id}, file不正={r_file}, source異常={r_src}, colors異常={r_col}, 非obj={r_nonobj}",
)

# ===========================================================================
# S7 主配色カテゴリ集合（CANONICAL_COLORS がちょうど7・集合メンバーシップ強制・§3.3/R-3）
# ===========================================================================
cc = bridge.CANONICAL_COLORS
s7_type = isinstance(cc, (set, frozenset))
s7_exact = set(cc) == set(COLOR7) and len(cc) == 7
# colors が集合外なら reject・7集合内なら受理（品質ではなく集合メンバーシップのみ）
# 受理ケースは件数上限(1..3・KLK-016)と衝突しない ≤3件の部分集合を使う（R3）。
one = copy.deepcopy(SAMPLE)
one["entries"] = [dict(SAMPLE["entries"][0])]
in_set = copy.deepcopy(one); in_set["entries"][0]["colors"] = ["グリーン", "ブルー", "レッド"]
s7_in = vc(in_set)[0] is True
out_set = copy.deepcopy(one); out_set["entries"][0]["colors"] = ["グリーン", "ホワイト"]
s7_out = vc(out_set)[0] is False
s7 = s7_type and s7_exact and s7_in and s7_out
check(
    "S7 主配色カテゴリ集合 (CANONICAL_COLORS が set でちょうど7カテゴリ・validate_catalog が colors の集合メンバーシップを強制[7集合内○・集合外×]・タグ品質は検証しない)",
    s7,
    f"set型={s7_type}, ちょうど7={s7_exact}({sorted(cc)}), 7集合内受理={s7_in}, 集合外reject={s7_out}",
)

# ===========================================================================
# S8 ブリッジ配信エンドポイント（静的・GET /catalog・/catalog.json・/catalog/img/・POST /catalog-import）
# ===========================================================================
s8_get_catalog = re.search(r'path\s*==\s*["\']/catalog["\']', BRIDGE_SRC) is not None
s8_get_json = re.search(r'path\s*==\s*["\']/catalog\.json["\']', BRIDGE_SRC) is not None
s8_get_img = re.search(r'path\.startswith\(\s*["\']/catalog/img/["\']\s*\)', BRIDGE_SRC) is not None
s8_post = re.search(r'path\s*==\s*["\']/catalog-import["\']', BRIDGE_SRC) is not None
# ハンドラの定義も確認
s8_handlers = all(h in BRIDGE_SRC for h in
                  ("def _serve_catalog_html", "def _serve_catalog_json",
                   "def _serve_catalog_img", "def _catalog_import"))
s8 = s8_get_catalog and s8_get_json and s8_get_img and s8_post and s8_handlers
check(
    "S8 ブリッジ配信エンドポイント (do_GET: /catalog・/catalog.json・/catalog/img/ ; do_POST: /catalog-import ; 各ハンドラ定義あり)",
    s8,
    f"GET /catalog={s8_get_catalog}, /catalog.json={s8_get_json}, /catalog/img/={s8_get_img}, "
    f"POST /catalog-import={s8_post}, ハンドラ定義={s8_handlers}",
)

# ===========================================================================
# S9 パストラバーサル防御（is_safe_catalog_name・GET /catalog/img/ が通す・R-5/§4.3）
# ===========================================================================
sc = bridge.is_safe_catalog_name
s9_ok = (sc("cat-0001.jpg") and sc("cat_0002.png") and sc("a") and sc("A1.b-c.jpeg"))
s9_trav = (sc("..") is False and sc("../x") is False and sc("a..b") is False)
s9_abs = (sc("/etc/passwd") is False and sc("/x") is False)
s9_sep = (sc("a/b") is False and sc("a\\b") is False and sc("img/x.jpg") is False)
s9_dot = (sc(".hidden") is False and sc(".env") is False)  # 先頭 '.' は RE で拒否
s9_nonstr = (sc(None) is False and sc(123) is False and sc("") is False)
s9_pure = s9_ok and s9_trav and s9_abs and s9_sep and s9_dot and s9_nonstr
# GET /catalog/img/ ハンドラが is_safe_catalog_name を通す（静的）
_ii = BRIDGE_SRC.find("def _serve_catalog_img")
_iseg = BRIDGE_SRC[_ii:_ii + 1400] if _ii >= 0 else ""
s9_gate = "is_safe_catalog_name(" in _iseg and "400" in _iseg and "realpath" in _iseg
s9 = s9_pure and s9_gate
check(
    "S9 パストラバーサル防御 (is_safe_catalog_name: 安全名○・'..'/絶対/'/'・'\\\\'/先頭'.'/非str× ; GET /catalog/img/ が is_safe_catalog_name＋realpath で 400 ガード)",
    s9,
    f"安全名○={s9_ok}, ..×={s9_trav}, 絶対×={s9_abs}, セパレータ×={s9_sep}, 先頭.×={s9_dot}, "
    f"非str×={s9_nonstr}, img配信ゲート={s9_gate}",
)

# ===========================================================================
# S10 is_allowed_origin 踏襲（POST /catalog-import 防御順・静的・R-6/KLK-010/011）
# ===========================================================================
_ci = BRIDGE_SRC.find("def _catalog_import")
_cseg = BRIDGE_SRC[_ci:_ci + 2400] if _ci >= 0 else ""
s10_origin = "is_allowed_origin(" in _cseg and "403" in _cseg
s10_size = "MAX_BODY_BYTES" in _cseg and "413" in _cseg
s10_valid = "validate_import_request(" in _cseg and "400" in _cseg
# 防御順: Origin403 → サイズ413 → JSON → validate_import_request。
# docstring 内の言及（例 "validate_import_request(400)"）を拾わないよう、実コードの
# 呼出トークンで位置を取る。
i_origin = _cseg.find("is_allowed_origin(self.headers")
i_size = _cseg.find("length > MAX_BODY_BYTES")
i_valid = _cseg.find("validate_import_request(obj)")
s10_order = 0 <= i_origin < i_size < i_valid
# is_allowed_origin(Origin, BRIDGE_HOST, port) 呼出形＋127.0.0.1
s10_call = re.search(
    r"is_allowed_origin\(\s*self\.headers\.get\(\s*[\"']Origin[\"']\s*\)\s*,\s*BRIDGE_HOST",
    _cseg) is not None
s10_host = getattr(bridge, "BRIDGE_HOST", None) == "127.0.0.1"
s10 = s10_origin and s10_size and s10_valid and s10_order and s10_call and s10_host
check(
    "S10 is_allowed_origin 踏襲 (POST /catalog-import: is_allowed_origin(403)→MAX_BODY_BYTES(413)→validate_import_request(400) の防御順・BRIDGE_HOST==127.0.0.1)",
    s10,
    f"Origin403={s10_origin}, サイズ413={s10_size}, 入力検証400={s10_valid}, "
    f"防御順={s10_order}, 呼出形={s10_call}, 127.0.0.1={s10_host}",
)

# ===========================================================================
# S11 最小権限コマンド（build_catalog_import_command・危険フラグ非含有・shell=True 非使用・R-6/NFR-004）
# ===========================================================================
bcc = bridge.build_catalog_import_command
cmd = bcc("catalog/.pending/x.import.json")
cmd_flat = " ".join(cmd)
s11_base = (cmd[:2] == ["claude", "-p"]
            and "/catalog-import catalog/.pending/x.import.json" in cmd
            and "--permission-mode" in cmd and "acceptEdits" in cmd
            and "--output-format" in cmd and "json" in cmd)
s11_no_danger = not any(f in cmd_flat for f in DANGER_FLAGS)
s11_no_open_default = "--allowedTools" not in cmd
cmd_open = bcc("/x.import.json", allow_open=True)
s11_open = ("--allowedTools" in cmd_open and "Bash(open *)" in cmd_open
            and not any(f in " ".join(cmd_open) for f in DANGER_FLAGS))
s11_no_shell = ("shell=True" not in BRIDGE_SRC and "shell=True" not in CATALOG_HTML)
s11 = (s11_base and s11_no_danger and s11_no_open_default and s11_open and s11_no_shell)
check(
    "S11 最小権限コマンド (build_catalog_import_command: /catalog-import {path} --permission-mode acceptEdits --output-format json・危険フラグ非含有・allow_openでopenのみ追加・shell=True 非使用[bridge/catalog.html])",
    s11,
    f"基本形={s11_base}, 危険フラグ非含有={s11_no_danger}, 既定open非付与={s11_no_open_default}, "
    f"allow_open時open追加={s11_open}, shell=True非使用={s11_no_shell}",
)

# ===========================================================================
# S12 セキュリティ/依存（S-SEC）— catalog.html・bridge.py の外部URL0・秘密0・実在案件名0
# ===========================================================================
ext_html = _external_urls(CATALOG_HTML)
ext_bridge = _external_urls(BRIDGE_SRC)
sec_html = _secret_hits(CATALOG_HTML)
sec_bridge = _secret_hits(BRIDGE_SRC)
# fixtures はダミーのみ（架空マーカーを含む＝実在案件名なし）。
_FICTION_MARKERS = ("架空", "ダミー", "サンプル", "デモ", "見本")
fixture_all_fiction = all(
    any(m in (str(e.get("title", "")) + str(e.get("note", ""))) for m in _FICTION_MARKERS)
    for e in SAMPLE.get("entries", [])
)
# 器（catalog.html）にカタログ実データ（案件名/画像ファイル名）が焼き込まれていない
# ＝ グリッドは fetch のみで得るため、cat-000N.jpg 等の実体名がソースに無いこと。
html_no_realdata = not re.search(r'cat-\d{3,}\.(jpg|jpeg|png)', CATALOG_HTML, re.I)
s12 = (not ext_html and not ext_bridge and not sec_html and not sec_bridge
       and fixture_all_fiction and html_no_realdata)
check(
    "S12 S-SEC (catalog.html/bridge.py: 外部URL0[local/placeholder除外]・秘密0[api key/secret/password/token/private key]; fixtures は架空マーカーのみ[実在案件名0]; 器にカタログ実データ非焼込)",
    s12,
    f"外部URL(html={ext_html or 0},bridge={ext_bridge or 0}), 秘密(html={sec_html or 0},bridge={sec_bridge or 0}), "
    f"fixture架空={fixture_all_fiction}, 器に実データ無={html_no_realdata}",
)

# ===========================================================================
# S13 収集見本の著作物表記（.src.ref＋「社内参考のみ」注記・source own|ref 限定・受け入れ条件5/NFR-004）
# ===========================================================================
s13_ref_badge = ".src.ref" in CATALOG_HTML and "収集見本" in CATALOG_HTML
s13_note = ("社内の参考目的のみ" in CATALOG_HTML
            and "公開・再配布・そっくり再現の材料にはしません" in CATALOG_HTML)
# validate_catalog が source を own|ref に限定（S6 で確認済みだが独立に再確認）
one2 = copy.deepcopy(SAMPLE); one2["entries"] = [dict(SAMPLE["entries"][0])]
own_ok = copy.deepcopy(one2); own_ok["entries"][0]["source"] = "own"
ref_ok = copy.deepcopy(one2); ref_ok["entries"][0]["source"] = "ref"
bad_so = copy.deepcopy(one2); bad_so["entries"][0]["source"] = "public"
s13_src = (vc(own_ok)[0] is True and vc(ref_ok)[0] is True and vc(bad_so)[0] is False)
s13 = s13_ref_badge and s13_note and s13_src
check(
    "S13 収集見本の著作物表記 (catalog.html に .src.ref[収集見本]バッジ＋「社内の参考目的のみ・公開/再配布/そっくり再現しない」注記・validate_catalog が source を own|ref に限定)",
    s13,
    f"refバッジ={s13_ref_badge}, 注記={s13_note}, source限定(own○/ref○/他×)={s13_src}",
)

# ===========================================================================
# S14 スキル・規約の記述（SKILL.md/CATALOG_RULES.md・REQ-106/§4.5）
# ===========================================================================
sk_human = ("登録前" in SKILL and ("確認" in SKILL and "修正" in SKILL)
            and "人間確認" in SKILL)
sk_6cat = ("7カテゴリ" in SKILL and "CANONICAL_COLORS" in SKILL)
sk_only = "catalog/" in SKILL and ("catalog/` 配下" in SKILL or "catalog/ 配下" in SKILL
                                   or "catalog/ の外へ" in SKILL)
sk_secret = "機密" in SKILL or "社外秘" in SKILL or "REQ-011" in SKILL or "NFR-004" in SKILL
sk_name = "name: catalog-import" in SKILL
ru_schema = ("klk-catalog" in RULES and "version" in RULES and "entries" in RULES)
ru_human = "登録前に確認" in RULES or ("人間承認" in RULES or "人間確認" in RULES)
ru_6cat = all(c in RULES for c in COLOR7) and "CANONICAL_COLORS" in RULES
ru_only = "catalog/" in RULES and ("Git除外" in RULES or "社外秘" in RULES)
s14 = (sk_human and sk_6cat and sk_only and sk_secret and sk_name
       and ru_schema and ru_human and ru_6cat and ru_only)
check(
    "S14 スキル・規約の記述 (SKILL.md/CATALOG_RULES.md: 登録前に人間が確認・修正／主配色7カテゴリ視覚推定／catalog/のみ保存・機密規律／カタログJSONスキーマ)",
    s14,
    f"SKILL(人間確認={sk_human},7カテゴリ={sk_6cat},catalog限定={sk_only},機密={sk_secret},name={sk_name}), "
    f"RULES(スキーマ={ru_schema},人間確認={ru_human},7カテゴリ={ru_6cat},catalog限定={ru_only})",
)

# ===========================================================================
# S15 .gitignore 3者同期（catalog/ 行が3ファイルすべてに存在・REQ-011/NFR-004/§4.6）
# ===========================================================================
gi_present = {}
for label, p in GITIGNORE_PATHS.items():
    try:
        txt = open(p, encoding="utf-8").read()
    except OSError:
        gi_present[label] = False
        continue
    gi_present[label] = any(
        line.strip() == "catalog/" for line in txt.splitlines())
s15 = all(gi_present.values())
check(
    "S15 .gitignore 3者同期 (.gitignore・.gitignore.public・.gitignore.private の3ファイルすべてに 'catalog/' 行が存在)",
    s15,
    f"存在={gi_present}",
)

# ===========================================================================
# S16 主配色の件数検証（第1必須・最大3件・KLK-016/§4.1b）
# ===========================================================================
_one = copy.deepcopy(SAMPLE)
_one["entries"] = [dict(SAMPLE["entries"][0])]


def _with_colors(cols):
    e = copy.deepcopy(_one)
    e["entries"][0]["colors"] = cols
    return vc(e)[0]


s16_empty = _with_colors([]) is False                                  # 空配列 reject（第1必須）
s16_one = _with_colors(["グリーン"]) is True                            # 1件 accept
s16_three = _with_colors(["グリーン", "ブルー", "レッド"]) is True       # 3件 accept
s16_four = _with_colors(["グリーン", "ブルー", "レッド", "ゴールド"]) is False  # 4件 reject
s16 = s16_empty and s16_one and s16_three and s16_four
check(
    "S16 主配色の件数検証 (validate_catalog: colors=[]→reject[第1必須] / 1件→accept / 3件→accept / 4件→reject[最大3件])",
    s16,
    f"空配列reject={s16_empty}, 1件accept={s16_one}, 3件accept={s16_three}, 4件reject={s16_four}",
)

# ===========================================================================
# S17 マルチカラー単独排他（具体色との併用不可・順序非依存・KLK-016/§4.1b）
# ===========================================================================
s17_solo = _with_colors(["マルチカラー"]) is True                       # 単独 accept
s17_mix1 = _with_colors(["マルチカラー", "ピンク"]) is False             # 併用 reject
s17_mix2 = _with_colors(["ピンク", "マルチカラー"]) is False             # 順序を変えても reject
s17 = s17_solo and s17_mix1 and s17_mix2
check(
    "S17 マルチカラー単独排他 (validate_catalog: ['マルチカラー']→accept[単独] / ['マルチカラー','ピンク']→reject / ['ピンク','マルチカラー']→reject[順序非依存])",
    s17,
    f"単独accept={s17_solo}, 併用reject={s17_mix1}, 逆順併用reject={s17_mix2}",
)

# ===========================================================================
# S18 sectionLayouts の shape 検証（validate_catalog・任意・KLK-030/§4-2）
# ===========================================================================
def _with_section_layouts(sl):
    e = copy.deepcopy(_one)
    e["entries"][0]["sectionLayouts"] = sl
    return vc(e)[0]


# sectionLayouts 無し → accept（後方互換・既存3エントリ相当）
_no_sl = copy.deepcopy(_one)
_no_sl["entries"][0].pop("sectionLayouts", None)
s18_absent = vc(_no_sl)[0] is True
s18_empty = _with_section_layouts({}) is True                                         # 空map accept
s18_valid = _with_section_layouts({"VOICE": "voice-quote-stack", "ABOUT": "img-left"}) is True  # 妥当 accept
s18_other = _with_section_layouts({"VOICE": "other"}) is True                          # 番兵 accept
s18_array = _with_section_layouts(["VOICE"]) is False                                  # 配列 reject
s18_numval = _with_section_layouts({"VOICE": 3}) is False                              # 非文字列値 reject
s18_emptyval = _with_section_layouts({"VOICE": ""}) is False                           # 空文字列値 reject
s18 = (s18_absent and s18_empty and s18_valid and s18_other
       and s18_array and s18_numval and s18_emptyval)
check(
    "S18 sectionLayouts の shape 検証 (validate_catalog: 無し/空map/妥当map/'other'→accept ; 配列/非文字列値/空文字列値→reject ; 値の語彙照合はしない)",
    s18,
    f"無しaccept={s18_absent}, 空mapaccept={s18_empty}, 妥当accept={s18_valid}, otheraccept={s18_other}, "
    f"配列reject={s18_array}, 非文字列値reject={s18_numval}, 空文字列値reject={s18_emptyval}",
)

# ===========================================================================
# S19 ドキュメントの語彙参照方式・自動確定禁止（CATALOG_RULES/SKILL・KLK-030/§4-6）
# ===========================================================================
# CATALOG_RULES.md に sectionLayouts フィールド定義があり、値の語彙の正として
# DRAFT_RULES §12.1 を参照する文言を含む（＝参照方式・再掲しない）。
ru_sl_field = "sectionLayouts" in RULES
ru_sl_ref = ("DRAFT_RULES" in RULES and "12.1" in RULES)
# CATALOG_RULES の sectionLayouts フィールド定義行の近傍に DRAFT_RULES 参照があること
# （同一段落で参照方式を担保。JSON例の出現ではなくフィールド定義行を anchor にする）。
_ri = RULES.find("entries[].sectionLayouts")
_rseg = RULES[_ri:_ri + 600] if _ri >= 0 else ""
ru_sl_ref_near = ("DRAFT_RULES" in _rseg and "12.1" in _rseg)
# SKILL.md 手順2/3 に sectionLayouts の提案＋人間確認の記述がある（自動確定しない）。
sk_sl = "sectionLayouts" in SKILL
sk_sl_pool = ("DRAFT_RULES" in SKILL and "12.1" in SKILL)
sk_sl_no_auto = "人間確認なしで自動確定" in SKILL
s19 = (ru_sl_field and ru_sl_ref and ru_sl_ref_near and sk_sl and sk_sl_pool and sk_sl_no_auto)
check(
    "S19 語彙参照方式・自動確定禁止 (CATALOG_RULES: sectionLayouts 定義＋DRAFT_RULES §12.1 参照[再掲しない] ; SKILL: 型提案＋DRAFT_RULES §12.1 語彙＋人間確認なし自動確定の禁止)",
    s19,
    f"RULES(定義={ru_sl_field},DRAFT_RULES参照={ru_sl_ref},近傍参照={ru_sl_ref_near}), "
    f"SKILL(記載={sk_sl},§12.1語彙={sk_sl_pool},自動確定禁止={sk_sl_no_auto})",
)

# ===========================================================================
# S20 業種タクソノミ17区分（catalog.html 業種チップの語彙 pin・KLK-032）
# ===========================================================================
# 器（catalog.html）の業種チップがちょうど17個・正準17区分と集合一致・
# 各チップの data-val とラベルが同一文字列であることを静的検証する。
# 実データ（catalog.json）の industry⊆17 は Git除外でCI外 → M群/人間ゲートで担保。
INDUSTRY17 = (
    "飲食店・カフェ・食関連", "美容室・エステ・化粧品", "ファッション",
    "スクール・教室", "不動産・建築", "ホテル・旅館・レジャー",
    "士業事務所（法律/会計/コンサルティング他）", "コーポレート／BtoB", "EC・物販",
    "フィットネス・ジム・スポーツ", "イベント・キャンペーンLP", "ジュエリー・時計・貴金属",
    "クリニック・病院・介護リハビリ", "農業・ファーム", "求人・採用",
    "アート・ポートフォリオ", "その他・団体/NPO",
)
# 業種 frow（data-facet="industry"）だけを切り出す（taste/colors のチップを拾わない）。
_ind0 = CATALOG_HTML.find('data-facet="industry"')
_ind1 = CATALOG_HTML.find('data-facet="taste"', _ind0)
_ind_seg = CATALOG_HTML[_ind0:_ind1] if 0 <= _ind0 < _ind1 else ""
# class="fchip"（color チップは class="fchip color" なので除外される）の data-val とラベル。
_ind_pairs = re.findall(r'class="fchip"\s+data-val="([^"]+)"\s*>([^<]+)</span>', _ind_seg)
_ind_vals = [v for v, _ in _ind_pairs]
s20_count = len(_ind_vals) == 17
s20_set = set(_ind_vals) == set(INDUSTRY17)
s20_val_eq_label = all(v == lbl for v, lbl in _ind_pairs)
s20 = s20_count and s20_set and s20_val_eq_label
check(
    "S20 業種17区分 (catalog.html 業種チップがちょうど17個・正準17区分と集合一致・各 data-val==ラベル)",
    s20,
    f"17個={s20_count}({len(_ind_vals)}), 集合一致={s20_set}"
    f"{'' if s20_set else ' 差分=' + str(set(_ind_vals) ^ set(INDUSTRY17))}, "
    f"data-val==ラベル={s20_val_eq_label}",
)

# ===========================================================================
# S21 種別フィルタ frow（catalog.html・own/ref・label≠val・KLK-033）
# ===========================================================================
# 種別 frow（data-facet="source"）だけを切り出す（industry/taste/colors のチップを拾わない）。
# frow の後ろは colors frow の直後＝filters を閉じる </div>。次 frow が無いので </div> で区切る。
_src0 = CATALOG_HTML.find('data-facet="source"')
_src1 = CATALOG_HTML.find('</div>', _src0 + 1) if _src0 >= 0 else -1
# fchips の内側までを含めるため、frow 全体（fchips を閉じる直前まで）を広めに切り出す。
_src_seg = CATALOG_HTML[_src0:_src0 + 400] if _src0 >= 0 else ""
# class="fchip"（color チップは class="fchip color" なので除外される）の data-val とラベル。
_src_pairs = re.findall(r'class="fchip"\s+data-val="([^"]+)"\s*>([^<]+)</span>', _src_seg)
_src_map = dict(_src_pairs)
s21_frow = _src0 >= 0
s21_count = len(_src_pairs) == 2
s21_vals = set(v for v, _ in _src_pairs) == {"own", "ref"}
s21_labels = set(lbl for _, lbl in _src_pairs) == {"自社実績", "収集見本"}
s21_pairing = _src_map.get("own") == "自社実績" and _src_map.get("ref") == "収集見本"
s21_label_ne_val = all(v != lbl for v, lbl in _src_pairs)  # 業種/テイスト(label==val)と異なる
s21 = s21_frow and s21_count and s21_vals and s21_labels and s21_pairing and s21_label_ne_val
check(
    "S21 種別フィルタ frow (catalog.html data-facet=\"source\" にチップ2個・data-val∈{own,ref}・ラベル∈{自社実績,収集見本}・own↔自社実績/ref↔収集見本・label≠val)",
    s21,
    f"frow存在={s21_frow}, 2チップ={s21_count}({_src_pairs}), val∈own/ref={s21_vals}, "
    f"ラベル一致={s21_labels}, 対応={s21_pairing}, label≠val={s21_label_ne_val}",
)

# ===========================================================================
# S22 取込許可拡張子（catalog_import_ext_ok・全件列挙 webp 許可・配信MIME非含有・KLK-033）
# ===========================================================================
cie = bridge.catalog_import_ext_ok
# 実ファイル名で判定（os.path.splitext は先頭ドットのみの ".webp" を拡張子無しの隠しファイル名として
# 扱うため、bare ".webp" は取込対象にならない＝is_safe_catalog_name も先頭ドットを拒否する。よって
# 現実の拡張子付き名 "a.webp"/"thumb.webp" で判定する）。
s22_webp = (cie("a.webp") is True and cie("thumb.webp") is True and cie("A.WEBP") is True)
s22_std = (cie("x.jpg") is True and cie("x.jpeg") is True and cie("x.png") is True)
s22_gif = (cie("x.gif") is False and cie("x.txt") is False)
s22_nonstr = (cie(None) is False and cie(123) is False)
s22_pure = s22_webp and s22_std and s22_gif and s22_nonstr
# 全件列挙フィルタが catalog_import_ext_ok を使う（catalog_content_type in (jpeg,png) 併用を廃止）
s22_enum = "catalog_import_ext_ok(n)" in BRIDGE_SRC
# 404文言に WebP/webp を含む
s22_404 = re.search(r"取り込み対象の画像がありません.*[Ww]eb[Pp]", BRIDGE_SRC) is not None
# 配信MIME CATALOG_MIME に webp が入っていない（配信/取込の切り分け・退行検知）
s22_mime = ".webp" not in getattr(bridge, "CATALOG_MIME", {})
# 取込許可集合 CATALOG_IMPORT_EXTS には webp が入っている
s22_impexts = ".webp" in getattr(bridge, "CATALOG_IMPORT_EXTS", set())
s22 = s22_pure and s22_enum and s22_404 and s22_mime and s22_impexts
check(
    "S22 取込許可拡張子 (catalog_import_ext_ok: webp/jpg/jpeg/png○・gif等/非str× ; 全件列挙が同関数使用 ; 404文言に WebP ; 配信 CATALOG_MIME に webp 非含有 ; CATALOG_IMPORT_EXTS に webp)",
    s22,
    f"webp○={s22_webp}, jpg/png○={s22_std}, gif×={s22_gif}, 非str×={s22_nonstr}, "
    f"全件列挙使用={s22_enum}, 404にWebP={s22_404}, 配信MIMEにwebp無={s22_mime}, 取込集合にwebp={s22_impexts}",
)

# ===========================================================================
# S23 SKILL/CATALOG_RULES の webp/sips/png/ref 文言 pin（KLK-033）
# ===========================================================================
sk_webp = ("webp" in SKILL.lower()) and ("sips" in SKILL) and ("png" in SKILL.lower()) and ("変換" in SKILL)
sk_webp_ref = ("ref" in SKILL) and ("既定候補" in SKILL or "ref` を既定" in SKILL)
ru_webp = ("webp" in RULES.lower()) and ("sips" in RULES) and ("png" in RULES.lower())
ru_webp_ref = ("ref" in RULES) and ("既定候補" in RULES or "webp→ref" in RULES)
s23 = sk_webp and sk_webp_ref and ru_webp and ru_webp_ref
check(
    "S23 SKILL/CATALOG_RULES 文言 (SKILL: webp/sips/png/変換＋webp→ref既定候補 ; CATALOG_RULES: webp/sips/png＋webp→ref既定候補)",
    s23,
    f"SKILL(webp/sips/png/変換={sk_webp}, ref既定={sk_webp_ref}), "
    f"RULES(webp/sips/png={ru_webp}, ref既定={ru_webp_ref})",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-013 static/core acceptance checks (docs/designs/KLK-013.md §9 S群 S1-S15＋KLK-016 S16-S17 を正とする)")
print("対象: draft-gen/catalog.html(静的) + draft-gen/bridge.py(import 純関数 + ソース静的) +")
print("      catalog-import/SKILL.md + CATALOG_RULES.md + tests/fixtures/klk013/catalog.sample.json +")
print("      .gitignore 3ファイル")
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
print("D群（test_palette_klk013.py で discover 回帰・git check-ignore・/catalog-import 実HTTP疎通）:")
print("  - D1 catalog/ の Git 除外成立（git check-ignore catalog/catalog.json 等が exit 0）")
print("  - D2 Quality Gate 全緑（python3 -m unittest discover -s tests・KLK-006〜012 回帰なし）")
print()
print("M群（環境制約で静的検証外 = tester がブリッジ起動＋実 /catalog-import＋ブラウザで手動確認）:")
print("  - M1 カタログ閲覧・絞り込み（業種×テイスト×主配色×種別[own/ref]×キーワード・拡大モーダル・/catalog/img/ 表示）")
print("  - M2 file:// フォールバック（空状態＋起動案内・任意 catalog/catalog.html オフライン閲覧）")
print("  - M3 実画像取り込み＋自動タグ付け＋人間確認（承認前に確定しない）; webp を1枚置き sips 変換で png 生成→ref 既定提示→人間ゲートで own 上書き可（KLK-033）")
print("  - M4 自動タグ品質（業種/テイスト/主配色の妥当性・目視評価）; webp→png 変換後 png の視覚認識品質（KLK-033・webpフィクスチャ本環境生成不能ゆえ実変換はM群）")
print("  - M5 ワンクリック取り込み（POST 実HTTP・jobId→ポーリング→一覧更新・不正Origin403）")
print("  - M6 機密のローカル完結・封じ込め（git status に現れず・/catalog/img/ で .. が catalog/img/ 外を読めない）")
print("  - M7 収集見本（ref）の著作物表記（橙バッジ＋社内参考のみ注記）")
sys.exit(1 if failed else 0)
