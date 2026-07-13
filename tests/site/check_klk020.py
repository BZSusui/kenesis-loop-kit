#!/usr/bin/env python3
"""
KLK-020 acceptance-condition checker (static / core・no browser・no network).

Verifies the statically-checkable acceptance conditions S1-S19 from
docs/designs/KLK-020.md §9（S群）for the MVフリー実写真アタリ（REQ-104 b方式）:

  設定画面 UI + 純ロジック(slice)        draft-gen/index.html
  ブリッジ本体(import + ソース静的検査)   draft-gen/bridge.py
  生成規約(文言)                          .claude/skills/draft-generate/templates/DRAFT_RULES.md
  生成規約(文言)                          .claude/skills/draft-generate/SKILL.md
  要件定義(文言)                          docs/SPEC.md
  ゴールデン/ダミー(静的)                 tests/fixtures/klk020/

Source of truth = 設計書 KLK-020 §9（S群 S1-S19）。check_klk013/019 と同型:
import 単体＋正規表現・文字列検索・tester所有・exit 0/1・Python3標準ライブラリのみ・
ネットワーク非使用。bridge.py は `if __name__ == "__main__"` ガードでサーバ起動を隔離して
いるため import で副作用（bind/実行）は起きない。UI/純ロジックは DOM に依存する DOM 層を
除いた純関数スライスと静的文字列検査で確認する。D群（実HTTPスモーク・standard等価・discover
回帰）は tests/test_palette_klk020.py が、M群（ブリッジ実起動＋ブラウザ実機＋実生成）は tester
が手動確認しチケットのログへ記録する。プロダクション成果物は変更しない。

Run: python3 tests/site/check_klk020.py
Exit code 0 = all static/core checks pass, 1 = at least one fail.
"""
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_PATH = os.path.join(ROOT, "draft-gen", "bridge.py")
INDEX_HTML_PATH = os.path.join(ROOT, "draft-gen", "index.html")
DRAFT_RULES_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md")
SKILL_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "SKILL.md")
SPEC_PATH = os.path.join(ROOT, "docs", "SPEC.md")
FIXTURES_DIR = os.path.join(ROOT, "tests", "fixtures", "klk020")
GOLDEN_PATH = os.path.join(FIXTURES_DIR, "golden.free-mv.html")
INSTR_FREE_PATH = os.path.join(FIXTURES_DIR, "instruction.free.json")
INSTR_STD_PATH = os.path.join(FIXTURES_DIR, "instruction.standard.json")

BRIDGE_SRC = open(BRIDGE_PATH, encoding="utf-8").read()
INDEX_HTML = open(INDEX_HTML_PATH, encoding="utf-8").read()
DRAFT_RULES = open(DRAFT_RULES_PATH, encoding="utf-8").read()
SKILL = open(SKILL_PATH, encoding="utf-8").read()
SPEC = open(SPEC_PATH, encoding="utf-8").read()
GOLDEN = open(GOLDEN_PATH, encoding="utf-8").read()

# bridge.py を import（__main__ ガードで副作用なし＝サーバは起動しない）。
_spec = importlib.util.spec_from_file_location("klk020_bridge", BRIDGE_PATH)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)

results = []  # (name, passed: bool, detail)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# 危険フラグ（決して含めてはならない・最小権限）。
DANGER_FLAGS = ("--dangerously-skip-permissions", "bypassPermissions")
# 秘密情報パターン（check_klk006 S15 と同一）。
SECRET_RE = re.compile(r"api[_-]?key|secret|password|token|private[_ ]key|BEGIN .*PRIVATE", re.I)
# 外部URL許可ホスト（check_klk006 S15 と同一）。
_ALLOW_HOSTS = ("www.w3.org", "example.com", "example.org", "example.net")


def _host(url):
    m = re.match(r"https?://([^/\s\"')]+)", url)
    return m.group(1).lower() if m else ""


def _ext_urls(text):
    return [m for m in re.findall(r'https?://[^\s"\')（]+', text)
            if _host(m) not in _ALLOW_HOSTS]


def _slice_between(src, start_pat, end_pat):
    """start_pat（正規表現）の一致位置から end_pat の次の一致手前までを返す。
    end_pat が無ければ末尾まで。start が無ければ空文字。"""
    m = re.search(start_pat, src)
    if not m:
        return ""
    i = m.end()
    m2 = re.search(end_pat, src[i:])
    return src[i:i + m2.start()] if m2 else src[i:]


# ソース中の主要スライス。
BUILD_SEG = _slice_between(INDEX_HTML, r"function buildInstruction\(input\)\s*\{", r"\nfunction render\(")
DO_POST_SEG = _slice_between(BRIDGE_SRC, r"\n        def do_POST\(self\):", r"\n        def _serve_index\(self\):")
UPLOAD_SEG = _slice_between(BRIDGE_SRC, r"\n        def _upload\(self\):", r"\n        def _generate\(self\):")

# ===========================================================================
# S1 見出し文言（MV 限定）
# ===========================================================================
s1 = "<h2>メインビジュアル アタリ画像の入れ方</h2>" in INDEX_HTML
check(
    "S1 見出し文言 (draft-gen/index.html セクション⑦の見出しが「メインビジュアル アタリ画像の入れ方」)",
    s1,
    f"見出し一致={s1}",
)

# ===========================================================================
# S2 radio 集合不変（{standard, free-photo}）
# ===========================================================================
atari_vals = set(re.findall(r'<input[^>]*name="atari"[^>]*value="([^"]*)"', INDEX_HTML))
atari_vals |= set(re.findall(r'<input[^>]*value="([^"]*)"[^>]*name="atari"', INDEX_HTML))
s2 = atari_vals == {"standard", "free-photo"}
check(
    "S2 radio 集合不変 (name=\"atari\" の value 集合が {\"standard\",\"free-photo\"} に完全一致・check_klk006 S12 と同型)",
    s2,
    f"value集合={sorted(atari_vals)}",
)

# ===========================================================================
# S3 サブUI存在・表示切替
# ===========================================================================
s3_container = 'id="mvFreePhoto"' in INDEX_HTML
s3_file = re.search(r'<input[^>]*id="mvPhotoFile"', INDEX_HTML) is not None
s3_file_type = re.search(r'<input[^>]*id="mvPhotoFile"[^>]*type="file"', INDEX_HTML) is not None \
    or re.search(r'<input[^>]*type="file"[^>]*id="mvPhotoFile"', INDEX_HTML) is not None
s3_accept = re.search(r'id="mvPhotoFile"[^>]*accept="image/\*"', INDEX_HTML) is not None \
    or re.search(r'accept="image/\*"[^>]*id="mvPhotoFile"', INDEX_HTML) is not None
# render() が atari==='free-photo' で display を block/none に切替える分岐がソースに存在
s3_toggle = re.search(r"value\s*===\s*'free-photo'", INDEX_HTML) is not None and \
    re.search(r"\.style\.display\s*=\s*isFree\s*\?\s*'block'\s*:\s*'none'", INDEX_HTML) is not None
s3 = s3_container and s3_file and s3_file_type and s3_accept and s3_toggle
check(
    "S3 サブUI存在・表示切替 (#mvFreePhoto container・#mvPhotoFile[type=file accept=image/*] が存在し、render/updateMvFreePhoto が atari==='free-photo' で style.display を block/none に切替)",
    s3,
    f"container={s3_container}, file={s3_file}, type=file={s3_file_type}, accept={s3_accept}, 表示切替={s3_toggle}",
)

# ===========================================================================
# S4 検索リンク4種（class="mv-search"・target=_blank rel=noopener・4ホスト）
# ===========================================================================
mv_anchors = re.findall(r'<a\s+class="mv-search"[^>]*>', INDEX_HTML)
_hosts = {
    "unsplash": "unsplash.com/s/photos/",
    "pexels": "www.pexels.com/search/",
    "pixabay": "pixabay.com/images/search/",
    "adobe": "stock.adobe.com/search?k=",
}
s4_count = len(mv_anchors) == 4
s4_bases = all(any(f'data-base="{b}"' in a for a in mv_anchors) for b in _hosts.values())
s4_blank = all('target="_blank"' in a for a in mv_anchors)
s4_noopener = all('rel="noopener"' in a for a in mv_anchors)
s4 = s4_count and s4_bases and s4_blank and s4_noopener
check(
    "S4 検索リンク4種 (class=\"mv-search\" の <a> が4つ・data-base に Unsplash/Pexels/Pixabay/Adobe Stock・全て target=\"_blank\" rel=\"noopener\")",
    s4,
    f"個数={len(mv_anchors)}, 4ホスト={s4_bases}, target=_blank={s4_blank}, rel=noopener={s4_noopener}",
)

# ===========================================================================
# S5 権利注記（有料/透かしは埋め込まず購入→アップロード）
# ===========================================================================
rights_seg = _slice_between(INDEX_HTML, r'class="[^"]*mv-rights[^"]*"', r"</p>")
s5_class = "mv-rights" in INDEX_HTML
s5_words = ("埋め込ま" in rights_seg) and ("アップロード" in rights_seg) and \
    (("購入" in rights_seg) or ("ダウンロード" in rights_seg))
s5 = s5_class and s5_words
check(
    "S5 権利注記 (class=\"mv-rights\" 注記に「埋め込まず・購入/ダウンロード・アップロードで取り込む」旨の文言)",
    s5,
    f"mv-rights存在={s5_class}, 文言={s5_words}",
)

# ===========================================================================
# S6 buildInstruction が mvPhoto を条件出力（free-photo かつ保存名あり）
# ===========================================================================
s6_guard = re.search(r"input\.atari\s*===\s*'free-photo'", BUILD_SEG) is not None
s6_assign = re.search(r"out\.mvPhoto\s*=\s*\{\s*file\s*:", BUILD_SEG) is not None
s6_name = re.search(r"input\.mvPhoto", BUILD_SEG) is not None
s6 = s6_guard and s6_assign and s6_name
check(
    "S6 buildInstruction が mvPhoto を条件出力 (純ロジックに『atari===\"free-photo\" かつ 保存名あり → out.mvPhoto={file:...}』分岐が存在)",
    s6,
    f"free-photoガード={s6_guard}, out.mvPhoto代入={s6_assign}, input.mvPhoto参照={s6_name}",
)

# ===========================================================================
# S7 standard 等価（mvPhoto キー非出力）
# ===========================================================================
# 無条件の out オブジェクトリテラルに mvPhoto が含まれない（条件分岐でのみ後付け＝standard 等価）。
OUT_LITERAL = _slice_between(BUILD_SEG, r"const out = \{", r"\n  \};")
s7_literal_clean = "mvPhoto" not in OUT_LITERAL
# 標準 fixtures に mvPhoto キーが無い（standard 出力の等価参照）。
try:
    std_obj = json.load(open(INSTR_STD_PATH, encoding="utf-8"))
    s7_std_no_mv = "mvPhoto" not in std_obj and std_obj.get("atari") == "standard"
except (OSError, ValueError):
    s7_std_no_mv = False
s7 = s7_literal_clean and s7_std_no_mv
check(
    "S7 standard 等価（キー非出力） (buildInstruction の無条件 out リテラルに mvPhoto 非含有・条件分岐でのみ後付け／instruction.standard.json に mvPhoto キーが無い)",
    s7,
    f"outリテラルmvPhoto無={s7_literal_clean}, standard fixture mvPhoto無={s7_std_no_mv}",
)

# ===========================================================================
# S8 POST /upload ルーティング
# ===========================================================================
s8 = re.search(r'path == "/upload"', DO_POST_SEG) is not None and "_upload()" in DO_POST_SEG
check(
    "S8 POST /upload ルーティング (do_POST に path == \"/upload\" → self._upload() 分岐が存在)",
    s8,
    f"分岐存在={s8}",
)

# ===========================================================================
# S9 /upload 防御順（静的）: Origin(403)→サイズ(413/400)→マジック(400)→保存→JSON(200)
# docstring は語を含むので取り除いてから本体コードの順序だけを検査する。
# ===========================================================================
UPLOAD_BODY = re.sub(r'^\s*""".*?"""', "", UPLOAD_SEG, count=1, flags=re.DOTALL)
i_origin = UPLOAD_BODY.find("is_allowed_origin")
i_403 = UPLOAD_BODY.find("self._json(403")
i_413 = UPLOAD_BODY.find("self._json(413")
i_sniff = UPLOAD_BODY.find("sniff_image_ext")
i_save = UPLOAD_BODY.find("makedirs")
i_200 = UPLOAD_BODY.find('self._json(200')
_order = [i_origin, i_403, i_413, i_sniff, i_save, i_200]
s9_present = all(v >= 0 for v in _order)
s9_order = s9_present and (i_origin < i_413 < i_sniff < i_save < i_200) and (i_origin < i_403)
s9 = s9_order
check(
    "S9 /upload 防御順（静的） (_upload 本体が is_allowed_origin(403)→サイズ上限(413/400)→sniff_image_ext(400)→makedirs保存→_json(200) の順)",
    s9,
    f"origin={i_origin}, 403={i_403}, 413={i_413}, sniff={i_sniff}, save={i_save}, json200={i_200}, 順序整合={s9_order}",
)

# ===========================================================================
# S10 /upload 専用サイズ上限（UPLOAD_MAX_BODY_BYTES > MAX_BODY_BYTES）
# ===========================================================================
umax = getattr(bridge, "UPLOAD_MAX_BODY_BYTES", None)
jmax = getattr(bridge, "MAX_BODY_BYTES", None)
s10_defined = isinstance(umax, int) and isinstance(jmax, int)
s10_bigger = s10_defined and umax > jmax
# JSON ルート(_generate/_regenerate/_catalog_import)は MAX_BODY_BYTES のまま（/upload だけ UPLOAD_ を使う）。
gen_seg = _slice_between(BRIDGE_SRC, r"\n        def _generate\(self\):", r"\n        def _regenerate\(self\):")
s10_json_route = "MAX_BODY_BYTES" in gen_seg and "UPLOAD_MAX_BODY_BYTES" not in gen_seg
s10_upload_uses = "UPLOAD_MAX_BODY_BYTES" in UPLOAD_SEG
s10 = s10_defined and s10_bigger and s10_json_route and s10_upload_uses
check(
    "S10 /upload 専用サイズ上限 (UPLOAD_MAX_BODY_BYTES 定数が MAX_BODY_BYTES より大・JSON ルート(_generate)は MAX_BODY_BYTES のまま・/upload は UPLOAD_ を使用)",
    s10,
    f"UPLOAD={umax}, JSON={jmax}, UPLOAD>JSON={s10_bigger}, _generate=MAX据置={s10_json_route}, _upload=UPLOAD使用={s10_upload_uses}",
)

# ===========================================================================
# S11 マジックバイト純関数 sniff_image_ext（import 単体）
# ===========================================================================
sniff = getattr(bridge, "sniff_image_ext", None)
if callable(sniff):
    r_jpg = sniff(b"\xff\xd8\xff\xe0\x00\x10JFIF") == ".jpg"
    r_png = sniff(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR") == ".png"
    r_none = sniff(b"GIF89a....") is None
    r_empty = sniff(b"") is None
    r_nonbytes = sniff("not-bytes") is None
    s11 = r_jpg and r_png and r_none and r_empty and r_nonbytes
    s11_detail = f"jpg={r_jpg}, png={r_png}, 非画像=None:{r_none}, 空=None:{r_empty}, 非bytes=None:{r_nonbytes}"
else:
    s11 = False
    s11_detail = "sniff_image_ext が定義されていない"
check(
    "S11 マジックバイト純関数 (sniff_image_ext: JPEG(FF D8 FF)→.jpg / PNG(89 50 4E 47 0D 0A 1A 0A)→.png / 非画像・空・非bytes→None)",
    s11,
    s11_detail,
)

# ===========================================================================
# S12 mvPhoto 安全名防御（存在時のみ検証・standard は受理）
# ===========================================================================
validate = getattr(bridge, "validate_instruction", None)
_base = {
    "schema": "design-draft-instruction", "version": 1,
    "industry": {"resolved": "飲食"},
    "layout": {"columns": "1col"},
    "colors": {"main": "#123456"},
}
if callable(validate):
    ok_std, _ = validate(dict(_base))                                    # mvPhoto 無し＝従来どおり受理
    ok_good, _ = validate(dict(_base, mvPhoto={"file": "upl-abc123.jpg"}))  # 安全名＝受理
    ok_trav, _ = validate(dict(_base, mvPhoto={"file": "../../etc/passwd"}))  # traversal＝reject
    ok_sep, _ = validate(dict(_base, mvPhoto={"file": "a/b.jpg"}))        # パス区切り＝reject
    ok_type, _ = validate(dict(_base, mvPhoto="upl-abc.jpg"))            # 非dict＝reject
    s12 = ok_std and ok_good and (not ok_trav) and (not ok_sep) and (not ok_type)
    s12_detail = f"standard受理={ok_std}, 安全名受理={ok_good}, ..reject={not ok_trav}, /reject={not ok_sep}, 非dict reject={not ok_type}"
else:
    s12 = False
    s12_detail = "validate_instruction が定義されていない"
check(
    "S12 mvPhoto 安全名防御 (validate_instruction が mvPhoto 存在時に file を is_safe_catalog_name で検証し ../ 等を reject・mvPhoto 無し[standard]は受理＝等価)",
    s12,
    s12_detail,
)

# ===========================================================================
# S13 ステージング保存先（mockups/.uploads/・保存名サーバ生成 upl-<hex>.<ext>）
# ===========================================================================
s13_dir = re.search(r'os\.path\.join\([^)]*["\']mockups["\']\s*,\s*["\']\.uploads["\']\s*\)', BRIDGE_SRC) is not None
s13_name = re.search(r'"upl-"\s*\+\s*uuid\.uuid4\(\)\.hex\s*\+\s*ext', BRIDGE_SRC) is not None
s13 = s13_dir and s13_name
check(
    "S13 ステージング保存先 (保存先が mockups/.uploads/[Git除外内包]・保存名がサーバ生成 upl-<uuid>.<ext>)",
    s13,
    f"uploads_dir={s13_dir}, サーバ生成保存名={s13_name}",
)

# ===========================================================================
# S14 危険フラグ非含有・最小権限維持（新規 /upload 経路にサブプロセス無し）
# ===========================================================================
s14_no_danger = not any(f in BRIDGE_SRC for f in DANGER_FLAGS)
s14_no_shell = "shell=True" not in BRIDGE_SRC
s14_upload_no_proc = ("subprocess" not in UPLOAD_SEG) and ("Popen" not in UPLOAD_SEG)
s14 = s14_no_danger and s14_no_shell and s14_upload_no_proc
check(
    "S14 危険フラグ非含有・最小権限維持 (bridge.py に --dangerously-skip-permissions/bypassPermissions/shell=True 無し・_upload 経路にサブプロセス起動無し)",
    s14,
    f"危険フラグ非含有={s14_no_danger}, shell=True非使用={s14_no_shell}, _uploadにsubprocess無={s14_upload_no_proc}",
)

# ===========================================================================
# S15 index.html 外部URL 0 維持（検索リンクはスキーム実行時組立て）
# ===========================================================================
idx_ext = _ext_urls(INDEX_HTML)
idx_secret = [f"{ln}: {line.strip()[:60]}" for ln, line in enumerate(INDEX_HTML.splitlines(), 1)
              if SECRET_RE.search(line)]
s15 = not idx_ext and not idx_secret
check(
    "S15 index.html 外部URL 0 維持 (外部 http URL literal 0件[w3.org/example.* 除外]・秘密パターン 0件・検索リンクはスキーム実行時組立て)",
    s15,
    f"外部URL={idx_ext or 0}, 秘密={idx_secret or 0}",
)

# ===========================================================================
# S16 DRAFT_RULES b方式規約
# ===========================================================================
s16_mv_only = ("MV-01" in DRAFT_RULES) and ("REQ-104" in DRAFT_RULES)
s16_relimg = re.search(r'相対[^\n]*<img', DRAFT_RULES) is not None or 'src="assets/mv' in DRAFT_RULES
s16_other_a = ("他のアタリ枠" in DRAFT_RULES) or ("他枠は" in DRAFT_RULES and "a方式" in DRAFT_RULES)
s16_fallback = "フォールバック" in DRAFT_RULES
s16_ext_ban = ("外部 http" in DRAFT_RULES) or ("http(s):// の外部 img" in DRAFT_RULES) or ("http(s)://" in DRAFT_RULES and "禁止" in DRAFT_RULES)
s16 = s16_mv_only and s16_relimg and s16_other_a and s16_fallback and s16_ext_ban
check(
    "S16 DRAFT_RULES b方式規約 (MV-01限定・相対<img>[assets/mv]・他枠a方式・未供給/失敗はaフォールバック・外部http img は依然禁止 の文言)",
    s16,
    f"MV限定={s16_mv_only}, 相対img={s16_relimg}, 他枠a方式={s16_other_a}, フォールバック={s16_fallback}, 外部http禁止={s16_ext_ban}",
)

# ===========================================================================
# S17 SKILL b方式規約＋同梱コピー手順
# ===========================================================================
s17_req = ("REQ-104" in SKILL) and ("MV-01" in SKILL)
s17_copy = "mockups/.uploads/" in SKILL and "assets/" in SKILL
s17_safe = ("basename" in SKILL) and ("安全名" in SKILL)
s17_relimg = 'src="assets/mv' in SKILL or re.search(r'相対[^\n]*<img', SKILL) is not None
s17_fallback = "フォールバック" in SKILL or "a方式" in SKILL
s17 = s17_req and s17_copy and s17_safe and s17_relimg and s17_fallback
check(
    "S17 SKILL b方式規約＋同梱手順 (MV-01限定・mockups/.uploads/{file}→assets/ コピー・basename/安全名限定・相対<img>・フォールバック の手順)",
    s17,
    f"REQ-104/MV={s17_req}, コピー手順={s17_copy}, 安全名basename={s17_safe}, 相対img={s17_relimg}, フォールバック={s17_fallback}",
)

# ===========================================================================
# S18 SPEC REQ-104 補足＋NFR-005 整合注記
# ===========================================================================
spec_104 = _slice_between(SPEC, r"REQ-104", r"\n\|")
s18_mv = "メインビジュアル" in spec_104 and ("限定" in spec_104)
s18_upload = "アップロード" in spec_104
s18_search = "検索リンク" in spec_104
s18_future = "URL" in spec_104 and "将来" in spec_104
s18_relbundle = "相対同梱" in spec_104
s18_nfr = ("NFR-005" in SPEC) and ("相対同梱" in SPEC) and ("オフライン" in SPEC)
s18 = s18_mv and s18_upload and s18_search and s18_future and s18_relbundle and s18_nfr
check(
    "S18 SPEC REQ-104 補足 (MV限定・アップロード＋検索リンク・URL直接入力は将来・相対同梱で自己完結・NFR-005 整合注記)",
    s18,
    f"MV限定={s18_mv}, アップロード={s18_upload}, 検索リンク={s18_search}, URL将来={s18_future}, 相対同梱={s18_relbundle}, NFR-005注記={s18_nfr}",
)

# ===========================================================================
# S19 セキュリティ（index.html＋bridge.py＋fixtures）: 外部URL/秘密/実案件名 0
# ===========================================================================
# index.html は S15 で確認済み。bridge.py と fixtures を追加検査する。
bridge_secret = [f"{ln}: {line.strip()[:60]}" for ln, line in enumerate(BRIDGE_SRC.splitlines(), 1)
                 if SECRET_RE.search(line)]
# fixtures: 外部URL 0・秘密 0・ダミー/架空マーカー有り（実案件名なしの担保）。
fixture_texts = {
    "golden.free-mv.html": GOLDEN,
    "instruction.free.json": open(INSTR_FREE_PATH, encoding="utf-8").read(),
    "instruction.standard.json": open(INSTR_STD_PATH, encoding="utf-8").read(),
}
fx_ext = {n: _ext_urls(t) for n, t in fixture_texts.items()}
fx_ext_any = any(v for v in fx_ext.values())
fx_secret_any = any(SECRET_RE.search(t) for t in fixture_texts.values())
# 合成ダミー・架空である旨のマーカー（実在案件でないことを明示）。
fx_dummy_marker = ("実在の顧客・案件ではありません" in GOLDEN) or ("サンプル" in GOLDEN)
s19 = (not bridge_secret) and (not fx_ext_any) and (not fx_secret_any) and fx_dummy_marker
check(
    "S19 セキュリティ (bridge.py 秘密 0・fixtures[golden/instruction] 外部URL 0・秘密 0・合成ダミー/架空マーカー有り＝実案件名なし)",
    s19,
    f"bridge秘密={bridge_secret or 0}, fixtures外部URL={ {k: v for k, v in fx_ext.items() if v} or 0}, fixtures秘密={fx_secret_any}, ダミーマーカー={fx_dummy_marker}",
)

# ===========================================================================
# ゴールデン静的検査（設計 §9・§4.6）: MV-01 相対 <img>・他枠 a方式・外部URL 0
# S15/S16 と対をなす生成物側の静的確認（S19 に内包して 1 checkとして扱う補助検証）。
# ===========================================================================
g_mv_img = re.search(r'<img[^>]*class="mv-photo"[^>]*src="assets/mv\.(jpg|png)"', GOLDEN) is not None \
    or re.search(r'<img[^>]*src="assets/mv\.(jpg|png)"', GOLDEN) is not None
g_ext = _ext_urls(GOLDEN)
g_imgs = re.findall(r'<img\b[^>]*src="([^"]*)"', GOLDEN)
g_all_relative = all(not re.match(r'https?://', s) for s in g_imgs)
g_ok = g_mv_img and (not g_ext) and g_all_relative
check(
    "G ゴールデン静的検査 (golden.free-mv.html: MV-01 に相対 <img src=\"assets/mv.<ext>\">・全 <img> が相対・外部 http URL 0件)",
    g_ok,
    f"MV相対img={g_mv_img}, img src一覧={g_imgs}, 全相対={g_all_relative}, 外部URL={g_ext or 0}",
)

# ===========================================================================
# Report
# ===========================================================================
print("=" * 78)
print("KLK-020 static/core acceptance checks (docs/designs/KLK-020.md §9 S群 S1-S19 を正とする)")
print("対象: draft-gen/index.html(静的+純ロジックslice) / draft-gen/bridge.py(import+ソース静的) /")
print("      DRAFT_RULES.md・SKILL.md・docs/SPEC.md(文言) / tests/fixtures/klk020(ゴールデン・ダミー静的)")
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
print("D群（test_palette_klk020.py で subprocess exit0・discover 回帰・standard等価・/upload 実HTTP）:")
print("  - D1 check_klk020.py subprocess exit0 / D2 discover 全緑（回帰なし）")
print("  - D3 standard 等価回帰（buildInstruction が mvPhoto キーを出さない・fixtures 整合）")
print("  - D4 /upload 実HTTPスモーク（200/savedName・不正Origin403・超過413・非画像400・git除外）")
print()
print("M群（tester がブリッジ起動＋ブラウザ実機＋実生成で手動確認・結果をログへ記録）:")
print("  - M1 UI表示切替 / M2 アップロード→生成→MV反映(Git追跡外) / M3 フォールバック")
print("  - M4 検索リンク別タブ・権利注記 / M5 standard 従来どおり / M6 /upload 防御 実機")
sys.exit(1 if failed else 0)
