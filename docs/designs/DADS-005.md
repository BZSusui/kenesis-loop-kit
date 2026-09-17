---
ticket: "DADS-005"
title: "標準搭載フォント版テンプレートを追加する"
created: "2026-09-17"
updated: "2026-09-17"
---

# [DADS-005] 標準搭載フォント版テンプレートを追加する 設計

## 1. 目的

PC標準搭載フォントのみで構成したテンプレートを A4・B5 で追加し、官公庁納品に耐える状態にする。
既存の Noto Sans JP 版は別枠として残す（人間の決定）。

## 2. 現状

- `build_template.py` の **モジュール定数 `FONT = "Noto Sans JP"`** が、テーマの
  `majorFont` / `minorFont` の `latin` `ea` `cs` `script="Jpan"` すべてに使われている（131-134行）
- `FONT_FALLBACK = "Yu Gothic Medium"` は定義されているが**どこからも参照されていない**（デッドコード）
- 判型は `spec.PROFILES` で切り替わるが、**書体はプロファイルの外**にある
- `render_preview.py` は `_FONT_CANDIDATES` に Noto のパスのみを持ち、
  和文・欧文を1つのフォントで描画している

## 3. 設計方針

### 方針1: 書体をプロファイルの属性にし、判型 × 書体でプロファイルを構成する

`spec.PROFILES` に `FONT_JP` / `FONT_LATIN` を追加し、6プロファイルにする。

| プロファイル | 判型 | 和文 | 欧文 |
|---|---|---|---|
| `a4` | A4 | Noto Sans JP | Noto Sans JP |
| `b5` | B5 | Noto Sans JP | Noto Sans JP |
| `b5-compact` | B5 | Noto Sans JP | Noto Sans JP |
| `a4-std` | A4 | **BIZ UDPGothic** | **Arial** |
| `b5-std` | B5 | **BIZ UDPGothic** | **Arial** |
| `b5-compact-std` | B5 | **BIZ UDPGothic** | **Arial** |

`-std`（standard fonts＝標準搭載フォント）を接尾辞にする。判型の定義は既存3つと**完全に共有**し、
違いは書体だけにする。グリッド・タイポグラフィスケール・余白は一切変えない。

**代替案と却下理由:**

| 案 | 却下理由 |
|---|---|
| 書体を独立した軸にして直交させる（判型×書体の総当たり） | 将来 判型か書体が増えるたび組み合わせが増える。現時点で6個なら素直に列挙するほうが読みやすい |
| `FONT` を環境変数で切り替える | 出力の内容が環境変数で変わると、どの成果物がどの書体か追えなくなる。再現性の観点でも不可 |
| 既存プロファイルの書体を差し替える | 人間が「Noto 版は別枠として残す」と決定済み |

### 方針2: 和文と欧文を分けて指定する（F2・F3 への対応）

BIZ UDPGothic 単体では欧文が間延びし版面が崩れるため、**`latin` に Arial、`ea` に BIZ UDPGothic** を指定する。

```xml
<a:majorFont>
  <a:latin typeface="Arial"/>
  <a:ea typeface="BIZ UDPGothic"/>
  <a:cs typeface=""/>
  <a:font script="Jpan" typeface="BIZ UDPGothic"/>
</a:majorFont>
```

Noto 版は現行どおり latin・ea とも Noto Sans JP（出力を変えないため）。

### 方針3: 出力を系統ごとに分ける（人間の要件）

```
dist/
├── DADS_A4_Portrait_Template.pptx              （Noto版・現行のまま）
├── DADS_B5_Portrait_Template.pptx
├── DADS_B5_Portrait_Compact_Template.pptx
├── .baseline/                                   （A4の回帰基準）
└── stdfont/                                     ← 標準搭載フォント版
    ├── STD_A4_Portrait_Template.pptx
    ├── STD_B5_Portrait_Template.pptx
    └── STD_B5_Portrait_Compact_Template.pptx

preview/
├── slide01.png 〜 / b5/ / b5-compact/           （Noto版・現行のまま）
└── stdfont/
    ├── a4/ / b5/ / b5-compact/
```

**フォルダ名とファイル名の両方で分ける。** Noto 版の既存パスは一切動かさない（後方互換）。

### 方針4: プレビューの書体解決を pptx から行う（F4 への対応）

`render_preview.py` を次のように拡張する。

1. **pptx のテーマから `latin` と `ea` の typeface を読む**
2. フォント名 → 実ファイルのマッピングで解決する
3. **文字ごとに和文・欧文を判定してフォントを切り替える**（`ord(ch) < 0x2E80` を欧文とみなす）

```python
FONT_FILES = {
    "Noto Sans JP":  {False: [...NotoSansJP-Regular...], True: [...Bold...]},
    "BIZ UDPGothic": {False: [...BIZUDPGothic-Regular...], True: [...Bold...]},
    "Arial":         {False: [...Arial.ttf...], True: [...Arial Bold.ttf...]},
}
```

**Noto 版のプレビューが1ピクセルも変わらないこと**が制約（latin も ea も Noto なので、
文字ごとの切り替えを入れても結果は同じになるはず）。これは PNG のバイト比較で確認する。

フォントが見つからない場合は、**どの書体が無いのかを名指しして**終了する
（現行の「日本語フォントが見つかりません」より具体的にする）。

## 4. 実装詳細

**変更するファイル:**
```
build/spec.py            PROFILES に FONT_JP / FONT_LATIN を追加し、6プロファイルへ
build/build_template.py  FONT 定数を廃止し S.FONT_JP / S.FONT_LATIN を使う。
                         使われていない FONT_FALLBACK を削除する
build/render_preview.py  テーマから書体を読み、和文/欧文で切り替えて描画する
build/rebuild.sh         6プロファイルをループする
build/overflow.py        変更不要（render_preview の解決を使うため自動的に追従する）
build/regress.py         変更不要（A4 Noto 版のみを見る）
README.md                2系統の使い分けとフォント選定の根拠
```

**処理フロー（rebuild.sh）:**
```
for profile in a4 b5 b5-compact a4-std b5-std b5-compact-std:
    DADS_PROFILE=$profile build_template.py <出力先>
    validate.py <出力先>
    render_preview.py <出力先> <プレビュー先>
    overflow.py <出力先>
regress.py        # A4 Noto 版が変わっていないこと
```

## 5. 影響範囲

| 対象 | 影響 | 対応方針 |
|---|---|---|
| Noto 版3種の `.pptx` | **変えない** | `regress.py` で担保。プロファイル定義を共有しても出力は同一 |
| Noto 版のプレビューPNG | **変えない** | 描画ロジック拡張後にバイト比較で確認 |
| `overflow.py` / `regress.py` | 変更なし | — |
| 既存の kenesis-loop-kit 成果物 | 影響なし | `dads-a4-template/` 内で完結 |

## 6. リスク

| リスク | 深刻度 | 軽減策 |
|---|---|---|
| 書体を変えると行長が変わり、ページから溢れる | **high** | `overflow.py` を6種すべてに掛ける。1行の字数が Noto 版と一致することも検証する |
| プレビュー描画の拡張で Noto 版の出力が変わる | medium | PNG のバイト比較。1ピクセルでも違えば実装の誤り |
| Arial と BIZ UDPGothic のベースラインがずれる | medium | 実文で描画して目視確認する（すでに比較画像で自然に見えることは確認済み） |
| BIZ UD が無い環境でビルドできない | medium | フォント名を名指しして止める。README に必要なフォントを明記する |
| MS ゴシックが混入する | medium | 生成物の全XMLを走査して `MS Gothic` `MS PGothic` が無いことを検査する（受け入れ基準） |

## 7. マイグレーション戦略

| Phase | 内容 | 完了条件 |
|---|---|---|
| 1 | `render_preview.py` を和文/欧文の切り替え対応にする（書体は Noto のまま） | Noto 版のプレビューPNGがバイト一致 |
| 2 | `spec.py` に `FONT_JP` / `FONT_LATIN` を追加（既存3つは Noto） | `regress.py` 一致・プレビュー不変 |
| 3 | `build_template.py` がプロファイルの書体を使うようにする | 同上 |
| 4 | `-std` 3プロファイルを追加、`rebuild.sh` を6種対応へ | 6種が生成され validate/overflow が [OK] |
| 5 | 検証（字数の一致・MSゴシック不在・再現性）と README 更新 | 受け入れ基準を満たす |

## 8. ロールバック戦略

```bash
git revert {マージコミット}   # [DADS-005][REVERT] 標準搭載フォント版の追加を取り消し
```

`-std` プロファイルを `PROFILES` から削除し `rebuild.sh` のループを3つに戻せば、DADS-004 時点に戻る。

## 9. 受け入れ条件

チケット本文の受け入れ基準を正とし、設計の観点から次を補足する。

- [ ] `-std` プロファイルは判型の定義（用紙・グリッド・タイポグラフィ）を既存3つと共有し、
      差分が `FONT_JP` / `FONT_LATIN` だけである
- [ ] `build_template.py` からモジュール定数 `FONT` と未使用の `FONT_FALLBACK` が無くなっている
- [ ] `render_preview.py` は pptx のテーマから書体を読む（ハードコードした書体名を持たない）
- [ ] フォントが見つからないとき、どの書体が無いのかがメッセージに出る

## 10. Open Questions

なし。

---

出典：デジタル庁デザインシステムウェブサイト https://design.digital.go.jp/dads/

本設計は DADS の規定を印刷テンプレート向けに加工したものである。書体を Noto Sans JP から
標準搭載フォントへ差し替える判断は、DADS が「OSやデバイスネイティブのシステムフォントの使用を
制限するものではない」と定めていることにもとづく（`foundations/typography/index.md` 20行）。
