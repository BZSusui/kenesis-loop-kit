@echo off
rem draft-gen\起動.bat - ローカルブリッジ ワンクリック起動 (KLK-070 / Windows)
rem macOS 版は 起動.command。中身は同じことをしている。
chcp 65001 > nul
setlocal

rem このバッチの場所を基準にリポジトリのルートへ移動する（起動.bat は draft-gen\ 配下）
cd /d "%~dp0.." || (
  echo 【エラー】リポジトリのフォルダへ移動できませんでした。
  pause
  exit /b 1
)

rem --- Python を探す（Windows の実情に合わせ py -3 → python の順。python3 はほぼ無い）---
set "PYEXE="
py -3 --version >nul 2>&1 && set "PYEXE=py -3"
if not defined PYEXE (
  python --version >nul 2>&1 && set "PYEXE=python"
)
if not defined PYEXE (
  python3 --version >nul 2>&1 && set "PYEXE=python3"
)
if not defined PYEXE (
  echo 【エラー】Python 3 が見つかりません。
  echo 対処: https://www.python.org/downloads/ から Python 3 をインストールしてください。
  echo       インストール時に「Add Python to PATH」に必ずチェックを入れてください。
  echo 確認: コマンドプロンプトで python --version が表示されればOKです。
  pause
  exit /b 1
)

rem --- Claude Code を探す（生成時に呼び出すため必須）---
where claude >nul 2>&1
if errorlevel 1 (
  echo 【エラー】claude（Claude Code）が見つかりません。
  echo ブリッジは生成時に claude を呼び出すため、これが無いと生成が失敗します。
  echo 対処: Claude Code をインストールし、コマンドプロンプトで claude --version が出ることを確認してください。
  pause
  exit /b 1
)

echo ローカルブリッジを起動します。設定画面が自動でブラウザに開きます。
echo 停止するには、このウィンドウで Ctrl+C を押してください。
rem ブリッジ本体を起動（設定画面をブラウザで開くのはブリッジ側の役割）
%PYEXE% draft-gen\bridge.py

rem 異常終了したときにウィンドウが即閉じないようにする
if errorlevel 1 (
  echo.
  echo ブリッジが終了しました（エラー）。上のメッセージをご確認ください。
  pause
)
endlocal
