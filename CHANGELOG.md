# CHANGELOG

Kenesis Loop Kitのすべての変更はこのファイルに記録されます。
フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に準拠し、
バージョン管理は [Semantic Versioning](https://semver.org/lang/ja/) に従います。

---

## [Unreleased]

<!-- KLK-090: KLK-061〜095 の34件は、受け取った人が読む文書として**主題ごとにまとめて**記録する。
     1件ずつ並べると内部の経緯が主になり、「このツールで何ができるか」が読み取れなくなるため。 -->

### Added（KLK-061〜095・2026-09-02〜09-05）

**ページ構成を自由に組める（KLK-086〜089・091〜094）**
- 「④ 本文コンテンツ構成」がチェックボックスから**ページ構成リスト**へ。載せるセクションを
  **上から順に並べ**、**同じセクションを複数**置ける（例: MENU を「ランチ」「ディナー」で2つ）
- 並べ替えは **`⠿` を掴んでドラッグ**、または ↑↓ ボタン
- 行ごとの「設定」で**見出し・リード文・レイアウト型・詳細ページ誘導ボタン**を指定できる。
  型を選ぶと3案ともその型になり、選ばなければ案ごとに振り分ける
- 並び順を指定すると**3案とも同じ並び**になる（案の違いは配色とレイアウト型で出る）
- 置ける数は本文あわせて12個・同じセクションは3個まで（ACCESS/CONTACT/SEARCH は1個）
- 入力例をセクションごとに用意（PRICE なら「料金プラン」、VOICE なら「お客様の声」）
- 参考サムネイルは既定18件で畳み、「さらに表示する」で開く（**選択済みは畳んでも隠れない**）

**生成後にセクションを作り直せる・型を入れ替えられる（KLK-078〜080・092）**
- 比較画面の 🔄 で、**そのページに実際にあるセクション**を選んで作り直せる
  （以前は6種の固定リストで、実ページと食い違っていた）
- **レイアウト型を選び直せる**（例: ギャラリーを均等グリッド→ベントー型へ）
- 作り直したあと、ブリッジが**実ファイルを読み直して**指示どおりになったか・規約を守っているかを
  機械的に確かめ、守られていなければ画面に赤字で伝える
- **1案だけ作ったときも比較画面が開く**。表示幅の切替も 🔄 も3案と同じように使える

**見本サイトURLから配色を読み取れる（KLK-083）**
- URL を貼って「配色を読み取る」で、よく使われている色をスウォッチで確認し、配色欄へ反映できる。
  AI を通さない決定的な処理で、外部アクセスは**社内ネットワークを覗けないよう厳重に制限**している

**実績カタログを画面から管理できる（KLK-063〜068）**
- カタログ画面へ**ドラッグ&ドロップ**で画像を追加 → AI がタグ付けを提案 → **画面で確認・修正してから登録**
- カードの 🗑 で登録を取り消せる（画像は消さず `catalog/.trash/` へ退避）
- 主配色をムードカラー ジェネレーター準拠の**16種**へ拡張

**配布とドキュメント（KLK-069〜071・077）**
- `README.md` を全面作成（「できないこと」を先に書く構成）・`tools/make-package.sh` で配布フォルダを組み立て
- **Windows 対応**（`起動.bat`・hook の両OS化）
- 見本となる生成ページ3点を `samples/` に同梱
- **カタログ同梱版（A）/ 同梱なし版（B）** の2種類を作れる。A では README が同梱前提の案内へ自動で切り替わる

**比較画面（KLK-062）**
- 画面幅プレビュー切替（全幅 / 768px / 375px）。スマホ版の二重生成は廃止

### Changed（KLK-061〜095）
- 生成規約に**セクション内型プール**を整備し、14セクション×各6型から案ごとに振り分けるように
  （KLK-051〜058。NEWS/PRICE/FAQ/ACCESS/CONTACT/SEARCH/SNS ほか）
- 画像アタリの比率を **4/3** に統一。狭いカラムではカード内を縦積みに畳む（KLK-072・073）
- 業種・テイストの語彙を実績カタログ側の正へ一本化（KLK-059）
- ブリッジのタイムアウトを **900→1800秒**（実測 262〜847秒に対し余裕が6%しかなかった・KLK-095）

### Fixed（KLK-061〜097）
- MV の「SCROLL ↓」がボタンと**重なる**不具合（KLK-097）。誘導は**画面左端に縦組み**になり、
  MV は誘導用の帯を左右に予約するので、見出し・リード文・ボタンをすべて置いても重ならない。
  あわせて MV の縦幅が**ファーストビューを覆う**高さになった（`full`/`split`/`band`/`center-scroll`）
- カタログ取り込みが**一度も登録に到達していなかった**不具合（非対話実行と人間確認ゲートの衝突・KLK-064/065）
- 🔄 セクション再生成が `<section>` を使うページで**全番地404**になっていた不具合
  （`<div>` 決め打ち・見本の2/3で機能していなかった・KLK-078）
- HERO `panel-band` のパネルが 1200〜1280px で**段落ち**していた不具合（KLK-081）
- 同じ端末なのに **Origin 判定で403**になる不具合（文字列一致で `http://[::1]:…` を弾いていた・KLK-084）
- UI と実装の食い違いを是正（「対応予定」表示・見本での 🔄 の見え方など・KLK-061・081）

### Removed
- 配布物に無関係な成果物をリポジトリから除去（KLK-060・パッケージ化準備）: `site/`（KLK-002 のコーポレートサイト静的サンプル）・`flyers/`（別件のチラシHTML 2点）・`src/`（`.gitkeep` のみの未使用ディレクトリ）。あわせて対象を失った `tests/site/check_klk002.py` を除去。**Git履歴は保持**しており `git checkout {削除前のコミット} -- site` で復元できる。デザインラフ・ジェネレーターのサンプルは、パッケージ化時に見本となる生成ページ3〜5点をあらためて生成して同梱する方針（`mockups/` の外）。

### Added
- 配色ジェネレーター `palette/index.html` v1.2（KLK-005）: CSS変数コピーに「HEXコード一覧」形式を追加し切替可能に（`hexListOf`／`copyTextOf`・グローバル `copyFormat` 保持・微調整後の値を反映）／KLK-005 検証 `tests/site/check_klk005.py`（静的S1-S13）・`tests/site/smoke_klk005.node.js`（動的D1-D7）・`tests/test_palette_klk005.py`（unittestラッパー）
- 配色ジェネレーター `palette/index.html` v1.1（KLK-004）: メインカラーの傾向に「ゴールド」「シルバー」を追加（色味サブ選択6変種・相性パートナーによる3案生成・最終段クランプ `clampMetalBand`・金属風グラデーションの参考表示）／CSS変数コピー（`--color-main` 等4変数）／URL共有（選択状態＋シードをURLパラメータ化・`replaceState` 同期）／生成ボタンを上段横長に分離
- KLK-004 検証: `tests/site/check_klk004.py`（静的S1-S12）・`tests/site/smoke_klk004.node.js`（動的D1-D6）・`tests/test_palette_klk004.py`（unittestラッパー、node無し環境はskip）
- 配色ジェネレーター `palette/index.html` v1.0（KLK-003）: 言葉・スライダーから配色3案を生成するツール。同系色モード・トーンチップ（PCCS風9種）・WCAGコントラスト比バッジ・色覚多様性チェック・70:25:5比率バー＋サイト風モック・H/S/L微調整モーダル等
- トップページFV刷新の静的サンプル `site/`（KLK-002）と設計書・検証テスト

### Changed
- 配色ジェネレーターの可読性バッジをWCAG等級から日常語＋信号色へ変更（KLK-005・読みやすい◎/小さい文字は注意△/読みにくい✕、注意・NG時に直し方を提示、生数値と正式等級はツールチップへ集約。判定ロジックは不変）
- 配色ジェネレーターの「ジャンル（業種）」を単一選択（ラジオ＋指定なし）に変更（KLK-004・複数業種の色相平均による濁りを解消）

## [1.2.0] - 2026-07-05

### Added
- スキル `spec-interview`（`.claude/skills/spec-interview/`）: 非エンジニア向けに対話形式で要件定義書 `docs/SPEC.md` を作成・改訂する。最短/フルの2モード、標準技術構成の「反証がなければ適用」（`DEFAULT_STACK.md`）、SPECテンプレート（`SPEC_TEMPLATE.md`）を同梱
- スキル `wireframe-gen`（`.claude/skills/wireframe-gen/`）: SPECの画面一覧（セクション6）から単一ファイル静的HTMLのワイヤーフレーム・ハブページ（index.html）・PC/スマホ比較ビュー（compare.html）を生成する。生成規約 `WIREFRAME_RULES.md` を同梱（外部依存ゼロ・中忠実度・コントラスト規律・Mermaid遷移図のCSSフォールバック）
- CLAUDE.md にスキルを登録: スラッシュコマンド一覧・開発ループフロー図の前工程（SPEC作成→ワイヤーフレーム→チケット作成）・ドキュメント管理表・investigatorのSPEC不在時の誘導
- `.gitignore` に `*.skill`（スキルのZIP配布物を除外し、ソースの正を `.md` に一本化）
- `docs/wireframes/`（出力ディレクトリのプレースホルダ `.gitkeep`）

### Removed
- 静的テンプレート `docs/SPEC.md`（要件定義は `/spec-interview` から生成する方式へ移行。テンプレートはスキル内 `SPEC_TEMPLATE.md` が正）

---

## [1.1.0] - 2026-06-17

### Added
- 状態検証hook: `validate_ticket_state.py`（PreToolUse）/ `check_loop_integrity.py`（Stop）/ `_ticket_lib.py`。チケット状態機械を機械的に強制
- ループ観測性: `record_metrics.py`（PostToolUse）でステータス遷移を `tickets/.metrics.jsonl` に記録、`.claude/metrics/aggregate.py` で集計、`/metrics` コマンドで表示
- `.claude/settings.json` にhook登録（PreToolUse / PostToolUse / Stop）
- 自動テスト `tests/`（unittest・依存なし）: 検証ルール・各hook・メトリクス集計を66ケースでカバー
- リトライカウンタ強制の二層化: L2 カウンタ単調性（PreToolUse・減少禁止でcap回避を防止）/ L3 差し戻し履歴照合（Stop・`.metrics.jsonl` の差し戻し回数とカウンタを和で照合し、増やし忘れ＝上限不発火の穴を塞ぐ）
- チケットフロントマターに `retry_counts` を追加し、本文「リトライカウンタ」セクションと併用（ハイブリッド管理）
- CLAUDE.md「ポリシー管理の原則」転記表・状態検証hook節
- 権限モード `auto` の既定化（`.claude/settings.json` `permissions.defaultMode = "auto"`）。コマンド承認でループが頻繁に停止する問題を解消
- ループ起動時チェック「Autoモードの確認」（`start-loop.md` 起動時チェックリスト / `orchestrator.md` Responsibilities）と、ポリシー管理表への該当行追記
- CI: `.github/workflows/test.yml`（push(main/develop)・PRで `tests/` を Python 3.10–3.12 マトリクス実行、stdlibのみ）
- `docs/batch-loop.md`: 複数チケットの連続ループ実行ガイド（事前バッチ承認で各完了時の承認ゲートを跨ぐ運用）
- `.claude/settings.json` の allow に `sed -n`（読み取り専用）のみ再追加（probe/テスト後始末の複合コマンド向け）。`echo` はファイル書き込みベクタ（`echo > file`）を再び開くため再追加せず、auto モードの分類器に委ねる。環境固有の `.venv/bin/python` / `rm -f` ルールは `settings.local.json` へ分離

### Changed
- 設計書を単一 `docs/DESIGN.md` から `docs/designs/{ID}.md`（チケット単位分割）へ変更
- 設計書frontmatterから `status`（draft/approved/superseded）を撤廃。設計の進行はチケットstatusを唯一の真実とし、履歴はGitに委ねる（dead state解消）
- orchestratorのステータス定義をCLAUDE.md準拠に統一（独自ステータス `review_approved` / `review_rejected` を廃止）
- architect後の人間承認ゲートを廃止し、実装ループを完全自律化
- README: Obsidianが任意であることを明言

### Removed
- `docs/DESIGN.md`（`docs/designs/` へ移行）
- `.claude/settings.json` の allow から `awk` / `echo`（ファイル書き込みをWrite権限に一元化）。※ `sed -n`（読み取り専用）のみ probe/テスト用途で再追加（上記 Added 参照）

---

## [1.0.0] - 2026-06-14

### Added
- エージェント定義: orchestrator / investigator / architect / implementer / tester / reviewer
- チケットテンプレート: ticket.md / ticket-bug.md
- スラッシュコマンド: /start-loop / /new-ticket / /improvement-loop / /archive
- ドキュメント: SPEC.md / docs/designs/ (チケット単位設計書) / obsidian-setup.md テンプレート
- チケットダッシュボード: tickets/_index.md
- Claude Code設定: .claude/settings.json（権限設定）
- .gitignoreテンプレート（プライベート用・パブリック用）
- 2ループ構造（実装ループ・改善ループ）の導入
- git-flowブランチ戦略の採用
- Gitコミット規約（チケットIDプレフィックス）

---

<!--
## バージョニングの指針

MAJOR（X.0.0）: エージェント定義の大幅な変更・ループフローの変更・既存プロジェクトとの後方互換性が失われる変更
MINOR（0.X.0）: 新規エージェント追加・新規コマンド追加・テンプレートの追加
PATCH（0.0.X）: ドキュメントの修正・既存テンプレートの軽微な修正・バグ修正

## 変更カテゴリ
- Added: 新機能
- Changed: 既存機能の変更
- Deprecated: 将来削除予定の機能
- Removed: 削除された機能
- Fixed: バグ修正
- Security: セキュリティ関連の修正
-->
