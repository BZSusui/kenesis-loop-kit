---
name: draft-generate
description: 生成指示書JSON（schema:"design-draft-instruction" / version:1）を入力に、output.variants（1〜3）に応じ最大3案のデザインラフHTMLを一括生成し mockups/{日付}_{案件名}/ に保存するスキル（複数案は index-a/b/c.html ＋ 比較ハブ compare.html を併置）。ユーザーが「デザインラフを生成」「このJSONからラフを作って」「生成指示書からデザイン案を作りたい」「複数案を見比べたい」と言ったとき、または SCR-001（draft-gen/index.html）で作った生成指示書を渡されたときに使う。外部依存ゼロの単一HTMLを生成する。
---

# デザインラフ生成 — 生成指示書JSONから最大3案のデザインラフHTMLを一括生成する

## 目的と成果物

KLK-006 で確定した**生成指示書JSON**（`schema:"design-draft-instruction"` / `version:1`・`docs/designs/KLK-006.md` §4.4）を
唯一の入力契約として、`docs/wireframes/SCR-002-compare.html` の `.mock` 部（生成本体）と chrome（比較ハブ）を見た目・構造の
正とする**デザインラフHTML（`output.variants` 1〜3 に応じ最大3案）**を生成し保存する。「デザインラフ・ジェネレーター」
（SPEC v1.2）の中核＝生成エンジン。SPEC §9 に従い生成エンジンは**Claude Code（本スキル）**とし、AI APIの個別契約・
サーバー・DBは使わない。

- **成果物（`output.variants` による分岐・DRAFT_RULES §9）**:
  - `variants:1`（後方互換）: `mockups/{YYYY-MM-DD}_{案件名}/index.html`（デザインラフ本体・1案）＋ `instruction.json`。
  - `variants≥2`: `index-a.html`／`index-b.html`／`index-c.html`（成功案ぶん・成功順 a→b→c）＋ 比較ハブ `compare.html`
    ＋ `instruction.json`（`compare.html` の構造規約は DRAFT_RULES §13）。
- 各案の生成HTMLは単一ファイル・外部依存ゼロ・配色CSS変数・番地ラベル・アタリ画像（a方式）・業種に合った仮文言・
  スクロール出現アニメ・印刷時は補助表示を非表示（`@media print`）。案間の差は**配色テーマ主軸**で振る（DRAFT_RULES §12）。

## 参照ファイル

| ファイル | 読むタイミング |
|---|---|
| `templates/DRAFT_RULES.md` | **HTML生成前に必ず全体を読む**。生成規約（配色マッピング・アタリ方式・番地ラベル・印刷CSS・出現アニメ・カラム・保存規約・§12 複数案バリエーション・§13 比較画面 compare.html 構造）の正はこのファイル |
| `docs/wireframes/SCR-002-compare.html` | 見た目・構造の正（`.mock` 部＝生成本体／chrome＝比較ハブ）。クラス名・骨格の参照元 |
| `tests/fixtures/klk007/sample-draft.html` | DRAFT_RULES に準拠した1案の代表出力（ゴールデンサンプル）。迷ったら実例として参照 |
| `tests/fixtures/klk009/compare.html`・`index-a/b/c.html` | 複数案・比較ハブの代表出力（ゴールデン）。案別 standalone と `compare.html` 構造の実例 |

## 起動と入力

- **起動語**: `/draft-generate`。実装ディレクトリ `draft-gen/`（SCR-001 の設定画面）とは別物。
- **入力**: 引数 `$ARGUMENTS`、またはユーザーが会話に貼り付けた**生成指示書JSON**。SCR-001（`draft-gen/index.html`）の
  「この内容で生成」でクリップボードにコピーされたJSONを想定する。
- **入力が既存の `.json` ファイルのパス**（例: ローカルブリッジ `draft-gen/bridge.py` が渡す
  `mockups/.pending/{id}.json`）のときは、**そのファイルを読み込んでから**次の受付チェックにかける。従来の
  `$ARGUMENTS`／会話貼付の生成指示書JSONも**引き続き受理**する（後方互換・KLK-010）。いずれの経路でも入力契約
  （`schema:"design-draft-instruction"` / `version:1`）と受付チェックは同一で、生成規約（DRAFT_RULES）・保存規約は変わらない。

## 手順

### 1. 受付チェック

入力JSONが次を満たすか確認する。満たさない場合は**生成せず**案内して終了する。

- `schema` が `"design-draft-instruction"` であること。
- `version` が `1` であること（**不変**。旧チケットのJSONも新JSONも version:1。`1` 以外なら「未対応の版です。SCR-001 を
  最新版で作り直してください」と伝えて停止。前方互換の版分岐は将来対応）。KLK-008 のカラム拡張・アニメ追加は additive・
  後方互換のため version は上げない。
- 必須フィールドが埋まっていること: `industry.resolved`（業種）・`layout.columns`（カラム構成）・`colors.main`（主色HEX）。
- **`layout.columns` の正規化（旧値エイリアス・KLK-008 §4.2/4.4）**: 旧 `2col-sub-left` → `2col-body-left`、
  `2col-sub-right` → `2col-body-right` に正規化してから生成する。正規化後の値が新6値
  （`1col`/`2col-full-left`/`2col-full-right`/`2col-body-left`/`2col-body-right`/`3col`）のいずれでもなければ
  「SCR-001（`draft-gen/index.html`）で生成指示書を作り直してください」と案内して停止する。
- **`output.animation` の既定補完（KLK-008 §4.3）**: `output.animation` が未指定（キー無し）なら `true`（従来ON）とみなす。
  明示 `false` のときのみアニメOFF（`.reveal`/`IntersectionObserver` を出さない・DRAFT_RULES §7）。
- 欠けている場合: 「生成に必要な項目（業種／カラム構成／主色）が不足しています。SCR-001（`draft-gen/index.html`）で
  生成指示書を作り直してください」と案内して終了する。会話の文脈から項目を勝手に推測して補完しない。

### 2. 規約読込

生成の前に必ず `templates/DRAFT_RULES.md` を全読する（`wireframe-gen` と同じ規律）。番地ラベル・アタリ方式・配色
マッピング・印刷CSS・出現アニメ・カラム構成・保存規約をこの時点で頭に入れる。

### 3. 生成（`output.variants` に応じ最大3案）

`output.variants`（1〜3）ぶんループし、各案について DRAFT_RULES に完全準拠した**単一HTML**を1枚ずつ書く。
**カラム数（`data-columns`）・番地・セクション構成・業種/テイストの骨子・アタリ a方式は全案で固定**し、**案間の差は
配色テーマ（§5の5変数）とレイアウト原型（`data-archetype`・§12.1）を両振り**する（振れ幅規約は DRAFT_RULES §12）。
各案（`index.html` または `index-{letter}.html`）は次を満たす:

- **配色（案ごとに振る）**: `colors.main/sub/accent/bg`（+ `autofill`）を DRAFT_RULES §5 の表どおり
  `--m-main/--m-nav/--m-accent/--m-bg/--m-text` へマッピングし、生成ルート要素に**案別の5変数**を定義（本体は `var(--m-*)`
  で参照・null 役割は補完ルールで補う）。**案A＝指示書の配色に忠実**／**案B＝濃色・高級方向**／**案C＝明色・ポップ方向**
  にテーマを振る（DRAFT_RULES §12）。案間で少なくとも `--m-main` が異なること。
- **カラム構成（全案共通）**: 生成ルート要素に `data-columns="{正規化後の canonical 値}"` を付け、DRAFT_RULES §8 の6系統骨格に
  合わせる（全体2カラム `2col-full-*` は `.m-layout` が NAV/HERO を内包・サイドバー全高。本文のみ `2col-body-*` は
  HERO を grid の外に出す。旧 `2col-sub-*` は `2col-body-*` へ正規化してから書く）。**全案で同一の `data-columns`**（列数固定）。
- **レイアウト原型（案ごとに振る・KLK-021/023・DRAFT_RULES §12.1/§12.1.1）**: 生成ルート要素に `data-columns` と並べて
  `data-archetype="{値}"` を付ける。3値enum＝`stack-centered`（案A・中央寄せ標準）／`split-editorial`（案B・左寄せ非対称・
  serif上質）／`banded-showcase`（案C・帯構成ビジュアル先行・sans）。**列数（`data-columns`）とセクション集合（`sections`）は
  全案同一**にし、archetype ごとに**本文構造の束**を振る（§12.1.1）: **並び順**（ルート `data-section-order` に本文DOM順を焼き込み・
  案A canonical／案B ABOUT→GALLERY→MENU／案C GALLERY先行）。**HERO型・GALLERY型・ABOUT画像配置・MENU型は §12.1.3（下記プール）で決定**する
  （KLK-036/037/044・archetype 固定から分離）。**案間で `data-archetype`・`data-section-order`・`data-hero`・MENU/GALLERY/ABOUT の型が相違**すること
  （複数の構造軸が動く・`--m-main` 相違と同型の機械検証フック）。番地は並べ替えても各1回のまま（§2）。単案（`variants:1`）は既定 `stack-centered`。
- **HERO/GALLERY/ABOUT/MENU/SNS の内部型プール（KLK-036/037/040/044/049・DRAFT_RULES §12.1.3）**: これらが `sections`（HERO=MV-01は常設）にあるときは、案ごとに
  **各セクションのプールから型を選ぶ**（archetype とは別軸・型数はセクション別）。選択は**算術せず表を読むだけ**: ① `data-columns`（正規化後）と
  `navPosition` を確定 → ② §12.1.2 の**オフセット表**（共有）で offset(0〜5) → ③ **§12.1.3 の該当セクション割り当て表**（GALLERY/MENU/HERO/ABOUT=6型mod6／SNS=3型mod3・offset 行→ (idxA,idxB,idxC)）
  → ④ 各案の該当容器に `pool[index]` のマーカーを付け対応 CSS を含める。マーカーは**実際に異なる grid/flex** を伴わせる（飾りにしない）。プールは
  **HERO（6型）**=`full`/`split`/`band`/`overlap`/`center-scroll`/`panel-band`（`.m-hero` の `data-hero`・型に整列シグネチャ(justify/align/text)が付随し案間相違＝6型で全distinct）、
  **GALLERY（6型）**=`pat-grid`/`pat-wide`/`pat-mosaic`/`pat-slider`/`pat-masonry`/`pat-tab-grid`（`.m-gallery`・pat-masonry=段組み高さ不揃い／pat-tab-grid=カテゴリタブ＋3列タイルグリッド・クリック切替）、
  **ABOUT（6型）**=`img-left`/`img-right`/`img-top`/`img-overlap`/`img-circle`/`img-zigzag`（`.m-about`）、
  **MENU（6型・KLK-044/045/046）**=`pat-cards`/`pat-list`/`pat-zigzag`/`price-table`/`tab-switch`/`feature-large`（`.m-menu`・price-table=価格表/料金プラン型・表形式 grid／tab-switch=カテゴリタブ切替型・タブ行＋パネル／feature-large=大画像＋詳細型・横長大画像＋詳細パネル）、
  **SNS（6型・mod6・KLK-049/050）**=`sns-grid`/`sns-slider`/`sns-cards`/`sns-masonry`/`sns-reels`/`sns-feed`（`.m-sns`・sns-grid=正方サムネ格子／sns-slider=横スクロールフィード／sns-cards=画像+キャプ+本文30字の横並び共通カード(VOICE同系)／sns-masonry=大小混在ベントー／sns-reels=縦長9:16リール帯／sns-feed=埋込風投稿カード縦列・実埋め込み禁止アタリ色面）。overlap/img-overlap=重なり型・center-scroll/panel-band=大型MV・img-circle=円形・img-zigzag=左右交互複数段。
  **offset0（1col×top）は各プール (index0,1,2)＝従来の archetype 既定と一致**（後方互換）。同一指示書＝同一割り当て・3案 distinct（連続3窓 mod N）。未選択は no-op。単案は idxA。
- **VOICE/FLOW/STAFF の内部型プール（KLK-029/035・DRAFT_RULES §12.1.2）**: これら3セクションが `sections` にあるときは、案ごとに
  **型プール（各6型）から型を選ぶ**（archetype とは別軸・§12.1.1 は不変・3セクションは常に同数）。選択は**算術せず表を読むだけ**で決める:
  ① ルートの `data-columns`（正規化後）と `navPosition` を確定 → ② **オフセット表**（`data-columns`×`navPosition`→offset 0〜5）で
  1セルを読む → ③ **割り当て表**（offset 行→ (idxA,idxB,idxC)）を読む → ④ 各案の容器 `.m-voice`/`.m-flow`/`.m-staff` に
  `pool[index]` のマーカーを付け、対応 CSS を `<head>` に含める。プール（index0〜5）は
  **VOICE**=`voice-cards`/`voice-quote-stack`/`voice-feature`/`voice-two-col`/`voice-slider`/`voice-zigzag`、
  **FLOW**=`flow-row`/`flow-timeline`/`flow-number-card`/`flow-arrow-band`/`flow-vertical-split`/`flow-zigzag`、
  **STAFF**=`staff-grid`/`staff-hscroll`/`staff-feature`/`staff-list`/`staff-two-col`/`staff-zigzag`（各マーカーは**実際に異なる grid/flex/order**
  を伴う・飾りにしない）。**同一指示書＝同一割り当て**（キー2値は全案不変で決定的）・**3案で型が相違**（連続3窓 distinct）。
  未選択セクションは no-op（出さない）。単案（`variants:1`）は idxA のマーカーで1型のみ。
- **参考準拠（KLK-034・DRAFT_RULES §12.2/§5.1）**: `references.thumbnails` が1件以上ある指示書では**案Aを参考準拠案**に
  する（対象は **thumbnails[0] のみ**）。①**レイアウト**: `thumbnails[0].sectionLayouts` の各値を §12.2 の**席替え規則**で
  反映する（案A=参考の型。既定でその型を持つ案があればその案は案Aの既定型へ。キー省略/`"other"`/語彙外は従来のまま。
  等値比較のみ・算術しない）。②**配色**: `references.colorSource:"reference"`（既定）なら案Aの `--m-main`（＋colors[1]→
  `--m-accent`）を **§5.1 の7カテゴリ→hex表**で決める（マルチカラーは指定色へフォールバック）。`"specified"` なら配色は
  従来のまま。③**マーカー**: 案Aルートに `data-ref-id`/`data-ref-colors`（案B/C には付けない）、compare.html の案Aカードに
  `.ref-badge`「参考準拠: {label}（{id}）／参考は着想のみ・そっくり再現はしません」。`references` の拡張キーが無い指示書は
  全て従来どおり（後方互換）。
- **番地ラベル（全案共通）**: 各セクションに `.addr > .pin`。既定は NAV-01 / MV-01 / ABOUT-01 / MENU-01 / GALLERY-01 /
  FOOTER-01 の6種。
- **本文セクション選択（KLK-022・DRAFT_RULES §2.1）**: `NAV-01`/`MV-01`/`FOOTER-01` は**常時必須**。本文は
  `instruction.sections`（**無指定は ABOUT/MENU/GALLERY**）で**選ばれたセクションだけ**を canonical順に、各自の `{KEY}-01`
  番地つきで出す（語彙14種＝NEWS/ABOUT/MENU/PRICE/GALLERY/SEARCH/FLOW/VOICE/STAFF/FAQ/SNS/ACCESS/CTA/CONTACT）。
  **`layout.navPosition`** が `top`（既定）なら NAV-01 を MV-01 の上、`below-hero` なら下に置く。**SNS/地図は外部依存ゼロの
  ため実埋め込み・実地図を出さずアタリ色面**にする（§1）。**CTA** は `sectionOptions.CTA.purpose`（label優先）で見出し・
  ボタン文言を可変にする（contact/order/reserve/document/signup/custom・§2.1）。**複数案は全案で同じ sections/navPosition**
  （中身を揃え、配色・レイアウト型だけ振る）。
- **アタリ画像**: a方式（色面＋`.desc`＋`.kw`。HERO は `.atari-tag`。キーワード未定は `.desc` のみ）。
  **REQ-104 b方式（KLK-020・MV-01 限定）**: `atari:"free-photo"` かつ `mvPhoto.file` 供給時は **MV-01 のアタリのみ**を
  出力フォルダ同梱の**相対** `<img src="assets/mv.<ext>">` で実写真化する（他枠は a方式・DRAFT_RULES §3.1）。未供給・
  ステージング画像の読込失敗時は MV-01 も a方式へフォールバック。`variants≥2` は同じ画像を全案共通で MV-01 に入れる。
- **仮文言**: 業種（`industry.resolved`）・テイスト（`taste`）に合った実文言。ダミー禁止。未定は `(要検討: …)`。
  **指定コピー優先（KLK-024・DRAFT_RULES §4.1）**: `copy.mvCatch`/`copy.mvLead` があるときは MV-01 の
  キャッチ/リードに**その文言をそのまま**使う（言い換え禁止・改行 `\n` は `<br>` に変換して行組を保持・
  HTMLエスケープして埋め込む・複数案でも全案共通）。無指定のフィールドのみAIが提案する。
  **セクション文言も同様（KLK-027・§4.2）**: `sectionOptions.{KEY}.heading` は該当セクションの見出し（h2）に
  そのまま、`sectionOptions.{KEY}.lead` は見出し直下の `<p class="sec-lead">`（`\n`→`<br>`）として反映する。
  無指定セクションは `.sec-lead` を出さずAI提案のまま。CTA の purpose/label とは独立に併用できる。
  **詳細誘導ボタン（KLK-048・§4.3）**: `sectionOptions.{KEY}.moreLink`（`{label, href?}`）があるセクション（本文のみ・NAV/MV/FOOTER除く）は、
  内容末尾に共通 `<div class="sec-more"><a class="sec-more-btn" href="{href省略時#}">{label} ＞</a></div>` を出す（`.sec-more` は中央・上余白広め margin-top≈40px）。
  **無指定は出さない（opt-in）**・外部URL禁止・label はエスケープ。MENU `feature-large` は §4.3 のとおり `.sec-more` を常設（moreLink 無くても既定ラベルで出す）。
- **印刷CSS / 出現アニメ / レスポンシブ**: DRAFT_RULES §6〜§8 のとおり（`@media print` で補助非表示・`IntersectionObserver`・
  `@media (max-width:640px)`・モバイルファーストで `.m-aside` を本文の後ろに畳む §8）。
- **成否の把握（一部失敗・U-G）**: 各案の生成が成立したかを案ごとに把握する。成功した案のみ letter を成功順に a→b→c で
  確定し、**失敗案は保存も参照もしない**。失敗があれば手順4で `compare.html` の `.partial-note` に焼き込み、手順5で報告する。
- **比較ハブ `compare.html`（`variants≥2` のみ・DRAFT_RULES §13）**: 成功案が2件以上のとき、案切替（隠しラジオ
  `type="radio" name="variant"` ＋ 兄弟結合子 `#ra:checked ~ .canvas #paneA{display:block}` の **CSS-only**）・各 `.pane` の
  相対 `<iframe src="index-{letter}.html">`・サムネイル `.thumbstrip`/`.vthumb`・原寸別タブ
  `<a href="index-{letter}.html" target="_blank">`・`@media print`（chrome 非表示）を備えた**単一ファイル・外部依存ゼロ**の
  比較ハブを書く。iframe・原寸リンクとも**同ディレクトリ相対 `.html` のみ**（外部URL 0）。`variants:1` では作らない。
  - **🔄 セクション再生成コントロール（REQ-103・KLK-012・additive）**: `compare.html` の toolbar 近傍に、番地 `<select>`＋
    「🔄 このセクションを再生成」ボタンと、ルート要素の `data-folder="mockups/{日付}_{案件名}"`、`</body>` 直前の health-gated
    インライン fetch（`GET /health` 約800ms → 成功で checked ラジオの letter＋番地を `POST http://127.0.0.1:8765/regenerate` へ・
    非稼働時は無効化して手動 `/draft-regenerate` を案内・localhost fetch のみで外部URL 0）を焼き込む（DRAFT_RULES §13/§14）。
    既存の隠しラジオ／iframe／サムネイル／`@media print` 構造は変えない（additive）。

### 4. 保存とフォルダ自動オープン

DRAFT_RULES §9 に従い **Claude Code が Write** で保存する（保存分岐は `output.variants`）:

- フォルダ: `mockups/{YYYY-MM-DD}_{案件名}/`（案件名＝`meta.project` をパス安全化: 前後空白除去 → 空白を `_` →
  `/ \ : * ? " < > |` と制御文字を除去。空なら `untitled`）。
- **保存ファイル（`output.variants` 分岐・成功案のみ）**:
  - `variants:1`（後方互換）: `mockups/{…}/index.html`＝デザインラフ本体（1案）。`compare.html` は作らない。
  - `variants≥2`: 成功案ぶんの `mockups/{…}/index-a.html`／`index-b.html`／`index-c.html`（成功順 a→b→c）＋ 比較ハブ
    `mockups/{…}/compare.html`（DRAFT_RULES §13）。
- `mockups/{…}/instruction.json`＝入力の生成指示書の写し（そのまま保存し、再実行・監査を可能にする）。**一部失敗時も
  必ず保存する**（SPEC §7・入力を失わない）。
- **MVフリー実写真の同梱（REQ-104 b方式・KLK-020・MV-01 限定）**: `atari:"free-photo"` かつ `mvPhoto.file` 供給時、
  ステージング画像 `mockups/.uploads/{mvPhoto.file}` を出力フォルダの `assets/mv.<ext>`（拡張子は元ファイル準拠）へ
  **コピー**し、各案（全案共通）の MV-01 アタリを相対 `<img src="assets/mv.<ext>">` にする（DRAFT_RULES §3.1）。
  `mvPhoto.file` は **basename のみ・安全名**（`^[A-Za-z0-9][A-Za-z0-9._-]*$`・`..`／絶対パス／パス区切りを拒否）を確認し、
  **`mockups/.uploads/` 配下からのみ読む**（多層防御・ブリッジ側 `validate_instruction` も同名を再検証）。ステージング画像が
  無い／読めないときは MV-01 を a方式で出力し、手順5で「MV 実写真を反映できず a方式にした」旨を報告する。`assets/` も
  `mockups/` 配下のためGit除外（機密＝実写真は追跡対象に入らない）。
- **一部失敗（U-G）**: 失敗案のファイルは作らず `compare.html` からも参照しない。失敗があれば `compare.html` の
  `.partial-note` に「案Xの生成が一部失敗したため成功案のみ表示／設定を変えて再生成できます」を焼き込む。
- `mockups/` はGit除外（`.gitignore` 3ファイルに登録済み）。案件名・生成物はコミットされない。
- **フォルダ自動オープン（REQ-010残り・U-D）**: 保存完了後、Claude Code（本スキル）が保存先フォルダを OS 別コマンドで開く。
  - mac: `open '{絶対パス}'` / win: `explorer '{パス}'`（または `start "" '{パス}'`）/ linux: `xdg-open '{パス}'`。OS を判定して選ぶ。
  - **フォールバック**: 開けない・非対応・失敗時は**保存先パスを報告に表示**する（SPEC §7「フォルダが開けない場合は
    保存先パスを表示」）。**ブラウザ単独では不可**（サンドボックス）。比較画面のダミーボタンでは実現しない。

### 5. 報告（非エンジニア向け）

- 保存先パス（`mockups/{日付}_{案件名}/`）と、フォルダを自動で開いた旨（開けなかった場合はパスを案内）。
- 生成した**案数と各案の配色方向**（案A＝指示書に忠実／案B＝濃色高級／案C＝明色ポップ）。
- 生成したセクションの番地ラベル一覧（NAV-01〜FOOTER-01・全案共通）。
- `(要検討: …)` で残した箇所の一覧（人間が後で埋める箇所）。
- MV 実写真の反映有無（`atari:"free-photo"`＋`mvPhoto.file` を `assets/mv.<ext>` に同梱し MV-01 を相対 `<img>` にした／
  未供給・読込失敗で MV-01 を a方式にした）。その他の除外した外部参照があれば併記する。
- **一部失敗があれば**その案と、`compare.html` に失敗を明示した旨・SCR-001 で設定を変えて再生成できる導線。
- 開き方: **複数案は `compare.html`**（案A/B/C を切り替え・サムネイルの「原寸 ↗」で各案を別タブ表示）、**1案は `index.html`**
  をブラウザで開く（ダブルクリック・印刷プレビューで補助表示が消え PDF 化できる）。高品質PDFは各案の原寸別タブから印刷する。

## してはならないこと

- 受付チェックを飛ばして、不足項目を会話の文脈から推測で補って生成すること。
- 外部リソース（CDN・外部CSS/JS・Webフォント・外部画像URL）に依存するHTMLを生成すること。
- アタリ画像に `<img src>` や実写真URLを使うこと（a方式＝色面のみ）。**例外**: REQ-104 使用時の **MV-01 のみ**、
  出力フォルダ同梱の**相対** `<img src="assets/…">` を許可する（KLK-020・DRAFT_RULES §3.1。外部 http(s) 画像URL は依然禁止）。
- 部分再生成の**エンジン**（REQ-103・番地指定でセクションを作り直す処理そのもの）を本スキルで実装すること（それは新スキル
  `/draft-regenerate`・KLK-012 の責務）。本スキルは `compare.html` に🔄トリガー導線を焼き込むのみ（DRAFT_RULES §13/§14）。
  見本URL反映（REQ-102）は本スキルで実装しない（別チケット）。フリー実写真 b方式（REQ-104）は **MV-01 限定で実装済み**
  （KLK-020・アップロード画像を `assets/` へ同梱し MV-01 を相対 `<img>` に・DRAFT_RULES §3.1・手順4）。
- 案間でカラム骨格・番地・セクション構成を変えること（案間の差は**配色テーマ主軸**に限る・DRAFT_RULES §12）。
- `compare.html` の iframe・原寸リンクに外部URLや案別ファイル以外を指定すること（同ディレクトリ相対 `.html` のみ）。
- 失敗案のファイルを保存・比較ハブから参照すること（成功案のみ・`.partial-note` で失敗通知）。
- 実在の顧客名・個人情報・シークレットを生成HTMLに含めること。
- 参考準拠（KLK-034・DRAFT_RULES §12.2）で参考の**画像・実文言**を参照・模写すること（受け取るのはタグ＝型マーカーと
  配色カテゴリのみ）。収集見本（`source:"ref"`）は第三者著作物であり、**着想の反映に限る**（1:1 の複製・実在サイトの
  文言流用の禁止）。
