#!/bin/bash
# tools/make-package.sh — 配布用フォルダを組み立てる (KLK-069)
#
# 配布方式: Git ではなく**フォルダを手渡し**する。受け取った人はフォルダを好きな場所へ置き、
# 起動.command をダブルクリックするだけで動く。
#
# なぜスクリプトにするか:
#   配布のたびに「どのフォルダを含めるか」を人が判断すると必ずどこかで間違える。
#   特に **含めてはいけないもの**（mockups/=案件名を含む生成物、tickets/active=作業ログ、
#   catalog/=社外秘）を うっかり cp -r で丸ごと持っていく事故は起きやすい。
#
# ★カタログ（社外秘・第三者著作物）は既定で含めない。含めるには --with-catalog を明示すること。
#
# ★デザインシステム（DADS）も既定で含めない (KLK-115)。
#   モック生成システムとは別案件なので、配布物には入れない（理恵さんの指示・2026-09-09）。
#   docs/design-system/ と デザインシステムの使い方.html を外すだけでは足りない。
#   CLAUDE.md・agents/×3・README.md・CHANGELOG.md が DADS を参照しており、
#   そのままだと **参照先が存在しない記述** が配布物に残るため、
#   `<!-- DADS:BEGIN/END -->` で囲んだ区間を tools/strip-dads-sections.py で取り除く。
#   リポジトリ本体からは消さない（リポジトリは分割しない・2026-09-10 の判断）。
#
# 使い方:
#   tools/make-package.sh [出力先] [--with-catalog] [--with-tests] [--with-design-system]
#
#   出力先を省略すると ~/Desktop/kenesis-loop-kit-package へ書き出す。
#
set -u

usage() {
  cat <<'USAGE'
使い方: tools/make-package.sh [出力先] [--with-catalog] [--with-tests] [--with-design-system]

  出力先                 配布フォルダを作る場所（省略時: ~/Desktop/kenesis-loop-kit-package）
  --with-catalog         実績カタログ（catalog/img と catalog.json）を含める
                         ★社外秘・第三者著作物を含みます。配布可否の確認を済ませてから使ってください
  --with-tests           テスト一式（tests/）を含める。開発する人へ渡すとき用
  --with-design-system   デジタル庁デザインシステム（DADS）を含める
                         既定では含めません。モック生成システムとは別案件のため
  -h, --help             この説明を表示

例:
  tools/make-package.sh                                   # 本体のみ（約1MB・DADSなし）
  tools/make-package.sh ~/Desktop/配布用 --with-tests      # 開発者向け
  tools/make-package.sh ~/Desktop/配布用 --with-catalog    # カタログ込み（約347MB）
USAGE
}

DEST=""
WITH_CATALOG=0
WITH_TESTS=0
WITH_DESIGN_SYSTEM=0
for arg in "$@"; do
  case "$arg" in
    --with-catalog)       WITH_CATALOG=1 ;;
    --with-tests)         WITH_TESTS=1 ;;
    --with-design-system) WITH_DESIGN_SYSTEM=1 ;;
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
# ★ここは allowlist（列挙したものだけ入る）。リポジトリ直下に新しいフォルダが増えても
#   ここへ足さない限り配布物には入らない。別案件（デザインシステム）の成果物が
#   紛れ込まないのはこの性質による（check_klk115 が実ビルドで確認する）。
for d in draft-gen palette .claude agents docs samples; do
  [ -d "$d" ] && cp -R "$d" "$DEST/" && echo "  含めた: $d/"
done
for f in 起動.command 起動.bat はじめにお読みください.txt README.md 使い方マニュアル.html CLAUDE.md CHANGELOG.md LICENSE; do
  [ -f "$f" ] && cp "$f" "$DEST/" && echo "  含めた: $f"
done

# ---- デザインシステム（DADS）: 既定では外す (KLK-115) -----------------------
if [ "$WITH_DESIGN_SYSTEM" -eq 1 ]; then
  [ -f デザインシステムの使い方.html ] && cp デザインシステムの使い方.html "$DEST/" \
    && echo "  含めた: デザインシステムの使い方.html（--with-design-system）"
  echo "  含めた: docs/design-system/（--with-design-system）"
else
  rm -rf "$DEST/docs/design-system"
  echo "  含めない: docs/design-system/ と デザインシステムの使い方.html"
  echo "            （別案件のため。含めるには --with-design-system）"
fi

# ---- 設計書はこのシステムのものだけ (KLK-135) -------------------------------
# ★docs/ はディレクトリごと写すので、docs/designs/ の中身は素通りする。
#   チケット番号と docs/designs/ は別案件（デザインシステム）と共有しており、
#   向こうが設計書を足すたびに配布物へ混ざる（実際 DADS-002/003/005 が混入していた）。
#   リポジトリ直下と同じく、ここも **allowlist**（残すものを列挙）で絞る。
#   残すもの: KLK-*.md（このシステムの設計書）・README.md・_TEMPLATE.md
if [ -d "$DEST/docs/designs" ]; then
  _dropped=0
  for f in "$DEST"/docs/designs/*; do
    [ -e "$f" ] || continue
    case "$(basename "$f")" in
      KLK-*.md|README.md|_TEMPLATE.md) ;;
      *) rm -rf "$f"; _dropped=$((_dropped + 1)) ;;
    esac
  done
  echo "  絞った: docs/designs/（KLK-* のみ / 別案件の設計書 ${_dropped} 件を外した）"
fi

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
  # ★配布用に画像を軽くする（KLK-110）。**元画像は catalog/img/ に温存**する。
  #   実測: 167枚 773MB → 217MB（72%減・約50秒）。
  #   767MB のままだとメール添付は不可で、共有フォルダ経由が前提になる。
  #   横幅1600px を上限にし、PNG は JPEG へ入れ替える（容量の94%が PNG だった）。
  #   ★「長辺」ではなく「横幅」基準。実績画像は縦長のフルページで、
  #     167枚のうち118枚が縦が横の3倍以上（最大17.2倍）。長辺で揃えると
  #     横幅が93〜194px まで潰れて実績が読めなくなる。
  if [ -d catalog/img ]; then
    echo "  カタログ画像を配布用に軽くしています（元画像は触りません）…"
    if python3 tools/shrink-catalog-images.py "$DEST/catalog/img" --src=catalog/img; then
      :
    else
      echo "  【注意】軽量化に失敗したため、元のサイズでコピーします"
      cp -R catalog/img "$DEST/catalog/"
    fi
  fi
  [ -f catalog/catalog.json ] && cp catalog/catalog.json "$DEST/catalog/"
  # ★一覧用のサムネイルも入れる（KLK-131）。
  #   入れ忘れると配布物では一覧が原寸へフォールバックし、KLK-128 で直した重さが戻る
  #   （167枚で展開メモリ 5.76GB → 0.50GB だったものが元通りになる）。
  #   ★リポジトリの catalog/thumb/ を写すのではなく、**配布用に縮めた画像から作り直す**。
  #     配布用画像はさらに小さいので、そこから作るほうが整合する。
  #   作れなくてもパッケージ作成は止めない（画面が原寸へ戻るだけで壊れない）。
  if [ -d "$DEST/catalog/img" ]; then
    echo "  一覧用のサムネイルを作っています…"
    if python3 tools/make-catalog-thumbs.py --src="$DEST/catalog/img" --out="$DEST/catalog/thumb"; then
      echo "  含めた: catalog/thumb/（一覧用）"
    else
      echo "  【注意】サムネイルを作れませんでした（一覧は原寸で表示されます）"
    fi
  fi
  echo "  含めた: catalog/img/ catalog/catalog.json（--with-catalog）"
  # README を「空から始める」前提から「最初から入っている」前提へ差し替える。
  # リポジトリの README.md は B（カタログなし）の内容のまま＝普段見る README が正。
  # 失敗したら組み立てを中止する。README が「カタログは空です」と言ったまま
  # 345MB の社外秘を配るのが一番まずいので、黙って続けない。
  if python3 tools/readme_for_catalog.py "$DEST/README.md" "$ROOT/catalog/catalog.json"; then
    echo "  書き換え: README.md（カタログ同梱版の案内・取り扱いの注意）"
  else
    echo "【エラー】README.md をカタログ同梱版へ書き換えられませんでした。" >&2
    echo "         中途半端な配布物を残さないため、$DEST を削除して中止します。" >&2
    rm -rf "$DEST"
    exit 1
  fi
else
  echo "  含めない: catalog/img/ catalog/catalog.json（社外秘。含めるには --with-catalog）"
fi

# ---- DADS の記述を配布物から取り除く (KLK-115) ------------------------------
# ★ファイルを外すだけでは終わらない。CLAUDE.md と agents/×3 が docs/design-system/ を
#   参照しているので、記述が残ると「書いてあるのに無いファイル」を探させることになる。
#   カタログ版 README の差し替え（上）より **後** に実行する。差し替え後の実物を処理する。
if [ "$WITH_DESIGN_SYSTEM" -eq 0 ]; then
  STRIP_TARGETS=""
  for rel in CLAUDE.md README.md CHANGELOG.md \
             agents/architect.md agents/implementer.md agents/reviewer.md; do
    [ -f "$DEST/$rel" ] && STRIP_TARGETS="$STRIP_TARGETS $DEST/$rel"
  done
  # shellcheck disable=SC2086
  if python3 tools/strip-dads-sections.py $STRIP_TARGETS; then
    echo "  取り除いた: 各文書のデザインシステム関連の記述"
  else
    # マーカーの対応が崩れている等。中途半端な配布物を残さない。
    echo "【エラー】デザインシステムの記述を取り除けませんでした。" >&2
    echo "         参照先の無い記述が残った配布物を作らないため、$DEST を削除して中止します。" >&2
    rm -rf "$DEST"
    exit 1
  fi
fi

# ---- Finder のメタデータを落とす --------------------------------------------
# .DS_Store は「そのフォルダに以前あったファイル名」を保持しうる。
# 削除済みの案件フォルダ名が配布物に残る余地を断つ。
DS_N=$(find "$DEST" -name '.DS_Store' | wc -l | tr -d ' ')
find "$DEST" -name '.DS_Store' -delete 2>/dev/null
echo "  取り除いた: .DS_Store $DS_N 個（Finder のメタデータ）"

# ---- 実行権限を戻す（cp で失われる環境があるため） --------------------------
[ -f "$DEST/起動.command" ] && chmod +x "$DEST/起動.command"

# ---- カスタムアイコンを付け直す（KLK-106）----------------------------------
# ★毎回ここで付ける。作業ツリーのアイコンを当てにしない。
#   Git は**リソースフォークを保存しない**ので、clone した環境では
#   アイコンも実行ビットも失われる（実測で確認：clone 直後は両方なし）。
#   元データ（SVG）から組み立てれば、どの環境で作っても同じものが出る。
if [ -f "$DEST/起動.command" ] && [ -f assets/icons/起動アイコン.svg ]; then
  if python3 tools/set-mac-icon.py assets/icons/起動アイコン.svg "$DEST/起動.command" >/dev/null 2>&1; then
    echo "  アイコン: 起動.command に設定しました"
  else
    # macOS 以外や道具が無い環境では付かない。**それだけで配布を止めない**（見た目の話）
    echo "  アイコン: 設定できませんでした（macOS 以外では付きません。動作には影響しません）"
  fi
fi
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
echo "  2. まず はじめにお読みください.txt を開く（セットアップ手順）"
echo "  3. 起動.command（Windows は 起動.bat）をダブルクリック"
echo "  4. 画面ごとの使い方は 使い方マニュアル.html（ダブルクリックで開く）"
echo "  5. 困ったときは README.md"
echo ""
echo "★ZIP にして渡すときは Finder の「圧縮」（またはターミナルで下記）を使ってください。"
echo "   起動.command のアイコンはリソースフォークに入っており、"
echo "   'zip -r' で固めると**アイコンが消えます**（実測で確認済み・KLK-106）。"
echo ""
echo "   ditto -c -k --sequesterRsrc --keepParent \"$DEST\" \"$DEST.zip\""
echo ""
echo "   受け取った方は Finder でダブルクリックして展開してください"
echo "   （'unzip' コマンドではアイコンが復元されません）。"

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
