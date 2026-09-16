# -*- coding: utf-8 -*-
"""
生成した pptx の構造検証。

  python validate.py [pptx]

PowerPoint が「修復」を要求する典型的な不整合を機械的に検出する。
ECMA-376 のスキーマ全体を検証するものではなく、本ビルダーが触る範囲を対象とする。
"""
import os
import posixpath
import sys
import zipfile
import collections
from lxml import etree

NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "ct": "http://schemas.openxmlformats.org/package/2006/content-types"}
Q = lambda t: "{%s}%s" % (NS[t.split(":")[0]], t.split(":")[1])
SHORT = {v: k for k, v in NS.items()}


def tag(e):
    u = e.tag
    for uri, pfx in SHORT.items():
        if u.startswith("{%s}" % uri):
            return pfx + ":" + u[len(uri) + 2:]
    return u


# 親要素 -> 子要素のスキーマ順（出現しうるものだけ列挙）。
# 同じ位置の選択肢はタプルでまとめる。
ORDER = {
    "p:cSld":      ["p:bg", "p:spTree", "p:custDataLst", "p:controls", "p:extLst"],
    "p:sldMaster": ["p:cSld", "p:clrMap", "p:sldLayoutIdLst", "p:transition",
                    "p:timing", "p:hf", "p:txStyles", "p:extLst"],
    "p:sldLayout": ["p:cSld", "p:clrMapOvr", "p:transition", "p:timing", "p:hf", "p:extLst"],
    "p:sld":       ["p:cSld", "p:clrMapOvr", "p:transition", "p:timing", "p:extLst"],
    "p:sp":        ["p:nvSpPr", "p:spPr", "p:style", "p:txBody", "p:extLst"],
    "p:nvSpPr":    ["p:cNvPr", "p:cNvSpPr", "p:nvPr"],
    "p:spPr":      ["a:xfrm", "a:custGeom", "a:prstGeom", "a:noFill", "a:solidFill",
                    "a:gradFill", "a:blipFill", "a:pattFill", "a:grpFill", "a:ln",
                    "a:effectLst", "a:effectDag", "a:scene3d", "a:sp3d", "a:extLst"],
    "p:txBody":    ["a:bodyPr", "a:lstStyle", "a:p"],
    "a:txBody":    ["a:bodyPr", "a:lstStyle", "a:p"],
    "a:bodyPr":    ["a:prstTxWarp", "a:noAutofit", "a:normAutofit", "a:spAutoFit",
                    "a:scene3d", "a:sp3d", "a:flatTx", "a:extLst"],
    "a:p":         ["a:pPr", "a:r", "a:br", "a:fld", "a:endParaRPr"],
    "a:pPr":       ["a:lnSpc", "a:spcBef", "a:spcAft", "a:buClrTx", "a:buClr",
                    "a:buSzTx", "a:buSzPct", "a:buSzPts", "a:buFontTx", "a:buFont",
                    "a:buNone", "a:buAutoNum", "a:buChar", "a:buBlip",
                    "a:tabLst", "a:defRPr", "a:extLst"],
    "a:rPr":       ["a:ln", "a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
                    "a:pattFill", "a:grpFill", "a:effectLst", "a:effectDag",
                    "a:highlight", "a:uLnTx", "a:uLn", "a:uFillTx", "a:uFill",
                    "a:latin", "a:ea", "a:cs", "a:sym", "a:hlinkClick",
                    "a:hlinkMouseOver", "a:rtl", "a:extLst"],
    "a:tcPr":      ["a:lnL", "a:lnR", "a:lnT", "a:lnB", "a:lnTlToBr", "a:lnBlToTr",
                    "a:cell3D", "a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
                    "a:pattFill", "a:grpFill", "a:headers", "a:extLst"],
    "a:tc":        ["a:txBody", "a:tcPr", "a:extLst"],
    "a:tbl":       ["a:tblPr", "a:tblGrid", "a:tr"],
    "p:bgPr":      ["a:noFill", "a:solidFill", "a:gradFill", "a:blipFill", "a:pattFill",
                    "a:grpFill", "a:effectLst", "a:effectDag", "a:extLst"],
}
ORDER["a:lvl1pPr"] = ORDER["a:pPr"]
for i in range(2, 10):
    ORDER["a:lvl%dpPr" % i] = ORDER["a:pPr"]
ORDER["a:defRPr"] = ORDER["a:rPr"]
ORDER["a:endParaRPr"] = ORDER["a:rPr"]

# 同じ親の中で1回しか現れてはいけない子
SINGLE = {
    "p:cSld": {"p:bg", "p:spTree"},
    "p:sldMaster": {"p:cSld", "p:clrMap", "p:sldLayoutIdLst", "p:txStyles"},
    "p:sldLayout": {"p:cSld", "p:clrMapOvr"},
    "p:sld": {"p:cSld", "p:clrMapOvr"},
    "p:sp": {"p:nvSpPr", "p:spPr", "p:txBody"},
    "p:txBody": {"a:bodyPr", "a:lstStyle"},
    "a:txBody": {"a:bodyPr", "a:lstStyle"},
    "a:p": {"a:pPr", "a:endParaRPr"},
    "a:tc": {"a:txBody", "a:tcPr"},
    "a:tbl": {"a:tblPr", "a:tblGrid"},
    "p:bgPr": {"a:effectLst"},
}


def check_tree(root, part, errs):
    for el in root.iter():
        t = tag(el)
        kids = [tag(c) for c in el if isinstance(c.tag, str)]
        if t in SINGLE:
            for k, c in collections.Counter(kids).items():
                if k in SINGLE[t] and c > 1:
                    errs.append(f"{part}: <{t}> に <{k}> が {c} 個（1個まで）")
        if t in ORDER:
            seq = ORDER[t]
            pos = -1
            for k in kids:
                if k not in seq:
                    continue
                i = seq.index(k)
                if i < pos:
                    errs.append(f"{part}: <{t}> の子要素の順序が不正（<{k}> が後ろ過ぎる位置に）")
                    break
                pos = i


def main(path):
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    errs, warns = [], []

    # 1. 整形式
    trees = {}
    for n in sorted(names):
        if n.endswith((".xml", ".rels")):
            try:
                trees[n] = etree.fromstring(z.read(n))
            except Exception as e:
                errs.append(f"{n}: XMLが不正 — {e}")

    # 2. パッケージ整合
    ct = trees.get("[Content_Types].xml")
    if ct is not None:
        ov = {e.get("PartName").lstrip("/") for e in ct.findall(Q("ct:Override"))}
        df = {e.get("Extension") for e in ct.findall(Q("ct:Default"))}
        for miss in sorted(ov - names):
            errs.append(f"[Content_Types].xml: 存在しないパートを宣言 — {miss}")
        for n in sorted(names - {"[Content_Types].xml"}):
            if n not in ov and n.rsplit(".", 1)[-1].lower() not in df:
                errs.append(f"[Content_Types].xml: 未宣言のパート — {n}")
    for n, root in trees.items():
        if not n.endswith(".rels"):
            continue
        base = n.rsplit("/_rels/", 1)[0] if "/_rels/" in n else ""
        for r in root:
            if r.get("TargetMode") == "External":
                continue
            p = posixpath.normpath(posixpath.join(base, r.get("Target")))
            if p not in names:
                errs.append(f"{n}: 参照先が存在しない — {r.get('Target')}")

    # 3. 要素の重複・順序
    for n, root in trees.items():
        if n.startswith(("ppt/slides/slide", "ppt/slideLayouts/slideL",
                         "ppt/slideMasters/slideM")) and n.endswith(".xml"):
            check_tree(root, n.split("/")[-1], errs)

    # 4. 図形ID・プレースホルダー
    def phs(part):
        root = trees[part]
        return [(p.get("type", "body"), p.get("idx", "0")) for p in root.iter(Q("p:ph"))]

    for n, root in trees.items():
        if not (n.startswith(("ppt/slides/slide", "ppt/slideLayouts/slideL",
                              "ppt/slideMasters/slideM")) and n.endswith(".xml")):
            continue
        short = n.split("/")[-1]
        ids = [e.get("id") for e in root.iter(Q("p:cNvPr"))]
        for k, c in collections.Counter(ids).items():
            if c > 1:
                errs.append(f"{short}: cNvPr id={k} が {c} 個（図形IDは一意）")
        for k, c in collections.Counter([i for _, i in phs(n)]).items():
            if c > 1:
                errs.append(f"{short}: ph idx={k} が {c} 個（プレースホルダーidxは一意）")

    for n in sorted(names):
        if not (n.startswith("ppt/slides/slide") and n.endswith(".xml")):
            continue
        rel = f"ppt/slides/_rels/{n.split('/')[-1]}.rels"
        lay = [r.get("Target") for r in trees[rel]
               if r.get("Type").endswith("slideLayout")]
        if len(lay) != 1:
            errs.append(f"{n}: slideLayout リレーションが {len(lay)} 個（1個であること）")
            continue
        lp = "ppt/" + lay[0].replace("../", "")
        lidx = {i for _, i in phs(lp)}
        for t, i in phs(n):
            if i not in lidx:
                errs.append(f"{n.split('/')[-1]}: ph({t}, idx={i}) がレイアウト"
                            f"{lp.split('/')[-1]}に存在しない")

    # 5. スライドサイズ
    pres = trees.get("ppt/presentation.xml")
    if pres is not None:
        sz = pres.find(Q("p:sldSz"))
        cx, cy = int(sz.get("cx")), int(sz.get("cy"))
        for nm, v in (("cx", cx), ("cy", cy)):
            if not (914400 <= v <= 51206400):
                errs.append(f"presentation.xml: sldSz {nm}={v} が有効範囲外")
        if sz.get("type") not in (None, "custom") and (cx, cy) != (9144000, 6858000):
            warns.append(f'presentation.xml: sldSz type="{sz.get("type")}" が実寸と不一致')
        print(f"スライドサイズ: {cx} × {cy} EMU = {cx/36000:.1f} × {cy/36000:.1f} mm "
              f'(type={sz.get("type")})')

    # 6. ガイド線（pos は 1/8 pt 単位）
    vp = trees.get("ppt/viewProps.xml")
    if vp is not None and pres is not None:
        W, H = cx / 36000.0, cy / 36000.0
        gl = vp.find(".//" + Q("p:guideLst"))
        if gl is None:
            warns.append("viewProps.xml: guideLst がありません")
        else:
            print("ガイド線:")
            for g in gl:
                o = g.get("orient", "horz")
                pos = int(g.get("pos", "0"))
                mm = pos * 25.4 / 72.0 / 8.0
                limit = W if o == "vert" else H
                ok = 0 <= mm <= limit
                print(f"  {o:<4} pos={pos:<5} = {mm:7.3f} mm" + ("" if ok else "  <<< 用紙外"))
                if o not in ("horz", "vert"):
                    errs.append(f"viewProps.xml: guide orient=\"{o}\" が不正")
                if not ok:
                    errs.append(f"viewProps.xml: guide {o} pos={pos} ({mm:.1f}mm) が用紙範囲外")

    print(f"検査パート数: {len(trees)}")
    if warns:
        print("\n[警告]")
        for w in warns:
            print("  -", w)
    if errs:
        print(f"\n[エラー] {len(errs)} 件")
        for e in errs:
            print("  -", e)
        return 1
    print("\n[OK] 検出された不整合はありません。")
    return 0


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    f = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        base, "dist", "DADS_A4_Portrait_Template.pptx")
    sys.exit(main(f))
