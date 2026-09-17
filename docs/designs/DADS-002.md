---
ticket: "DADS-002"
title: "B5タテPowerPointテンプレートの作成"
created: "2026-09-17"
updated: "2026-09-17"
---

# [DADS-002] B5タテPowerPointテンプレートの作成 設計

> このファイルはarchitectが生成・更新するチケット単位の設計書です。
> チケット DADS-002 に対応します。implementer・tester・reviewerが参照します。

## 1. 目的

`dads-a4-template/` の生成系を**テンプレートプロファイル方式**へ拡張し、A4タテに加えて
JIS B5タテを2種（標準版・コンパクト版）生成できるようにする。
利用者が用途に応じて判型と文字サイズの組み合わせを選べる状態にすることが目的。

本サブプロジェクトは `docs/SPEC.md` の対象外のため、REQ/SCR との対応付けは行わない
（仕様は `dads-a4-template/README.md`、受け入れ基準はチケット本文が正）。

## 2. 現状

investigator の調査（チケット DADS-002 の調査レポート Finding 1〜6）にもとづく。

**現在のフロー:**
```
spec.py（モジュールレベル定数） ──import spec as S──→ build_template.py ──→ dist/DADS_A4_Portrait_Template.pptx
   │                                                                              │
   └──import spec as S──→ oxml_helpers.py（S.MM のみ使用）                        ├─→ validate.py       （spec非依存／pptxから実測）
                                                                                  └─→ render_preview.py （spec非依存／pptxから実測）
```

- `build_template.py` は `S.XXX` の形で spec を約250箇所参照している（モジュール属性アクセス）
- `validate.py` / `render_preview.py` は spec を import せず、用紙サイズを `p:sldSz` から読む＝**判型非依存**
- 3スクリプトとも入出力パスは `sys.argv` で差し替え可能（新たな引数設計は不要）
- サンプルページ本文に、用紙寸法・グリッド・書式の数値が **22箇所ハードコード**されている
- `dads-a4-template` を対象とする自動テストは存在しない（A4の回帰を検知できない）

**関連する既存ファイル:**
- `dads-a4-template/build/spec.py` — 寸法・書式・配色・ガイドの唯一の正
- `dads-a4-template/build/build_template.py` — マスター／レイアウト／サンプル13ページの組み立て
- `dads-a4-template/build/oxml_helpers.py` — OOXML生成ヘルパー（`S.MM` のみ依存）
- `dads-a4-template/build/rebuild.sh` — 生成→検証→プレビューの一括実行

## 3. 設計方針

### 採用する方針: プロファイル生成関数 + モジュール差し替え

`spec.py` に「プロファイル名を受け取り、定数一式を持つ名前空間を返す関数」を追加する。
`build_template.py` はモジュールレベルで1つのプロファイルを解決し、`S.XXX` の参照形を**そのまま維持**する。

```python
# spec.py
PROFILES = {"a4": {...}, "b5": {...}, "b5-compact": {...}}

def load(name="a4"):
    """プロファイル名から定数一式を持つ SimpleNamespace を返す。"""
```

```python
# build_template.py（変更は import 行の周辺のみ）
import spec
S = spec.load(os.environ.get("DADS_PROFILE", "a4"))
```

**この方針を採る理由:**

1. `S.XXX` の参照 約250箇所を**一切書き換えない**。差分が最小になり、A4の回帰リスクが最も低い
2. 「寸法・書式を変えるときは `spec.py` だけを編集する」という既存の運用ルール
   （`dads-a4-template/CLAUDE.md`）をそのまま維持できる
3. 1プロセス＝1プロファイルとなるため、プロファイル間の状態汚染が起こり得ない
   （`rebuild.sh` が3回呼び出す）

**代替案と却下理由:**

| 案 | 却下理由 |
|---|---|
| spec をクラス化し各関数へ引数で渡す | `S.XXX` 約250箇所の書き換えが必要。A4回帰のリスクが設計利得に見合わない |
| `spec_a4.py` / `spec_b5.py` / `spec_b5_compact.py` の3ファイルに分割 | グリッド導出ロジックが3重複し、DADSの構成則を直すときに3箇所直す羽目になる |
| 1プロセスで3プロファイルを順に生成（グローバル書き換え） | モジュール定数を書き換える実装になり、プロファイル間の汚染が検知しづらい |

### プロファイルの定義

プロファイルが持つのは用紙寸法だけではなく、**用紙・グリッド・タイポグラフィスケールのセット**である
（コンパクト版は本文14px基準でスタイル全体が変わるため）。派生値（カラム幅・ガター・マージン・
垂直リズム）はすべて下の4つの入力から計算する。

| プロファイル入力 | a4 | b5 | b5-compact |
|---|---|---|---|
| `PAGE_W_MM` × `PAGE_H_MM` | 210 × 297 | 182 × 257 | 182 × 257 |
| `BASE_PX`（本文文字サイズ） | 16 | 16 | **14** |
| `COL_MULT`（カラム幅＝本文の何倍か） | 5 | **4** | 5 |
| `MARGIN_U`（上下マージン＝Uの何倍か） | 8 | **7** | **7** |

`COLS = 6` と `GUTTER = BASE_PX × 2`（DADS規定）は全プロファイル共通。

### 導出される値（implementer はこの表を検証に使う）

| 項目 | a4 | b5 | b5-compact |
|---|---|---|---|
| スライドサイズ (EMU) | 7,560,000 × 10,692,000 | 6,552,000 × 9,252,000 | 6,552,000 × 9,252,000 |
| 本文 | 16px / 12.0pt | 16px / 12.0pt | 14px / 10.5pt |
| カラム幅 | 21.1667mm (16×5) | 16.9333mm (16×4) | 18.5208mm (14×5) |
| ガター | 8.4667mm (32px) | 8.4667mm (32px) | 7.4083mm (28px) |
| 版面幅 | 169.3333mm | 143.9333mm | 148.1667mm |
| 左右マージン | 20.3333mm (9.683%) | 19.0333mm (10.458%) | 16.9167mm (9.295%) |
| 上下マージン | 16.9333mm (5.701%) | 14.8167mm (5.765%) | 14.8167mm (5.765%) |
| 本文上端 / 下端 | 44.9500 / 266.1083 | 42.8333 / 228.2250 | 42.8333 / 228.2250 |
| 本文高 | 221.1583mm | 185.3917mm | 185.3917mm |
| 2カラム片側 | 80.4333mm | 67.7333mm | 70.3792mm |
| 1行の字数 | 40字 | 34字 | **40字（A4と一致）** |
| 2カラム片側の字数 | 19字 | 16字 | **19字（A4と一致）** |
| 1ページに入る本文行数（行高170%） | 30.7行 | 25.8行 | 29.4行 |

### DADS との整合（正直に書くこと）

参照した DADS ファイル:

- `docs/design-system/foundations/layout/index.md` — マージン／カラム／ガターの規定
  （53行「カラム幅は本文の文字サイズの整数倍」、61行「ガターは原則として本文の文字サイズの2倍」）
- `docs/design-system/foundations/typography/index.md` — 文字サイズと行間の規定
  （70・139行「本文は16 CSS px以上が基準」、71行「14pxは領域的な制約がある場合のみ」、
  75行「読み物の本文行高は1.5倍以上を推奨」）
- `docs/design-system/foundations/spacing/index.md` — 余白スケール（基準単位 8 CSS px）
- `docs/design-system/foundations/color/index.md` — コントラスト比の下限（配色は現行から変更しない）

| プロファイル | DADS適合 |
|---|---|
| a4 | 例外なく満たす（現行のまま） |
| b5 | **例外なく満たす。** 本文16px・ガター32px・カラム幅は本文の4倍 |
| b5-compact | **一部は例外規定に依拠する。** グリッド規定（ガター＝本文の2倍／カラム幅＝本文の5倍）は満たすが、<br>本文14pxは「領域的な制約がある場合のみ」の例外に当たる（71行） |

**b5-compact の本文行高について（設計判断）:** DADSのテキストスタイル表で 14px を持つのは Dense系
（行高130% / 120%）のみで、Standard系は16pxが最小である。つまり「14px・行高170%」は
**DADSのスタイル表に存在しない組み合わせ**になる。本設計では読み物としての可読性を優先し、
行高は本文と同じ170%（固定値pt）を採用する。DADS 75行の「本文行高は1.5倍以上を推奨」は満たす。
この逸脱は README に明記する（受け入れ基準に含む）。

## 4. 実装詳細

**ファイル構成（変更・追加）:**
```
dads-a4-template/
├── build/
│   ├── spec.py             ← 変更: PROFILES と load() を追加。既存の定数はプロファイル由来へ
│   ├── build_template.py   ← 変更: import 行の差し替え + サンプル文言22箇所の動的生成
│   ├── regress.py          ← 追加: 基準pptxとのzip内パート比較（U2対応）
│   ├── rebuild.sh          ← 変更: 3プロファイルを順に生成・検証・プレビュー
│   ├── oxml_helpers.py     （変更なし。S.MM は全プロファイル共通）
│   ├── validate.py         （変更なし。pptxから実測するため判型非依存）
│   └── render_preview.py   （変更なし。同上）
├── dist/
│   ├── DADS_A4_Portrait_Template.pptx           （現行のまま）
│   ├── DADS_B5_Portrait_Template.pptx           ← 追加
│   ├── DADS_B5_Portrait_Compact_Template.pptx   ← 追加
│   └── .baseline/DADS_A4_Portrait_Template.pptx ← 追加: 改修前のA4（回帰比較の基準）
└── preview/
    ├── slide01.png 〜 slide13.png, guides.png, preview.pdf  （A4・現行のまま）
    ├── b5/          ← 追加
    └── b5-compact/  ← 追加
```

**A4のpreview出力先を `preview/a4/` へ移さない理由:** DADS-001 の成果物パスと README の参照を
壊さないため（後方互換を優先）。非対称になるが、既に公開・push済みのパスを動かす不利益の方が大きい。

**主要なインターフェース:**

```python
# spec.py
PROFILES = {
    "a4":         dict(PAGE_W_MM=210.0, PAGE_H_MM=297.0, BASE_PX=16, COL_MULT=5, MARGIN_U=8,
                       PAPER_NAME="A4タテ", LABEL="標準"),
    "b5":         dict(PAGE_W_MM=182.0, PAGE_H_MM=257.0, BASE_PX=16, COL_MULT=4, MARGIN_U=7,
                       PAPER_NAME="B5タテ", LABEL="標準"),
    "b5-compact": dict(PAGE_W_MM=182.0, PAGE_H_MM=257.0, BASE_PX=14, COL_MULT=5, MARGIN_U=7,
                       PAPER_NAME="B5タテ", LABEL="コンパクト"),
}

def load(name="a4"):
    """プロファイル名 -> 定数一式を持つ SimpleNamespace。未知の名前は ValueError。"""
```

返す名前空間は**現行 spec.py が公開している名前をすべて同名で保持する**こと
（`MM` `PX` `PT` `px2mm` `U` `S1`〜`S8` `COLS` `COL_W` `GUTTER` `CONTENT_W` `MARGIN_X` `LEFT` `RIGHT`
`col_x` `span_w` `HALF_W` `MARGIN_T` `MARGIN_B` `EYEBROW_Y` … `BODY_H` 配色一式 `T` `guide_pos`
`GUIDES` `GRID_EMU` `ATTRIBUTION` `ATTRIBUTION_NOTE`）。
`build_template.py` 側の `S.XXX` を書き換えないことが本設計の肝である。

追加で公開する名前: `PROFILE`（プロファイル名）、`PAPER_NAME`、`LABEL`、`BASE_PX`、`COL_MULT`。

**タイポグラフィスケール `T` の扱い:**

- `a4` / `b5` — 現行の `T` をそのまま使う（本文16px基準。DADSのテキストスタイルは紙サイズに依存しない）
- `b5-compact` — 本文を14pxにするため、`T` を再割り当てする。方針は次のとおり。

**使用できるサイズは DADS のテキストスタイル表に実在するものに限る**（2026-09-17 改訂）。
DADSが定義するサイズは Display 48 / 57 / 64、Standard 16 / 17 / 18 / 20 / 22 / 24 / 26 / 28 / 32 / 36 / 45、
Dense 14 / 16 / 17 のみである（`foundations/typography/index.md`）。表に無いサイズを新設しない。

| スタイル | a4 / b5 | b5-compact | 備考 |
|---|---|---|---|
| `cover_title` | 48px (Dsp-48) | **36px (Std-36)** | 表紙。40pxはDADSに存在しないため36pxとする |
| `cover_sub` | 20px | 18px (Std-18) | |
| `cover_meta` | 16px | 14px (Dns-14) | |
| `section_no` | 20px | 18px (Std-18) | |
| `section_ttl` | 32px | 28px (Std-28) | |
| `page_title` | 24px | 20px (Std-20) | 本文14pxとの差を確保 |
| `kpi_num` | 32px | 28px (Std-28) | KPIカードの数値 |
| `h2` | 20px | 18px (Std-18) | |
| `h3` | 16px | 16px | 本文(14px)より大きいこと |
| `body` | 16px | **14px (Dns-14)** | 行高170%を維持（上記「設計判断」を参照） |
| `dense` / `dense_b` / `note` / `label` | 14px | **14px（据え置き）** | DADSは14px未満を原則不許容。本文と同サイズになる |

**`b5-compact` で本文と補助テキストが同サイズになる件への対処（Finding 2）:**
文字サイズによる階層が作れないため、次で代替する。これは実装必須事項とする。

1. 色 — 補助テキストは `TEXT_SUB`（#626264・白背景に6.09:1）、本文は `TEXT`（#000000・21:1）
2. ウェイト — `label` / `dense_b` は bold を維持
3. 行高 — 本文は170%、補助テキストは130%（`dense`系の現行値）を維持し、行の密度で差をつける

**サンプル本文22箇所の動的生成（Finding 4）:**

3プロファイル分を手書きで持つと必ず乖離するため、**すべてプロファイル値から組み立てる**。
実装時は次の形にする（例）。

```python
# 変更前
para("A4タテ（210×297mm）の版面は、デジタル庁デザインシステムのレイアウト規定…")
para(f"マージン：左右 20.3mm／上下 16.9mm。版面幅は 169.3mm となります。")
para(f"カラム：6カラム。1カラムの幅は 21.2mm（本文文字サイズ16pxの5倍）です。")

# 変更後
para(f"{S.PAPER_NAME}（{S.PAGE_W_MM:.0f}×{S.PAGE_H_MM:.0f}mm）の版面は、デジタル庁デザインシステムのレイアウト規定…")
para(f"マージン：左右 {S.MARGIN_X:.1f}mm／上下 {S.MARGIN_T:.1f}mm。版面幅は {S.CONTENT_W:.1f}mm となります。")
para(f"カラム：{S.COLS}カラム。1カラムの幅は {S.COL_W:.1f}mm（本文文字サイズ{S.BASE_PX}pxの{S.COL_MULT}倍）です。")
```

1行あたりの字数のような導出値も計算する: `int(S.CONTENT_W / (S.T["body"]["pt"] * 25.4 / 72))`。

> **重要（A4回帰の条件）**: 動的生成後も **A4の文言が1文字も変わらない**ことが必須である。
> 丸め桁を現行の表記に合わせること（`20.3` `16.9` `169.3` `21.2` `8.5` `2.1` のように小数第1位、
> 用紙サイズのみ整数）。Phase 3 完了時点で `regress.py` が差分ゼロを報告しなければ実装が誤っている。

**回帰テスト `regress.py`（U2対応）:**

```
usage: python build/regress.py [--update-baseline]

  既定: dist/.baseline/DADS_A4_Portrait_Template.pptx と dist/DADS_A4_Portrait_Template.pptx を
        zip内のパート単位で比較し、差分があるパート名を列挙して終了コード1で終わる。
  --update-baseline: 現在のA4出力を基準として保存し直す（A4を意図的に変更したときのみ人間が実行）。
```

比較は**パートの中身のみ**を対象とし、zipのタイムスタンプは無視する
（同一内容でもファイル全体のSHA256は毎回変わるため。DADS-001 で確認済みの挙動）。

**処理フロー（`rebuild.sh`）:**
```
1. .venv が無ければ作成して requirements.txt を導入
2. for profile in a4 b5 b5-compact:
     DADS_PROFILE=$profile python build/build_template.py <dist/出力パス>
     python build/validate.py <dist/出力パス>
     PPMM=11.81 python build/render_preview.py <dist/出力パス> <preview/出力先>   # PDF(300dpi相当)
     python build/render_preview.py <dist/出力パス> <preview/出力先>              # PNG(152dpi相当)
3. python build/regress.py            # A4が改修前と一致することを確認
4. いずれかが非ゼロ終了なら set -e で停止する
```

## 5. 影響範囲

| 対象 | 影響の種類 | 対応方針 |
|---|---|---|
| `build/spec.py` | 変更 | プロファイル化。公開する名前は現行と同一に保つ |
| `build/build_template.py` | 変更 | import 行の差し替え、サンプル文言22箇所の動的生成 |
| `build/rebuild.sh` | 変更 | 3プロファイルのループ + 回帰テスト呼び出し |
| `build/regress.py` | 追加 | A4回帰の検知 |
| `build/oxml_helpers.py` | 影響なし | `S.MM` は全プロファイル共通の定数 |
| `build/validate.py` | 影響なし | pptxから実測。判型非依存 |
| `build/render_preview.py` | 影響なし | 同上 |
| `dist/` `preview/` | 追加 | B5 2種の出力とプレビューを追加。A4のパスは変更しない |
| `README.md` / `HANDOVER.md` | 変更 | 3種の寸法表・使い分けの指針・コンパクト版の逸脱の明記 |
| kenesis-loop-kit の既存成果物 | **影響なし** | `dads-a4-template/` 配下で完結。相互参照しない |

## 6. リスク

| リスク | 深刻度 | 軽減策 |
|---|---|---|
| A4の出力が変わってしまう（特に文言の動的生成で丸め表記がずれる） | **high** | Phase 1〜3 を A4のみで進め、各Phase後に `regress.py` で差分ゼロを確認してから B5 へ進む |
| `spec.load()` の返す名前空間に漏れがあり `AttributeError` になる | medium | 現行 spec.py の公開名を一覧化し、`dir()` の差分が空であることを Phase 1 で確認する |
| B5で文字がはみ出す（本文高が 221.16mm → 185.39mm、-16.2%） | medium | プレビュー画像で全ページ目視。特に9「タイポグラフィ」10「カラー」「利用上の注意」の情報量が多いページ。溢れる場合はサンプルの文章量を判型ごとに調整する（レイアウト定義は変えない） |
| b5-compact で本文と補助テキストが同サイズになり階層が消える | medium | 色・ウェイト・行高で代替（実装必須事項として §4 に明記） |
| b5-compact が「DADS準拠」と誤解される | medium | READMEに例外規定依拠と行高逸脱を明記（受け入れ基準） |
| 表紙タイトルが B5 の版面幅に収まらない | low | b5-compact は 48→40px へ縮小。b5(16px基準)は48pxのままとし、プレビューで確認 |

## 7. マイグレーション戦略

段階移行とし、**A4の出力が変わらないことを各段階で確認してから次へ進む**。

| Phase | 内容 | 完了条件 |
|---|---|---|
| 1 | 改修前のA4を `dist/.baseline/` へ保存し、`regress.py` を追加 | `regress.py` が差分ゼロを報告する |
| 2 | `spec.py` をプロファイル化（a4のみ定義）、`build_template.py` の import を差し替え | `regress.py` 差分ゼロ / `validate.py` 無警告 |
| 3 | サンプル文言22箇所を動的生成へ | `regress.py` 差分ゼロ（**文言が1文字も変わらないこと**） |
| 4 | `b5` プロファイルを追加、`rebuild.sh` を2プロファイル対応へ | B5標準が生成され `validate.py` 無警告 / A4は差分ゼロ |
| 5 | `b5-compact` プロファイルを追加（`T` の再割り当て含む） | B5コンパクトが生成され `validate.py` 無警告 / A4は差分ゼロ |
| 6 | `README.md` / `HANDOVER.md` の更新 | 受け入れ基準のドキュメント項目を満たす |

## 8. ロールバック戦略

`dads-a4-template/` 配下で完結しており、他の成果物への影響がないため、ブランチ単位で戻せる。

```bash
# 作業中の巻き戻し
git checkout develop -- dads-a4-template/

# マージ後に問題が出た場合
git revert {マージコミットのハッシュ}
# コミットメッセージ: [DADS-002][REVERT] B5テンプレート対応を取り消し
```

A4のpptxだけを緊急に復旧する場合は `dist/.baseline/DADS_A4_Portrait_Template.pptx` をコピーする。

## 9. 受け入れ条件

チケット本文の受け入れ基準（全体5 / B5共通8 / 標準2 / コンパクト4 / ドキュメント2）を正とし、
設計の観点から次を補足する。

- [ ] `spec.load()` が返す名前空間の公開名が、改修前の `spec.py` の公開名を**すべて**含む
- [ ] `build_template.py` 内の `S.XXX` 参照が改修前と同一である（import 行と文言生成部以外を変更しない）
- [ ] Phase 3 完了時点で `regress.py` が差分ゼロを報告する（A4の文言が1文字も変わらない）
- [ ] `oxml_helpers.py` / `validate.py` / `render_preview.py` に変更が入っていない
- [ ] 3プロファイルの導出値が §3「導出される値」の表と一致する（実測して確認する）
- [ ] b5-compact について、本文14pxの例外規定依拠と「14px・行高170%」がDADSのスタイル表に無い
      組み合わせであることの両方が README に書かれている

## 10. Open Questions

なし（論点1・2は人間が決定済み、論点3は本設計で確定した）。

ただし **implementer が人間の確認を取るべき事項**が1件ある。

- 出力ファイル名と呼称（「標準」「コンパクト」）は利用者が直接目にする。
  `DADS_B5_Portrait_Template.pptx` / `DADS_B5_Portrait_Compact_Template.pptx` を提案値とするが、
  Phase 4 に入る前に人間へ確認すること（チケット論点3に記載済み）。

---

出典：デジタル庁デザインシステムウェブサイト https://design.digital.go.jp/dads/

本設計は DADS の規定を A4・B5 の印刷テンプレート向けに加工したものであり、デジタル庁が作成したものではない。
`b5-compact` プロファイルは DADS の本文文字サイズ基準（16 CSS px以上）に対する例外規定に依拠しており、
またテキストスタイル表に存在しない組み合わせ（14px・行高170%）を採用している。
