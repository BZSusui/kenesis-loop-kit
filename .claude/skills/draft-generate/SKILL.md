---
name: draft-generate
description: 生成指示書JSON（schema:"design-draft-instruction" / version:1）を入力に、デザインラフHTML（1案）を生成し mockups/{日付}_{案件名}/ に保存するスキル。ユーザーが「デザインラフを生成」「このJSONからラフを作って」「生成指示書からデザイン案を作りたい」と言ったとき、または SCR-001（draft-gen/index.html）で作った生成指示書を渡されたときに使う。外部依存ゼロの単一HTMLを生成する。
---

# デザインラフ生成 — 生成指示書JSONからデザインラフHTML（1案）を生成する

## 目的と成果物

KLK-006 で確定した**生成指示書JSON**（`schema:"design-draft-instruction"` / `version:1`・`docs/designs/KLK-006.md` §4.4）を
唯一の入力契約として、`docs/wireframes/SCR-002-compare.html` の `.mock` 部を見た目・構造の正とする**デザインラフHTML（1案）**を
生成し保存する。「デザインラフ・ジェネレーター」（SPEC v1.2）の中核＝生成エンジン。SPEC §9 に従い生成エンジンは
**Claude Code（本スキル）**とし、AI APIの個別契約・サーバー・DBは使わない。

- **成果物**: `mockups/{YYYY-MM-DD}_{案件名}/index.html`（デザインラフ本体・1案）＋ `instruction.json`（入力の写し）
- 生成HTMLは単一ファイル・外部依存ゼロ・配色CSS変数・番地ラベル・アタリ画像（a方式）・業種に合った仮文言・
  スクロール出現アニメ・印刷時は補助表示を非表示（`@media print`）。

## 参照ファイル

| ファイル | 読むタイミング |
|---|---|
| `templates/DRAFT_RULES.md` | **HTML生成前に必ず全体を読む**。生成規約（配色マッピング・アタリ方式・番地ラベル・印刷CSS・出現アニメ・カラム・保存規約）の正はこのファイル |
| `docs/wireframes/SCR-002-compare.html` | 見た目・構造の正（`.mock` 部）。クラス名・骨格の参照元 |
| `tests/fixtures/klk007/sample-draft.html` | DRAFT_RULES に準拠した代表出力（ゴールデンサンプル）。迷ったら実例として参照 |

## 起動と入力

- **起動語**: `/draft-generate`。実装ディレクトリ `draft-gen/`（SCR-001 の設定画面）とは別物。
- **入力**: 引数 `$ARGUMENTS`、またはユーザーが会話に貼り付けた**生成指示書JSON**。SCR-001（`draft-gen/index.html`）の
  「この内容で生成」でクリップボードにコピーされたJSONを想定する。

## 手順

### 1. 受付チェック

入力JSONが次を満たすか確認する。満たさない場合は**生成せず**案内して終了する。

- `schema` が `"design-draft-instruction"` であること。
- `version` が `1` であること（`1` 以外なら「未対応の版です。SCR-001 を最新版で作り直してください」と伝えて停止。
  前方互換の版分岐は将来対応）。
- 必須フィールドが埋まっていること: `industry.resolved`（業種）・`layout.columns`（カラム構成）・`colors.main`（主色HEX）。
- 欠けている場合: 「生成に必要な項目（業種／カラム構成／主色）が不足しています。SCR-001（`draft-gen/index.html`）で
  生成指示書を作り直してください」と案内して終了する。会話の文脈から項目を勝手に推測して補完しない。

### 2. 規約読込

生成の前に必ず `templates/DRAFT_RULES.md` を全読する（`wireframe-gen` と同じ規律）。番地ラベル・アタリ方式・配色
マッピング・印刷CSS・出現アニメ・カラム構成・保存規約をこの時点で頭に入れる。

### 3. 生成（1案のみ）

DRAFT_RULES に完全準拠した**単一HTML**を書く:

- **配色**: `colors.main/sub/accent/bg`（+ `autofill`）を DRAFT_RULES §5 の表どおり `--m-main/--m-nav/--m-accent/--m-bg/--m-text`
  へマッピング。生成ルート要素に5変数を定義し、本体は `var(--m-*)` で参照する。null 役割は補完ルールで埋める。
- **カラム構成**: 生成ルート要素に `data-columns="{layout.columns}"` を付け、本文レイアウトを合わせる。
- **番地ラベル**: 各セクションに `.addr > .pin`（NAV-01 / HERO-01 / ABOUT-01 / MENU-01 / GALLERY-01 / FOOTER-01）。
- **アタリ画像**: a方式（色面＋`.desc`＋`.kw`。HERO は `.atari-tag`。キーワード未定は `.desc` のみ）。`atari:"free-photo"` でも
  a方式で生成し「b方式は別チケット（REQ-104）」と注記。
- **仮文言**: 業種（`industry.resolved`）・テイスト（`taste`）に合った実文言。ダミー禁止。未定は `(要検討: …)`。
- **印刷CSS / 出現アニメ / レスポンシブ**: DRAFT_RULES §6〜§8 のとおり（`@media print` で補助非表示・`IntersectionObserver`・
  `@media (max-width:640px)`）。
- **1案のみ**: `output.variants` が `3` でも**本スキルは1案のみ**生成する。複数案（REQ-008）・比較UI（SCR-002）は別チケット。

### 4. 保存

DRAFT_RULES §9 に従い **Claude Code が Write** で保存する:

- フォルダ: `mockups/{YYYY-MM-DD}_{案件名}/`（案件名＝`meta.project` をパス安全化: 前後空白除去 → 空白を `_` →
  `/ \ : * ? " < > |` と制御文字を除去。空なら `untitled`）。
- `mockups/{…}/index.html`＝デザインラフ本体。
- `mockups/{…}/instruction.json`＝入力の生成指示書の写し（そのまま保存し、再実行・監査を可能にする）。
- `mockups/` はGit除外（`.gitignore` 3ファイルに登録済み）。案件名・生成物はコミットされない。

### 5. 報告（非エンジニア向け）

- 保存先パス（`mockups/{日付}_{案件名}/`）。
- 生成したセクションの番地ラベル一覧（NAV-01〜FOOTER-01）。
- `(要検討: …)` で残した箇所の一覧（人間が後で埋める箇所）。
- 除外した外部参照（`atari:"free-photo"` を a方式に切り替えた等）や、`output.variants:3` を**1案のみ**生成した旨と
  「複数案は別チケット」の注記。
- ブラウザで `index.html` を開いて確認する方法（ダブルクリックで開ける・印刷プレビューで補助表示が消える）。

## してはならないこと

- 受付チェックを飛ばして、不足項目を会話の文脈から推測で補って生成すること。
- 外部リソース（CDN・外部CSS/JS・Webフォント・外部画像URL）に依存するHTMLを生成すること。
- アタリ画像に `<img src>` や実写真URLを使うこと（a方式＝色面のみ）。
- 複数案（最大3案）・比較UI・部分再生成・フリー実写真b方式・見本URL反映を本スキルで実装すること（すべて別チケット）。
- 実在の顧客名・個人情報・シークレットを生成HTMLに含めること。
