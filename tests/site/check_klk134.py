#!/usr/bin/env python3
"""
KLK-134 acceptance-condition checker — 置き場所の前提を案内する。

★経緯（2026-09-16 の実使用レビュー）
  一式が WSL 側（\\\\wsl.localhost\\...）に置かれており、起動.bat が失敗した。
  cmd.exe は「\\\\」で始まるパス（UNC パス）をカレントフォルダにできないため、
  cd /d "%~dp0" の時点で止まる。表示は「移動できませんでした」だけで原因に届かない。

  さらに、同梱の案内が**実態と食い違っていた**。
  「社内の共有フォルダに置いても、デスクトップに置いても構いません」と書いていたが、
  共有フォルダを \\\\サーバー名\\... の形のまま開くと Windows では起動できない。

★この checker が守っているもの
  1. 起動.bat が **cd より前に** 置き場所を判定すること（順序が逆だと意味がない）
  2. その案内が、対処（C:\\ へコピー / ドライブ文字の割り当て / WSL では直接起動）を示すこと
  3. 同梱の案内・README・マニュアルの3つに、この条件が書かれていること
  4. 「どこに置いても構わない」と読める古い記述が残っていないこと
  5. 起動ファイルの場所の記述が最上位になっていること（KLK-105 で移したのに古い記述が残っていた）

Run: python3 tests/site/check_klk134.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ★KLK-132: 起動.bat は CP932(Shift_JIS)+CRLF が正
BAT = io.open(os.path.join(ROOT, "起動.bat"), encoding="cp932").read()
GUIDE = io.open(os.path.join(ROOT, "はじめにお読みください.txt"), encoding="utf-8").read()
README = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
MANUAL = io.open(os.path.join(ROOT, "使い方マニュアル.html"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# E1-E3 起動.bat
# ---------------------------------------------------------------------------
_i_probe = BAT.find('if "%KLK_HERE:~0,2%"=="\\\\"')
_i_cd = BAT.find('cd /d "%~dp0"')
check("E1 ★置き場所の判定が cd より前にある（順序が逆だと原因に届かない）",
      _i_probe >= 0 and _i_cd >= 0 and _i_probe < _i_cd,
      "判定@%d / cd@%d" % (_i_probe, _i_cd))

_remedies = ("C:\\", "ドライブ文字", "python3 draft-gen/bridge.py")
_missing = [r for r in _remedies if r not in BAT]
check("E2 案内が対処を示す（C:\\ へコピー / ドライブ文字 / WSL では直接起動）",
      not _missing, "欠けている対処=%s" % (_missing or "なし"))

check("E3 判定した場所を画面に出す（どこから起動したか分かる）",
      "%KLK_HERE%" in BAT, "場所の表示=%s" % ("%KLK_HERE%" in BAT))

# ---------------------------------------------------------------------------
# E4-E6 3つの文書に書かれていること
# ---------------------------------------------------------------------------
for label, text, name in (("E4 同梱の案内", GUIDE, "はじめにお読みください.txt"),
                          ("E5 README", README, "README.md"),
                          ("E6 マニュアル", MANUAL, "使い方マニュアル.html")):
    _has_unc = "wsl.localhost" in text
    _has_fix = ("C:\\" in text) and ("ドライブ文字" in text)
    _has_wsl = "python3 draft-gen/bridge.py" in text
    check("%s に置き場所の条件が書かれている（%s）" % (label, name),
          _has_unc and _has_fix and _has_wsl,
          "UNC の説明=%s / 対処=%s / WSL の代替手順=%s" % (_has_unc, _has_fix, _has_wsl))

# ---------------------------------------------------------------------------
# E7-E8 古い記述が残っていないこと
# ---------------------------------------------------------------------------
_old_claim = "社内の共有フォルダに置いても、デスクトップに置いても構いません"
check("E7 「どこに置いても構わない」と読める古い記述が残っていない",
      _old_claim not in GUIDE,
      "残存=%s" % (_old_claim in GUIDE))

# KLK-105 で起動ファイルは最上位へ移したのに、README とマニュアルは draft-gen を開けと書いていた
_readme_old = "`draft-gen` フォルダの中の起動ファイル" in README
_manual_old = "フォルダの中の <code>draft-gen</code> を開きます" in MANUAL
check("E8 起動ファイルの場所の記述が最上位になっている（KLK-105 の反映漏れ）",
      not _readme_old and not _manual_old,
      "README の古い記述=%s / マニュアルの古い記述=%s" % (_readme_old, _manual_old))

print("=" * 78)
print("KLK-134 置き場所の前提を案内する チェック")
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
