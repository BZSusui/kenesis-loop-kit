#!/usr/bin/env python3
"""
KLK-018 acceptance-condition checker (static / core・no browser・no network).

Verifies the statically-checkable acceptance conditions S1-S9 from
docs/designs/KLK-018.md §9（S群）against ブリッジの成功判定の堅牢化
（終了コード単独判定 → 成果物ベース判定・失敗message日本語化・生JSON非露出）:

  ブリッジ本体(純関数 import + ソース静的検査)  draft-gen/bridge.py

Source of truth = 設計書 KLK-018 §9（S群 S1-S9）。独立ファイルのため S番号は S1 から
開始する（check_klk010〜017 は各チケットの正・本チェッカは触らない）。check_klk011/012
と同型: import 単体（純関数 is_job_success の真理値表）＋正規表現・文字列検索・波括弧/
出現順の静的検査・tester所有・exit 0/1・Python3標準ライブラリのみ・ネットワーク非使用。
bridge.py は `if __name__ == "__main__"` ガードでサーバ起動を隔離しているため import で
副作用（bind/実行）は起きない。D群（discover 回帰＋任意の worker 動的検証）は
tests/test_palette_klk018.py が、M群（ブリッジ起動＋ブラウザ実機）は tester=人間が
確認してチケットのログへ記録する。プロダクション成果物（bridge.py）は変更しない。

Run: python3 tests/site/check_klk018.py
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
_spec = importlib.util.spec_from_file_location("klk018_bridge", BRIDGE_PATH)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# --- 3ワーカーのソースブロックを抽出（関数境界＝連続する def 間で切り出す） ---
def _slice_func(src, name):
    """`def {name}(` から「同一インデントの次の def」までの本文を返す（見つからねば ''）。

    ワーカー内のネスト def（例: _run_catalog_import_job 内の _count_entries）で
    途中打ち切りしないよう、境界はワーカーと同じインデント段の def のみとする。
    """
    m = re.search(r"\n([ \t]*)def " + re.escape(name) + r"\(", src)
    if not m:
        return ""
    start = m.start()
    indent = m.group(1)
    nxt = re.search(r"\n" + re.escape(indent) + r"def \w+\(", src[m.end():])
    end = m.end() + nxt.start() if nxt else len(src)
    return src[start:end]


RUN_JOB = _slice_func(BRIDGE_SRC, "_run_job")
RUN_REGEN = _slice_func(BRIDGE_SRC, "_run_regen_job")
RUN_CATALOG = _slice_func(BRIDGE_SRC, "_run_catalog_import_job")

# 危険フラグ（決して含めてはならない・最小権限）。
DANGER_FLAGS = ("--dangerously-skip-permissions", "bypassPermissions")

# 外部URL検査で除外するホスト（ローカル/プレースホルダ/ドキュメント慣用）。
_ALLOW_HOSTS = ("www.w3.org", "example.com", "example.org", "example.net")
_LOCAL_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0")


def _host(url):
    m = re.match(r"https?://([^/\s\"')（]+)", url)
    return m.group(1).lower() if m else ""


def _external_urls(txt):
    """外部URL（ローカル・プレースホルダ・許可ホストを除く）を列挙する（check_klk011 S15 と同配慮）。"""
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


# 3処理の失敗時 確定日本語 message（§3.3・生JSON非露出）。全角括弧（claude）に注意。
CONFIRMED_MESSAGES = (
    "生成できませんでした。もう一度お試しください。解決しない場合は Claude Code（claude）が起動しているかご確認ください",
    "再生成できませんでした。もう一度お試しください。解決しない場合は Claude Code（claude）が起動しているかご確認ください",
    "取り込みできませんでした。もう一度お試しください。解決しない場合は Claude Code（claude）が起動しているかご確認ください",
)


# ===========================================================================
# S1 判定コア純関数の真理値表（is_job_success・MTIME_TOLERANCE_SEC）
# ===========================================================================
has_fn = callable(getattr(bridge, "is_job_success", None))
if has_fn:
    f = bridge.is_job_success
    # 真理値表（設計 §3.1）: 成果物ありは returncode を問わず成功／無ければ returncode==0 のみ成功。
    t_00 = f(0, False) is True     # 後方互換（従来 returncode==0）
    t_0t = f(0, True) is True      # 通常成功
    t_1t = f(1, True) is True      # ★本修正: 非0＋成果物あり→成功
    t_1f = f(1, False) is False    # ★真の失敗: 非0＋成果物なし→失敗
    t_2t = f(2, True) is True
    t_n1f = f(-1, False) is False
    tol = getattr(bridge, "MTIME_TOLERANCE_SEC", None)
    t_tol = isinstance(tol, float) and tol == 2.0
    s1 = t_00 and t_0t and t_1t and t_1f and t_2t and t_n1f and t_tol
    s1_detail = (
        f"(0,False)→成功={t_00}, (0,True)→成功={t_0t}, (1,True)→成功={t_1t}(★), "
        f"(1,False)→失敗={t_1f}(★), (2,True)→成功={t_2t}, (-1,False)→失敗={t_n1f}, "
        f"MTIME_TOLERANCE_SEC==2.0={t_tol}(値={tol})"
    )
else:
    s1 = False
    s1_detail = "is_job_success が bridge.py に存在しません"
check(
    "S1 判定コア純関数の真理値表 (is_job_success: 成果物ありは非0でも成功・非0＋成果物なしのみ失敗・MTIME_TOLERANCE_SEC==2.0)",
    s1,
    s1_detail,
)

# ===========================================================================
# S2 判定順序（timeout/起動失敗の温存が is_job_success より前）
# ===========================================================================
s2_details = []
s2 = True
for label, block in (("_run_job", RUN_JOB), ("_run_regen_job", RUN_REGEN),
                     ("_run_catalog_import_job", RUN_CATALOG)):
    i_timeout = block.find("except subprocess.TimeoutExpired")
    i_except = block.find("except Exception")
    i_judge = block.find("is_job_success(")
    ok = (0 <= i_timeout < i_judge) and (0 <= i_except < i_judge) and i_judge >= 0
    s2 = s2 and ok
    s2_details.append(
        f"{label}: timeout@{i_timeout}<判定@{i_judge}={0 <= i_timeout < i_judge}, "
        f"起動失敗except@{i_except}<判定={0 <= i_except < i_judge}")
check(
    "S2 判定順序温存 (3ワーカーとも except TimeoutExpired と 起動失敗 except が is_job_success 判定よりソース上で前)",
    s2,
    " / ".join(s2_details),
)

# ===========================================================================
# S3 成果物優先の判定へ置換（旧 returncode 単独判定が3処理から消えている）
# ===========================================================================
n_calls = len(re.findall(r"if\s+not\s+is_job_success\(", BRIDGE_SRC))
n_any = len(re.findall(r"is_job_success\(", BRIDGE_SRC))  # def 1 + calls
s3_old_gone = re.search(r"if\s+proc\.returncode\s*!=\s*0", BRIDGE_SRC) is None
s3 = (n_calls >= 3) and (n_any >= 4) and s3_old_gone
check(
    "S3 成果物優先へ置換 (if not is_job_success(...) が3処理で3回以上・旧 if proc.returncode != 0 単独判定が非残存)",
    s3,
    f"if not is_job_success 出現={n_calls}(>=3), is_job_success 総出現={n_any}(def+3calls>=4), "
    f"旧 proc.returncode!=0 非残存={s3_old_gone}",
)

# ===========================================================================
# S4 生成の成功条件（表示物の存在・_run_job）
# ===========================================================================
s4_folder = "build_folder(" in RUN_JOB
s4_select = "select_open_target(" in RUN_JOB
s4_exists = re.search(
    r"is_job_success\(\s*proc\.returncode\s*,\s*os\.path\.exists\(\s*abs_target\s*\)\s*\)",
    RUN_JOB) is not None
# 表示物パス構築が失敗判定より前（abs_target 定義 < is_job_success 呼び出し）
i_abs = RUN_JOB.find("abs_target =")
i_judge = RUN_JOB.find("is_job_success(")
s4_order = 0 <= i_abs < i_judge
s4 = s4_folder and s4_select and s4_exists and s4_order
check(
    "S4 生成の成功条件 (_run_job が build_folder/select_open_target で abs_target を構築し is_job_success(rc, os.path.exists(abs_target)) 判定・構築が判定の前)",
    s4,
    f"build_folder={s4_folder}, select_open_target={s4_select}, "
    f"is_job_success(rc,os.path.exists(abs_target))={s4_exists}, abs_target構築<判定={s4_order}",
)

# ===========================================================================
# S5 再生成の成功条件（mtime 更新検知・_run_regen_job）
# ===========================================================================
s5_getmtime = "os.path.getmtime(" in RUN_REGEN
s5_ts = "started_at.timestamp()" in RUN_REGEN
s5_tol = "MTIME_TOLERANCE_SEC" in RUN_REGEN
s5_judge = re.search(r"is_job_success\(\s*proc\.returncode\s*,", RUN_REGEN) is not None
s5 = s5_getmtime and s5_ts and s5_tol and s5_judge
check(
    "S5 再生成の成功条件 (_run_regen_job が os.path.getmtime + started_at.timestamp() + MTIME_TOLERANCE_SEC で更新検知し is_job_success(rc, …) へ渡す)",
    s5,
    f"os.path.getmtime={s5_getmtime}, started_at.timestamp()={s5_ts}, "
    f"MTIME_TOLERANCE_SEC={s5_tol}, is_job_success(rc,…)={s5_judge}",
)

# ===========================================================================
# S6 取込の成功条件（KLK-064 で改訂: proposal.json の生成有無・_run_catalog_import_job）
#
# 旧契約は「catalog.json が読める(after is not None)」を成果物有無としていたが、これは**常に真**で
# 成否を区別できず、ブリッジ経由の取り込みが一度も登録に到達しないまま「完了」と報告される一因だった。
# KLK-064 で成果物を **proposal.json の生成** に変更したため、本チェックも新契約へ更新する。
# ===========================================================================
s6_after_judge = re.search(
    r"is_job_success\(\s*proc\.returncode\s*,\s*proposal_ok\s*\)",
    RUN_CATALOG) is not None
# proposal_ok 算出が失敗判定の前（proposal_ok = os.path.isfile(...) < is_job_success）
i_after = RUN_CATALOG.find("proposal_ok = os.path.isfile(")
i_cat_judge = RUN_CATALOG.find("is_job_success(")
s6_order = 0 <= i_after < i_cat_judge
# 旧契約（常に真になる判定）が復活していないこと＝退行防止
s6_no_legacy = "is_job_success(proc.returncode, after is not None)" not in RUN_CATALOG
s6 = s6_after_judge and s6_order and s6_no_legacy
check(
    "S6 取込の成功条件 (_run_catalog_import_job が proposal_ok=os.path.isfile() を判定前に算出し is_job_success(rc, proposal_ok) 判定・旧契約の復活なし)",
    s6,
    f"is_job_success(rc, proposal_ok)={s6_after_judge}, proposal_ok算出<判定={s6_order}, 旧契約の不在={s6_no_legacy}",
)

# ===========================================================================
# S7 失敗messageの日本語化・生JSON非露出
# ===========================================================================
s7_msgs = [(m in BRIDGE_SRC) for m in CONFIRMED_MESSAGES]
s7_all_msgs = all(s7_msgs)
# 生JSON露出トークンがソース全体に非含有（tail 連結を除去済み）。
GLOBAL_FORBIDDEN = ("[-400:]", "proc.stdout", "proc.stderr", "total_cost_usd", ".format(tail")
s7_global = [tok for tok in GLOBAL_FORBIDDEN if tok in BRIDGE_SRC]
# message 割当行に JSON トークンが混入していない（usage/cost/json/--output-format）。
MSG_FORBIDDEN = ("usage", "cost", "json", "--output-format", "tail")
msg_lines = [line for line in BRIDGE_SRC.splitlines() if '"message"]' in line]
s7_msg_hits = [
    (tok, line.strip())
    for line in msg_lines for tok in MSG_FORBIDDEN if tok in line
]
s7 = s7_all_msgs and not s7_global and not s7_msg_hits
check(
    "S7 失敗message日本語化・生JSON非露出 (3確定文言が存在・[-400:]/proc.stdout/proc.stderr/total_cost_usd/tail 非含有・message割当行に usage/cost/json/--output-format 非混入)",
    s7,
    f"確定3文言存在={s7_all_msgs}({s7_msgs}), 全体禁止トークン={s7_global or 0}, "
    f"message行混入={s7_msg_hits or 0}",
)

# ===========================================================================
# S8 S14 維持（_now().strftime 非導入・started_at.strftime 維持）
# ===========================================================================
s8_no_now = re.search(r"_now\(\)\.strftime\(", BRIDGE_SRC) is None
s8_started = re.search(r"started_at\.strftime\(", BRIDGE_SRC) is not None
s8 = s8_no_now and s8_started
check(
    "S8 S14維持 (_now().strftime 非導入・生成 folder 導出は started_at.strftime を維持)",
    s8,
    f"_now().strftime 非含有={s8_no_now}, started_at.strftime 残存={s8_started}",
)

# ===========================================================================
# S9 S15 回帰保護（危険緩和なし・localhost限定・外部URL/秘密 0）
# ===========================================================================
b_danger = [flg for flg in DANGER_FLAGS if flg in BRIDGE_SRC]
b_shell = "shell=True" in BRIDGE_SRC
b_wildcard = ('"0.0.0.0"' in BRIDGE_SRC) or ("'0.0.0.0'" in BRIDGE_SRC)
b_host = getattr(bridge, "BRIDGE_HOST", None) == "127.0.0.1"
b_ext = _external_urls(BRIDGE_SRC)
b_sec = _secret_hits(BRIDGE_SRC)
s9 = (not b_danger and not b_shell and not b_wildcard and b_host
      and not b_ext and not b_sec)
check(
    "S9 S15回帰保護 (危険フラグ/shell=True/0.0.0.0リテラル 非含有・BRIDGE_HOST==127.0.0.1・外部URL0[local/placeholder除外]・秘密0)",
    s9,
    f"危険フラグ={b_danger or 0}, shellTrue={b_shell}, 0.0.0.0リテラル={b_wildcard}, "
    f"BRIDGE_HOST=127.0.0.1={b_host}, 外部URL={b_ext or 0}, 秘密={b_sec or 0}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-018 static/core acceptance checks (docs/designs/KLK-018.md §9 S群 S1-S9 を正とする)")
print("対象: draft-gen/bridge.py(import 純関数 is_job_success + ソース静的検査)")
print("注: check_klk010〜017 は各チケットの正・本チェッカは触らない(独立実行)")
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
print("D群（test_palette_klk018.py で discover 回帰＋任意の worker 動的検証）:")
print("  - D1 Quality Gate 全緑（python3 -m unittest discover -s tests・KLK-002〜017 回帰なし）")
print("  - D2 S群 subprocess 実行 exit0")
print("  - D3 worker 動的検証（subprocess.run を rc=1 noop 化・表示物あり→done／なし→error 日本語）")
print()
print("M群（環境制約で静的検証外 = tester=人間がブリッジ起動＋ブラウザ実機で手動確認）:")
print("  - M1 非0でも成果物ありで成功（比較画面が自動で開く・「生成が完了しました」）")
print("  - M2 真の失敗（claude不在/成果物なし）は日本語要約で失敗表示・使用量JSON非露出")
print("  - M3（任意）再生成/取込も成果物基準（対象更新/catalog.json ありで成功）")
sys.exit(1 if failed else 0)
