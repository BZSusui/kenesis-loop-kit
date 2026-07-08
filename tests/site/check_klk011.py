#!/usr/bin/env python3
"""
KLK-011 acceptance-condition checker (static / core / no browser・no network).

Verifies the statically-checkable acceptance conditions S11-S15 from
docs/designs/KLK-011.md §9（S群）against ローカルブリッジのセキュリティハードニング
(Origin検証・サイズ上限・保存先日付整合):

  ブリッジ本体(純関数 import + ソース静的検査)  draft-gen/bridge.py

Source of truth = 設計書 KLK-011 §9（S群 S11-S15）。check_klk010.py（S1-S10・KLK-010の正）
とは独立し、S番号は S11 から開始する（check_klk010.py は触らない）。check_klk010 と同型:
import 単体＋正規表現・文字列検索・tester所有・exit 0/1・Python3標準ライブラリのみ・
ネットワーク非使用。bridge.py は `if __name__ == "__main__"` ガードでサーバ起動を隔離して
いるため import で副作用（bind/実行）は起きない。D群（discover 回帰）は
tests/test_palette_klk011.py が、M群（ブリッジ起動＋擬似HTTP/ブラウザ実機）は tester が
確認してチケットのログへ記録する。プロダクション成果物（bridge.py）は変更しない。

Run: python3 tests/site/check_klk011.py
Exit code 0 = all static/core checks pass, 1 = at least one fail.
"""
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_PATH = os.path.join(ROOT, "draft-gen", "bridge.py")

BRIDGE_SRC = open(BRIDGE_PATH, encoding="utf-8").read()

# bridge.py を import（__main__ ガードで副作用なし＝サーバは起動しない）。
_spec = importlib.util.spec_from_file_location("klk011_bridge", BRIDGE_PATH)
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


def _host(url):
    m = re.match(r"https?://([^/\s\"')（]+)", url)
    return m.group(1).lower() if m else ""


def _external_urls(txt):
    """外部URL（ローカル・プレースホルダ・許可ホストを除く）を列挙する（check_klk010 S10 と同配慮）。"""
    out = []
    for m in re.findall(r'https?://[^\s"\')（]+', txt):
        host = _host(m)
        noport = host.split(":", 1)[0]
        if noport in _LOCAL_HOSTS or noport in _ALLOW_HOSTS:
            continue
        if "{" in host or "%" in host:  # format プレースホルダ（http://{0}:{1}/ 等）
            continue
        out.append(m)
    return out


_SECRET_RE = re.compile(
    r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)


def _secret_hits(txt):
    return [ln for ln, line in enumerate(txt.splitlines(), 1)
            if _SECRET_RE.search(line)]


# ===========================================================================
# S11 Origin 許可判定（4条件・is_allowed_origin・M-SEC-1）
# ===========================================================================
# 純関数を import して直接検証（任意ポート注入）。
has_fn = callable(getattr(bridge, "is_allowed_origin", None))
if has_fn:
    f = bridge.is_allowed_origin
    HOST = getattr(bridge, "BRIDGE_HOST", "127.0.0.1")
    # ①不在(None)→許可 ②"null"(file://)→許可
    c_none = f(None, HOST, 8765) is True
    c_null = f("null", HOST, 8765) is True
    # ③正規オリジン→許可（既定ポート/env上書きポート＝任意ポート注入で一致）
    c_127_default = f("http://127.0.0.1:8765", HOST, 8765) is True
    c_local_default = f("http://localhost:8765", HOST, 8765) is True
    c_127_alt = f("http://127.0.0.1:9999", HOST, 9999) is True
    c_local_alt = f("http://localhost:9999", HOST, 9999) is True
    # ④別オリジン→拒否（evil / http以外 / ポート不一致 / スキーム違い）
    c_evil = f("http://evil.example", HOST, 8765) is False
    c_evil_slash = f("http://evil.example/", HOST, 8765) is False
    c_wrong_port = f("http://127.0.0.1:9999", HOST, 8765) is False
    c_https = f("https://127.0.0.1:8765", HOST, 8765) is False
    c_empty = f("", HOST, 8765) is False
    s11 = (c_none and c_null and c_127_default and c_local_default
           and c_127_alt and c_local_alt
           and c_evil and c_evil_slash and c_wrong_port and c_https and c_empty)
    s11_detail = (
        f"None許可={c_none}, null許可={c_null}, "
        f"127:default許可={c_127_default}, localhost:default許可={c_local_default}, "
        f"127:alt許可={c_127_alt}, localhost:alt許可={c_local_alt}, "
        f"evil拒否={c_evil}, evil/拒否={c_evil_slash}, ポート不一致拒否={c_wrong_port}, "
        f"https拒否={c_https}, 空文字拒否={c_empty}"
    )
else:
    s11 = False
    s11_detail = "is_allowed_origin が bridge.py に存在しません"
check(
    "S11 Origin許可判定 (is_allowed_origin: None/null許可・http://{127.0.0.1,localhost}:{port}許可[任意ポート]・別オリジン/ポート不一致/https/空文字は拒否)",
    s11,
    s11_detail,
)

# ===========================================================================
# S12 サイズ上限定数＋チェック（MAX_BODY_BYTES・413/400 ガード・L-1）
# ===========================================================================
mbb = getattr(bridge, "MAX_BODY_BYTES", None)
s12_const = isinstance(mbb, int) and not isinstance(mbb, bool) and mbb == (1 << 20)
# _generate に 413（超過）ガードが静的にある
s12_413 = (re.search(r"length\s*>\s*MAX_BODY_BYTES", BRIDGE_SRC) is not None
           and re.search(r"self\._json\(\s*413", BRIDGE_SRC) is not None)
# Content-Length を int() で読み ValueError→400・負値(length < 0)→400 のガードが静的にある
s12_int = re.search(
    r"int\(\s*self\.headers\.get\(\s*[\"']Content-Length[\"']", BRIDGE_SRC) is not None
s12_neg = re.search(r"length\s*<\s*0", BRIDGE_SRC) is not None
s12_400 = re.search(r"self\._json\(\s*400", BRIDGE_SRC) is not None
s12 = s12_const and s12_413 and s12_int and s12_neg and s12_400
check(
    "S12 サイズ上限 (MAX_BODY_BYTES==1<<20 の正整数・_generate に >MAX→413・int(Content-Length)/負値→400 ガード静的存在)",
    s12,
    f"定数1<<20={s12_const}(値={mbb}), >MAX→413={s12_413}, int(Content-Length)={s12_int}, "
    f"負値<0ガード={s12_neg}, 400応答={s12_400}",
)

# ===========================================================================
# S13 Origin 検証の適用（_generate 冒頭で判定→非許可 403・M-SEC-1）
# ===========================================================================
# _generate 冒頭で is_allowed_origin(...Origin..., BRIDGE_HOST, port) を判定し非許可 403。
s13_call = re.search(
    r"is_allowed_origin\(\s*self\.headers\.get\(\s*[\"']Origin[\"']\s*\)\s*,\s*BRIDGE_HOST\s*,\s*port\s*\)",
    BRIDGE_SRC) is not None
# not で否定し 403 を返すガード（呼び出しと 403 が近接）
s13_guard = re.search(
    r"if\s+not\s+is_allowed_origin\([^)]*\)[^)]*\):\s*\n\s*self\._json\(\s*403",
    BRIDGE_SRC) is not None
s13_403 = re.search(r"self\._json\(\s*403", BRIDGE_SRC) is not None
# body 読取前に判定していること（is_allowed_origin の位置 < rfile.read の位置）
_gen_idx = BRIDGE_SRC.find("def _generate")
_call_idx = BRIDGE_SRC.find("is_allowed_origin(self.headers", _gen_idx)
if _call_idx < 0:
    _call_idx = BRIDGE_SRC.find("is_allowed_origin(", _gen_idx)
_read_idx = BRIDGE_SRC.find("self.rfile.read", _gen_idx)
s13_before_read = (0 <= _call_idx < _read_idx)
s13 = s13_call and s13_guard and s13_403 and s13_before_read
check(
    "S13 Origin検証の適用 (_generate 冒頭で is_allowed_origin(Origin, BRIDGE_HOST, port) 判定→非許可 403・body読取前)",
    s13,
    f"呼出形一致={s13_call}, not…→403ガード={s13_guard}, 403応答={s13_403}, body読取前={s13_before_read}",
)

# ===========================================================================
# S14 保存先日付整合（_run_job が started_at 基準・_now().strftime 不使用・L-2）
# ===========================================================================
# _run_job に started_at 引数が渡る
s14_param = re.search(r"def\s+_run_job\(\s*[^)]*started_at[^)]*\)", BRIDGE_SRC) is not None
# folder 導出が started_at.strftime を使う
s14_started = re.search(r"started_at\.strftime\(", BRIDGE_SRC) is not None
# 旧: 完了時 _now().strftime による日付再導出を使っていない
s14_no_now = re.search(r"_now\(\)\.strftime\(", BRIDGE_SRC) is None
# worker 起動 args に started_at が渡る（Thread へ受渡）
s14_args = re.search(r"args=\([^)]*started_at[^)]*\)", BRIDGE_SRC) is not None
s14 = s14_param and s14_started and s14_no_now and s14_args
check(
    "S14 保存先日付整合 (_run_job に started_at 引数・started_at.strftime で folder 導出・_now().strftime 再導出は不使用・Thread args に started_at)",
    s14,
    f"started_at引数={s14_param}, started_at.strftime使用={s14_started}, "
    f"_now().strftime不使用={s14_no_now}, Thread args渡し={s14_args}",
)

# ===========================================================================
# S15 回帰保護（危険緩和なし・localhost限定・CORS維持・外部URL/秘密 0）
# ===========================================================================
b_danger = [flg for flg in DANGER_FLAGS if flg in BRIDGE_SRC]
b_shell = "shell=True" in BRIDGE_SRC
b_wildcard = ('"0.0.0.0"' in BRIDGE_SRC) or ("'0.0.0.0'" in BRIDGE_SRC)
b_host = getattr(bridge, "BRIDGE_HOST", None) == "127.0.0.1"
# CORS `*` が（GET 応答含め）残存＝KLK-010 疎通維持
b_cors = re.search(r'Access-Control-Allow-Origin["\']\s*,\s*["\']\*["\']', BRIDGE_SRC) is not None
b_ext = _external_urls(BRIDGE_SRC)
b_sec = _secret_hits(BRIDGE_SRC)
s15 = (not b_danger and not b_shell and not b_wildcard
       and b_host and b_cors and not b_ext and not b_sec)
check(
    "S15 回帰保護 (危険フラグ/shell=True/0.0.0.0リテラル 非含有・BRIDGE_HOST==127.0.0.1・CORS `*` 残存・外部URL0[local/placeholder除外]・秘密0)",
    s15,
    f"危険フラグ={b_danger or 0}, shellTrue={b_shell}, 0.0.0.0リテラル={b_wildcard}, "
    f"BRIDGE_HOST=127.0.0.1={b_host}, CORS*残存={b_cors}, 外部URL={b_ext or 0}, 秘密={b_sec or 0}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-011 static/core acceptance checks (docs/designs/KLK-011.md §9 S群 S11-S15 を正とする)")
print("対象: draft-gen/bridge.py(import 純関数 + ソース静的検査)")
print("注: check_klk010.py(S1-S10) は KLK-010 の正・本チェッカは触らない(独立実行)")
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
print("D群（test_palette_klk011.py で discover 回帰）:")
print("  - D1 Quality Gate 全緑（python3 -m unittest discover -s tests・KLK-006〜010 回帰なし）")
print()
print("M群（環境制約で静的検証外 = tester がブリッジ起動＋擬似HTTP/ブラウザで手動確認）:")
print("  - M1 正規オリジン(127.0.0.1:8765)からの生成が通る（403にならない）")
print("  - M2 別オリジン POST は 403 で拒否（claude 非起動）")
print("  - M3 file:// フォールバック（Origin なし/null）が壊れない・null POST が許可される")
print("  - M4 巨大ボディ（>MAX_BODY_BYTES）は 413 で拒否")
sys.exit(1 if failed else 0)
