# -*- coding: utf-8 -*-
"""テンプレート各ページのテキストが枠に収まっているかを検査する（DADS-003）。

    python build/overflow.py dist/DADS_B5_Portrait_Template.pptx [...]

判定は2つ。1件でもあれば終了コード 1 を返す。

  1. **フッター越え** — 本文領域の図形がフッター罫（FRULE_Y）を越えた
  2. **重なり** — ある図形のテキストが、その下にある別の図形の上端を越えた

1 は DADS-002 で、2 は DADS-005 で実際に起きた不具合と同じ形である。
2 は「テキストが枠を超えて下の要素に重なる」ケースで、1 だけでは検出できない
（ページ途中での重なりはフッター罫に届かない）。

対象は次の2つで絞る。

  - **フッター罫を持つレイアウトのページだけ**を見る。表紙・章扉・裏表紙は罫が無く、
    ページ下部まで要素を置く設計なので、判定の前提が当てはまらない。
  - **上端がフッター罫より上にある図形だけ**を見る。フッターの注記欄とページ番号は
    もともと罫より下に置かれており、外さないと全ページが誤検知になる。

**「テキストの必要高さが枠高を超えること」自体は判定しない。** PowerPoint のテキストボックスは
枠を超えて描画するのが通常で、本テンプレートにも意図してそう作った箇所がある
（例: 表紙の章名欄は枠高5.3mmに対し行高7.2mm。下寄せなので見た目は正しい）。
これを一律にあふれと呼ぶと誤検知だらけになり、検査が信用されなくなる。

必要高さは render_preview.layout_text() で求める。折り返しの判断をそこに集約しているため、
この検査とプレビュー描画は必ず同じ結果になる（複製すると静かに乖離して検査が嘘をつく）。

**この検査は PIL のフォントメトリクスによる近似であり、PowerPoint 実機での折り返しと
厳密に一致するわけではない。** 明らかなあふれを捕まえるためのもので、実機確認の代わりにはならない。

日本語フォントが無い環境では検査できないため、その旨を出力してスキップする（終了コード 0）。
pptx の生成と validate.py はフォント無しでも動く、という性質を壊さないため。
"""
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lxml import etree  # noqa: E402

import render_preview as R  # noqa: E402
import spec as S  # noqa: E402

# PIL と PowerPoint のフォントメトリクス差を吸収する緩衝。
# 0.5mm は本文1行(約4.2mm)の1/8 で、1行増えたぶんの高さ(約7mm)より十分小さい。
# これ以上緩めると1行のあふれを見逃す。
TOLERANCE_MM = 0.5


def _profile_of(pptx_path):
    """pptx の用紙サイズから、どのプロファイルの出力かを特定する。"""
    with zipfile.ZipFile(pptx_path) as z:
        pres = etree.fromstring(z.read("ppt/presentation.xml"))
    sz = pres.find(R.Q("p:sldSz"))
    w, h = int(sz.get("cx")), int(sz.get("cy"))
    for name in S.PROFILES:
        p = S.load(name)
        if (round(p.PAGE_W_MM * S.MM) == w and round(p.PAGE_H_MM * S.MM) == h):
            return p
    return None


def _bottom_of(by, bh, total, anchor):
    """アンカーを考慮したテキストの下端(px)。"""
    if anchor == "b":
        return by + bh
    if anchor == "ctr":
        return by + (bh + total) / 2
    return by + total


def _shapes_of(z, target):
    """スライド上の図形を (名前, 枠, テキストの必要高さ, テキスト有無) で返す。"""
    root = etree.fromstring(z.read(target))
    rels = etree.fromstring(z.read(os.path.dirname(target) + "/_rels/"
                                   + os.path.basename(target) + ".rels"))
    lt = next((r.get("Target") for r in rels
               if r.get("Type", "").endswith("/slideLayout")), None)
    inherit = {}
    if lt:
        lay = etree.fromstring(z.read("ppt/" + lt.replace("../", "")))
        for sp in lay.iter(R.Q("p:sp")):
            k = R.ph_key(sp)
            if k is not None:
                inherit[k] = sp
        has_rule = any(e.get("name") == "フッター罫" for e in lay.iter(R.Q("p:cNvPr")))
    else:
        has_rule = False
    out = []
    for sp in root.iter(R.Q("p:sp")):
        tx = sp.find(R.Q("p:txBody"))
        box, src = R.xfrm_of(sp), sp
        if box is None:
            k = R.ph_key(sp)
            if k is None or k not in inherit:
                continue
            src = inherit[k]
            box = R.xfrm_of(src)
            if box is None:
                continue
        el = sp.find(".//" + R.Q("p:cNvPr"))
        name = el.get("name") if el is not None else "?"
        has_text = tx is not None and any((t.text or "").strip()
                                          for t in tx.iter(R.Q("a:t")))
        bottom = box[1]
        if has_text:
            _, total, anchor = R.layout_text(tx, box, R.lst_defaults(src))
            bottom = _bottom_of(box[1], box[3], total, anchor)
        out.append((name, box, bottom, has_text))
    return out, has_rule


def check_overlap(pptx_path):
    """下にある図形へ重なっているものを返す。[(slide番号, 上の図形, 下の図形, 重なりmm)]"""
    z = zipfile.ZipFile(pptx_path)
    R.THEME_FONTS.update(R.read_theme_fonts(z))
    R.FONTS.clear(); R._cache.clear()
    tol = TOLERANCE_MM * R.PPMM
    found = []
    for i, target in enumerate(_slide_targets(z), 1):
        shp, _ = _shapes_of(z, target)
        for name, box, bottom, has_text in shp:
            if not has_text:
                continue
            bx, by, bw, bh = box
            for n2, b2, _, _ in shp:
                if n2 == name:
                    continue
                x2, y2, w2, h2 = b2
                if x2 + w2 <= bx + 1 or bx + bw <= x2 + 1:
                    continue        # 横方向に重なりがない
                if y2 < by + 1:
                    continue        # 相手が上にある
                if bottom > y2 + tol:
                    found.append((i, name, n2, (bottom - y2) / R.PPMM))
    return found


def _slide_targets(z):
    pres = etree.fromstring(z.read("ppt/presentation.xml"))
    prels = etree.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
    rid2t = {r.get("Id"): r.get("Target") for r in prels}
    return ["ppt/" + rid2t[s.get("{%s}id" % R.NS["r"])].replace("../", "")
            for s in pres.find(R.Q("p:sldIdLst"))]


def check(pptx_path):
    """フッター罫を越えた図形の一覧を返す。[(slide番号, 図形名, 下端mm, 罫のmm)]"""
    prof = _profile_of(pptx_path)
    frule_px = R.X(round(prof.FRULE_Y * S.MM)) if prof else None
    tol_px = TOLERANCE_MM * R.PPMM

    z = zipfile.ZipFile(pptx_path)
    pres = etree.fromstring(z.read("ppt/presentation.xml"))
    prels = etree.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
    rid2t = {r.get("Id"): r.get("Target") for r in prels}
    slides = ["ppt/" + rid2t[s.get("{%s}id" % R.NS["r"])].replace("../", "")
              for s in pres.find(R.Q("p:sldIdLst"))]

    found = []
    for i, target in enumerate(slides, 1):
        root = etree.fromstring(z.read(target))
        # レイアウトのプレースホルダから座標・書式を継承する（render_preview と同じ解決）
        rels = etree.fromstring(z.read(os.path.dirname(target) + "/_rels/"
                                       + os.path.basename(target) + ".rels"))
        layout_t = next((r.get("Target") for r in rels
                         if r.get("Type", "").endswith("/slideLayout")), None)
        inherit = {}
        has_rule = False
        if layout_t:
            lay = etree.fromstring(z.read("ppt/" + layout_t.replace("../", "")))
            for sp in lay.iter(R.Q("p:sp")):
                k = R.ph_key(sp)
                if k is not None:
                    inherit[k] = sp
            has_rule = any(e.get("name") == "フッター罫"
                           for e in lay.iter(R.Q("p:cNvPr")))
        if not has_rule:
            continue      # 表紙・章扉・裏表紙。フッター罫が無いページは判定しない

        for sp in root.iter(R.Q("p:sp")):
            tx = sp.find(R.Q("p:txBody"))
            if tx is None:
                continue
            box = R.xfrm_of(sp)
            src = sp
            if box is None:
                k = R.ph_key(sp)
                if k is None or k not in inherit:
                    continue
                src = inherit[k]
                box = R.xfrm_of(src)
                if box is None:
                    continue
            # 文字が1つも無い枠（プロンプトだけの空プレースホルダ）は対象外
            if not any((t.text or "").strip() for t in tx.iter(R.Q("a:t"))):
                continue
            bx, by, bw, bh = box
            if frule_px is None or by >= frule_px:
                continue          # フッター領域の要素（注記欄・ページ番号）は対象外
            _, total, anchor = R.layout_text(tx, box, R.lst_defaults(src))
            bottom = _bottom_of(by, bh, total, anchor)
            if bottom > frule_px + tol_px:
                name = (sp.find(".//" + R.Q("p:cNvPr")).get("name")
                        if sp.find(".//" + R.Q("p:cNvPr")) is not None else "?")
                found.append((i, name, bottom / R.PPMM, frule_px / R.PPMM))
    return found


def main(paths):
    if not paths:
        print("使い方: python build/overflow.py <pptx> [<pptx> ...]")
        return 1
    # 検査対象の書体が揃っているか先に確かめる。
    # 書体はテンプレートごとに違うため、pptx のテーマを読んでから判定する。
    try:
        for p0 in paths:
            if os.path.exists(p0):
                with zipfile.ZipFile(p0) as z0:
                    R.THEME_FONTS.update(R.read_theme_fonts(z0))
                R.FONTS.clear(); R._cache.clear()
                R.font(12.0, False)          # 和文
                R.font(12.0, False, latin=True)   # 欧文
    except SystemExit as e:
        print("[スキップ] あふれ検査を実行できません。")
        for line in str(e).split("\n"):
            print("  " + line)
        return 0

    ng = 0
    for p in paths:
        if not os.path.exists(p):
            print(f"[エラー] ファイルがありません: {p}")
            return 1
        label = os.path.basename(p)
        found = check(p)
        laps = check_overlap(p)
        if not found and not laps:
            print(f"[OK] {label}: フッター越え・重なりともにありません。")
            continue
        ng += len(found) + len(laps)
        print(f"[NG] {label}: フッター越え {len(found)} 件 / 重なり {len(laps)} 件")
        for n, name, bottom, limit in found:
            print(f"  slide{n:02d} 「{name}」: 下端 {bottom:.1f}mm > フッター罫 {limit:.1f}mm")
        for n, a, b, d in laps:
            print(f"  slide{n:02d} 「{a}」が「{b}」に {d:.1f}mm 重なっています")
    if ng:
        print()
        print("サンプル本文の分量か、枠の大きさを見直してください。")
        print("判型ごとに文言を変える場合は build_template.py の S.PROFILE 分岐を使います。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
