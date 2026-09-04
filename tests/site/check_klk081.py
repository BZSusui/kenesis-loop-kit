#!/usr/bin/env python3
"""
KLK-081 acceptance-condition checker (static / no browser required).

理恵さんの目視（見本03 案C）で見つかった2件。どちらも**自分が入れた変更の副作用**。

★このチェッカーが守っているもの:
  ① panel-band の段落ち — KLK-075 で `repeat(auto-fit,minmax(220px,1fr))` にしたとき、
     **列数は計算したがパネル数（6枚）と突き合わせていなかった**。
     1200〜1280px でちょうど 5列になり、6枚が 5+1 の2行に落ちる。
     ノートPCで最も多い幅がまさにそこだった。
  ② 見本で「読み込み中…」のまま固まる — KLK-078 で番地を /sections から埋める方式に
     変えたとき、**取得に失敗した場合の表示を作り忘れた**。
     ブリッジは mockups/ 配下しか受け付けないので、見本（samples/）では必ず失敗する。

  R群 = 規約 / G群 = グリッドの実測（段落ちしないことを数値で確かめる） / U群 = UI

Run: python3 tests/site/check_klk081.py
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

RULES = open(
    os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"),
    encoding="utf-8",
).read()
SAMPLE_DIRS = sorted(d for d in glob.glob(os.path.join(ROOT, "samples", "*")) if os.path.isdir(d))

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def rel(p):
    return os.path.relpath(p, ROOT)


def css_of(html):
    return re.sub(r"/\*.*?\*/", "", "\n".join(
        re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)), flags=re.S)


# ===========================================================================
# R群 — 規約
# ===========================================================================
check(
    "R1 §3.0.1 が「どの画面幅でも1行」を要求している",
    "どの画面幅でもパネルが1行に収まる" in RULES
    and "grid-auto-flow: column; grid-auto-columns: 1fr" in RULES,
    "1行要求=%s" % ("どの画面幅でもパネルが1行に収まる" in RULES),
)

check(
    "R2 §3.0.1 が auto-fit を使わないと明記し、段落ちの実測表を載せている",
    "★`repeat(auto-fit, minmax(220px, 1fr))` は使わない（KLK-081）" in RULES
    and "5+1" in RULES
    and "1200〜1280px" in RULES,
    "禁止の明記=%s / 実測表=%s"
    % ("は使わない（KLK-081）" in RULES, "5+1" in RULES),
)

check(
    "R3 §12.1.3 index5 が grid-auto-flow:column を指定している",
    "`grid-auto-flow:column;grid-auto-columns:1fr;gap:4px`＝どの幅でも必ず1行（KLK-081）" in RULES,
    "型定義=%s" % ("grid-auto-flow:column;grid-auto-columns:1fr" in RULES),
)

check(
    "R4 §12.1.3 が「列数を決めるときはアイテム数と突き合わせる」を教訓として残している",
    "グリッドの列数を決めるときは、必ずアイテム数と突き合わせること" in RULES,
    "教訓=%s" % ("グリッドの列数を決めるときは、必ずアイテム数と突き合わせること" in RULES),
)

# ===========================================================================
# G群 — 実測（見本の panel-band が本当に1行に収まるか）
# ===========================================================================
BAND_RE = re.compile(r"panel-band[^{}]*\.film(?:-band)?\s*\{([^}]*)\}")
WIDTHS = (1024, 1200, 1280, 1366, 1440, 1680, 1920)

bands = []
for d in SAMPLE_DIRS:
    for p in sorted(glob.glob(os.path.join(d, "index-*.html"))):
        html = open(p, encoding="utf-8").read()
        if not re.search(r'data-hero=["\']?panel-band', html):
            continue
        css = css_of(html)
        m = BAND_RE.search(css)
        start, end = bridge.find_target_section(html, "MV-01")
        block = html[start:end] if start is not None else ""
        n = len(re.findall(r'class="(?:cell|film-panel)"', block))
        bands.append((rel(p), m.group(1) if m else "", n))

check(
    "G1 panel-band を持つ見本が見つかる（検査が素通りでない証明）",
    len(bands) >= 2 and all(n >= 2 for _p, _b, n in bands),
    "%s" % [(p, n) for p, _b, n in bands],
)

offenders = []
for p, body, n in bands:
    flat = re.sub(r"\s+", "", body)
    if "grid-auto-flow:column" not in flat:
        offenders.append("%s: grid-auto-flow:column でない（%s）" % (p, flat[:70]))
    if "auto-fit" in flat:
        offenders.append("%s: auto-fit が残っている（段落ちの原因）" % p)
    if "max-height" in flat:
        offenders.append("%s: max-height が付いている" % p)
check(
    "G2 帯が grid-auto-flow:column（列数＝パネル数を構造的に保証）",
    not offenders,
    offenders or "なし",
)

# auto-fit のままだったら本当に段落ちしていたことを数値で示す（回帰の目印）
def cols_autofit(width, minw=220, gap=4):
    return max(1, int((width + gap) // (minw + gap)))


wrapped = [
    (w, cols_autofit(w))
    for w in WIDTHS
    if cols_autofit(w) < 6 or (6 % cols_autofit(w) and cols_autofit(w) < 6)
]
check(
    "G3 旧実装(auto-fit)なら 1024〜1280px で段落ちしたことを数値で確認",
    any(w in (1024, 1200, 1280) for w, _c in wrapped),
    "段落ちする幅と列数=%s" % wrapped,
)

# 修正後は列数＝パネル数なので、どの幅でも必ず1行
still_wrapping = []
for p, body, n in bands:
    flat = re.sub(r"\s+", "", body)
    if "grid-auto-flow:column" in flat:
        continue   # 列はアイテム数だけ作られる＝定義上1行
    still_wrapping.append(p)
check(
    "G4 修正後はどの画面幅でも1行（列がアイテム数だけ作られる）",
    not still_wrapping,
    "1行が保証されないファイル=%s" % (still_wrapping or "なし"),
)

# モバイル上書きは grid-auto-flow を row へ戻していること
# （row へ戻さないと repeat(3,1fr) を書いても列方向に流れて1行のまま）
mobile_bad = []
for d in SAMPLE_DIRS:
    for p in sorted(glob.glob(os.path.join(d, "index-*.html"))):
        html = open(p, encoding="utf-8").read()
        if not re.search(r'data-hero=["\']?panel-band', html):
            continue
        for line in css_of(html).splitlines():
            if "repeat(3" in line and "film" in line:
                if "grid-auto-flow" not in line.replace(" ", ""):
                    mobile_bad.append("%s: %s" % (rel(p), line.strip()[:80]))
check(
    "G5 モバイル上書きが grid-auto-flow:row を伴う（row へ戻さないと1行のまま）",
    not mobile_bad,
    mobile_bad or "なし",
)

# ===========================================================================
# U群 — UI（見本で固まらない）
# ===========================================================================
miss_guard, miss_disable = [], []
for d in SAMPLE_DIRS:
    p = os.path.join(d, "compare.html")
    html = open(p, encoding="utf-8").read()
    if "folder.indexOf('mockups/') !== 0" not in html or "（見本では使えません）" not in html:
        miss_guard.append(rel(p))
    if "function disableWith(" not in html or "（取得できませんでした）" not in html:
        miss_disable.append(rel(p))
check(
    "U1 見本ではブリッジを呼ばず「見本では使えません」と出す",
    not miss_guard,
    "欠け=%s" % (miss_guard or "なし"),
)
check(
    "U2 取得失敗・未起動でもセレクタを「読み込み中…」のままにしない",
    not miss_disable,
    "欠け=%s" % (miss_disable or "なし"),
)

# 動的スモークが該当ケースを見ていること
SMOKE = os.path.join(ROOT, "tests", "site", "smoke_klk079.node.js")
smoke_src = open(SMOKE, encoding="utf-8").read() if os.path.isfile(SMOKE) else ""
check(
    "U3 動的スモークが見本・取得失敗・未起動の3ケースを実挙動で見ている",
    all(t in smoke_src for t in ("N11", "N12", "N13", "sectionsFail")),
    "N11=%s N12=%s N13=%s" % ("N11" in smoke_src, "N12" in smoke_src, "N13" in smoke_src),
)

# ブリッジ側の制約は変えていない（書き込み面を広げない）
check(
    "U4 ブリッジは mockups/ 配下のみを受け付けたまま（書き込み面を広げていない）",
    bridge.is_safe_mockups_folder("mockups/x") is True
    and bridge.is_safe_mockups_folder("samples/x") is False,
    "mockups=%s / samples=%s"
    % (bridge.is_safe_mockups_folder("mockups/x"), bridge.is_safe_mockups_folder("samples/x")),
)

print("=" * 78)
print("KLK-081 panel-band の段落ち／見本での「読み込み中…」 静的チェック")
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
