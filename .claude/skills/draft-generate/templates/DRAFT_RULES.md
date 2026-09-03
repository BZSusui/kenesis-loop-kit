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
| 1 | NEWS | `NEWS-01` | お知らせ | 日付つきリスト等のお知らせ（仮文言）。内部型は §12.1.3 プール（6型・KLK-051・list/cards/media/timeline/table/accordion） |
| 2 | ABOUT | `ABOUT-01` | CONCEPT | アタリ＋紹介文（§3 a方式） |
| 3 | MENU | `MENU-01` | MENU / SERVICE | カード群（アタリ＋名称＋価格） |
| 4 | PRICE | `PRICE-01` | PRICE | プラン比較の表等（仮文言）。内部型は §12.1.3 プール（6型・KLK-052・table/cards/featured/list/toggle/matrix） |
| 5 | GALLERY | `GALLERY-01` | GALLERY | アタリのグリッド |
| 6 | SEARCH | `SEARCH-01` | SEARCH | 条件検索フォーム面（**静的**・入力欄は飾り・送信なし）。内部型は §12.1.3 プール（6型・KLK-056・bar/keywords/filters/sidebar/header/hero）。**SEARCH 選択時は §12.1.3(7) で HERO（対応型）または NAV-01（バー型）内へ検索窓を実埋め込みし本セクションは一本化（KLK-057）** |
| 7 | FLOW | `FLOW-01` | FLOW | ステップ ①→②→③ |
| 8 | VOICE | `VOICE-01` | VOICE | お客様の声カード（アタリ＋コメント） |
| 9 | STAFF | `STAFF-01` | STAFF | 人物カード（アタリ＋肩書） |
| 10 | FAQ | `FAQ-01` | FAQ | Q&A 積み上げ等（抜粋→誘導文）。内部型は §12.1.3 プール（6型・KLK-053・list/accordion/two-col/cards/category-tabs/search） |
| 11 | SNS | `SNS-01` | SNS | フィード/投稿の**アタリ面**（**実埋め込み禁止**・外部URL 0・NFR-005）。内部型は §12.1.3 プール（6型・KLK-049/050） |
| 12 | ACCESS | `ACCESS-01` | ACCESS | 地図の**アタリ面**（実地図禁止）＋住所・営業時間。内部型は §12.1.3 プール（6型・KLK-054・side/top/overlay/hours/cards/steps・全型に地図アタリ内包） |
| 13 | CTA | `CTA-01` | （誘導） | 見出し＋ひとこと＋ボタン（**目的で文言可変**・下記）。ボタンは1〜4個＋文字数で自動整列（§4.4・KLK-058） |
| 14 | CONTACT | `CONTACT-01` | CONTACT | お問い合わせ誘導（ボタン/リンク）。内部型は §12.1.3 プール（6型・KLK-055・cta/form/split/methods/banner/steps・フォームは静的アタリ） |

- **並び順**: v1 は上の canonical 順のうち**選ばれた分だけ**。案ごとの並び替え・型振りは KLK-023。
- **VOICE/FLOW/STAFF の内部型**: これら3セクションは案ごとに型プール（各6型・§12.1.2・KLK-029/035）から型を選ぶ。ここの語彙行は
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

### 3.0 アタリ枠の比率（KLK-072・**既定 `aspect-ratio: 4 / 3`**）

**画像アタリの縦横比は `aspect-ratio: 4 / 3`（横4:縦3）を既定とする。**
`min-height` だけで高さを決めてはならない（幅がコンテナ任せになり、**横に長細い帯**になってしまう）。

```css
/* 良い: 幅が変わっても比率が保たれる */
.atari { aspect-ratio: 4 / 3; }
/* 悪い: サイドバーでは細長く、全幅では潰れる */
.atari { min-height: 90px; }
```

- **対象**: 写真・イラスト・地図が入る想定のアタリ全般。
  ABOUT / MENU / GALLERY / VOICE / NEWS / PRICE / FAQ / CONTACT / **ACCESS の地図アタリ（`.map-atari`）** など。
- **`min-height` は下限としてのみ併用してよい**（`aspect-ratio` と併記した場合、狭い幅でも潰れすぎないための保険）。
  ただし `min-height` が支配的にならない値にすること。

**この比率を適用しない例外（意図して別の形にしている型）:**

| 例外 | 比率 | 理由 |
|---|---|---|
| STAFF のプロフィール写真・`sns-grid`・`sns-reels`・`img-circle` | `1 / 1`（正方・円） | 人物や SNS サムネは正方が自然。型の定義そのものが正方を前提にしている |
| HERO の全面ビジュアル（`.hero-atari` 等・`full`/`center-scroll`/`overlap`/`split`/`band`） | 画面を覆う（`min-height` 可） | ファーストビューは画面いっぱいに見せるもので、比率で縛る対象ではない |
| HERO `panel-band` のフィルム風パネル | `3 / 2`（KLK-043） | フィルムのコマ帯としてあえて横長にした型。4/3 にすると帯の見た目が崩れる。**ただし帯は MV の左右いっぱいまで伸ばし、`max-height` は付けない**（§3.0.1・KLK-076） |
| ロゴ枠・アイコン枠など画像ではない飾り | 対象外 | 写真が入る想定の枠ではない |

**★この規約は型定義の表現より優先する（KLK-075）**

型プール（§12.1.x）の説明に「**横長**」「**横帯ワイド**」「**大判横長**」などの語があっても、
**それは形の方向性を示すだけで、`16/6` や `16/7` のような極端な比率を意味しない。比率は本節の 4/3 を使う。**

実際に KLK-072 の規約追加後も、次の3箇所が極端な横長のまま生成された（型の語に引きずられた）:

| 生成された CSS | あるべき |
|---|---|
| `.map-atari { aspect-ratio: 16/7 }` | `4/3` |
| `.m-gallery.pat-wide .atari { aspect-ratio: 16/6 }` | `4/3` |
| `.m-about.img-top .atari { aspect-ratio: 16/7 }` | `4/3` |

**判断に迷ったら 4/3。** 例外は下の表に載っている型**だけ**であり、型の説明文は例外の根拠にならない。

**なぜ 4/3 か**: 実績カタログの参考画像も一般的な写真も横長が多く、`16/9` ほど細くない
`4/3` が「写真らしさ」と「縦の情報量」の折り合いが良い。正方に近づくため、
サイドバーのような狭い幅でも帯にならない。

#### 3.0.1 HERO `panel-band` の帯は MV の左右いっぱいに伸ばす（KLK-076）

`panel-band` のフィルム帯（`.film` / `.film-band` など名前は問わない）は、
**MV の左右端まで届かせる**。左右に余白が残るとフィルムのコマ帯に見えず、ただのカード列になる。

**守るべき結果は3つだけ:**

1. 帯の左右端が **MV の左右端と一致**している（`.m-hero` の左右 padding の**内側で止まらない**）
2. `grid-template-columns` は **`repeat(auto-fit, minmax(220px, 1fr))`**（列数を画面幅にあわせて可変にする）
3. 帯にもコマにも **`max-height` を付けない**

**実装は次のどちらでもよい**（結果が上の3つを満たせば形は問わない）:

| 解き方 | 書き方 |
|---|---|
| A: padding を相殺する | `.m-hero{padding:56px 30px 0}` に対し `.film{margin-inline:-30px;width:calc(100% + 60px)}` |
| B: padding を内側の要素へ移す | `.m-hero` の左右 padding を 0 にし、見出しだけを包む `.hero-head{padding:50px 30px 24px}` に持たせる。帯は `width:100%` のままで端まで届く |

**★実際に負けた CSS（KLK-075 で直したはずが KLK-076 の再生成で再発した）:**

```css
/* NG — width:100% は padding の内側で 100%。左右に 30px の余白が残る */
.m-hero[data-hero=panel-band]{ padding:56px 30px 0; }
.m-hero[data-hero=panel-band] .film{ grid-template-columns:repeat(6,1fr); width:100%; max-height:130px; }
```

`repeat(6,1fr)` と `max-height` の組合せは**KLK-075 で撤廃した旧実装そのもの**である。
1440px 幅では 1コマが 226px になり、`aspect-ratio:3/2` なら高さ 151px。
`max-height:130px` がこれを切り落とすため、コマの下端が欠ける。

モバイル（`max-width:640px`）だけは `repeat(3,1fr)` の上書きでよい（`minmax(220px,1fr)` では1列になるため）。

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

#### 4.1.1 AI が文言を書く場合の改行（KLK-074）

`copy` の指定が**無い**とき（＝AIが §4 本則で文言を提案するとき）も、**改行位置は AI が決めて `<br>` を置く**。
ブラウザの自動折り返し任せにしない。

- **句点（`。`）で改行する**のが基本。2文なら2行にする。
  例: `初回相談は無料です。<br>まずはお話をお聞かせください。`
- 1文が長いときは**読点（`、`）**で改行してよい。
  例: `あなたの笑顔を、<br>一生の健康と共に。`
- **改行は最大2行まで**（キャッチ）／**3行まで**（リード）。それ以上は文言自体を短くする。
- **改行した行の途中でさらに折り返されないよう、器の幅を内容にあわせる**（§12.1.3 `overlap` の白背景など）。
  `<br>` で決めた行組と、幅不足による再折り返しが二重にかかると
  「あなたの笑顔／を、／一生の健康と共／に。」のような**不格好な行組**になる（実際に見本で発生）。

**★3案すべてに同じ規律を適用する（KLK-076）**

`catch` と `lead` の文言は3案で共通なので、**行組も3案で揃える**。
案Aで `<br>` を入れたのに案B/案Cが1行のまま、という不一致を作らない。

実際に、規約と例文があるのに次のように**案Aだけ**適用されて生成された:

| 案 | 生成された lead |
|---|---|
| 案A | `初回のご相談は無料です。<br>まずはあなたのお話を、じっくりお聞かせください。` |
| 案B | `初回のご相談は無料です。まずはあなたのお話を、じっくりお聞かせください。` ← NG |
| 案C | `初回のご相談は無料です。まずはあなたのお話を、じっくりお聞かせください。` ← NG |

**確認のしかた**: 書き終えたら3案の `catch` / `lead` を並べ、
**文末以外に `。` があるのに `<br>` が無い行が1つでもあれば直す**。

**なぜ AI が改行を決めるのか**: キャッチが1行か2行かで紙面の印象が大きく変わる（§4.1 と同じ理由）。
自動折り返しに任せると、幅によって毎回違う位置で切れ、デザインラフとして見せられない。

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

### 4.3 詳細ページ誘導ボタン（KLK-048・`sectionOptions.{KEY}.moreLink`・opt-in・共通 `.sec-more`）

実サイトは1ページ完結でなく、各セクションから**下層の詳細/一覧ページへ誘導**する構成が一般的。これを表す
**オプトインの共通ボタン**を additive に足す。**既定OFF**（指定の無いセクション・既存生成物は不変）。

- **トリガー**: `sectionOptions.{KEY}.moreLink = { "label": "…", "href"?: "…" }`。KEY が本文セクション
  （NAV/MV/FOOTER を除く・§2.1 の語彙）で、その `moreLink` があるとき、当該 `.sec` の**内容末尾**に誘導ボタンを出す。
  無指定のセクションには出さない（opt-in・従来出力は不変）。
- **マークアップ（共通規約）**: セクション内容の直後に
  `<div class="sec-more"><a class="sec-more-btn" href="{href}">{label} ＞</a></div>`。
  - **`.sec-more`**: 中央寄せ・**十分な上余白**（`text-align:center; margin-top:40px`＝約2.4em。シャドウ付きカード/表との
    窮屈さを避けるため広めに取る）。
  - **`.sec-more-btn`**: アウトライン pill（`display:inline-block; border:1.5px solid var(--m-main); color:var(--m-main);
    background:#fff; padding:11px 30px; border-radius:24px; font-size:13px; font-weight:700`）。
- **href**: 省略時は下層ページ想定のプレースホルダ `#`（または相対パス）。**外部 http(s) URL は禁止**（§1 外部依存ゼロ）。
- **label**: 制御文字除去・過長（40字目安）切り詰め・HTMLエスケープ（§4.1/§4.2 と同じ注入対策）。
- **MENU `feature-large`（§12.1.3・KLK-046）の常設ボタンはこの `.sec-more` を使う**（1件ピックアップ型の性質上、
  一覧導線を常設。`moreLink` 未指定でも label 既定「一覧を見る」で出す＝型に内包）。他型は opt-in のときのみ。
- **複数案共通**: `variants≥2` でも全案同じ（§12。配色・レイアウト型は案別のまま）。`.sec-more-btn` の枠色は各案の
  `--m-main` を使うので配色は案ごとに追従する。
- **後方互換**: `moreLink` が無い sectionOptions は従来どおり（CTA の `purpose`/`label`・`heading`/`lead` と独立に併用可）。
  部分再生成（§14）でも該当 `sectionOptions.moreLink` を尊重する。

#### 4.3.1 スクロール誘導（`SCROLL ↓`）はクリックできること（KLK-074）

HERO に置くスクロール誘導（`SCROLL ↓` / `.scroll-cue` / `.scrolldown` 等）は、
**押したら次のコンテンツがブラウザ最上部に来るようにスクロールする**こと。
ただの飾りテキストにしない（実際に見本で「押しても何も起きない」状態が発生・KLK-074）。

- **実装は同一ページ内アンカー**（`<a href="#next">`）。JS は使わない。
  ```html
  <a class="scroll-cue" href="#after-hero">SCROLL <span class="arrow">↓</span></a>
  ...
  <div class="sec" id="after-hero"> ← HERO の次に来るセクション（本文の先頭）
  ```
  `html { scroll-behavior: smooth; }` を添えるとなめらかに動く（任意・外部依存なし）。
- **飛び先は「HERO の次に表示されるもの」**。`2col-*` レイアウトでは
  **本文カラムとサイドバーを含む `.m-layout` の先頭**（＝画面に次に現れる塊）を指す。
  本文だけを指すとサイドバーが画面外に取り残される。
- `text-decoration:none` を当て、リンクらしい下線が出ないようにする（見た目は従来どおり）。
- **対象は `SCROLL ↓` を出すすべての型**（`center-scroll` のほか、HERO で同様の誘導を置いた型すべて）。

### 4.4 CTA マルチボタンと自動整列（KLK-058・`sectionOptions.CTA.buttons`・1〜4個・文字数で整列）

CTA はレイアウト差異が小さいため §12.1.3 の6型プールは設けず、**ボタン数（1〜4）と文字数による整列**を可変点とする。基本構成（見出し＋説明文＋ボタン群）は不変。

- **データ（後方互換）**: `sectionOptions.CTA.buttons` ＝ **1〜4個の配列**。各要素 `{ label（必須・40字・1行）, purpose?（§2.1 の6種）または href?（相対/#のみ・外部URL/危険スキーム不可） }`。**`buttons` が無ければ従来どおり単一ボタン**（`purpose`/`label`）。bridge が検証する（`buttons` 1〜4・各 label 40字・purpose enum・href 相対）。
- **整列の決定（生成時に各 label の文字数で決める・算術は単純比較のみ・静的/JSなし）**: ボタン群を `<div class="cta-btns {marker}">` で包み、各ボタンは `<a class="cta-btn" href="#">`（長文ボタンには `wide` を付す）。CSS grid で実装。
  - **`single`**（1個）: 中央1つ。
  - **`row`**（横並び）: 2個通常・3個で全て短く同程度・4個で全て短い。`grid-auto-flow:column`。
  - **`stack`**（縦2段）: 2個で両方長文。`grid-template-columns:1fr`。
  - **`two-plus-one`**（3個で1つだけ明らかに長文）: `grid-template-columns:1fr 1fr`＝上に短い2個、**長文1個に `wide`（`grid-column:1/-1`）を付け全幅**（＝短2列と同じ横幅で下段）。
  - **`grid2`**（4個の既定）: `grid-template-columns:1fr 1fr` の2×2。
- **「長文」判定**: あるラベルの文字数が **他ボタンの最長の約1.4倍以上**（相対）＝「明らかに長文」。補助として絶対閾値（全角**約12字以上＝長／約8字以下＝短**）も用いる。しきい値は目視で調整可。
- **モバイル**: `row`/`grid2`/`two-plus-one` とも1列縦積みへ。**ボタンは静的アタリ**（実送信・`<form action>`・外部URL・iframe なし・href は相対/#・NFR-005）。
- **配色/複数案**: `.cta-btn` は `--m-accent`、CTA 帯は `--m-main` を使い案ごとに追従。`variants≥2` でも buttons 構成は全案同じ（配色のみ案別）。
- 代表出力（ゴールデン）: `tests/fixtures/klk058/`（row(2)/row(3)/two-plus-one）／`tests/fixtures/klk058b/`（grid2(4)/single(1)/stack(2長文)）。

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

### 5.1 参考配色の16カテゴリ→hex 変換表（KLK-034 / KLK-067・案A限定・決定的）

`references.colorSource:"reference"` かつ `references.thumbnails[0].colors`（16カテゴリ・1..3件）があるとき、
**案Aに限り** §5 の入力を次の**明示表**で差し替える（表を読むだけ・算術しない・§12.1.2 と同じ決定性原理）:

**語彙の正は `palette/index.html` の `const COLORS`（ムードカラー ジェネレーターの「メインカラーの傾向（カラー）」・
16種）**。新規9色の hex は palette の HSL から導出し、**主色 `--m-main` として使える帯**（S ≤ 0.55 / L 0.34〜0.52）へ
正規化してある（生の HSL は明るすぎ・鮮やかすぎて既存6色と質感が揃わないため）。
**既存6色（グリーン/ブルー/レッド/ゴールド/ピンク/モノトーン）の hex は KLK-067 でも変更していない**
（golden `klk034` が表引き結果を固定しているため）。

| 16カテゴリ | hex | トーンの意図 |
|---|---|---|
| レッド | `#B3402F` | 朱寄りの赤（彩度を上げすぎない） |
| ピンク | `#E86FA0` | ワイヤー案Cの桃 |
| オレンジ | `#C87F42` | くすませた橙 |
| イエロー | `#BFA23C` | 黄土寄りの黄（主色として使える明度へ） |
| イエローグリーン | `#7E9B45` | 苔寄りの黄緑 |
| グリーン | `#2E7D6B` | 深緑（ワイヤーSCR-002 案Aの基準緑） |
| ミント・水色 | `#3E9AA6` | 青緑（ティール） |
| ブルー | `#2C5F8A` | 落ち着いた紺青 |
| ネイビー | `#2A3C6B` | 濃紺 |
| パープル | `#6F4E9C` | 青紫（彩度控えめ） |
| ブラウン | `#885A3A` | 焦茶 |
| ベージュ | `#A98E60` | 主色に使えるよう暗めへ寄せた砂色 |
| ゴールド | `#C6A15B` | ワイヤー案Bの金 |
| シルバー | `#7C858D` | 低彩度のグレー（主色に使えるよう暗めへ） |
| モノトーン | `#444850` | 墨色 |
| カラフル | （表引きしない） | 下のフォールバックへ（旧「マルチカラー」・KLK-067 で改名） |

- `colors[0]` → 案A `--m-main`。`colors[1]`（あれば）→ 案A `--m-accent`。`colors[2]` は反映しない。
- `sub`/`bg`/`--m-text` は §5 の autofill 規則をそのまま適用する（main 起点の color-mix）。
- **カラフル（単独指定のみ・§2規約）のフォールバック**: 表引きせず**指示書の指定色（従来の案A忠実・§12）**へ
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

### 8.1 狭い本文カラムでの畳み方（KLK-073）

`layout.columns` が **`2col-*` または `3col`** のとき、本文カラム（`.m-main-col`）は
サイドバーに幅を取られて**1カラム時よりずっと狭くなる**（例: `2col-body-left` は `300px 1fr`）。

**この狭い幅では、カード内で「画像＋本文」を横並びにしてはならない。**
横並びのままだと画像が数十pxまで潰れ、本文も1行に数文字しか入らない。
実際に見本（`2col-body-left` の VOICE）で、写真が 64px の帯になる事故が起きた。

**規律:**

1. **カード内で画像と本文を横並びにする型は、`2col-*` / `3col` では縦積み（画像が上・本文が下）にする。**
   対象例: `voice-two-col` / `voice-cards` / **`voice-zigzag`** / `news-cards` / `news-media` /
   `faq-cards` / `price-cards` / `contact-methods` / `map-cards` / **`flow-zigzag`** / **`staff-zigzag`** /
   **`img-left` / `img-right` / `img-overlap`（ABOUT）** / `feature-large`（MENU）など、
   **カード内・セクション内で画像と本文を左右に並べる型すべて**。

   **★この規律は型定義より優先する（KLK-075）。**
   型の説明に「**左右交互**」「**画像左／文章右**」とあっても、`2col-*` / `3col` では**縦積みにする**。
   「左右交互」は1カラムページでの見せ方であり、狭いカラムでは成立しない。
   実際に KLK-073 の規約追加後も、`2col-body-left` の `voice-zigzag` が
   `grid-template-columns: 170px 1fr` の横並びのまま生成された（型の語に引きずられた）。
   **偶数項の `order` 反転も、縦積みにしたら不要**（上下が入れ替わるだけで意味がない）ので外す。
   ```css
   /* 1col: 横並びでよい */
   .v-item { display: grid; grid-template-columns: 120px 1fr; gap: 14px; }
   /* 2col-* / 3col: 縦積みにする */
   .v-item { display: grid; grid-template-columns: 1fr; gap: 10px; }
   ```
2. **画像の比率は §3.0 の `aspect-ratio: 4 / 3` を、1カラム時も狭いカラム時も同じく守る。**
   縦積みにしたからといって正方や横長へ変えない。
3. **セクション自体の列数も減らす**（狭い本文で3列カードは破綻する）。
   `2col-*` / `3col` では、`repeat(3,1fr)` → `repeat(2,1fr)`、`1fr 1fr` → `1fr` を基本とする。
4. モバイル（`@media (max-width:640px)`）は従来どおり全型で縦積み（本規律とは独立・§8 のまま）。

**なぜ「カラム構成」で分けるのか**: 同じ型でも、1カラムのページでは横並びが読みやすく、
2カラムのページでは縦積みでないと成立しない。**型の選択ではなくレイアウトの帰結**なので、
型プール（§12.1.x）ではなくカラム構成の規約（本節）で決める。


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

> **※KLK-036/037/044: GALLERY・HERO・ABOUT・MENU の型は §12.1.3（各独立プール）で決定する（archetype 固定ではない）。**
> 上表の GALLERY/HERO/ABOUT/MENU 列は **offset0 の割り当てと一致する既定値**として残す（1col×top では従来どおり）。
> **KLK-044 で MENU も §12.1.3 プール（4型・mod4・`price-table` 追加）へ移譲済み。§12.1.1 archetype 固定のセクションは無くなった。** 並び順・区切りは §12.1.1 のまま不変。
> HERO の整列シグネチャは §12.1.3 の型（full/split/band/overlap/center-scroll/panel-band）に付随する（§12.1 不変条件4を維持）。

**離散マーカー契約（生成物に焼き込み・機械検証フック）:**
- ルート `.mock`: `data-columns`（**全案同一**）・`data-archetype`（相違）・**`data-section-order`**（本文セクションの DOM 順を
  カンマ連結・案間**相違**）・`data-nav-position`（§2.1）。
- `.m-menu` に **`pat-cards|pat-list|pat-zigzag|price-table`** を付す（案間**相違**・各修飾は**実際に異なる grid/flex 宣言**を伴う＝飾りにしない）。
  **`.m-menu`・`.m-hero` の型(`data-hero`)・`.m-gallery`・`.m-about` の型は §12.1.3（各独立プール）で決定**する（KLK-036/037/044・archetype 固定から移譲）。
  HERO は型に整列シグネチャ（justify/align/text-align）が付随し案間相違（§12.1 継承）。

**不変条件（機械検証の正・check_klk023.py）:** 3案で ①`data-columns` 同一 ②本文セクション集合同一（並べ替えのみ・抜き差し
しない）③`--m-main` 相違 ④`data-archetype` 相違 に加えて、⑤`data-section-order` ⑥`data-hero` ⑦MENU型 ⑧GALLERY型
⑨ABOUT画像配置 が**それぞれ案間で相違**（＝複数の構造軸が動く）。**⑥HERO型・⑧GALLERY型・⑨ABOUT配置は KLK-036/037 以降 §12.1.3 の表引きで決定**
（archetype 固定ではないが offset0＝1col×top では従来と同一・案間 distinct は §12.1.3 の連続3窓が保証。HERO は整列シグネチャも4型で全distinct）。

- **ABOUT画像配置**は `img-left`（左画像右キャプション）/ `img-right`（右画像左キャプション）/ `img-top`（横長画像の下に
  キャプション）。パターン増・他セクション内部の型拡充は後続チケット。
- **番地の一意性は不変**: 並べ替えても各セクションの `.pin` は1回のまま（§2・§14 の一意性を保持）。誘導系（CTA/CONTACT）は
  末尾寄りを保つ。
- 代表出力（ゴールデン）: `tests/fixtures/klk023/index-a/b/c.html`。3案とも `data-columns="1col"` 同一・
  `sections=[ABOUT,MENU,GALLERY,CTA]` 同一・上の⑤〜⑨が案間相違。

#### 12.1.2 セクション内型プール方式（KLK-029・VOICE/FLOW/STAFF・§12.1.1 と直交する新設・additive）

§12.1.1 は HERO/MENU/GALLERY/ABOUT を archetype に1対1で固定する。KLK-029 は VOICE/FLOW/STAFF に**型プール**（KLK-035 で各6型）を持たせ、
**案ごとに異なる型を「表を読むだけ」で決める**新方式を **additive** に足す。§12.1.1（既存の a/b/c 固定軸・klk021/023 ゴールデン）は
**一切変えない**。理恵さんの最終ゴール（各セクションを段階的に多種多様＝20型以上へ）を後で作り直さずに叶えるための土台（STEP A）。

**設計原理（算術を使わない・決定的）:** 「文字コード合計 mod N」等の算術は Claude が寸分違わず再現できないため**禁止**。
すべて**書き下した明示表**を「読むだけ」で決める。キーは指示書中の**全案不変**な2値（`data-columns`・§8／`navPosition`・§2.1）
なので、**同一指示書＝同一の型割り当て**（決定性）になる。

**(1) 型プール（各セクション6型・index 0〜5 固定・順序を変えない・KLK-035 で index5 を追加）:**

容器は `m-{sec}`（`.m-voice`/`.m-flow`/`.m-staff`）に**プールマーカー1個**を足す（KLK-023 の `class="m-menu pat-cards"` と同型）。
各マーカーは**実際に異なる grid/flex/order 宣言**を伴う（属性だけの飾りにしない）。index0 は「最も定番・従来寄り」を置く。

**★重要な不変条件（KLK-035 で明文化）: VOICE/FLOW/STAFF の型数は常に等しく N（現在 N=6）でなければならない。**
割り当て表（(3)）は1つの pool index を3プール共通に適用するため、型数が非対称だと `pool[index]` が範囲外になる。
型を増やすときは必ず3セクション同数で増やす（(6) 参照）。

| section | 容器 | index0 | index1 | index2 | index3 | index4 | index5 |
|---|---|---|---|---|---|---|---|
| VOICE | `.m-voice` | `voice-cards` | `voice-quote-stack` | `voice-feature` | `voice-two-col` | `voice-slider` | `voice-zigzag` |
| FLOW | `.m-flow` | `flow-row` | `flow-timeline` | `flow-number-card` | `flow-arrow-band` | `flow-vertical-split` | `flow-zigzag` |
| STAFF | `.m-staff` | `staff-grid` | `staff-hscroll` | `staff-feature` | `staff-list` | `staff-two-col` | `staff-zigzag` |

各型の見た目とモバイルの畳み方（`@media (max-width:640px)`）:

- **VOICE** — `voice-cards`: 声カードを横3列（`grid-template-columns:repeat(3,1fr)`／モバイル1列）。
  `voice-quote-stack`: 縦積みの引用ブロック＋左罫線アクセント（`flex-direction:column`＋各項 `border-left`）。
  `voice-feature`: 代表の声を大きく1枚＋下に小カード3枚（`grid-template-columns:1fr`＋`.voice-rest{repeat(3,1fr)}`）。
  `voice-two-col`: 2カラム千鳥で `order` 交互反転（`grid-template-columns:1fr 1fr`＋偶数項 `order`／モバイルは縦積み・order解除）。
  `voice-slider`: 横スクロール風1行（`flex-wrap:nowrap;overflow-x:auto`＋各カード `flex:0 0 260px`）。
  `voice-zigzag`（KLK-035）: 全幅1カラム縦積み（`flex-direction:column`）＋各カード内 `grid-template-columns:1fr 1fr`、
  偶数カードで画像 `order` 反転＝画像/文章を左右交互（voice-two-col の「2カラム並列」とは別＝全幅縦積みの千鳥／モバイルは各カード縦積み・order解除）。
- **FLOW** — `flow-row`: 横並び①→②→③（`flex-direction:row`＋各 `flex:1`／モバイル縦積み）。
  `flow-timeline`: 縦タイムライン＋左縦線（`flex-direction:column`＋`border-left`）。
  `flow-number-card`: 番号大きめカードのグリッド（`grid-template-columns:repeat(4,1fr)`／モバイル2列）。
  `flow-arrow-band`: 全幅の矢羽根帯（`grid-auto-flow:column`＋各帯 `clip-path`／モバイルは `grid-auto-flow:row`）。
  `flow-vertical-split`: 各ステップ＝2カラム（左大番号／右説明）を縦に並べる（`flex-direction:column`＋`.step{grid-template-columns:88px 1fr}`）。**番号枠は正方形**（`aspect-ratio:1`・KLK-073）。
  `flow-zigzag`（KLK-035・KLK-073調整）: 全幅縦積み（`flex-direction:column`）＋各ステップ内で
  **番号枠と本文の2カラム**。偶数ステップで `order` 反転＝左右交互（モバイルは縦積み・order解除）。
  **番号枠は数字だけを入れる枠なので正方形にする**（`aspect-ratio:1`・幅は数字が収まる程度＝`grid-template-columns:<番号枠の一辺> 1fr`）。
  `1fr 1fr` で半々にすると**番号枠だけが不自然に間延びする**（実際に見本で発生・KLK-073）。**本文側を広く取る**こと。
  ただし**番号枠の背景に画像を置く設計にする場合は、正方ではなく §3.0 の `aspect-ratio:4/3`** とし幅も保持する。
- **STAFF** — `staff-grid`: 顔写真グリッド4列（`grid-template-columns:repeat(4,1fr)`／モバイル2列）。
  `staff-hscroll`: 横スクロール風1列（`flex-wrap:nowrap;overflow-x:auto`＋各 `flex:0 0 200px`）。
  `staff-feature`: 代表1名を大写し＋残りをリスト（`grid-template-columns:1.2fr .8fr`／モバイル縦積み）。
  `staff-list`: 横1行×人数のリスト（`flex-direction:column`＋各 `.st{grid-template-columns:96px 1fr}`）。
  `staff-two-col`: 2カラムのプロフィールカード（`grid-template-columns:repeat(2,1fr)`／モバイル1列）。
  `staff-zigzag`（KLK-035）: 全幅縦積み（`flex-direction:column`）＋各カード `grid-template-columns:200px 1fr`、偶数カードで
  画像 `order` 反転＝画像左右交互（staff-two-col「repeat(2,1fr)・反転なし」・staff-list「96px列・反転なし」とは別／モバイルは縦積み・order解除）。

**(2) オフセット表（`data-columns` × `navPosition` → offset・12セルを全書き下し・KLK-035 で 3col×top を 5 に）:**

| data-columns ＼ navPosition | `top` | `below-hero` |
|---|---|---|
| `1col` | 0 | 3 |
| `2col-full-left` | 1 | 4 |
| `2col-full-right` | 2 | 0 |
| `2col-body-left` | 3 | 1 |
| `2col-body-right` | 4 | 2 |
| `3col` | 5 | 3 |

**(3) 割り当て表（offset → 案A/B/C の pool index・6行を全書き下し・巡回窓 `(o,o+1,o+2) mod 6`・KLK-035）:**

| offset | 案A（`a`） | 案B（`b`） | 案C（`c`） |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

- 全12セルの offset 集合 = {0,1,2,3,4,5}（`3col×top`=5 が offset5 を供給）、割り当て表の全 index 集合 = {0,1,2,3,4,5}
  → **プール全体（6型）が到達可能**（システムとして）。
- 各割り当て行は連続3窓（wrap 込み）で必ず**3値 distinct** → **3案で型が重複しない**。
- キー2値は全案不変 → **同一指示書＝同一割り当て**（決定性）。1col でも `navPosition` を切替れば offset 0 と 3 の両方に届き、
  1col のまま6型のうち到達域が広がる（2次元キーの狙い）。全6型の網羅は golden klk029(offset0={0,1,2})∪klk029b(offset3={3,4,5}) で実証。

**(4) Claude の生成手順（表を"読むだけ"・計算しない・SKILL 手順3 に転記）:**

1. ルートの `data-columns`（正規化後・§8）と `navPosition`（§2.1）を確定する（既に §8/§2.1 で確定済み）。
2. **オフセット表**で該当する1セルを読み、offset（0〜5）を得る（**表を読むだけ・算術しない**）。
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

型を N→N+1 に増やすときは **(a) 型プールへ1列（各セクション同数のマーカー・制約A）を追記、(b) 対応する CSS ブロックを追加、
(c) 割り当て表を N+1 行（連続3窓 `(o,o+1,o+2) mod (N+1)`）に伸ばし、(d) オフセット表の12セルのうち1つ以上を新 offset 値へ振り
値域を 0..N へ広げる（到達可能性の確保）** だけで済む。**選択ロジック・検証の作り直しは不要**（表構造は不変）。
KLK-035 で 5→6（各セクション +`voice-zigzag`/`flow-zigzag`/`staff-zigzag`・3col×top を offset5 に振った）を実施済み。
ABOUT/MENU/GALLERY のプール方式化・ラフ画像からの型抽出も STEP B（別チケット）。

- 代表出力（ゴールデン）: `tests/fixtures/klk029/index-a/b/c.html`（1col×top＝offset0→{0,1,2}）＋ `tests/fixtures/klk029b/index-a/b/c.html`
  （1col×below-hero＝offset3→{3,4,5}）。両者の union で VOICE/FLOW/STAFF 各プールの**6マーカー**全てが実 HTML に出現する（到達可能性の実証・KLK-035）。
  加えて `tests/fixtures/klk035/index-a/b/c.html`（2col-body-right×top＝offset4→{4,5,0}）で 2col 系の表引き決定性を固定（KLK-035・R1）。

#### 12.1.3 単セクション独立プール方式（KLK-036・GALLERY を第1適用・§12.1.1/§12.1.2 と直交・additive）

§12.1.2 は VOICE/FLOW/STAFF を「3セクション**共通** index・型数一致（制約A・N=6）」で束ねる。§12.1.3 は
HERO/MENU/GALLERY/ABOUT（§12.1.1 で archetype 固定だったセクション）を段階的にプール化するため、
**セクションごとに独立した型プール（型数はセクション自由・共通 index に縛られない）**を持たせる新方式を additive に足す。
第1適用は **GALLERY**（HERO/MENU/ABOUT は後続チケットで同機構へ移譲・現状は §12.1.1 の archetype 固定のまま）。
archetype（§12.1/§12.1.1）が担う**並び順・区切り・整列シグネチャは不変**（骨格として残す）。§12.1.3 は「セクション内の型」だけを決める。

**設計原理（§12.1.2 と同一・算術しない・決定的）:** キーは §12.1.2 と同じ全案不変の2値 (`data-columns` × `navPosition`)。
**オフセット表は §12.1.2(2) を共有**（重複定義しない＝ドリフト防止）。割り当てはセクションの型数 N_section に応じた
巡回窓 `(offset+0, offset+1, offset+2) mod N_section` を**表で読む**（算術で導出しない・書き下した表を読むだけ）。

**(1) セクション別型プール（GALLERY/HERO/ABOUT/MENU/SNS/NEWS/PRICE/FAQ/ACCESS/CONTACT/SEARCH・index0=最頻/従来定番・KLK-036/037/044/049/051/052/053/054/055/056）:**

各セクション容器（`.m-gallery`／`.m-hero` の `data-hero`／`.m-about`／`.m-menu`）にプールマーカー1個。各マーカーは**実際に異なる grid/flex 宣言**を
伴う（飾りにしない）。型数は各セクション独立（§12.1.2 の「3セクション一致（制約A）」とは別系統・GALLERY/MENU=4型・HERO/ABOUT=6型）。

**GALLERY プール（`.m-gallery`）:**

| index | マーカー | 見た目（実CSS差）／モバイル |
|---|---|---|
| 0 | `pat-grid` | 均等グリッド（`grid-template-columns:repeat(3〜4,1fr)`・従来／最頻 6件）。モバイル2列 |
| 1 | `pat-wide` | 横帯ワイド（1列の大判を積む。**比率は §3.0 の 4/3**＝「ワイド」は1列いっぱいに使うという意味であり、極端に平たくしない）。モバイル1列 |
| 2 | `pat-mosaic` | 大小モザイク（`grid`＋`grid-column/row span` 強弱）。モバイル2列 |
| 3 | `pat-slider`（KLK-036新） | 横スクロール/カルーセル（`display:flex;flex-wrap:nowrap;overflow-x:auto`＋各 `flex:0 0 <幅>`＋`scroll-snap-type`。矢印/スワイプ送り想定）。**モバイルも横スクロール継続** |
| 4 | `pat-masonry`（KLK-047新） | 大小混在タイルを**長方形にきれいに敷き詰めるベントー型**（縦長・横長・大の混在を隙間なく矩形に収める。`display:grid;grid-template-columns:repeat(4,1fr);grid-auto-rows:<列幅の約0.75倍＝タイルが約4:3の横長に見える基準>;grid-auto-flow:row dense` ＋各タイルに `grid-column:span N`／`grid-row:span N`＝横長/大2×2・縦長1×2・小1×1 の組合せで矩形充填。横長タイルは**縦:横≒3:4**）。**最終行に空きを作らないこと（KLK-072）**: `dense` は既存の穴を後続タイルで埋めるだけで、**タイル総数が足りなければ右下に空白が残る**。実際に見本で空白が出た。**対策＝下の「使ってよい構成」からそのまま選ぶ（KLK-075）**。「合計を倍数に」という抽象的な指示では守られず、**11タイル全部が 1×1・最終行に1セル空き**という結果になった（ベントーの大小混在も失われた）。**次の3構成のいずれかを使うこと**:<br>**(A) 8タイル・2行**: `big(2×2)` ×1 ＋ `1×1` ×4 ＋ `wide(2×1)` ×2 → 4列×3行が完全に埋まる<br>**(B) 6タイル・2行**: `big(2×2)` ×1 ＋ `tall(1×2)` ×2 ＋ `1×1` ×2<br>**(C) 12タイル・3行**: `wide(2×1)` ×2 ＋ `1×1` ×8 （大判なしの均等寄り）<br>**必ず大小を混在させる**（全部 1×1 はベントー型ではない＝`pat-grid` と区別がつかない）。各タイルの見た目の比率は §3.0 の 4/3 を基準に、`grid-auto-rows` を列幅の約0.75倍に置く。cat-0001/cat-0037 系。モバイル2列 |
| 5 | `pat-tab-grid`（KLK-047新） | カテゴリタブ切替＋タイルグリッド（`display:flex;flex-direction:column`＝上部にカテゴリタブ行＋下部にタブごとのパネル `grid-template-columns:repeat(3,1fr)` の**3列×2行程度のサムネタイル**。商品/作品が多いサイト向け）。**クリックで切替（最小インライン JS・外部依存なし。各パネル既定 `display:none`・active のみ `display:grid`・`data-tab`/`data-panel` 対応・MENU tab-switch と同型）**。モバイルはタブ横スクロール・パネル2列 |

**HERO プール（`.m-hero` の `data-hero`・KLK-037）— ★型ごとに整列シグネチャ(justify-content/align-items/text-align)が付随（§12.1 不変条件4）:**

| index | マーカー | 見た目・整列シグネチャ |
|---|---|---|
| 0 | `full` | 全面中央（`center` / `center` / `center`）・従来最頻 |
| 1 | `split` | 左右分割（`space-between` / `center` / `left`） |
| 2 | `band` | 下寄せ帯（`flex-end` / `flex-start` / `left`） |
| 3 | `overlap`（KLK-037新・KLK-038/039調整） | せり出し横長画像＋白背景文言の重なり（`display:grid;grid-template-columns:1fr 2fr`＝**画像列を広め約2/3**・画像を右、白背景文言を左から `transform` で重ね・**画像は角丸なし＝直角でシャープ（`border-radius:0`）**）。**白背景ブロックの幅はキャッチコピーの改行位置にあわせて可変にする**（`width:max-content;max-width:<列幅>` 等・KLK-073）。固定幅にすると、`<br>` で意図した改行位置とブラウザの折り返しが二重にかかり「あなたの笑顔／を、／一生の健康と共／に。」のような**不格好な折り返し**になる（実際に見本で発生）。**整列＝`flex-start` / `center` / `left`（既存3型と非重複＝3案 distinct 維持）**。モバイルは重なり解除・縦積み |
| 4 | `center-scroll`（KLK-040新・KLK-074調整） | 全面ビジュアル＋キャッチを上・スクロール誘導（↓）を下に（`display:flex;flex-direction:column`）。**スクロール誘導はクリックできること**（§4.3.1・KLK-074）。**整列＝`space-between` / `center` / `center`（上下分散・中央）**。モバイルは padding 縮小 |
| 5 | `panel-band`（KLK-040新・KLK-041調整） | 全幅背景ビジュアル＋見出し（上〜中）＋**下部に横一列のフィルム風パネル群**（**`grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:4px`**・**`aspect-ratio:3/2` の横長**（KLK-043）・`border-radius:0` で直角＝フィルムのコマ風・縦幅広め `min-height:480px`）。**帯は MV の左右いっぱいまで伸ばす（KLK-075）**: `.m-hero` の左右 padding を`margin-inline:calc(-1 * <padding>);width:calc(100% + 2 * <padding>)` で相殺し、端まで届かせる。**`max-height` は付けない**。cat-0007/0019 の形。**整列＝`flex-end` / `center` / `center`**。モバイルはパネル3列<br>**なぜ `auto-fit` か（KLK-075）**: 旧実装は `repeat(6,1fr)` ＋ `max-height:150px` だった。`aspect-ratio:3/2` と `max-height` が組み合わさると**幅も 225px で頭打ち**になり、画面が広いほど余りが増えて**左右に大きなマージン**が出た（1680px 幅で余り270px）。`auto-fit` は列数を画面幅にあわせて増減させるので**余りが出ず、パネル幅も 224〜237px に揃う**（1200px→5列237px / 1366px→6列224px / 1440px→6列237px / 1680px→7列237px）。比率は 3/2 のままでこの範囲に収まるため変更不要（高さ150〜158px＝MV 460px の約1/3・KLK-043 の意図を維持） |

**ABOUT プール（`.m-about`・KLK-037）:**

| index | マーカー | 見た目（実CSS差）／モバイル |
|---|---|---|
| 0 | `img-left` | 左画像・右文言（`grid-template-columns:1fr 1fr`）・従来最頻 |
| 1 | `img-right` | 右画像・左文言 |
| 2 | `img-top` | 画像を上・下にキャプション（**画像は §3.0 の 4/3**＝「上に置く」型であり、平たい帯にしない） |
| 3 | `img-overlap`（KLK-037新・KLK-038調整） | せり出し横長画像＋白背景文言の重なり（`display:grid;grid-template-columns:1fr 1fr`・画像を左、白背景文言を右から `transform` で重ね）。**画像は文言背景に対し縦に余裕をとる（`min-height` を大きめ・上下に余白＝圧迫感を避けるモダン志向）**。モバイルは重なり解除・縦積み |
| 4 | `img-circle`（KLK-040新） | 円形/型抜き画像（`border-radius:50%;aspect-ratio:1`）＋横にテキスト（`display:grid;grid-template-columns:1fr 1fr`）。モバイル1列 |
| 5 | `img-zigzag`（KLK-040新） | 画像/文言を左右交互に複数段（`display:flex;flex-direction:column`＋各段 `grid-template-columns:1fr 1fr`＋偶数段 `order` 反転）＝ストーリー型。モバイル縦積み・order解除 |

**MENU プール（`.m-menu`・KLK-044/045/046・6型・mod6。§12.1.1 archetype 固定から移譲）:**

| index | マーカー | 見た目（実CSS差）／モバイル |
|---|---|---|
| 0 | `pat-cards` | カード群（`grid-template-columns:repeat(3,1fr)`・アタリ＋名称＋価格）・従来最頻。モバイル1列 |
| 1 | `pat-list` | 横並びリスト（`display:flex;flex-direction:column`＋各行 `display:flex` の左アタリ＋右テキスト）。モバイルも縦 |
| 2 | `pat-zigzag` | ジグザグ交互（`flex-direction:column`＋各行 `display:flex`＋偶数行 `flex-direction:row-reverse`）。モバイル縦積み |
| 3 | `price-table`（KLK-044新） | 価格表/料金プラン（`display:grid;grid-template-columns:<プラン列 内容列 料金列>` の表形式・見出し行＋料金行を並べる料金一覧）。モバイルは横スクロールまたは列縮小 |
| 4 | `tab-switch`（KLK-045新） | タブ切替（`display:flex;flex-direction:column`＝上部にカテゴリタブ行＋下部に**タブごとのパネル** `grid-template-columns:repeat(2,1fr)`。ランチ/ディナー等の分類切替を想定・active タブを強調）。**クリックで切替（最小インライン JS・外部依存なし。各パネルは既定 `display:none`・active のみ `display:grid`。タブ数=パネル数で `data-tab`/`data-panel` を対応）**。パネル内アイテムの画像は**横長 `aspect-ratio:4/3`**。モバイルはタブ横スクロール・パネル1列 |
| 5 | `feature-large`（KLK-046新） | 大画像＋詳細（`display:grid;grid-template-columns:1.2fr 1fr` の左に**横長の大きなフィーチャー画像**＋右に詳細パネル[名称・価格・説明文・補足リスト]。看板メニュー/一押しプランを**1件**大きく見せる型）。**1件ピックアップの性質上、直下に「MENU 一覧/その他を見る」への導線ボタン（§4.3 共通 `.sec-more`／`.sec-more-btn`・十分な上余白 margin-top≈40px・下層の一覧ページ想定）を常設する**。モバイルは縦積み1列 |

**SNS プール（`.m-sns`・KLK-049/050・6型・mod6。実埋め込み禁止・外部URL0・各型ともアタリ色面で構成）:**

| index | マーカー | 見た目（実CSS差）／モバイル |
|---|---|---|
| 0 | `sns-grid` | Instagram フィード風の**正方サムネ格子**（`display:grid;grid-template-columns:repeat(4,1fr)` の正方タイル `aspect-ratio:1`）。cat-0015 上部フィード系。モバイル3列 |
| 1 | `sns-slider` | 横スクロールの投稿フィード（`display:flex;flex-wrap:nowrap;overflow-x:auto`＋各 `flex:0 0 <幅>`＋`scroll-snap-type`）。GALLERY pat-slider 流用。**モバイルも横スクロール継続** |
| 2 | `sns-cards`（共通カード） | **画像＋キャプション（日付/属性）＋本文30字程度**を**横並び3〜4件**（`display:grid;grid-template-columns:repeat(3,1fr)` の `.sns-card`＝角丸/円形アタリ＋`.cap`＋短文）。お客様の声/ビフォーアフター/SNS投稿で使える**共通カードパターン**（VOICE `voice-cards` と視覚同系＝両セクションで使える）。§4.3 `.sec-more`（もっと見る）と併用可。モバイル1列 |
| 3 | `sns-masonry`（KLK-050新） | 大小混在タイルを長方形に敷き詰めるベントー型（縦長横長を隙間なく矩形に・`display:grid;grid-template-columns:repeat(4,1fr);grid-auto-rows:<基準>;grid-auto-flow:row dense`＋各タイル `grid-column/row:span N`）。cat-0001 系・Instagram 埋込でよく見る。GALLERY `pat-masonry` 同機構（**最終行に空きを作らない**規律も同じ・KLK-072）。モバイル2列 |
| 4 | `sns-reels`（KLK-050新・KLK-050調整） | リール/ストーリーズ帯（`display:flex;flex-wrap:nowrap;overflow-x:auto`＋各 `.sns-reel` の `flex:0 0 <幅>`・アタリは**正方 `aspect-ratio:1`**・`🎬` でリール/動画を示す）。近年のリール普及に対応。**モバイルも横スクロール継続** |
| 5 | `sns-feed`（KLK-050新・KLK-050調整） | 公式埋込ウィジェット風の**投稿カードを横並び3〜4件**（`display:grid;grid-template-columns:repeat(3,1fr)`＋`.sns-post`＝ヘッダ[丸アバター＋ハンドル]＋正方アタリ＋キャプション＋いいね/コメント風アイコン行）。実埋め込みに最も近い見立て（実埋め込みはしない）。モバイル1列 |

**NEWS プール（`.m-news`・KLK-051・6型・mod6。「1カード/行を繰り返す」共通項で FAQ/PRICE へ流用可・各型ともアタリ色面＋仮文言で構成）:**

| index | マーカー | 見た目（実CSS差）／モバイル |
|---|---|---|
| 0 | `news-list` | 日付＋カテゴリバッジ＋見出しの行を縦積み（`display:flex;flex-direction:column`＋各行 `border-bottom` の1行リスト）。従来 default 相当・最頻。cat-0017/cat-0039 Schedule 系。モバイルも縦 |
| 1 | `news-cards`（KLK-051新） | サムネ＋日付＋見出し＋抜粋の**3列カード**（`display:grid;grid-template-columns:repeat(3,1fr)` の `.news-card`＝上アタリ＋日付＋見出し＋短い抜粋）。新着記事/ブログ風。**PRICE のプランカードに流用可**。cat-0039 Nominated 系。モバイル1列 |
| 2 | `news-media`（KLK-051新） | 画像左＋日付/見出し/抜粋右の**横長メディア行を縦積み**（`display:flex;flex-direction:column`＋各行 `display:grid;grid-template-columns:200px 1fr`＝左アタリ＋右テキスト）。記事一覧/特集風。モバイルは縦積み |
| 3 | `news-timeline`（KLK-051新） | **縦の時系列**（`display:flex;flex-direction:column`＝左に日付・縦線・ドット＋右に内容。各行 `grid-template-columns:110px 1fr`・左境界に縦ライン）。沿革/更新履歴向け。cat-0039 Schedule 系。モバイルは線を左端へ寄せ縦積み |
| 4 | `news-table`（KLK-051新） | **日付｜カテゴリ｜見出しの表形式**（`display:grid;grid-template-columns:110px 120px 1fr` の罫線付き行を積む・見出し行＋データ行）。企業IR/お知らせ一覧風。**PRICE の料金表に流用可**。モバイルは横スクロールまたは列縮小 |
| 5 | `news-accordion`（KLK-051新） | 見出しクリックで本文を開閉（`display:flex;flex-direction:column`＋各項目 `<details><summary>`＝ネイティブ開閉・**最小・外部依存/JSなし**）。**FAQ の Q&A 開閉に流用可**。cat-0039 Awards 系。モバイルも縦 |

**PRICE プール（`.m-price`・KLK-052・6型・mod6。NEWS/MENU の「表・カード・リスト・タブ切替・強調」を積極流用・各型ともアタリ色面＋仮文言）:**

| index | マーカー | 見た目（実CSS差）／モバイル |
|---|---|---|
| 0 | `price-table` | 項目｜内容｜料金の**表形式**（`display:grid;grid-template-columns:<項目 内容 料金>` の罫線付き行を積む。見出し行＋データ行）。現行 default「プラン比較の表」相当・最頻。NEWS news-table／MENU 価格表型と同機構。cat-0038 料金表/cat-0051 系。モバイルは横スクロールまたは列縮小 |
| 1 | `price-cards` | プラン比較の**3列カード**（`display:grid;grid-template-columns:repeat(3,1fr)` の `.price-card`＝プラン名＋価格＋含まれる項目リスト＋申込ボタン。松竹梅）。NEWS news-cards／MENU pat-cards 流用。cat-0033 撮影PLAN/cat-0001 コース3カード/cat-0038 A/B/C。モバイル1列 |
| 2 | `price-featured`（KLK-052新） | 3プランのうち**中央を一段大きく強調**（`display:grid;grid-template-columns:1fr 1.3fr 1fr;align-items:center` で中央カードを拡大＋「おすすめ/人気No.1」バッジ）。看板プランを目立たせる型。MENU feature-large の強調思想＋cards。cat-0038 Bプラン「人気No.1」。モバイルは縦積み（強調カードを先頭） |
| 3 | `price-list` | 「**項目 …… ¥価格**」の**シンプルな縦リスト**（`display:flex;flex-direction:column`＋各行 `display:flex;justify-content:space-between` の左項目・右価格）。NEWS news-list／MENU pat-list 流用。cat-0038 各種プラン/cat-0014 お品書き。モバイルも縦 |
| 4 | `price-toggle`（KLK-052新） | 月額/年額・A/B 等を**タブで切替**（`display:flex;flex-direction:column`＝上部タブ行＋下部に**タブごとの料金パネル** `grid-template-columns:repeat(3,1fr)` 等）。**クリックで切替（最小インライン JS・外部依存なし。各パネル既定 `display:none`・active のみ表示・`data-tab`/`data-panel` 対応・MENU tab-switch と同型）**。cat-0038 料金表A/B。モバイルはタブ横スクロール・パネル1列 |
| 5 | `price-matrix`（KLK-052新） | **プラン×機能の比較マトリクス**（`display:grid;grid-template-columns:<機能列＋プラン列×N>` の◯×/数値セル。横にプラン・縦に項目・ヘッダ行＋機能行）。詳細比較向け（SaaS/サービスの定番）。news-table を列方向に拡張。モバイルは横スクロール |

**FAQ プール（`.m-faq`・KLK-053・6型・mod6。NEWS/MENU/PRICE の「アコーディオン・カード・リスト・タブ切替」を積極流用・各型ともアタリ色面＋仮文言・検索欄は静的[飾り]で外部依存ゼロ）:**

| index | マーカー | 見た目（実CSS差）／モバイル |
|---|---|---|
| 0 | `faq-list` | Qバッジ＋質問／A＋回答を**開いた状態で縦積み**（`display:flex;flex-direction:column`＋各項目 `.qa` に `.q`[Qバッジ＋質問]＋`.a`[A＋回答]）。現行 default「Q&A 積み上げ」相当・最頻。cat-0005 系。モバイルも縦 |
| 1 | `faq-accordion`（KLK-053新） | 質問クリックで**開閉**（`display:flex;flex-direction:column`＋各項目 `<details><summary>`＝ネイティブ開閉・＋/−・**最小・外部依存/JSなし**）。現代FAQの定番。NEWS news-accordion 直接流用。cat-0039 Awards 系。モバイルも縦 |
| 2 | `faq-two-col`（KLK-053新） | 開閉できるQ&Aを**2カラム**に並べる（`display:grid;grid-template-columns:1fr 1fr`＋各セル `<details>`）。質問数が多いサイト向け。モバイル1列 |
| 3 | `faq-cards`（KLK-053新） | アイコン＋質問＋短い回答の**3列カード**（`display:grid;grid-template-columns:repeat(3,1fr)` の `.faq-card`＝アイコン＋Q＋短答）。カテゴリ入口/サポートトップ風。NEWS news-cards／MENU pat-cards 流用。モバイル1列 |
| 4 | `faq-category-tabs`（KLK-053新） | **カテゴリタブ切替**＋各タブにQ&A（`display:flex;flex-direction:column`＝上部タブ行＋下部にタブごとのQ&Aパネル）。**クリックで切替（CSS-only・隠しラジオ＋兄弟結合子・各パネル既定 `display:none`・active のみ表示・外部依存なし。MENU tab-switch／PRICE price-toggle と同型）**。FAQ が多くカテゴリ分けする SaaS/サポート向け。モバイルはタブ横スクロール |
| 5 | `faq-search`（KLK-053新） | **検索ボックス（静的アタリ・飾り・送信なし）**＋その下にアコーディオンQ&A（`display:flex;flex-direction:column`＝上部に `.faq-searchbar`[入力欄アタリ]＋下部に `<details>` 群）。ヘルプセンター型。**入力欄は飾りで送信・外部依存なし（SEARCH 同様・NFR-005）**。モバイルも縦 |

**ACCESS プール（`.m-access`・KLK-054・6型・mod6。全型に地図アタリ `.map-atari`[イラスト地図/Google Map 埋め込みを想定したプレースホルダ・実地図/実埋め込みなし・外部URL0・NFR-005]を内包・住所/営業時間は仮文言）:**

| index | マーカー | 見た目（実CSS差・地図の扱い）／モバイル |
|---|---|---|
| 0 | `map-side` | 地図アタリ＋住所/営業時間の**2カラム**（`display:grid;grid-template-columns:1fr 1fr`＝片側 `.map-atari`・反対側に住所・TEL・営業時間）。現行 default「地図＋住所・営業時間」相当・最頻。ABOUT img-left と同機構。モバイル1列（地図→情報） |
| 1 | `map-top` | **横長の大きな地図アタリを上**＋下に住所・アクセス情報（`display:flex;flex-direction:column`＝上 `.map-atari`[全幅・**`aspect-ratio:4/3`**・§3.0]＋下に中央寄せ情報）。cat-0002 下部の全幅地図系。モバイルも縦 |
| 2 | `map-overlay`（KLK-054新） | **全幅の地図アタリの上に情報カードを重ねる**（`display:grid`＝`.map-atari` を全面に敷き、住所カードを `transform`/`align-self` で重ねる）。モダン・不動産/店舗系。cat-0042 系。モバイルは重なり解除・縦積み |
| 3 | `map-hours`（KLK-054新） | 地図アタリ＋**営業/診療時間テーブル（曜日×時間）**（`display:grid;grid-template-columns:<地図列 情報列>`＋情報側に `.hours-table`＝曜日ヘッダ×時間帯行の grid 表）。クリニック/店舗向け。PRICE price-table／NEWS news-table と同機構。cat-0002 診療時間表。モバイルは縦積み・表は横スクロール |
| 4 | `map-cards`（KLK-054新） | **複数店舗を小地図アタリ付きカードで並べる**（`display:grid;grid-template-columns:repeat(3,1fr)` の `.access-card`＝上に小 `.map-atari`＋下に店舗名・住所・TEL）。多店舗/グループ展開。NEWS news-cards／MENU pat-cards 流用。cat-0018 系。モバイル1列 |
| 5 | `map-steps`（KLK-054新） | 地図アタリ＋**駅からの道順ステップ ①→②→③**（`display:flex;flex-direction:column`＝上 `.map-atari`＋下に `.route-steps`[各ステップ番号＋説明を横並び/縦並び]）。アクセス手順の図解・道案内。FLOW flow-row/flow-timeline と同機構。モバイルは縦積み |

**CONTACT プール（`.m-contact`・KLK-055・6型・mod6。フォームは静的アタリ `.c-field`[飾り・実送信なし・`<form action>`/外部URL/iframe なし・NFR-005]・住所/連絡先は仮文言）:**

| index | マーカー | 見た目（実CSS差）／モバイル |
|---|---|---|
| 0 | `contact-cta` | 見出し＋ひとこと＋大きなボタン（`display:flex;flex-direction:column;align-items:center`＝フォームなしの誘導のみ）。現行 default「お問い合わせ誘導（ボタン/リンク）」相当・最頻。cat-0028 系。モバイルも縦 |
| 1 | `contact-form`（KLK-055新） | お名前/メール/電話/内容の**縦積みフォーム**（`display:flex;flex-direction:column`＋各 `.c-field`[ラベル＋アタリ入力欄]＋送信ボタン）。**静的アタリ・実送信なし**。cat-0005/cat-0024 系。モバイルも縦 |
| 2 | `contact-split`（KLK-055新） | **左に連絡先情報（住所/TEL/営業/SNS）＋右にフォーム**の2カラム（`display:grid;grid-template-columns:1fr 1fr`）。モダン定番。ABOUT img-left と同機構。モバイル1列 |
| 3 | `contact-methods`（KLK-055新） | 電話/メール/LINE/来店などの**連絡手段を3〜4カード**（`display:grid;grid-template-columns:repeat(3,1fr)` の `.contact-card`＝アイコン＋手段名＋ボタン）。選択式導線。NEWS news-cards／MENU pat-cards 流用。モバイル1列 |
| 4 | `contact-banner`（KLK-055新） | **全幅の色帯に大見出し＋電話番号＋ボタン**（`display:flex;flex-direction:column;align-items:center` の全幅バンド・フォームなし・強い誘導）。電話重視の店舗向け。HERO band/overlay 流用。cat-0028 系。モバイルも縦 |
| 5 | `contact-steps`（KLK-055新） | **お問い合わせ→ご返信→ご相談の流れステップ**（`display:flex;flex-direction:column`＝`.route-steps` 相当の ①→②→③＋下にフォーム/ボタン）。FLOW flow-row/flow-timeline 流用。cat-0020 ご相談の流れ。モバイルは縦積み |

**SEARCH プール（`.m-search`・KLK-056・6型・mod6。**入力欄は静的アタリ**[飾り・実送信なし・`<form action>`/外部URL/iframe なし・NFR-005]・①コンテンツ展開型4＋②小型窓[配置別]2 の混在）:**

| index | マーカー | 見た目（実CSS差）／モバイル |
|---|---|---|
| 0 | `search-bar` | **中央の大きな検索バー**（`display:flex;flex-direction:column;align-items:center`＝入力欄アタリ＋🔍検索ボタン＋ひとこと）。現行 default「条件検索フォーム面」相当・最頻。①コンテンツ。モバイルも縦 |
| 1 | `search-keywords`（KLK-056新） | **キーワードをボタン化してパネル状に並べる**（`display:flex;flex-wrap:wrap` の `.kw-chip` 群＝タグ/チップをクリック選択風）。ムードジェネレーター的な入口。①コンテンツ。モバイルも wrap |
| 2 | `search-filters`（KLK-056新・KLK-056調整） | **カテゴリ/エリア/価格などの絞り込みフォーム**（`display:grid;grid-template-columns:repeat(3〜4,1fr)` の各項目が **`<details><summary>` のクリック展開ドロップダウン**＝クリックで選択肢リストが開く・最小/外部依存なし＋検索ボタン）。EC/不動産/求人。①コンテンツ。モバイル1列 |
| 3 | `search-sidebar`（KLK-056新） | **左に絞り込みナビ＋右に結果カードグリッド**の2カラム（`display:grid;grid-template-columns:220px 1fr`＝左 `.filter-nav`＋右 `.result-grid` の `repeat(3,1fr)`）。EC定番。ABOUT grid＋news-cards 流用。cat-0011 系。①コンテンツ。モバイル1列 |
| 4 | `search-header`（KLK-056新・KLK-056調整） | **ヘッダー（グローバルナビ）内の小型検索窓**（`display:flex;flex-direction:row;align-items:center` のナビバー＝ロゴ＋メニュー＋**検索窓（入力欄アタリ＋🔍ボタン）をナビ右側「カート」ボタンの左隣に配置**）。ナビ内検索の定番位置。②小型窓(header 想定・入力+ボタン固定)。モバイルは縦 |
| 5 | `search-hero`（KLK-056新・KLK-056調整。旧 search-footer から差し替え） | **メインビジュアル内に検索窓を配置**（`display:flex;flex-direction:column;align-items:center` の全幅ビジュアル帯＝背景アタリ＋中央にキャッチ＋大きめ検索バー[入力欄アタリ＋🔍ボタン]＋人気キーワード）。旅行/不動産/求人/EC で超定番のヒーロー検索。②小型窓(HERO 内配置)。モバイルも縦 |

**(2) 割り当て表（型数別 mod・offset → 案A/B/C の pool index・オフセット表§12.1.2共有・KLK-040 で型数別に一般化）:**

型数 N のセクションは巡回窓 `(offset+0, offset+1, offset+2) mod N` を読む。offset0→(0,1,2) は全 N で共通（既存不変）。

**GALLERY（6型・mod6・KLK-047。HERO/ABOUT/MENU の mod6 と同値）:**

| offset | 案A | 案B | 案C |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

**HERO/ABOUT（6型・mod6・KLK-040。§12.1.2 VOICE系の割り当て表と同値）:**

| offset | 案A | 案B | 案C |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

- **offset0→(0,1,2)** は各プールの index0/1/2＝§12.1.1 の archetype 既定と**一致**（GALLERY=(pat-grid,pat-wide,pat-mosaic)／
  HERO=(full,split,band)／ABOUT=(img-left,img-right,img-top)／MENU=(pat-cards,pat-list,pat-zigzag)）＝1col×top（offset0）の既存生成物・golden はマーカー不変。
- 案A の index = `offset mod N`。offset 集合 {0..5}（オフセット表 §12.1.2 共有・`3col×top`=5 含む）で index 集合 {0..N-1} を
  網羅（新型 index3〜5 は offset3〜5 の案Aで到達。MENU=6型は offset3 の案Aで `price-table`(index3)・offset4 で `tab-switch`(index4)・offset5 で `feature-large`(index5) に到達）。各行は連続3窓（wrap込み）→ **3案 distinct**（N≥3）。
  到達可能性は golden **klk023(offset0→(0,1,2))∪klk036(offset3→HERO/ABOUT/GALLERYは mod6 で(3,4,5))∪klk044(offset3→MENU/GALLERYは mod6 で(3,4,5)＝MENU:price-table/tab-switch/feature-large・GALLERY:pat-slider/pat-masonry/pat-tab-grid)** で実証。

**MENU（6型・mod6・KLK-046。HERO/ABOUT の mod6 と同値・GALLERY の mod4 とは別系統）:**

| offset | 案A | 案B | 案C |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

**SNS（6型・mod6・KLK-050。HERO/ABOUT/GALLERY/MENU の mod6 と同値）:**

| offset | 案A | 案B | 案C |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

**NEWS（6型・mod6・KLK-051。HERO/ABOUT/GALLERY/MENU/SNS の mod6 と同値）:**

| offset | 案A | 案B | 案C |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

**PRICE（6型・mod6・KLK-052。HERO/ABOUT/GALLERY/MENU/SNS/NEWS の mod6 と同値）:**

| offset | 案A | 案B | 案C |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

**FAQ（6型・mod6・KLK-053。HERO/ABOUT/GALLERY/MENU/SNS/NEWS/PRICE の mod6 と同値）:**

| offset | 案A | 案B | 案C |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

**ACCESS（6型・mod6・KLK-054。HERO/ABOUT/GALLERY/MENU/SNS/NEWS/PRICE/FAQ の mod6 と同値）:**

| offset | 案A | 案B | 案C |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

**CONTACT（6型・mod6・KLK-055。HERO/ABOUT/GALLERY/MENU/SNS/NEWS/PRICE/FAQ/ACCESS の mod6 と同値）:**

| offset | 案A | 案B | 案C |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

**SEARCH（6型・mod6・KLK-056。HERO/ABOUT/GALLERY/MENU/SNS/NEWS/PRICE/FAQ/ACCESS/CONTACT の mod6 と同値）:**

| offset | 案A | 案B | 案C |
|---|---|---|---|
| 0 | 0 | 1 | 2 |
| 1 | 1 | 2 | 3 |
| 2 | 2 | 3 | 4 |
| 3 | 3 | 4 | 5 |
| 4 | 4 | 5 | 0 |
| 5 | 5 | 0 | 1 |

**(3) 生成手順（表を"読むだけ"・GALLERY/HERO/ABOUT/MENU/SNS/NEWS/PRICE/FAQ/ACCESS/CONTACT/SEARCH 共通）:** ① `data-columns`（正規化後）と `navPosition` を確定 → ② §12.1.2 の
**オフセット表**で offset(0〜5) → ③ 上の **該当セクションの割り当て表**（GALLERY/MENU/HERO/ABOUT/SNS/NEWS/PRICE/FAQ/ACCESS/CONTACT/SEARCH すべて6型・mod6）で (idxA,idxB,idxC) → ④ 各案の該当容器（`.m-gallery`／`.m-hero` の `data-hero`／
`.m-about`／`.m-menu`／`.m-sns`／`.m-news`／`.m-price`／`.m-faq`／`.m-access`／`.m-contact`／`.m-search`）に `該当プール[index]` のマーカーを付け、対応 CSS を `<head>` に含める。**ACCESS は全型に地図アタリ `.map-atari` を内包**（実地図/実埋め込みなし）。**CONTACT のフォームは静的アタリ `.c-field`**、**SEARCH の入力欄も静的アタリ**（実送信/`<form action>`/外部URL なし）。**HERO は型に整列シグネチャが付随**するので
各案の `.m-hero` 基底に該当型の整列を書く（§12.1 不変条件4・overlap は flex-start/center/left）。archetype の並び順・区切りは §12.1.1 のまま。

**(4) 後方互換・不変（additive）:** 対象セクションが `sections` に無ければ no-op。offset0 は各プール (index0,1,2)＝
既存生成物・klk021/023/034/034b golden と一致（HTML 無変更）。**MENU も本節の対象（KLK-044/045/046・mod6）**。offset0 の MENU=(pat-cards,pat-list,pat-zigzag) は
§12.1.1 の archetype 既定と一致し、既存 klk023/034/034b golden（すべて offset0）はマーカー不変。

**(5) 拡張（STEP B・データ追加だけ）:** 型を N→N+1 は (a)該当プールへ1行追記 (b)CSS1つ (c)割り当て表の `mod` を N+1 に
＋新 offset を出すオフセット表セルの確保（到達可能性）。**各プールの型量産は、同機構にセクション別プールを足す/伸ばすだけ**
（型数は各セクション独立でよい＝§12.1.2 の制約A に縛られない。MENU は KLK-044→045→046 で §12.1.3 化→5型→**6型mod6**へ伸長＝自動振り分け上限6に到達）。

**(6) §12.2 参考準拠との整合:** GALLERY/HERO/ABOUT/MENU/SNS の席替えは §12.1.3 プール基準（VOICE系 `expected_pool` と同型の index 比較）。
KLK-044 で **MENU も §12.1.3 へ移譲**したため、§12.2 の §12.1.1 系既定型表（DEFAULT 転記）は**空（archetype 固定のセクションは無い）**。全セクションが §12.1.3 プール基準で席替えする。

- 代表出力（ゴールデン）: `tests/fixtures/klk036/index-a/b/c.html`（offset3 → 案A=`pat-slider`/`overlap`/`img-overlap`(index3)／
  案B=index0／案C=index1）で GALLERY/HERO/ABOUT の index3 新型の到達と実CSS差を固定。**MENU は `tests/fixtures/klk044/`（offset3 → 案A=`price-table`(index3)／案B=`pat-cards`／案C=`pat-list`）で実証**。offset0 の (0,1,2) は既存 klk023/034 で担保。

**(7) HERO / NAV 埋め込み検索窓（KLK-057・SEARCH 連動・方式B 条件レンダリング・additive）:**

SEARCH を選んだとき、独立した SEARCH セクションではなく **HERO（メインビジュアル）または NAV（グローバルナビ）内に検索窓を実埋め込み**する。

- **検索窓の配置優先（重複させない・SEARCH ∈ sections のとき）**:
  1. **HERO 対応型** `full` / `center-scroll` / `overlap` / `panel-band` → **HERO 内に埋め込み**（prominent）。`.m-hero` 内に **`.hero-search`**（`.hs-input` 入力アタリ＋`.hs-btn` 🔍ボタン）を出力し `.m-hero` に **`data-hero-search="on"`**。
  2. HERO が非対応（`split` / `band` 等）→ **NAV-01 内に埋め込み**（バー型ナビは総じて適用可）。`.m-nav` 内・CTA/カートボタンの左隣に **`.nav-search`**（`.ns-input`＋`.ns-btn`）を出力し `.m-nav` に **`data-nav-search="on"`**。
  3. HERO/NAV いずれにも置けない特殊ケースのみ → 独立 `SEARCH-01` セクション（§12.1.3 SEARCH プール・KLK-056）。※SEARCH プール（KLK-056）はコンテンツとして検索を大きく見せたい場合の**明示指定**用として引き続き有効。
  いずれの埋め込みでも、**独立 `SEARCH-01` セクションは出力しない**（一本化）。
- **未選択（非生成）**: `sections` に SEARCH が無ければ `.hero-search`・`.nav-search` とも**出力しない**（コメントアウトではなく非生成。NAV/HERO は従来どおり）。
- 検索窓は**静的アタリ**（実送信・`<form action>`・外部URL・iframe なし・NFR-005）。`.hero-search` は白いピル（入力＋🔍ボタン）を各型の自然な位置（full/center-scroll＝キャッチ下中央・overlap＝白背景文言内・panel-band＝見出し下）、`.nav-search` はナビ右側・CTA の左隣にコンパクトに置く。
- **出力に仕組みの説明文を含めない**: 「非生成」「フォールバック」等の**デモ/内部挙動の説明はキャプションに出さない**（本文は業種に合った自然な文言のみ。プレースホルダである旨の最小注記は §3 アタリ方針に準ずる）。
- 代表出力（ゴールデン）: `tests/fixtures/klk057/`（HERO 埋め込みON: full/center-scroll/overlap）／`tests/fixtures/klk057b/`（panel-band HERO 埋め込み／SEARCH 未選択で非生成／split で NAV-01 埋め込み）。

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
   - §12.1.2 系（VOICE/FLOW/STAFF）**および §12.1.3 系（GALLERY/HERO/ABOUT/MENU/SNS・KLK-036/037/044/049）**: v の pool index を表引き結果 (idxA,idxB,idxC) の
     idxB/idxC と比べ、一致した案 := `pool[idxA]`（§12.1.3 は §12.1.2 と同型の index 比較・各セクションのプールと mod 割り当て[GALLERY/MENU/HERO/ABOUT/SNS すべて mod6]を使う）。
   - **§12.1.1 archetype 固定のセクションは無くなった（KLK-044 で MENU も §12.1.3 へ移譲）**。下記の §12.1.1 系既定型表は空。
   - どの案とも重複しなければ案B/C は従来のまま。→ いずれの場合も **3案の型は常に3値 distinct**
     （§12.1.1⑤⑦・§12.1.2・§12.1.3 の不変条件を維持）。

**§12.1.1 系の既定型（席替えの参照表・§12.1.1 archetype 固定のセクション用）:** KLK-036/037/044 で GALLERY/HERO/ABOUT/MENU をすべて §12.1.3 プールへ移譲し**本表から除外**したため、
**本表は空**（archetype 固定で席替えするセクションは存在しない）。全セクションが §12.1.3 プール基準の index 比較で席替えする。

| KEY | 案A既定 | 案B既定 | 案C既定 |
|---|---|---|---|
| （なし） | － | － | － |

**本節が触らないもの（スコープ外・不変）:** `data-columns`・`sections` 集合・並び順（`data-section-order`）・
`data-archetype`（3案 distinct のまま）・番地一意性（§2/§14）・§4 文言・アニメ/印刷。HERO の整列シグネチャは
`data-hero` の型に付随して振る（`full`=中央/`split`=左/`band`=下寄せ帯）＝型が distinct ならシグネチャ相違
（§12.1 不変条件4）も維持される。

**生成物マーカー（機械検証フック）:**
- **案Aルート `.mock` のみ**に `data-ref-id="{thumbnails[0].id}"` と `data-ref-colors="reference|specified"`
  （**実効**の配色ソース・§5.1。カラフルfallback は `specified`）を付ける。案B/C のルートにはどちらも付けない。
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
  `tests/fixtures/klk034b/`（カラフルfallback＋HERO 席替え）。参照データはダミー（実カタログ非依存）。

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
8. **画面幅プレビュー切替（REQ-201・KLK-062）**: 生成物は §8 により `@media (max-width: 640px)` を必ず持つ＝
   **レスポンシブ**なので、スマホ表示版を別ファイルで二重生成せず、**比較画面で iframe の幅を切り替えて確認**する。
   案切替と**同じ CSS-only 方式**（第2の隠しラジオ群）で実装する。**追加 JS は使わない**。
   - **隠しラジオ**: `<input type="radio" name="vw" id="vwfull" checked>` / `id="vw768"` / `id="vw375"` を
     `name="variant"` の隠しラジオと**同じ位置**（`.canvas` より前の兄弟）に置く。`name` が異なるため案切替と干渉しない。
   - **セグメント**: variant-bar 内に `.vwseg`（`<label for="vwfull">全幅</label>` /
     `<label for="vw768">768px</label>` / `<label for="vw375">375px</label>`）。
     ハイライトは案切替と同方式（`#vwfull:checked ~ .toolchrome label[for=vwfull]`）。
   - **CSS**: 既定 `.pane iframe { width: 100%; display: block; margin: 0 auto; }`。
     `#vw768:checked ~ .canvas .pane iframe { width: 768px; }` /
     `#vw375:checked ~ .canvas .pane iframe { width: 375px; }`。
     幅を絞ったときに枠が分かるよう `.pane` に中央寄せの余白・背景を持たせる。
   - **`@media print`**: `.vwseg { display: none; }`（chrome 非表示の既存方針に合流）。
   - **プリセットの根拠**: 生成物のブレークポイントは `640px` の1つだけ。`375px`＝モバイル版レイアウト、
     `768px`＝PC版が狭まった状態、`全幅`＝通常、の3つで取りうる見え方を網羅できる。
     **任意幅の数値指定は行わない**（JS が必要になり「JS は原則不要」に反するため。任意幅はブラウザの
     開発者ツールで代替できる）。
   - **`variants:1` には compare.html が無い**ため幅切替も無い。standalone はレスポンシブなので
     ブラウザ幅を変えて確認する。

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
- **コントロール本体**: 「🔄 セクション再生成」＝番地 `<select id="regen-addr">` ＋ 現在型ラベル `<span id="regen-type">`
  ＋「このセクションを再生成」`<button id="regen-btn">`。既定は無効化しておく。
  **★番地は焼き込まない（KLK-078）**: `<option>` は `<option value="">読み込み中…</option>` の1つだけを出力し、
  中身は **`GET /sections` の結果で埋める**。ユーザー自由入力は作らない（＝注入面を作らない）点は不変。

**★なぜ固定列挙をやめたか（KLK-078）**

  以前は `NAV-01`/`MV-01`/`ABOUT-01`/`MENU-01`/`GALLERY-01`/`FOOTER-01` の6番地を**固定で列挙**していた。
  しかし KLK-022 以降、本文セクションは**指示書ごとに変わる**（§2.1 の14語彙から選択）。
  結果、選択肢と実ページが食い違い、**同梱の見本3点すべてで壊れていた**:

  | 見本 | 症状 |
  |---|---|
  | 01 カフェ | `ACCESS-01`・`CONTACT-01` が実在するのに**選べない** |
  | 02 士業 | `MENU-01`・`GALLERY-01` は**404** ／ `NEWS`・`VOICE`・`FAQ`・`CONTACT` が選べない |
  | 03 クリニック | `GALLERY-01` は**404** ／ `FLOW`・`STAFF`・`ACCESS`・`CONTACT` が選べない |

  **生成時に分かっている情報でも、後から変わりうるものは焼き込まない。**実ファイルから読む。

- **型 `<select id="regen-type">`（KLK-079）**: `GET /sections` が返す `pool` で組み立てる。
  現在の型には `（現在）` を付け、既定で選択しておく。**型を持たない番地（`NAV-01`/`FOOTER-01`/`CTA-01`）では
  `disabled` にし、`この番地に型はありません` の1項目だけを出す**。
  **案を切り替えたら読み直す**（案ごとに別の型が割り当たるため・§12.1.2/§12.1.3）。
  ボタン押下時、**現在と違う型が選ばれているときだけ** `desiredType` を body に載せる
  （同じ型なら載せない＝従来の「同じ型で文言だけ作り直す」になる）。
- **結果を正直に出す（KLK-079）**: `/status` の `typeApplied` が `false` のときは、
  完了メッセージを**そのまま出したうえで**「型は変わりませんでした」と分かる形にする。
  成功と同じ見た目にしない。
- **`</body>` 直前のインライン JS（外部依存ゼロ・localhost fetch のみ）**:
  1. 起動時に `GET http://127.0.0.1:8765/health` を **AbortController 約800ms** で試行。**失敗ならコントロールを無効化**し
     「ローカルブリッジ未起動。`python3 draft-gen/bridge.py` を起動するか、Claude Code で `/draft-regenerate {folder} {letter} {番地}`
     でも再生成できます」と案内する（**graceful**・KLK-010 U-7 同型）。
  1'. 成功後、**`GET http://127.0.0.1:8765/sections?folder=&letter=`** を呼び、返った番地で `<select>` を組み立て、
     現在型ラベルを更新する（`textContent` で構築＝注入対策）。`input[name=variant]` の `change` でも呼び直す。
     取得に失敗したらボタンを無効化し、理由を出す（**空の選択肢のまま押させない**）。
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

**VOICE/FLOW/STAFF のプールマーカー再付与（KLK-029・§12.1.2 と対）／GALLERY・HERO・ABOUT のプールマーカー再付与（KLK-036/037・§12.1.3 と対・additive）:**

対象 `.sec` が **VOICE-01 / FLOW-01 / STAFF-01 / GALLERY-01 / MV-01 / ABOUT-01 / MENU-01 / SNS-01** のときは、そのセクションが持つべき**プールマーカー**
（`voice-*`/`flow-*`/`staff-*` は §12.1.2、`.m-gallery` の `pat-*`／`.m-hero` の `data-hero`／`.m-about` の `img-*`／`.m-menu` の `pat-*|price-table` は §12.1.3）を再付与してから
差し替える。マーカーは**対象HTMLだけで自己決定できる**（`instruction.json` 不要・決定的）:

1. 対象HTMLのルート `.mock` から **`data-columns`** と **`data-nav-position`** の実値を読む（両方とも生成時に焼き込み済み・§8/§2.1）。
2. §12.1.2 の**オフセット表**で (`data-columns` × `data-nav-position`) の1セルを読み offset を得る（§12.1.2/§12.1.3 共有）。
3. 対象ファイルの **letter**（`index-{letter}.html` の a/b/c。単案 `index.html` は案A相当＝letter=a）から、
   **VOICE/FLOW/STAFF は §12.1.2 の割り当て表**（mod 6）、**GALLERY/MENU/HERO/ABOUT/SNS は §12.1.3 の割り当て表（すべて mod 6）**の offset 行で pool index を読む。
4. その `pool[index]` のマーカーを容器 `.m-{sec}` に付け、対応 CSS ブロックが `<head>` に無ければ足す（HERO は型に付随する整列シグネチャも
   合わせる・他セクション・配色・ルート属性は不変）。→ 元の生成と**同じ型**が決定的に再現される（表を読むだけ・算術なし）。

**★型の決め方の優先順位（KLK-079）:**

| 順 | 決め手 | 出どころ |
|---|---|---|
| 1 | **`desiredType`**（人が画面で選んだ型） | ジョブ仕様 `.regen.json` |
| 2 | 対象セクションの**現行マーカー**（`data-ref-id` がある参考準拠の案のみ） | 対象HTML（§12.2） |
| 3 | **表引き**（`data-columns` × `data-nav-position` × letter） | §12.1.2 / §12.1.3 |

`desiredType` があるときは 2・3 を**見ない**。容器のマーカーを指定の型**ひとつだけ**に入れ替え
（旧マーカーは必ず外す＝2つ付いたままにしない）、対応 CSS が `<head>` に無ければ足す。
型の見た目は §12.1.2 / §12.1.3 の定義どおりに作るが、**§3.0（アタリ 4/3）・§8.1（狭いカラムでの畳み方）
などの横断ルールは型定義より優先する**（両節の明記どおり）。

**ブリッジが後段で検証する（KLK-079・黙って成功と言わせない）:** 再生成が終わったあと、
ブリッジは対象HTMLを読み直して `desiredType` のマーカーになったかを確かめ、
`/status` の **`typeApplied`**（`true`/`false`/型指定なしは `null`）で返す。
食い違えば「型は {X} になりませんでした（現在 {Y}）」と利用者に伝える。
**このリポジトリは「指示 → LLM が生成 → 守ったかは誰も見ていない」形で4回失敗している**
（KLK-064 の登録未到達、KLK-072〜076 の規約無視）。同じ形を作らないための装置である。

**参考準拠の保持（KLK-034・§12.2 と対）:** 対象HTMLのルート `.mock` に **`data-ref-id` があるファイル（＝参考準拠の案A）**は、
表引き・archetype 既定より**「対象セクションの現行マーカー」を優先**する: 差し替え前の対象 `.sec` 内の容器
（`.m-hero` の `data-hero` ／ `.m-menu`・`.m-gallery`・`.m-about`・`.m-voice`・`.m-flow`・`.m-staff` の型マーカー）を読み取り、
**同じ型マーカーで再生成**する（§12.2 の席替え結果＝参考の型を保持。対象HTMLだけで自己決定・`instruction.json` 不要・決定的）。
現行マーカーが読めない/語彙外のときのみ、上の従来規則（表引き・archetype 既定）へフォールバックする。
`data-ref-id` が無いファイル（従来生成・案B/C）は本段落の対象外＝従来規則のまま。

- ~~`compare.html` の再生成 `<select>` は基本6番地のまま~~ → **KLK-078 で撤回**。`<select>` は `GET /sections` が返す
  **実ページの番地**で組み立てる（§13）。VOICE/FLOW/STAFF もブラウザから選べる。手動
  `/draft-regenerate {folder} {letter} VOICE-01` は従来どおり番地パターン（`^[A-Z][A-Z0-9]*-\d{2}$`）で通る。

**★`.sec` の要素名は `div` とは限らない（KLK-078）**

生成物のセクション容器は `<section class="sec">` / `<nav class="sec">` / `<header class="sec">` / `<footer class="sec">` も使う
（ゴールデン `tests/fixtures/klk007` は `<div>` のみだったため、この差に長く気づけなかった）。
**番地から `.sec` ブロックを特定する処理は、要素名を決め打ちにしないこと。**
`bridge.py` の `find_target_section` が `<div class="sec` 決め打ちだった間、`<section>` を使うページでは
**全番地が 404 になり、🔄 セクション再生成が丸ごと機能していなかった**（見本 01・03 で再現）。
