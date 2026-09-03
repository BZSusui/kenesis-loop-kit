#!/usr/bin/env python3
"""
KLK-079 acceptance-condition checker (static / no browser required).

生成後の型入れ替え（`desiredType`）の end-to-end。

★このチェッカーが守っているもの:
  型入れ替えは「ブリッジが指示 → LLM が生成 → 守ったかは誰も見ていない」という、
  このリポジトリが**4回失敗している形**そのもの（KLK-064 の登録未到達、KLK-072〜076 の規約無視）。
  そこで **ブリッジが後段で実ファイルを読み、型が変わったかを確かめる**装置を入れた。
  この装置と、それを支える語彙・優先順位・UI が揃っていることを見張る。

  R群 = 規約 / K群 = スキル / B群 = ブリッジ実装 / S群 = 見本の compare.html

Run: python3 tests/site/check_klk079.py
"""
import glob
import inspect
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
SKILL = open(
    os.path.join(ROOT, ".claude", "skills", "draft-regenerate", "SKILL.md"), encoding="utf-8"
).read()
BRIDGE_SRC = open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def rel(p):
    return os.path.relpath(p, ROOT)


# ===========================================================================
# R群 — 規約
# ===========================================================================
check(
    "R1 §14 が型の決め方の優先順位（desiredType > 現行マーカー > 表引き）を表で示している",
    "★型の決め方の優先順位（KLK-079）" in RULES
    and "`desiredType`があるときは" in RULES.replace(" ", "").replace("**", "")
    and "表引き" in RULES,
    "優先順位の節=%s" % ("★型の決め方の優先順位（KLK-079）" in RULES),
)

check(
    "R2 §14 が「旧マーカーを外す」ことを求めている（2つ付いたままにしない）",
    "旧マーカーは必ず外す" in RULES,
    "明記=%s" % ("旧マーカーは必ず外す" in RULES),
)

check(
    "R3 §14 が横断ルール（§3.0/§8.1）は型定義より優先すると再掲している",
    "横断ルールは型定義より優先する" in RULES.replace("**", ""),
    "再掲=%s" % ("横断ルールは型定義より優先する" in RULES.replace("**", "")),
)

check(
    "R4 §14 がブリッジの後段検証（typeApplied）を規定している",
    "ブリッジが後段で検証する（KLK-079・黙って成功と言わせない）" in RULES
    and "`typeApplied`" in RULES,
    "後段検証=%s" % ("ブリッジが後段で検証する（KLK-079・黙って成功と言わせない）" in RULES),
)

check(
    "R5 §14 が「4回失敗している形」を根拠として残している（再発の目印）",
    "4回失敗している" in RULES,
    "根拠=%s" % ("4回失敗している" in RULES),
)

check(
    "R6 §13 が型セレクタと、現在と違うときだけ desiredType を載せることを規定",
    "型 `<select id=\"regen-type\">`（KLK-079）" in RULES
    and "現在と違う型が選ばれているときだけ" in RULES,
    "型select=%s / 差分のみ送信=%s"
    % (
        '型 `<select id="regen-type">`（KLK-079）' in RULES,
        "現在と違う型が選ばれているときだけ" in RULES,
    ),
)

check(
    "R7 §13 が typeApplied=false を成功と同じ見た目にしないと規定",
    "結果を正直に出す（KLK-079）" in RULES and "成功と同じ見た目にしない" in RULES,
    "明記=%s" % ("成功と同じ見た目にしない" in RULES),
)

# ===========================================================================
# K群 — スキル
# ===========================================================================
check(
    "K1 スキルが desiredType を最優先すると明記している",
    "★型指定の最優先(KLK-079・`desiredType`)" in SKILL
    and "表引きも参考準拠の現行マーカーも見ず" in SKILL,
    "最優先=%s" % ("★型指定の最優先(KLK-079・`desiredType`)" in SKILL),
)

check(
    "K2 スキルが「元の型マーカーを外す」ことを求めている",
    "元の型マーカーは必ず外す" in SKILL,
    "明記=%s" % ("元の型マーカーは必ず外す" in SKILL),
)

check(
    "K3 スキルが自己確認（マーカーがちょうど1つ・他が残っていない）を求めている",
    "ちょうど1つ" in SKILL and "残っていない" in SKILL,
    "自己確認=%s" % ("ちょうど1つ" in SKILL),
)

check(
    "K4 スキルがブリッジの後段検証を知っている（黙って成功と言えない）",
    "typeApplied" in SKILL and "黙って成功と言えない" in SKILL,
    "認識=%s" % ("黙って成功と言えない" in SKILL),
)

check(
    "K5 スキルの入力仕様に desiredType（任意）が載っている",
    "desiredType?" in SKILL,
    "仕様=%s" % ("desiredType?" in SKILL),
)

check(
    "K6 プールマーカー再付与が「desiredType が無いとき」に限定されている",
    "**`desiredType` が無いとき**に適用する" in SKILL,
    "限定=%s" % ("**`desiredType` が無いとき**に適用する" in SKILL),
)

# ===========================================================================
# B群 — ブリッジ実装
# ===========================================================================
check(
    "B1 /regenerate が desiredType を許可リストで検証する",
    "is_valid_desired_type(addr, desired)" in BRIDGE_SRC
    and "desiredType が不正です" in BRIDGE_SRC,
    "検証=%s" % ("is_valid_desired_type(addr, desired)" in BRIDGE_SRC),
)

check(
    "B2 拒否時に選べる型（pool）を返す",
    '"pool": list(pool)' in BRIDGE_SRC,
    "pool返却=%s" % ('"pool": list(pool)' in BRIDGE_SRC),
)

check(
    "B3 ジョブ仕様へは型指定があるときだけ書く（後方互換）",
    'if desired:' in BRIDGE_SRC and 'spec["desiredType"] = desired' in BRIDGE_SRC,
    "条件付き書出し=%s" % ('spec["desiredType"] = desired' in BRIDGE_SRC),
)

_sig = inspect.signature(bridge._run_server) if hasattr(bridge, "_run_server") else None
check(
    "B4 worker が実ファイルで検証し、**指定の型がちょうど1つ**を要求する",
    "read_section_markers(fh.read(), addr)" in BRIDGE_SRC
    and "type_applied = (hits == [desired])" in BRIDGE_SRC,
    "後段検証=%s / ちょうど1つ=%s"
    % (
        "read_section_markers(fh.read(), addr)" in BRIDGE_SRC,
        "type_applied = (hits == [desired])" in BRIDGE_SRC,
    ),
)

# ★旧マーカーの外し忘れを見逃さないこと（実装レビューで見つかった穴）
_two = (
    '<section class="sec"><div class="addr"><span class="pin">GALLERY-01</span></div>'
    '<div class="m-gallery pat-grid pat-masonry"></div></section>'
)
_one = _two.replace(" pat-grid", "")
check(
    "B4b read_section_markers が複数マーカーを畳まずに返す（外し忘れの検出）",
    bridge.read_section_markers(_two, "GALLERY-01") == ["pat-grid", "pat-masonry"]
    and bridge.read_section_markers(_one, "GALLERY-01") == ["pat-masonry"]
    and bridge.read_section_markers(_two, "NAV-01") == [],
    "2つ=%s / 1つ=%s"
    % (
        bridge.read_section_markers(_two, "GALLERY-01"),
        bridge.read_section_markers(_one, "GALLERY-01"),
    ),
)

check(
    "B4c 外し忘れのときメッセージで理由が分かる",
    "古い型が残っています" in BRIDGE_SRC,
    "理由の明示=%s" % ("古い型が残っています" in BRIDGE_SRC),
)

# 型マーカーは class でも data-* でも付く（見本の MENU は data-menu）。
# 検出は**属性に依存しない**こと＝どちらの書き方でも読めること。
_cls = ('<section class="sec"><div class="addr"><span class="pin">MENU-01</span></div>'
        '<div class="m-menu tab-switch"></div></section>')
_attr = ('<section class="sec"><div class="addr"><span class="pin">MENU-01</span></div>'
         '<div class="m-menu" data-menu="tab-switch"></div></section>')
check(
    "B4d 型マーカーが class でも data-* でも読める（見本の MENU は data-menu）",
    bridge.read_section_markers(_cls, "MENU-01") == ["tab-switch"]
    and bridge.read_section_markers(_attr, "MENU-01") == ["tab-switch"],
    "class=%s / data-*=%s"
    % (bridge.read_section_markers(_cls, "MENU-01"), bridge.read_section_markers(_attr, "MENU-01")),
)

check(
    "B5 反映されなかったとき、メッセージが成功と区別できる",
    "型は {0} になりませんでした" in BRIDGE_SRC,
    "区別=%s" % ("型は {0} になりませんでした" in BRIDGE_SRC),
)

check(
    "B6 /status が typeApplied と desiredType を返す",
    '"typeApplied": job.get("typeApplied")' in BRIDGE_SRC
    and '"desiredType": job.get("desiredType")' in BRIDGE_SRC,
    "status拡張=%s" % ('"typeApplied": job.get("typeApplied")' in BRIDGE_SRC),
)

check(
    "B7 後段検証の失敗をサーバコンソールにも残す（黙らせない）",
    "型が反映されませんでした addr=" in BRIDGE_SRC,
    "ログ=%s" % ("型が反映されませんでした addr=" in BRIDGE_SRC),
)

# 純関数の実挙動（KLK-078 の語彙を KLK-079 の入口で使えていること）
check(
    "B8 is_valid_desired_type が入口として機能する（語彙外・型なし番地を弾く）",
    bridge.is_valid_desired_type("MENU-01", "pat-list")
    and not bridge.is_valid_desired_type("MENU-01", "pat-grid")
    and not bridge.is_valid_desired_type("NAV-01", "pat-list")
    and bridge.is_valid_desired_type("MENU-01", None),
    "pat-list=%s / GALLERY型=%s / NAV=%s"
    % (
        bridge.is_valid_desired_type("MENU-01", "pat-list"),
        bridge.is_valid_desired_type("MENU-01", "pat-grid"),
        bridge.is_valid_desired_type("NAV-01", "pat-list"),
    ),
)

# ===========================================================================
# S群 — 見本の compare.html
# ===========================================================================
SAMPLE_DIRS = sorted(d for d in glob.glob(os.path.join(ROOT, "samples", "*")) if os.path.isdir(d))
miss_sel, miss_diff, miss_warn, miss_disabled = [], [], [], []
for d in SAMPLE_DIRS:
    p = os.path.join(d, "compare.html")
    if not os.path.isfile(p):
        continue
    html = open(p, encoding="utf-8").read()
    if '<select id="regen-type"' not in html:
        miss_sel.append(rel(p))
    if "typeSel.value !== s.current" not in html:
        miss_diff.append(rel(p))
    if "typeApplied === false" not in html:
        miss_warn.append(rel(p))
    if "この番地に型はありません" not in html or "typeSel.disabled = true" not in html:
        miss_disabled.append(rel(p))

check(
    "S1 見本の compare.html が型 <select> を持つ",
    not miss_sel, "欠け=%s" % (miss_sel or "なし"),
)
check(
    "S2 現在と違う型のときだけ desiredType を送る",
    not miss_diff, "欠け=%s" % (miss_diff or "なし"),
)
check(
    "S3 typeApplied=false を成功と同じ見た目にしない",
    not miss_warn, "欠け=%s" % (miss_warn or "なし"),
)
check(
    "S4 プール無しの番地で型セレクタを無効化する",
    not miss_disabled, "欠け=%s" % (miss_disabled or "なし"),
)

# 番地の焼き込み（KLK-078 の回帰）と外部URL（NFR-005）を引き続き見張る
baked, external = [], []
for d in SAMPLE_DIRS:
    for p in sorted(glob.glob(os.path.join(d, "*.html"))):
        html = open(p, encoding="utf-8").read()
        if os.path.basename(p) == "compare.html" and re.search(
            r'<option value="[A-Z][A-Z0-9]*-\d{2}"', html
        ):
            baked.append(rel(p))
        for u in re.findall(r'https?://[^"\'\s)]+', html):
            if not re.match(r"https?://(127\.0\.0\.1|localhost)(:|/)", u) and "w3.org" not in u:
                external.append("%s -> %s" % (rel(p), u))
check("S5 番地の焼き込みが復活していない（KLK-078 の回帰）", not baked, baked or "なし")
check("S6 見本に外部URLが無い（NFR-005）", not external, external or "なし")

# 静的検査は compare.html を文字列一致で見ているだけなので、
# 「その文字列はあるが動かない」を検出できない。実挙動は動的スモークが担う。
_SMOKE = os.path.join(ROOT, "tests", "site", "smoke_klk079.node.js")
check(
    "S7 UI の実挙動を確かめる動的スモークがある（文字列一致だけに頼らない）",
    os.path.isfile(_SMOKE)
    and "typeApplied" in open(_SMOKE, encoding="utf-8").read()
    and "desiredType" in open(_SMOKE, encoding="utf-8").read(),
    "smoke_klk079.node.js=%s" % os.path.isfile(_SMOKE),
)

print("=" * 78)
print("KLK-079 生成後の型入れ替え（desiredType）静的チェック")
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
