#!/usr/bin/env python3
"""
KLK-028 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S4 from
docs/designs/KLK-028.md §9（S群）against 配色カラーコードの「#」省略入力（6桁）受理:

  SCR-001 ビルダー   draft-gen/index.html（normalizeHex の6桁受理分岐・hex欄 blur 整形・ヒント文言）

要望: Photoshop 等のスポイトでコピーした #なし6桁（例 444850）を貼り付けても色が反映されるように。
3桁の#省略は従来どおり不可（smoke_klk006 D4 の既存ピンと整合・誤入力回避）。

Source of truth = 設計書 §9（S群）。check_klk025 と同型（正規表現・文字列検索・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。K群は smoke_klk028.node.js が実挙動を検証する。

Run: python3 tests/site/check_klk028.py
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


def fn_block(name):
    m = re.search(r"function %s\([^)]*\) \{(.*?)\n\}" % re.escape(name), SRC, re.S)
    return m.group(1) if m else ""


NORM = fn_block("normalizeHex")

# S1 normalizeHex の #なし6桁 受理分岐
s1_branch = re.search(r"if \(/\^\[0-9a-fA-F\]\{6\}\$/\.test\(t\)\) t = '#' \+ t;", NORM) is not None
s1_note = "KLK-028" in SRC and "3桁の#省略" in SRC
check("S1 normalizeHex 6桁受理分岐 (/^[0-9a-fA-F]{6}$/ → '#'+t・3桁は#必須の注記)",
      s1_branch and s1_note, f"分岐={s1_branch}, 注記={s1_note}")

# S2 hex 欄 blur（change）整形
s2 = re.search(
    r"hex\.addEventListener\('change', function \(\) \{\s*\n\s*const norm = normalizeHex\(hex\.value\);\s*\n\s*"
    r"if \(norm\) \{ hex\.value = norm; pick\.value = norm; render\(\); \}", SRC) is not None
check("S2 hex欄 blur整形 (change で norm 時のみ #rrggbb へ表示整形・pick 同期・render)",
      s2, f"blur整形={s2}")

# S3 ヒント文言
s3 = "#なし6桁（例 444850）でも入力できます" in SRC
check("S3 ヒント文言 (「#なし6桁（例 444850）でも入力できます」)", s3, f"文言={s3}")

# S4 既存回帰（従来分岐・validateRequired 依存が不変）
s4_six = re.search(r"/\^#\(\[0-9a-fA-F\]\{6\}\)\$/\.exec\(t\)", NORM) is not None
s4_three = re.search(r"/\^#\(\[0-9a-fA-F\]\{3\}\)\$/\.exec\(t\)", NORM) is not None
VALID = fn_block("validateRequired")
s4_valid = "normalizeHex(input.colors && input.colors.main)" in VALID
check("S4 既存回帰保持 (従来の #6桁/#3桁 分岐・validateRequired の normalizeHex(main) 依存が不変)",
      s4_six and s4_three and s4_valid, f"#6桁={s4_six}, #3桁={s4_three}, validate={s4_valid}")

# Report
print("=" * 78)
print("KLK-028 static acceptance checks (docs/designs/KLK-028.md §9 S群 を正とする)")
print("対象: draft-gen/index.html（normalizeHex・hex欄 blur 整形・ヒント）")
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
print("K群（smoke_klk028.node.js）: 444850受理 / 既存ピン維持(abc,#12,空,#12345,5桁,7桁→null) /")
print("  validateRequired 充足 / buildInstruction 出力は #つき小文字")
print("M群（人間が実機確認）: Photoshopコピー値の貼り付けで4色反映・blurで #444850 表示")
sys.exit(1 if failed else 0)
