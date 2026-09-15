#!/usr/bin/env python3
"""
KLK-126 acceptance-condition checker — 型ピッカーを図解アイコンのモーダルにする。

★経緯
  型を選ぶ UI は KLK-117/125 で「日本語ラベル（マーカー）」まで来たが、
  <option> の中には図を描けない。KLK-124 の検証の結論どおり、
  **セレクタ自体をアイコン付きの一覧へ作り替える**のがこのチケット。

★この checker が守っているもの
  R. レシピ表が**全マーカーを覆っている**こと（bridge のプールが正）
  K. <select> を**残したまま隠して**いること（KLK-078/079 の不変条件を書き直さないため）
  M. モーダルの部品が揃っていること
  N. 外部依存ゼロ（NFR-005）— アイコンに img/svg/CDN を持ち込んでいないこと
  T. 生成物（samples/）がテンプレートと同じ中身であること（KLK-103）

  実際に開いて選べるかは tests/test_palette_klk126.py が実ブラウザで見る。

Run: python3 tests/site/check_klk126.py
"""
import glob
import importlib.util
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TPL_PATH = os.path.join(ROOT, "draft-gen", "compare_template.html")
TPL = io.open(TPL_PATH, encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "bridge_klk126", os.path.join(ROOT, "draft-gen", "bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def recipe_keys(src):
    """var ICONS = {...} のキー（マーカー）を返す（純粋関数）。"""
    m = re.search(r"var\s+ICONS\s*=\s*\{(.*?)\n\s*\};", src, re.S)
    if not m:
        return None
    return re.findall(r"^\s*'([^']+)':\s*\{", m.group(1), re.M)


b = load_bridge()
KEYS = recipe_keys(TPL)
NEEDED = sorted({t for pool in b.SECTION_TYPE_POOLS.values() for t in pool})

# ---------------------------------------------------------------------------
# R. レシピ表
# ---------------------------------------------------------------------------
check("R1 レシピ表がある", KEYS is not None, "パースできた=%s" % (KEYS is not None))

if KEYS is not None:
    missing = [t for t in NEEDED if t not in KEYS]
    check("R2 ★プールの全マーカーにレシピがある（絵の無い型を作らない）",
          not missing, "必要=%d 有り=%d 欠け=%s" % (len(NEEDED), len(KEYS), missing or "なし"))

    extra = [t for t in KEYS if t not in NEEDED]
    check("R3 プールに無いマーカーを抱えていない（表が腐っていない）",
          not extra, "余り=%s" % (extra or "なし"))

    check("R4 レシピが重複していない", len(KEYS) == len(set(KEYS)),
          "重複=%s" % (sorted({k for k in KEYS if KEYS.count(k) > 1}) or "なし"))

    kinds = sorted(set(re.findall(r"\{\s*k:'([a-z0-9]+)'", TPL)))
    unknown = [k for k in kinds if ("r.k === '%s'" % k) not in TPL]
    check("R5 ★レシピの種別をレンダラが全部知っている（描けない指定を書いていない）",
          not unknown, "種別=%d 未対応=%s" % (len(kinds), unknown or "なし"))

# ---------------------------------------------------------------------------
# K. <select> を値の受け皿として残す（KLK-078/079 の不変条件を守る土台）
# ---------------------------------------------------------------------------
check("K1 ★<select id=\"regen-type\"> が残っている（消していない）",
      '<select id="regen-type"' in TPL, "")

check("K2 <select> は hidden で隠してある（見た目だけモーダルへ移す）",
      re.search(r'<select id="regen-type"[^>]*\shidden', TPL) is not None, "")

check("K3 ★選んだ型は select へ書き戻す（送信側は select しか見ない）",
      re.search(r"function pickType\(t\)\{\s*\n\s*typeSel\.value = t;", TPL) is not None, "")

check("K4 ★現在と違う型のときだけ desiredType を送る（KLK-079 のまま）",
      "typeSel.value !== s.current" in TPL and "body.desiredType = wanted;" in TPL, "")

check("K5 型を持たない番地の文言が残っている（KLK-081）",
      "この番地に型はありません" in TPL, "")

# ---------------------------------------------------------------------------
# M. モーダル
# ---------------------------------------------------------------------------
for name, needle in [
    ("M1 モーダル本体がある", 'id="type-modal"'),
    ("M2 ダイアログとして印が付いている", 'role="dialog"'),
    ("M3 一覧の入れ物がある", 'id="type-modal-list"'),
    ("M4 どの番地かを出す場所がある", 'id="type-modal-addr"'),
    ("M5 閉じるボタンがある", 'id="type-modal-x"'),
    ("M6 顔になるボタンがある", 'id="regen-type-btn"'),
]:
    check(name, needle in TPL, needle)

check("M7 Esc で閉じる", "'Escape'" in TPL and "closeTypeModal()" in TPL, "")
check("M8 閉じたらフォーカスを戻す",
      re.search(r"function closeTypeModal\(\)\{.*?lastFocus", TPL, re.S) is not None, "")
check("M9 1行にアイコン・日本語ラベル・マーカーの3つを並べる",
      "tm-ico" in TPL and "tm-name" in TPL and "tm-mk" in TPL, "")
check("M10 現在の型に印が付く", "'tm-now'" in TPL and "aria-current" in TPL, "")
check("M11 ★「現在」の印が案件の配色に依存しない（配色次第でコントラストが割れる）",
      re.search(r"\.tm-row \.tm-now\{[^}]*background:#[0-9a-f]{6}", TPL) is not None
      and not re.search(r"\.tm-row \.tm-now\{[^}]*var\(--c-", TPL)
      and not re.search(r'\.tm-row\[aria-current="true"\]\{[^}]*var\(--c-', TPL),
      "札と枠を固定色にしている")

check("M12 スマホでも1行を保つ（アイコンを小さくするだけ）",
      re.search(r"@media \(max-width:600px\)\{.*?\.tm-row \.tm-ico\{[^}]*56px", TPL, re.S) is not None, "")

# ---------------------------------------------------------------------------
# N. 外部依存ゼロ（NFR-005）
# ---------------------------------------------------------------------------
ICO_CSS = re.search(r"/\* 型アイコンの部品（KLK-126）.*?\n\n", TPL, re.S)
ico_css = ICO_CSS.group(0) if ICO_CSS else ""
check("N1 アイコンの CSS が見つかる", bool(ico_css), "%d 文字" % len(ico_css))
check("N2 ★アイコンに外部参照が無い（url() / http / svg / img）",
      not re.search(r"url\(|https?://|<svg|<img", ico_css), "")

modal_js = TPL[TPL.find("var ICONS"):TPL.find("// 型セレクタを、選んだ番地")]
check("N3 ★アイコンの組み立てに img/svg を使っていない",
      not re.search(r"createElement\('(img|svg)'\)|<img|<svg", modal_js), "")
check("N4 動的値は textContent（innerHTML を導入していない）",
      ".innerHTML" not in TPL, "innerHTML=%s" % (".innerHTML" in TPL))

# ---------------------------------------------------------------------------
# T. 生成物がテンプレートと同じ（KLK-103: 生成側は書かない）
# ---------------------------------------------------------------------------
stale = []
for p in sorted(glob.glob(os.path.join(ROOT, "samples", "*", "compare.html"))):
    src = io.open(p, encoding="utf-8").read()
    if "var ICONS" not in src or 'id="type-modal"' not in src:
        stale.append(os.path.relpath(p, ROOT))
check("T1 ★見本の compare.html が現テンプレートで書き直されている",
      not stale, "古いまま=%s" % (stale or "なし"))

print("=" * 78)
print("KLK-126 型ピッカーを図解アイコンのモーダルにする チェック")
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
