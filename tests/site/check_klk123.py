#!/usr/bin/env python3
"""
KLK-123 acceptance-condition checker — カタログ登録時に画像を自動で軽くする。

★経緯
  理恵さんの明示的な要望（引き継ぎ書の保留中の宿題）:
    「カタログ登録時の自動リサイズ。`tools/shrink-catalog-images.py` の `shrink_one` を
      `/catalog-import` 時に適用する形」
  KLK-110 で「167枚 773MB → 217MB」と**後からまとめて**縮めた。
  取り込み時に揃えておけば、その作業が二度と要らない。

★実測（2026-09-14）
  `catalog/img/` は**原本のまま**だった（810MB / 167枚 / PNG 140枚 / 1600px超が21枚）。
  KLK-110 が縮めていたのは配布パッケージ内のコピーだけである。

★この checker が守っているもの
  S. 取り込みの確定後に軽量化を通すこと。**画像移動と catalog.json 保存の間**に置く
  F. ★失敗しても登録を止めないこと（画像が大きいのは、登録できないことより軽い問題）
  P. 純関数が壊れた入力で例外を投げないこと
  D. 何が起きるか（原本は残らない）が規約とスキルに書かれていること

Run: python3 tests/site/check_klk123.py
"""
import importlib.util
import io
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = io.open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
RULES = io.open(os.path.join(ROOT, ".claude", "skills", "catalog-import",
                             "templates", "CATALOG_RULES.md"), encoding="utf-8").read()
SKILL = io.open(os.path.join(ROOT, ".claude", "skills", "catalog-import", "SKILL.md"),
                encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "bridge_klk123", os.path.join(ROOT, "draft-gen", "bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


b = load_bridge()

# ---------------------------------------------------------------------------
# S. 組み込み位置
# ---------------------------------------------------------------------------
check("S1 純関数 shrink_registered_image がある",
      hasattr(b, "shrink_registered_image"), "")

seg = SRC[SRC.index("def _catalog_commit"):SRC.index("def _catalog_delete")]
check("S2 取り込みの確定処理から呼んでいる",
      "shrink_registered_image(dst)" in seg, "")

i_move = seg.index("shutil.move(src, dst)")
i_shrink = seg.index("shrink_registered_image(dst)")
i_save = seg.index("os.replace(tmp, catalog_json_path)")
check("S3 ★画像移動のあと・catalog.json 保存の前に置く",
      i_move < i_shrink < i_save,
      "移動=%d 軽量化=%d 保存=%d" % (i_move, i_shrink, i_save))

check("S4 tools/shrink-catalog-images.py を使う（縮め方を二重に書かない）",
      "shrink-catalog-images.py" in SRC and "shrink_one" in SRC,
      "参照=%s" % ("shrink-catalog-images.py" in SRC))

check("S5 モジュール先頭で兄弟を import しない流儀を守っている（関数内 import）",
      "\nimport importlib.util\n" not in SRC[:SRC.index("def ")],
      "先頭 import なし=%s" % ("\nimport importlib.util\n" not in SRC[:SRC.index("def ")]))

# ---------------------------------------------------------------------------
# F. 失敗しても登録を止めない
# ---------------------------------------------------------------------------
check("F1 軽量化の失敗で登録処理を中断しない（例外を投げない作りである）",
      "return (size, size, \"軽量化できませんでした" in SRC,
      "握って戻す=%s" % ("軽量化できませんでした" in SRC))

check("F2 ★軽量化は catalog.json 保存の前にあるが、失敗してもそこで return しない",
      "shrink_registered_image(dst)" in seg
      and "self._json(500" not in seg[i_shrink:i_save],
      "軽量化〜保存の間に中断なし=%s" % ("self._json(500" not in seg[i_shrink:i_save]))

# ---------------------------------------------------------------------------
# P. 純関数の頑丈さ（妨害注入）
# ---------------------------------------------------------------------------
n, a, why = b.shrink_registered_image("/no/such/file.png")
check("P1 存在しないファイルでも例外を投げない", n == 0 and a == 0, "%s" % why)

with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
    fh.write(b"not an image")
    bogus = fh.name
try:
    n2, a2, why2 = b.shrink_registered_image(bogus)
    check("P2 画像でないファイルでも例外を投げず、サイズも壊さない",
          n2 == a2 == os.path.getsize(bogus), "%s" % why2)
    n3, a3, why3 = b.shrink_registered_image(bogus, tool_path="/no/such/tool.py")
    check("P3 軽量化ツールが無くても例外を投げない", n3 == a3, "%s" % why3)
    leftovers = [f for f in os.listdir(os.path.dirname(bogus))
                 if f.startswith(os.path.basename(bogus)) and f.endswith(".shrink.tmp")]
    check("P4 一時ファイルを残さない", not leftovers, "残骸=%s" % (leftovers or "なし"))
finally:
    os.unlink(bogus)

# ---------------------------------------------------------------------------
# D. 書かれていること
# ---------------------------------------------------------------------------
check("D1 規約に「取り込み時に軽くする」と書いてある",
      "取り込み時" in RULES and "軽く" in RULES, "")
check("D2 ★原本は残らないことが書いてある（後から元の解像度へ戻せない）",
      "原本は残りません" in RULES, "明記=%s" % ("原本は残りません" in RULES))
check("D3 スキルにも記載がある", "自動で軽く" in SKILL, "")

print("=" * 78)
print("KLK-123 カタログ登録時の自動リサイズ チェック")
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
