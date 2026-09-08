#!/usr/bin/env python3
"""配布用にカタログ画像を軽くする（KLK-110）。**元画像は触らない。**

    python3 tools/shrink-catalog-images.py <出力先ディレクトリ>
    python3 tools/shrink-catalog-images.py <出力先> --src catalog/img --width 1600 --quality 82

★なぜ要るか
  カタログ画像は 167枚で 773MB あり、同梱するとパッケージが約775MBになる。
  メール添付は不可、共有フォルダ経由が前提になる。

★なぜ「長辺」ではなく「横幅」基準か（実測で判明・KLK-110）
  実績画像は**サイトのフルページ・スクリーンショット**で、167枚のうち118枚が
  「縦が横の3倍以上」（最大 17.2倍・952x16383）。
  長辺で揃えると横幅が 93〜194px まで潰れ、**実績が読めなくなる**。
  横幅を基準にすればアスペクト比は保たれ、縦は自然に長いまま残る。

★なぜ縮小だけでは足りないか（実測で判明）
  容量の 94% は PNG（140枚728MB・1枚平均5.2MB）。しかも元から横幅1600px以下が多く、
  **横幅を縮めても標本10枚でほぼ減らなかった**。効くのは PNG→JPEG の変換。
  両方あわせて 773MB → 約216MB（72%減）。

★守ること
  - **拡大しない。** `sips -Z` は小さい画像を引き伸ばす（1253x1589 → 1261x1600）。
    画質が落ちるだけで無意味なので、横幅が上限以下ならサイズは触らない。
  - **ファイル名を変えない。** catalog.json が名前で参照している。
    PNG を JPEG の中身にしても**拡張子は .png のまま**にする
    （ブラウザは中身で判断するので表示できる。名前を変えると参照が切れる）。
  - macOS 以外・sips が無い環境では**そのままコピー**する（fail-soft）。
    配布物が大きくなるだけで、壊れはしない。
"""
import os
import re
import shutil
import subprocess
import sys

DEFAULT_WIDTH = 1600
DEFAULT_QUALITY = 82
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


# ---------------------------------------------------------------------------
# 純関数
# ---------------------------------------------------------------------------
def has_sips():
    return shutil.which("sips") is not None


def image_width(path):
    """横幅を返す。読めなければ None（副作用なし）。"""
    try:
        r = subprocess.run(["sips", "-g", "pixelWidth", path],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"pixelWidth:\s*(\d+)", r.stdout)
    return int(m.group(1)) if m else None


def needs_resize(width, limit):
    """横幅を縮めるべきか。**上限以下なら触らない**（拡大しない）。"""
    return isinstance(width, int) and width > limit


def needs_recompress(name):
    """PNG は JPEG へ入れ替える（容量の94%がここ）。"""
    return name.lower().endswith(".png")


def plan(names, limit=DEFAULT_WIDTH):
    """何をするかの計画を返す（テストしやすいように分離・副作用なし）。"""
    out = []
    for n in names:
        if not n.lower().endswith(IMAGE_EXT):
            continue
        out.append((n, needs_recompress(n)))
    return out


# ---------------------------------------------------------------------------
# 副作用
# ---------------------------------------------------------------------------
def shrink_one(src, dst, limit=DEFAULT_WIDTH, quality=DEFAULT_QUALITY):
    """1枚を軽くして dst へ置く。戻り値: (元バイト, 後バイト, 何をしたか)。"""
    shutil.copy2(src, dst)
    before = os.path.getsize(src)
    actions = []
    if not has_sips():
        return before, before, "そのままコピー（sips なし）"

    w = image_width(dst)
    if needs_resize(w, limit):
        subprocess.run(["sips", "--resampleWidth", str(limit), dst],
                       capture_output=True, timeout=120)
        actions.append("幅%d→%d" % (w, limit))
    if needs_recompress(os.path.basename(dst)):
        # ★拡張子は変えない（catalog.json が名前で参照している）。
        #   中身が JPEG でもブラウザは表示できる。
        subprocess.run(["sips", "-s", "format", "jpeg",
                        "-s", "formatOptions", str(quality), dst],
                       capture_output=True, timeout=120)
        actions.append("PNG→JPEG(q%d)" % quality)
    after = os.path.getsize(dst)
    # ★「軽くならなかったら元に戻す」を**横幅の縮小まで巻き戻してはいけない**（KLK-110）。
    #   JPEG は再エンコードで容量が増えることがあり、そのせいで
    #   **2506px のまま残った画像が12枚あった**（実装時に全数調査で判明）。
    #   横幅を絞ったこと自体は目的（表示に必要な解像度へ揃える）なので取り消さない。
    #   巻き戻すのは「サイズも形式も変えていないのに増えた」ときだけ。
    if after >= before and not actions:
        shutil.copy2(src, dst)
        return before, before, "元のまま（変更点なし）"
    if after >= before and "幅" not in " ".join(actions):
        # 形式の入れ替えだけで増えたなら、その入れ替えは無意味なので戻す
        shutil.copy2(src, dst)
        return before, before, "元のまま（形式変更で増えた）"
    return before, after, " / ".join(actions) or "変更なし"


def shrink_all(src_dir, dst_dir, limit=DEFAULT_WIDTH, quality=DEFAULT_QUALITY, quiet=False):
    """src_dir の画像を軽くして dst_dir へ。戻り値: (枚数, 元合計, 後合計)。"""
    os.makedirs(dst_dir, exist_ok=True)
    try:
        names = sorted(os.listdir(src_dir))
    except OSError:
        return 0, 0, 0
    total_before = total_after = 0
    n = 0
    for name in names:
        src = os.path.join(src_dir, name)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(dst_dir, name)
        if not name.lower().endswith(IMAGE_EXT):
            shutil.copy2(src, dst)          # 画像以外はそのまま
            continue
        b, a, what = shrink_one(src, dst, limit, quality)
        total_before += b
        total_after += a
        n += 1
        if not quiet and n % 20 == 0:
            print("    %d/%d 枚…" % (n, len(names)))
    return n, total_before, total_after


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    opts = {}
    for a in argv[1:]:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            opts[k] = v
    if not args:
        print(__doc__)
        return 2
    dst = args[0]
    src = opts.get("src", os.path.join("catalog", "img"))
    limit = int(opts.get("width", DEFAULT_WIDTH))
    quality = int(opts.get("quality", DEFAULT_QUALITY))
    if not os.path.isdir(src):
        print("[NG] 元フォルダがありません: %s" % src, file=sys.stderr)
        return 1
    if not has_sips():
        print("  【注意】sips が無いため画像はそのままコピーします"
              "（macOS 以外。配布物が大きくなりますが動作には影響しません）")
    n, before, after = shrink_all(src, dst, limit, quality)
    if n == 0:
        print("[OK] 画像がありませんでした: %s" % src)
        return 0
    print("[OK] %d 枚を軽くしました: %.0f MB → %.0f MB（%.0f%% 減）"
          % (n, before / 1048576, after / 1048576,
             (1 - after / before) * 100 if before else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
