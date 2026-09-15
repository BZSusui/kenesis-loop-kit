#!/usr/bin/env python3
"""
KLK-130 acceptance-condition checker — マニュアルの更新と mac 初回起動の警告対応。

★経緯（理恵さんの依頼・2026-09-15）
  「mac 環境だと初回に限り『このアプリは開いていません』というポップアップが出て、
   設定で調整しないと起動してくれないという声が多くあった」

  調べると **README.md と はじめにお読みください.txt には既に書いてあった**。
  それでも声が多かったのは、
    1. 利用者が読むのは 使い方マニュアル.html なのに、そこには一言も無かった
    2. 既存の記述は「右クリック →『開く』」だけで、
       新しい macOS ではそれでは開けず システム設定 → プライバシーとセキュリティ が要る
  の2点による。原因はツールの不具合ではなく macOS が付ける検疫の印。

★この checker が守っているもの
  M. マニュアルに mac 初回の警告の対処が**両方の経路**で載っていること
  D. 「不具合ではない」理由が書いてあること・対処表からも辿れること
  P. 同梱の README / はじめにお読みください にも新しい経路が載っていること
  U. 今回の改修（KLK-119〜129）にマニュアルが追いついていること

Run: python3 tests/site/check_klk130.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read(rel):
    p = os.path.join(ROOT, rel)
    return io.open(p, encoding="utf-8").read() if os.path.isfile(p) else ""


M = read("使い方マニュアル.html")
R = read("README.md")
T = read("はじめにお読みください.txt")
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def section_of(html, heading):
    """見出しから次の見出しまでを返す（純粋関数）。無ければ空文字。"""
    m = re.search(r"<h3>[^<]*%s[^<]*</h3>(.*?)(?=<h[23]>|</section>)" % re.escape(heading), html, re.S)
    return m.group(1) if m else ""


MAC = section_of(M, "Mac で初回")

# ---------------------------------------------------------------------------
# M / D. マニュアルの mac 対応
# ---------------------------------------------------------------------------
check("M1 マニュアルに mac 初回の節がある", bool(MAC), "%d 文字" % len(MAC))
check("M2 ★実際に出る文言を載せている（利用者が自分の画面と照合できる）",
      "開発元を確認できないため開けません" in M, "")
check("M3 ★経路1: Control キー／右クリック →「開く」",
      "Control キーを押しながらクリック" in MAC and "「開く」" in MAC, "")
check("M4 ★経路2: システム設定 → プライバシーとセキュリティ →「このまま開く」",
      "システム設定" in MAC and "プライバシーとセキュリティ" in MAC
      and "このまま開く" in MAC, "")
check("M5 ★経路2 が「経路1で開けないとき」の位置づけで書かれている",
      "開けないとき" in MAC, "")
check("D1 ★ツールの不具合ではないと明記している",
      "ツールの不具合ではありません" in MAC, "")
check("D2 なぜ出るのか（macOS が印を付ける）を書いている",
      "印" in MAC and "macOS" in MAC, "")
check("D3 初回だけであることを書いている",
      "最初の1回だけ" in MAC and "2回目" in MAC, "")
check("D4 Windows の同種の警告にも触れている",
      "WindowsによってPCが保護されました" in MAC, "")
check("D5 ★「うまくいかないとき」の対処表からも辿れる",
      re.search(r"<tr><td>Mac で「開発元を確認できないため開けません」[^<]*</td><td>.*?#start", M, re.S) is not None, "")

# ---------------------------------------------------------------------------
# P. 同梱ドキュメント
# ---------------------------------------------------------------------------
check("P1 README にシステム設定の経路がある",
      "プライバシーとセキュリティ" in R and "このまま開く" in R, "")
check("P2 はじめにお読みください にシステム設定の経路がある",
      "プライバシーとセキュリティ" in T and "このまま開く" in T, "")
check("P3 3つの文書で案内が食い違っていない（どれも両経路を書いている）",
      all("Control" in x or "Control キー" in x for x in (MAC, R, T)), "")

# ---------------------------------------------------------------------------
# U. 今回の改修にマニュアルが追いついているか
# ---------------------------------------------------------------------------
for name, needles in [
    ("U1 業種の「くわしい業種」（KLK-127）", ["くわしい業種"]),
    ("U2 ★参考素材の絞り込みは「一覧から選ぶ」を使う（KLK-127）",
     ["絞り込みには「一覧から選ぶ」を使います", "17区分"]),
    ("U3 行ごとの設定で型が日本語ラベルで出る（KLK-125）", ["日本語の説明つき"]),
    ("U4 ★型を図解アイコンの一覧から選ぶ（KLK-126）",
     ["選べる6つの形が一覧で開きます", "かんたんな図"]),
    ("U5 図は並び方を表す・同じ並びには同じ図（KLK-126）", ["同じ並び方の形には同じ図"]),
    ("U6 背景トーン（KLK-119）", ["背景トーン", "ライト／ダーク"]),
    ("U7 登録後に編集できる（KLK-120）", ["登録したあとでも直せます"]),
    ("U8 取り込み時に画像が自動で軽くなる（KLK-123/128）",
     ["画像は自動で軽くなります", "元の画像は加工されません"]),
]:
    missing = [n for n in needles if n not in M]
    check(name, not missing, "足りない記述=%s" % (missing or "なし"))

check("U9 一覧が Esc でも閉じられることを書いている（KLK-126）",
      "Esc キー" in M, "")

# ---------------------------------------------------------------------------
# 既存の約束を壊していないか
# ---------------------------------------------------------------------------
ext = re.findall(r'https?://(?!127\.0\.0\.1|localhost)[^\s"\'<)]+', M)
check("S1 外部依存ゼロを保っている（NFR-005）", not ext, "検出=%s" % (ext[:3] or "なし"))
check("S2 実在のカタログ内容を載せていない（案件名・画像）",
      "<img" not in M and "catalog/img" not in M, "")

print("=" * 78)
print("KLK-130 マニュアルの更新と mac 初回起動の警告 チェック")
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
