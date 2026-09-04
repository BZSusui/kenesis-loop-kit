#!/usr/bin/env python3
"""
KLK-083 acceptance-condition checker (static / no browser required).

見本サイトURL（REQ-102）から**配色だけ**を機械的に読み取る機能。

★このチェッカーが守っているもの:
  ① **SSRF** — これはブリッジが**初めて外へ出る**機能。ブリッジは利用者の端末で動くので、
     `http://127.0.0.1:…` や `http://192.168.x.x/` を読ませると
     **社内ネットワークを覗く踏み台**になる。ここが壊れたら実害が出る。
  ② **AI を通さない決定性** — 同じページなら同じ結果になること。
     生成パイプラインに触れないこと（配色欄に値が入るだけ）。
  ③ **UI が嘘をつかない** — 読み取るのは配色だけで構成は読まない、と正確に書くこと。

  X群 = hex→16カテゴリ（§5.1 の実データで往復）
  S群 = SSRF ガード
  C群 = 色の抽出と役割の下書き
  B群 = ブリッジへの配線 / U群 = UI / R群 = SPEC

★このチェッカーは**第三者サイトへ一切アクセスしない**（純関数と差し替え可能な fetcher のみ）。

Run: python3 tests/site/check_klk083.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

BRIDGE_SRC = io.open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
INDEX = io.open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
SPEC = io.open(os.path.join(ROOT, "docs", "SPEC.md"), encoding="utf-8").read()
RULES = io.open(
    os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md"),
    encoding="utf-8",
).read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ===========================================================================
# X群 — hex → 16カテゴリ（§5.1 の実データで往復させる）
# ===========================================================================
_seg = RULES[RULES.index("### 5.1 参考配色の16カテゴリ"):]
_seg = _seg[:_seg.index("## 6.")]
PAIRS = [(m.group(1).strip(), m.group(2).lower())
         for m in re.finditer(r"^\|\s*([^\|]+?)\s*\|\s*`(#[0-9A-Fa-f]{6})`", _seg, re.M)]
mismatch = [(c, h, bridge.hex_to_category(h)) for c, h in PAIRS if bridge.hex_to_category(h) != c]
check(
    "X1 §5.1 の変換表の色が、すべて自分のカテゴリへ戻る（境界が表と揃っている）",
    len(PAIRS) >= 15 and not mismatch,
    "%d色 / ずれ=%s" % (len(PAIRS), mismatch or "なし"),
)
check(
    "X2 白・黒・薄いグレーが妥当に分類される",
    bridge.hex_to_category("#ffffff") == "モノトーン"
    and bridge.hex_to_category("#000000") == "モノトーン"
    and bridge.hex_to_category("#c0c0c0") == "シルバー",
    "白=%s / 黒=%s / 銀=%s"
    % (bridge.hex_to_category("#ffffff"), bridge.hex_to_category("#000000"),
       bridge.hex_to_category("#c0c0c0")),
)
check(
    "X3 不正な入力では None を返す（でっち上げない）",
    bridge.hex_to_category("") is None and bridge.hex_to_category(None) is None
    and bridge.hex_to_category("#GGGGGG") is None,
    "空=%s / None=%s" % (bridge.hex_to_category(""), bridge.hex_to_category(None)),
)

# ===========================================================================
# S群 — SSRF ガード
# ===========================================================================
BAD_URLS = [
    "file:///etc/passwd", "ftp://example.com/", "javascript:alert(1)",
    "http://u:p@example.com/", "https://user@example.com/", "", None, 123,
    "http:///nohost", "x" * 3000,
]
leaked = [u for u in BAD_URLS if bridge.is_safe_external_url(u)]
check(
    "S1 危険・不正な URL 形式を通さない（http/https のみ・資格情報つき不可）",
    not leaked,
    "通ってしまった=%s" % (leaked or "なし"),
)
check(
    "S2 正当な URL は通す",
    bridge.is_safe_external_url("http://example.com/")
    and bridge.is_safe_external_url("https://example.com/a/b?c=d#e"),
    "http=%s / https=%s"
    % (bridge.is_safe_external_url("http://example.com/"),
       bridge.is_safe_external_url("https://example.com/a/b?c=d#e")),
)

INTERNAL = ["127.0.0.1", "0.0.0.0", "10.0.0.1", "172.16.0.1", "192.168.1.1",
            "169.254.169.254", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1",
            "224.0.0.1", "240.0.0.1"]
passed_internal = [a for a in INTERNAL if bridge.is_public_ip(a)]
check(
    "S3 内部アドレスを拒否する（ループバック/プライベート/リンクローカル/予約/マルチキャスト）",
    not passed_internal,
    "通ってしまった=%s" % (passed_internal or "なし"),
)
check(
    "S4 クラウドのメタデータアドレス(169.254.169.254)を拒否する",
    not bridge.is_public_ip("169.254.169.254"),
    "拒否=%s" % (not bridge.is_public_ip("169.254.169.254")),
)
check(
    "S5 公開アドレスは通す（ガードが厳しすぎて何も読めない、にしない）",
    bridge.is_public_ip("8.8.8.8") and bridge.is_public_ip("2001:4860:4860::8888"),
    "v4=%s / v6=%s"
    % (bridge.is_public_ip("8.8.8.8"), bridge.is_public_ip("2001:4860:4860::8888")),
)
check(
    "S6 リダイレクトを自前で追い、毎ホップ検査する（自動追従に任せない）",
    "_NoRedirect" in BRIDGE_SRC
    and "各ホップで必ず再検査する" in BRIDGE_SRC
    and "READ_COLORS_MAX_REDIRECTS" in BRIDGE_SRC,
    "自前追従=%s / 説明=%s"
    % ("_NoRedirect" in BRIDGE_SRC, "各ホップで必ず再検査する" in BRIDGE_SRC),
)
check(
    "S7 名前解決の全レコードが公開アドレスであることを要求する（片方だけ内部を拒否）",
    "all(is_public_ip(a) for a in addrs)" in BRIDGE_SRC,
    "全件検査=%s" % ("all(is_public_ip(a) for a in addrs)" in BRIDGE_SRC),
)
check(
    "S8 取得サイズ・時間・CSS本数に上限がある",
    all(k in BRIDGE_SRC for k in
        ("READ_COLORS_MAX_BYTES", "READ_COLORS_TIMEOUT_SEC", "READ_COLORS_MAX_CSS")),
    "上限の定義=%s" % all(k in BRIDGE_SRC for k in
                        ("READ_COLORS_MAX_BYTES", "READ_COLORS_TIMEOUT_SEC", "READ_COLORS_MAX_CSS")),
)

# ===========================================================================
# C群 — 色の抽出・順位づけ・役割の下書き（fetcher を差し替え＝外へ出ない）
# ===========================================================================
HTML = """<!doctype html><html><head>
<style>
  body{ background:#f7f5f0; color:#333333; }
  .btn{ background:#2e7d6b; border:1px solid #2e7d6b; color:#fff; }
  .accent{ color:#e8a33d; }
  .hero{ background:rgb(46,125,107); }
  .sub{ color:#8fb9ae; }
  /* #ff0000 はコメントなので数えない */
</style>
<link rel="stylesheet" href="/css/site.css">
<link rel="stylesheet" href="https://other.example.net/x.css">
</head><body style="background:#f7f5f0"></body></html>"""
CSS = ".a{color:#2e7d6b}.b{color:#e8a33d}.c{color:#f7f5f0}.d{color:#8fb9ae}"
BASE = "https://sample.example.com/"
_fetched = []


def fake_fetch(url, **kw):
    _fetched.append(url)
    if url.endswith("/css/site.css"):
        return CSS, None
    if url.startswith("https://other.example.net"):
        return "SHOULD-NOT-BE-FETCHED", None
    return HTML, None


check(
    "C1 色の指定を正規化する（#rgb / #rrggbb / rgb() / rgba()）",
    bridge.normalize_color_value("#ABC") == "#aabbcc"
    and bridge.normalize_color_value("#2E7D6B") == "#2e7d6b"
    and bridge.normalize_color_value("rgb(46,125,107)") == "#2e7d6b"
    and bridge.normalize_color_value("rgba(46, 125, 107, .5)") == "#2e7d6b"
    and bridge.normalize_color_value("red") is None
    and bridge.normalize_color_value("rgb(300,0,0)") is None,
    "#ABC=%s / rgb=%s / 色名=%s"
    % (bridge.normalize_color_value("#ABC"), bridge.normalize_color_value("rgb(46,125,107)"),
       bridge.normalize_color_value("red")),
)
check(
    "C2 CSS コメント内の色は数えない",
    "#ff0000" not in bridge.collect_page_colors(HTML),
    "コメント内の色=%s" % ("#ff0000" in bridge.collect_page_colors(HTML)),
)
_same = bridge.same_origin_css_urls(HTML, BASE)
check(
    "C3 同一オリジンのCSSだけを対象にする（1つのURL入力で他所を巡回しない）",
    _same == ["https://sample.example.com/css/site.css"],
    "対象=%s" % _same,
)

_res = bridge.read_site_colors(BASE, fetcher=fake_fetch)
check(
    "C4 別オリジンのCSSを取りに行っていない",
    not any(u.startswith("https://other.example.net") for u in _fetched),
    "取得したURL=%s" % _fetched,
)
check(
    "C5 頻度順にスウォッチを返し、カテゴリを添える",
    _res["ok"] and _res["colors"] and _res["colors"][0]["hex"] == "#2e7d6b"
    and _res["colors"][0]["category"] == "グリーン"
    and all(0 <= c["ratio"] <= 1 for c in _res["colors"]),
    "先頭=%s" % (_res["colors"][0] if _res["colors"] else None),
)
check(
    "C6 役割の下書きが妥当（メイン=最頻の有彩色 / 背景=明るい色 / アクセント=色相の遠い色）",
    _res["suggestion"] == {"main": "#2e7d6b", "sub": "#8fb9ae",
                           "accent": "#e8a33d", "bg": "#f7f5f0"},
    "下書き=%s" % _res["suggestion"],
)
check(
    "C7 同じ入力なら同じ結果（決定的・AI を通さない）",
    bridge.read_site_colors(BASE, fetcher=fake_fetch) == _res,
    "2回目が一致=%s" % (bridge.read_site_colors(BASE, fetcher=fake_fetch) == _res),
)

_empty = bridge.read_site_colors(BASE, fetcher=lambda u, **k: ("<html><body>x</body></html>", None))
check(
    "C8 色が拾えないとき黙らず理由を返す（JS 描画サイトなど）",
    (not _empty["ok"]) and "JavaScript" in (_empty["error"] or ""),
    "error=%s" % _empty["error"],
)
_err = bridge.read_site_colors(BASE, fetcher=lambda u, **k: (None, "取得できませんでした（X）"))
check(
    "C9 取得失敗をそのまま伝える",
    (not _err["ok"]) and _err["error"],
    "error=%s" % _err["error"],
)
check(
    "C10 役割が埋まらないときは None のまま（適当な色をでっち上げない）",
    bridge.suggest_color_roles([]) == {"main": None, "sub": None, "accent": None, "bg": None},
    "空入力=%s" % bridge.suggest_color_roles([]),
)

# ===========================================================================
# B群 — ブリッジへの配線
# ===========================================================================
check(
    "B1 POST /read-colors が生えている",
    'if path == "/read-colors":' in BRIDGE_SRC and "def _read_colors(self):" in BRIDGE_SRC,
    "配線=%s" % ('if path == "/read-colors":' in BRIDGE_SRC),
)
check(
    "B2 既存と同じ防御の並び（Origin → サイズ → JSON → URL）",
    all(t in BRIDGE_SRC.split("def _read_colors(self):")[1].split("def _sections")[0]
        for t in ("is_allowed_origin", "MAX_BODY_BYTES", "json.loads", "is_safe_external_url")),
    "防御=%s" % all(t in BRIDGE_SRC.split("def _read_colors(self):")[1].split("def _sections")[0]
                   for t in ("is_allowed_origin", "MAX_BODY_BYTES", "json.loads",
                             "is_safe_external_url")),
)
check(
    "B3 取得内容を保存しない（読むだけ）",
    "取得内容は保存しない" in BRIDGE_SRC,
    "明記=%s" % ("取得内容は保存しない" in BRIDGE_SRC),
)
check(
    "B4 生成パイプラインに触れていない（build_claude_command 等に URL が混ざらない）",
    "read_site_colors" not in BRIDGE_SRC.split("def build_claude_command")[1].split("\ndef ")[0],
    "生成コマンドへの混入=なし",
)

# ===========================================================================
# U群 — UI
# ===========================================================================
_i = INDEX.find("見本サイトのURL")
SEG_URL = INDEX[_i - 300:_i + 1800] if _i >= 0 else ""
check(
    "U1 「配色を読み取る」ボタンとスウォッチ表示がある",
    all(t in INDEX for t in ("readColorsBtn", "readColorsSwatches", "readColorsApply")),
    "要素=%s" % all(t in INDEX for t in ("readColorsBtn", "readColorsSwatches", "readColorsApply")),
)
check(
    "U2 UI が読み取る範囲を正確に書いている（配色だけ・構成は読まない・代替の案内）",
    "配色だけ" in SEG_URL and "レイアウト構成は読み取りません" in SEG_URL
    and "スクリーンショット" in SEG_URL and "対応予定" not in SEG_URL,
    "配色だけ=%s / 構成は読まない=%s / 代替=%s / 旧注記の残存=%s"
    % ("配色だけ" in SEG_URL, "レイアウト構成は読み取りません" in SEG_URL,
       "スクリーンショット" in SEG_URL, "対応予定" in SEG_URL),
)
check(
    "U3 既存の配色欄へ合流する（貼り付け取り込みと同じ setColorRole 経路）",
    "readColorsApply" in INDEX and "setColorRole(k, sug[k])" in INDEX,
    "合流=%s" % ("setColorRole(k, sug[k])" in INDEX),
)
check(
    "U4 動的値を textContent で描画する（注入対策）",
    "b.textContent = c.hex" in INDEX,
    "textContent=%s" % ("b.textContent = c.hex" in INDEX),
)
check(
    "U5 ブリッジ未起動でも案内を出す（黙って失敗しない）",
    "ローカルブリッジに接続できませんでした" in INDEX,
    "案内=%s" % ("ローカルブリッジに接続できませんでした" in INDEX),
)

# ===========================================================================
# R群 — SPEC
# ===========================================================================
_r = SPEC[SPEC.index("| REQ-102 |"):]
REQ102 = _r[:_r.index("\n")]
check(
    "R1 SPEC REQ-102 が実装済みと、読み取る範囲を書いている",
    "配色の読み取りを実装済み" in REQ102 and "読み取らない" in REQ102,
    "実装済み=%s / 範囲=%s"
    % ("配色の読み取りを実装済み" in REQ102, "読み取らない" in REQ102),
)
check(
    "R2 SPEC が SSRF ガードを規定している",
    "SSRF" in REQ102 and "リダイレクト先も毎ホップ再検査" in REQ102,
    "SSRF=%s" % ("SSRF" in REQ102),
)
check(
    "R3 外部アクセスの可否が AI利用管理責任者の確認事項だと記録されている",
    "AI利用管理責任者" in SPEC,
    "記録=%s" % ("AI利用管理責任者" in SPEC),
)

# ===========================================================================
# O群 — Origin 判定（KLK-084・理恵さんの実機で 403 になった不具合）
# ===========================================================================
_H = bridge.BRIDGE_HOST
_ok = [("http://127.0.0.1:8765", 8765), ("http://localhost:8765", 8765),
       ("http://[::1]:8765", 8765), ("http://127.0.0.2:8765", 8765),
       ("http://localhost:9999", 9999), (None, 8765), ("null", 8765)]
_ng = [("http://evil.example", 8765), ("http://evil.example/", 8765),
       ("http://127.0.0.1:9999", 8765), ("https://127.0.0.1:8765", 8765),
       ("", 8765), ("http://192.168.1.5:8765", 8765),
       ("http://127.0.0.1:8765/", 8765), ("http://[::1]:9999", 8765)]
_bad_ok = [o for o, pt in _ok if bridge.is_allowed_origin(o, _H, pt) is not True]
_bad_ng = [o for o, pt in _ng if bridge.is_allowed_origin(o, _H, pt) is not False]
check(
    "O1 同じ端末のブリッジからの呼び出しを、綴りが違っても許可する（127.0.0.1 / localhost / [::1]）",
    not _bad_ok,
    "拒否されてしまった=%s" % (_bad_ok or "なし"),
)
check(
    "O2 別オリジン・別ポート・https・LAN内の別端末は拒否する",
    not _bad_ng,
    "通ってしまった=%s" % (_bad_ng or "なし"),
)
check(
    "O3 ループバック判定で見ている（文字列の完全一致に戻していない）",
    "is_loopback" in BRIDGE_SRC.split("def is_allowed_origin")[1].split("\ndef ")[0],
    "ループバック判定=%s"
    % ("is_loopback" in BRIDGE_SRC.split("def is_allowed_origin")[1].split("\ndef ")[0]),
)
check(
    "O4 403 の本文に受け取った Origin を添える（原因がその場で分かる）",
    "許可されていないオリジンです（受信:" in BRIDGE_SRC,
    "Origin の提示=%s" % ("許可されていないオリジンです（受信:" in BRIDGE_SRC),
)

print("=" * 78)
print("KLK-083 見本サイトURLからの配色読み取り 静的チェック")
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
