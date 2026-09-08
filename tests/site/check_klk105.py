#!/usr/bin/env python3
"""
KLK-105/106 acceptance-condition checker — 起動を最上位へ／アイコン／セットアップ手順書。

理恵さんのご要望（2026-09-08）:
  ・パッケージを展開してすぐの階層に起動アイコンを置きたい（draft-gen まで探すのは手間）
  ・起動ファイルのアイコンを変えたい（3案から C を採用）
  ・最上位に、起動するための設定方法を書いた手引きを置きたい

★この checker が守っているもの
  **「フォルダを開いた人が、迷わず押せる」状態。**
  起動スクリプトが1階層でも奥に戻ると、その価値が消える。
  さらに**パッケージに含まれること**まで見る。実際に、最上位へ移しただけで
  `make-package.sh` のコピー一覧に入れ忘れ、**配布物から消えていた**（実装時に発覚）。

Run: python3 tests/site/check_klk105.py
"""
import io
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


PKG = io.open(os.path.join(ROOT, "tools", "make-package.sh"), encoding="utf-8").read()

# ---------------------------------------------------------------------------
# 起動スクリプトが最上位にあり、そこから動く形になっているか
# ---------------------------------------------------------------------------
for fn in ("起動.command", "起動.bat"):
    check("A %s が**最上位**に実在する" % fn,
          os.path.isfile(os.path.join(ROOT, fn)),
          "最上位=%s / 旧位置(draft-gen/)=%s"
          % (os.path.isfile(os.path.join(ROOT, fn)),
             os.path.isfile(os.path.join(ROOT, "draft-gen", fn))))
    check("B %s が旧位置(draft-gen/)に残っていない（どちらが正か迷わせない）" % fn,
          not os.path.isfile(os.path.join(ROOT, "draft-gen", fn)),
          "旧位置の残存=%s" % os.path.isfile(os.path.join(ROOT, "draft-gen", fn)))

CMD = io.open(os.path.join(ROOT, "起動.command"), encoding="utf-8").read()
BAT = io.open(os.path.join(ROOT, "起動.bat"), encoding="utf-8").read()

# ★最上位へ移したので `/..` は付かない。付いたままだと1つ上（＝親フォルダ）へ出てしまう。
check("C 起動.command が自分の場所へ cd する（`/..` が付いていない）",
      'cd "$(dirname "$0")"' in CMD and 'cd "$(dirname "$0")/.."' not in CMD,
      "cd の形=%s" % (re.search(r'cd "\$\(dirname[^\n]*', CMD) or ["?"])[0])
check("D 起動.bat が自分の場所へ cd する（`%~dp0..` が残っていない）",
      "%~dp0" in BAT and "%~dp0.." not in BAT,
      "cd の形=%s" % (re.search(r'cd /d "[^"\n]*"', BAT) or ["?"])[0])
check("E 両方とも draft-gen/bridge.py を起動する（移動で参照が壊れていない）",
      "draft-gen/bridge.py" in CMD and "draft-gen\\bridge.py" in BAT,
      "command=%s / bat=%s"
      % ("draft-gen/bridge.py" in CMD, "draft-gen\\bridge.py" in BAT))
check("F 起動.command に実行権限がある",
      os.access(os.path.join(ROOT, "起動.command"), os.X_OK),
      "実行可=%s" % os.access(os.path.join(ROOT, "起動.command"), os.X_OK))

# ---------------------------------------------------------------------------
# セットアップ手順書
# ---------------------------------------------------------------------------
GUIDE_NAME = "はじめにお読みください.txt"
guide_path = os.path.join(ROOT, GUIDE_NAME)
check("G %s が最上位に実在する" % GUIDE_NAME, os.path.isfile(guide_path), guide_path)

G = io.open(guide_path, encoding="utf-8").read() if os.path.isfile(guide_path) else ""
for label, needle in (
    ("必要なもの Python 3", "Python 3"),
    ("必要なもの Claude Code", "Claude Code"),
    ("Mac の起動手順", "起動.command"),
    ("Windows の起動手順", "起動.bat"),
    ("初回の警告への対処", "右クリック"),
    ("PATH の注意（Windows）", "Add Python to PATH"),
    ("clone 済みの人向けの案内", "clone"),
    ("ポート衝突の回避", "KLK_BRIDGE_PORT"),
    ("困ったときの導線", "README.md"),
    ("使い方マニュアルへの導線", "使い方マニュアル.html"),
    ("取り扱いの確認先", "AI利用管理責任者"),
):
    check("H 手引きが「%s」に触れている" % label, needle in G, "記載=%s" % (needle in G))

check("I 手引きに開発用の番号が出ていない（KLK-085 と同じ規律）",
      not re.search(r"(?:REQ|KLK|SCR|NFR|OQ)-\d+", G),
      "検出=%s" % (re.findall(r"(?:REQ|KLK|SCR|NFR|OQ)-\d+", G)[:3] or "なし"))

# 手引きの記述が実装と食い違っていないか
BRIDGE = io.open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
check("J 手引きの既定ポートが実装と一致する",
      "8765" in G and "DEFAULT_PORT = 8765" in BRIDGE,
      "手引き=%s / 実装=%s" % ("8765" in G, "DEFAULT_PORT = 8765" in BRIDGE))

# ---------------------------------------------------------------------------
# ★パッケージに載ること（ここを落とすと全部が無意味になる）
# ---------------------------------------------------------------------------
# ★文字列の有無では**足りない**。一覧から外しても chmod 行や案内文に名前が残るので
#   素通りする（実際にこの検査を書いたとき素通りした）。
#   **実際にパッケージを作って、最上位に在るか**を見る。
_pkg_missing, _pkg_err = [], None
with tempfile.TemporaryDirectory() as _wd:
    _dest = os.path.join(_wd, "pkgcheck")
    _r = subprocess.run(["bash", os.path.join(ROOT, "tools", "make-package.sh"), _dest],
                        capture_output=True, text=True, cwd=ROOT, timeout=180)
    if _r.returncode != 0:
        _pkg_err = (_r.stderr or _r.stdout)[-200:]
    else:
        for fn in ("起動.command", "起動.bat", GUIDE_NAME, "使い方マニュアル.html", "README.md"):
            if not os.path.isfile(os.path.join(_dest, fn)):
                _pkg_missing.append(fn)
        _cmd = os.path.join(_dest, "起動.command")
        if os.path.isfile(_cmd) and not os.access(_cmd, os.X_OK):
            _pkg_missing.append("起動.command（実行権限なし）")
        # ★出来上がったパッケージにアイコンが**実際に付いているか**まで見る。
        #   Git はリソースフォークを保存しないので、作業ツリーを見ても意味がない。
        #   make-package.sh が毎回付け直しているかは、成果物でしか確かめられない。
        if sys.platform == "darwin" and os.path.isfile(_cmd):
            _rsrc = os.path.join(_cmd, "..namedfork", "rsrc")
            if not (os.path.isfile(_rsrc) and os.path.getsize(_rsrc) > 1000):
                _pkg_missing.append("起動.command（アイコンなし）")
check("K ★実際に作ったパッケージの**最上位**に、起動と手引きが在る",
      _pkg_err is None and not _pkg_missing,
      "作成エラー=%s / 欠落=%s" % (_pkg_err or "なし", _pkg_missing or "なし"))

check("L 完了メッセージが手引きを最初に案内している",
      GUIDE_NAME in PKG and "まず" in PKG,
      "案内=%s" % (GUIDE_NAME in PKG))

# ---------------------------------------------------------------------------
# アイコン（macOS のみ）
# ---------------------------------------------------------------------------
check("M アイコンの元データ（SVG）を残している（作り直せる）",
      os.path.isfile(os.path.join(ROOT, "assets", "icons", "起動アイコン.svg")),
      "assets/icons/起動アイコン.svg")
check("N アイコン適用ツールがある",
      os.path.isfile(os.path.join(ROOT, "tools", "set-mac-icon.py")),
      "tools/set-mac-icon.py")

TOOL = (io.open(os.path.join(ROOT, "tools", "set-mac-icon.py"), encoding="utf-8").read()
        if os.path.isfile(os.path.join(ROOT, "tools", "set-mac-icon.py")) else "")
check("O ツールが ZIP の注意（ditto でないとアイコンが消える）を記録している",
      "ditto" in TOOL and "zip -r" in TOOL,
      "記録=%s" % ("ditto" in TOOL))
check("P make-package.sh が ZIP 手順を案内する（ditto でないと消える）",
      "ditto -c -k --sequesterRsrc" in PKG, "ZIP案内=%s" % ("ditto -c -k --sequesterRsrc" in PKG))

# ★Git はリソースフォークを保存しない。clone 直後はアイコンも実行ビットも失われる
#   （実測で確認）。**作業ツリーのアイコンを当てにせず、毎回 SVG から付け直す**こと。
check("P2 ★make-package.sh が毎回アイコンを付け直す（clone した環境でも付く）",
      "set-mac-icon.py" in PKG and "assets/icons/起動アイコン.svg" in PKG,
      "道具の呼び出し=%s / 元データの参照=%s"
      % ("set-mac-icon.py" in PKG, "assets/icons/起動アイコン.svg" in PKG))

# 実際にアイコンが付いているか（macOS でのみ判定・他OSでは素通り）
if sys.platform == "darwin" and os.path.isfile(os.path.join(ROOT, "起動.command")):
    rsrc = os.path.join(ROOT, "起動.command", "..namedfork", "rsrc")
    has_rsrc = os.path.isfile(rsrc) and os.path.getsize(rsrc) > 1000
    icns_ok = False
    if has_rsrc:
        with open(rsrc, "rb") as fh:
            blob = fh.read(512)
        icns_ok = b"icns" in blob
    flags = subprocess.run(["GetFileInfo", "-a", os.path.join(ROOT, "起動.command")],
                           capture_output=True, text=True).stdout.strip()
    check("Q ★起動.command にカスタムアイコンが実際に付いている",
          has_rsrc and icns_ok and "C" in flags,
          "リソースフォーク=%s / icns=%s / フラグ=%s" % (has_rsrc, icns_ok, flags))
else:
    check("Q ★起動.command にカスタムアイコンが実際に付いている",
          True, "macOS 以外（判定不能・素通り）")

print("=" * 78)
print("KLK-105/106 起動を最上位へ／アイコン／セットアップ手順書 チェック")
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
