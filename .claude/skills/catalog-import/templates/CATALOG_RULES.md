# CATALOG_RULES — 実績カタログのJSONスキーマ・主配色7カテゴリ・タグ付け規約・機密規律

`/catalog-import` が取り込み前に必ず全読する規約の正。`draft-gen/bridge.py` の決定論コア
(`validate_catalog` / `is_safe_catalog_name` / `CANONICAL_COLORS`)と**同一の契約**を人間可読でまとめる。
ここと bridge.py の定数がずれた場合は bridge.py を機械的な正とし、本ファイルを合わせる。

---

## 1. カタログJSONスキーマ(`catalog/catalog.json`・`schema:"klk-catalog"` / `version:1`)

```json
{
  "schema": "klk-catalog",
  "version": 1,
  "generatedAt": "2026-07-09T09:00:00.000Z",
  "entries": [
    {
      "id": "cat-0001",
      "file": "cat-0001.jpg",
      "title": "サロン内観サイト",
      "industry": "美容・サロン",
      "taste": "ナチュラル",
      "colors": ["グリーン"],
      "source": "own",
      "columns": "1col",
      "tags": ["美容", "ナチュラル", "グリーン", "1カラム"],
      "sectionLayouts": {"HERO": "split", "ABOUT": "img-left"},
      "note": "落ち着いた内観写真主体。ヘッダ余白広め",
      "addedAt": "2026-07-09T09:00:00.000Z"
    }
  ]
}
```

### フィールド定義

| パス | 型・値域 | 必須 | 備考 |
|---|---|---|---|
| `schema` | 固定 `"klk-catalog"` | ✓ | 契約識別子。`validate_catalog` が検証 |
| `version` | 整数 `1` | ✓ | スキーマ版。将来変更時にインクリメント |
| `generatedAt` | ISO8601 | - | 最終更新時刻(取り込みのたびに更新) |
| `entries[]` | 配列 | ✓ | カタログ1件＝1エントリ |
| `entries[].id` | `^[A-Za-z0-9][A-Za-z0-9._-]*$`(安全名) | ✓ | 画像id。一意な連番(`cat-0001`…)。`/catalog/img/` の照合キー |
| `entries[].file` | 安全名(`..`/`/`/`\` 不可) | ✓ | `catalog/img/` 内の実体ファイル名(移動後の名前) |
| `entries[].title` | string | - | 表示ラベル。**社外秘可**(＝`catalog/` 配下にのみ置く) |
| `entries[].industry` | string(自由文字列可) | - | 業種フィルタのキー。暫定業種を叩き台に前進(OQ-003 は本チケットで確定不要) |
| `entries[].taste` | string(単一) | - | テイスト語彙(暫定7種・自由文字列で前進) |
| `entries[].colors` | string配列・各値は下記7カテゴリ。**第1主配色が必須(1件以上)・最大3件**。マルチカラーは単独指定 | ✓ | 主配色(第1必須・第2/第3は任意)。**7カテゴリ外の値を入れない** |
| `entries[].source` | `"own"` \| `"ref"` | ✓ | own=自社実績(緑バッジ)/ref=収集見本(橙バッジ・第三者著作物) |
| `entries[].columns` | `1col`/`2col-full-left`/`2col-full-right`/`2col-body-left`/`2col-body-right`/`3col` | - | カラム構成ヒント(DRAFT_RULES §8) |
| `entries[].tags` | string配列 | - | 表示用の非正規化タグ(キーワード検索対象)。省略時は構造値から導出 |
| `entries[].sectionLayouts` | オブジェクト(`"SECTION_KEY":"型マーカー"`)。キーは7セクション(HERO/ABOUT/MENU/GALLERY/VOICE/FLOW/STAFF)・1セクション1型 | - | セクション別レイアウト型(参考準拠生成 KLK-031 の土台)。**値の語彙の正は DRAFT_RULES §12.1.1/§12.1.2(ここには再掲しない・乖離時は DRAFT_RULES に合わせる)**。キー省略＝未判定/該当なし、値 `"other"`＝プール外。`null` は使わない |
| `entries[].note` | string | - | 用途メモ(キーワード検索対象) |
| `entries[].addedAt` | ISO8601 | - | 取り込み日時(「新しい順」並び替え用) |

`validate_catalog` は最低限 **schema / version / entries=list / 各entryの id・file・source∈{own,ref}・
colors⊆7カテゴリ・件数1..3(第1必須・最大3件)・マルチカラー単独排他** を検証する。id/file の欠落や
安全名違反、`source` の逸脱、7カテゴリ外の色、空配列/4件以上、マルチカラーと具体色の併用は reject。

`sectionLayouts` は present のとき **object かつ各値が非空文字列**であることを構造(shape)検証する
(array・数値・空文字は reject / absent は OK)。**値の語彙照合は行わない**(品質＝正しいマーカーかは、
色と同じく M群/人間確認ゲートで担保する。色の集合メンバーシップが S群なのは正が bridge.py にあるからで、
レイアウト型は正が DRAFT_RULES §12.1.x にあるため対称的に「機械は shape だけ・語彙は人間」とする)。

---

## 2. 主配色の7カテゴリ(`CANONICAL_COLORS`・§3.3)

```
グリーン / ブルー / レッド / ゴールド / ピンク / モノトーン / マルチカラー
```

- 主配色は **AI(Claude)の視覚推定**で上記7カテゴリから付ける。**第1主配色が必須・第2/第3は任意(最大3件)**。**画素の厳密HEXは求めない**。
- 単一色を決められない多色サイトは `マルチカラー` を**単独**で付ける(他色と併用不可・具体色との混在は reject)。マルチカラーは「多色サイトの受け皿」であり色ではなく色集合を表す意味軸。
- 理由: 本環境に PIL/Pillow が無く、Python標準ライブラリで JPEG/PNG の画素デコードは不可(NFR-005 外部依存禁止)。
  厳密HEX抽出は外部依存禁止と両立しないため、7離散カテゴリの視覚推定を唯一の方式とする。
- ベージュ・ホワイト等の微細色は**フィルタ対象外** ＝ `tags`/`note` の自由記述に置く(フィルタは7カテゴリで統一)。
- 品質(推定が妥当か)は非決定的 → **M群(人間の目視確認)**。決定論チェックは「`colors` の各値が7カテゴリに入るか」の
  集合メンバーシップ＋「件数1..3・マルチカラー単独排他」に**限定**する(タグ品質をS群に課さない)。

---

## 3. タグ付け規約(視覚認識の指針)

- **業種**: 画面の被写体・文言・雰囲気から最も近い1業種。断定できないときは候補を挙げ、人間確認で確定する。
- **テイスト**: 配色・余白・書体感から単一。
- **主配色**: 支配的な色面を7カテゴリへ寄せる。第1主配色を必須で1件、拮抗する色があれば第2/第3を任意で足す(最大3件)。単一色を決められない多色サイトは `マルチカラー` を単独指定(他色と併用しない)。
- **カラム**: 全体レイアウトから DRAFT_RULES §8 の6値に近いものを推定(任意)。
- **セクション別レイアウト型**(`sectionLayouts`・任意): 参考画像に写る各セクションを **DRAFT_RULES §12.1.1/§12.1.2 の型プール**へ寄せ、1セクション1型で提案する。対象は語彙を持つ7セクション(HERO/ABOUT/MENU/GALLERY/VOICE/FLOW/STAFF)のみ。**該当セクションが画像に無い/未判定はキーを省略**、**近い型が無い(プール外)は `"other"`**。**型マーカーの語彙は再掲しない(正は DRAFT_RULES §12.1.x・乖離時はそちらに合わせる。独自語で付けない)**。確定は人間承認後のみ。
- **own/ref**: 既定 `own`。収集見本は取り込み指示で `ref` が明示された分のみ `ref` にする。
- **確定は人間承認後のみ**。推測で `catalog.json` に書き込まない(登録前に確認・修正できる導線を必ず通す)。

---

## 4. 機密規律(REQ-011 / NFR-004・最重要)

- 画像・`catalog.json`・案件名(`title`/`note`)は**社外秘**。**`catalog/` 配下(Git除外)にのみ**保存する。
  `catalog/` は `.gitignore`・`.gitignore.public`・`.gitignore.private` の3ファイルで除外済み。
- **`catalog/` の外へ画像・JSON・案件名を書き出さない**。committed の器 `draft-gen/catalog.html` には
  カタログ実データ(案件名・画像)を**一切焼き込まない**(器は同一オリジン fetch でのみデータを読む)。
- オフラインスナップショット `catalog/catalog.html`(データインライン・機密)を作る場合も**`catalog/` 配下に限定**する。
- **収集見本(`ref`)は第三者著作物**。UI・JSON・報告に「**社内の参考目的のみ。公開・再配布・そっくり再現の材料に
  しません**」を反映する(ワイヤー SCR-004 の注記が正)。
- 安全名でないファイル名・`catalog/.pending/` の外を指す入力は取り込まない(パストラバーサル/注入対策)。
- シークレット(api key / secret / password / token / private key)を `catalog/` の外へ出さない。
