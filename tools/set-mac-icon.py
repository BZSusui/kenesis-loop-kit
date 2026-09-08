#!/usr/bin/env python3
"""macOS のファイルにカスタムアイコンを付ける（KLK-106）。

    python3 tools/set-mac-icon.py <icns または svg/png> <対象ファイル>

★なぜ自前で書くのか
  - `Rez` は .rsrc 形式を期待するので、生の .icns をそのまま追記できない（実際に失敗した）。
  - Finder/AppleScript 経由は GUI に依存し、ヘッドレスでは動かない。
  → **リソースフォークを直接組み立てる**。仕様は固定なので決定論で書ける。

仕組み（macOS のカスタムアイコン）:
  ① ファイルのリソースフォーク（`<path>/..namedfork/rsrc`）へ
     タイプ `icns`・ID -16455 のリソースを1つ書く
  ② FinderInfo の Finder flags に kHasCustomIcon(0x0400) を立てる（SetFile -a C）

★ZIP を通すときの注意（実測で確認済み）
  リソースフォークは **`ditto -c -k --sequesterRsrc`（＝Finder の「圧縮」と同じ）**で
  作った zip なら残る。展開も Finder か `ditto -x -k` を使うこと。
  `zip -r` / `unzip` の組み合わせでは**消える**。
"""
import os
import struct
import subprocess
import sys

CUSTOM_ICON_RESOURCE_ID = -16455        # kCustomIconResource
RESOURCE_TYPE = b"icns"
HEADER_LEN = 256


def build_resource_fork(icns_bytes):
    """icns を1つだけ含むリソースフォークのバイト列を組み立てる（純関数）。"""
    # --- データ部: 4バイト長 + 本体
    data = struct.pack(">I", len(icns_bytes)) + icns_bytes
    data_off = HEADER_LEN
    map_off = data_off + len(data)

    # --- マップ部
    type_list_off = 28                   # マップ先頭からの相対
    ref_list = struct.pack(
        ">hhBBH I",
        CUSTOM_ICON_RESOURCE_ID,         # リソースID
        -1,                              # 名前なし
        0,                               # 属性
        0, 0,                            # データ開始オフセット（3バイト）→ 上位1+下位2
        0,                               # ハンドル（未使用）
    )
    # 3バイトのオフセットを正しく詰め直す（データ部の先頭＝0）
    ref_list = (struct.pack(">h", CUSTOM_ICON_RESOURCE_ID)
                + struct.pack(">h", -1)
                + bytes([0])                       # 属性
                + (0).to_bytes(3, "big")           # データ開始オフセット
                + (0).to_bytes(4, "big"))          # ハンドル
    assert len(ref_list) == 12, len(ref_list)

    type_list = struct.pack(">H", 0)                       # 型の数 - 1
    type_list += RESOURCE_TYPE + struct.pack(">HH", 0, 10) # 型 / 個数-1 / 参照リストへの相対
    name_list_off = type_list_off + len(type_list)

    rmap = bytes(16)                                        # ヘッダの写し（0で可）
    rmap += (0).to_bytes(4, "big")                          # 次マップ
    rmap += (0).to_bytes(2, "big")                          # ファイル参照
    rmap += (0).to_bytes(2, "big")                          # 属性
    rmap += struct.pack(">H", type_list_off)
    rmap += struct.pack(">H", name_list_off)
    rmap += type_list + ref_list

    header = struct.pack(">IIII", data_off, map_off, len(data), len(rmap))
    header += bytes(HEADER_LEN - len(header))
    return header + data + rmap


def png_to_icns(src_png, out_icns, workdir):
    """PNG から .icns を作る（sips + iconutil・macOS 標準）。"""
    iconset = os.path.join(workdir, "klk.iconset")
    os.makedirs(iconset, exist_ok=True)
    # iconutil が要求する名前で各サイズを書き出す
    for size in (16, 32, 128, 256, 512):
        for scale, suffix in ((1, ""), (2, "@2x")):
            px = size * scale
            name = "icon_%dx%d%s.png" % (size, size, suffix)
            subprocess.run(["sips", "-z", str(px), str(px), src_png,
                            "--out", os.path.join(iconset, name)],
                           capture_output=True, check=False)
    r = subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out_icns],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("iconutil に失敗: " + r.stderr.strip())
    return out_icns


def svg_to_png(src_svg, out_png, workdir):
    """SVG を PNG にする（qlmanage・macOS 標準）。"""
    subprocess.run(["qlmanage", "-t", "-s", "1024", "-o", workdir, src_svg],
                   capture_output=True, check=False)
    made = os.path.join(workdir, os.path.basename(src_svg) + ".png")
    if not os.path.isfile(made):
        raise RuntimeError("qlmanage で SVG を変換できませんでした: " + src_svg)
    os.replace(made, out_png)
    return out_png


def apply_icon(icns_path, target):
    """リソースフォークへ書き、カスタムアイコンのフラグを立てる。"""
    with open(icns_path, "rb") as fh:
        icns = fh.read()
    fork = build_resource_fork(icns)
    with open(os.path.join(target, "..namedfork", "rsrc"), "wb") as fh:
        fh.write(fork)
    r = subprocess.run(["SetFile", "-a", "C", target], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("SetFile に失敗: " + r.stderr.strip())
    return len(fork)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, target = argv[1], argv[2]
    if not os.path.isfile(target):
        print("[NG] 対象が見つかりません: %s" % target, file=sys.stderr)
        return 1
    import tempfile
    with tempfile.TemporaryDirectory() as wd:
        icns = src
        if src.lower().endswith(".svg"):
            icns = png_to_icns(svg_to_png(src, os.path.join(wd, "s.png"), wd),
                               os.path.join(wd, "s.icns"), wd)
        elif src.lower().endswith(".png"):
            icns = png_to_icns(src, os.path.join(wd, "s.icns"), wd)
        n = apply_icon(icns, target)
        print("[OK] %s にアイコンを設定しました（リソースフォーク %d bytes）" % (target, n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
