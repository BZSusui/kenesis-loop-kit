#!/bin/bash
# draft-gen/起動.command — ローカルブリッジ ワンクリック起動 (KLK-014 / macOS)
# ダブルクリックで開けない場合は、ターミナルで一度だけ次を実行してください:
#   chmod +x draft-gen/起動.command

# このスクリプトの場所を基準にリポジトリのルートへ移動する（起動.command は draft-gen/ 配下）
cd "$(dirname "$0")/.." || { echo "リポジトリのフォルダへ移動できませんでした。" >&2; exit 1; }

# 必須ツールの存在チェック（黙って失敗しない＝受入条件2）
if ! command -v python3 >/dev/null 2>&1; then
  echo "【エラー】python3 が見つかりません。" >&2
  echo "対処: macOS に Python 3 を入れてください（ターミナルで xcode-select --install など）。" >&2
  echo "確認: ターミナルで python3 --version が表示されればOKです。" >&2
  exit 1
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "【エラー】claude（Claude Code）が見つかりません。" >&2
  echo "ブリッジは生成時に claude を呼び出すため、これが無いと生成が失敗します。" >&2
  echo "対処: Claude Code をインストールし、ターミナルで claude --version が出ることを確認してください。" >&2
  exit 1
fi

echo "ローカルブリッジを起動します。設定画面が自動でブラウザに開きます。"
echo "停止するには、このウィンドウで Ctrl+C を押してください。"
# ブリッジ本体を起動（設定画面をブラウザで開くのはブリッジ側の役割＝ここで open はしない）
exec python3 draft-gen/bridge.py
