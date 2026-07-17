#!/usr/bin/env python3
"""
KLK-026 acceptance-condition checker (static / no browser required).

Verifies the statically-checkable acceptance conditions S1-S7 from
docs/designs/KLK-026.md §9（S群）against カタログ非表示時の開き方ガイダンスと自動復帰:

  SCR-001 ビルダー   draft-gen/index.html（showCatalogGuidance / startCatalogRecovery / setupThumbPicker）

バグ（UXの罠）: file:// で開くとブリッジ稼働中でもカタログ非表示のうえ、案内文が「ブリッジを起動すると〜」で
原因に辿り着けない。修正＝開き方の自動検知（開き直しリンク / 起動.command 手順）＋ http 時の自動復帰。
同一オリジン設計（/catalog.json 相対 fetch・REQ-011）は不変。

Source of truth = 設計書 §9（S群）。check_klk025 と同型（正規表現・文字列検索・exit 0/1・
Python3標準ライブラリのみ・ネットワーク非使用）。M群（実機での開き直し導線）は人間が確認する。

Run: python3 tests/site/check_klk026.py
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


def fn_body(name):
    m = re.search(r"function %s\([^)]*\) \{(.*?)\n\}" % re.escape(name), SRC, re.S)
    return m.group(1) if m else ""


GUID = fn_body("showCatalogGuidance")
RECOV = fn_body("startCatalogRecovery")

# S1 setupThumbPicker が非稼働時に startCatalogRecovery を呼ぶ
s1 = re.search(
    r"if \(!catalogAlive\) \{ renderThumbs\(\[\]\); startCatalogRecovery\(\); return; \}", SRC) is not None
check("S1 setupThumbPicker 連携 (非稼働時に renderThumbs([])→startCatalogRecovery() の1行追加)",
      s1, f"呼び出し={s1}")

# S2 file:// 稼働時: 開き直しリンク（BRIDGE_ORIGIN 組立・注記つき）
s2_link = ("a.href = BRIDGE_ORIGIN + '/'" in GUID) and ("a.textContent = BRIDGE_ORIGIN" in GUID)
s2_word = "開き直してください" in GUID and "入力中の内容は引き継がれません" in GUID
check("S2 file://稼働時分岐 (BRIDGE_ORIGIN から開き直しリンクを組立・引き継がれない注記)",
      s2_link and s2_word, f"リンク組立={s2_link}, 文言={s2_word}")

# S3 file:// 未稼働: 起動.command / bridge.py の両手順
s3 = ("起動.command" in GUID) and ("python3 draft-gen/bridge.py" in GUID) and ("再確認しています" in GUID)
check("S3 file://未稼働分岐 (起動.command と python3 draft-gen/bridge.py の両手順＋再確認中の明示)",
      s3, f"手順案内={s3}")

# S4 http 分岐: 復帰時の自動読込
s4 = ("catalogAlive = true" in RECOV) and ("await loadCatalog()" in RECOV) \
    and ("applyThumbFilter()" in RECOV)
check("S4 http分岐の自動復帰 (復帰時 catalogAlive=true → loadCatalog → applyThumbFilter・リロード不要)",
      s4, f"自動復帰={s4}")

# S5 再探知の上限（3秒×最大40回・無限ポーリングでない）
s5 = ("MAX_ATTEMPTS = 40" in RECOV) and ("setTimeout(tick, 3000)" in RECOV) \
    and ("attempts < MAX_ATTEMPTS" in RECOV)
check("S5 再探知上限 (3秒間隔×最大40回で打ち切り・無限ポーリングなし)",
      s5, f"上限={s5}")

# S6 注入対策: createElement/textContent のみ・ガイダンスに innerHTML なし
s6_dom = ("document.createElement" in GUID) and (".textContent" in GUID)
s6_no_inner = "innerHTML" not in GUID and "innerHTML" not in RECOV
check("S6 注入対策 (ガイダンスは createElement/textContent 組立・innerHTML への変数埋め込みなし)",
      s6_dom and s6_no_inner, f"DOM組立={s6_dom}, innerHTML不使用={s6_no_inner}")

# S7 既存回帰: ピン文言残置・同一オリジン設計不変
s7_pin = "ブリッジを起動すると実績カタログから参考を選べます" in SRC
s7_rel = "fetch('/catalog.json')" in SRC
s7_no_abs = re.search(r"fetch\(BRIDGE_ORIGIN \+ '/catalog", SRC) is None  # カタログの絶対URL化をしていない
check("S7 既存回帰保持 (check_klk017ピン文言残置・/catalog.json 相対fetch不変・カタログの絶対URL化なし)",
      s7_pin and s7_rel and s7_no_abs,
      f"ピン文言={s7_pin}, 相対fetch={s7_rel}, 絶対URL化なし={s7_no_abs}")

# Report
print("=" * 78)
print("KLK-026 static acceptance checks (docs/designs/KLK-026.md §9 S群 を正とする)")
print("対象: draft-gen/index.html（showCatalogGuidance / startCatalogRecovery / setupThumbPicker）")
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
print("M群（人間が実機確認）: file://+稼働中→開き直しリンク / file://+未稼働→起動.command案内→起動で自動更新 /")
print("  起動.command から開く→最初からサムネイル表示")
sys.exit(1 if failed else 0)
