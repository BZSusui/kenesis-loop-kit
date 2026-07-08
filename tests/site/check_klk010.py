#!/usr/bin/env python3
"""
KLK-010 acceptance-condition checker (static / core / no browser・no network).

Verifies the statically-checkable acceptance conditions S1-S10 from
docs/designs/KLK-010.md §9（S群）against ローカルブリッジによるワンクリック生成:

  ブリッジ本体(純関数 import)  draft-gen/bridge.py
  設定画面(静的検証)            draft-gen/index.html
  スキル定義(additive)         .claude/skills/draft-generate/SKILL.md
  要件定義(§9/REQ-010)         docs/SPEC.md

Source of truth = 設計書 §9（S群）。check_klk006/009.py と同型（import 単体＋正規表現・
文字列検索・tester所有・exit 0/1・Python3標準ライブラリのみ・ネットワーク非使用）。
bridge.py は `if __name__ == "__main__"` ガードでサーバ起動を隔離しているため import で
副作用（bind/実行）は起きない。D群（git check-ignore＋回帰）は tests/test_palette_klk010.py が、
M群（ブリッジ起動＋実生成＋ブラウザ実機）は tester が手動確認してチケットのログへ記録する。
プロダクション成果物（bridge.py / index.html / SKILL.md / SPEC.md）は変更しない。

Run: python3 tests/site/check_klk010.py
Exit code 0 = all static/core checks pass, 1 = at least one fail.
"""
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_PATH = os.path.join(ROOT, "draft-gen", "bridge.py")
INDEX_PATH = os.path.join(ROOT, "draft-gen", "index.html")
SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md")
SPEC_PATH = os.path.join(ROOT, "docs", "SPEC.md")

INDEX = open(INDEX_PATH, encoding="utf-8").read()
SKILL = open(SKILL_PATH, encoding="utf-8").read()
SPEC = open(SPEC_PATH, encoding="utf-8").read()
BRIDGE_SRC = open(BRIDGE_PATH, encoding="utf-8").read()

# bridge.py を import（__main__ ガードで副作用なし＝サーバは起動しない）。
_spec = importlib.util.spec_from_file_location("klk010_bridge", BRIDGE_PATH)
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
    """外部URL（ローカル・プレースホルダ・許可ホストを除く）を列挙する。"""
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
# S1 スキーマ二重検証（validate_instruction・U-2 / U-8 / KLK-006 §4.4）
# ===========================================================================
def _valid_instr(**over):
    obj = {
        "schema": "design-draft-instruction",
        "version": 1,
        "industry": {"resolved": "美容室"},
        "layout": {"columns": "3col"},
        "colors": {"main": "#3366cc"},
    }
    obj.update(over)
    return obj


ok_valid, _ = bridge.validate_instruction(_valid_instr())
# 旧エイリアス columns（正規化後 canonical）も受理
ok_alias, _ = bridge.validate_instruction(_valid_instr(layout={"columns": "2col-sub-left"}))
ok_schema, _ = bridge.validate_instruction(_valid_instr(schema="other"))
ok_ver, _ = bridge.validate_instruction(_valid_instr(version=2))
ok_ind, _ = bridge.validate_instruction(_valid_instr(industry={"resolved": ""}))
ok_col, _ = bridge.validate_instruction(_valid_instr(layout={"columns": "5col"}))
ok_main, _ = bridge.validate_instruction(_valid_instr(colors={"main": "blue"}))
ok_notdict, _ = bridge.validate_instruction("not a dict")
s1 = (ok_valid and ok_alias
      and not ok_schema and not ok_ver and not ok_ind and not ok_col
      and not ok_main and not ok_notdict)
check(
    "S1 スキーマ二重検証 (validate_instruction: 正当/alias受理・schema/version≠1/industry欠落/未対応columns/不正main/非dict をreject)",
    s1,
    f"valid={ok_valid}, alias受理={ok_alias}, schema拒否={not ok_schema}, "
    f"version≠1拒否={not ok_ver}, industry欠落拒否={not ok_ind}, "
    f"未対応columns拒否={not ok_col}, 不正main拒否={not ok_main}, 非dict拒否={not ok_notdict}",
)

# columns 正規化の単体確認（normalize_columns）
nc_canon = bridge.normalize_columns("3col") == "3col"
nc_alias = bridge.normalize_columns("2col-sub-right") == "2col-body-right"
nc_bad = bridge.normalize_columns("5col") is None
nc_nonstr = bridge.normalize_columns(3) is None
check(
    "S1b normalize_columns (canonical維持・旧alias→body正規化・不正/非strは None)",
    nc_canon and nc_alias and nc_bad and nc_nonstr,
    f"canonical={nc_canon}, alias→body={nc_alias}, 不正None={nc_bad}, 非strNone={nc_nonstr}",
)

# ===========================================================================
# S2 案件名安全化＋保存先構築（sanitize_project / build_folder・DRAFT_RULES §9）
# ===========================================================================
sp_empty = bridge.sanitize_project("   ") == "untitled"
sp_blank = bridge.sanitize_project("") == "untitled"
sp_space = bridge.sanitize_project("株式会社 A") == "株式会社_A"
sp_forbidden = bridge.sanitize_project('a/b\\c:d*e?f"g<h>i|j') == "abcdefghij"
sp_nonstr = bridge.sanitize_project(None) == "untitled"
bf = bridge.build_folder("2026-07-08", "カフェ 案件") == "mockups/2026-07-08_カフェ_案件"
bf_default = bridge.build_folder("2026-07-08", "") == "mockups/2026-07-08_untitled"
check(
    "S2 案件名安全化＋保存先 (sanitize_project: 空白/空→untitled・空白→_・禁止文字除去 / build_folder: mockups/{日付}_{safe})",
    sp_empty and sp_blank and sp_space and sp_forbidden and sp_nonstr and bf and bf_default,
    f"空白→untitled={sp_empty}, 空→untitled={sp_blank}, 空白→_={sp_space}, "
    f"禁止文字除去={sp_forbidden}, 非str→untitled={sp_nonstr}, build_folder={bf}, "
    f"既定untitled={bf_default}",
)

# ===========================================================================
# S3 variants別オープン対象選択（select_open_target・U-5）
# ===========================================================================
so_folder = "mockups/2026-07-08_案件"
so_3 = bridge.select_open_target(so_folder, 3) == so_folder + "/compare.html"
so_2 = bridge.select_open_target(so_folder, 2) == so_folder + "/compare.html"
so_1 = bridge.select_open_target(so_folder, 1) == so_folder + "/index.html"
check(
    "S3 variants別オープン対象 (variants≥2→compare.html / variants==1→index.html を決定論選択)",
    so_3 and so_2 and so_1,
    f"3案→compare={so_3}, 2案→compare={so_2}, 1案→index={so_1}",
)

# ===========================================================================
# S4 コマンド/フラグ構築（build_claude_command・最小権限・U-1）
# ===========================================================================
cmd = bridge.build_claude_command("/abs/mockups/.pending/x.json")
cmd_flat = " ".join(cmd)
s4_base = (cmd[:2] == ["claude", "-p"]
           and "/draft-generate /abs/mockups/.pending/x.json" in cmd
           and "--permission-mode" in cmd and "acceptEdits" in cmd
           and "--output-format" in cmd and "json" in cmd)
s4_no_danger = not any(f in cmd_flat for f in DANGER_FLAGS)
s4_no_open_default = "--allowedTools" not in cmd
cmd_open = bridge.build_claude_command("/x.json", allow_open=True)
s4_open = ("--allowedTools" in cmd_open and "Bash(open *)" in cmd_open
           and not any(f in " ".join(cmd_open) for f in DANGER_FLAGS))
check(
    "S4 コマンド/フラグ構築 (claude -p /draft-generate {path} --permission-mode acceptEdits --output-format json・危険フラグ非含有・allow_openでopenのみ追加)",
    s4_base and s4_no_danger and s4_no_open_default and s4_open,
    f"基本形={s4_base}, 危険フラグ非含有={s4_no_danger}, "
    f"既定はopen非付与={s4_no_open_default}, allow_open時open追加={s4_open}",
)

# ===========================================================================
# S5 OSオープンコマンド構築（build_open_command・U-5）
# ===========================================================================
oc_mac = bridge.build_open_command("/t.html", "darwin") == ["open", "/t.html"]
oc_win = bridge.build_open_command("/t.html", "win32") == ["cmd", "/c", "start", "", "/t.html"]
oc_lin = bridge.build_open_command("/t.html", "linux") == ["xdg-open", "/t.html"]
oc_other = bridge.build_open_command("/t.html", "freebsd7") == ["xdg-open", "/t.html"]
check(
    "S5 OSオープンコマンド (darwin=open / win32=start / その他=xdg-open)",
    oc_mac and oc_win and oc_lin and oc_other,
    f"darwin={oc_mac}, win32={oc_win}, linux={oc_lin}, その他=xdg-open={oc_other}",
)

# ===========================================================================
# S6 localhost限定bind（BRIDGE_HOST定数・U-8 / NFR-004）
# ===========================================================================
s6_host = getattr(bridge, "BRIDGE_HOST", None) == "127.0.0.1"
# "0.0.0.0" を bind 用の文字列リテラルとして使用していない（コメント内の言及は許容）
s6_no_wildcard = ('"0.0.0.0"' not in BRIDGE_SRC) and ("'0.0.0.0'" not in BRIDGE_SRC)
check(
    "S6 localhost限定bind (BRIDGE_HOST==\"127.0.0.1\"・0.0.0.0 の文字列リテラル bind 非使用)",
    s6_host and s6_no_wildcard,
    f"BRIDGE_HOST=127.0.0.1={s6_host}, 0.0.0.0リテラル非使用={s6_no_wildcard}",
)

# ===========================================================================
# S7 index.html ブリッジ分岐（health/POST/status/ローディング/フォールバック・温存）
# ===========================================================================
i_health = "/health" in INDEX and "probeHealth" in INDEX
i_post = (re.search(r"'/generate'|\"/generate\"|/generate", INDEX) is not None
          and re.search(r"method:\s*'POST'|method:\s*\"POST\"", INDEX) is not None)
i_status = "/status/" in INDEX and "pollStatus" in INDEX
i_loading = ("bridgeStatus" in INDEX and "showLoading" in INDEX)
i_fallback = "showManualGuidance" in INDEX  # health 失敗時に従来 clipboard 経路へ退避
i_keep_build = "buildInstruction" in INDEX
i_keep_valid = "validateRequired" in INDEX
i_keep_clip = "navigator.clipboard.writeText" in INDEX
check(
    "S7 index.htmlブリッジ分岐 (/healthプローブ・POST /generate・/status/ポーリング・ローディングUI・フォールバック分岐・buildInstruction/validateRequired/clipboard 温存)",
    (i_health and i_post and i_status and i_loading and i_fallback
     and i_keep_build and i_keep_valid and i_keep_clip),
    f"health={i_health}, POST/generate={i_post}, status/poll={i_status}, "
    f"ローディング={i_loading}, フォールバック={i_fallback}, "
    f"buildInstruction={i_keep_build}, validateRequired={i_keep_valid}, clipboard={i_keep_clip}",
)

# ===========================================================================
# S8 SKILL ファイルパス受理（additive・後方互換・U-2 / R-2）
# ===========================================================================
sk_filepath = (".pending" in SKILL and "読み込んで" in SKILL
               and (".json` ファイル" in SKILL or "`.json`" in SKILL))
sk_args = "$ARGUMENTS" in SKILL           # 従来入力の後方互換
sk_paste = "貼り付け" in SKILL or "貼付" in SKILL
sk_version = (re.search(r"`version`[^\n]*`1`", SKILL) is not None) and "不変" in SKILL
sk_schema = "design-draft-instruction" in SKILL
check(
    "S8 SKILLファイルパス受理 (.pending/.json 読込を additive 追記・$ARGUMENTS/貼付JSON・version==1不変・schema 受付が残存)",
    sk_filepath and sk_args and sk_paste and sk_version and sk_schema,
    f"ファイルパス受理={sk_filepath}, $ARGUMENTS残存={sk_args}, 貼付残存={sk_paste}, "
    f"version==1不変={sk_version}, schema残存={sk_schema}",
)

# ===========================================================================
# S9 SPEC §9 / REQ-010 更新（ローカルブリッジのオプション構成＋フォールバック）
# ===========================================================================
sp_bridge = "ローカルブリッジ" in SPEC and "127.0.0.1" in SPEC
sp_option = "オプション" in SPEC
sp_fallback = "フォールバック" in SPEC and "外部依存なし" in SPEC
sp_oneclick = "ワンクリック" in SPEC
sp_req010 = "REQ-010" in SPEC
check(
    "S9 SPEC §9/REQ-010 更新 (ローカルブリッジがオプション構成・127.0.0.1・非稼働フォールバックで外部依存なし維持・ワンクリック挙動・REQ-010)",
    sp_bridge and sp_option and sp_fallback and sp_oneclick and sp_req010,
    f"ブリッジ+127.0.0.1={sp_bridge}, オプション={sp_option}, "
    f"フォールバック+外部依存なし={sp_fallback}, ワンクリック={sp_oneclick}, REQ-010={sp_req010}",
)

# ===========================================================================
# S10 セキュリティ/依存（外部URL0・秘密0・危険フラグ非含有・shell=True非使用）
# ===========================================================================
b_ext = _external_urls(BRIDGE_SRC)
i_ext = _external_urls(INDEX)
b_sec = _secret_hits(BRIDGE_SRC)
i_sec = _secret_hits(INDEX)
b_danger = [f for f in DANGER_FLAGS if f in BRIDGE_SRC]
i_danger = [f for f in DANGER_FLAGS if f in INDEX]
b_shell = "shell=True" in BRIDGE_SRC
i_shell = "shell=True" in INDEX
s10 = (not b_ext and not i_ext and not b_sec and not i_sec
       and not b_danger and not i_danger and not b_shell and not i_shell)
check(
    "S10 セキュリティ/依存 (bridge.py/index.html: 外部URL0[local/placeholder/w3.org/example.*除外]・秘密0・危険フラグ非含有・shell=True非使用)",
    s10,
    f"bridge外部URL={b_ext or 0}/秘密={b_sec or 0}/危険={b_danger or 0}/shellTrue={b_shell}; "
    f"index外部URL={i_ext or 0}/秘密={i_sec or 0}/危険={i_danger or 0}/shellTrue={i_shell}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-010 static/core acceptance checks (docs/designs/KLK-010.md §9 S群 を正とする)")
print("対象: draft-gen/bridge.py(import 純関数) + draft-gen/index.html(静的) +")
print("      .claude/skills/draft-generate/SKILL.md + docs/SPEC.md")
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
print("D群（test_palette_klk010.py で git check-ignore・回帰・git不在時skip）:")
print("  - D1 mockups/.pending/{id}.json の Git 除外成立（git check-ignore exit 0）")
print("  - D2 Quality Gate 全緑（python3 -m unittest discover -s tests・回帰なし）")
print()
print("M群（環境制約で静的検証外 = tester がブリッジ起動＋実生成＋ブラウザで手動確認）:")
print("  - M1 ワンクリック生成が権限プロンプトなしでヘッドレス実行され保存される")
print("  - M2 生成後 compare.html(複数案)/index.html(1案) がブリッジにより自動オープン")
print("  - M3 待ち時間UI/ポーリング（スピナー＋経過秒・完了/失敗表示）")
print("  - M4 ブリッジ非稼働時はクリップボード＋手順案内へフォールバック（壊れない）")
print("  - M5 タイムアウト/エラー処理・サブプロセス残留なし")
print("  - M6 機密のローカル完結（案件名の外部送信なし・生成物/一時ファイルGit非管理）")
print("  - M7 .claude/settings.json 非変更（開発ループ本体の権限を緩めない）")
sys.exit(1 if failed else 0)
