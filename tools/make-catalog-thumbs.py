#!/usr/bin/env python3
"""一覧用のサムネイルを作る（KLK-128）。**元画像は触らない。**

    python3 tools/make-catalog-thumbs.py               # 足りないぶんだけ作る
    python3 tools/make-catalog-thumbs.py --force       # 全部作り直す
    python3 tools/make-catalog-thumbs.py --width 400 --quality 80

★なぜ要るか（2026-09-15 の実測）
  カタログ画像は**サイト全体を縦に撮った原寸のスクリーンショット**で、
  たとえば cat-0005.png は 1500 x 12391 px ある。一方、表示は 123 x 91px のカード。
  既定で並ぶ18枚だけで、ブラウザが展開する画像メモリは **634MB**（1.7億画素）。
  「さらに表示する」で167枚全部になると **5.8GB**。
  メモリに余裕が無いと展開が見送られ、**枠だけが残る**。
  実際に理恵さんの環境でその状態になった（ブリッジ再起動で復帰）。

★なぜ「切り抜かず」に一様縮小するのか
  見せている場所が画面ごとに違う。
    index.html  … object-position 指定なし＝**中央**の帯が見える
    catalog.html … object-position: top center＝**上端**が見える
  一様に縮めておけば、切り出すのは今までどおり各画面の CSS の仕事になり、
  **見た目がまったく変わらない**。
  （sips は中央でしか切り抜けない。`--cropOffset` は効かないことを実測で確認した。）

★横幅400の根拠（実測）
  18枚の展開メモリ 634MB → **42MB**。
  カードは 123px 幅なので、2倍表示の端末でも 246px あれば足りる。

★守ること
  - **原寸は消さない。** 拡大（🔍）は原寸を出す。
  - サムネイルが無くても壊れない。画面側は原寸へ自動で戻す。
  - sips が無い環境（Windows 等）ではそのままコピーになる（fail-soft）。
    容量は減らないが、壊れはしない。
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "catalog", "img")
DST_DIR = os.path.join(ROOT, "catalog", "thumb")
DEFAULT_WIDTH = 400
DEFAULT_QUALITY = 80
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


def load_shrink():
    """既存の縮小処理を読み込む（同じ道具を二度書かない）。"""
    import importlib.util
    path = os.path.join(ROOT, "tools", "shrink-catalog-images.py")
    spec = importlib.util.spec_from_file_location("klk_shrink_for_thumbs", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def is_image(name):
    return name.lower().endswith(IMAGE_EXT)


def needs_thumb(src, dst, force):
    """作る必要があるか（純粋関数に近い・os.stat のみ）。"""
    if force or not os.path.isfile(dst):
        return True
    try:
        return os.path.getmtime(dst) < os.path.getmtime(src)
    except OSError:
        return True


def make_one(mod, src, dst, width, quality):
    """1枚ぶん。戻り値: (元バイト, 後バイト, 何をしたか)。"""
    tmp = dst + ".tmp"
    try:
        before, after, what = mod.shrink_one(src, tmp, limit=width, quality=quality)
        os.replace(tmp, dst)
        return before, after, what
    except Exception as exc:                     # 1枚失敗しても全体は続ける
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return 0, 0, "失敗: {0}".format(exc)


def main(argv):
    force = "--force" in argv
    width = DEFAULT_WIDTH
    quality = DEFAULT_QUALITY
    for i, a in enumerate(argv):
        if a == "--width" and i + 1 < len(argv):
            width = int(argv[i + 1])
        if a == "--quality" and i + 1 < len(argv):
            quality = int(argv[i + 1])

    if not os.path.isdir(SRC_DIR):
        print("[NG] %s がありません" % SRC_DIR, file=sys.stderr)
        return 2
    mod = load_shrink()
    if not mod.has_sips():
        print("※ sips が無い環境です。そのままコピーになります（容量は減りません）")
    os.makedirs(DST_DIR, exist_ok=True)

    names = sorted(n for n in os.listdir(SRC_DIR) if is_image(n))
    made = skipped = failed = 0
    total_before = total_after = 0
    for n in names:
        src = os.path.join(SRC_DIR, n)
        dst = os.path.join(DST_DIR, n)
        if not needs_thumb(src, dst, force):
            skipped += 1
            continue
        before, after, what = make_one(mod, src, dst, width, quality)
        if not before:
            failed += 1
            print("[NG] %s — %s" % (n, what), file=sys.stderr)
            continue
        made += 1
        total_before += before
        total_after += after

    print("対象 %d 件: 作成 %d / 据え置き %d / 失敗 %d" % (len(names), made, skipped, failed))
    if total_before:
        print("作成ぶんの容量: %.1fMB → %.1fMB（%.0f%% 減）"
              % (total_before / 1048576.0, total_after / 1048576.0,
                 100.0 * (total_before - total_after) / total_before))
    print("置き場所: %s" % os.path.relpath(DST_DIR, ROOT))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
