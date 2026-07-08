# DRAFT_RULES.md — デザインラフHTML生成規約

> このファイルは `/draft-generate` スキル（`.claude/skills/draft-generate/SKILL.md`）が従うマスター規約です。
> 生成される**デザインラフHTML（1案）**はこの規約に完全準拠すること。見た目・構造の正は
> `docs/wireframes/SCR-002-compare.html` の `.mock` 部（プレビュー本体）。生成前に必ず本ファイルを全読する。
>
> 入力契約 = 生成指示書JSON（`schema:"design-draft-instruction"` / `version:1`・`docs/designs/KLK-006.md` §4.4）。
> 対応要件 = REQ-005 / 006 / 007 / 009 / 010（保存部分）/ 011・NFR-002 / 003 / 004 / 005 / 006。

---

## 0. 生成物の位置づけ

- デザインラフ＝**ワイヤーフレームとデザインモックの中間物**。完成イメージ（配色・レイアウト・アタリ画像配置・
  仮文言・スクロール出現アニメ）を非エンジニアが確認・印刷できる単一HTML。
- 本スキルは**1回の生成で1案のみ**を出す（REQ-008 の複数案・SCR-002 比較UI・部分再生成 REQ-103・フリー実写真
  b方式 REQ-104・見本URL反映 REQ-102 は別チケット）。生成指示書の `output.variants` が `3` でも**1案のみ**生成し、
  「複数案は別チケット」と報告する。

---

## 1. 単一ファイル・外部依存ゼロ（NFR-005）

- **単一の静的HTMLファイル**。CSSは `<head>` 内の `<style>`、スクロール出現アニメJSは `</body>` 直前の
  インライン `<script>` に書く。
- **禁止**: `<link rel="stylesheet">`・`<script src="…">`・`@import`・Webフォント（`fonts.googleapis.com` /
  `fonts.gstatic.com`）・CDN（`cdn.*` / `unpkg.com` / `jsdelivr` 等）・外部画像URL（`<img src="http…">`）。
- アイコン・図はUnicode文字（絵文字等）またはインラインSVGで表現する。**アタリ画像は色面のみ**（`<img>` を使わない・§3）。
- 外部URL参照は 0 件（`www.w3.org` / `example.com` `.org` `.net` のみ例外）。実在の顧客名・案件名・URL・
  シークレット（api key / secret / password / token / private key）を含めない（NFR-004 / REQ-011）。

---

## 2. 番地ラベル（REQ-005・部分再生成 REQ-103 の基盤）

各セクションを `.sec`（`position: relative`）で囲み、その左上に番地ラベル `.addr > .pin` を付ける（**画面のみ表示・
印刷では非表示**・§6）。ラベルは以下の6種を各1回、対応セクションに付与する。

| 番地 | セクション |
|---|---|
| `NAV-01` | グローバルナビ |
| `HERO-01` | ヒーロー（メインビジュアル） |
| `ABOUT-01` | コンセプト・紹介 |
| `MENU-01` | メニュー・料金 |
| `GALLERY-01` | ギャラリー・実績 |
| `FOOTER-01` | フッター（CTA＋ナビ） |

```html
<div class="sec">
  <div class="addr"><span class="pin">HERO-01</span></div>
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
- `atari` が `free-photo`（b方式）でも**本チケットは a方式で生成**し「フリー実写真（b方式）は別チケット（REQ-104）」と注記する。

```html
<div class="atari">
  <span class="ic">📷</span>
  <span class="desc">スタイリストの施術風景</span>
  <span class="kw">検索: <b>hair stylist working</b></span>
</div>
<!-- kw 無フォールバック -->
<div class="atari"><span class="ic">📷</span><span class="desc">ボブ</span></div>
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
- **レスポンシブ**: `@media (max-width: 640px)` を必ず定義し、モバイル時に次の変形を明示する（SCR-002:213-223 準拠）:
  - 多カラム → 縦積み（`.m-layout` を `grid-template-columns: 1fr`）。全体2カラムのサイドバーも縦積み時は本文の後ろ（または前）へ回す。
  - グローバルナビ → ハンバーガー相当（`.m-nav ul` を隠し `☰` を表示）。
  - ギャラリーの列を減らす（例 4列 → 2列）。
  - HERO の見出しを縮小。本文は 14px 以上を維持。

---

## 9. 保存規約（REQ-010 / U4）

生成後、**Claude Code が Write で** 次のとおり保存する（ブラウザ保存ではない）。`mockups/` はGit除外（§11・NFR-004）。

- **日付書式**: `YYYY-MM-DD`（例 `2026-07-07`）。生成日をローカル日付で決める。
- **フォルダ**: `mockups/{YYYY-MM-DD}_{案件名}/`
  - 案件名＝生成指示書 `meta.project` を**パス安全化**する: 前後空白除去 → 内部空白を `_` に置換 →
    `/ \ : * ? " < > |` と制御文字を除去。結果が空なら `untitled` とする。
- **ファイル**:
  - `index.html`＝デザインラフ本体（1案）。
  - `instruction.json`＝入力の生成指示書の写し（再実行・監査用・SPEC §7）。
- 複数案（REQ-008）へ拡張する際は同フォルダ内で案別ファイルへ拡張予定（本チケットは1案＝`index.html` のみ）。

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
可視性を切り替えても除外が外れないよう、3ファイルの同期を崩さないこと。
