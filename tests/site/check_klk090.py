#!/usr/bin/env python3
"""
KLK-090 acceptance-condition checker (static / no browser required).

出荷整合 — 配布物に入る文書（README / CHANGELOG / SPEC）が実態と合っているか。

★このチェッカーが守っているもの:
  README と CHANGELOG は**配布物に入る**（make-package.sh がコピーする）。
  受け取った人はそれを読んで「何ができるか」を知る。実装が進むたびに書き足さないと、
  **文書が製品を過小に見せる**（実際 CHANGELOG は KLK-060 で34件ぶん止まっていた）。
  KLK-061 で「UIと実態の食い違い」を潰したのと同じ問題が、文書側で起きていた。

  R群 = README が主要機能を説明しているか
  C群 = CHANGELOG が現在地まで来ているか
  S群 = SPEC が実装を反映しているか

Run: python3 tests/site/check_klk090.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
README = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
CHANGELOG = io.open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
SPEC = io.open(os.path.join(ROOT, "docs", "SPEC.md"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ===========================================================================
# R群 — README（受け取った人が最初に読む）
# ===========================================================================
FEATURES = [
    ("ページ構成の組み立て", ["ページ構成", "同じセクションを複数", "本文あわせて12個"]),
    ("並べ替え（⠿ ドラッグ・理恵さんの要望）", ["⠿", "ドラッグ", "↑↓"]),
    ("レイアウト型の指定", ["レイアウト型", "3案ともその型"]),
    ("1案でも機能が同等", ["1案だけ作ったときも", "3案と同じように使えます"]),
    ("セクションの作り直し・型入れ替え", ["セクションを作り直す", "型を入れ替える"]),
    ("見本サイトURLからの配色読み取り", ["配色を読み取る", "レイアウト構成は読み取りません"]),
    ("参考サムネイルの段階表示", ["さらに表示する", "折りたたんでも隠れません"]),
    ("実績カタログの追加・削除", ["ドラッグ&ドロップ", "画面で確認・修正してから登録"]),
    ("ブリッジの状態確認", ["ローカルブリッジが動いているかの確認"]),
]
for label, needles in FEATURES:
    missing = [n for n in needles if n not in README]
    check(
        "R1 README が「%s」を説明している" % label,
        not missing,
        "欠け=%s" % (missing or "なし"),
    )

check(
    "R2 README が外部アクセスの扱いを説明している（配色読み取り）",
    "外部のサイトへアクセスします" in README and "保存せず" in README,
    "説明=%s" % ("外部のサイトへアクセスします" in README),
)

# ===========================================================================
# C群 — CHANGELOG（配布物に入る／実装から取り残されやすい）
# ===========================================================================
_klk = sorted({int(m) for m in re.findall(r"KLK-(\d{3})", CHANGELOG)})
check(
    "C1 CHANGELOG が KLK-095 まで来ている（34件の取り残しを繰り返さない）",
    _klk and max(_klk) >= 95,
    "記録済みの最大=KLK-%03d" % (max(_klk) if _klk else 0),
)
for label, needle in [
    ("ページ構成", "ページ構成を自由に組める"),
    ("型入れ替え", "型を入れ替えられる"),
    ("配色読み取り", "配色を読み取れる"),
    ("1案の機能同等化", "1案だけ作ったときも比較画面が開く"),
    ("タイムアウト延長", "1800秒"),
]:
    check("C2 CHANGELOG が「%s」を記録している" % label, needle in CHANGELOG,
          "記録=%s" % (needle in CHANGELOG))
check(
    "C3 CHANGELOG が主題ごとにまとめる方針を明記している（羅列に戻さない）",
    "主題ごとにまとめて" in CHANGELOG,
    "方針=%s" % ("主題ごとにまとめて" in CHANGELOG),
)

# ===========================================================================
# S群 — SPEC
# ===========================================================================
def spec_row(key):
    i = SPEC.find("| %s |" % key)
    return SPEC[i:SPEC.find("\n", i)] if i >= 0 else ""


check(
    "S1 SPEC REQ-005 が composition を反映している",
    "composition" in spec_row("REQ-005") and "3案とも同じ並び" in spec_row("REQ-005"),
    "反映=%s" % ("composition" in spec_row("REQ-005")),
)
check(
    "S2 SPEC REQ-008 が1案でも compare.html を出すと書いている",
    "variants:1" in spec_row("REQ-008") and "3案と同等" in spec_row("REQ-008"),
    "反映=%s" % ("variants:1" in spec_row("REQ-008")),
)
check(
    "S3 SPEC NFR-001 が生成時間の実測とタイムアウトの根拠を持つ",
    "847" in spec_row("NFR-001") and "1800秒" in spec_row("NFR-001"),
    "実測=%s" % ("847" in spec_row("NFR-001")),
)
check(
    "S4 SPEC の版数が v2.4 まで来ている",
    "| v2.4 |" in SPEC,
    "v2.4=%s" % ("| v2.4 |" in SPEC),
)

# ===========================================================================
# 配布物に入る文書であることの確認
# ===========================================================================
MK = io.open(os.path.join(ROOT, "tools", "make-package.sh"), encoding="utf-8").read()
check(
    "P1 README と CHANGELOG が配布物に入る（だから実態と合っている必要がある）",
    "README.md" in MK and "CHANGELOG.md" in MK,
    "同梱=%s" % ("CHANGELOG.md" in MK),
)

print("=" * 78)
print("KLK-090 出荷整合（README / CHANGELOG / SPEC）静的チェック")
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
