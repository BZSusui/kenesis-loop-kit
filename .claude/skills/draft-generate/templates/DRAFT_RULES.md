# DRAFT_RULES.md — デザインラフHTML生成規約

> このファイルは `/draft-generate` スキル（`.claude/skills/draft-generate/SKILL.md`）が従うマスター規約です。
> 生成される**デザインラフHTML（各案）**はこの規約に完全準拠すること。見た目・構造の正は
> `docs/wireframes/SCR-002-compare.html` の `.mock` 部（プレビュー本体）と、比較ハブ chrome（案切替バー・サムネイル・
> partial-note・@media print）。生成前に必ず本ファイルを全読する。
>
> 入力契約 = 生成指示書JSON（`schema:"design-draft-instruction"` / `version:1`・`docs/designs/KLK-006.md` §4.4）。
> 対応要件 = REQ-005 / 006 / 007 / 008（複数案・比較画面）/ 009 / 010（保存・フォルダオープン部分）/ 011・
> NFR-002 / 003 / 004 / 005 / 006。

---

## 0. 生成物の位置づけ

- デザインラフ＝**ワイヤーフレームとデザインモックの中間物**。完成イメージ（配色・レイアウト・アタリ画像配置・
  仮文言・スクロール出現アニメ）を非エンジニアが確認・印刷できる単一HTML。
- 本スキルは生成指示書の **`output.variants`（1〜3）に応じて最大3案**を一括生成する（REQ-008）。各案は独立した
  単一HTML（`variants:1` は `index.html`、`variants≥2` は `index-a.html`/`index-b.html`/`index-c.html`）で、
  **配色テーマとレイアウト原型（`data-archetype`）を両振りする**（振れ幅規約は §12/§12.1・カラム数や番地は全案共通）。複数案のときは案を切り替えて
  見比べる**比較ハブ `compare.html`**（SCR-002・構造規約は §13）を併せて生成する（`variants:1` は比較ハブなし）。
- 一部の案が失敗しても**成功案のみ**を保存・表示し、`compare.html` の `.partial-note` に失敗を焼き込んで通知する
  （REQ-008 失敗時挙動・§12・SKILL 手順4/5）。入力の写し `instruction.json` は常に保存する。
- **別チケット（本スキルでは実装しない）**: 部分再生成 REQ-103（🔄 セクション単位の作り直し）・見本URL反映 REQ-102。
- **REQ-104 フリー実写真 b方式は MV-01 限定で実装済み（KLK-020）**: `atari:"free-photo"` かつ `mvPhoto.file` 供給時のみ、
  **メインビジュアル（MV-01）のアタリだけ**をアップロード画像で実写真化する（**出力フォルダへ同梱・相対 `<img>`**・§3/§1/§12）。
  他のアタリ枠は常に a方式。画像未供給・読込失敗は MV-01 も a方式へフォールバックする。外部 http 画像URL の埋め込みは依然禁止。

---

## 1. 単一ファイル・外部依存ゼロ（NFR-005）

- **単一の静的HTMLファイル**。CSSは `<head>` 内の `<style>`、スクロール出現アニメJSは `</body>` 直前の
  インライン `<script>` に書く。
- **禁止**: `<link rel="stylesheet">`・`<script src="…">`・`@import`・Webフォント（`fonts.googleapis.com` /
  `fonts.gstatic.com`）・CDN（`cdn.*` / `unpkg.com` / `jsdelivr` 等）・外部画像URL（`<img src="http…">`）。
- アイコン・図はUnicode文字（絵文字等）またはインラインSVGで表現する。**アタリ画像は色面のみ**（`<img>` を使わない・§3）。
- **例外（REQ-104 使用時のみ・KLK-020）**: `atari:"free-photo"` かつ `mvPhoto.file` 供給時、**MV-01 のアタリに限り**
  出力フォルダ同梱の**相対** `<img src="assets/mv.<ext>">` を使ってよい（**相対参照のみ**。`http(s)://` の外部 img は依然禁止）。
  同梱画像はフォルダ内で自己完結し、外部URL 0件の原則は維持される。
- 外部URL参照は 0 件（`www.w3.org` / `example.com` `.org` `.net` のみ例外）。実在の顧客名・案件名・URL・
  シークレット（api key / secret / password / token / private key）を含めない（NFR-004 / REQ-011）。

---

## 2. 番地ラベル（REQ-005・部分再生成 REQ-103 の基盤）

各セクションを `.sec`（`position: relative`）で囲み、その左上に番地ラベル `.addr > .pin` を付ける（**画面のみ表示・
印刷では非表示**・§6）。ラベルは以下の6種を各1回、対応セクションに付与する。

| 番地 | セクション |
|---|---|
| `NAV-01` | グローバルナビ |
| `MV-01` | メインビジュアル |
| `ABOUT-01` | コンセプト・紹介 |
| `MENU-01` | メニュー・料金 |
| `GALLERY-01` | ギャラリー・実績 |
| `FOOTER-01` | フッター（CTA＋ナビ） |

```html
<div class="sec">
  <div class="addr"><span class="pin">MV-01</span></div>
  ...
</div>
```

- SCR-002 の `.regen`（🔄 再生成ボタン）は**部分再生成が別チケット（REQ-103）のため本チケットでは省略**する
  （番地ラベル＝`.pin` のみで足りる）。
- 番地は業種・レイアウトに応じて増減してよいが、上記6種は基本セット。増やす場合は `SECTION-01` の連番規約に従う。
- **本文セクションを人間が選ぶ場合（KLK-022・§2.1）**: `NAV-01`／`MV-01`／`FOOTER-01` は**常時必須**、本文は
  `instruction.sections`（無指定は `ABOUT/MENU/GALLERY`）で**選ばれたセクションだけ**を各自の `{KEY}-01` 番地つきで出す。

### 2.1 本文セクション選択とヘッダー位置（KLK-022・中身の器）

生成する本文コンテンツを**人間が SCR-001 で選択**できる。生成側は生成指示書の指定を**忠実に反映**する
（レイアウトの型で振るのは別軸＝KLK-023）。

**入力（生成指示書・後方互換の既定つき）:**
- `layout.navPosition`: `top`（既定・MV上）／ `below-hero`（MV下）。**無指定は `top`**。
- `sections`: 出す本文セクションの配列（下の enum・**canonical順**）。**無指定は `["ABOUT","MENU","GALLERY"]`**（従来互換）。
- `sectionOptions`: セクション個別設定（現状 `CTA` のみ）。**無指定は `{}`**。

**セクション語彙（14種・canonical生成順・各 `{KEY}-01` 番地・a方式プレースホルダ）:**

| 順 | KEY | 番地 | 見出し例 | 中身（外部依存ゼロのアタリ＋仮文言） |
|---|---|---|---|---|
| 1 | NEWS | `NEWS-01` | お知らせ | 日付つきリスト（仮文言） |
| 2 | ABOUT | `ABOUT-01` | CONCEPT | アタリ＋紹介文（§3 a方式） |
| 3 | MENU | `MENU-01` | MENU / SERVICE | カード群（アタリ＋名称＋価格） |
| 4 | PRICE | `PRICE-01` | PRICE | プラン比較の表（仮） |
| 5 | GALLERY | `GALLERY-01` | GALLERY | アタリのグリッド |
| 6 | SEARCH | `SEARCH-01` | SEARCH | 条件検索フォーム面（**静的**・入力欄は飾り・送信なし） |
| 7 | FLOW | `FLOW-01` | FLOW | ステップ ①→②→③ |
| 8 | VOICE | `VOICE-01` | VOICE | お客様の声カード（アタリ＋コメント） |
| 9 | STAFF | `STAFF-01` | STAFF | 人物カード（アタリ＋肩書） |
| 10 | FAQ | `FAQ-01` | FAQ | Q&A 積み上げ（抜粋→誘導文） |
| 11 | SNS | `SNS-01` | SNS | 埋め込み**枠**のアタリ面（**実埋め込み禁止**・外部URL 0・NFR-005） |
| 12 | ACCESS | `ACCESS-01` | ACCESS | 地図の**アタリ面**（実地図禁止）＋住所・営業時間 |
| 13 | CTA | `CTA-01` | （誘導） | 見出し＋ひとこと＋ボタン（**目的で文言可変**・下記） |
| 14 | CONTACT | `CONTACT-01` | CONTACT | お問い合わせ誘導（ボタン/リンク） |

- **並び順**: v1 は上の canonical 順のうち**選ばれた分だけ**。案ごとの並び替え・型振りは KLK-023。
- **VOICE/FLOW/STAFF の内部型**: これら3セクションは案ごとに5型プールから型を選ぶ（§12.1.2・KLK-029）。ここの語彙行は
  セクションの**有無**の器のみを定義し、内部レイアウトの型振りは §12.1.2 の表引きで決める。
- **ヘッダー位置**: `navPosition:top` は `NAV-01` を `MV-01` の**上**、`below-hero` は **下**に置く（番地文字列は不変）。
- **SNS/地図の制約**: 外部依存ゼロ（§1・NFR-005）のため実埋め込み・実地図は不可。アタリ色面で「ここに入る」を示す。

**CTA 誘導先（`sectionOptions.CTA.purpose` → 既定ボタン文言。`label` があれば優先）:**

| purpose | 既定ボタン文言 |
|---|---|
| `contact` | お問い合わせはこちら |
| `order` | ご注文はこちら |
| `reserve` | ご予約はこちら |
| `document` | 資料を請求する |
| `signup` | 友だち追加・会員登録 |
| `custom` | `label` の自由入力テキストをそのまま使う（動的値は `textContent` 相当＝注入対策） |

- CTA選択かつ purpose 未指定 → 業種から無難な誘導（既定 `お問い合わせはこちら`）。
- `sections` に無い KEY の `sectionOptions` は無視する。`label` は制御文字除去・過長（40字目安）を切り詰める。

**複数案（`variants≥2`）との関係**: 3案は**同じ `sections`・同じ `navPosition`**（中身は揃える＝公平比較）。案間で振るのは
配色・レイアウト型（§12/§12.1）であり、セクション集合は振らない。

---

## 3. アタリ画像 a方式（REQ-006）

写真の代わりに**配色に調和した色面プレースホルダ**を置く。実写真URL・`<img>` は使わない。

- `.atari`＝色面（`linear-gradient` + `color-mix(in srgb, var(--m-main) …, var(--m-accent) …)`）＋破線枠。
  内部に以下を持つ:
  - `.desc`＝**内容説明**（何の写真が入るか。例「スタイリストの施術風景」）。**必須**。
  - `.kw`＝**ストック検索キーワード**（`検索: <b>keyword</b>` 形式・英語キーワード）。
- **HERO の背景アタリ**は `.atari-tag`（右下の小ラベル）で「アタリ内容 / 検索キーワード」を示す（**印刷で非表示**・§6）。
- **kw 無フォールバック（REQ-006）**: 検索キーワードが定まらない箇所は `.kw` を省き `.desc` のみとする
  （例: ギャラリーのスタイル一覧）。**ゴールデンサンプルは kw 有・kw 無の両方を含む**。

```html
<div class="atari">
  <span class="ic">📷</span>
  <span class="desc">スタイリストの施術風景</span>
  <span class="kw">検索: <b>hair stylist working</b></span>
</div>
<!-- kw 無フォールバック -->
<div class="atari"><span class="ic">📷</span><span class="desc">ボブ</span></div>
```

### 3.1 MV-01 フリー実写真 b方式（REQ-104・KLK-020・MV-01 限定）

`atari:"free-photo"` かつ `mvPhoto.file` 供給時は、**MV-01（HERO）のアタリのみ**を実写真（相対 `<img>`）にする。
**他のアタリ枠（NAV / ABOUT / MENU / GALLERY / FOOTER・および MENU 等の枠内アタリ）は常に a方式**。
`mvPhoto` 未供給・ステージング画像が読めない場合は **MV-01 も a方式へフォールバック**（SPEC §7「失敗要素は除外して継続」）。

- スキルが `mockups/.uploads/{mvPhoto.file}` を出力フォルダの `assets/mv.<ext>` へコピーし（SKILL 手順4）、
  MV-01 のアタリを**相対** `<img class="mv-photo" src="assets/mv.<ext>" alt="{業種}のメインビジュアル">` に差し替える。
- テキスト（キャッチコピー・CTA）の可読性のため、`<img>` の上に半透明オーバーレイを重ねる。`.atari-tag`（検索KWラベル）は
  実写真が入るため**省いてよい**。**外部 http(s) 画像URLは使わない**（相対同梱のみ・§1 の例外条項）。
- `variants≥2` のときは**同じアップロード画像を全案共通**で MV-01 に相対参照する（画像コピーは1回・§12）。

```html
<!-- REQ-104 b方式: MV-01 のみ実写真（相対同梱・他枠は a方式） -->
<div class="sec">
  <div class="addr"><span class="pin">MV-01</span></div>
  <div class="m-hero mv-hero">
    <img class="mv-photo" src="assets/mv.jpg" alt="美容室のメインビジュアル">
    <div class="mv-overlay"></div>
    <h1 class="catch">…</h1><p class="lead">…</p><span class="hero-cta">…</span>
  </div>
</div>
```

---

## 4. 仮文言（REQ-007・ダミーテキスト禁止）

- 業種（`industry.resolved`）・テイスト（`taste`）に合った**実キャッチコピー・見出し・本文**を書く。
- **禁止**: 「サンプルテキスト」「テキストテキスト」「aaa（連続a）」「lorem ipsum」等の無意味な埋め草。
- 決めきれない箇所（顧客固有情報＝開業年数・在籍数・こだわり設備など）は
  `<span class="todo">(要検討: …)</span>` で明示する（**丸括弧の中に「要検討:」＋補足**）。
- 実在の個人名・顧客名・住所・電話番号・メールアドレス・シークレットは書かない。案件名は生成指示書 `meta.project`
  のプレースホルダのみ。

### 4.1 指定コピー（KLK-024・`copy.mvCatch` / `copy.mvLead`・MV-01 限定）

コピー確定済みの案件（リニューアル等）では、生成指示書の **`copy`** に指定された文言を**そのまま**使う
（AIが言い換え・要約・追記をしない）。無指定のフィールドは従来どおり §4 本則でAIが提案する。

- **`copy.mvCatch`**（最大60字・改行可）→ MV-01 の**キャッチコピー**（`.catch`）にそのまま反映。
- **`copy.mvLead`**（最大200字・改行可）→ MV-01 の**リード文**（`.lead`）にそのまま反映。
- **改行の保持**: 入力の改行（`\n`）は **`<br>` に変換**して行組を保持する（キャッチが1行か2行かで紙面の印象が
  大きく変わるため・KLK-024 の核）。
- **エスケープ（注入対策）**: 指定文言は **HTMLエスケープして埋め込む**（`<` `>` `&` を実体参照へ・textContent 相当）。
  タグやスクリプトとして解釈させない。
- **複数案共通**: `variants≥2` でも**全案同じ copy**（中身は揃える・§12。配色・レイアウト型は従来どおり案別に振る）。
- **後方互換**: `copy` キーが無い instruction は従来どおり（§4 本則のAI提案）。`copy` は指定があるときのみ
  instruction に現れる（KLK-020 `mvPhoto` と同型・SCR-001/ブリッジ側で 60/200字切詰め・改行以外の制御文字は除去/拒否）。
- 部分再生成（§14）で MV-01 を作り直す場合も、対象フォルダの `instruction.json` に `copy` があればそれを尊重する。

### 4.2 セクション見出し・リード文の指定（KLK-027・`sectionOptions.{KEY}.heading` / `.lead`）

選択セクション（§2.1）ごとに見出し・リード文を事前指定できる。指定があれば §4 本則のAI提案より優先し
**その文言をそのまま**使う（クライアントワイヤーの文言をそのまま写す用途）。

- **`sectionOptions.{KEY}.heading`**（最大40字・1行）→ 該当セクションの**見出し（`.m-sec h2` 等）にそのまま**反映。
  小ラベル `.en` は従来どおりAIが補う。
- **`sectionOptions.{KEY}.lead`**（最大200字・改行可）→ 見出しブロック直下に **`<p class="sec-lead">`** として出力
  （`\n`→`<br>` で行組保持）。**無指定のセクションには `.sec-lead` 自体を出力しない**（additive・従来出力は不変）。
- **エスケープ（注入対策）**: §4.1 と同じく HTMLエスケープして埋め込む（textContent 相当）。
- **複数案共通**: `variants≥2` でも**全案同じ**見出し・リード（§12。配色・レイアウト型は案別のまま）。
- **後方互換**: `heading`/`lead` が無い sectionOptions は従来どおり（CTA の `purpose`/`label`＝§2.1 とは**独立に併用可**・
  同一オブジェクトに同居する）。`sections` に無い KEY への指定は無視する。
- 部分再生成（§14）で対象セクションを作り直す場合も、`instruction.json` の該当 `sectionOptions` を尊重する。

---

## 5. 配色マッピングと autofill 補完（U5）

生成指示書 `colors`（`main` 必須・`sub`/`accent`/`bg` は任意で `null` 可・`autofill` に null 役割名を列挙）を
SCR-002 mock テーマ変数へ写す。**生成ルート要素（`.mock` 等）の `style` または `:root` に5つのCSS変数を定義し、
本体はすべて `var(--m-*)` で参照**する（主要色の直値散在を禁止・S2）。

| 指示書 `colors` | mock テーマ変数 | 役割 | autofill（null）時の補完ルール |
|---|---|---|---|
| `main`（必須） | `--m-main` | 主色（見出し・HERO地・アクセント面） | （必須のため補完なし） |
| `sub` | `--m-nav` | ナビ／フッター地（濃色） | null → `color-mix(in srgb, var(--m-main) 62%, #000)`（主色を暗くした濃色） |
| `accent` | `--m-accent` | CTA・強調・アタリ差し色 | null → 主色と調和する暖色アクセント（例 `color-mix(in srgb, var(--m-main) 45%, #E8A33D)`） |
| `bg` | `--m-bg` | 背景 | null → `color-mix(in srgb, var(--m-main) 6%, #fff)`（主色の極淡ティント＝オフホワイト） |
| （指示書に無し） | `--m-text` | 本文文字色 | `--m-bg` の明度で自動決定（明背景→`#333` / 暗背景→`#fff`）。純黒 `#000` は使わない |

- `colors.mode`（`explicit` / `main-only` / `pasted`）に関わらずマッピングは同一。`main-only` は sub/accent/bg が
  すべて `autofill` に入るので3補完ルールが全適用される。
- CSS変数化により配色4色が確実に反映され、テストで検証可能になる（S2）。

```html
<div class="mock" data-columns="1col"
     style="--m-main:#2e7d6b; --m-nav:#24463e; --m-accent:#e8a33d; --m-bg:#f7f5f0; --m-text:#333;">
```

### 5.1 参考配色の7カテゴリ→hex 変換表（KLK-034・案A限定・決定的）

`references.colorSource:"reference"` かつ `references.thumbnails[0].colors`（7カテゴリ・1..3件）があるとき、
**案Aに限り** §5 の入力を次の**明示表**で差し替える（表を読むだけ・算術しない・§12.1.2 と同じ決定性原理）:

| 7カテゴリ | hex | トーンの意図 |
|---|---|---|
| グリーン | `#2E7D6B` | 深緑（ワイヤーSCR-002 案Aの基準緑） |
| ブルー | `#2C5F8A` | 落ち着いた紺青 |
| レッド | `#B3402F` | 朱寄りの赤（彩度を上げすぎない） |
| ゴールド | `#C6A15B` | ワイヤー案Bの金 |
| ピンク | `#E86FA0` | ワイヤー案Cの桃 |
| モノトーン | `#444850` | 墨色 |
| マルチカラー | （表引きしない） | 下のフォールバックへ |

- `colors[0]` → 案A `--m-main`。`colors[1]`（あれば）→ 案A `--m-accent`。`colors[2]` は反映しない。
- `sub`/`bg`/`--m-text` は §5 の autofill 規則をそのまま適用する（main 起点の color-mix）。
- **マルチカラー（単独指定のみ・§2規約）のフォールバック**: 表引きせず**指示書の指定色（従来の案A忠実・§12）**へ
  退避し、実効の配色ソースを `"specified"` として扱う（案Aルートの `data-ref-colors="specified"`・§12.2 と
  compare.html の注記にその旨を出す）。
- `references.colorSource:"specified"` のとき配色は従来どおり（レイアウトだけ §12.2 で参考準拠）。
- **案B/C の配色は常に従来どおり**（指示書 `colors.main` 起点の濃色/明色・§12）。案間 `--m-main` 相違の不変条件は
  維持する（万一表引き hex と案B/C の派生色が一致する場合は、案B/C 側の派生で必ずずらす＝§12 既存要件）。
- `colorSource` が無い・`thumbnails` が無い指示書は本節不発（従来どおり・後方互換）。

---

## 6. 印刷CSS（@media print・REQ-009 / NFR-003）

印刷（PDF化）時は**補助表示を隠し、デザイン本体（nav / HERO / セクション）は残す**。`<style>` に必ず次を含める:

```css
@media print {
  .addr, .atari-tag, .anim-note { display: none !important; }
  body { background: #fff; }
  .mock { box-shadow: none; border-radius: 0; }
  .reveal { opacity: 1 !important; transform: none !important; } /* 出現アニメ対象を全表示 */
}
```

- 隠す対象＝番地ラベル `.addr`・HERO の `.atari-tag`・注記 `.anim-note`（補助注記）。
- 出現アニメの対象（`.reveal`）は印刷時に必ず全表示にする（§7）。

---

## 7. スクロール出現アニメ（REQ-005 / U6・外部依存ゼロ）

**アニメON/OFF の分岐（`output.animation`・KLK-008 §4.3）**: 生成前に生成指示書 `output.animation` を判定する。
**既定は true（未指定時も ON）**。

- **`output.animation !== false`（ON・既定）**: 下記のとおり対象セクションに `.reveal` を付け、`<style>` に
  `.reveal{opacity:0;…}` ＋ `.reveal.in{…}`、`</body>` 直前に `IntersectionObserver` の `<script>` を出力する。
- **`output.animation === false`（OFF）**: `.reveal` クラス・`.reveal{opacity:0;transition:…}` のCSS・
  `IntersectionObserver` の `<script>` を**いずれも出力しない**。全セクションは初期状態で完全表示（`opacity:1`）にする。
  `@media print` のアニメ全表示行（`.reveal{opacity:1…}`）は `.reveal` 自体が無いので**不要（省略可）**。他の印刷CSS
  （`.addr`/`.atari-tag`/`.anim-note` の `display:none`）は**アニメと無関係に常に出力**する。OFF 時の姿の実例＝ゴールデン
  `tests/fixtures/klk008/sample-anim-off.html`。

以下は **ON（既定）時**の実装。外部ライブラリ・CDNを使わず、**インラインJSの `IntersectionObserver`** で実装する。
対象セクションに `.reveal` を付け、可視化時に `.in` を付与してフェードイン。graceful degradation を必ず備える。

```html
<style>
  .reveal { opacity: 0; transform: translateY(16px); transition: opacity .6s ease, transform .6s ease; }
  .reveal.in { opacity: 1; transform: none; }
  @media (prefers-reduced-motion: reduce) { .reveal { opacity: 1; transform: none; transition: none; } }
  @media print { .reveal { opacity: 1 !important; transform: none !important; } }
</style>
<script>
  (function () {
    var els = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window)) {            // 非対応 → 全表示（コンテンツを隠さない）
      els.forEach(function (e) { e.classList.add('in'); });
      return;
    }
    var io = new IntersectionObserver(function (ens) {
      ens.forEach(function (x) {
        if (x.isIntersecting) { x.target.classList.add('in'); io.unobserve(x.target); }
      });
    }, { threshold: .12 });
    els.forEach(function (e) { io.observe(e); });
  })();
</script>
```

- `IntersectionObserver` 非対応環境 → 全要素即表示。`prefers-reduced-motion: reduce` / 印刷 → アニメ無効・全表示。
- SCR-002 の `.anim-note`（注記）はワイヤー用の説明なので、生成HTMLでは**実アニメに置き換える**。

---

## 8. カラム構成（REQ-002・6系統）とレスポンシブ（NFR-002）

- **カラム構成の反映**: 生成ルート要素（`.mock` 等）に `data-columns="{layout.columns の canonical 値}"` 属性を付ける。
  canonical は次の**6系統**（KLK-008 §4.1）。本文レイアウト（サイドバー位置・グリッド列数）をこの値に合わせる
  （機械検証のフック＝S8）。

| enum 値 | 系統 | サブ位置 | 骨格 |
|---|---|---|---|
| `1col` | 単一 | - | `.m-layout` を使わず NAV/HERO/本文/FOOTER を `.sec` で縦積み（全幅）。既存 `klk007` ゴールデン準拠 |
| `2col-full-left` | 全体2カラム（サイドバー全高） | 左 | `.m-layout` を**ページ全体に掛け**、`.m-main-col` に NAV/HERO/本文/FOOTER を**すべて内包**、`.m-aside` を**左列**に置き全高に立てる |
| `2col-full-right` | 全体2カラム（サイドバー全高） | 右 | 同上・`.m-aside` を**右列** |
| `2col-body-left` | 本文のみ2カラム（FV全幅） | 左 | NAV `.sec`（全幅）→ HERO `.sec`（全幅）→ `.m-layout`（本文＋サイドバー）→ FOOTER `.sec`（全幅）。**HERO は grid の外**。`.m-aside` を**左列** |
| `2col-body-right` | 本文のみ2カラム（FV全幅） | 右 | 同上・`.m-aside` を**右列**（既存 税理士事務所ラフの構造そのまま） |
| `3col` | 3分割 | 両 | 本文領域を `grid-template-columns:200px 1fr 200px`（左サブ・中メイン・右サブ）で3分割。NAV/HERO/FOOTER は本文のみ系統と同様に全幅 `.sec` |

- **全体2カラム（`2col-full-*`）と本文のみ2カラム（`2col-body-*`）の決定的な差**: 全体は `.m-layout` が **NAV/HERO を内側に含み**
  サイドバー（`.m-aside`）が HERO の横にも回る（全高）。本文のみは HERO を grid の外に出し、本文だけを2分割する。
  - 全体2カラムのグリッド例: `-right` は `.m-layout{grid-template-columns:1fr 300px}`、`-left` は `300px 1fr`。
    `.m-aside` は `position: sticky; top:0` 等で全高に見せてよい（`align-items: stretch`）。
  - 本文のみ2カラムのグリッド例: `-right` は `1fr 300px`、`-left` は `300px 1fr`（`.m-aside` を左列へ）。
- **旧値エイリアス正規化（KLK-008 §4.2・U-2）**: 生成側は入力の旧カラム値を canonical へ正規化してから `data-columns` に書く。

  ```
  2col-sub-left  → 2col-body-left
  2col-sub-right → 2col-body-right
  ```

  version:1 で作られた既存 `instruction.json`（`mockups/*`）はそのまま再現できる。`data-columns` には**正規化後の
  canonical 値**を出力する（旧値をそのまま書かない）。
- **レスポンシブ（モバイルファースト原則）**: `@media (max-width: 640px)` を必ず定義し、モバイル時に次の変形を明示する
  （SCR-002:213-223 準拠）:
  - **メインカラム優先で畳む**: 多カラム → 縦積み（`.m-layout` を `grid-template-columns: 1fr`）。**メインカラム
    （`.m-main-col`）をスマホ版の中核・先頭**に置き、**サイドバー（`.m-aside`）は二次情報として本文（`.m-main-col`）の
    後ろに畳む**。「本文の前へ回す」ことはしない（＝「または前」は採らない）。この原則は**全体2カラム（`2col-full-*`）・
    本文のみ2カラム（`2col-body-*`）・3カラム（`3col`）の全系統**に等しく適用する。メインが先頭に来ることを
    **DOM 順**（PC でもメインカラムを先に書く）**または CSS `order`**（`.m-main-col{order:0}` / `.m-aside{order:1}`）で保証する。
  - グローバルナビ → ハンバーガー相当（`.m-nav ul` を隠し `☰` を表示）。
  - ギャラリーの列を減らす（例 4列 → 2列）。
  - HERO の見出しを縮小。本文は 14px 以上を維持。
- ※ 実在ギャラリーサイトのスクレイピング等は SPEC スコープ外。本規約は上記のモバイルファースト**設計原則のみ**を定める。

---

## 9. 保存規約（REQ-010 / U4・複数案対応 U-A/U-F/U-H）

生成後、**Claude Code が Write で** 次のとおり保存する（ブラウザ保存ではない）。`mockups/` はGit除外（§11・NFR-004）。

- **日付書式**: `YYYY-MM-DD`（例 `2026-07-07`）。生成日をローカル日付で決める。
- **フォルダ**: `mockups/{YYYY-MM-DD}_{案件名}/`
  - 案件名＝生成指示書 `meta.project` を**パス安全化**する: 前後空白除去 → 内部空白を `_` に置換 →
    `/ \ : * ? " < > |` と制御文字を除去。結果が空なら `untitled` とする。
- **ファイル（`output.variants` による分岐）**:

  | `output.variants` | 生成ファイル |
  |---|---|
  | `1`（後方互換） | `index.html`（デザインラフ本体・1案）＋ `instruction.json`。**`compare.html` は作らない** |
  | `2` | `index-a.html`・`index-b.html` ＋ `compare.html` ＋ `instruction.json` |
  | `3` | `index-a.html`・`index-b.html`・`index-c.html` ＋ `compare.html` ＋ `instruction.json` |

  - `index.html`／`index-{letter}.html`＝デザインラフ本体。各案は本規約に完全準拠した**単一ファイル・外部依存ゼロ**。
  - **案別ファイルの letter は成功順に a→b→c**（最大3）。`compare.html` の iframe・原寸リンクは各案の `index-{letter}.html` を
    **同ディレクトリ相対パス**で参照する（§13）。
  - `instruction.json`＝入力の生成指示書の写し（**常に1つ・再実行・監査用**・SPEC §7）。一部失敗時も必ず保存する。
- **一部失敗（U-G）**: 生成に成功した案のみ `index-{letter}.html` を書き出し、`compare.html` に載せる。失敗案のファイルは
  作らず、比較ハブからも参照しない。失敗があれば `compare.html` に `.partial-note` を焼き込む（§13・§12）。
- **フォルダ自動オープン（REQ-010残り・U-D）**: 保存完了後、Claude Code（スキル）が保存先フォルダを OS 別コマンドで開く。
  - mac: `open '{絶対パス}'` / win: `explorer '{パス}'`（または `start "" '{パス}'`）/ linux: `xdg-open '{パス}'`。OS を判定して選ぶ。
  - **フォールバック**: 開けない・非対応・失敗時は**保存先パスを報告に表示**する（SPEC §7「フォルダが開けない場合は保存先パスを表示」）。
  - **ブラウザ単独では不可**（サンドボックスで Finder/フォルダを開けない）。比較画面（`compare.html`）にフォルダを開くダミー
    ボタンは置かない。フォルダオープンは Claude Code（スキル）の責務。

---

## 10. HTML 骨格（SCR-002 `.mock` 部を正とする参照構造）

構造・クラス名の正は `docs/wireframes/SCR-002-compare.html`（`.mock` / `.m-nav` / `.m-hero` / `.m-sec` / `.m-about` /
`.m-menu` / `.m-card` / `.m-gallery` / `.m-foot` / `.atari` / `.atari-tag` / `.addr .pin` / `.todo`）。全体2カラムの
`.m-layout` / `.m-main-col` / `.m-aside` は §8 の骨格表を正とする。代表出力の実例（ゴールデンサンプル）は次を参照する:

| ゴールデン | カラム | アニメ | 用途 |
|---|---|---|---|
| `tests/fixtures/klk007/sample-draft.html` | `1col` | ON | 基本の縦積み1カラム |
| `tests/fixtures/klk008/sample-full-2col.html` | `2col-full-right` | ON | 全体2カラム（`.m-layout` が NAV/HERO を内包・サイドバー全高） |
| `tests/fixtures/klk008/sample-anim-off.html` | `2col-body-left` | OFF | 本文のみ2カラム＋アニメOFF（`.reveal`/observer 不在） |

生成時はこの骨格に業種・配色・仮文言・カラム構成・アニメ有無を差し込む。

---

## 11. .gitignore（生成物のGit除外・REQ-011 / NFR-004）

`mockups/` は**アクティブ `.gitignore`・`.gitignore.public`・`.gitignore.private` の3ファイルすべて**に登録済み
（本チケット Phase 1）。案件名・生成物・生成指示書がGit管理に入らないことを `git check-ignore mockups/…` で検証できる。
可視性を切り替えても除外が外れないよう、3ファイルの同期を崩さないこと。案別ファイル（`index-a/b/c.html`）・比較ハブ
（`compare.html`）も `mockups/` 配下なので同じく除外される。

---

## 12. 複数案バリエーション規約（REQ-008・U-C/U-G）

同一の生成指示書から `output.variants`（1〜3）ぶんの案を出す際の**振れ幅**を規約化し、非決定的生成でも品質を安定させる。
案ごとに振る軸は **2つ**: **配色テーマ（§5の5変数）** と **レイアウト原型（`data-archetype`・下の 12.1）**。両者を両振りして
「同じ紙面の色違い」ではなく、色も構成も見分けられる案にする（KLK-021）。**カラム数（`data-columns`）を含む骨格は全案で
固定**する（比較の等条件性・§8骨格の安定）。`data-archetype` は `data-columns` と**直交**し、**列数を変えずに**紙面の構成・
重心だけを切り替える。

**全案で固定（案間で変えない）:**
- `layout.columns`（カラム骨格・§8 の6系統のいずれか。**全案同一の `data-columns`**）・番地ラベル6種（§2）・
  セクション構成（NAV / HERO / ABOUT / MENU / GALLERY / FOOTER）・業種（`industry.resolved`）とテイストの骨子・
  アタリ a方式（§3）・仮文言の骨子・外部依存ゼロ・印刷CSS（§6）・アニメ ON/OFF（§7）。
  **ただし REQ-104 使用時は MV-01 のみ実写真**（`atari:"free-photo"` かつ `mvPhoto.file` 供給時・**同じアップロード画像を
  全案共通**で相対参照・§3.1）。MV-01 以外の枠は全案 a方式で不変。

**案ごとに振る（配色 × レイアウト原型の両振り＋テイスト副次差）:**

| 案 | letter | 配色方針 | レイアウト原型（`data-archetype`・12.1） | 副次の振れ |
|---|---|---|---|---|
| 案A（ベース） | `a` | **生成指示書の配色に忠実**（`colors.main/sub/accent/bg` ＋ §5 autofill 補完のまま） | `stack-centered`（中央寄せ標準） | 標準テイスト |
| 案B | `b` | `colors.main` を起点に**濃色・高級方向**へ調和させた別テーマ（例 紺＋金） | `split-editorial`（左寄せ・非対称） | フォント／見出しトーンを上質寄り（serif 等） |
| 案C | `c` | `colors.main` を起点に**明色・ポップ方向**へ調和させた別テーマ（例 桃＋シアン） | `banded-showcase`（帯構成・ビジュアル先行） | sans-serif・角丸・軽い配色 |

- 各案は §5 の**5変数（`--m-main`/`--m-nav`/`--m-accent`/`--m-bg`/`--m-text`）を案別の値で定義**する。案間で
  少なくとも `--m-main` が異なること（配色方向の差が機械検証で確認できる）。
- `colors.mode:"main-only"`（sub/accent/bg が autofill）: 案B/C は sub/accent/bg を**大きく振ってよい**。
- `colors.mode:"explicit"`（4色指定）: 案B/C は main を**大きく裏切らず**、差し色（accent）・フォント・トーンで差をつける。
- 参考の振れ幅（ワイヤー SCR-002）: 案A 緑（`--m-main:#2E7D6B`）／案B 紺金（`#22303A`＋`--m-accent:#C6A15B`）／
  案C 桃（`#E86FA0`＋`--m-accent:#57C4C4`・sans-serif）。
- **一部失敗（U-G）**: 生成ループで各案の成否を把握する。**成功案のみ** `index-{letter}.html` を保存し `compare.html` に
  載せる。失敗があれば `compare.html` に `.partial-note` を焼き込み（失敗案の明示＋「設定を変えて再生成できます」＝SCR-001
  再実行に寄せた文言）、報告でも通知する。失敗案のファイルは作らず比較ハブから参照しない。`instruction.json` は常に保存する。

### 12.1 レイアウト原型 `data-archetype`（KLK-021・列数を変えないレイアウト差別化）

複数案のレイアウト差を、**カラム数（`data-columns`）を変えずに**表す離散属性。生成ルート `.mock` に `data-columns` と
**並べて** `data-archetype="{値}"` を付ける。`data-columns` がマクロ骨格（サイドバー有無・列数）を、`data-archetype` が
その内側の**構成・重心**（HERO重心・見出し整列・帯/余白リズム・ギャラリー比重）を決める。**両者は直交**し、archetype は
`.m-layout` の列数・サイドバー位置に触れない。

**enum（3値・固定語彙・案別に割り当てる）:**

| `data-archetype` | 割当案 | レイアウトの型（`data-columns` は不変・列数を変えない） |
|---|---|---|
| `stack-centered` | 案A `a` | 中央寄せの標準構成。`.m-hero{align-items:center;text-align:center}`・`.m-sec h2{text-align:center}`・対称グリッド。既存 klk007/009 骨格に忠実 |
| `split-editorial` | 案B `b` | エディトリアル/非対称。`.m-hero{align-items:flex-start;text-align:left}`・`.m-sec h2{text-align:left;border-left:…}`・`.m-about{grid-template-columns:1.4fr .9fr}`（**列数=2は不変**・比率のみ非対称）。serif で上質方向（配色の濃色・高級と同調） |
| `banded-showcase` | 案C `c` | ビジュアル先行/帯構成。`.m-hero{justify-content:flex-end;text-align:left}`（下寄せキャプション）・セクションを全幅帯で交互色・GALLERY 比重増・見出しに下線アクセント。sans-serif で軽い方向（配色の明色・ポップと同調） |

**不変条件（機械検証の正・check_klk021.py S群）:**
1. **全案 `data-columns` 同一**（列数固定を維持・§8 canonical の6値のいずれか）。`--m-main` 相違検証と同じ骨格で
   `data-columns` 同一を確認する。
2. **案間 `data-archetype` 相違**（3案で3値 distinct・各値は上の enum のいずれか）。`--m-main` distinct と**同型**の離散
   フックで機械検証できる。
3. **配色は従来どおり案間で振る**（`--m-main` 相違を維持）＝**配色＋レイアウトの両振り**。
4. **archetype は実 CSS 差として現れる**こと（属性だけの飾りにしない）。HERO の整列シグネチャ
   （`justify-content`/`align-items`/`text-align` の組）が案間で相違する。

- **単案（`variants:1`）**: `data-archetype` は既定 `stack-centered`（従来の中央寄せ標準）でよい。単案では相違検証は働かない。
- **additive**: 既存生成物（`data-archetype` 無し）や §13 compare.html・§14 部分再生成の構造には影響しない。部分再生成は
  対象 `.sec` 以外を保存するため、`data-archetype` はルート属性として保持される（§14 の「カラム骨格を保持」と同じ扱い）。
- 代表出力（ゴールデン）: `tests/fixtures/klk021/index-a.html`（`stack-centered`）／`index-b.html`（`split-editorial`）／
  `index-c.html`（`banded-showcase`）。3案とも `data-columns="2col-body-right"` 同一・`--m-main` 相違。

#### 12.1.1 本文構造の束（KLK-023・archetype を「整列だけ」から「本文の組み立て」へ深化）

KLK-021 の archetype は整列と配色しか振らず、本文の**組み立て**（並び順・各セクション内部の型）が3案で同じになりがち
だった。archetype に**本文構造の束**を持たせ、案間で**実際に違う紙面**にする。**カラム数（`data-columns`）と
セクション集合（`sections`・§2.1）は全案同一**（＝公平比較）を保ち、振るのは**並び順と各セクション内部の構造**だけ。

**archetype → 本文構造の束（案別・すべて離散マーカーで機械検証可能）:**

| archetype | 並び順（本文） | HERO `data-hero` | MENU `.m-menu` | GALLERY `.m-gallery` | ABOUT `.m-about` | 区切り |
|---|---|---|---|---|---|---|
| `stack-centered`（a） | canonical（選択順のまま） | `full`（全面中央） | `pat-cards` | `pat-grid` | `img-left` | プレーン |
| `split-editorial`（b） | ABOUT→GALLERY→MENU（入替） | `split`（左右分割） | `pat-list`（横並びリスト） | `pat-wide`（横帯ワイド） | `img-right` | 罫線 |
| `banded-showcase`（c） | GALLERY先行 | `band`（下寄せ帯） | `pat-zigzag`（ジグザグ交互） | `pat-mosaic`（大小モザイク） | `img-top`（横長画像＋下キャプション） | 全幅帯（交互色） |

**離散マーカー契約（生成物に焼き込み・機械検証フック）:**
- ルート `.mock`: `data-columns`（**全案同一**）・`data-archetype`（相違）・**`data-section-order`**（本文セクションの DOM 順を
  カンマ連結・案間**相違**）・`data-nav-position`（§2.1）。
- `.m-hero` に **`data-hero="full|split|band"`**（案間相違）＋ HERO 整列シグネチャも相違（§12.1 継承）。
- `.m-menu` に **`pat-cards|pat-list|pat-zigzag`**、`.m-gallery` に **`pat-grid|pat-mosaic|pat-wide`**、`.m-about` に
  **`img-left|img-right|img-top`** を付す（案間**相違**・各修飾は**実際に異なる grid/flex 宣言**を伴う＝属性だけの飾りにしない）。

**不変条件（機械検証の正・check_klk023.py）:** 3案で ①`data-columns` 同一 ②本文セクション集合同一（並べ替えのみ・抜き差し
しない）③`--m-main` 相違 ④`data-archetype` 相違 に加えて、⑤`data-section-order` ⑥`data-hero` ⑦MENU型 ⑧GALLERY型
⑨ABOUT画像配置 が**それぞれ案間で相違**（＝複数の構造軸が動く）。

- **ABOUT画像配置**は `img-left`（左画像右キャプション）/ `img-right`（右画像左キャプション）/ `img-top`（横長画像の下に
  キャプション）。パターン増・他セクション内部の型拡充は後続チケット。
- **番地の一意性は不変**: 並べ替えても各セクションの `.pin` は1回のまま（§2・§14 の一意性を保持）。誘導系（CTA/CONTACT）は
  末尾寄りを保つ。
- 代表出力（ゴールデン）: `tests/fixtures/klk023/index-a/b/c.html`。3案とも `data-columns="1col"` 同一・
  `sections=[ABOUT,MENU,GALLERY,CTA]` 同一・上の⑤〜⑨が案間相違。

#### 12.1.2 セクション内型プール方式（KLK-029・VOICE/FLOW/STAFF・§12.1.1 と直交する新設・additive）

§12.1.1 は HERO/MENU/GALLERY/ABOUT を archetype に1対1で固定する。KLK-029 は VOICE/FLOW/STAFF に**5型のプール**を持たせ、
**案ごとに異なる型を「表を読むだけ」で決める**新方式を **additive** に足す。§12.1.1（既存の a/b/c 固定軸・klk021/023 ゴールデン）は
**一切変えない**。理恵さんの最終ゴール（各セクションを段階的に多種多様＝20型以上へ）を後で作り直さずに叶えるための土台（STEP A）。

**設計原理（算術を使わない・決定的）:** 「文字コード合計 mod N」等の算術は Claude が寸分違わず再現できないため**禁止**。
すべて**書き下した明示表**を「読むだけ」で決める。キーは指示書中の**全案不変**な2値（`data-columns`・§8／`navPosition`・§2.1）
なので、**同一指示書＝同一の型割り当て**（決定性）になる。

**(1) 型プール（各セクション5型・index 0〜4 固定・順序を変えない）:**

容器は `m-{sec}`（`.m-voice`/`.m-flow`/`.m-staff`）に**プールマーカー1個**を足す（KLK-023 の `class="m-menu pat-cards"` と同型）。
各マーカーは**実際に異なる grid/flex/order 宣言**を伴う（属性だけの飾りにしない）。index0 は「最も定番・従来寄り」を置く。

| section | 容器 | index0 | index1 | index2 | index3 | index4 |
|---|---|---|---|---|---|---|
| VOICE | `.m-voice` | `voice-cards` | `voice-quote-stack` | `voice-feature` | `voice-two-col` | `voice-slider` |
| FLOW | `.m-flow` | `flow-row` | `flow-timeline` | `flow-number-card` | `flow-arrow-band` | `flow-vertical-split` |
| STAFF | `.m-staff` | `staff-grid` | `staff-hscroll` | `staff-feature` | `staff-list` | `staff-two-col` |

各型の見た目とモバイルの畳み方（`@media (max-width:640px)`）:

- **VOICE** — `voice-cards`: 声カードを横3列（`grid-template-columns:repeat(3,1fr)`／モバイル1列）。
  `voice-quote-stack`: 縦積みの引用ブロック＋左罫線アクセント（`flex-direction:column`＋各項 `border-left`）。
  `voice-feature`: 代表の声を大きく1枚＋下に小カード3枚（`grid-template-columns:1fr`＋`.voice-rest{repeat(3,1fr)}`）。
  `voice-two-col`: 2カラム千鳥で `order` 交互反転（`grid-template-columns:1fr 1fr`＋偶数項 `order`／モバイルは縦積み・order解除）。
  `voice-slider`: 横スクロール風1行（`flex-wrap:nowrap;overflow-x:auto`＋各カード `flex:0 0 260px`）。
- **FLOW** — `flow-row`: 横並び①→②→③（`flex-direction:row`＋各 `flex:1`／モバイル縦積み）。
  `flow-timeline`: 縦タイムライン＋左縦線（`flex-direction:column`＋`border-left`）。
  `flow-number-card`: 番号大きめカードのグリッド（`grid-template-columns:repeat(4,1fr)`／モバイル2列）。
  `flow-arrow-band`: 全幅の矢羽根帯（`grid-auto-flow:column`＋各帯 `clip-path`／モバイルは `grid-auto-flow:row`）。
  `flow-vertical-split`: 各ステップ＝2カラム（左大番号／右説明）を縦に並べる（`flex-direction:column`＋`.step{grid-template-columns:88px 1fr}`）。
- **STAFF** — `staff-grid`: 顔写真グリッド4列（`grid-template-columns:repeat(4,1fr)`／モバイル2列）。
  `staff-hscroll`: 横スクロール風1列（`flex-wrap:nowrap;overflow-x:auto`＋各 `flex:0 0 200px`）。
  `staff-feature`: 代表1名を大写し＋残りをリスト（`grid-template-columns:1.2fr .8fr`／モバイル縦積み）。
  `staff-list`: 横1行×人数のリスト（`flex-direction:column`＋各 `.st{grid-template-columns:96px 1fr}`）。
  `staff-two-col`: 2カラムのプロフィールカード（`grid-template-columns:repeat(2,1fr)`／モバイル1列）。

**(2) オフセット表（`data-columns` × `navPosition` → offset・12セルを全書き下し）:**

| data-columns ＼ navPosition | `top` | `below-hero` |
|---|---|---|
| `1col` | 0 | 3 |
| `2col-full-left` | 1 | 4 |
| `2col-full-right` | 2 | 0 |
| `2col-body-left` | 3 | 1 |
| `2col-body-right` | 4 | 2 |
| `3col` | 0 | 3 |

**(3) 割り当て表（offset → 案A/B/C の pool index・5行を全書き下し）:**

| offset | 案A（`a`） | 案B（`b`） | 案C（`c`） |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 0 |
| 4 | 4 | 0 | 1 |

- 全12セルの offset 集合 = {0,1,2,3,4}、割り当て表の全 index 集合 = {0,1,2,3,4} → **プール全体が到達可能**（システムとして）。
- 各割り当て行は連続3窓（wrap 込み）で必ず**3値 distinct** → **3案で型が重複しない**。
- キー2値は全案不変 → **同一指示書＝同一割り当て**（決定性）。1col でも `navPosition` を切替れば offset 0 と 3 の両方に届き、
  1col のまま5型すべてに到達できる（2次元キーの狙い）。

**(4) Claude の生成手順（表を"読むだけ"・計算しない・SKILL 手順3 に転記）:**

1. ルートの `data-columns`（正規化後・§8）と `navPosition`（§2.1）を確定する（既に §8/§2.1 で確定済み）。
2. **オフセット表**で該当する1セルを読み、offset（0〜4）を得る（**表を読むだけ・算術しない**）。
3. **割り当て表**の offset 行から (idxA, idxB, idxC) の3つの pool index を読む。
4. VOICE/FLOW/STAFF が `sections` にあるとき、各案の容器へ **プール[該当 index] のマーカー**を付け、対応する CSS ブロックを
   `<head>` に含める。例: 1col×top（offset 0）→ 案A VOICE=`voice-cards`／案B=`voice-quote-stack`／案C=`voice-feature`
   （FLOW/STAFF も同 index で `flow-*`/`staff-*` の対応マーカー）。
5. `variants:1`（単案）は archetype 既定 `stack-centered`＝**案A相当** → 各セクションは **idxA のマーカー**を使う（単一・案間 distinct 検証は働かない）。

**(5) 後方互換・不変（additive）:**

- **未選択は no-op（そのセクションが出ない）**: VOICE/FLOW/STAFF が `sections` に無ければセクション自体を出さず、プール
  マーカー・CSS とも不発。既存生成物・klk021/023 ゴールデン・§12.1.1 の既存軸は影響を受けない。
- data-columns 同一・`sections` 集合同一・番地一意性（VOICE-01/FLOW-01/STAFF-01 各1回・§2/§14）は不変。セクションの**有無**は
  案間で同じで、変わるのは**内部マーカーだけ**。

**(6) STEP B での型追加（"データ追加だけ"で完結・拡張性）:**

型を 5→N に増やすときは **(a) 型プールへ1行（マーカー）を追記、(b) 対応する CSS ブロックを1つ追加、(c) 割り当て表を N 行
（連続3窓）に伸ばし、オフセット表の値域を 0..(N-1) へ広げる** だけで済む。**選択ロジック・検証の作り直しは不要**（表構造は不変）。
ABOUT/MENU/GALLERY のプール方式化・ラフ画像からの型抽出も STEP B（別チケット）。

- 代表出力（ゴールデン）: `tests/fixtures/klk029/index-a/b/c.html`（1col×top＝offset0）＋ `tests/fixtures/klk029b/index-a/b/c.html`
  （1col×below-hero＝offset3）。両者の union で VOICE/FLOW/STAFF 各プールの5マーカー全てが実 HTML に出現する（到達可能性の実証）。

### 12.2 参考準拠レイアウト（KLK-034・席替え規則・§12.1.1/§12.1.2 と直交・additive）

SCR-001 でカタログサムネイルを選んだ指示書では、**案Aを「参考準拠案」**にする。対象は
**`references.thumbnails[0]`（先頭の1件）のみ**。その `sectionLayouts`（KLK-030 の1対1 map・語彙は §12.1.1/§12.1.2）を
セクション型の割り当てに反映する。`thumbnails` が無い・`sectionLayouts` が無い指示書は本節不発（従来どおり・後方互換）。
`variants:1`（単案）は案A相当なので同様に適用する。

**規則（各セクションKEYごとに独立に適用・等値比較のみ・算術しない）:**

1. KEY が指示書 `sections` に無い → 何もしない（セクション自体が出ない・§12.1.2(5) と同じ）。
2. 参考の値 v が無い（キー省略）・`"other"`・語彙外 → 何もしない（そのセクションは従来規則のまま）。
3. **案A := v**（参考の型をそのまま採る）。
4. **席替え**: 既定で v と同じ型を持つ案があれば、**その案は「案Aの既定型」を代わりに使う**。
   - §12.1.1 系（HERO/MENU/GALLERY/ABOUT）: v を下の既定型表の案B/C列と比べ、一致した案 := 案Aの既定型。
   - §12.1.2 系（VOICE/FLOW/STAFF）: v の pool index を表引き結果 (idxA,idxB,idxC) の idxB/idxC と比べ、
     一致した案 := `pool[idxA]`。
   - どの案とも重複しなければ案B/C は従来のまま。→ いずれの場合も **3案の型は常に3値 distinct**
     （§12.1.1⑥⑦⑧⑨・§12.1.2 の不変条件を維持）。

**§12.1.1 の既定型（席替えの参照表・§12.1.1 表の転記）:**

| KEY | 案A既定 | 案B既定 | 案C既定 |
|---|---|---|---|
| HERO | `full` | `split` | `band` |
| MENU | `pat-cards` | `pat-list` | `pat-zigzag` |
| GALLERY | `pat-grid` | `pat-wide` | `pat-mosaic` |
| ABOUT | `img-left` | `img-right` | `img-top` |

**本節が触らないもの（スコープ外・不変）:** `data-columns`・`sections` 集合・並び順（`data-section-order`）・
`data-archetype`（3案 distinct のまま）・番地一意性（§2/§14）・§4 文言・アニメ/印刷。HERO の整列シグネチャは
`data-hero` の型に付随して振る（`full`=中央/`split`=左/`band`=下寄せ帯）＝型が distinct ならシグネチャ相違
（§12.1 不変条件4）も維持される。

**生成物マーカー（機械検証フック）:**
- **案Aルート `.mock` のみ**に `data-ref-id="{thumbnails[0].id}"` と `data-ref-colors="reference|specified"`
  （**実効**の配色ソース・§5.1。マルチカラーfallback は `specified`）を付ける。案B/C のルートにはどちらも付けない。
- compare.html: 案Aカードに `.ref-badge`「参考準拠: {label}（{id}）／参考は着想のみ・そっくり再現はしません」を出す
  （own/ref を問わず同文言・§13 に additive）。

**規律（そっくり再現の禁止）:** 生成は参考の**タグ（型マーカー・配色カテゴリ）だけ**を受け取り、参考の画像・実文言には
一切アクセスしない（模写は構造的に不可能）。収集見本（`source:"ref"`）は第三者著作物であり、参考準拠は**着想の反映に限る**。
1:1 の複製・実在サイトの文言流用をしてはならない。

- **部分再生成（§14）との整合**: ルートに `data-ref-id` があるファイルの部分再生成は、対象セクションの**現行マーカーを
  保持**する（§14「参考準拠の保持」・表引き既定へ戻さない＝参考の型が再生成で失われない）。
- 将来拡張（未採番・後続）: 対象を「案×thumbnails[n]」へ広げる場合も本規則を案ごとに独立適用すればよい（作り直し不要）。
  `sectionLayouts` の多値化（KLK-031）は「先頭値を採る」拡張で成立する。
- 代表出力（ゴールデン）: `tests/fixtures/klk034/`（席替え/無衝突/other/省略/プール直採用/プール席替え＋§5.1 表引き）・
  `tests/fixtures/klk034b/`（マルチカラーfallback＋HERO 席替え）。参照データはダミー（実カタログ非依存）。

---

## 13. 比較画面 compare.html の構造規約（REQ-008 / REQ-009・U-B/U-H）

`output.variants≥2` のとき、案を切り替えて見比べる**比較ハブ `compare.html`**（＝**単一ファイル・外部依存ゼロ**）を
`mockups/{…}/` に生成する。見た目の正は `docs/wireframes/SCR-002-compare.html` の chrome。技術制約に沿って作り直す
（ワイヤーを本番へコピーしない）。

**骨格（上から）:**
1. `<head><style>`: ツール chrome CSS ＋ 案切替 CSS ＋ `@media print`（chrome 非表示）。**外部CDN／Webフォント／
   `<link rel="stylesheet">`／`<script src>` 禁止**（JS は原則不要。使う場合も `</body>` 直前のインラインのみ）。
2. **隠しラジオ**: `<input type="radio" name="variant">` を成功案数ぶん（`id="ra"`/`rb`/`rc`・既定は先頭案に `checked`）。
   切替は **CSS のみ**（兄弟結合子）で行う: `#ra:checked ~ .canvas #paneA{display:block}`。セグメント／サムネイルの
   ハイライトも同方式（`#ra:checked ~ .toolchrome label[for=ra]` / `.vthumb.va`）。**JS 非依存＝graceful**。
3. **toolchrome**: `.proj-head`（案件名＝`meta.project` プレースホルダ／生成日／「N案」）＋ `.settings-chips`
   （業種・カラム・テイスト・配色・アタリ方式）。
4. **partial-note（一部失敗時のみ・U-G）**: `.partial-note` に「案Xの生成が一部失敗したため成功案のみ表示」＋
   「設定を変えて再生成できます」を**スキルが焼き込む**。全案成功時は出力しない。
5. **variant-bar**: `.seg`（`label for=ra/rb/rc` の案A/B/C セグメント）＋ `.thumbstrip`（`.vthumb va/vb/vc`＝案別テーマ色の
   ミニ CSS サムネイル。実スクショではなく色面）。各サムネイル cap に「案X」＋
   `<a href="index-{letter}.html" target="_blank" class="full">原寸 ↗</a>`（原寸を別タブで表示）。
6. **toolbar**: 「🖨 印刷 / PDFで保存」＝**選択中の案の standalone を別タブで開く導線**（`index-{letter}.html`）。
   「← 設定を変えて再生成」（任意・SCR-001 への案内）。**「📁 保存フォルダを開く」ダミーボタンは置かない**（U-D・§9）。
7. **canvas**: `.pane#paneA … #paneC` の中に相対 `<iframe src="index-{letter}.html" title="案X プレビュー">`。CSS-only で
   選択案のみ `display:block`。

**依存・安全:**
- iframe `src`・原寸リンク `href` とも**同ディレクトリの相対 `.html` のみ**（`index-a.html` 等）。`http(s)://` 参照 0 件
  （`www.w3.org` / `example.*` を除く）・秘密パターン 0 件・実在案件名なし（NFR-005 / NFR-004 / REQ-011）。

**印刷（REQ-009）:**
- 比較画面の印刷は iframe 経由で不安定なため、**高品質PDFは原寸別タブの standalone `index-{letter}.html`**
  （KLK-007/008 の §6 `@media print` 準拠）で行う導線を正とする。`compare.html` 自身の `@media print` は chrome
  （toolchrome / toolbar / variant-bar / info-bar）を隠す保険とする。

**🔄 セクション再生成コントロール（REQ-103・KLK-012・health-gated・additive）:**

`compare.html` の toolbar 近傍に、控えめな**1つ**の再生成コントロールを additive に置く（既存の隠しラジオ／iframe／サムネイル／
`@media print` 構造は不変）。standalone `index-{letter}.html` には🔄を注入しない（印刷成果物にJSを増やさない・注入面を広げない）。

- **ルート要素に `data-folder="mockups/{YYYY-MM-DD}_{案件名}"` を焼き込む**（保存先フォルダの相対パス。`compare.html` は既に
  `meta.project` を表示しており、フォルダパスは新たな機密ではない・`mockups/` はGit除外）。JS はこれを読んで `folder` を得る。
- **コントロール本体**: 「🔄 セクション再生成」＝番地 `<select>`（`NAV-01`/`MV-01`/`ABOUT-01`/`MENU-01`/`GALLERY-01`/`FOOTER-01` を
  **列挙**した固定 `<option>`。ユーザー自由入力は作らない＝注入面を作らない）＋「このセクションを再生成」`<button>`。既定は無効化しておく。
- **`</body>` 直前のインライン JS（外部依存ゼロ・localhost fetch のみ）**:
  1. 起動時に `GET http://127.0.0.1:8765/health` を **AbortController 約800ms** で試行。**失敗ならコントロールを無効化**し
     「ローカルブリッジ未起動。`python3 draft-gen/bridge.py` を起動するか、Claude Code で `/draft-regenerate {folder} {letter} {番地}`
     でも再生成できます」と案内する（**graceful**・KLK-010 U-7 同型）。
  2. 成功時、ボタン押下で **checked ラジオの letter**（`document.querySelector('input[name=variant]:checked')` の id `ra/rb/rc` → `a/b/c`）と
     選択中の番地を取り、`fetch('http://127.0.0.1:8765/regenerate', {method:'POST', headers:{'Content-Type':'application/json'},
     body: JSON.stringify({folder, letter, addr})})` を投げ、返った `jobId` で `GET /status/{jobId}` をポーリングする
     （`draft-gen/index.html` の probeHealth／pollStatus と同型）。完了でブリッジが対象/`compare.html` を再オープンする（U-7）。
  3. 動的値は `textContent` で表示する（注入対策）。localhost fetch は §1 が禁じる外部CDN/フォント/画像ではない（外部URL 0 を保つ）。
- ブリッジ側で `folder`/`letter`/`addr` を再検証（`is_safe_mockups_folder`/`is_valid_letter`/`is_valid_addr`＋対象ファイルでの番地一意性）
  するため、compare.html 側は安全な番地列挙のみで足りる（多層防御・§4.4）。

---

## 14. 部分再生成規約（REQ-103・`/draft-regenerate`）

生成済みラフの**特定セクションだけ**を番地ラベル指定で作り直す規約（`.claude/skills/draft-regenerate/SKILL.md` の正）。
指定した1つの `.sec` ブロックのみを本規約準拠で差し替え、**それ以外はすべて保存**する（SPEC §7・ラフを壊さない）。

**保持すべき不変（指定 `.sec` 以外は全保存）:**

1. **配色5変数**（`--m-main`/`--m-nav`/`--m-accent`/`--m-bg`/`--m-text`）= **対象 `index-{letter}.html` のルート `.mock` 定義から
   実値を読む**（インライン `style="--m-*:…"` 形式・`<style>` 内 `.mock { --m-*:…; }` 形式の双方）。**★ `instruction.json` からは
   読まない**（案B/C は `colors.main` から派生した別テーマのため、指示書から読むと配色が壊れる・§12）。新セクションも `var(--m-*)` で参照する。
2. **カラム骨格とレイアウト原型**（ルート要素の `data-columns`・§8／`data-archetype`・§12.1）。どちらもルート属性として
   バイト等価で保持する（対象 `.sec` の差し替えでルート属性は変えない）。
3. **全番地ラベル**（他5セクションの `.pin` と対象セクションの `.pin {addr}`・§2）。番地ラベル文字列は変えない。
4. **`<head>` の CSS**（`.reveal`/`@media print`/`.atari` 等）・**`</body>` 直前のアニメ `<script>`**（§7）。
   アニメ状態は対象ファイルの現状に合わせる（ON 案は `.reveal` を付け、OFF 案は付けない）。
5. **他5セクションの `.sec` ブロック**（バイト等価で保存）。

**番地一意性（未知/重複はファイル無変更で停止・SPEC §7）:**

- 番地は安全文字集合パターン `^[A-Z][A-Z0-9]*-\d{2}$`（注入不能・§2 の `SECTION-NN` 拡張も許容）に一致し、かつ対象HTML内に
  `<span class="pin">{addr}</span>` が**ちょうど1回**存在すること。**0回=未知 / 2回以上=重複**なら生成を開始せずエラーで停止し、
  **ファイルを一切変更しない**。

**上書き方針（U-4）:**

- 対象 `index-{letter}.html`（単一案は `index.html`）を**直接上書き**する。ファイル名・`compare.html` の iframe `src`・原寸リンク
  `href` は不変のまま → 再表示はリロードで反映される（リビジョン `index-{letter}-r{n}.html` は作らない）。

**トリガー導線（`compare.html` の🔄再生成コントロール・§13 と対）:** ローカルブリッジ経由のワンクリック導線は §13 の
「🔄 セクション再生成」コントロールを参照する。

**VOICE/FLOW/STAFF のプールマーカー再付与（KLK-029・§12.1.2 と対・additive）:**

対象 `.sec` が **VOICE-01 / FLOW-01 / STAFF-01** のときは、そのセクションが持つべき**プールマーカー**（`voice-*`/`flow-*`/`staff-*`・
§12.1.2）を再付与してから差し替える。マーカーは**対象HTMLだけで自己決定できる**（`instruction.json` 不要・決定的）:

1. 対象HTMLのルート `.mock` から **`data-columns`** と **`data-nav-position`** の実値を読む（両方とも生成時に焼き込み済み・§8/§2.1）。
2. §12.1.2 の**オフセット表**で (`data-columns` × `data-nav-position`) の1セルを読み offset を得る。
3. 対象ファイルの **letter**（`index-{letter}.html` の a/b/c。単案 `index.html` は案A相当＝letter=a）から、§12.1.2 の
   **割り当て表**の offset 行で pool index を読む。
4. その `pool[index]` のマーカーを容器 `.m-{sec}` に付け、対応 CSS ブロックが `<head>` に無ければ足す（他5セクション・配色・
   ルート属性は不変）。→ 元の生成と**同じ型**が決定的に再現される（表を読むだけ・算術なし）。

**参考準拠の保持（KLK-034・§12.2 と対）:** 対象HTMLのルート `.mock` に **`data-ref-id` があるファイル（＝参考準拠の案A）**は、
表引き・archetype 既定より**「対象セクションの現行マーカー」を優先**する: 差し替え前の対象 `.sec` 内の容器
（`.m-hero` の `data-hero` ／ `.m-menu`・`.m-gallery`・`.m-about`・`.m-voice`・`.m-flow`・`.m-staff` の型マーカー）を読み取り、
**同じ型マーカーで再生成**する（§12.2 の席替え結果＝参考の型を保持。対象HTMLだけで自己決定・`instruction.json` 不要・決定的）。
現行マーカーが読めない/語彙外のときのみ、上の従来規則（表引き・archetype 既定）へフォールバックする。
`data-ref-id` が無いファイル（従来生成・案B/C）は本段落の対象外＝従来規則のまま。

- `compare.html` の再生成 `<select>` は基本6番地のまま（VOICE 等は追加しない・§13）。ブラウザ経由の VOICE/FLOW/STAFF 部分
  再生成は既存制約どおり非対象。手動 `/draft-regenerate {folder} {letter} VOICE-01` は番地パターン（`^[A-Z][A-Z0-9]*-\d{2}$`）が
  既に許容する。`bridge.py`（KNOWN_ADDR / ADDR_RE）への変更は不要。
