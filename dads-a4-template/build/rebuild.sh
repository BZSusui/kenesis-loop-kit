#!/bin/sh
# DADS A4タテ テンプレート: 生成 → 検証 → プレビューを一括実行する。
#
#   sh build/rebuild.sh
#
# 初回は dads-a4-template/.venv を作成して依存を入れる。
# 検証(validate.py)が失敗した場合は終了コード 1 で止まる。配布前に必ず通すこと。
set -e
DIR=$(cd "$(dirname "$0")/.." && pwd)
VENV="$DIR/.venv"

if [ ! -x "$VENV/bin/python" ]; then
  echo "== 仮想環境を作成: $VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -r "$DIR/requirements.txt"
fi
PY="$VENV/bin/python"

echo "== 1/3 pptx を生成"
"$PY" "$DIR/build/build_template.py"

echo
echo "== 2/3 構造検証"
"$PY" "$DIR/build/validate.py"

echo
echo "== 3/3 プレビュー生成"
PPMM=11.81 "$PY" "$DIR/build/render_preview.py" >/dev/null   # 300dpi の preview.pdf
"$PY" "$DIR/build/render_preview.py" >/dev/null               # 152dpi の PNG 群
echo "preview/ を更新しました"

echo
echo "== 完了: $DIR/dist/DADS_A4_Portrait_Template.pptx"
