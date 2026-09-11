#!/usr/bin/env python3
"""
KLK-112 acceptance-condition checker — デザインシステム（DADS）の使い方マニュアル。

★このマニュアルが抱えるリスク
  DADSのMarkdownには**色の値（HEX）が存在しない**。にもかかわらず「DADSの色は
  #xxxxxx」と書いてしまう事故が起きやすく、CLAUDE.md / agents 側でも禁止している。
  マニュアルは読者が最初に見る文書なので、ここが間違っていると全員に伝播する。

★この checker が守っているもの
  1. 事実整合 — 49種・ファイル数・出典行が**実物と一致**すること（数字を書き写した
     時点で腐り始めるため、実データから照合する）
  2. 値の捏造防止 — 「DADSが定める色」の類を書いていないこと
  3. 掲載した実測値が本当に正しいこと — マニュアル中のコントラスト比を**再計算して照合**する
     （書いた数字を自分で正とせず、計算で確かめる）
  4. 単一HTML・外部リソース依存ゼロ／リンク切れなし
  5. 実際に作ったパッケージへ同梱されること（形でなく成果物を見る）

Run: python3 tests/site/check_klk112.py [--fast]   (--fast はパッケージ実ビルドを省く)
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANUAL_NAME = "デザインシステムの使い方.html"
MANUAL = os.path.join(ROOT, MANUAL_NAME)
DS = os.path.join(ROOT, "docs", "design-system")
ATTRIBUTION_LINE = "出典：デジタル庁デザインシステムウェブサイト https://design.digital.go.jp/dads/"
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def relative_luminance(hex_color):
    """WCAG の相対輝度。hex は #rrggbb（小文字）。"""
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(a, b):
    """2色のコントラスト比。DADSの下限（本文4.5:1 / 非テキスト3:1）判定に使う。"""
    hi, lo = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def strip_non_text(html):
    """コメント・script・style を除いた、読者の目に入る部分だけを返す。"""
    out = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    out = re.sub(r"<script\b.*?</script>", "", out, flags=re.S | re.I)
    out = re.sub(r"<style\b.*?</style>", "", out, flags=re.S | re.I)
    return out


def external_resource_refs(html):
    """外部から読み込んでいるリソースを返す（<a href> は読み込みではないので対象外）。"""
    hits = []
    hits += re.findall(r'<script[^>]+src=["\'](https?://[^"\']+)', html, re.I)
    hits += re.findall(r'<link[^>]+href=["\'](https?://[^"\']+)', html, re.I)
    hits += re.findall(r'<img[^>]+src=["\']([^"\']+)', html, re.I)
    hits += re.findall(r'@import\s+["\']?(https?://[^"\';]+)', html, re.I)
    hits += re.findall(r'url\(\s*["\']?(https?://[^"\')]+)', html, re.I)
    return hits


def component_count(ds_dir=DS):
    comp = os.path.join(ds_dir, "components")
    if not os.path.isdir(comp):
        return 0
    return len([d for d in os.listdir(comp) if os.path.isdir(os.path.join(comp, d))])


def dads_file_counts(ds_dir=DS):
    """(DADS配布物の数, キット側で足した補助ファイルの数) を返す。"""
    dads = kit = 0
    for root, _dirs, files in os.walk(ds_dir):
        for f in files:
            if not f.endswith(".md"):
                continue
            if f.startswith("_"):
                kit += 1
            else:
                dads += 1
    return dads, kit


HTML = io.open(MANUAL, encoding="utf-8").read() if os.path.isfile(MANUAL) else ""
TEXT = strip_non_text(HTML)

check("A1 マニュアル本体が存在する", bool(HTML), "%s / %d bytes" % (MANUAL_NAME, len(HTML)))

# ---------------------------------------------------------------------------
# B. 単一HTML・外部リソース依存ゼロ・図解はCSS/SVGのみ
# ---------------------------------------------------------------------------
ext = external_resource_refs(HTML)
check("B1 外部リソースを読み込んでいない（単一HTMLで完結）",
      not ext, "検出=%s" % (ext[:4] or "なし"))

check("B2 ラスタ画像を埋め込んでいない（図解はCSS/SVGのみ）",
      "data:image/png" not in HTML and "data:image/jpeg" not in HTML and "<img" not in HTML,
      "img要素=%s data:image=%s" % ("<img" in HTML, "data:image" in HTML))

check("B3 図解が入っている（文字だけの説明にしない）",
      HTML.count("<svg") >= 2, "svg=%d個" % HTML.count("<svg"))

# ---------------------------------------------------------------------------
# C. リンクが切れていない
# ---------------------------------------------------------------------------
anchors = re.findall(r'href="#([^"]+)"', HTML)
ids = set(re.findall(r'id="([^"]+)"', HTML))
dead_anchors = sorted({a for a in anchors if a not in ids})
check("C1 ページ内リンクが全件つながる", not dead_anchors,
      "リンク%d件 / 切れ=%s" % (len(anchors), dead_anchors or "なし"))

nav_links = re.findall(r'<nav id="toc">(.*?)</nav>', HTML, re.S)
nav_ids = re.findall(r'href="#([^"]+)"', nav_links[0]) if nav_links else []
section_ids = re.findall(r'<section id="([^"]+)"', HTML)
check("C2 サイドナビと本文の節が過不足なく対応する",
      nav_ids and nav_ids == section_ids,
      "ナビ%d件 / 節%d件 / 差=%s" % (len(nav_ids), len(section_ids),
                                     sorted(set(nav_ids) ^ set(section_ids)) or "なし"))

local_links = [h for h in re.findall(r'href="([^"#]+)"', HTML)
               if not h.startswith(("http://", "https://", "mailto:"))]
missing_local = [h for h in local_links if not os.path.exists(os.path.join(ROOT, h))]
check("C3 ローカルファイルへのリンク先が実在する",
      not missing_local, "リンク=%s / 欠落=%s" % (sorted(set(local_links)), missing_local or "なし"))

# ---------------------------------------------------------------------------
# D. 事実整合（実データと照合する。数字の書き写しは腐る）
# ---------------------------------------------------------------------------
n_comp = component_count()
check("D1 「49種」がコンポーネント実数と一致する",
      n_comp == 49 and "49種" in TEXT, "実数=%d / 本文に49種=%s" % (n_comp, "49種" in TEXT))

n_dads, n_kit = dads_file_counts()
claimed_total = re.search(r"全部で(\d+)個", TEXT)
claimed_dads = re.search(r"うち(\d+)個がデジタル庁の配布物", TEXT)
check("D2 ファイル数の記載が実数と一致する",
      claimed_total and claimed_dads
      and int(claimed_total.group(1)) == n_dads + n_kit
      and int(claimed_dads.group(1)) == n_dads,
      "実数 合計%d(配布物%d/キット%d) / 記載 合計%s・配布物%s" % (
          n_dads + n_kit, n_dads, n_kit,
          claimed_total.group(1) if claimed_total else "無",
          claimed_dads.group(1) if claimed_dads else "無"))

check("D3 出典行が原文どおり載っている", ATTRIBUTION_LINE in TEXT,
      "一致=%s" % (ATTRIBUTION_LINE in TEXT))

check("D4 「色の値はDADSに無い」ことを明記している",
      "色のコードは書かれていません" in TEXT or "色のコードは資料にない" in TEXT,
      "明記=%s" % ("色のコードは書かれていません" in TEXT or "色のコードは資料にない" in TEXT))

# 値の捏造: 「DADSが定める色 #xxxxxx」のような書き方をしていないこと
fabricated = re.findall(r"DADS[^。]{0,20}(?:定める|規定する)[^。]{0,10}色[^。]{0,20}#[0-9a-fA-F]{6}", TEXT)
check("D5 DADSが定めた色として具体値を書いていない",
      not fabricated, "検出=%s" % (fabricated[:2] or "なし"))

# 2026-09-09 方針: デザインシステムとモック生成は別案件として進める。
# マニュアルは DADS だけを扱い、モック生成へは言及しない（配布パッケージも分ける）
mock_refs = [w for w in ("モック生成", "使い方マニュアル.html", "デザインラフ", "draft-gen")
             if w in TEXT]
check("D7 モック生成システムへ言及していない（別案件として分離）",
      not mock_refs, "検出=%s" % (mock_refs or "なし"))

check("D6 見本の色が「DADSの値ではない」と断ってある",
      "DADSが定めた色ではありません" in TEXT,
      "断り書き=%s" % ("DADSが定めた色ではありません" in TEXT))

# ---------------------------------------------------------------------------
# E. 掲載した実測値を再計算して照合する（書いた数字を自分で正としない）
# ---------------------------------------------------------------------------
demo_hex = re.search(r"--demo-blue:\s*(#[0-9a-f]{6})", HTML)
claimed_ratio = re.search(r"明暗差を測ると([\d.]+):1", TEXT)
if demo_hex and claimed_ratio:
    actual = contrast_ratio(demo_hex.group(1), "#ffffff")
    stated = float(claimed_ratio.group(1))
    check("E1 ★本文のコントラスト実測値が再計算と一致する",
          abs(actual - stated) < 0.05,
          "本文=%.2f:1 / 再計算=%.2f:1（%s と白）" % (stated, actual, demo_hex.group(1)))
    check("E2 見本の配色がDADSの下限（本文4.5:1）を満たす",
          actual >= 4.5, "実測=%.2f:1" % actual)
else:
    check("E1 ★本文のコントラスト実測値が再計算と一致する", False,
          "見本色=%s / 記載=%s" % (bool(demo_hex), bool(claimed_ratio)))
    check("E2 見本の配色がDADSの下限（本文4.5:1）を満たす", False, "照合不能")

check("E3 押せる範囲44pxを見本自身が満たしている",
      re.search(r"\.demo-btn\s*\{[^}]*min-height:\s*44px", HTML, re.S) is not None,
      "min-height:44px=%s" % (re.search(r"min-height:\s*44px", HTML) is not None))

check("E4 フォーカスの2重構造を見本自身が実装している",
      "focus-visible" in HTML and "box-shadow:0 0 0 4px" in HTML,
      "focus-visible=%s 2重=%s" % ("focus-visible" in HTML, "box-shadow:0 0 0 4px" in HTML))

# ---------------------------------------------------------------------------
# F. 案内としての整合（README・パッケージ・モック生成側との住み分け）
# ---------------------------------------------------------------------------
PKG = io.open(os.path.join(ROOT, "tools", "make-package.sh"), encoding="utf-8").read()
# KLK-115: 既定では同梱しない（別案件）。--with-design-system の分岐に載っていること
check("F1 make-package.sh の --with-design-system 分岐で同梱される",
      MANUAL_NAME in PKG and "--with-design-system" in PKG,
      "記載=%s フラグ=%s" % (MANUAL_NAME in PKG, "--with-design-system" in PKG))

README = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
check("F2 README から辿れる", MANUAL_NAME in README, "記載=%s" % (MANUAL_NAME in README))

# 隔離: モック生成側のファイルへこのマニュアルを置いていないこと（KLK-111の不変条件）
ui = io.open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
check("F3 モック生成画面へは載せていない（KLK-111の隔離を壊さない）",
      MANUAL_NAME not in ui and "design-system" not in ui,
      "UIへの記載=%s" % (MANUAL_NAME in ui))

# ---------------------------------------------------------------------------
# G. 実効果 — 実際にパッケージを組んで確かめる
# ---------------------------------------------------------------------------
if "--fast" not in sys.argv:
    tmp = tempfile.mkdtemp(prefix="klk112_pkg_")
    dest = os.path.join(tmp, "pkg")
    try:
        # KLK-115: マニュアルは --with-design-system を付けたときだけ入る。
        # 既定ビルドに入らないことは tests/site/check_klk115.py が見る。
        r = subprocess.run(["bash", os.path.join(ROOT, "tools", "make-package.sh"),
                            dest, "--with-design-system"],
                           capture_output=True, text=True, timeout=600)
        built = os.path.join(dest, MANUAL_NAME)
        check("G1 ★--with-design-system で組んだパッケージへ同梱される",
              r.returncode == 0 and os.path.isfile(built),
              "rc=%d / 同梱=%s" % (r.returncode, os.path.isfile(built)))
        if os.path.isfile(built):
            body = io.open(built, encoding="utf-8").read()
            # (a) 配布される実物が原本と同一か（コピーで欠けていないか）
            same = body == HTML
            # (b) 出典行が配布物に残っているか（デジタル庁の利用条件は配布物にかかる）
            has_credit = ATTRIBUTION_LINE in strip_non_text(body)
            # (c) ローカルリンクがあればパッケージ内で解決するか
            #     （2026-09-09 現在はリンク0本。将来足したときに効く）
            pkg_local = [h for h in re.findall(r'href="([^"#]+)"', body)
                         if not h.startswith(("http://", "https://", "mailto:"))]
            broken = [h for h in pkg_local if not os.path.exists(os.path.join(dest, h))]
            check("G2 ★配布される実物が原本と同一で、出典行が残り、リンクが切れない",
                  same and has_credit and not broken,
                  "原本と同一=%s 出典行=%s ローカルリンク%d本 切れ=%s" % (
                      same, has_credit, len(pkg_local), broken or "なし"))
        else:
            check("G2 ★配布される実物が原本と同一で、出典行が残り、リンクが切れない",
                  False, "同梱されていない")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

print("=" * 78)
print("KLK-112 デザインシステム（DADS）の使い方マニュアル チェック")
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
