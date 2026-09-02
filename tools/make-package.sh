#!/bin/bash
# tools/make-package.sh — 配布用フォルダを組み立てる (KLK-069)
#
# 配布方式: Git ではなく**フォルダを手渡し**する。受け取った人はフォルダを好きな場所へ置き、
# draft-gen/起動.command をダブルクリックするだけで動く。
#
# なぜスクリプトにするか:
#   配布のたびに「どのフォルダを含めるか」を人が判断すると必ずどこかで間違える。
#   特に **含めてはいけないもの**（mockups/=案件名を含む生成物、tickets/active=作業ログ、
#   catalog/=社外秘）を うっかり cp -r で丸ごと持っていく事故は起きやすい。
#
# ★カタログ（社外秘・第三者著作物）は既定で含めない。含めるには --with-catalog を明示すること。
#
# 使い方:
#   tools/make-package.sh [出力先] [--with-catalog] [--with-tests]
#
#   出力先を省略すると ~/Desktop/kenesis-loop-kit-package へ書き出す。
#
set -u

usage() {
  cat <<'USAGE'
使い方: tools/make-package.sh [出力先] [--with-catalog] [--with-tests]

  出力先            配布フォルダを作る場所（省略時: ~/Desktop/kenesis-loop-kit-package）
  --with-catalog    実績カタログ（catalog/img と catalog.json）を含める
                    ★社外秘・第三者著作物を含みます。配布可否の確認を済ませてから使ってください
  --with-tests      テスト一式（tests/）を含める。開発する人へ渡すとき用
  -h, --help        この説明を表示

例:
  tools/make-package.sh                                   # 本体のみ（約2MB）
  tools/make-package.sh ~/Desktop/配布用 --with-tests      # 開発者向け
  tools/make-package.sh ~/Desktop/配布用 --with-catalog    # カタログ込み（約347MB）
USAGE
}

DEST=""
WITH_CATALOG=0
WITH_TESTS=0
for arg in "$@"; do
  case "$arg" in
    --with-catalog) WITH_CATALOG=1 ;;
    --with-tests)   WITH_TESTS=1 ;;
    -h|--help)      usage; exit 0 ;;
    -*)             echo "【エラー】不明なオプション: $arg" >&2; usage; exit 1 ;;
    *)              DEST="$arg" ;;
  esac
done
[ -n "$DEST" ] || DEST="$HOME/Desktop/kenesis-loop-kit-package"

# スクリプトの位置からリポジトリルートを決める（どこから呼んでも動く）
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || { echo "【エラー】リポジトリのルートへ移動できませんでした。" >&2; exit 1; }

if [ -e "$DEST" ]; then
  echo "【エラー】出力先が既に存在します: $DEST" >&2
  echo "         別の名前を指定するか、先に移動・削除してください（誤って上書きしないための停止です）。" >&2
  exit 1
fi

echo "配布フォルダを組み立てます"
echo "  元: $ROOT"
echo "  先: $DEST"
echo

mkdir -p "$DEST" || { echo "【エラー】出力先を作成できませんでした。" >&2; exit 1; }

# ---- 必須（動作に要るもの） -------------------------------------------------
# KLK-071: samples/ は「まず開いてもらう見本」。ダミー案件名の生成物のみで機密は無い（既定で含める）
for d in draft-gen palette .claude agents docs samples; do
  [ -d "$d" ] && cp -R "$d" "$DEST/" && echo "  含めた: $d/"
done
for f in README.md CLAUDE.md CHANGELOG.md LICENSE; do
  [ -f "$f" ] && cp "$f" "$DEST/" && echo "  含めた: $f"
done

# ---- チケットの雛形だけ（作業ログは含めない） -------------------------------
if [ -d tickets/Templates ]; then
  mkdir -p "$DEST/tickets/Templates"
  cp tickets/Templates/* "$DEST/tickets/Templates/" 2>/dev/null
  echo "  含めた: tickets/Templates/（雛形のみ・作業中のチケットは含めない）"
fi

# ---- 実行時に使う空フォルダ -------------------------------------------------
mkdir -p "$DEST/mockups" "$DEST/catalog/.pending" "$DEST/tickets/active" "$DEST/tickets/done"
touch "$DEST/tickets/active/.gitkeep" "$DEST/tickets/done/.gitkeep"
echo "  作った: mockups/ catalog/.pending/ tickets/active/ tickets/done/（いずれも空）"

# ---- 任意: テスト -----------------------------------------------------------
if [ "$WITH_TESTS" -eq 1 ]; then
  cp -R tests "$DEST/" && echo "  含めた: tests/（--with-tests）"
else
  echo "  含めない: tests/（開発する人へ渡すなら --with-tests）"
fi

# ---- 任意: 実績カタログ（社外秘） -------------------------------------------
if [ "$WITH_CATALOG" -eq 1 ]; then
  [ -d catalog/img ] && cp -R catalog/img "$DEST/catalog/"
  [ -f catalog/catalog.json ] && cp catalog/catalog.json "$DEST/catalog/"
  echo "  含めた: catalog/img/ catalog/catalog.json（--with-catalog）"
else
  echo "  含めない: catalog/img/ catalog/catalog.json（社外秘。含めるには --with-catalog）"
fi

# ---- 実行権限を戻す（cp で失われる環境があるため） --------------------------
[ -f "$DEST/draft-gen/起動.command" ] && chmod +x "$DEST/draft-gen/起動.command"
[ -f "$DEST/tools/make-package.sh" ] && chmod +x "$DEST/tools/make-package.sh"

echo
echo "  含めない: mockups/ の中身（生成物・案件名を含む）"
echo "  含めない: tickets/active・done の中身（作業ログ・内部情報）"
echo "  含めない: .git/（履歴。過去の社外秘が入る余地も断つ）"
echo
echo "完成: $DEST"
echo "  サイズ: $(du -sh "$DEST" 2>/dev/null | cut -f1)"
echo
echo "渡した相手には次を伝えてください:"
echo "  1. このフォルダを好きな場所（デスクトップ等）に置く"
echo "  2. draft-gen/起動.command をダブルクリック"
echo "  3. 使い方は README.md"

if [ "$WITH_CATALOG" -eq 1 ]; then
  echo
  echo "============================================================"
  echo "  ★ この配布物には実績カタログ（社外秘・第三者著作物）が"
  echo "     含まれています。"
  echo "     ・渡す相手と配布可否の確認が済んでいるかご確認ください"
  echo "     ・誰に渡したかを記録しておいてください"
  echo "     ・受け取った人にも取り扱いの注意（README 末尾）を伝えてください"
  echo "============================================================"
fi
