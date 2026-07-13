#!/usr/bin/env python3
"""
KLK-019 acceptance-condition checker (static / core・no browser・no network).

Verifies the statically-checkable acceptance conditions S1-S8 from
docs/designs/KLK-019.md §9（S群）against ブリッジの palette 配信ルート追加:

  ブリッジ本体(import + ソース静的検査)   draft-gen/bridge.py
  起動リンク(文字列静的検査)              draft-gen/index.html

Source of truth = 設計書 KLK-019 §9（S群 S1-S8）。S番号は S1 から開始する独立ファイル
（check_klk013 と同型: import 単体＋正規表現・文字列検索・tester所有・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。bridge.py は `if __name__ == "__main__"`
ガードでサーバ起動を隔離しているため import で副作用（bind/実行）は起きない。
palette 配信ルートの主要シンボル（palette_index_path・do_GET 分岐・_serve_palette）は
`_run_server` のクロージャ内に定義されるため、ソース文字列を正として静的に検査する。
D群（実HTTPスモーク・discover 回帰）は tests/test_palette_klk019.py が、M群（ブリッジ実起動
＋ブラウザ実機）は tester が確認しチケットのログへ記録する。プロダクション成果物
（bridge.py / index.html / palette/index.html）は変更しない。

Run: python3 tests/site/check_klk019.py
Exit code 0 = all static/core checks pass, 1 = at least one fail.
"""
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_PATH = os.path.join(ROOT, "draft-gen", "bridge.py")
INDEX_HTML_PATH = os.path.join(ROOT, "draft-gen", "index.html")

BRIDGE_SRC = open(BRIDGE_PATH, encoding="utf-8").read()
INDEX_HTML = open(INDEX_HTML_PATH, encoding="utf-8").read()

# bridge.py を import（__main__ ガードで副作用なし＝サーバは起動しない）。
_spec = importlib.util.spec_from_file_location("klk019_bridge", BRIDGE_PATH)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# 危険フラグ（決して含めてはならない・最小権限）。
DANGER_FLAGS = ("--dangerously-skip-permissions", "bypassPermissions")


def _slice_between(src, start_pat, end_pat):
    """start_pat（正規表現）の一致位置から end_pat の次の一致位置手前までを返す。
    end_pat が見つからなければ末尾まで。start が無ければ空文字。"""
    m = re.search(start_pat, src)
    if not m:
        return ""
    i = m.end()
    m2 = re.search(end_pat, src[i:])
    return src[i:i + m2.start()] if m2 else src[i:]


# do_GET 本体（次メソッド do_POST の手前まで）を切り出す。
DO_GET_SEG = _slice_between(BRIDGE_SRC, r"\n        def do_GET\(self\):", r"\n        def do_POST\(self\):")
# _serve_palette 本体（次の def 手前まで）を切り出す。
PALETTE_SEG = _slice_between(BRIDGE_SRC, r"\n        def _serve_palette\(self\):", r"\n        def ")

# ===========================================================================
# S1 palette配信ルートの存在（パス定数・do_GET 分岐・ハンドラ定義）
# ===========================================================================
s1_const = re.search(
    r'palette_index_path\s*=\s*os\.path\.join\([^)]*["\']palette["\']\s*,\s*["\']index\.html["\']\s*\)',
    BRIDGE_SRC) is not None
s1_branch = "/palette/index.html" in DO_GET_SEG and "_serve_palette()" in DO_GET_SEG
s1_handler = "def _serve_palette(self):" in BRIDGE_SRC
s1 = s1_const and s1_branch and s1_handler
check(
    "S1 palette配信ルートの存在 (palette_index_path=os.path.join(...,'palette','index.html') 定数・do_GET に /palette/index.html→_serve_palette 分岐・def _serve_palette 定義)",
    s1,
    f"パス定数={s1_const}, do_GET分岐={s1_branch}, ハンドラ定義={s1_handler}",
)

# ===========================================================================
# S2 分岐位置（404フォールバックの手前）
# ===========================================================================
i_branch = DO_GET_SEG.find("/palette/index.html")
i_404 = DO_GET_SEG.find('self._json(404, {"error": "not found"})')
s2 = i_branch >= 0 and i_404 >= 0 and i_branch < i_404
check(
    "S2 分岐位置（404の手前） (do_GET 内で palette 分岐がソース上 self._json(404, {\"error\": \"not found\"}) より前に現れる＝未知パスは従来どおり404)",
    s2,
    f"palette分岐index={i_branch}, 404フォールバックindex={i_404}, 前後={i_branch < i_404 if (i_branch>=0 and i_404>=0) else 'N/A'}",
)

# ===========================================================================
# S3 固定パス決め打ち・パストラバーサル面なし
# ===========================================================================
s3_html_mime = "text/html; charset=utf-8" in PALETTE_SEG
s3_fixed_open = "palette_index_path" in PALETTE_SEG and re.search(
    r'open\(\s*palette_index_path\s*,\s*["\']rb["\']\s*\)', PALETTE_SEG) is not None
# ユーザー入力を取らない＝パストラバーサル面なし
s3_no_issafe = "is_safe" not in PALETTE_SEG
s3_no_realpath = "realpath" not in PALETTE_SEG
s3_no_unquote = "unquote" not in PALETTE_SEG
s3 = s3_html_mime and s3_fixed_open and s3_no_issafe and s3_no_realpath and s3_no_unquote
check(
    "S3 固定パス決め打ち・パストラバーサル面なし (_serve_palette が text/html; charset=utf-8 を返し palette_index_path を決め打ちで open(...,'rb')・本体に is_safe/realpath/unquote 非含有)",
    s3,
    f"text/html={s3_html_mime}, 固定open={s3_fixed_open}, is_safe無={s3_no_issafe}, realpath無={s3_no_realpath}, unquote無={s3_no_unquote}",
)

# ===========================================================================
# S4 _serve_index と同型のヘッダ（Content-Length・_cors()・500 グレースフル）
# ===========================================================================
s4_200 = "self.send_response(200)" in PALETTE_SEG
s4_ctype = re.search(
    r'send_header\(\s*["\']Content-Type["\']\s*,\s*["\']text/html; charset=utf-8["\']\s*\)',
    PALETTE_SEG) is not None
s4_clen = re.search(
    r'send_header\(\s*["\']Content-Length["\']\s*,\s*str\(len\(body\)\)\s*\)',
    PALETTE_SEG) is not None
s4_cors = "self._cors()" in PALETTE_SEG
s4_end = "self.end_headers()" in PALETTE_SEG and "self.wfile.write(body)" in PALETTE_SEG
s4_500 = "self._json(500," in PALETTE_SEG
s4 = s4_200 and s4_ctype and s4_clen and s4_cors and s4_end and s4_500
check(
    "S4 _serve_index と同型のヘッダ (_serve_palette: send_response(200)・Content-Type text/html; charset=utf-8・Content-Length str(len(body))・self._cors()・end_headers→wfile.write・読取失敗は self._json(500,…))",
    s4,
    f"200={s4_200}, Content-Type={s4_ctype}, Content-Length={s4_clen}, _cors={s4_cors}, write={s4_end}, 500={s4_500}",
)

# ===========================================================================
# S5 既存GETルート・404応答が不変（回帰保護）
# ===========================================================================
s5_root = re.search(r'path in \("/", "/index\.html"\)', DO_GET_SEG) is not None
s5_health = re.search(r'path == "/health"', DO_GET_SEG) is not None
s5_status = re.search(r'path\.startswith\("/status/"\)', DO_GET_SEG) is not None
s5_catalog = re.search(r'path == "/catalog"', DO_GET_SEG) is not None
s5_catalog_json = re.search(r'path == "/catalog\.json"', DO_GET_SEG) is not None
s5_catalog_img = re.search(r'path\.startswith\("/catalog/img/"\)', DO_GET_SEG) is not None
s5_404 = 'self._json(404, {"error": "not found"})' in DO_GET_SEG
s5 = (s5_root and s5_health and s5_status and s5_catalog and s5_catalog_json
      and s5_catalog_img and s5_404)
check(
    "S5 既存GETルート不変 (do_GET に /・/index.html・/health・/status/・/catalog・/catalog.json・/catalog/img/ と 404 フォールバックがすべて残存＝additive で既存を消していない)",
    s5,
    f"/,index={s5_root}, /health={s5_health}, /status/={s5_status}, /catalog={s5_catalog}, "
    f"/catalog.json={s5_catalog_json}, /catalog/img/={s5_catalog_img}, 404={s5_404}",
)

# ===========================================================================
# S6 起動リンク不変（check_klk006 整合・index.html 非変更）
# ===========================================================================
s6_link = re.search(
    r'href="\.\./palette/index\.html"[^>]*target="_blank"', INDEX_HTML) is not None
s6_no_parent2 = "../../palette" not in INDEX_HTML
s6_no_abs = re.search(r'href="https?://[^"]*palette', INDEX_HTML) is None
s6 = s6_link and s6_no_parent2 and s6_no_abs
check(
    "S6 起動リンク不変 (draft-gen/index.html に href=\"../palette/index.html\"＋target=\"_blank\" が存在・../../palette 不在・palette への絶対URLリンク不在＝リンクを変更していない)",
    s6,
    f"相対リンク={s6_link}, ../../palette無={s6_no_parent2}, 絶対URL無={s6_no_abs}",
)

# ===========================================================================
# S7 セキュリティ不変（危険フラグ非含有・shell=True 非使用・127.0.0.1）
# ===========================================================================
s7_no_danger = not any(f in BRIDGE_SRC for f in DANGER_FLAGS)
s7_no_shell = "shell=True" not in BRIDGE_SRC
s7_host = getattr(bridge, "BRIDGE_HOST", None) == "127.0.0.1"
s7 = s7_no_danger and s7_no_shell and s7_host
check(
    "S7 セキュリティ不変 (bridge.py: 危険フラグ[--dangerously-skip-permissions/bypassPermissions]非含有・shell=True 非使用・BRIDGE_HOST==127.0.0.1)",
    s7,
    f"危険フラグ非含有={s7_no_danger}, shell=True非使用={s7_no_shell}, 127.0.0.1={s7_host}",
)

# ===========================================================================
# S8 3パス正規化（完全一致・prefix一致で配下を配信しない）
# ===========================================================================
s8_exact = re.search(
    r'path in \(\s*"/palette"\s*,\s*"/palette/"\s*,\s*"/palette/index\.html"\s*\)',
    DO_GET_SEG) is not None
# palette 配下を startswith で拾っていない（任意ファイル配信面を作らない）
s8_no_prefix = 'startswith("/palette/")' not in BRIDGE_SRC and 'startswith("/palette")' not in BRIDGE_SRC
s8 = s8_exact and s8_no_prefix
check(
    "S8 3パス正規化 (palette 分岐が \"/palette\"・\"/palette/\"・\"/palette/index.html\" を path in (...) で完全一致受理・path.startswith(\"/palette/\") で配下を配信していない)",
    s8,
    f"3パス完全一致={s8_exact}, prefix一致なし={s8_no_prefix}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-019 static/core acceptance checks (docs/designs/KLK-019.md §9 S群 S1-S8 を正とする)")
print("対象: draft-gen/bridge.py(import + do_GET/_serve_palette ソース静的) + draft-gen/index.html(起動リンク)")
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
print("D群（test_palette_klk019.py で実HTTPスモーク・discover 回帰）:")
print("  - D1 S群 subprocess exit0")
print("  - D2 実HTTPスモーク（/palette[/][index.html]→200 text/html・想定外→404・/health,/→200 不変）")
print("  - D3 Quality Gate 全緑（python3 -m unittest discover -s tests・KLK-006〜018 回帰なし）")
print()
print("M群（tester がブリッジ起動＋ブラウザで手動確認・結果をログへ記録）:")
print("  - M1 ブリッジ経由でワンクリック起動（設定画面→配色ジェネレーター起動→別タブで表示・not found が出ない）")
print("  - M2 file:// 従来動作の非破壊（ブリッジ非稼働で兄弟 palette/index.html が開ける）")
print("  - M3 正規化の直打ち（/palette・/palette/ で開く・/palette/foo は {\"error\":\"not found\"}）")
sys.exit(1 if failed else 0)
