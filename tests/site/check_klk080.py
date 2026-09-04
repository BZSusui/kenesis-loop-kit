#!/usr/bin/env python3
"""
KLK-080 acceptance-condition checker (static / no browser required).

後段検証を「型が変わったか」から「**その型が規約を守って作られているか**」へ広げた変更。

★このチェッカーが守っているもの:
  KLK-079 の後段検証は型マーカーしか見ていなかった。
  地図のアタリが 16/7 でも masonry の最終行に空白があっても、
  ブリッジは「GALLERY-01 を pat-masonry にしました」と満足そうに報告してしまう。
  KLK-072〜076 で4回続けて起きたのは、まさにその手の違反だった。

  Q群 = find_quality_warnings の実挙動（仕込んだ違反を検出し、正しい生成物では黙る）
  B群 = ブリッジ/UI への配線
  T群 = tools/verify-mockup.py
  S群 = 見本の実物（警告ゼロで通ること）

Run: python3 tests/site/check_klk080.py
"""
import glob
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

BRIDGE_SRC = open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
TOOL = os.path.join(ROOT, "tools", "verify-mockup.py")
TOOL_SRC = open(TOOL, encoding="utf-8").read() if os.path.isfile(TOOL) else ""
SAMPLE_DIRS = sorted(d for d in glob.glob(os.path.join(ROOT, "samples", "*")) if os.path.isdir(d))

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def rel(p):
    return os.path.relpath(p, ROOT)


S1A = io.open(os.path.join(ROOT, "samples", "01_カフェ_1カラム", "index-a.html"), encoding="utf-8").read()
S1C = io.open(os.path.join(ROOT, "samples", "01_カフェ_1カラム", "index-c.html"), encoding="utf-8").read()
S2C = io.open(os.path.join(ROOT, "samples", "02_士業_本文2カラム", "index-c.html"), encoding="utf-8").read()


def warn_after(src, addr, old, new):
    """src の old を new に置き換えてから検査する（置換できなければ None）。"""
    if old not in src:
        return None
    return bridge.find_quality_warnings(src.replace(old, new, 1), addr)


# ===========================================================================
# Q群 — 仕込んだ違反を検出できるか
# ===========================================================================
w = warn_after(S1A, "ACCESS-01",
               ".map-atari{ position:relative; aspect-ratio:4/3;",
               ".map-atari{ position:relative; aspect-ratio:16/7;")
check(
    "Q1 §3.0 極端な横長比率を検出する（16/7）",
    w and any("極端な横長比率" in x for x in w),
    "警告=%s" % (w if w is not None else "対象文字列なし"),
)

w = warn_after(S1A, "ACCESS-01",
               ".map-atari{ position:relative; aspect-ratio:4/3;",
               ".map-atari{ position:relative; min-height:300px;")
check(
    "Q2 §3.0 min-height だけで高さを決めたアタリを検出する",
    w and any("min-height だけ" in x for x in w),
    "警告=%s" % (w if w is not None else "対象文字列なし"),
)

w = warn_after(S1A, "GALLERY-01",
               'class="m-gallery pat-grid"', 'class="m-gallery pat-grid pat-masonry"')
check(
    "Q3 型マーカーが2つ付いた状態を検出する（旧マーカーの外し忘れ）",
    w and any("型マーカーが2個" in x for x in w),
    "警告=%s" % (w if w is not None else "対象文字列なし"),
)

w = warn_after(S1C, "GALLERY-01", '<div class="atari g-big', '<div class="atari x-big')
check(
    "Q4 masonry / mosaic の空きセルと同サイズ化を検出する",
    w and any("最終行に空き" in x for x in w),
    "警告=%s" % (w if w is not None else "対象文字列なし"),
)

w = warn_after(S2C, "ABOUT-01",
               ".m-about.img-zigzag .zz-row { display: grid; grid-template-columns: 1fr;",
               ".m-about.img-zigzag .zz-row { display: grid; grid-template-columns: 220px 1fr;")
check(
    "Q5 §8.1 2カラムでの画像と本文の横並びを検出する",
    w and any("画像と本文が横並び" in x for x in w),
    "警告=%s" % (w if w is not None else "対象文字列なし"),
)

# --- 誤検出しないこと（ここを外すと警告だらけで誰も読まなくなる）-------------
w = warn_after(S2C, "ABOUT-01",
               ".m-about.img-zigzag .zz-row { display: grid; grid-template-columns: 1fr;",
               ".m-about.img-zigzag .zz-row { display: grid; grid-template-columns: 64px 1fr;")
check(
    "Q6 番号バッジのような小さな固定幅は §8.1 の対象にしない",
    w == [],
    "警告=%s" % w,
)

w = warn_after(S1A, "ABOUT-01", ".m-about.img-left{", ".m-about.img-left{ grid-template-columns:1fr 1fr;")
check(
    "Q7 1カラムのページでは §8.1 を当てない",
    w == [],
    "警告=%s" % w,
)

# panel-band の 3/2 は §3.0 の例外。例外を落とすと KLK-043 で作り込んだフィルム帯が壊れる
_pb = ('<style>.m-hero[data-hero=panel-band] .film .cell{aspect-ratio:3/2;}</style>'
       '<section class="sec"><div class="addr"><span class="pin">MV-01</span></div>'
       '<div class="m-hero" data-hero="panel-band"><div class="film">'
       '<div class="cell"></div></div></div></section>')
check(
    "Q10 §3.0 の例外（panel-band の 3/2）を誤検出しない／16/9 は検出する",
    bridge.find_quality_warnings(_pb, "MV-01") == []
    and any("極端な横長比率" in x
            for x in bridge.find_quality_warnings(_pb.replace("3/2", "16/9"), "MV-01")),
    "3/2=%s / 16/9=%s"
    % (bridge.find_quality_warnings(_pb, "MV-01"),
       bridge.find_quality_warnings(_pb.replace("3/2", "16/9"), "MV-01")),
)

# 壊れた入力で例外を投げないこと（fail-open・ループを止めない）
_robust = []
for bad in (None, "", "<html></html>",
            '<style>.m-hero{color:red</style><section class="sec">'
            '<div class="addr"><span class="pin">MV-01</span></div>'
            '<div class="m-hero" data-hero="full"></div></section>',
            '<span class="pin">MV-01</span><span class="pin">MV-01</span>'):
    try:
        bridge.find_quality_warnings(bad, "MV-01")
    except Exception as exc:
        _robust.append("%s: %s" % (type(exc).__name__, exc))
check(
    "Q11 壊れた入力でも例外を投げない（fail-open・再生成を止めない）",
    not _robust,
    "例外=%s" % (_robust or "なし"),
)

check(
    "Q8 型を持たない番地・読めないHTMLでは黙る（fail-open）",
    bridge.find_quality_warnings(S1A, "NAV-01") == []
    and bridge.find_quality_warnings(S1A, "FOOTER-01") == []
    and bridge.find_quality_warnings("", "MV-01") == []
    and bridge.find_quality_warnings(S1A, "NOPE-99") == [],
    "NAV=%s / 空=%s" % (bridge.find_quality_warnings(S1A, "NAV-01"),
                        bridge.find_quality_warnings("", "MV-01")),
)

# ★:nth-child(N) の span を読めること（KLK-079 の実機検証で判明した書き方）
_nth = (
    '<style>.m-gallery.pat-masonry{grid-template-columns:repeat(4,1fr);}'
    '.m-gallery.pat-masonry .atari:nth-child(1){grid-column:span 2;grid-row:span 2;}'
    '.m-gallery.pat-masonry .atari:nth-child(6){grid-column:span 2;}'
    '.m-gallery.pat-masonry .atari:nth-child(7){grid-column:span 2;}</style>'
    '<section class="sec"><div class="addr"><span class="pin">GALLERY-01</span></div>'
    '<div class="m-gallery pat-masonry">'
    + '<div class="atari"></div>' * 7 +
    '</div></section>'
)
check(
    "Q9 :nth-child(N) で書かれた span を読める（クラス指定だけに頼らない）",
    bridge.find_quality_warnings(_nth, "GALLERY-01") == [],
    "警告=%s（構成A＝4列×3行を隙間なく充填のはず）" % bridge.find_quality_warnings(_nth, "GALLERY-01"),
)
_nth_bad = _nth.replace(".m-gallery.pat-masonry .atari:nth-child(1){grid-column:span 2;grid-row:span 2;}", "")
check(
    "Q9b その span を消せば空きセルとして検出される（Q9 が素通りでない証明）",
    any("最終行に空き" in x for x in bridge.find_quality_warnings(_nth_bad, "GALLERY-01")),
    "警告=%s" % bridge.find_quality_warnings(_nth_bad, "GALLERY-01"),
)

# ===========================================================================
# B群 — ブリッジ / UI への配線
# ===========================================================================
check(
    "B1 worker が型指定の有無にかかわらず品質を検査する",
    "quality = find_quality_warnings(fh.read(), addr)" in BRIDGE_SRC,
    "配線=%s" % ("quality = find_quality_warnings(fh.read(), addr)" in BRIDGE_SRC),
)
check(
    "B2 /status が warnings を返す",
    '"warnings": job.get("warnings") or []' in BRIDGE_SRC,
    "status=%s" % ('"warnings": job.get("warnings") or []' in BRIDGE_SRC),
)
check(
    "B3 違反があれば完了メッセージにも件数が出る",
    "規約違反の疑いが {0} 件あります" in BRIDGE_SRC,
    "メッセージ=%s" % ("規約違反の疑いが {0} 件あります" in BRIDGE_SRC),
)
check(
    "B4 違反をサーバコンソールにも残す（黙らせない）",
    "[bridge] 規約違反の疑い: {0}" in BRIDGE_SRC,
    "ログ=%s" % ("[bridge] 規約違反の疑い: {0}" in BRIDGE_SRC),
)

miss = []
for d in SAMPLE_DIRS:
    p = os.path.join(d, "compare.html")
    html = open(p, encoding="utf-8").read()
    if "s2.warnings" not in html or "warns.length" not in html:
        miss.append(rel(p))
check(
    "B5 UI が warnings を受け取り、成功と同じ見た目にしない",
    not miss,
    "欠け=%s" % (miss or "なし"),
)

# ===========================================================================
# T群 — tools/verify-mockup.py
# ===========================================================================
check(
    "T1 tools/verify-mockup.py がある",
    bool(TOOL_SRC) and "find_quality_warnings" in TOOL_SRC,
    "ツール=%s（%d字）" % (bool(TOOL_SRC), len(TOOL_SRC)),
)
check(
    "T2 ツールがブリッジの純関数を再利用する（規約判定を二重に書かない）",
    "import bridge" in TOOL_SRC and "bridge.find_quality_warnings" in TOOL_SRC,
    "再利用=%s" % ("bridge.find_quality_warnings" in TOOL_SRC),
)

_proc = subprocess.run(
    ["python3", TOOL] + [d for d in SAMPLE_DIRS],
    capture_output=True, text=True, cwd=ROOT, timeout=180,
)
check(
    "T3 ツールが見本3点を違反ゼロで通す（実際に実行）",
    _proc.returncode == 0 and "違反 0 件" in _proc.stdout,
    "exit=%s / 末尾=%s" % (_proc.returncode, _proc.stdout.strip().splitlines()[-1:]),
)

_proc2 = subprocess.run(
    ["python3", TOOL], capture_output=True, text=True, cwd=ROOT, timeout=60,
)
check(
    "T4 引数なしは使い方を出して exit 2（違反0と紛らわしくしない）",
    _proc2.returncode == 2,
    "exit=%s" % _proc2.returncode,
)

# ===========================================================================
# S群 — 見本の実物
# ===========================================================================
total, files = 0, 0
noisy = []
for d in SAMPLE_DIRS:
    for p in sorted(glob.glob(os.path.join(d, "index-*.html"))):
        files += 1
        html = open(p, encoding="utf-8").read()
        for a in bridge.list_page_addrs(html):
            ws = bridge.find_quality_warnings(html, a)
            total += len(ws)
            for x in ws:
                noisy.append("%s: %s" % (rel(p), x))
check(
    "S1 見本9ファイル・全番地が警告ゼロ（誤検出していない証明）",
    files == 9 and total == 0,
    "%dファイル / 警告 %d 件 %s" % (files, total, noisy[:3]),
)

print("=" * 78)
print("KLK-080 型を入れ替えた実物の機械検査 静的チェック")
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
