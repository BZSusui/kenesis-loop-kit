@echo off
rem 起動.bat - ローカルブリッジ ワンクリック起動 (KLK-070 / Windows)
rem ★KLK-105: フォルダを開いてすぐ押せるよう**最上位**へ置く（旧: draft-gen\ 配下）。
rem macOS 版は 起動.command。中身は同じことをしている。
rem ★このファイルは CP932(Shift_JIS) + CRLF で保存すること（KLK-132）。
rem   UTF-8 や LF で保存し直すと、Windows でダブルクリックしても起動しなくなる。
rem   検査: python3 tests/site/check_klk132.py
setlocal

rem ★KLK-134: ネットワーク上の場所（\\サーバー名\... や \\wsl.localhost\...）から起動された場合、
rem   cmd.exe はそこをカレントフォルダにできない。cd より**前**に見て、理由の分かる案内を出す。
rem   （後ろに置くと「移動できませんでした」としか出ず、原因にたどり着けない）
set "KLK_HERE=%~dp0"
if "%KLK_HERE:~0,2%"=="\\" (
  echo 【エラー】ネットワーク上の場所から起動されています。
  echo 場所: %KLK_HERE%
  echo Windows では、\\ で始まる場所のファイルをダブルクリックしても起動できません。
  echo 対処1: このフォルダを C:\ の下（デスクトップなど）へコピーしてから起動してください。
  echo 対処2: 共有フォルダなら、ドライブ文字（Z: など）を割り当ててから開いてください。
  echo 対処3: WSL の中に置いている場合は、この bat を使わず WSL のターミナルで次を実行してください。
  echo         python3 draft-gen/bridge.py
  pause
  exit /b 1
)

rem このバッチの場所を基準にリポジトリのルートへ移動する（起動.bat はリポジトリ直下）
cd /d "%~dp0" || (
  echo 【エラー】このフォルダへ移動できませんでした。
  echo 場所: %KLK_HERE%
  echo フォルダを C:\ の下（デスクトップなど）へコピーしてからお試しください。
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
  echo 確認: コマンドプロンプトで python --version が出ればOKです。
  pause
  exit /b 1
)

rem --- Claude Code を探す（生成時に呼び出すため必須）---
rem ★KLK-133: PATH だけに頼らない。インストーラは %USERPROFILE%\.local\bin へ置くが、
rem   そこが PATH に入っていない環境がある（実際に起動できなかった報告あり）。
rem   見つけた場所は **このウィンドウの PATH にだけ** 足す（setlocal の中なので
rem   利用者の環境変数は書き換えない）。入れ子の括弧は使わない（cmd の変数展開の落とし穴を避ける）。
where claude >nul 2>&1
if not errorlevel 1 goto claude_ok
if exist "%USERPROFILE%\.local\bin\claude.exe" set "PATH=%PATH%;%USERPROFILE%\.local\bin"
if exist "%APPDATA%\npm\claude.cmd" set "PATH=%PATH%;%APPDATA%\npm"
if exist "%LOCALAPPDATA%\Programs\claude\claude.exe" set "PATH=%PATH%;%LOCALAPPDATA%\Programs\claude"
where claude >nul 2>&1
if not errorlevel 1 goto claude_ok
echo 【エラー】claude（Claude Code）が見つかりません。
echo ブリッジは生成時に claude を呼び出すため、これが無いと生成が失敗します。
echo 探した場所:
echo   ・PATH の中
echo   ・%USERPROFILE%\.local\bin\claude.exe
echo   ・%APPDATA%\npm\claude.cmd
echo   ・%LOCALAPPDATA%\Programs\claude\claude.exe
echo 対処: Claude Code をインストールし、コマンドプロンプトで claude --version が出ることを確認してください。
pause
exit /b 1
:claude_ok

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
