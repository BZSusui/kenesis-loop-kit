# -*- coding: utf-8 -*-
"""
生成した pptx を読み取って PNG プレビューを出力する（目視検証用）。

  python render_preview.py [pptx] [出力ディレクトリ]

PowerPoint の完全な再現ではなく、版面・余白・文字サイズ・配色の確認が目的。
"""
import os
import sys
import zipfile
from lxml import etree
from PIL import Image, ImageDraw, ImageFont

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
Q = lambda t: "{%s}%s" % (NS[t.split(":")[0]], t.split(":")[1])

EMU_MM = 36000.0
PPMM = float(os.environ.get("PPMM", "6.0"))   # 1mm あたりの描画ピクセル

# 描画用フォント。Noto Sans JP を優先し、無ければ環境にある日本語書体へ退避する。
# 明示指定したい場合は環境変数 FONT_BOLD / FONT_REGULAR にファイルパスを渡す。
_FONT_CANDIDATES = {
    True: [  # Bold
        "~/Library/Fonts/NotoSansJP-Bold.otf",
        "/Library/Fonts/NotoSansJP-Bold.otf",
        "/System/Library/Fonts/Supplemental/NotoSansJP-Bold.otf",
        "C:/Windows/Fonts/NotoSansJP-Bold.otf",
        "C:/Users/*/AppData/Local/Microsoft/Windows/Fonts/NotoSansJP-Bold.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "C:/Windows/Fonts/YuGothB.ttc",
        "C:/Windows/Fonts/meiryob.ttc",
    ],
    False: [  # Regular
        "~/Library/Fonts/NotoSansJP-Regular.otf",
        "/Library/Fonts/NotoSansJP-Regular.otf",
        "/System/Library/Fonts/Supplemental/NotoSansJP-Regular.otf",
        "C:/Windows/Fonts/NotoSansJP-Regular.otf",
        "C:/Users/*/AppData/Local/Microsoft/Windows/Fonts/NotoSansJP-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "C:/Windows/Fonts/YuGothR.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
    ],
}


def _resolve_font(bold):
    import glob
    env = os.environ.get("FONT_BOLD" if bold else "FONT_REGULAR")
    if env:
        if not os.path.exists(env):
            raise SystemExit(f"指定されたフォントが見つかりません: {env}")
        return env
    for pat in _FONT_CANDIDATES[bold]:
        for path in sorted(glob.glob(os.path.expanduser(pat))):
            if os.path.exists(path):
                return path
    raise SystemExit(
        "プレビュー描画用の日本語フォントが見つかりません。\n"
        "  Noto Sans JP を導入するか（https://fonts.google.com/noto/specimen/Noto+Sans+JP）、\n"
        "  環境変数 FONT_REGULAR / FONT_BOLD にフォントファイルのパスを指定してください。\n"
        "  ※ プレビューは目視確認用です。pptx の生成（build_template.py）と\n"
        "     検証（validate.py）はフォント無しでも動作します。")


FONTS = {}
_cache = {}
NO_LINE_START = "。、）」』】〉》”’,.)]}%"


def font(pt, bold):
    if bold not in FONTS:
        FONTS[bold] = _resolve_font(bold)
    px = max(1, int(round(pt * 25.4 / 72.0 * PPMM)))
    key = (px, bold)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(FONTS[bold], px)
    return _cache[key]


def X(emu):   return emu / EMU_MM * PPMM


def rgb(h):   return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------------ 属性抽出
def solid(el):
    if el is None:
        return None
    f = el.find(Q("a:solidFill"))
    if f is None:
        return None
    c = f.find(Q("a:srgbClr"))
    if c is not None:
        return rgb(c.get("val"))
    sc = f.find(Q("a:sysClr"))
    if sc is not None:
        return rgb(sc.get("lastClr", "000000"))
    return None


def xfrm_of(sp):
    x = sp.find(".//" + Q("a:xfrm"))
    if x is None:
        x = sp.find(".//" + Q("p:xfrm"))   # graphicFrame は p:xfrm
    if x is None:
        return None
    off, ext = x.find(Q("a:off")), x.find(Q("a:ext"))
    if off is None or ext is None:
        return None
    return (X(int(off.get("x"))), X(int(off.get("y"))),
            X(int(ext.get("cx"))), X(int(ext.get("cy"))))


def run_props(rPr, inherit):
    st = dict(inherit)
    if rPr is None:
        return st
    if rPr.get("sz"):
        st["sz"] = int(rPr.get("sz")) / 100.0
    if rPr.get("b") is not None:
        st["b"] = rPr.get("b") in ("1", "true")
    if rPr.get("spc"):
        st["spc"] = int(rPr.get("spc")) / 100.0
    c = solid(rPr)
    if c:
        st["color"] = c
    return st


def para_props(pPr, inherit):
    st = dict(inherit)
    if pPr is None:
        return st
    if pPr.get("algn"):
        st["algn"] = pPr.get("algn")
    if pPr.get("marL"):
        st["marL"] = X(int(pPr.get("marL")))
    if pPr.get("indent"):
        st["indent"] = X(int(pPr.get("indent")))
    ln = pPr.find(Q("a:lnSpc"))
    if ln is not None:
        pts = ln.find(Q("a:spcPts"))
        if pts is not None:
            st["line"] = int(pts.get("val")) / 100.0
    sb = pPr.find(Q("a:spcBef"))
    if sb is not None:
        pts = sb.find(Q("a:spcPts"))
        if pts is not None:
            st["before"] = int(pts.get("val")) / 100.0
    st["bullet"] = pPr.find(Q("a:buChar")) is not None
    dr = pPr.find(Q("a:defRPr"))
    if dr is not None:
        st.update({k: v for k, v in run_props(dr, st).items()
                   if k in ("sz", "b", "spc", "color")})
    return st


# ------------------------------------------------------------------ 描画
def text_width(s, f, spc):
    return sum(f.getlength(ch) + spc for ch in s)


def layout_text(txBody, box, lst_default, anchor_default="t"):
    """テキストを折り返して行のリストと必要高さ(px)を返す。描画はしない。

    draw_text() と overflow.py が共有する。折り返しの判断を1箇所に保つため、
    この関数を複製しないこと（判定が静かに乖離すると検査が嘘をつく）。
    """
    bx, by, bw, bh = box
    bodyPr = txBody.find(Q("a:bodyPr"))
    anchor = (bodyPr.get("anchor", anchor_default)
              if bodyPr is not None else anchor_default)

    base = dict(sz=12.0, b=False, spc=0.0, color=(0, 0, 0),
                algn="l", line=None, before=0.0, marL=0.0, indent=0.0, bullet=False)
    base.update(lst_default)

    lines = []   # (segments, para_state, before)
    for p in txBody.findall(Q("a:p")):
        ps = para_props(p.find(Q("a:pPr")), base)
        segs = []
        for r in p.findall(Q("a:r")):
            rs = run_props(r.find(Q("a:rPr")), ps)
            t = r.find(Q("a:t"))
            segs.append((t.text or "", rs))
        for fld in p.findall(Q("a:fld")):
            rs = run_props(fld.find(Q("a:rPr")), ps)
            t = fld.find(Q("a:t"))
            segs.append((t.text or "", rs))
        if not segs:
            lines.append(([], ps, ps["before"], True))
            continue
        # 折り返し
        indent = ps["marL"]
        avail = bw - indent
        cur, cur_w, first = [], 0.0, True
        for text, rs in segs:
            f = font(rs["sz"], rs["b"])
            for ch in text:
                w = f.getlength(ch) + rs["spc"] * PPMM * 25.4 / 72.0 / 25.4 * 25.4 / 72.0 * 0
                w = f.getlength(ch) + rs["spc"] * 25.4 / 72.0 * PPMM
                if ch == "\n" or (cur_w + w > avail and cur):
                    if ch != "\n" and cur and cur[-1][0] and ch in NO_LINE_START:
                        pass
                    lines.append((cur, ps, ps["before"] if first else 0.0, first))
                    first = False
                    cur, cur_w = [], 0.0
                    if ch == "\n":
                        continue
                cur.append((ch, rs))
                cur_w += w
        lines.append((cur, ps, ps["before"] if first else 0.0, first))

    # 総高さ
    total = 0.0
    for segs, ps, before, _f in lines:
        sz = max([rs["sz"] for _, rs in segs], default=ps["sz"])
        lh = (ps["line"] or sz * 1.2)
        total += before * 25.4 / 72.0 * PPMM + lh * 25.4 / 72.0 * PPMM

    return lines, total, anchor


def draw_text(dr, txBody, box, lst_default, anchor_default="t"):
    bx, by, bw, bh = box
    lines, total, anchor = layout_text(txBody, box, lst_default, anchor_default)

    y = by
    if anchor == "ctr":
        y = by + (bh - total) / 2
    elif anchor == "b":
        y = by + bh - total

    for segs, ps, before, is_first in lines:
        sz = max([rs["sz"] for _, rs in segs], default=ps["sz"])
        lh_px = (ps["line"] or sz * 1.2) * 25.4 / 72.0 * PPMM
        y += before * 25.4 / 72.0 * PPMM
        if segs:
            w = sum(font(rs["sz"], rs["b"]).getlength(ch) +
                    rs["spc"] * 25.4 / 72.0 * PPMM for ch, rs in segs)
            indent = ps["marL"]
            x = bx + indent
            if ps["algn"] == "ctr":
                x = bx + (bw - w) / 2
            elif ps["algn"] == "r":
                x = bx + bw - w
            f0 = font(sz, False)
            asc, desc = f0.getmetrics()
            baseline = y + lh_px - (lh_px - (asc + desc)) / 2 - desc
            if ps["bullet"] and is_first and indent:
                fb = font(sz * 0.8, False)
                dr.text((bx + indent - 4.5 * PPMM, baseline), "•",
                        font=fb, fill=segs[0][1]["color"], anchor="ls")
            for ch, rs in segs:
                f = font(rs["sz"], rs["b"])
                dr.text((x, baseline), ch, font=f, fill=rs["color"], anchor="ls")
                x += f.getlength(ch) + rs["spc"] * 25.4 / 72.0 * PPMM
        y += lh_px


def lst_defaults(sp):
    """<a:lstStyle> の lvl1pPr を既定値として返す"""
    out = {}
    lst = sp.find(".//" + Q("a:lstStyle"))
    if lst is None:
        return out
    lvl = lst.find(Q("a:lvl1pPr"))
    if lvl is None:
        return out
    return para_props(lvl, dict(sz=12.0, b=False, spc=0.0, color=(0, 0, 0),
                                algn="l", line=None, before=0.0, marL=0.0,
                                indent=0.0, bullet=False))


def ph_key(sp):
    ph = sp.find(".//" + Q("p:ph"))
    if ph is None:
        return None
    return ph.get("idx", "0")


def draw_shape(dr, sp, inherit_map=None):
    box = xfrm_of(sp)
    src = sp
    if box is None and inherit_map:
        base = inherit_map.get(ph_key(sp))
        if base is not None:
            box = xfrm_of(base)
            src = base
    if box is None:
        return
    x, y, w, h = box
    spPr = sp.find(Q("p:spPr"))
    fill = solid(spPr)
    geom = spPr.find(Q("a:prstGeom")) if spPr is not None else None
    rounded = geom is not None and geom.get("prst") == "roundRect"
    ln = spPr.find(Q("a:ln")) if spPr is not None else None
    line_c = solid(ln) if ln is not None else None
    line_w = X(int(ln.get("w"))) if (ln is not None and ln.get("w")) else 0
    if fill or line_c:
        if rounded:
            dr.rounded_rectangle([x, y, x + w, y + h], radius=min(w, h) * 0.12,
                                 fill=fill, outline=line_c, width=max(1, int(line_w)))
        else:
            dr.rectangle([x, y, x + w, y + h], fill=fill, outline=line_c,
                         width=max(1, int(line_w)) if line_c else 0)
    tx = sp.find(Q("p:txBody"))
    if tx is not None:
        dflt = lst_defaults(src)
        own = lst_defaults(sp)
        dflt.update(own)
        src_bp = src.find(".//" + Q("a:bodyPr"))
        anc = src_bp.get("anchor", "t") if src_bp is not None else "t"
        draw_text(dr, tx, box, dflt, anc)


def draw_table(dr, gf):
    box = xfrm_of(gf)
    tbl = gf.find(".//" + Q("a:tbl"))
    if box is None or tbl is None:
        return
    x0, y0, _, _ = box
    widths = [X(int(g.get("w"))) for g in tbl.findall(Q("a:tblGrid") + "/" + Q("a:gridCol"))]
    y = y0
    for tr in tbl.findall(Q("a:tr")):
        rh = X(int(tr.get("h")))
        x = x0
        for i, tc in enumerate(tr.findall(Q("a:tc"))):
            w = widths[i]
            tcPr = tc.find(Q("a:tcPr"))
            f = solid(tcPr)
            if f:
                dr.rectangle([x, y, x + w, y + rh], fill=f)
            if tcPr is not None:
                for tag, ypos in ((Q("a:lnT"), y), (Q("a:lnB"), y + rh)):
                    el = tcPr.find(tag)
                    if el is not None:
                        c = solid(el)
                        lw = max(1, int(X(int(el.get("w", "0")))))
                        if c:
                            dr.rectangle([x, ypos - lw / 2, x + w, ypos + lw / 2], fill=c)
                mL = X(int(tcPr.get("marL", "0")))
                mR = X(int(tcPr.get("marR", "0")))
                mT = X(int(tcPr.get("marT", "0")))
                anchor = tcPr.get("anchor", "t")
            else:
                mL = mR = mT = 0
                anchor = "t"
            tx = tc.find(Q("a:txBody"))
            if tx is not None:
                bodyPr = tx.find(Q("a:bodyPr"))
                if bodyPr is None:
                    tx.insert(0, etree.SubElement(tx, Q("a:bodyPr")))
                if bodyPr is not None:
                    bodyPr.set("anchor", anchor)
                draw_text(dr, tx, (x + mL, y + mT, w - mL - mR, rh - mT * 2), {})
            x += w
        y += rh


def bg_color(cSld):
    bg = cSld.find(Q("p:bg"))
    if bg is None:
        return None
    return solid(bg.find(Q("p:bgPr")))


def render(pptx_path, out_dir, pdf_path=None):
    os.makedirs(out_dir, exist_ok=True)
    z = zipfile.ZipFile(pptx_path)
    pres = etree.fromstring(z.read("ppt/presentation.xml"))
    sz = pres.find(Q("p:sldSz"))
    W, H = X(int(sz.get("cx"))), X(int(sz.get("cy")))

    prels = etree.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
    rid2t = {r.get("Id"): r.get("Target") for r in prels}
    slide_targets = []
    for sid in pres.find(Q("p:sldIdLst")):
        t = rid2t[sid.get("{%s}id" % NS["r"])]
        slide_targets.append("ppt/" + t.replace("../", ""))

    outs, pages = [], []
    for n, sp_path in enumerate(slide_targets, 1):
        slide = etree.fromstring(z.read(sp_path))
        rels = etree.fromstring(z.read(sp_path.replace("slides/", "slides/_rels/") + ".rels"))
        lay = [r.get("Target") for r in rels
               if r.get("Type").endswith("slideLayout")][0]
        lay_path = "ppt/" + lay.replace("../", "")
        layout = etree.fromstring(z.read(lay_path))

        cSld_s = slide.find(Q("p:cSld"))
        cSld_l = layout.find(Q("p:cSld"))
        bg = bg_color(cSld_s) or bg_color(cSld_l) or (255, 255, 255)

        img = Image.new("RGB", (int(W), int(H)), bg)
        dr = ImageDraw.Draw(img)

        # レイアウトの ph を継承元として索引化
        inherit = {}
        for sp in cSld_l.find(Q("p:spTree")).findall(Q("p:sp")):
            k = ph_key(sp)
            if k is not None:
                inherit[k] = sp
        # レイアウトの非プレースホルダー図形
        for sp in cSld_l.find(Q("p:spTree")).findall(Q("p:sp")):
            if sp.find(".//" + Q("p:ph")) is None:
                draw_shape(dr, sp)
        # スライド図形
        tree = cSld_s.find(Q("p:spTree"))
        for el in tree:
            if el.tag == Q("p:sp"):
                draw_shape(dr, el, inherit)
            elif el.tag == Q("p:graphicFrame"):
                draw_table(dr, el)

        out = os.path.join(out_dir, f"slide{n:02d}.png")
        img.save(out)
        outs.append(out)
        pages.append(img)
        print("rendered", out)
    # ガイド線の重ね合わせ確認画像（標準1カラムのページを使用）
    if len(pages) >= 4:
        gl = etree.fromstring(z.read("ppt/viewProps.xml")).find(".//" + Q("p:guideLst"))
        if gl is not None:
            img = pages[3].copy()
            dr = ImageDraw.Draw(img)
            for g in gl:
                o = g.get("orient", "horz")
                mm = int(g.get("pos", "0")) * 25.4 / 72.0 / 8.0
                v = mm * PPMM
                if o == "vert":
                    dr.line([(v, 0), (v, img.height)], fill=(230, 60, 60), width=2)
                else:
                    dr.line([(0, v), (img.width, v)], fill=(230, 60, 60), width=2)
            out = os.path.join(out_dir, "guides.png")
            img.save(out)
            print("rendered", out, "(ガイド線を赤で重ねた確認用)")

    if pdf_path and pages:
        dpi = PPMM * 25.4
        pages[0].save(pdf_path, "PDF", save_all=True, append_images=pages[1:],
                      resolution=dpi)
        print("rendered", pdf_path, f"({dpi:.0f} dpi)")
    return outs


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, "dist", "DADS_A4_Portrait_Template.pptx")
    o = sys.argv[2] if len(sys.argv) > 2 else os.path.join(base, "preview")
    render(p, o, os.path.join(o, "preview.pdf"))
