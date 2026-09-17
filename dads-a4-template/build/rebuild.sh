#!/bin/sh
# DADS 印刷テンプレート: 生成 → 検証 → プレビューを一括実行する。
#
#   sh build/rebuild.sh
#
# A4タテ / B5タテ（標準）/ B5タテ（コンパクト）の3種を作る。
# 初回は dads-a4-template/.venv を作成して依存を入れる。
# 検証(validate.py)・あふれ検査(overflow.py)・回帰テスト(regress.py)のいずれかが
# 失敗した場合は終了コード 1 で止まる。
# 配布前に必ず通すこと。
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

# プロファイル名:出力pptx名:プレビュー出力先
# A4 のプレビューは preview/ 直下（DADS-001 の成果物パスを変えないため）
PROFILES="a4:DADS_A4_Portrait_Template:.
b5:DADS_B5_Portrait_Template:b5
b5-compact:DADS_B5_Portrait_Compact_Template:b5-compact"

n=1
echo "$PROFILES" | while IFS=: read -r prof name prev; do
  echo "== $n/3 $prof を生成・検証・プレビュー"
  PPTX="$DIR/dist/$name.pptx"
  PREV="$DIR/preview/$prev"
  DADS_PROFILE="$prof" "$PY" "$DIR/build/build_template.py" "$PPTX"
  echo
  "$PY" "$DIR/build/validate.py" "$PPTX"
  mkdir -p "$PREV"
  PPMM=11.81 "$PY" "$DIR/build/render_preview.py" "$PPTX" "$PREV" >/dev/null  # 300dpi の preview.pdf
  "$PY" "$DIR/build/render_preview.py" "$PPTX" "$PREV" >/dev/null             # 152dpi の PNG 群
  echo "preview/$prev を更新しました"
  "$PY" "$DIR/build/overflow.py" "$PPTX"
  echo
  n=$((n + 1))
done

echo "== A4の回帰テスト"
"$PY" "$DIR/build/regress.py"

echo
echo "== 完了"
ls -1 "$DIR"/dist/*.pptx
