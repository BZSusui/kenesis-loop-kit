#!/usr/bin/env python3
"""
KLK-133 acceptance-condition checker — claude を PATH 頼みでなく実体で見つける。

★経緯（2026-09-16 の実使用レビュー / Windows 実機）
  `claude.exe` が `%USERPROFILE%\\.local\\bin` に**実在するのに**、起動.bat が
  「claude が見つかりません」で止まった。そのフォルダがユーザー PATH に無かったため。
  レビュー時は手作業で PATH を書き換えて回避したが、配布先の全員には頼めない。

  調査で、同じ原因系の問題がもう2つ見つかった。
    ・起動.command（macOS）も PATH しか見ていない
    ・★bridge.py は claude.cmd（npm 版）を起動できない。Windows の CreateProcess は
      PATHEXT を見ず .exe しか補わないため、`where claude` が通るのに
      **生成の瞬間だけ失敗する**

★この checker が守っているもの
  1. 解決が**純関数**で、環境を引数で渡せること（Windows 実機が無くても条件を再現できる）
  2. ★4条件（PATH にある / PATH に無いが実体あり / .cmd しかない / どこにも無い）の振る舞い
  3. `cmd /c` を挟むのは **Windows かつ .cmd/.bat のときだけ**であること
  4. 組み立て（build_*_command）の形を変えていないこと（既存4検査が見ている）
  5. 起動3箇所すべてが解決を通っていること
  6. 起動スクリプト2本が、PATH 以外も探し、**そのウィンドウ／プロセスの中だけ**に足すこと
  7. 見つからないときに**探した場所**を示すこと

Run: python3 tests/site/check_klk133.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

BRIDGE_SRC = io.open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
# ★KLK-132: 起動.bat は CP932(Shift_JIS)+CRLF が正
BAT = io.open(os.path.join(ROOT, "起動.bat"), encoding="cp932").read()
CMD = io.open(os.path.join(ROOT, "起動.command"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


WIN_ENV = {
    "USERPROFILE": "C:\\Users\\tester",
    "APPDATA": "C:\\Users\\tester\\AppData\\Roaming",
    "LOCALAPPDATA": "C:\\Users\\tester\\AppData\\Local",
}
MAC_ENV = {"HOME": "/Users/tester"}
BASE_CMD = ["claude", "-p", "/draft-generate x.json", "--permission-mode", "acceptEdits"]

# ---------------------------------------------------------------------------
# D1 純関数であること（環境を引数で渡せる＝実機が無くても条件を再現できる）
# ---------------------------------------------------------------------------
_sig_ok = all(hasattr(bridge, n) for n in ("resolve_claude_argv", "claude_candidates"))
check("D1 解決が純関数として在り、環境・PATH探索・実在判定を引数で渡せる",
      _sig_ok
      and bridge.resolve_claude_argv(BASE_CMD, platform="win32", env=WIN_ENV,
                                     which=lambda n: None, isfile=lambda p: False) == BASE_CMD,
      "resolve_claude_argv=%s / claude_candidates=%s"
      % (hasattr(bridge, "resolve_claude_argv"), hasattr(bridge, "claude_candidates")))

# ---------------------------------------------------------------------------
# D2 ★4条件の振る舞い（Windows 実機が無くても引数で再現する）
# ---------------------------------------------------------------------------
_cases = []

# ①PATH にある → **書き換えない**。exec も同じ PATH を辿って同じものを見つけるので、
#   絶対パスへ置き換える利点が無い。コマンドの見た目を変えると、この形に依存する
#   テストダブル（偽 claude）が反応しなくなる（実際にフルスイートで6件落ちて気づいた）
_r = bridge.resolve_claude_argv(BASE_CMD, platform="win32", env=WIN_ENV,
                                which=lambda n: "C:\\bin\\claude.exe", isfile=lambda p: False)
_cases.append(("①PATH にあるなら変えない", _r == BASE_CMD, _r[:2]))

# ②PATH に無いが、よくある場所に実体がある（レビューで起きた条件そのもの）
_want = "C:\\Users\\tester\\.local\\bin\\claude.exe"
_r = bridge.resolve_claude_argv(BASE_CMD, platform="win32", env=WIN_ENV,
                                which=lambda n: None, isfile=lambda p: p == _want)
_cases.append(("②PATH に無いが実体あり", _r[0] == _want and _r[1:] == BASE_CMD[1:], _r[:2]))

# ③.cmd しかない（npm 版）→ cmd /c を挟む
_r = bridge.resolve_claude_argv(BASE_CMD, platform="win32", env=WIN_ENV,
                                which=lambda n: "C:\\npm\\claude.cmd", isfile=lambda p: False)
_cases.append(("③.cmd は cmd /c 経由", _r[:3] == ["cmd", "/c", "C:\\npm\\claude.cmd"]
               and _r[3:] == BASE_CMD[1:], _r[:3]))

# ③' PATH に無く、よくある場所に .cmd しかない → 実体を指しつつ cmd /c も挟む
_r = bridge.resolve_claude_argv(BASE_CMD, platform="win32", env={"APPDATA": "C:\\A"},
                                which=lambda n: None, isfile=lambda p: p.endswith("claude.cmd"))
_cases.append(("③'PATH に無い .cmd", _r[:3] == ["cmd", "/c", "C:\\A\\npm\\claude.cmd"], _r[:3]))

# ④どこにも無い → 変えない（呼び出し側が従来どおり失敗し、案内を出す）
_r = bridge.resolve_claude_argv(BASE_CMD, platform="win32", env=WIN_ENV,
                                which=lambda n: None, isfile=lambda p: False)
_cases.append(("④どこにも無ければ変えない", _r == BASE_CMD, _r[:2]))

_ng = [n for n, ok, _ in _cases if not ok]
check("D2 ★4条件（PATHにある/PATHに無いが実体あり/.cmdのみ/どこにも無い）が正しい",
      not _ng, "不合格=%s / 実測=%s" % (_ng or "なし", [(n, v) for n, _, v in _cases]))

# ---------------------------------------------------------------------------
# D3 cmd /c を挟むのは Windows かつ .cmd/.bat のときだけ
# ---------------------------------------------------------------------------
_mac_cmdfile = bridge.resolve_claude_argv(BASE_CMD, platform="darwin", env=MAC_ENV,
                                          which=lambda n: "/usr/local/bin/claude.cmd",
                                          isfile=lambda p: False)
_win_exe = bridge.resolve_claude_argv(BASE_CMD, platform="win32", env=WIN_ENV,
                                      which=lambda n: "C:\\bin\\claude.exe", isfile=lambda p: False)
check("D3 cmd /c を挟むのは Windows かつ .cmd/.bat のときだけ",
      _mac_cmdfile[0] != "cmd" and _win_exe == BASE_CMD,
      "mac(.cmd 名でも挟まない)=%s / win(.exe には挟まない)=%s" % (_mac_cmdfile[0], _win_exe[0]))

# ---------------------------------------------------------------------------
# D4 組み立ての形は変えていない（既存4検査が見ている契約）
# ---------------------------------------------------------------------------
_builders = [
    ("build_claude_command", bridge.build_claude_command("x.json")),
    ("build_regenerate_command", bridge.build_regenerate_command("x.json")),
    ("build_catalog_import_command", bridge.build_catalog_import_command("x.json")),
]
_bad = [n for n, c in _builders if c[:2] != ["claude", "-p"]]
check("D4 組み立ての形は不変（build_*_command は claude -p のまま）",
      not _bad, "形が変わったもの=%s" % (_bad or "なし"))

# ---------------------------------------------------------------------------
# D5 起動3箇所すべてが解決を通っている
# ---------------------------------------------------------------------------
_wrapped = re.findall(r"resolve_claude_argv\(build_\w+\(", BRIDGE_SRC)
check("D5 起動3箇所すべてが解決を通っている（生成・再生成・取り込み）",
      len(_wrapped) == 3, "解決を挟んでいる箇所=%d件（期待3）" % len(_wrapped))

check("D6 shell=True を使っていない（最小権限の非回帰）",
      "shell=True" not in BRIDGE_SRC, "shell=True の出現=%s" % ("shell=True" in BRIDGE_SRC))

# ---------------------------------------------------------------------------
# D7-D9 起動スクリプト2本
# ---------------------------------------------------------------------------
_bat_probe = all(s in BAT for s in ("%USERPROFILE%\\.local\\bin\\claude.exe",
                                    "%APPDATA%\\npm\\claude.cmd"))
_bat_local = "set \"PATH=%PATH%;" in BAT and "setlocal" in BAT and "setx" not in BAT
check("D7 起動.bat が PATH 以外も探し、このウィンドウの中だけに足す（setx を使わない）",
      _bat_probe and _bat_local,
      "候補の探索=%s / 局所的な PATH 追加=%s / setx 不使用=%s"
      % (_bat_probe, "set \"PATH=%PATH%;" in BAT, "setx" not in BAT))

check("D8 起動.bat が、見つからないとき探した場所を示す",
      "探した場所" in BAT, "案内=%s" % ("探した場所" in BAT))

_cmd_probe = "$HOME/.local/bin" in CMD and "/opt/homebrew/bin" in CMD
check("D9 起動.command も同じ方針（探す・プロセス内だけに足す・探した場所を示す）",
      _cmd_probe and 'PATH="$PATH:$d"' in CMD and "探した場所" in CMD,
      "候補の探索=%s / PATH 追加=%s / 案内=%s"
      % (_cmd_probe, 'PATH="$PATH:$d"' in CMD, "探した場所" in CMD))

print("=" * 78)
print("KLK-133 claude を実体で見つける チェック")
print("=" * 78)
failed = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print("[%s] %s" % (status, name))
    print("        %s" % detail)
print("-" * 78)
print("%d checks, %d failed" % (len(results), failed))
sys.exit(1 if failed else 0)
