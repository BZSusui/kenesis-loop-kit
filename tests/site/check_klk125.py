#!/usr/bin/env python3
"""
KLK-125 acceptance-condition checker — SCR-001 の型選択にも日本語ラベルを出す。

★経緯
  KLK-117 で型の日本語ラベルを入れたが、**比較画面（compare.html）にしか適用していなかった**。
  SCR-001（生成設定）の「ページ構成 → 行ごとの設定 → レイアウト型」は今も英語マーカーのみで、
  理恵さんが見る2箇所のうち片方が取り残されていた（KLK-124 の調査で判明）。
  KLK-124 の段取りの**第1段**にあたる。

★この checker が守っているもの
  V. SCR-001 のラベル表が bridge.py（正）と**過不足なく一致**すること
  U. 選択肢が「日本語ラベル（マーカー）」で作られ、**送る値はマーカーのまま**であること
  S. 「自動（案ごとに振り分け）」が先頭に残っていること（既存の振る舞いを壊さない）

  実際に描かれた選択肢は tests/test_palette_klk125.py が実ブラウザで見る。

Run: python3 tests/site/check_klk125.py
"""
import importlib.util
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INDEX = io.open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "bridge_klk125", os.path.join(ROOT, "draft-gen", "bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def js_labels(src):
    """SCR-001 の const SECTION_TYPE_LABELS を {セクション: {マーカー: ラベル}} で返す（純粋関数）。"""
    m = re.search(r"const\s+SECTION_TYPE_LABELS\s*=\s*\{(.*?)\n\};", src, re.S)
    if not m:
        return None
    out = {}
    for line in m.group(1).split("\n"):
        mm = re.match(r"\s*([A-Z]+):\s*\{(.*)\},\s*$", line)
        if not mm:
            continue
        out[mm.group(1)] = dict(re.findall(r'"([^"]+)":\s*\'([^\']+)\'', mm.group(2)))
    return out


b = load_bridge()
SCR = js_labels(INDEX)

# ---------------------------------------------------------------------------
# V. 縦串の一致
# ---------------------------------------------------------------------------
check("V1 SCR-001 にラベル表がある", SCR is not None, "パースできた=%s" % (SCR is not None))

if SCR is not None:
    check("V2 セクションが bridge と一致する（14）",
          set(SCR) == set(b.SECTION_TYPE_LABELS) and len(SCR) == 14,
          "SCR=%d 差=%s" % (len(SCR), sorted(set(SCR) ^ set(b.SECTION_TYPE_LABELS)) or "なし"))

    diff = []
    for sec, tbl in b.SECTION_TYPE_LABELS.items():
        mine = SCR.get(sec, {})
        for m, lab in tbl.items():
            if mine.get(m) != lab:
                diff.append("%s:%s bridge=%r scr=%r" % (sec, m, lab, mine.get(m)))
        for m in mine:
            if m not in tbl:
                diff.append("%s:%s が bridge に無い" % (sec, m))
    check("V3 ★84型すべてのラベルが bridge と一字一句一致する",
          not diff, "不一致=%s（%d件）" % (diff[:3] or "なし", len(diff)))

    total = sum(len(v) for v in SCR.values())
    check("V4 84型ぶんある", total == 84, "%d 件" % total)

    pools_ok = []
    m = re.search(r"const\s+SECTION_TYPE_POOLS\s*=\s*\{(.*?)\n\};", INDEX, re.S)
    for sec, tbl in (SCR or {}).items():
        mm = re.search(r"\s%s:\s*\[(.*?)\]" % sec, m.group(1)) if m else None
        if mm:
            pool = re.findall(r"'([^']+)'", mm.group(1))
            if list(tbl) != pool:
                pools_ok.append("%s: ラベル順=%s プール順=%s" % (sec, list(tbl)[:2], pool[:2]))
    check("V5 ラベルの並びが同じ画面のプールと揃っている（選択肢の順が食い違わない）",
          not pools_ok, "ずれ=%s" % (pools_ok[:2] or "なし"))

# ---------------------------------------------------------------------------
# U. 画面の作り
# ---------------------------------------------------------------------------
check("U1 選択肢を「日本語ラベル（マーカー）」で作る",
      "lab ? lab + '（' + t + '）' : t" in INDEX,
      "組み立て=%s" % ("lab ? lab + '（' + t + '）' : t" in INDEX))

check("U2 ★送る値はマーカーのまま（o.value = t）",
      re.search(r"const o = document\.createElement\('option'\); o\.value = t;", INDEX) is not None,
      "value=t=%s" % (re.search(r"o\.value = t;", INDEX) is not None))

check("U3 選択肢を実際に追加している（appendChild を落としていない）",
      re.search(r"o\.textContent = lab \?.*\n\s*sel\.appendChild\(o\);", INDEX) is not None,
      "appendChild=%s" % (re.search(r"sel\.appendChild\(o\);", INDEX) is not None))

check("U4 動的値は textContent（innerHTML を導入していない）",
      ".innerHTML" not in INDEX, "innerHTML=%s" % (".innerHTML" in INDEX))

check("S1 「自動（案ごとに振り分け）」が残っている（既存の振る舞い）",
      "自動（案ごとに振り分け）" in INDEX, "")

check("S2 ラベルが無い型はマーカーだけで出す（穴が空いても空欄にしない）",
      "lab ? lab" in INDEX and "' : t;" in INDEX, "フォールバック=%s" % ("' : t;" in INDEX))

print("=" * 78)
print("KLK-125 SCR-001 の型選択に日本語ラベルを出す チェック")
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
