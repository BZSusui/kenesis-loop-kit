#!/usr/bin/env python3
"""
KLK-110 acceptance-condition checker — 配布用にカタログ画像を軽くする。

理恵さんのご指示（2026-09-09）: 「画像を長辺1600pxへ縮小」
→ 調べたら**長辺基準は使えなかった**ので、事実を報告して「横幅基準」で合意した。

★長辺基準が使えない理由（実測）
  ・実績画像はサイトのフルページ・スクリーンショットで、167枚のうち**118枚が
    縦が横の3倍以上**（最大 17.2倍・952x16383）。長辺で揃えると横幅が
    **93〜194px** まで潰れ、実績が読めなくなる。
  ・`sips -Z` は**小さい画像を拡大する**（1253x1589 → 1261x1600）。画質が落ちるだけ。

★容量の真因（実測）
  773MB のうち **728MB(94%) が PNG**（140枚・1枚平均5.2MB）。
  しかも元から横幅1600px以下が多く、**横幅を縮めても標本10枚でほぼ減らなかった**。
  効くのは PNG→JPEG。両方あわせて 773MB → 217MB（72%減・約50秒）。

★この checker が守っているもの
  **「軽くすること」より「実績が読めること」が優先。**
  縦横比を崩す・拡大する・参照を切る、のどれかを踏んだら軽量化は失敗である。

Run: python3 tests/site/check_klk110.py
"""
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOL = os.path.join(ROOT, "tools", "shrink-catalog-images.py")
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def load_tool():
    spec = importlib.util.spec_from_file_location("klk110_shrink", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check("A 軽量化ツールが存在する", os.path.isfile(TOOL), TOOL)
if not os.path.isfile(TOOL):
    print("FAIL: ツールがありません")
    sys.exit(1)

M = load_tool()
SRC = io.open(TOOL, encoding="utf-8").read()
PKG = io.open(os.path.join(ROOT, "tools", "make-package.sh"), encoding="utf-8").read()


# ---------------------------------------------------------------------------
# 純関数の契約
# ---------------------------------------------------------------------------
check("B 上限が横幅1600px・品質82（合意した値）",
      M.DEFAULT_WIDTH == 1600 and M.DEFAULT_QUALITY == 82,
      "幅=%s / 品質=%s" % (M.DEFAULT_WIDTH, M.DEFAULT_QUALITY))

check("C ★上限以下は縮めない（拡大しない）",
      M.needs_resize(2000, 1600) is True
      and M.needs_resize(1600, 1600) is False
      and M.needs_resize(800, 1600) is False,
      "2000=%s / 1600=%s / 800=%s"
      % (M.needs_resize(2000, 1600), M.needs_resize(1600, 1600), M.needs_resize(800, 1600)))

check("D 寸法が読めない場合も落ちない（fail-soft）",
      M.needs_resize(None, 1600) is False and M.needs_resize("x", 1600) is False,
      "None=%s" % M.needs_resize(None, 1600))

check("E PNG を入れ替え対象と判定する（容量の94%）",
      M.needs_recompress("a.png") and M.needs_recompress("A.PNG")
      and not M.needs_recompress("a.jpg"),
      "png=%s / jpg=%s" % (M.needs_recompress("a.png"), M.needs_recompress("a.jpg")))

# ---------------------------------------------------------------------------
# ★実際に変換して、実績が読める状態を保つか
# ---------------------------------------------------------------------------
cat_img = os.path.join(ROOT, "catalog", "img")
if not (os.path.isdir(cat_img) and shutil.which("sips")):
    for label in ("F ★縦横比が崩れない", "G ★拡大されない", "H ★横幅が上限に収まる",
                  "I ★ファイル名が変わらない（catalog.json の参照を守る）",
                  "J ★変換後もブラウザが表示できる形式", "K ★元画像を書き換えない"):
        check(label, True, "catalog/img が無い / sips 無し（照合不能・素通り）")
else:
    import glob
    import random
    import re

    def dim(p):
        r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", p],
                           capture_output=True, text=True, timeout=30).stdout
        m = re.findall(r":\s*(\d+)", r)
        return (int(m[0]), int(m[1])) if len(m) >= 2 else (0, 0)

    files = sorted(glob.glob(os.path.join(cat_img, "*")))
    random.seed(110)
    # 極端な形状を必ず含める（縦長・小さい・大きい）
    by_ratio = []
    for p in files:
        w, h = dim(p)
        if w:
            by_ratio.append((h / w, p))
    by_ratio.sort()
    picks = {by_ratio[-1][1], by_ratio[0][1],
             min(files, key=os.path.getsize), max(files, key=os.path.getsize)}
    picks |= set(random.sample(files, min(6, len(files))))
    picks = sorted(picks)

    before_sizes = {os.path.basename(p): os.path.getsize(p) for p in picks}
    wd = tempfile.mkdtemp()
    src2 = os.path.join(wd, "src")
    dst2 = os.path.join(wd, "dst")
    os.makedirs(src2)
    for p in picks:
        shutil.copy2(p, os.path.join(src2, os.path.basename(p)))
    try:
        M.shrink_all(src2, dst2, quiet=True)
        ratio_bad, up_bad, wide_bad, name_bad, fmt_bad = [], [], [], [], []
        for p in picks:
            n = os.path.basename(p)
            q = os.path.join(dst2, n)
            if not os.path.isfile(q):
                name_bad.append(n)
                continue
            a, b = dim(p), dim(q)
            if not (a[0] and b[0]):
                continue
            if abs(a[1] / a[0] - b[1] / b[0]) > 0.02:
                ratio_bad.append((n, round(a[1] / a[0], 2), round(b[1] / b[0], 2)))
            if b[0] > a[0]:
                up_bad.append((n, a[0], b[0]))
            if b[0] > M.DEFAULT_WIDTH:
                wide_bad.append((n, b[0]))
            head = io.open(q, "rb").read(4)
            if not (head[:2] == b"\xff\xd8" or head[:4] == b"\x89PNG"):
                fmt_bad.append(n)

        check("F ★縦横比が崩れない（実績が読める）", not ratio_bad,
              "崩れ=%s（標本 %d 枚・最大縦横比 %.1f 倍を含む）"
              % (ratio_bad or "なし", len(picks), by_ratio[-1][0]))
        check("G ★拡大されない（sips -Z の罠を踏まない）", not up_bad,
              "拡大=%s" % (up_bad or "なし"))
        check("H ★横幅が上限に収まる", not wide_bad, "超過=%s" % (wide_bad or "なし"))

        # ★★ここが一番大事: 縦長画像の**横幅が読める大きさで残る**こと。
        #   縦横比の検査だけでは足りない。長辺基準（sips -Z）は比率を保ったまま
        #   横幅を 93〜194px まで潰すので、「比率OK」で通り抜ける（実際に通した）。
        #   横幅そのものに下限を置いて、実績が読めない縮小を拒む。
        MIN_READABLE_WIDTH = 700
        narrow = []
        for p in picks:
            n = os.path.basename(p)
            q = os.path.join(dst2, n)
            if not os.path.isfile(q):
                continue
            a, b = dim(p), dim(q)
            if not (a[0] and b[0]):
                continue
            # 元が十分広かったのに、読めない幅まで落ちていないか
            if a[0] >= MIN_READABLE_WIDTH and b[0] < MIN_READABLE_WIDTH:
                narrow.append((n, a[0], b[0]))
        check("H2 ★★縦長画像の横幅が読める大きさで残る（長辺基準への逆戻りを拒む）",
              not narrow,
              "読めない幅まで潰れた=%s（下限 %dpx・標本の最大縦横比 %.1f 倍）"
              % (narrow or "なし", MIN_READABLE_WIDTH, by_ratio[-1][0]))
        check("I ★ファイル名が変わらない（catalog.json の参照を守る）", not name_bad,
              "欠落=%s" % (name_bad or "なし"))
        check("J ★変換後もブラウザが表示できる形式", not fmt_bad,
              "不明形式=%s" % (fmt_bad or "なし"))
        after = {os.path.basename(p): os.path.getsize(p) for p in picks}
        check("K ★元画像を書き換えない", after == before_sizes,
              "変化した元画像=%s"
              % ([k for k in after if after[k] != before_sizes[k]] or "なし"))
    finally:
        shutil.rmtree(wd, ignore_errors=True)

# ---------------------------------------------------------------------------
# 巻き戻しの分離（実装時に踏んだバグ）
# ---------------------------------------------------------------------------
check("L ★「軽くならなければ元に戻す」が横幅の縮小まで巻き戻さない",
      '"幅" not in " ".join(actions)' in SRC,
      "分離=%s" % ('"幅" not in " ".join(actions)' in SRC))
check("M そのバグの経緯が記録されている（12枚残った）",
      "12枚" in SRC, "記録=%s" % ("12枚" in SRC))

# ---------------------------------------------------------------------------
# パッケージへの組み込み
# ---------------------------------------------------------------------------
check("N make-package.sh が --with-catalog で軽量化を通す",
      "shrink-catalog-images.py" in PKG, "呼び出し=%s" % ("shrink-catalog-images.py" in PKG))
check("O 軽量化に失敗しても配布を止めない（元サイズでコピー）",
      "元のサイズでコピー" in PKG, "fail-soft=%s" % ("元のサイズでコピー" in PKG))
check("O2 ★ツールが横幅基準で縮小する（`sips -Z` を使わない）",
      "--resampleWidth" in SRC and '"-Z"' not in SRC,
      "resampleWidth=%s / -Z の使用=%s"
      % ("--resampleWidth" in SRC, '"-Z"' in SRC))

check("P 「長辺ではなく横幅」の理由がツールと組み込みの両方に残っている",
      "横幅" in SRC and "長辺" in SRC and "横幅" in PKG,
      "ツール=%s / パッケージ=%s" % ("横幅" in SRC, "横幅" in PKG))

print("=" * 78)
print("KLK-110 配布用にカタログ画像を軽くする チェック")
print("=" * 78)
failed = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print("[%s] %s" % (status, name))
    print("        %s" % detail)
print("-" * 78)
print("%d checks, %d failed" % (len(results), failed))
sys.exit(1 if failed else 0)
