#!/usr/bin/env python3
"""
KLK-131 acceptance-condition checker — 配布パッケージにサムネイルが入っていない。

★経緯（2026-09-16・パッケージ化の依頼を受けて点検中に発見）
  `make-package.sh --with-catalog` が `catalog/img` と `catalog.json` しか写しておらず、
  KLK-128 で足した `catalog/thumb/` が配布物に入らなかった。
  表示は壊れないが原寸へフォールバックするため、**KLK-128 で直した重さが戻る**
  （167枚で展開メモリ 5.76GB → 0.50GB にしたものが元通りになる）。
  カタログは 220 件・372MB あり、明日 複数名に実際に使ってもらうので直した。

  あわせて、カタログが空の配布物（パッケージB）で参考素材の欄が
  「条件に合う実績がありません。絞り込みを変えてみてください」と出ていた。
  **1件も無いのだから絞り込みを変えても出ない**。初めて使う人が迷うので直した。

★この checker が守っているもの
  P. パッケージがサムネイルを作って入れること・失敗しても止めないこと
  T. 生成ツールが出力先を指定できること（配布物の中で作るために要る）
  E. 空のカタログと「絞り込みに当たらない」を画面が区別すること

Run: python3 tests/site/check_klk131.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG = io.open(os.path.join(ROOT, "tools", "make-package.sh"), encoding="utf-8").read()
TOOL = io.open(os.path.join(ROOT, "tools", "make-catalog-thumbs.py"), encoding="utf-8").read()
INDEX = io.open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# P. パッケージ
# ---------------------------------------------------------------------------
check("P1 ★--with-catalog でサムネイルを作る",
      "make-catalog-thumbs.py" in PKG, "")
check("P2 ★配布用に縮めた画像から作る（リポジトリの thumb を写さない）",
      '--src="$DEST/catalog/img"' in PKG and '--out="$DEST/catalog/thumb"' in PKG, "")
# 失敗しても止めないこと: if/else で受けており、exit していない
_thumb_block = PKG[PKG.find("make-catalog-thumbs.py"):]
_thumb_block = _thumb_block[:_thumb_block.find("\n  fi\n") + 6] if "\n  fi\n" in _thumb_block else _thumb_block[:600]
check("P3 作れなくてもパッケージ作成を止めない",
      "else" in _thumb_block and "一覧は原寸で表示されます" in _thumb_block
      and "exit 1" not in _thumb_block,
      "失敗時の分岐=%s / 中断=%s" % ("あり" if "else" in _thumb_block else "なし",
                                   "あり" if "exit 1" in _thumb_block else "なし"))
check("P4 なぜ要るかを書いている（入れ忘れると重さが戻る）",
      "KLK-128 で直した重さが戻る" in PKG, "")
check("P5 カタログ無しの既定は変えていない（社外秘を既定で含めない）",
      "含めるには --with-catalog" in PKG, "")

# ---------------------------------------------------------------------------
# T. 生成ツール
# ---------------------------------------------------------------------------
check("T1 ★--src / --out を受け取れる",
      "def parse_args(" in TOOL and '--src=' in TOOL and '--out=' in TOOL, "")
check("T2 既定は従来どおり catalog/img → catalog/thumb",
      "src, dst = SRC_DIR, DST_DIR" in TOOL, "")
check("T3 引数の読み取りが純粋関数（テストから突ける）",
      re.search(r"def parse_args\(argv\):(?:(?!\ndef ).)*return src, dst, width, quality, force",
                TOOL, re.S) is not None, "")

# ---------------------------------------------------------------------------
# E. 空のカタログの見せ方
# ---------------------------------------------------------------------------
check("E1 ★「まだ空」と「絞り込みに当たらない」を区別している",
      "catalogEntries.length === 0" in INDEX
      and "実績カタログはまだ空です" in INDEX, "")
check("E2 空のときに次の一歩を示している（取り込みへ誘導）",
      "から画像を取り込むと、ここに並びます" in INDEX, "")
check("E3 絞り込みで0件のときの案内は残っている",
      "絞り込みを「すべての実績」に変えてみてください" in INDEX, "")

print("=" * 78)
print("KLK-131 配布パッケージのサムネイルと空カタログの案内 チェック")
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
