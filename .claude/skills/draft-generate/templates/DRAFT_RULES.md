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
