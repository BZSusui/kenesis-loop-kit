---
name: draft-regenerate
description: 番地ラベル(例 MV-01)を指定して、生成済みデザインラフHTMLの1セクションだけを DRAFT_RULES 準拠で作り直すスキル(REQ-103 / SCR-002)。他5セクション・配色5変数・カラム骨格(data-columns)・全番地ラベル・head/アニメscript は保持し、指定した1つの .sec ブロックのみ差し替える。ユーザーが「このセクションだけ作り直したい」「案BのHEROだけ別案にしたい」「MV-01を再生成して」と言ったとき、またはローカルブリッジ(draft-gen/bridge.py)の POST /regenerate が渡すジョブ仕様パスを受けたときに使う。存在しない/重複する番地はファイルを一切変更せず停止する(SPEC §7)。
---

# デザイン部分再生成 — 番地ラベル指定でセクション単位に作り直す

## 目的と成果物

生成済みデザインラフ(`mockups/{日付}_{案件名}/index-{letter}.html` 複数案 or `index.html` 1案)の**特定セクションだけ**を、
番地ラベル(`MV-01` 等)を指定して DRAFT_RULES 準拠で作り直す(REQ-103 / SCR-002)。「案BのHEROだけ別案にしたい」を実現する。

- **成果物**: 対象HTMLの**当該 `.sec` ブロックのみ**を差し替えた更新版(上書き保存)。ファイル名・`compare.html` のリンクは不変。
- **保持すべき不変(最重要)**: 指定 `.sec` 以外はすべて保存する(§保持すべき不変)。
- **未知/重複番地はファイルを一切変更せず停止**(SPEC §7・ラフを壊さない)。
- 生成規約は `/draft-generate` と共通の `.claude/skills/draft-generate/templates/DRAFT_RULES.md`(§2 番地・§3 アタリ・
  §5 配色・§6 印刷・§7 アニメ・§12 バリエーション・**新設 §14 部分再生成**)を**参照**する(規約の重複を作らない)。

## 参照ファイル

| ファイル | 読むタイミング |
|---|---|
| `.claude/skills/draft-generate/templates/DRAFT_RULES.md` | **セクション再生成の前に必ず全体を読む**。特に §14(部分再生成規約)・§2(番地)・§3(アタリ)・§5(配色)・§7(アニメ)。生成規約の正 |
| 対象 `index-{letter}.html` / `index.html` | 再生成対象。**配色5変数(ルート `.mock` の `--m-*`)・`data-columns`・他5セクション・番地ラベル・`<head>`・アニメ`<script>` の把握元** |
| `{folder}/instruction.json` | 業種(`industry.resolved`)・テイスト(`taste`)・カラム(`layout.columns`)の**文脈**を読む(配色はここから読まない・§保持すべき不変) |
| `tests/fixtures/klk009/index-a.html` | 生成ラフの代表構造(`.sec`/`.addr > .pin`/ルート `.mock` の `--m-*`/`data-columns`)。迷ったら実例として参照 |

## 起動と入力(2経路・後方互換)

- **起動語**: `/draft-regenerate`。
- **① ジョブ仕様 `.json` パス(ローカルブリッジ経由)**: `mockups/.pending/{jobId}.regen.json`
  (`{schema:"design-regenerate-job", version:1, target, addr}`)。引数がこのファイルパスのときは**そのファイルを読み込み**、
  `schema` が `"design-regenerate-job"` / `version` が `1` であることを確認し、`target`(対象HTMLの相対パス)・`addr`(番地)を取り出す。
  ブリッジが検証済みの安全値のみを書くため、プロンプトに可変ユーザー文字列は載らない(注入対策)。
- **② 手動 `$ARGUMENTS`**:
  - 複数案: `{folder} {letter} {addr}`(例 `mockups/2026-07-08_サンプル案件 a MV-01`)。対象 = `{folder}/index-{letter}.html`。
  - 単一案: `{対象HTMLパス} {addr}`(例 `mockups/2026-07-08_サンプル案件/index.html MV-01`)。
- いずれの経路でも**同じ受付チェック**へ合流する。生成規約(DRAFT_RULES)・保持すべき不変・上書き方針は経路によらず同一。

## 手順

### 1. 受付チェック(未知/重複ならファイル無変更で停止・SPEC §7)

- `addr` が番地パターン `^[A-Z][A-Z0-9]*-\d{2}$` に一致するか確認する(基本6種 `NAV-01`/`MV-01`/`ABOUT-01`/`MENU-01`/
  `GALLERY-01`/`FOOTER-01` ＋ `SECTION-NN` 連番拡張)。一致しなければ停止して案内する。
- 対象HTMLを読み、`<span class="pin">{addr}</span>` が**ちょうど1回**存在するか確認する。
  - **0回(未知)/2回以上(重複)なら、ファイルを一切変更せず**「番地 {addr} が見つからない/重複しています。
    `docs/wireframes/SCR-002-compare.html` の番地一覧を確認してください」と案内して**停止**する(SPEC §7・ラフを壊さない)。
- ちょうど1回のときのみ、その pin を含む唯一の `.sec` ブロックを対象として次へ進む。

### 2. 文脈と不変の把握

- **文脈(instruction.json から)**: 併置 `{folder}/instruction.json` から業種(`industry.resolved`)・テイスト(`taste`)・
  カラム(`layout.columns`)を読む。当該セクションの作り直しの方向づけに使う。
- **不変(対象HTMLから)**: 次を対象HTMLから把握し、**再生成後も変えない**:
  - **配色5変数**: ルート `.mock` 定義の `--m-main`/`--m-nav`/`--m-accent`/`--m-bg`/`--m-text` の**実値**
    (インライン `style="--m-*:…"` 形式・`<style>` 内 `.mock { --m-*:…; }` 形式の双方)。
    **★ instruction.json からは読まない**(案B/C は `colors.main` から派生した別テーマのため、指示書から読むと配色が壊れる)。
  - **カラム骨格**: ルート要素の `data-columns`。
  - **全番地ラベル**: 他5セクションの `.pin` と対象セクションの `.pin {addr}`。
  - **`<head>` の CSS**(`.reveal`/`@media print`/`.atari` 等)・**`</body>` 直前のアニメ `<script>`**(§7)の有無。
  - **アニメ状態**: 対象ファイルの現状に合わせる(`.reveal`/observer がある案なら新セクションにも `.reveal` を付け、OFF 案なら付けない)。

### 3. 当該セクションのみ再生成(DRAFT_RULES 準拠)

pin 一致の1つの `.sec` ブロックを DRAFT_RULES に準拠して作り直す:

- §2 番地: `.sec`/`.addr`/`.pin {addr}` の枠と**番地ラベルは保持**する(ラベル文字列を変えない)。
- §3 アタリ a方式: 写真は色面プレースホルダ(`.atari`/`.desc`/`.kw`、HERO は `.atari-tag`)。実写真URL・`<img>` を使わない。
- §5 配色: 手順2で対象HTMLから読んだ5変数を `var(--m-*)` で参照する。**新しい色値を導入しない**(直値の主要色散在を作らない)。
- §7 アニメ: 対象ファイルの現状に合わせる(ON 案は `.reveal` を付ける・OFF 案は付けない)。
- §14 部分再生成: 保持すべき不変・上書き方針・番地一意性・配色は対象HTMLから、を厳守する。
- **プールマーカー再付与(KLK-029/036/037・DRAFT_RULES §12.1.2/§12.1.3/§14)**: 対象が `VOICE-01`/`FLOW-01`/`STAFF-01`(§12.1.2・mod6)
  ／`GALLERY-01`/`MV-01`(HERO)/`ABOUT-01`(§12.1.3・mod4) のときは、そのセクションが持つべき型マーカー
  (`voice-*`/`flow-*`/`staff-*`／`.m-gallery` の `pat-*`／`.m-hero` の `data-hero`／`.m-about` の `img-*`)を**対象HTMLだけで自己決定**して
  再付与する(instruction.json 不要・決定的): ①対象HTMLのルート `.mock` から `data-columns` と `data-nav-position` の実値を読む →
  ②§12.1.2 のオフセット表で offset を得る(§12.1.2/§12.1.3 共有) → ③対象ファイルの letter(`index-{letter}.html` の a/b/c、単案 `index.html`
  は letter=a) から、VOICE/FLOW/STAFF は §12.1.2 割り当て表(mod6)、GALLERY/HERO/ABOUT は §12.1.3 割り当て表(mod4)で pool index を
  読む → ④その `pool[index]` のマーカーを容器 `.m-{sec}` に付け(HERO は型に付随する整列シグネチャも合わせる)、対応 CSS が `<head>`
  に無ければ足す。元の生成と同じ型が再現される(表を読むだけ・算術なし)。他セクション・配色5変数・ルート属性は不変。
- **参考準拠の保持(KLK-034・DRAFT_RULES §12.2/§14)**: 対象HTMLのルート `.mock` に **`data-ref-id` があるファイル(=参考準拠の案A)**
  は、表引き・archetype 既定より**「対象セクションの現行マーカー」を優先**する: 差し替え前の対象 `.sec` 内の容器
  (`.m-hero` の `data-hero`/`.m-menu`・`.m-gallery`・`.m-about`・`.m-voice`・`.m-flow`・`.m-staff` の型マーカー)を読み取り、
  **同じ型マーカーで再生成**する(参考の型を保持・対象HTMLだけで自己決定・決定的)。現行マーカーが読めない/語彙外のときのみ
  従来規則へフォールバック。`data-ref-id` が無いファイルは従来どおり。
- 仮文言(§4): 業種・テイストに合った実文言。ダミー禁止。未定は `<span class="todo">(要検討: …)</span>`。

### 4. 書き戻し(上書き・当該 .sec ブロックのみ)

- 対象HTMLの**当該 `.sec` ブロックのみ**を Edit で差し替える(ファイル名は不変=`index-{letter}.html` / `index.html`)。
- **他5セクションの `.sec` ブロック・配色5変数・`data-columns`・全番地ラベル・`<head>`・アニメ `<script>` は変更しない**
  (バイト等価で残す)。差し替えは指定 `.sec` の 1 ブロックに厳密に閉じること。

### 5. 報告(非エンジニア向け)

- どのセクション(番地)を作り直したか。
- **配色5変数・カラム(`data-columns`)・他5セクション・全番地ラベル・`<head>`/アニメ`<script>` を保持した旨**。
- `(要検討: …)` で残した箇所の一覧(人間が後で埋める箇所)。
- 開き方: `{folder}/compare.html` があればそれを開いて更新版を確認できる旨(上書きなので iframe/リンク不変=リロードで反映)。
  無ければ対象 `index-{letter}.html` / `index.html` をブラウザで開く。

## 保持すべき不変(DRAFT_RULES §14 と対応)

指定 `.sec` 以外は**すべて保存**する。次を再生成で変更してはならない:

1. **配色5変数**(`--m-main`/`--m-nav`/`--m-accent`/`--m-bg`/`--m-text`)= **対象HTMLのルート `.mock` 定義から実値を読む**
   (instruction.json からは読まない)。新セクションも `var(--m-*)` で参照する。
2. **カラム骨格**(ルート要素の `data-columns`)。
3. **全番地ラベル**(他5セクションの `.pin` と対象セクションの `.pin {addr}`)。
4. **`<head>` の CSS**・**アニメ `<script>`**(§7)。
5. **他5セクションの `.sec` ブロック**(バイト等価)。

## してはならないこと

- 指定 `.sec` 以外を変更すること(他5セクション・配色5変数・`data-columns`・番地ラベル・`<head>`・アニメ`<script>` の書き換え)。
- **未知・重複番地で生成を進めること**(ファイルを変更せず停止する・SPEC §7)。
- **配色を `instruction.json` から読むこと**(対象HTMLのルート定義から読む)。
- 新しい配色の直値を主要色として散在させること(配色は `var(--m-*)` 参照)。
- 外部リソース(CDN・外部CSS/JS・Webフォント・外部画像URL)や実写真URL(`<img src>`)に依存すること(a方式=色面のみ)。
- 実在の顧客名・個人情報・シークレット(api key / secret / password / token / private key)を生成HTMLに含めること。
