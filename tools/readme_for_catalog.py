#!/usr/bin/env python3
"""配布物の README.md を「カタログ同梱版（A）」の内容へ差し替える（KLK-077）。

なぜ別ファイルにするか:
  リポジトリの README.md は **B（カタログなし）の内容が正**。
  普段開く README が配布バリエーションで揺れると、どちらが本当か分からなくなる。
  そこで README.md にはマーカーだけを置き、A を組み立てるときに
  **配布物側のコピーだけ**を書き換える。

使い方: python3 tools/readme_for_catalog.py <配布物のREADME.md> <catalog.json>
"""
import json
import os
import re
import sys

INTRO_BEGIN = "<!-- KLK-077:CATALOG-INTRO:BEGIN -->"
INTRO_END = "<!-- KLK-077:CATALOG-INTRO:END -->"
HANDLING_BEGIN = "<!-- KLK-077:HANDLING-EXTRA:BEGIN -->"
HANDLING_END = "<!-- KLK-077:HANDLING-EXTRA:END -->"


def intro_text(n_total, n_own, n_ref):
    return """このパッケージには、**実績カタログが入った状態**でお渡ししています（現在 **{total}件**）。
自分で登録しなくても、生成設定画面の「参考にする素材」からすぐに選べます。

| 内訳 | 件数 | 中身 |
|---|---|---|
| 自社実績（`own`） | {own}件 | 過去に制作したデザインラフ |
| 収集見本（`ref`） | {ref}件 | 参考として集めた他社サイトのキャプチャ |

> **このカタログは社内限定です。** 配布にあたり、AI利用管理責任者の確認を得ています。
> 条件は「**社内でのみ使用すること**」です。詳しくはこの README 末尾の「取り扱いの注意」を必ずお読みください。

自分の実績を足したいときは、下の手順で追加できます（追加した分もこのPCの中だけに保存されます）。""".format(
        total=n_total, own=n_own, ref=n_ref
    )


HANDLING_TEXT = """> ### ★このパッケージには実績カタログが入っています
>
> - **社内でのみ使用してください。** 社外への持ち出し・共有・アップロードはしないでください
> - **フォルダごとの再配布はしないでください。** 必要な人がいたら**このパッケージを渡してくれた人**へお知らせください
> - **誰が持っているかを配布元が把握しています。** 別のPCへコピーするときは一報をお願いします
> - **退職・異動のときは、このフォルダごと削除してください**
> - 生成したラフ（`mockups/`）にも案件名が入ります。同じ扱いでお願いします
"""


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    readme_path, catalog_path = sys.argv[1], sys.argv[2]
    if not os.path.isfile(readme_path):
        print("README が見つかりません: %s" % readme_path, file=sys.stderr)
        return 1

    n_total = n_own = n_ref = 0
    try:
        with open(catalog_path, encoding="utf-8") as fh:
            items = json.load(fh).get("entries", [])
        n_total = len(items)
        n_own = sum(1 for it in items if it.get("source") == "own")
        n_ref = sum(1 for it in items if it.get("source") == "ref")
    except Exception as exc:  # カタログが読めなくても README は差し替える（件数だけ伏せる）
        print("catalog.json を読めませんでした（件数は 0 と表記）: %s" % exc, file=sys.stderr)

    body = open(readme_path, encoding="utf-8").read()

    for begin, end, text in (
        (INTRO_BEGIN, INTRO_END, intro_text(n_total, n_own, n_ref)),
        (HANDLING_BEGIN, HANDLING_END, HANDLING_TEXT),
    ):
        if begin not in body or end not in body:
            print("マーカーが見つかりません（README の構造が変わった？）: %s" % begin, file=sys.stderr)
            return 1
        body = re.sub(
            re.escape(begin) + r".*?" + re.escape(end),
            begin + "\n" + text + "\n" + end,
            body,
            flags=re.S,
        )

    open(readme_path, "w", encoding="utf-8").write(body)
    print("README をカタログ同梱版へ差し替えました（%d件 / own %d / ref %d）" % (n_total, n_own, n_ref))
    return 0


if __name__ == "__main__":
    sys.exit(main())
