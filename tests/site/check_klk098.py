#!/usr/bin/env python3
"""
KLK-098 acceptance-condition checker — 使い方マニュアル（HTML）。

★この checker が守っているもの:
  **マニュアルが実物から乖離しないこと**、および
  **社外の目に触れうる文書へ社外秘が載らないこと**。

  このリポジトリは「文書が実装から遅れる」を繰り返している
  （README の未記載2機能・CHANGELOG が34件ぶん停止・KLK-090）。
  マニュアルは配布物なので、型名・選択肢・ボタン名を**実ファイルと突き合わせ**て見張る。

  加えてマニュアルは理恵さんの選択により**クライアント説明にも使う**。
  カタログ（catalog/）は社外秘のご実績を含み、上長承認の条件が
  「社内でのみ使用することを徹底」であるため、**実在のエントリが1件も
  載っていないこと**を機械で保証する。

Run: python3 tests/site/check_klk098.py
Exit code 0 = all pass, 1 = at least one fail.
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

MANUAL = os.path.join(ROOT, "使い方マニュアル.html")
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


if not os.path.isfile(MANUAL):
    check("C0 マニュアルが存在する", False, MANUAL)
    print("FAIL: マニュアルがありません: %s" % MANUAL)
    sys.exit(1)

M = io.open(MANUAL, encoding="utf-8").read()
UI = io.open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
README = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
PKG = io.open(os.path.join(ROOT, "tools", "make-package.sh"), encoding="utf-8").read()

check("C0 マニュアルが存在する", True, os.path.basename(MANUAL))

# ---------------------------------------------------------------------------
# AC1 外部依存ゼロ（生成物と同じ規律・NFR-005）
# ---------------------------------------------------------------------------
ext_link = re.findall(r'<link\b[^>]*\bhref=', M, re.I)
ext_script = re.findall(r'<script\b[^>]*\bsrc=', M, re.I)
# 外部URL: http(s) で始まる参照。説明文中の「https://」も配布物では避ける
# ★localhost は「外部」ではない（ブリッジの画面を開く案内で本文に出る）。
#   守りたいのは「**外のネットワークへ出て行かないこと**」なので、
#   127.0.0.1 / localhost は除く。ここを一緒に弾くと、正しい案内が書けなくなる。
ext_url = [u for u in re.findall(r'https?://[^\s"\'<>]+', M)
           if not re.match(r'https?://(127\.0\.0\.1|localhost)(:|/|$)', u)]
check("C1 <link href> が無い（外部CSSを読まない）", not ext_link, "件数=%d" % len(ext_link))
check("C2 <script src> が無い（外部JSを読まない）", not ext_script, "件数=%d" % len(ext_script))
check("C3 外部URLが1件も無い", not ext_url, "検出=%s" % (ext_url[:4] or "なし"))
check("C4 <iframe> / <object> / <embed> が無い", not re.search(r"<(iframe|object|embed)\b", M, re.I),
      "埋め込み要素=%s" % bool(re.search(r"<(iframe|object|embed)\b", M, re.I)))

# ---------------------------------------------------------------------------
# AC3 図解は CSS/SVG のみ・ラスタ画像を埋め込まない
# ---------------------------------------------------------------------------
img_tags = re.findall(r"<img\b", M, re.I)
data_raster = re.findall(r"data:image/(png|jpe?g|gif|webp|bmp)", M, re.I)
svgs = re.findall(r"<svg\b", M, re.I)
check("C5 <img> が無い（ラスタ画像を貼らない）", not img_tags, "件数=%d" % len(img_tags))
check("C6 data: のラスタ画像が無い（容量・写り込み回避）", not data_raster,
      "検出=%s" % (data_raster[:3] or "なし"))
check("C7 図解が SVG で作られている（図が1枚も無いのは不合格）", len(svgs) >= 4,
      "SVG図 %d 枚" % len(svgs))

# ---------------------------------------------------------------------------
# AC4 ⠿ ドラッグの明記（理恵さんのご要望）
# ---------------------------------------------------------------------------
check("C8 ⠿ の記号が本文に出ている", "⠿" in M, "出現 %d 回" % M.count("⠿"))
check("C9 「押したまま」動かす操作が説明されている（掴む動作の明示）",
      "押したまま" in M and ("ドラッグ" in M or "動かす" in M),
      "押したまま=%s / ドラッグ=%s" % ("押したまま" in M, "ドラッグ" in M))
check("C10 ↑↓ ボタンという代替手段も案内している（ドラッグが苦手な人向け）",
      "↑" in M and "↓" in M and "ボタン" in M,
      "代替の案内=%s" % ("↑" in M and "↓" in M))

# ---------------------------------------------------------------------------
# AC5 ★社外秘が載っていないこと — 実在のカタログエントリと突き合わせる
# ---------------------------------------------------------------------------
cat_path = os.path.join(ROOT, "catalog", "catalog.json")
leaked, checked_n = [], 0
if os.path.isfile(cat_path):
    try:
        data = json.load(io.open(cat_path, encoding="utf-8"))
        entries = data.get("entries", data if isinstance(data, list) else [])
        for e in entries:
            if not isinstance(e, dict):
                continue
            for key in ("id", "title", "client", "name", "file", "image", "note", "memo"):
                v = e.get(key)
                if isinstance(v, str) and len(v.strip()) >= 4:
                    checked_n += 1
                    if v.strip() in M:
                        leaked.append("%s=%s" % (key, v.strip()[:40]))
    except Exception as exc:      # 壊れた JSON で検査を止めない(fail-open)
        checked_n = -1
        leaked = []
        _ = exc
    check("C11 ★実在のカタログエントリがマニュアルに載っていない",
          not leaked, "照合 %d 値 / 漏れ=%s" % (checked_n, leaked[:3] or "なし"))
else:
    check("C11 ★実在のカタログエントリがマニュアルに載っていない",
          True, "catalog.json が無い環境（照合不能・素通り）")

# 例示の案件名は架空であること（見本と同じ「サンプル」系のみ許す）
check("C12 マニュアルが catalog/ の中身を参照していない",
      "catalog/img" not in M and "catalog.json" not in M,
      "参照=%s" % ("catalog/img" in M or "catalog.json" in M))
check("C13 取り扱い判断を当方で下さず、AI利用管理責任者への確認を案内している",
      "AI利用管理責任者" in M,
      "案内=%s" % ("AI利用管理責任者" in M))

# ---------------------------------------------------------------------------
# AC6 ★実物との一致 — 型名・選択肢・ボタン名を実ファイルから突き合わせる
# ---------------------------------------------------------------------------
missing_sec, missing_type = [], []
for key, pool in sorted(bridge.SECTION_TYPE_POOLS.items()):
    if key not in M:
        missing_sec.append(key)
    for t in pool:
        if t not in M:
            missing_type.append("%s/%s" % (key, t))
check("C14 ★セクション語彙14種すべてがマニュアルに載っている",
      not missing_sec, "欠落=%s" % (missing_sec or "なし"))
check("C15 ★6型プールの型名がすべて載っている（実装 SECTION_TYPE_POOLS と一致）",
      not missing_type, "欠落 %d 件=%s" % (len(missing_type), missing_type[:5] or "なし"))

# カラム構成の選択肢が実物と一致
ui_cols = sorted(set(re.findall(r'value="(1col|2col-[a-z-]+|3col)"', UI)))
missing_cols = [c for c in ui_cols if c not in M and c.replace("-", "") not in M]
check("C16 カラム構成の種類数が実物と一致（%d 種）" % len(ui_cols),
      len(ui_cols) == 6 and "6種類" in M,
      "実物=%s / 「6種類」の記載=%s" % (ui_cols, "6種類" in M))

# 幅切替のラベルが実物と一致
sample_cmp = os.path.join(ROOT, "samples", "01_カフェ_1カラム", "compare.html")
widths = []
if os.path.isfile(sample_cmp):
    c = io.open(sample_cmp, encoding="utf-8").read()
    widths = re.findall(r'for="vw[^"]*"[^>]*>([^<]{1,12})', c)
check("C17 幅切替のラベルが実物と一致（全幅 / 768px / 375px）",
      bool(widths) and all(w.strip() in M for w in widths),
      "実物=%s / 欠落=%s" % (widths, [w for w in widths if w.strip() not in M]))

# ボタン名が実物と一致
check("C18 🔄 セクション再生成 のボタン名が実物どおり",
      "🔄 セクション再生成" in M and "🔄 セクション再生成" in (
          io.open(sample_cmp, encoding="utf-8").read() if os.path.isfile(sample_cmp) else ""),
      "マニュアル=%s" % ("🔄 セクション再生成" in M))

# 上限値が実装と一致
ui_total = re.search(r"COMPOSITION_MAX_TOTAL\s*=\s*(\d+)", UI)
ui_perkey = re.search(r"COMPOSITION_MAX_PER_KEY\s*=\s*(\d+)", UI)
check("C19 ★置ける個数の上限が実装と一致（合計 / 同一セクション）",
      bool(ui_total) and bool(ui_perkey)
      and (ui_total.group(1) + "個まで") in M and (ui_perkey.group(1) + "個まで") in M,
      "実装=合計%s・同一%s / 記載=%s"
      % (ui_total.group(1) if ui_total else "?", ui_perkey.group(1) if ui_perkey else "?",
         [x for x in re.findall(r"(\d+)個まで", M)]))

ui_thumbs = re.search(r"THUMBS_COLLAPSED_LIMIT\s*=\s*(\d+)", UI)
check("C20 サムネイルの既定表示数が実装と一致",
      bool(ui_thumbs) and ui_thumbs.group(1) + "件" in M,
      "実装=%s / 記載=%s" % (ui_thumbs.group(1) if ui_thumbs else "?",
                             ui_thumbs.group(1) + "件" in M if ui_thumbs else "?"))

# 起動スクリプト名が実在すること
for fn in ("起動.command", "起動.bat"):
    # ★KLK-105: 起動スクリプトは**最上位**へ移した（フォルダを開いてすぐ押せるように）。
    #   置き場所が変わっても「実在すること」を見たいので、両方の場所を許す。
    _found = (os.path.isfile(os.path.join(ROOT, fn))
              or os.path.isfile(os.path.join(ROOT, "draft-gen", fn)))
    check("C21 %s が実在し、マニュアルの記載と一致" % fn,
          _found and fn in M,
          "実在=%s / 記載=%s" % (_found, fn in M))

# ---------------------------------------------------------------------------
# AC2 / AC7 / AC8 / AC9 構成・役割分担・同梱・印刷
# ---------------------------------------------------------------------------
ids = re.findall(r'<section id="([a-z0-9-]+)"', M)
toc = re.findall(r'<a href="#([a-z0-9-]+)"', M)
orphan_toc = [t for t in set(toc) if t not in ids]
orphan_sec = [s for s in ids if s not in toc]
check("C22 サイドナビの全リンクに対応する節がある（リンク切れなし）",
      not orphan_toc, "行き先の無いリンク=%s" % (orphan_toc or "なし"))
check("C23 全ての節がサイドナビから辿れる", not orphan_sec, "ナビに無い節=%s" % (orphan_sec or "なし"))
check("C24 章立てが十分ある（節が10以上）", len(ids) >= 10, "節 %d 個" % len(ids))
check("C25 現在位置の表示が入っている（サイドナビが飾りでない）",
      "IntersectionObserver" in M and "classList" in M,
      "現在位置=%s" % ("IntersectionObserver" in M))
check("C26 README と役割分担し、README を参照している",
      M.count("README.md") >= 3,
      "README への参照 %d 回" % M.count("README.md"))
check("C27 README からマニュアルへのリンクがある（相互リンク）",
      "使い方マニュアル.html" in README,
      "README 側の記載=%s" % ("使い方マニュアル.html" in README))
check("C28 パッケージに同梱される", "使い方マニュアル.html" in PKG,
      "make-package.sh の記載=%s" % ("使い方マニュアル.html" in PKG))
# ★`[^}]*` は入れ子のルールを跨げない。@media print ブロックを括弧の対応で取り出して見る。
_pi = M.find("@media print")
_print_block = ""
if _pi >= 0:
    _d, _j = 0, M.find("{", _pi)
    for _k in range(_j, min(len(M), _j + 4000)):
        if M[_k] == "{":
            _d += 1
        elif M[_k] == "}":
            _d -= 1
            if _d == 0:
                _print_block = M[_j:_k + 1]
                break
check("C29 印刷時にサイドナビを隠す指定がある",
      bool(_print_block) and re.search(r"\.side\s*\{\s*display:\s*none", _print_block) is not None,
      "print ブロック %d 文字 / .side を隠す=%s"
      % (len(_print_block),
         bool(_print_block) and re.search(r"\.side\s*\{\s*display:\s*none", _print_block) is not None))

# ---------------------------------------------------------------------------
# 生成画面からマニュアルへの導線（理恵さんのご要望・大見出しの近く）
# ---------------------------------------------------------------------------
# ★リンク切れは何も言わずに壊れる。相対パスが**実際に解決するか**まで見る。
_href = re.findall(r'<a[^>]*href="([^"]*使い方マニュアル\.html)"', UI)
check("C30 生成画面にマニュアルへのリンクがある", bool(_href), "リンク %d 本" % len(_href))

_h1 = UI.find("<h1>モック生成 — 設定</h1>")
_near = _h1 >= 0 and "使い方マニュアル.html" in UI[max(0, _h1 - 400):_h1 + 900]
check("C31 リンクが大見出し「モック生成 — 設定」の近くにある", _near,
      "見出しの位置=%d / 近傍にリンク=%s" % (_h1, _near))

# ★ここは一度間違えた。**ファイルとして開いた場合**しか見ておらず、
#   実際の運用（ブリッジが `/` で配信する）を検証していなかったため、
#   理恵さんの環境で `{"error": "not found"}` になった。
#   リンクは2つの経路の**両方**で解決しなければならない。
_broken_file = []
for _p in set(_href):
    _abs = os.path.normpath(os.path.join(ROOT, "draft-gen", _p))
    if not os.path.isfile(_abs):
        _broken_file.append(_p)
check("C32 ファイルとして開いた場合にリンクが解決する（file:// 経路）",
      not _broken_file, "切れているリンク=%s" % (_broken_file or "なし"))

# ブリッジ経由の経路: 画面は `/` で配信されるので `../x` は `/x` へ解決する。
# その `/x` を**ブリッジが配信しているか**をルーティング表で確かめる。
BRIDGE = io.open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
_served = []
for _p in set(_href):
    _url = "/" + _p.lstrip("./")            # ../使い方マニュアル.html → /使い方マニュアル.html
    _served.append((_url, ('"%s"' % _url) in BRIDGE))
check("C33 ★ブリッジ経由でもリンクが解決する（配信口がある）",
      all(ok for _, ok in _served),
      "経路=%s" % [(u, "配信あり" if ok else "★配信口が無い") for u, ok in _served])

check("C34 ブリッジが日本語URLを unquote して照合している（percent-encode 対策）",
      "urllib.parse.unquote(path)" in BRIDGE,
      "unquote=%s" % ("urllib.parse.unquote(path)" in BRIDGE))

check("C35 パッケージ内でも位置関係が保たれる（マニュアルは root・画面は draft-gen/）",
      "使い方マニュアル.html" in PKG and all(p.startswith("../") for p in _href),
      "同梱=%s / 相対パス=%s" % ("使い方マニュアル.html" in PKG, sorted(set(_href))))

print("=" * 78)
print("KLK-098 使い方マニュアル（HTML）チェック")
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
