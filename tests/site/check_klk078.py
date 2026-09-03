#!/usr/bin/env python3
"""
KLK-078 acceptance-condition checker (static / no browser required).

型入れ替え（第3弾）の**土台**: 番地リストを実ページから作り、現在の型を読めるようにした変更。

★このチェッカーが守っているもの:
  compare.html は番地6種を**焼き込んで**いた。KLK-022 以降セクション構成は指示書ごとに変わるため、
  選択肢と実ページが食い違い、**同梱の見本3点すべてで 🔄 が壊れていた**
  （選べるのに404 / 実在するのに選べない）。さらに `find_target_section` が `<div class="sec` 決め打ちで、
  `<section>` を使うページでは**全番地が404**＝機能が丸ごと死んでいた。
  この2つが戻らないよう、**規約・純関数・見本の実物**の3面から見張る。

  R群 = 規約テキスト / U群 = 純関数の実挙動 / S群 = 見本(samples/)の実物

Run: python3 tests/site/check_klk078.py
Exit code 0 = all checks pass, 1 = at least one fail.
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
DESIGN_PATH = os.path.join(ROOT, "docs", "designs", "KLK-078.md")
DESIGN = open(DESIGN_PATH, encoding="utf-8").read() if os.path.isfile(DESIGN_PATH) else ""

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def rel(p):
    return os.path.relpath(p, ROOT)


# ===========================================================================
# R群 — 規約
# ===========================================================================
check(
    "R1 §13 が「番地を焼き込まない」と明記している",
    "★番地は焼き込まない（KLK-078）" in RULES and "GET /sections` の結果で埋める" in RULES,
    "明記=%s" % ("★番地は焼き込まない（KLK-078）" in RULES),
)

check(
    "R2 §13 が固定列挙をやめた理由（見本3点で壊れていた実例）を載せている",
    "★なぜ固定列挙をやめたか（KLK-078）" in RULES
    and "同梱の見本3点すべてで壊れていた" in RULES,
    "理由と実例=%s" % ("同梱の見本3点すべてで壊れていた" in RULES),
)

# ★契約更新（KLK-079）: KLK-078 は現在の型を読み取り専用ラベルで出していたが、
#   KLK-079 で選べる <select> に置き換わり、現在の型は「（現在）」付きの選択肢として出るようになった。
#   見せ方は変わってよいが、「**現在の型が分かること**」「**案切替で読み直すこと**」は
#   KLK-078 が作った不変条件なので、そちらを検査する。
check(
    "R3 §13 が現在型の明示と、案切替での読み直しを求めている",
    "（現在）" in RULES and "案を切り替えたら読み直す" in RULES,
    "現在型の明示=%s / 読み直し=%s" % ("（現在）" in RULES, "案を切り替えたら読み直す" in RULES),
)

check(
    "R4 §14 が「.sec の要素名は div とは限らない」と警告している",
    "★`.sec` の要素名は `div` とは限らない（KLK-078）" in RULES
    and "要素名を決め打ちにしないこと" in RULES,
    "警告=%s" % ("要素名を決め打ちにしないこと" in RULES),
)

check(
    "R5 §14 の「select は基本6番地のまま」が撤回されている",
    "KLK-078 で撤回" in RULES,
    "撤回の明記=%s" % ("KLK-078 で撤回" in RULES),
)

check(
    "R6 設計書 docs/designs/KLK-078.md がある（078/079/080 共通）",
    bool(DESIGN) and "KLK-079" in DESIGN and "KLK-080" in DESIGN,
    "設計書=%s（%d字）" % (bool(DESIGN), len(DESIGN)),
)

# ===========================================================================
# U群 — 純関数の実挙動（import して実際に呼ぶ）
# ===========================================================================
POOLS = bridge.SECTION_TYPE_POOLS

check(
    "U1 型プールが14セクション×各6型そろっている",
    len(POOLS) == 14 and all(len(v) == 6 for v in POOLS.values()),
    "%dセクション / 6型でないもの=%s"
    % (len(POOLS), [k for k, v in POOLS.items() if len(v) != 6] or "なし"),
)

# 規約の表とコードの語彙が一致しているか（ドリフト検出）
drift = []
for sec, pool in POOLS.items():
    for marker in pool:
        if "`%s`" % marker not in RULES:
            drift.append("%s:%s" % (sec, marker))
check(
    "U2 コードの型語彙が規約(§12.1.2/§12.1.3)に全部載っている（ドリフト検出）",
    not drift,
    "規約に無い語=%s" % (drift or "なし"),
)

check(
    "U3 pool_for_addr が番地から正しく引ける（連番拡張も同じプール）",
    bridge.pool_for_addr("MV-01")[0] == "full"
    and bridge.pool_for_addr("ABOUT-02")[0] == "img-left"
    and bridge.pool_for_addr("NAV-01") == ()
    and bridge.pool_for_addr("FOOTER-01") == ()
    and bridge.pool_for_addr("CTA-01") == ()
    and bridge.pool_for_addr("../etc") == (),
    "MV=%s / ABOUT-02=%s / NAV=%s / CTA=%s"
    % (
        bridge.pool_for_addr("MV-01")[:1],
        bridge.pool_for_addr("ABOUT-02")[:1],
        bridge.pool_for_addr("NAV-01"),
        bridge.pool_for_addr("CTA-01"),
    ),
)

check(
    "U4 is_valid_desired_type が許可リスト判定（語彙外・別セクションの型を弾く）",
    bridge.is_valid_desired_type("MV-01", "overlap")
    and bridge.is_valid_desired_type("MV-01", None)
    and bridge.is_valid_desired_type("MV-01", "")
    and not bridge.is_valid_desired_type("MV-01", "pat-grid")
    and not bridge.is_valid_desired_type("MV-01", "OVERLAP")
    and not bridge.is_valid_desired_type("NAV-01", "full")
    and not bridge.is_valid_desired_type("MV-01", "overlap; rm -rf /"),
    "overlap=%s / 別セクション型=%s / 注入風=%s"
    % (
        bridge.is_valid_desired_type("MV-01", "overlap"),
        bridge.is_valid_desired_type("MV-01", "pat-grid"),
        bridge.is_valid_desired_type("MV-01", "overlap; rm -rf /"),
    ),
)

# `band` が `panel-band` に誤ヒットしないこと（単語境界）
_hero_band = '<section class="sec"><div class="addr"><span class="pin">MV-01</span></div>' \
             '<div class="m-hero" data-hero="panel-band"></div></section>'
check(
    "U5 read_section_marker の単語境界（band が panel-band に誤ヒットしない）",
    bridge.read_section_marker(_hero_band, "MV-01") == "panel-band",
    "読めた型=%s" % bridge.read_section_marker(_hero_band, "MV-01"),
)

_no_marker = '<section class="sec"><div class="addr"><span class="pin">MV-01</span></div>' \
             '<div class="m-hero"></div></section>'
check(
    "U6 型が無いときは None（読めないことを黙って捏造しない）",
    bridge.read_section_marker(_no_marker, "MV-01") is None
    and bridge.read_section_marker(_no_marker, "NAV-01") is None
    and bridge.read_section_marker("", "MV-01") is None,
    "型なし=%s" % bridge.read_section_marker(_no_marker, "MV-01"),
)

# ★要素名を決め打ちにしない（この回帰が本チケットの主眼）
_tags = ("div", "section", "nav", "header", "footer")
bad_tags = []
for tag in _tags:
    html = '<{0} class="sec"><div class="addr"><span class="pin">ABOUT-01</span></div>' \
           '<div class="m-about img-circle"></div></{0}>'.format(tag)
    if bridge.read_section_marker(html, "ABOUT-01") != "img-circle":
        bad_tags.append(tag)
check(
    "U7 .sec の要素名が div/section/nav/header/footer のどれでも特定できる",
    not bad_tags,
    "特定できない要素=%s" % (bad_tags or "なし"),
)

# class="sec-more-btn" のような別クラスを .sec と誤認しない
_decoy = '<a class="sec-more-btn" href="#">more</a>' \
         '<section class="sec"><div class="addr"><span class="pin">MENU-01</span></div>' \
         '<div class="m-menu tab-switch"></div></section>'
check(
    "U8 class=\"sec-more-btn\" 等を .sec と誤認しない",
    bridge.read_section_marker(_decoy, "MENU-01") == "tab-switch",
    "読めた型=%s" % bridge.read_section_marker(_decoy, "MENU-01"),
)

check(
    "U9 list_page_addrs が DOM 順で返し、重複を1回にまとめる",
    bridge.list_page_addrs(
        '<span class="pin">MV-01</span><span class="pin">NAV-01</span><span class="pin">MV-01</span>'
    ) == ["MV-01", "NAV-01"]
    and bridge.list_page_addrs(None) == [],
    "順序=%s"
    % bridge.list_page_addrs(
        '<span class="pin">MV-01</span><span class="pin">NAV-01</span><span class="pin">MV-01</span>'
    ),
)

# ===========================================================================
# S群 — 見本(samples/)の実物
# ===========================================================================
SAMPLE_DIRS = sorted(d for d in glob.glob(os.path.join(ROOT, "samples", "*")) if os.path.isdir(d))

# ★本チケットの核心: 実ページの全番地が特定でき、型が読めること
unresolved, typed, untyped = [], 0, 0
for d in SAMPLE_DIRS:
    for p in sorted(glob.glob(os.path.join(d, "index-*.html"))):
        html = open(p, encoding="utf-8").read()
        addrs = bridge.list_page_addrs(html)
        if not addrs:
            unresolved.append("%s: 番地が1つも読めない" % rel(p))
            continue
        for a in addrs:
            start, _ = bridge.find_target_section(html, a)
            if start is None:
                unresolved.append("%s: %s のブロックを特定できない" % (rel(p), a))
                continue
            if bridge.pool_for_addr(a):
                if bridge.read_section_marker(html, a):
                    typed += 1
                else:
                    unresolved.append("%s: %s の型が読めない" % (rel(p), a))
            else:
                untyped += 1
check(
    "S1 見本9ファイルの全番地でブロックが特定でき、型のある番地は型が読める",
    not unresolved,
    "型を読めた=%d / プール無し=%d / 失敗=%s" % (typed, untyped, unresolved or "なし"),
)

# compare.html が番地を焼き込んでいないこと
baked, has_type_label, has_sections_call = [], 0, 0
for d in SAMPLE_DIRS:
    p = os.path.join(d, "compare.html")
    if not os.path.isfile(p):
        continue
    html = open(p, encoding="utf-8").read()
    fixed = re.findall(r'<option value="[A-Z][A-Z0-9]*-\d{2}"', html)
    if fixed:
        baked.append("%s: %s" % (rel(p), fixed[:3]))
    if 'id="regen-type"' in html:
        has_type_label += 1
    if "/sections?folder=" in html:
        has_sections_call += 1
check(
    "S2 見本の compare.html が番地を焼き込んでいない",
    not baked,
    "焼き込み=%s" % (baked or "なし"),
)
check(
    "S3 見本の compare.html が /sections を呼び、現在型ラベルを持つ",
    has_sections_call == len(SAMPLE_DIRS) and has_type_label == len(SAMPLE_DIRS),
    "/sections 呼出=%d/%d / 型ラベル=%d/%d"
    % (has_sections_call, len(SAMPLE_DIRS), has_type_label, len(SAMPLE_DIRS)),
)

# 案ごとに型が違うこと（案切替で読み直す必要がある根拠）
per_variant = {}
for d in SAMPLE_DIRS:
    for p in sorted(glob.glob(os.path.join(d, "index-*.html"))):
        html = open(p, encoding="utf-8").read()
        per_variant.setdefault(os.path.basename(d), []).append(
            tuple(sorted(
                (a, bridge.read_section_marker(html, a))
                for a in bridge.list_page_addrs(html) if bridge.pool_for_addr(a)
            ))
        )
same = [k for k, v in per_variant.items() if len(set(v)) != len(v)]
check(
    "S4 3案の型の組合せが案ごとに相違する（案切替で読み直す必要がある根拠）",
    not same,
    "案間で同一の見本=%s" % (same or "なし"),
)

# graceful（ブリッジ未起動時の案内）が残っていること
missing_graceful = [
    rel(os.path.join(d, "compare.html"))
    for d in SAMPLE_DIRS
    if "ローカルブリッジ未起動" not in open(os.path.join(d, "compare.html"), encoding="utf-8").read()
]
check(
    "S5 ブリッジ未起動時の graceful な案内が残っている",
    not missing_graceful,
    "案内が無い=%s" % (missing_graceful or "なし"),
)

# 外部依存ゼロ（NFR-005）— localhost は除外
external = []
for d in SAMPLE_DIRS:
    for p in sorted(glob.glob(os.path.join(d, "*.html"))):
        html = open(p, encoding="utf-8").read()
        for u in re.findall(r'https?://[^"\'\s)]+', html):
            if not re.match(r"https?://(127\.0\.0\.1|localhost)(:|/)", u) and "w3.org" not in u:
                external.append("%s -> %s" % (rel(p), u))
check(
    "S6 見本に外部URLが無い（NFR-005・localhost は例外）",
    not external,
    external or "なし",
)

print("=" * 78)
print("KLK-078 型入れ替えの土台（番地の実ページ化・現在型の読み取り）静的チェック")
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
