# DADS 参照ガイド（エージェント向け）

> このファイルはデジタル庁デザインシステム由来の本文ではなく、kenesis-loop-kit 側で
> 追加した参照ルールです。出典・ライセンスは [_ATTRIBUTION.md](_ATTRIBUTION.md) を参照。

## 参照の大原則

**125ファイルを全件読み込んではならない。** コンテキストを浪費し、無関係な仕様で判断が濁る。

1. まず `MANIFEST.md` を読む（全収録ファイルの索引。日本語タイトル＋概要付き）
2. 目的に関係するファイルだけを開く（通常1〜5ファイル）
3. 引用・準拠した場合は、参照したパスを設計書・チケットの `related_files` に記録する

## この一式に「含まれないもの」

DADSのMarkdownは**仕様の記述**であり、実装値は含まれていない。ここを取り違えると存在しない
値を捏造することになる。

| 求めているもの | この一式にあるか | 実際の所在 |
|---|---|---|
| コンポーネントの用途・構造・状態・アクセシビリティ要件 | **ある** | `components/{slug}/index.md` |
| カラーの**設計原則**とコントラスト比の下限 | **ある** | `foundations/color/index.md` |
| 余白の**基準単位（8 CSS px）とスケールの組み方** | **ある** | `foundations/spacing/index.md` |
| 具体的なHEX値・デザイントークン定義 | **ない** | コードスニペット（GitHub）／Figma。カラーページ内の色見本は画像参照のみ |
| フォントファミリの実ファイル | **ない** | 別途調達 |
| 実装コード（HTML/React） | **ない** | コードスニペット（GitHub） |

したがって**具体的な色は「DADSの原則を満たす値をプロジェクト側で決める」**という運用になる。
DADSが定める下限は次のとおり（`foundations/color/index.md`）。

| 対象 | コントラスト比の下限 |
|---|---|
| テキストとその背景色 | 4.5:1 以上（常時） |
| 枠線・ディバイダー等の非テキスト要素と隣接背景 | 3:1 以上 |
| プライマリーカラーと主要背景色 | 4.5:1 以上 |
| セカンダリー／ターシャリーカラーと主要背景色（隣接表示要素として使う場合） | 3:1 以上（テキストに使うなら 4.5:1 以上） |

また**フォーカスカラーは Yellow-300 と Black の2重構造で、いかなる場合も変更してはならない**と
明記されている（`foundations/color/index.md` 機能カラー節）。

## 目的別の参照先

| 知りたいこと | 参照パス |
|---|---|
| 全収録ファイルの索引 | `MANIFEST.md` |
| ライセンス・出典条件 | `introduction/notices/index.md` |
| カラースキームの組み方・コントラスト下限・リンク色・フォーカス色 | `foundations/color/index.md` |
| 余白の基準単位とスケール設計 | `foundations/spacing/index.md` |
| タイポグラフィ | `foundations/typography/index.md` |
| レイアウト・グリッド | `foundations/layout/index.md` |
| 角の形状 / 影 / アイコン / リンクテキスト | `foundations/corner-shapes|elevation|icon|link-text/index.md` |
| アクセシビリティの方針と根拠 | `guidance/accessibility/index.md` |
| スタイルガイド（自プロジェクト向け仕様書）の作り方 | `guidance/style-guides/index.md` |
| ロール別の使い方 | `guidance/how-to-use/index.md` |
| ウェブアクセシビリティ試験の実施例・結果 | `webaccessibility/index.md` |
| 各コンポーネントの更新履歴 | `components/{slug}/changelog.md` |

## UIコンポーネント 49種の参照パス

| コンポーネント | 参照パス |
|---|---|
| アコーディオン | `components/accordion/index.md` |
| 引用ブロック | `components/blockquote/index.md` |
| ボトムナビゲーション | `components/bottom-navigation/index.md` |
| パンくずナビゲーション | `components/breadcrumb/index.md` |
| ボタン | `components/button/index.md` |
| カード | `components/card/index.md` |
| カルーセル | `components/carousel/index.md` |
| チェックボックス | `components/checkbox/index.md` |
| チップラベル | `components/chip-label/index.md` |
| チップタグ | `components/chip-tag/index.md` |
| コンボボックス | `components/combobox/index.md` |
| 日付ピッカー／カレンダー | `components/date-picker/index.md` |
| 説明リスト | `components/description-list/index.md` |
| ディスクロージャー | `components/disclosure/index.md` |
| ディバイダー | `components/divider/index.md` |
| ドロワー | `components/drawer/index.md` |
| 緊急時バナー | `components/emergency-banner/index.md` |
| ファイルアップロード／ドロップエリア | `components/file-upload/index.md` |
| ハンバーガーメニューボタン | `components/hamburger-menu-button/index.md` |
| ヘッダーコンテナ | `components/header-container/index.md` |
| 見出し | `components/heading/index.md` |
| 水平メニュー | `components/horizontal-menu/index.md` |
| 画像 | `components/image/index.md` |
| イメージスライダー | `components/image-slider/index.md` |
| インプットテキスト | `components/input-text/index.md` |
| ランゲージセレクター | `components/language-selector/index.md` |
| 箇条書きリスト | `components/list/index.md` |
| メガメニュー | `components/mega-menu/index.md` |
| メニューリスト | `components/menu-list/index.md` |
| メニューリストボックス | `components/menu-list-box/index.md` |
| モバイルメニュー | `components/mobile-menu/index.md` |
| モーダルダイアログ | `components/modal-dialog/index.md` |
| 注釈ブロック | `components/notice-block/index.md` |
| ノティフィケーションバナー | `components/notification-banner/index.md` |
| ページナビゲーション | `components/page-navigation/index.md` |
| プログレスインジケーター | `components/progress-indicator/index.md` |
| ラジオボタン | `components/radio/index.md` |
| リソースリスト | `components/resource-list/index.md` |
| スクロールトップボタン | `components/scroll-top-button/index.md` |
| 検索ボックス | `components/search-box/index.md` |
| セレクトボックス | `components/select/index.md` |
| ステップナビゲーション | `components/step-navigation/index.md` |
| スイッチ | `components/switch/index.md` |
| タブ | `components/tab/index.md` |
| テーブル／データテーブル | `components/table/index.md` |
| テーブルコントロール | `components/table-control/index.md` |
| テキストエリア | `components/textarea/index.md` |
| 目次 | `components/toc/index.md` |
| ユーティリティリンク | `components/utility-link/index.md` |

> 名称は改訂されることがある（v2.17.1で「パンくずリスト」→「パンくずナビゲーション」）。
> 最新の正は `MANIFEST.md` と各 `changelog.md`。
