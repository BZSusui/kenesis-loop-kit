#!/usr/bin/env python3
"""
KLK-025 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S4 from
docs/designs/KLK-025.md §9（S群）against 配色「②メインカラーだけ」初回反映バグ修正:

  SCR-001 ビルダー   draft-gen/index.html（init のイベント登録）

バグ: mainOnlyPick が input イベントのみバインドされており、macOS Safari では input[type=color] の
input が初回選択で発火しないことがある → 1回目未反映・2回目反映。修正＝input/change 両イベント束ね。

Source of truth = 設計書 §9（S群）。check_klk018/019 と同型（正規表現・文字列検索・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。M群（実機 Safari での初回反映）は人間が確認する。

Run: python3 tests/site/check_klk025.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ===========================================================================
# S1 mainOnlyPick の両イベント束ね
# ===========================================================================
s1_pair = re.search(
    r"\['input',\s*'change'\]\.forEach\(function \(ev\) \{\s*\n\s*"
    r"document\.getElementById\('mainOnlyPick'\)\.addEventListener\(ev,\s*applyMainOnly\);",
    SRC) is not None
s1_no_single = re.search(
    r"getElementById\('mainOnlyPick'\)\.addEventListener\('input'", SRC) is None
check("S1 mainOnlyPick 両イベント束ね (['input','change'] で applyMainOnly を登録・単独'input'バインドの残存なし)",
      s1_pair and s1_no_single,
      f"両イベント={s1_pair}, 単独input残存なし={s1_no_single}")

# ===========================================================================
# S2 ハンドラの挙動不変（setColorRole main・colorMode main-only・render）
# ===========================================================================
m = re.search(r"const applyMainOnly = function \(e\) \{(.*?)\};", SRC, re.S)
body = m.group(1) if m else ""
s2 = ("setColorRole('main', e.target.value)" in body
      and "colorMode = 'main-only'" in body
      and "render()" in body)
check("S2 ハンドラ挙動不変 (applyMainOnly が setColorRole('main')・colorMode='main-only'・render() を含む)",
      s2, f"applyMainOnly本体={bool(m)}, 3要素={s2}")

# ===========================================================================
# S3 方法①スウォッチも両イベント束ね（同型の予防修正）
# ===========================================================================
s3_pair = re.search(
    r"\['input',\s*'change'\]\.forEach\(function \(ev\) \{ pick\.addEventListener\(ev,\s*applyPick\); \}\);",
    SRC) is not None
s3_apply = re.search(
    r"const applyPick = function \(\) \{\s*\n\s*hex\.value = pick\.value\.toLowerCase\(\);", SRC) is not None
s3_no_single = re.search(r"pick\.addEventListener\('input',", SRC) is None
check("S3 方法①スウォッチ両イベント束ね (applyPick を ['input','change'] へ・単独'input'残存なし)",
      s3_pair and s3_apply and s3_no_single,
      f"両イベント={s3_pair}, applyPick={s3_apply}, 単独input残存なし={s3_no_single}")

# ===========================================================================
# S4 既存回帰（hex欄 input リスナー・方法③貼り付け取り込みが不変）
# ===========================================================================
s4_hex = re.search(r"hex\.addEventListener\('input', function \(\) \{\s*\n\s*const norm = normalizeHex\(hex\.value\);", SRC) is not None
s4_paste = "getElementById('pasteImport').addEventListener('click'" in SRC \
    and "colorMode = 'pasted'" in SRC
check("S4 既存回帰保持 (hex欄の input リスナー・方法③ pasteImport click / colorMode='pasted' が不変)",
      s4_hex and s4_paste, f"hex欄={s4_hex}, 貼り付け取り込み={s4_paste}")

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-025 static acceptance checks (docs/designs/KLK-025.md §9 S群 を正とする)")
print("対象: draft-gen/index.html（配色イベント登録）")
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
print("M群（人間が実機確認・macOS Safari）: 4色初期状態→②で1回目の色選択が即 #hex-main に反映される")
sys.exit(1 if failed else 0)
