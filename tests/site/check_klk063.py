#!/usr/bin/env python3
"""
KLK-063 acceptance-condition checker (static + 純関数の実行 / no browser required).

Verifies U1-U14 from docs/designs/KLK-063.md §4.4 / §9:
SCR-004 のドロップゾーンを実働化し、ブラウザから catalog/.pending/ へ画像を追加できるようにした変更。

  縦串 ブリッジ  draft-gen/bridge.py     （sniff_catalog_image_ext / _catalog_upload / _catalog_pending）
  縦串 SCR-004   draft-gen/catalog.html  （D&D・ファイル選択・health-gate）
  縦串 仕様      docs/SPEC.md            （REQ-106）

`sniff_catalog_image_ext` は **bridge を import して実関数を実行**して検証する
（check_klk020 S11 と同方式）。ネットワークは使用しない。

★最重要の非回帰: `/upload`（MV写真・REQ-104/KLK-020）は JPEG/PNG 限定のまま。
  `sniff_image_ext` は**変更してはならない**（U2 で WebP を受け付けないままであることを検証）。

Run: python3 tests/site/check_klk063.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_SRC = open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
CATHTML = open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()
SPEC = open(os.path.join(ROOT, "docs", "SPEC.md"), encoding="utf-8").read()

sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402  (純関数の機能検証に使用)

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# U1-U2 マジックバイト判定（純関数を実行）
# ---------------------------------------------------------------------------
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 12
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
WEBP = b"RIFF" + struct.pack("<I", 20) + b"WEBP" + b"VP8 "
GIF = b"GIF89a" + b"\x00" * 10
HTML_BYTES = b"<html><body>x</body></html>"

sniff_cat = getattr(bridge, "sniff_catalog_image_ext", None)
if sniff_cat is None:
    check("U1 sniff_catalog_image_ext が JPEG/PNG/WebP を判定し非画像に None を返す", False,
          "sniff_catalog_image_ext が定義されていない")
else:
    cases = [
        (JPEG, ".jpg"), (PNG, ".png"), (WEBP, ".webp"),
        (GIF, None), (HTML_BYTES, None), (b"", None), (b"RIFF", None),
        # RIFF だが WEBP でない（AVI 等）→ 受け付けない
        (b"RIFF" + struct.pack("<I", 20) + b"AVI ", None),
        ("文字列", None), (None, None),
    ]
    bad = []
    for data, want in cases:
        got = sniff_cat(data)
        if got != want:
            bad.append((repr(data)[:22], want, got))
    check("U1 sniff_catalog_image_ext が JPEG/PNG/WebP を判定し非画像に None を返す",
          not bad, "不一致=%s" % (bad or "なし（10ケース一致）"))

sniff_mv = getattr(bridge, "sniff_image_ext", None)
check(
    "U2 既存 sniff_image_ext（MV写真用）は WebP を受け付けないまま（REQ-104 の非回帰）",
    sniff_mv is not None and sniff_mv(WEBP) is None
    and sniff_mv(JPEG) == ".jpg" and sniff_mv(PNG) == ".png",
    "WebP=%r / JPEG=%r / PNG=%r" % (sniff_mv(WEBP), sniff_mv(JPEG), sniff_mv(PNG)) if sniff_mv else "未定義",
)

# ---------------------------------------------------------------------------
# U3-U7 ブリッジ（ルーティング・防御順・保存先）
# ---------------------------------------------------------------------------
check(
    "U3 POST /catalog-upload のルーティングがある",
    'path == "/catalog-upload"' in BRIDGE_SRC and "self._catalog_upload()" in BRIDGE_SRC,
    "ルート=%s / 呼び出し=%s"
    % ('path == "/catalog-upload"' in BRIDGE_SRC, "self._catalog_upload()" in BRIDGE_SRC),
)

_i = BRIDGE_SRC.find("def _catalog_upload")
_FULL = BRIDGE_SRC[_i:BRIDGE_SRC.find("def _pending_names_count")] if _i >= 0 else ""
# docstring には防御順の説明として "413" 等が現れるため、**本体コードだけ**を対象にする
# （docstring を含めると説明文の出現位置で順序判定が狂う）。
_ds_end = _FULL.find('"""', _FULL.find('"""') + 3)
UPBODY = _FULL[_ds_end + 3:] if _ds_end > 0 else _FULL
order = [
    ("is_allowed_origin", UPBODY.find("is_allowed_origin(")),
    ("size-limit(413)", UPBODY.find("> CATALOG_UPLOAD_MAX_BODY_BYTES")),
    ("sniff_catalog_image_ext", UPBODY.find("sniff_catalog_image_ext(raw")),
    ("save(wb)", UPBODY.find('"wb"')),
    ("_json(200", UPBODY.find("_json(200")),
]
positions = [p for _, p in order]
check(
    "U4 _catalog_upload の防御順が Origin(403)→サイズ上限(413/400)→マジックバイト(400)→保存→200 である",
    bool(UPBODY) and all(p >= 0 for p in positions) and positions == sorted(positions),
    "位置=%s" % ({k: v for k, v in order}),
)
check(
    "U5 保存名がサーバ生成（uuid）で、クライアント由来の名前を保存パスに使っていない",
    'saved_name = "pnd-" + uuid.uuid4().hex + ext' in UPBODY
    and "filename" not in UPBODY and "self.headers.get(\"Content-Type\")" not in UPBODY,
    "uuid 生成=%s / filename 参照=%s"
    % ('saved_name = "pnd-" + uuid.uuid4().hex + ext' in UPBODY, "filename" in UPBODY),
)
check(
    "U6 保存先が catalog_pending_dir（catalog/ の外へ書かない・REQ-011）",
    "os.makedirs(catalog_pending_dir" in UPBODY
    and "os.path.join(catalog_pending_dir, saved_name)" in UPBODY,
    "makedirs=%s / join=%s"
    % ("os.makedirs(catalog_pending_dir" in UPBODY,
       "os.path.join(catalog_pending_dir, saved_name)" in UPBODY),
)
check(
    "U7 GET /catalog-pending があり、catalog_import_ext_ok で対象拡張子に絞っている",
    'path == "/catalog-pending"' in BRIDGE_SRC and "def _catalog_pending" in BRIDGE_SRC
    and "catalog_import_ext_ok(n)" in BRIDGE_SRC,
    "ルート=%s / ハンドラ=%s / 絞り込み=%s"
    % ('path == "/catalog-pending"' in BRIDGE_SRC, "def _catalog_pending" in BRIDGE_SRC,
       "catalog_import_ext_ok(n)" in BRIDGE_SRC),
)

# ---------------------------------------------------------------------------
# U8-U13 SCR-004（catalog.html）
# ---------------------------------------------------------------------------
_m = re.search(r'<input type="file" id="pendingFiles"([^>]*)>', CATHTML)
FILE_ATTRS = _m.group(1) if _m else ""
check(
    "U8 SCR-004 に複数選択できるファイル入力があり、accept が jpg/png/webp を含む",
    bool(FILE_ATTRS) and "multiple" in FILE_ATTRS
    and all(x in FILE_ATTRS for x in (".jpg", ".png", ".webp")),
    "属性=%r" % FILE_ATTRS.strip()[:110],
)
check(
    "U9 SCR-004 にドラッグ&ドロップの配線がある（dragover / drop）",
    '"dragover"' in CATHTML and '"drop"' in CATHTML and "dataTransfer" in CATHTML,
    "dragover=%s / drop=%s / dataTransfer=%s"
    % ('"dragover"' in CATHTML, '"drop"' in CATHTML, "dataTransfer" in CATHTML),
)
check(
    "U10 SCR-004 が POST /catalog-upload を呼んでいる",
    '"/catalog-upload"' in CATHTML and 'method: "POST"' in CATHTML,
    "エンドポイント=%s" % ('"/catalog-upload"' in CATHTML),
)
_i = CATHTML.find("function setBridgeState")
STATEBODY = CATHTML[_i:_i + 900] if _i >= 0 else ""
check(
    "U11 ブリッジ未起動時にアップロードが無効化される（health-gate に合流）",
    "input.disabled = !alive" in STATEBODY and "disabled" in STATEBODY
    and "bridgeAlive" in CATHTML and "if (!bridgeAlive)" in CATHTML,
    "setBridgeState で無効化=%s / uploadFiles のガード=%s"
    % ("input.disabled = !alive" in STATEBODY, "if (!bridgeAlive)" in CATHTML),
)
_i = CATHTML.find('class="dropzone"')
DZ = CATHTML[_i:_i + 700] if _i >= 0 else ""
check(
    "U12 ドロップゾーンの文言が D&D とクリック選択の両方を案内し、手動コピーにも触れている",
    "ドラッグ" in DZ and "クリック" in DZ and "catalog/.pending/" in DZ,
    "ドラッグ=%s / クリック=%s / 手動コピー=%s"
    % ("ドラッグ" in DZ, "クリック" in DZ, "catalog/.pending/" in DZ),
)
ext_urls = [u for u in re.findall(r'https?://[^"\'\s)]+', CATHTML) if "w3.org" not in u]
check(
    "U13 SCR-004 に外部URL参照が無い（NFR-005）",
    not ext_urls,
    "外部URL=%s" % (ext_urls or "なし"),
)

# ---------------------------------------------------------------------------
# U14 SPEC
# ---------------------------------------------------------------------------
row106 = re.search(r"^\|\s*REQ-106\s*\|.*$", SPEC, re.M)
ROW = row106.group(0) if row106 else ""
check(
    "U14 SPEC REQ-106 に UI 経由のアップロードが明記されている",
    bool(ROW) and "アップロード" in ROW and "サーバ生成" in ROW and "マジックバイト" in ROW,
    "アップロード=%s / サーバ生成名=%s / マジックバイト=%s"
    % ("アップロード" in ROW, "サーバ生成" in ROW, "マジックバイト" in ROW),
)

print("=" * 78)
print("KLK-063 カタログ画像のアップロードUI（A-3・ドロップゾーンの実働化）静的チェック")
print("対象: bridge.py（判定関数・防御順・保存先）/ SCR-004 / SPEC REQ-106")
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
