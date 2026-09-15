#!/usr/bin/env python3
"""
KLK-128 acceptance-condition checker — 一覧用のサムネイル画像。

★経緯（2026-09-15 の実測）
  カタログ画像は**サイト全体を縦に撮った原寸**（例: 1500 x 12391px）。
  表示は 123 x 91px のカードなのに、既定で並ぶ18枚の**展開メモリが 634MB**、
  167枚全部なら 5.8GB あった。メモリに余裕が無いと展開が見送られ、枠だけが残る。
  理恵さんの環境で実際にその状態になった（ブリッジ再起動で復帰）。
  さらに img.onerror が**黙って img を消す**ため、失敗と読み込み中が区別できなかった。

★この checker が守っているもの
  G. 生成の道具があり、原寸を壊さないこと
  B. ブリッジがサムネイルを配信し、取り込み時に作ること（失敗しても登録は止めない）
  U. 両画面が一覧でサムネイルを使い、**無ければ原寸へ戻す**こと
  Z. 拡大は原寸のままであること
  F. 画像を出せなかったときに黙らないこと

  実際の枚数・展開メモリ・フォールバックは tests/test_palette_klk128.py が実ブラウザで見る。

Run: python3 tests/site/check_klk128.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE = io.open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
INDEX = io.open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
CATALOG = io.open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()
TOOL_PATH = os.path.join(ROOT, "tools", "make-catalog-thumbs.py")
TOOL = io.open(TOOL_PATH, encoding="utf-8").read() if os.path.isfile(TOOL_PATH) else ""
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# G. 生成の道具
# ---------------------------------------------------------------------------
check("G1 サムネイル生成ツールがある", bool(TOOL), TOOL_PATH)
check("G2 既存の縮小処理を使い回している（同じ道具を二度書かない）",
      "shrink-catalog-images.py" in TOOL and "def load_shrink" in TOOL, "")
check("G3 ★原寸を書き換えない（出力先は catalog/thumb/ だけ）",
      '"thumb"' in TOOL and "SRC_DIR" in TOOL and "DST_DIR" in TOOL
      and not re.search(r"shrink_one\(\s*src\s*,\s*src", TOOL), "")
check("G4 作り直しの要否を更新時刻で判断する（毎回全部作らない）",
      "def needs_thumb" in TOOL and "getmtime" in TOOL, "")
check("G5 sips が無い環境でも止まらない（fail-soft）",
      "has_sips" in TOOL, "")

# ---------------------------------------------------------------------------
# B. ブリッジ
# ---------------------------------------------------------------------------
check("B1 サムネイルの置き場所を持つ", "catalog_thumb_dir" in BRIDGE, "")
check("B2 ★/catalog/thumb/ を配信する",
      '"/catalog/thumb/"' in BRIDGE and "_serve_catalog_thumb" in BRIDGE, "")
check("B3 配信の検査は原寸と同じ実装を通す（安全確認を二重に書かない）",
      "_serve_catalog_file" in BRIDGE
      and BRIDGE.count("is_safe_catalog_name(name)") >= 1, "")
check("B4 ★取り込み時にサムネイルも作る", "make_thumb_for(dst, catalog_thumb_dir)" in BRIDGE, "")
check("B5 ★作れなくても登録は止めない（無ければ画面が原寸へ戻る）",
      re.search(r"ok, tw = make_thumb_for\(.*?\)\s*\n\s*if not ok:\s*\n\s*print\(", BRIDGE, re.S) is not None, "")

# ---------------------------------------------------------------------------
# U. 画面（一覧はサムネイル・無ければ原寸）
# ---------------------------------------------------------------------------
check("U1 ★生成設定画面の一覧がサムネイルを使う",
      "'/catalog/thumb/' + encodeURIComponent(file)" in INDEX, "")
check("U2 ★生成設定画面が原寸へ戻す（サムネイルが無くても壊れない）",
      "img.dataset.fellBack" in INDEX
      and "img.setAttribute('src', '/catalog/img/' + encodeURIComponent(file));" in INDEX, "")
check("U3 ★実績カタログ画面の一覧がサムネイルを使う",
      "function thumbSrc" in CATALOG and '"/catalog/thumb/"' in CATALOG, "")
check("U4 ★実績カタログ画面が原寸へ戻す",
      "function bindThumbFallback" in CATALOG and "data-full" in CATALOG
      and "bindThumbFallback(grid)" in CATALOG, "")
check("U5 file:// の写しではサムネイルを使わない（写しには入っていない）",
      re.search(r"function thumbSrc[^}]*?if \(!bridgeAlive\) return \"img/\"", CATALOG, re.S) is not None, "")

# ---------------------------------------------------------------------------
# Z. 拡大は原寸
# ---------------------------------------------------------------------------
check("Z1 ★生成設定画面の拡大は原寸",
      "img.setAttribute('src', '/catalog/img/' + encodeURIComponent(file));" in INDEX
      and "host.textContent = label + '（拡大プレビュー）';" in INDEX, "")
check("Z2 ★実績カタログ画面の拡大は原寸（modal は imgSrc のまま）",
      re.search(r"var mImg = src\s*\n\s*\? '<img src=\"' \+ esc\(src\)", INDEX + CATALOG) is not None, "")

# ---------------------------------------------------------------------------
# F. 黙らない
# ---------------------------------------------------------------------------
check("F1 ★出せなかった枚数を画面に出す（黙って消さない）",
      "thumbImgFailures" in INDEX and "件の画像を表示できませんでした" in INDEX, "")
check("F2 描き直すたびに数え直す",
      re.search(r"function renderThumbs\(list, note\) \{[^}]*thumbImgFailures = 0;", INDEX, re.S) is not None, "")

print("=" * 78)
print("KLK-128 一覧用のサムネイル画像 チェック")
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
