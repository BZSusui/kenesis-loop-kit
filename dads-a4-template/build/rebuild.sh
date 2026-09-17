#!/bin/sh
# DADS 印刷テンプレート: 生成 → 検証 → プレビューを一括実行する。
#
#   sh build/rebuild.sh
#
# DADS採用書体版3種（A4 / B5標準 / B5コンパクト）と、
# 標準搭載フォント版3種（同じ判型・BIZ UDPGothic + Arial）の計6種を作る。
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

# バイトコードキャッシュを作らない。
# spec.py を編集してもファイルサイズが変わらない場合（例: MARGIN_U=8 -> 7）、
# Python が mtime とサイズで「変更なし」と誤判定して古い __pycache__ を使い、
# 古い定義のままビルドされることがある（DADS-004 で実際に起きた）。
export PYTHONDONTWRITEBYTECODE=1
rm -rf "$DIR/build/__pycache__"

# プロファイル名:出力pptx（distからの相対）:プレビュー出力先（previewからの相対）
# DADS採用書体版(Noto Sans JP)の出力先は DADS-001/002 のパスを変えない。
# 標準搭載フォント版は stdfont/ 配下に分ける（DADS-005・人間の要件）。
PROFILES="a4:DADS_A4_Portrait_Template:.
b5:DADS_B5_Portrait_Template:b5
b5-compact:DADS_B5_Portrait_Compact_Template:b5-compact
a4-std:stdfont/STD_A4_Portrait_Template:stdfont/a4
b5-std:stdfont/STD_B5_Portrait_Template:stdfont/b5
b5-compact-std:stdfont/STD_B5_Portrait_Compact_Template:stdfont/b5-compact"

n=1
echo "$PROFILES" | while IFS=: read -r prof name prev; do
  echo "== $n/6 $prof を生成・検証・プレビュー"
  PPTX="$DIR/dist/$name.pptx"
  PREV="$DIR/preview/$prev"
  mkdir -p "$(dirname "$PPTX")"
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
