#!/usr/bin/env python3
"""
KLK-014 acceptance-condition checker (static / core / no browser・no network).

Verifies the statically-checkable acceptance conditions S1-S10 from
docs/designs/KLK-014.md §9（S群）against 生成導線の改善（ワンクリック起動ランチャー
＋フォールバック文言の正確化・SCR-001）:

  設定画面(静的検証)      draft-gen/index.html
  起動ランチャー(静的検証) draft-gen/起動.command

Source of truth = 設計書 KLK-014 §9（S群 S1-S10）。check_klk010/013.py と同型
（正規表現・文字列検索・tester所有・exit 0/1・Python3標準ライブラリのみ・
ネットワーク非使用・**起動.command は決して実行しない**＝ブリッジ副作用なし）。
D群（bash -n 構文チェック・discover 回帰）は tests/test_palette_klk014.py が、
M群（実機ダブルクリック起動・ワンクリック生成・claude不在案内・文言の分かりやすさ・
実行ビット復旧・実機 PATH）は tester/利用者が手動確認しチケットのログへ記録する。
プロダクション成果物（index.html / 起動.command）は変更しない。

Run: python3 tests/site/check_klk014.py
Exit code 0 = all static/core checks pass, 1 = at least one fail.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INDEX_PATH = os.path.join(ROOT, "draft-gen", "index.html")
LAUNCHER_REL = os.path.join("draft-gen", "起動.command")
LAUNCHER_PATH = os.path.join(ROOT, LAUNCHER_REL)

INDEX = open(INDEX_PATH, encoding="utf-8").read()
LAUNCHER = open(LAUNCHER_PATH, encoding="utf-8").read()

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
    """外部URL（ローカル・プレースホルダ・許可ホストを除く）を列挙する（check_klk010 同配慮）。"""
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


def _fn_body(src, header):
    """`function {name}() {` 相当のヘッダから次の関数定義までの本文を返す（静的抽出）。"""
    i = src.find(header)
    if i < 0:
        return ""
    j = src.find("\nfunction ", i + len(header))
    return src[i: j if j >= 0 else i + 1200]


# showManualGuidance() / showBridgeError(msg) の本文を抽出（トークン検査を各文言に限定）。
GUIDE_BODY = _fn_body(INDEX, "function showManualGuidance()")
ERROR_BODY = _fn_body(INDEX, "function showBridgeError(")

# ===========================================================================
# S1 新guide文言トークン（showManualGuidance・受入3）
# ===========================================================================
S1_TOKENS = ("チャット欄", "貼り付けて Enter", "コマンドは自動判定",
             "起動.command", "python3 draft-gen/bridge.py")
s1_hits = {t: (t in GUIDE_BODY) for t in S1_TOKENS}
s1 = bool(GUIDE_BODY) and all(s1_hits.values())
check(
    "S1 新guide文言トークン (showManualGuidance に「チャット欄」「貼り付けて Enter」「コマンドは自動判定」「起動.command」「python3 draft-gen/bridge.py」が含まれる)",
    s1,
    f"本文抽出={bool(GUIDE_BODY)}, トークン={s1_hits}",
)

# ===========================================================================
# S2 旧誤解文言の撤去（guide/error 双方・受入3）
# ===========================================================================
OLD_PHRASE = "/draft-generate に貼り付け"
s2_index = OLD_PHRASE not in INDEX          # ファイル全体から撤去
s2_cmdname = "/draft-generate" not in INDEX  # コマンド名の明示自体を撤去（§3.2）
s2 = s2_index and s2_cmdname
check(
    "S2 旧誤解文言の撤去 (index.html 全体から「/draft-generate に貼り付け」および「/draft-generate」コマンド名明示が消えている・guide/error双方)",
    s2,
    f"旧文言非残存={s2_index}, /draft-generate非残存={s2_cmdname}",
)

# ===========================================================================
# S3 新error文言トークン＋プレフィクス/msg連結維持（showBridgeError・受入3）
# ===========================================================================
S3_TOKENS = ("チャット欄", "貼り付けて Enter", "起動.command")
s3_hits = {t: (t in ERROR_BODY) for t in S3_TOKENS}
s3_prefix = "'エラー：'" in ERROR_BODY or "エラー：" in ERROR_BODY
s3_concat = "+ msg +" in ERROR_BODY or "+ msg" in ERROR_BODY
s3 = bool(ERROR_BODY) and all(s3_hits.values()) and s3_prefix and s3_concat
check(
    "S3 新error文言トークン＋連結維持 (showBridgeError に「チャット欄」「貼り付けて Enter」「起動.command」・'エラー：'プレフィクスと msg 連結を維持)",
    s3,
    f"本文抽出={bool(ERROR_BODY)}, トークン={s3_hits}, エラー：プレフィクス={s3_prefix}, msg連結={s3_concat}",
)

# ===========================================================================
# S4 関数/要素の維持（回帰・受入4）
# ===========================================================================
S4_SYMBOLS = ("function showManualGuidance", "function showBridgeError",
              "function setBridgeStatus", "id=\"bridgeStatus\"",
              "function probeHealth", "function tryBridge")
s4_sym = {s: (s in INDEX) for s in S4_SYMBOLS}
# health 失敗経路で showManualGuidance() を呼ぶ分岐（tryBridge 内）が残存。
s4_health_call = re.search(r"if\s*\(\s*!ok\s*\)\s*\{\s*showManualGuidance\(\)", INDEX) is not None
s4 = all(s4_sym.values()) and s4_health_call
check(
    "S4 関数/要素の維持 (showManualGuidance/showBridgeError/setBridgeStatus/#bridgeStatus/probeHealth/tryBridge が残存・health失敗経路の showManualGuidance() 呼出が残存)",
    s4,
    f"シンボル={s4_sym}, health失敗→showManualGuidance()={s4_health_call}",
)

# ===========================================================================
# S5 注入対策＋多行手段の維持（受入3/5）
# ===========================================================================
_sbs = _fn_body(INDEX, "function setBridgeStatus(")
s5_createtext = "createTextNode" in _sbs
s5_textcontent = "textContent" in _sbs
s5_no_innerhtml = ".innerHTML" not in INDEX  # innerHTML 非導入（注入対策）
# .bridge-status に white-space: pre-line（または pre-wrap）
_bs_css = re.search(r"\.bridge-status\s*\{[^}]*\}", INDEX, re.S)
_bs_css_txt = _bs_css.group(0) if _bs_css else ""
s5_preline = re.search(r"white-space:\s*pre-(line|wrap)", _bs_css_txt) is not None
s5 = s5_createtext and s5_textcontent and s5_no_innerhtml and s5_preline
check(
    "S5 注入対策＋多行手段 (setBridgeStatus が createTextNode/textContent を使用・innerHTML 非導入・.bridge-status に white-space: pre-line/pre-wrap)",
    s5,
    f"createTextNode={s5_createtext}, textContent={s5_textcontent}, innerHTML非導入={s5_no_innerhtml}, pre-line={s5_preline}",
)

# ===========================================================================
# S6 ランチャー存在＋shebang（受入1）
# ===========================================================================
s6_exists = os.path.isfile(LAUNCHER_PATH)
_first_line = LAUNCHER.splitlines()[0] if LAUNCHER else ""
s6_shebang = _first_line in ("#!/bin/bash", "#!/usr/bin/env bash")
s6 = s6_exists and s6_shebang
check(
    "S6 ランチャー存在＋shebang (draft-gen/起動.command が存在し先頭行が #!/bin/bash または #!/usr/bin/env bash)",
    s6,
    f"存在={s6_exists}, shebang={_first_line!r}",
)

# ===========================================================================
# S7 ランチャー存在チェック（黙って失敗しない・受入2）
# ===========================================================================
s7_py = "command -v python3" in LAUNCHER
s7_claude = "command -v claude" in LAUNCHER
s7_exit1 = "exit 1" in LAUNCHER
s7_jp = ("エラー" in LAUNCHER) or ("見つかりません" in LAUNCHER)
# 不在時に exit 1 する分岐（! command -v ... の if ブロック内で exit 1）が2つ以上ある
s7_branches = len(re.findall(r"if\s+!\s+command\s+-v\s+\w+", LAUNCHER)) >= 2
s7 = s7_py and s7_claude and s7_exit1 and s7_jp and s7_branches
check(
    "S7 ランチャー存在チェック (command -v python3 / command -v claude を含み・不在時 exit 1＋日本語案内[エラー/見つかりません]・不在分岐が2つ以上=黙って失敗しない)",
    s7,
    f"python3チェック={s7_py}, claudeチェック={s7_claude}, exit1={s7_exit1}, 日本語案内={s7_jp}, 不在分岐2+={s7_branches}",
)

# ===========================================================================
# S8 ランチャーがブリッジ起動（二重 open しない・受入1）
# ===========================================================================
s8_exec = "exec python3 draft-gen/bridge.py" in LAUNCHER
s8_cd = 'cd "$(dirname "$0")/.."' in LAUNCHER
# ブラウザを二重に open しない（open http / URLを開く行が無い）。
s8_no_open_url = re.search(r"\bopen\s+[\"']?https?://", LAUNCHER) is None
s8_no_open_bin = re.search(r"(?m)^\s*open\s", LAUNCHER) is None  # `open ...` 単体呼出も無い
s8 = s8_exec and s8_cd and s8_no_open_url and s8_no_open_bin
check(
    "S8 ランチャーがブリッジ起動 (exec python3 draft-gen/bridge.py・dirname で repoルートへ cd・open http/URL open 行なし=二重openしない)",
    s8,
    f"exec bridge={s8_exec}, cd repoルート={s8_cd}, open URL無={s8_no_open_url}, open単体無={s8_no_open_bin}",
)

# ===========================================================================
# S9 ランチャー安全性（受入5）
# ===========================================================================
s9_no_danger = [f for f in DANGER_FLAGS if f in LAUNCHER]
s9_no_rmrf = re.search(r"rm\s+-rf", LAUNCHER) is None
s9_no_fetch = [t for t in ("curl", "wget") if re.search(r"\b" + t + r"\b", LAUNCHER)]
s9_ext = _external_urls(LAUNCHER)
s9_sec = _secret_hits(LAUNCHER)
s9 = (not s9_no_danger and s9_no_rmrf and not s9_no_fetch
      and not s9_ext and not s9_sec)
check(
    "S9 ランチャー安全性 (危険フラグ非含有・rm -rf 非含有・curl/wget 等の外部取得非含有・外部URL0・秘密0)",
    s9,
    f"危険フラグ={s9_no_danger or 0}, rm -rf無={s9_no_rmrf}, 外部取得={s9_no_fetch or 0}, "
    f"外部URL={s9_ext or 0}, 秘密={s9_sec or 0}",
)

# ===========================================================================
# S10 実行ビット＋index回帰（受入1/5）
# ===========================================================================
s10_xbit = os.access(LAUNCHER_PATH, os.X_OK)
# git 追跡モードが 100755（実行ビット付き）で保存されている（git不在/未追跡は fail-open）。
s10_git_mode = None
try:
    proc = subprocess.run(
        ["git", "ls-files", "-s", LAUNCHER_REL],
        capture_output=True, text=True, cwd=ROOT, timeout=30)
    if proc.returncode == 0 and proc.stdout.strip():
        s10_git_mode = proc.stdout.split()[0]  # 例: "100755"
except (OSError, subprocess.SubprocessError):
    s10_git_mode = None
s10_git_ok = (s10_git_mode is None) or (s10_git_mode == "100755")
# index.html 回帰（S-SEC）: 外部URL0・秘密0・危険フラグ非含有・shell=True 非使用。
i_ext = _external_urls(INDEX)
i_sec = _secret_hits(INDEX)
i_danger = [f for f in DANGER_FLAGS if f in INDEX]
i_shell = "shell=True" in INDEX
s10 = (s10_xbit and s10_git_ok and not i_ext and not i_sec
       and not i_danger and not i_shell)
check(
    "S10 実行ビット＋index回帰 (起動.command が os.X_OK True[git追跡は100755] ; index.html 外部URL0・秘密0・危険フラグ非含有・shell=True 非使用)",
    s10,
    f"X_OK={s10_xbit}, git mode={s10_git_mode or 'N/A(fail-open)'}, "
    f"index外部URL={i_ext or 0}/秘密={i_sec or 0}/危険={i_danger or 0}/shellTrue={i_shell}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-014 static/core acceptance checks (docs/designs/KLK-014.md §9 S群 S1-S10 を正とする)")
print("対象: draft-gen/index.html(静的) + draft-gen/起動.command(静的・**実行しない**)")
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
print("D群（test_palette_klk014.py で束ね）:")
print("  - D1 check_klk014.py が exit 0（S群 束ね）")
print("  - D2 python3 -m unittest discover -s tests 全緑（既存 KLK-006〜013 回帰なし・特に check_klk010 S7）")
print("  - D3 bash -n draft-gen/起動.command が exit 0（構文解析のみ・実行しない）")
print()
print("M群（環境制約で静的検証外 = 人間[臼井さん]が実機で手動確認しチケットのログへ記録）:")
print("  - M1 起動.command ダブルクリック→Terminal→ブリッジ稼働→設定画面が自動でブラウザに開く")
print("  - M2 「ラフを生成」→貼り付けゼロのワンクリック生成→比較画面が自動オープン（主経路回帰なし）")
print("  - M3 claude 不在時に起動.command が日本語エラーを表示して停止（黙って失敗しない）")
print("  - M4 ブリッジ未起動で新フォールバック文言が表示され「チャット欄に貼り付け」で迷わず生成到達")
print("  - M5 実行ビットが落ちた配布物で冒頭コメントの chmod +x 案内で復旧できる")
print("  - M6 実機で claude が PATH に在り、ブリッジ経由の実生成が通る（U1確認）")
sys.exit(1 if failed else 0)
