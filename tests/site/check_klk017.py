#!/usr/bin/env python3
"""
KLK-017 acceptance-condition checker (static / no browser required).

docs/designs/KLK-017.md §9 の受け入れ条件（静的検査可能分）を draft-gen/index.html
に対して検証する。SCR-001 参考画像ピッカーの実績カタログ接続（REQ-004）の受け入れ:
  - 実データ接続（/catalog.json fetch・/catalog/img/ 参照）
  - 絞り込み #thumbFilter のハンドラ登録・業種の先頭トークン処理
  - S13/S9 温存（画像タグ・リテラル不在・thumbnails: キー・class="thumb"/data-id=）
  - 機密（REQ-011: 実カタログ実タイトルが器に焼き込まれていない）
  - NFR-005（新規の外部URL/CDN 混入なし・画像/JSONは相対同一オリジン）
  - フォールバック案内文・KLK-014 S5（HTML一括代入 .innerHTML 非導入）温存

供給側（catalog.html / bridge.py / catalog.json）は参照のみで変更しない。
check_klk006（S9/S13 含む全 check_klk*）は無改訂で全通すること（本チェッカは独立）。

Run: python3 tests/site/check_klk017.py
Exit code 0 = all static checks pass, 1 = at least one fail.
Python3 標準ライブラリのみ・ネットワーク非使用。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML_PATH = os.path.join(ROOT, "draft-gen", "index.html")
HTML = open(HTML_PATH, encoding="utf-8").read()

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ===========================================================================
# T1 実データ接続 (/catalog.json fetch ・ /catalog/img/ 画像参照)
# ===========================================================================
has_catalog_fetch = bool(re.search(r"fetch\(\s*'/catalog\.json'", HTML)) or "'/catalog.json'" in HTML
has_img_ref = "'/catalog/img/'" in HTML or "/catalog/img/" in HTML
# 画像は相対・同一オリジン（絶対 http(s)://…/catalog/img は使わない）
no_abs_img = re.search(r"https?://[^\s\"'()]*catalog/img", HTML) is None
check(
    "T1 実データ接続 (/catalog.json fetch ・ /catalog/img/ 参照が相対・同一オリジンで存在)",
    has_catalog_fetch and has_img_ref and no_abs_img,
    f"/catalog.json fetch={has_catalog_fetch}, /catalog/img/参照={has_img_ref}, 絶対URL画像無={no_abs_img}",
)

# ===========================================================================
# T2 絞り込み #thumbFilter 結線 ＋ 業種先頭トークン処理
# ===========================================================================
thumbfilter_handler = bool(re.search(
    r"getElementById\(\s*'thumbFilter'\s*\)\s*\.addEventListener", HTML))
# KLK-059: 業種写像の契約を更新。
# 旧契約は「split('(' で先頭トークンを取り出し双方向前方一致」だったが、これは SCR-001 の語彙が
# カタログ canonical と乖離していた時代の吸収策であり、業種13種中8種で一致に失敗していた（設計 §2）。
# 新契約は「一覧選択＝canonical 完全一致 / 自由入力＝従来の双方向前方一致でフォールバック」。
# 語彙そのものの四者一致は check_klk059.py が検証する。ここでは結線と分岐の存在のみを見る。
exact_match = bool(re.search(r"if\s*\(\s*!isCustom\s*\)\s*return\s+a\s*===\s*key", HTML))
is_custom_branch = "function isCustomIndustry" in HTML and "matchesIndustry(e, key, isCustom)" in HTML
# 自由入力フォールバック（双方向前方一致）の痕跡は維持されていること
bidirectional = "indexOf(key)" in HTML and "indexOf(a)" in HTML
# 旧実装が残っていないこと（退行防止）
no_legacy = "industryKey" not in HTML
check(
    "T2 絞り込み結線＋業種写像 (thumbFilter に addEventListener・canonical 完全一致・自由入力は前方一致・industryKey 廃止)",
    thumbfilter_handler and exact_match and is_custom_branch and bidirectional and no_legacy,
    f"thumbFilterハンドラ={thumbfilter_handler}, canonical完全一致={exact_match}, "
    f"自由入力分岐={is_custom_branch}, 前方一致フォールバック={bidirectional}, industryKey廃止={no_legacy}",
)

# ===========================================================================
# T3 S13/S9 温存 (画像タグ・リテラル不在・thumbnails:・class=\"thumb\"/data-id=)
# ===========================================================================
no_img = re.search(r"<img\b", HTML, re.I) is None
has_thumbnails_key = "thumbnails:" in HTML
has_thumb_literal = 'class="thumb"' in HTML and "data-id=" in HTML
placeholder_grad = ".thumb .ph" in HTML and bool(re.search(r"\.ph\s*\{[^}]*linear-gradient", HTML, re.S))
count_label = 'id="thumbCount"' in HTML and "/ 3枚" in HTML
max3_logic = bool(re.search(r"\.thumb\.selected'?\)?\.length\s*>=\s*3", HTML)) or ">= 3" in HTML
# 実画像は createElement で後付け（器に画像タグを書かない）
img_created = "createElement('img')" in HTML
check(
    "T3 S13/S9温存 (画像タグ・リテラル無・thumbnails:キー・class=\"thumb\"/data-id=・.phグラデ・/3枚・最大3・createElement('img'))",
    (no_img and has_thumbnails_key and has_thumb_literal and placeholder_grad
     and count_label and max3_logic and img_created),
    f"画像タグ無={no_img}, thumbnails:={has_thumbnails_key}, thumb/data-id={has_thumb_literal}, "
    f".phグラデ={placeholder_grad}, /3枚={count_label}, 最大3={max3_logic}, createElement('img')={img_created}",
)

# ===========================================================================
# T4 契約写像 (selectedThumbs が id/label/tags を返し・tags を JSON.parse で配列化)
# ===========================================================================
sel_body_i = HTML.find("function selectedThumbs()")
sel_body = HTML[sel_body_i:sel_body_i + 500] if sel_body_i >= 0 else ""
sel_keys = ("id:" in sel_body and "label:" in sel_body and "tags:" in sel_body)
tags_parsed = "JSON.parse(el.dataset.tags" in sel_body
# 写像元: id=e.id, label=e.title（cardHtml の data-label に e.title を載せる）
maps_title = "data-label=" in HTML and "esc(e.title)" in HTML
check(
    "T4 契約写像 (selectedThumbs が {id,label,tags}・tags を JSON.parse で配列化・label=e.title 写像)",
    sel_keys and tags_parsed and maps_title,
    f"{{id,label,tags}}={sel_keys}, tags JSON.parse={tags_parsed}, label=e.title={maps_title}",
)

# ===========================================================================
# T5 機密 (REQ-011: 実カタログ実タイトルが器に焼き込まれていない)
# ===========================================================================
SECRET_TITLES = ["アミュール", "大村クリニック", "日原果樹園", "日原", "ひはら",
                 "オーダージュエリー", "CADスクール", "tamonten"]
leaked = [t for t in SECRET_TITLES if t in HTML]
check(
    "T5 機密 (実カタログのタイトル・実案件名が index.html に焼き込まれていない・同一オリジン fetch のみ)",
    not leaked,
    f"焼き込み検出={leaked or 'なし'}",
)

# ===========================================================================
# T6 フォールバック案内文 (非稼働/file:///空カタログで案内・生成はブロックしない)
# ===========================================================================
guide_text = "ブリッジを起動すると実績カタログから参考を選べます" in HTML
# 稼働判定に file: 非稼働ルール（location.protocol!=='file:')
file_guard = bool(re.search(r"location\.protocol\s*!==\s*'file:'", HTML))
check(
    "T6 フォールバック (非稼働/file:// 案内文・location.protocol!=='file:' の稼働判定)",
    guide_text and file_guard,
    f"案内文={guide_text}, file:非稼働判定={file_guard}",
)

# ===========================================================================
# T7 NFR-005 / KLK-014 温存 (新規外部URL無・.innerHTML 一括代入 非導入)
# ===========================================================================
_ALLOW_HOSTS = ("www.w3.org", "example.com", "example.org", "example.net")


def _host(url):
    m = re.match(r"https?://([^/\s\"')]+)", url)
    return m.group(1).lower() if m else ""


ext_urls = [m for m in re.findall(r'https?://[^\s"\')（]+', HTML)
            if _host(m) not in _ALLOW_HOSTS]
no_innerhtml = ".innerHTML" not in HTML   # KLK-014 S5（HTML一括代入の注入対策）を温存
uses_insert = "insertAdjacentHTML" in HTML
check(
    "T7 NFR-005/KLK-014温存 (外部URL 0件[w3.org/example.* 除外]・.innerHTML 一括代入 非導入・insertAdjacentHTML 使用)",
    (not ext_urls) and no_innerhtml and uses_insert,
    f"外部URL={ext_urls or 0}, .innerHTML非導入={no_innerhtml}, insertAdjacentHTML={uses_insert}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-017 static acceptance checks (docs/designs/KLK-017.md §9 を正とする)")
print("=" * 78)
failed = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print(f"[{status}] {name}")
    print(f"        {detail}")
print("-" * 78)
print(f"{len(results)} checks, {failed} failed")
print()
print("M群（環境制約で静的検証外 = tester/人間がブラウザ実機で手動確認しログへ記録）:")
print("  - MA ブリッジ稼働時: #thumbs が /catalog.json entries を実画像付きで描画")
print("  - MB 参考2枚選択→生成で references.thumbnails に {id,label,tags} が載る（tags は配列）")
print("  - MC #thumbFilter 3択・業種連動（KLK-059: canonical 完全一致。例「クリニック・病院・介護リハビリ」→2件。")
print("        実績0件の canonical を選ぶと全表示＋注記へフォールバック）が効く")
print("  - MD 拡大モーダルが稼働時 /catalog/img/{file} の実画像・非稼働はプレースホルダ")
print("  - ME 非稼働/file:// で空＋案内文・生成はブロックしない")
sys.exit(1 if failed else 0)
