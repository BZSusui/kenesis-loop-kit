#!/usr/bin/env python3
"""
KLK-070 acceptance-condition checker (static + hook の実行 / no browser required).

Verifies W1-W13 from docs/designs/KLK-070.md §4.5 / §9:
Windows 対応（起動.bat / hook の両OS化 / webp の非macOSフォールバック / README の両OS化）。
あわせて catalog-import SKILL の手順2-0 と 手順3' の矛盾解消も検証する。

  縦串 起動      draft-gen/起動.bat（Windows）・起動.command（macOS）
  縦串 hook      .claude/settings.json（python3 が無い環境でも動くか）
  縦串 スキル    catalog-import/SKILL.md（変換先・id 採番・非macOS の skip）
  縦串 README    README.md（両OS の手順）
  縦串 ブリッジ  bridge.py（win32 の open・既存の非回帰）

★hook の `||` フォールバックが安全な理由（W5b で担保）:
  hook 3本は **常に exit 0** で終わり、拒否/ブロックは **stdout の JSON** で伝える。
  もし exit コードで拒否を伝える実装に変えると、`cmd || cmd2` の右辺が走って
  **拒否が打ち消される**。W5b はその退行を検出する。

Run: python3 tests/site/check_klk070.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BAT_PATH = os.path.join(ROOT, "draft-gen", "起動.bat")
CMD_PATH = os.path.join(ROOT, "draft-gen", "起動.command")
BAT = open(BAT_PATH, encoding="utf-8").read() if os.path.exists(BAT_PATH) else ""
SETTINGS = json.load(open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8"))
SKILL = open(os.path.join(ROOT, ".claude", "skills", "catalog-import", "SKILL.md"), encoding="utf-8").read()
README = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
BRIDGE_SRC = open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# W1-W4 起動.bat
# ---------------------------------------------------------------------------
check(
    "W1 draft-gen/起動.bat が存在し、macOS 版 起動.command も残っている",
    os.path.isfile(BAT_PATH) and os.path.isfile(CMD_PATH),
    "起動.bat=%s / 起動.command=%s" % (os.path.isfile(BAT_PATH), os.path.isfile(CMD_PATH)),
)
check(
    "W2 起動.bat が %~dp0.. でルートへ移動し bridge.py を起動する",
    '%~dp0..' in BAT and "draft-gen\\bridge.py" in BAT,
    "ルート移動=%s / bridge起動=%s" % ('%~dp0..' in BAT, "draft-gen\\bridge.py" in BAT),
)
check(
    "W3 起動.bat が Python を py -3 → python の順で探す（Windows の実情）",
    BAT.find("py -3 --version") >= 0 and BAT.find("python --version") > BAT.find("py -3 --version"),
    "py -3 の位置=%d / python の位置=%d" % (BAT.find("py -3 --version"), BAT.find("python --version")),
)
check(
    "W4 起動.bat が claude の有無を確認し、日本語で対処を出す",
    "where claude" in BAT and "【エラー】claude" in BAT and "Add Python to PATH" in BAT,
    "claude確認=%s / 日本語エラー=%s / PATH注意=%s"
    % ("where claude" in BAT, "【エラー】claude" in BAT, "Add Python to PATH" in BAT),
)

# ---------------------------------------------------------------------------
# W5-W6 hook
# ---------------------------------------------------------------------------
cmds = []
for ev, groups in (SETTINGS.get("hooks") or {}).items():
    for g in groups:
        for h in g.get("hooks", []):
            cmds.append((ev, h.get("command", "")))
no_fallback = [(e, c[:60]) for e, c in cmds if "|| python " not in c]
check(
    "W5 hook がすべて python フォールバックを持つ（python3 が無い環境でも動く）",
    len(cmds) == 3 and not no_fallback,
    "hook数=%d / フォールバック無し=%s" % (len(cmds), no_fallback or "なし"),
)
scripts = []
for _e, c in cmds:
    scripts += re.findall(r'\.claude/hooks/([A-Za-z_]+\.py)', c)
missing = [s for s in set(scripts) if not os.path.exists(os.path.join(ROOT, ".claude", "hooks", s))]
check(
    "W6 hook のスクリプトが3本とも実在する",
    len(set(scripts)) == 3 and not missing,
    "スクリプト=%s / 欠落=%s" % (sorted(set(scripts)), missing or "なし"),
)
# ★|| が安全である前提: hook は常に exit 0 で、拒否は stdout の JSON で伝える
bad_exit = []
for s in sorted(set(scripts)):
    path = os.path.join(ROOT, ".claude", "hooks", s)
    proc = subprocess.run([sys.executable, path], input="", capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        bad_exit.append((s, proc.returncode))
check(
    "W5b hook が空入力でも exit 0（|| の右辺が誤って走らない＝拒否が打ち消されない）",
    not bad_exit,
    "非0で終了したhook=%s" % (bad_exit or "なし（3本とも exit 0）"),
)
check(
    "W5c hook が拒否/ブロックを stdout の JSON で伝える（exit コードに依存しない）",
    all("permissionDecision" in open(os.path.join(ROOT, ".claude", "hooks", s), encoding="utf-8").read()
        or '"decision"' in open(os.path.join(ROOT, ".claude", "hooks", s), encoding="utf-8").read()
        or "record_metrics" in s
        for s in set(scripts)),
    "JSON で伝える=%s" % sorted(set(scripts)),
)

# ---------------------------------------------------------------------------
# W7-W10 SKILL（矛盾解消・非macOS フォールバック）
# ---------------------------------------------------------------------------
check(
    "W7 手順2-0 の変換先が .pending/ で、catalog/img/ へ書かない",
    "catalog/.pending/<同じbasename>.png" in SKILL
    and "**`catalog/img/` へは書かない。id も採番しない。**" in SKILL,
    "変換先=%s / img へ書かない明記=%s"
    % ("catalog/.pending/<同じbasename>.png" in SKILL,
       "**`catalog/img/` へは書かない。id も採番しない。**" in SKILL),
)
check(
    "W8 id 採番がブリッジの責務だと明記されている",
    "id 採番もブリッジが行う" in SKILL,
    "明記=%s" % ("id 採番もブリッジが行う" in SKILL),
)
check(
    "W9 sips が macOS 専用であり、無い環境では skip すると明記されている",
    "**`sips` は macOS 専用**" in SKILL and "当該ファイルだけを skip" in SKILL
    and "質問せず" in SKILL and "JPG / PNG は OS を問わず取り込める" in SKILL,
    "macOS専用=%s / skip=%s / 質問しない=%s / JPG/PNG可=%s"
    % ("**`sips` は macOS 専用**" in SKILL, "当該ファイルだけを skip" in SKILL,
       "質問せず" in SKILL, "JPG / PNG は OS を問わず取り込める" in SKILL),
)
check(
    "W10 手順2-0 と手順3' が矛盾しない（catalog/img/<新id>.png への変換指示が残っていない）",
    "catalog/img/<新id>.png" not in SKILL,
    "旧指示の残存=%s" % ("catalog/img/<新id>.png" in SKILL),
)

# ---------------------------------------------------------------------------
# W11-W12 README
# ---------------------------------------------------------------------------
check(
    "W11 README に Windows の起動手順（起動.bat）がある",
    "起動.bat" in README and "WindowsによってPCが保護されました" in README,
    "起動.bat=%s / SmartScreen の対処=%s"
    % ("起動.bat" in README, "WindowsによってPCが保護されました" in README),
)
check(
    "W12 README に両OSの停止方法・ポート確認方法がある",
    "netstat -ano" in README and "taskkill" in README and "lsof -nP" in README
    and "py -3 --version" in README,
    "netstat=%s / taskkill=%s / lsof=%s / py -3=%s"
    % ("netstat -ano" in README, "taskkill" in README, "lsof -nP" in README,
       "py -3 --version" in README),
)

# ---------------------------------------------------------------------------
# W13 bridge（既存の非回帰）
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402
check(
    "W13 bridge.build_open_command が win32 を扱う（既存の非回帰）",
    bridge.build_open_command("x.html", "win32") == ["cmd", "/c", "start", "", "x.html"]
    and bridge.build_open_command("x.html", "darwin") == ["open", "x.html"],
    "win32=%s / darwin=%s"
    % (bridge.build_open_command("x.html", "win32"), bridge.build_open_command("x.html", "darwin")),
)

print("=" * 78)
print("KLK-070 Windows 対応 静的チェック")
print("対象: 起動.bat / settings.json の hook / catalog-import SKILL / README / bridge")
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
