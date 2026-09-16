# -*- coding: utf-8 -*-
"""PowerPoint(OOXML) 生成ヘルパー。spec.py の定数を EMU / XML へ落とす。"""
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn

import spec as S

EMU = S.MM  # 1mm


def emu(mm):
    return int(round(mm * S.MM))


def _fill(color):
    return f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'


def rpr(st, color, italic=False):
    """run/def run プロパティの属性＋子要素を返す"""
    attrs = f'sz="{st["sz"]}" b="{1 if st["b"] else 0}" i="{1 if italic else 0}" spc="{st["spc"]}" kern="1200" dirty="0"'
    kids = _fill(color) + '<a:latin typeface="+mn-lt"/><a:ea typeface="+mn-ea"/><a:cs typeface="+mn-cs"/>'
    return attrs, kids


def lst_style(st, color, align="l", bullet=False, indent_mm=0.0):
    """プレースホルダーの既定書式 <a:lstStyle>"""
    a, k = rpr(st, color)
    if bullet:
        mar = f'marL="{emu(4.5)}" indent="{-emu(4.5)}"'
        bu = ('<a:buSzPct val="80000"/>'
              f'<a:buFont typeface="Arial" pitchFamily="34" charset="0"/><a:buChar char="&#8226;"/>')
    else:
        mar = f'marL="{emu(indent_mm)}" indent="0"'
        bu = '<a:buNone/>'
    return (
        '<a:lstStyle>'
        f'<a:lvl1pPr {mar} algn="{align}">'
        f'<a:lnSpc><a:spcPts val="{st["lnPts"]}"/></a:lnSpc>'
        '<a:spcBef><a:spcPts val="0"/></a:spcBef>'
        f'{bu}<a:defRPr {a}>{k}</a:defRPr>'
        '</a:lvl1pPr>'
        '</a:lstStyle>'
    )


def body_pr(anchor="t", wrap=True, autofit="norm"):
    af = {"norm": "<a:normAutofit/>", "none": "", "shape": "<a:spAutoFit/>"}[autofit]
    return (f'<a:bodyPr wrap="{"square" if wrap else "none"}" lIns="0" tIns="0" rIns="0" bIns="0" '
            f'anchor="{anchor}" anchorCtr="0">{af}</a:bodyPr>')


def para(text, st, color, align="l", bullet=False, space_before_pt=0, indent_mm=0.0, color2=None):
    """明示書式付きの <a:p>。text が空文字なら空段落。"""
    a, k = rpr(st, color)
    if bullet:
        mar = f'marL="{emu(4.5)}" indent="{-emu(4.5)}"'
        bu = ('<a:buSzPct val="80000"/>'
              '<a:buFont typeface="Arial" pitchFamily="34" charset="0"/><a:buChar char="&#8226;"/>')
    else:
        mar = f'marL="{emu(indent_mm)}" indent="0"'
        bu = '<a:buNone/>'
    ppr = (f'<a:pPr {mar} algn="{align}">'
           f'<a:lnSpc><a:spcPts val="{st["lnPts"]}"/></a:lnSpc>'
           f'<a:spcBef><a:spcPts val="{int(round(space_before_pt*100))}"/></a:spcBef>'
           f'{bu}<a:defRPr {a}>{k}</a:defRPr></a:pPr>')
    if text == "":
        return f'<a:p>{ppr}<a:endParaRPr lang="ja-JP" {a}>{k}</a:endParaRPr></a:p>'
    runs = ""
    for seg, seg_color in _segments(text, color, color2):
        aa, kk = rpr(st, seg_color)
        runs += f'<a:r><a:rPr lang="ja-JP" altLang="en-US" {aa}>{kk}</a:rPr><a:t>{_esc(seg)}</a:t></a:r>'
    return f'<a:p>{ppr}{runs}</a:p>'


def _segments(text, color, color2):
    """'通常{強調}通常' の {} 部分を color2 で塗り分ける"""
    if color2 is None or "{" not in text:
        return [(text, color)]
    out, buf, cur = [], "", color
    i = 0
    while i < len(text):
        c = text[i]
        if c == "{":
            if buf:
                out.append((buf, cur))
            buf, cur = "", color2
        elif c == "}":
            if buf:
                out.append((buf, cur))
            buf, cur = "", color
        else:
            buf += c
        i += 1
    if buf:
        out.append((buf, cur))
    return out


def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# --------------------------------------------------------------- shape 生成
def ph_sp(sid, name, ph_type, idx, x, y, w, h, st, color,
          align="l", anchor="t", prompt="", bullet=False, wrap=True, autofit="norm"):
    """レイアウト用プレースホルダー"""
    ph = f'<p:ph type="{ph_type}"' + (f' idx="{idx}"' if idx is not None else "") + ' hasCustomPrompt="1"/>'
    txt = para(prompt, st, color, align=align, bullet=bullet) if prompt else para("", st, color, align=align)
    return parse_xml(
        f'<p:sp {nsdecls("p", "a")}>'
        f'<p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/>'
        f'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>{ph}</p:nvPr></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        f'<p:txBody>{body_pr(anchor, wrap, autofit)}'
        f'{lst_style(st, color, align=align, bullet=bullet)}{txt}</p:txBody>'
        f'</p:sp>'
    )


def rect_sp(sid, name, x, y, w, h, fill=None, line=None, line_w_mm=0.0, radius=None):
    """装飾用の矩形（罫線・帯・枠）"""
    if radius is None:
        geom = '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
    else:
        adj = int(round(radius / min(w, h) * 100000))
        geom = f'<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val {adj}"/></a:avLst></a:prstGeom>'
    f = _fill(fill) if fill else '<a:noFill/>'
    ln = (f'<a:ln w="{emu(line_w_mm)}" cap="flat">{_fill(line)}</a:ln>' if line else '<a:ln><a:noFill/></a:ln>')
    return parse_xml(
        f'<p:sp {nsdecls("p", "a")}>'
        f'<p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
        f'{geom}{f}{ln}</p:spPr>'
        f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>'
        f'</p:sp>'
    )


def text_sp(sid, name, x, y, w, h, paras, anchor="t", wrap=True):
    """明示書式のテキストボックス（paras は para() の出力文字列リスト）"""
    return parse_xml(
        f'<p:sp {nsdecls("p", "a")}>'
        f'<p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
        f'<p:txBody>{body_pr(anchor, wrap, "none")}<a:lstStyle/>{"".join(paras)}</p:txBody>'
        f'</p:sp>'
    )


def sldnum_sp(sid, x, y, w, h, st, color, align="r"):
    """スライド番号フィールド"""
    a, k = rpr(st, color)
    fld = (f'<a:fld id="{{B7C08BE7-1D4E-4C2E-9A31-9E9E3C7A0001}}" type="slidenum">'
           f'<a:rPr lang="ja-JP" {a}>{k}</a:rPr><a:t>2</a:t></a:fld>')
    ppr = (f'<a:pPr algn="{align}"><a:lnSpc><a:spcPts val="{st["lnPts"]}"/></a:lnSpc>'
           f'<a:spcBef><a:spcPts val="0"/></a:spcBef><a:buNone/></a:pPr>')
    return parse_xml(
        f'<p:sp {nsdecls("p", "a")}>'
        f'<p:nvSpPr><p:cNvPr id="{sid}" name="Slide Number Placeholder"/>'
        f'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        f'<p:nvPr><p:ph type="sldNum" sz="quarter" idx="20"/></p:nvPr></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        f'<p:txBody>{body_pr("t")}<a:lstStyle/><a:p>{ppr}{fld}</a:p></p:txBody>'
        f'</p:sp>'
    )


def set_bg(cSld, color):
    """<p:cSld> の背景を設定する。<p:bg> は最大1つなので既存分を必ず除去する。"""
    for old in cSld.findall(qn("p:bg")):
        cSld.remove(old)
    bg = parse_xml(f'<p:bg {nsdecls("p", "a")}><p:bgPr>{_fill(color)}<a:effectLst/></p:bgPr></p:bg>')
    cSld.insert(0, bg)


def clear_shapes(shape_tree):
    for child in list(shape_tree):
        if child.tag not in (qn("p:nvGrpSpPr"), qn("p:grpSpPr")):
            shape_tree.remove(child)
