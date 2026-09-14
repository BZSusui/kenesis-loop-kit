#!/usr/bin/env python3
"""
KLK-119 acceptance-condition checker — 背景トーン（`bgTone`）を主配色と別の2軸目として足す。

★経緯（2026-09-11 のフィードバック・2026-09-14 着手）
  「カタログの主配色にモノトーンはあるが**ホワイト・ブラックが無い**。
    背景で白や黒を使いつつモノトーンでない配色のラフが選びにくい」

  主配色（`CANONICAL_COLORS`）へ「ホワイト」「ブラック」を足す案もあったが採らなかった。
  主配色の正は `palette/index.html` の **色相ファミリー16種**であり、白黒は色相ではなく
  **背景の明暗**なので軸が違う。同じ軸に混ぜると「メインカラー＝白」から配色を作る意味が
  立たず、KLK-067 の「タグ付けと配色生成が同じ言葉を話す」原則も崩れる。
  → **主配色は触らず、2軸目 `bgTone` を足す**（理恵さん判断・2026-09-14）。

★この checker が守っているもの
  V. 語彙が縦串で一致すること（bridge が正・画面・ワイヤー・規約が写し）
  A. **additive であること** — 既存167件は未設定のまま妥当であり続ける
  B. 検証が効くこと（語彙外を弾く・任意項目として扱う）
  U. 画面が絞り込みと承認フォームを持ち、主配色のチップ数を汚さないこと
  D. 規約とスキルに「主配色に足さない理由」と「付ける基準」が書かれていること

Run: python3 tests/site/check_klk119.py
"""
import importlib.util
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT_HTML = io.open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()
WIRE = io.open(os.path.join(ROOT, "docs", "wireframes", "SCR-004-catalog.html"), encoding="utf-8").read()
RULES = io.open(os.path.join(ROOT, ".claude", "skills", "catalog-import",
                             "templates", "CATALOG_RULES.md"), encoding="utf-8").read()
SKILL = io.open(os.path.join(ROOT, ".claude", "skills", "catalog-import", "SKILL.md"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def load_bridge():
    path = os.path.join(ROOT, "draft-gen", "bridge.py")
    spec = importlib.util.spec_from_file_location("bridge_klk119", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def js_array(src, name):
    """`var NAME = ["a","b"];` の中身を返す（純粋関数・wrapper が使う）。"""
    m = re.search(r"var\s+%s\s*=\s*\[(.*?)\]\s*;" % re.escape(name), src, re.S)
    if not m:
        return None
    return re.findall(r'"([^"]+)"', m.group(1))


bridge = load_bridge()
ORDER = bridge.CANONICAL_BG_TONES_ORDER

# ---------------------------------------------------------------------------
# V. 語彙の縦串
# ---------------------------------------------------------------------------
check("V1 bridge が語彙を持つ（正・ライト/ダークの2値・順序つき）",
      ORDER == ["ライト", "ダーク"] and bridge.CANONICAL_BG_TONES == set(ORDER),
      "順序=%s 集合=%s" % (ORDER, sorted(bridge.CANONICAL_BG_TONES)))

cat_js = js_array(CAT_HTML, "CANONICAL_BG_TONES")
check("V2 SCR-004 の語彙が bridge と順序まで一致する",
      cat_js == ORDER, "画面=%s / bridge=%s" % (cat_js, ORDER))

chips = re.findall(r'<span class="fchip tone" data-val="([^"]+)"', CAT_HTML)
check("V3 SCR-004 の絞り込みチップが語彙と一致する",
      chips == ORDER, "チップ=%s" % chips)

wire_chips = re.findall(r'<span class="fchip tone"[^>]*>.*?</span>\s*([^<]+)</span>', WIRE)
check("V4 ワイヤー SCR-004 にも背景トーンの行がある（KLK-016 の流儀）",
      "背景トーン" in WIRE and all(v in WIRE for v in ORDER),
      "行=%s 値=%s" % ("背景トーン" in WIRE, [v for v in ORDER if v in WIRE]))

check("V5 規約に語彙が載っている（正は bridge と明記）",
      all(v in RULES for v in ORDER) and "CANONICAL_BG_TONES_ORDER" in RULES,
      "値=%s 正の明記=%s" % (all(v in RULES for v in ORDER), "CANONICAL_BG_TONES_ORDER" in RULES))

# ---------------------------------------------------------------------------
# A. additive — 既存データを壊さない
# ---------------------------------------------------------------------------
cat_path = os.path.join(ROOT, "catalog", "catalog.json")
if os.path.isfile(cat_path):
    real = json.load(io.open(cat_path, encoding="utf-8"))
    ok, errs = bridge.validate_catalog(real)
    n = len(real.get("entries", []))
    tagged = sum(1 for e in real.get("entries", []) if e.get("bgTone"))
    check("A1 ★既存カタログが未設定のまま妥当（additive・付与は別作業）",
          ok, "%d件 検証=%s 付与済み=%d件 %s" % (n, ok, tagged, errs[:2]))
else:
    check("A1 ★既存カタログが未設定のまま妥当（additive）[SKIP]", True,
          "catalog.json が無い環境（社外秘・Git除外）")

check("A2 主配色（CANONICAL_COLORS）を触っていない（16種のまま）",
      len(bridge.CANONICAL_COLORS) == 16
      and "ホワイト" not in bridge.CANONICAL_COLORS
      and "ブラック" not in bridge.CANONICAL_COLORS,
      "%d種 / ホワイト=%s ブラック=%s" % (
          len(bridge.CANONICAL_COLORS),
          "ホワイト" in bridge.CANONICAL_COLORS, "ブラック" in bridge.CANONICAL_COLORS))

# ---------------------------------------------------------------------------
# B. 検証が効く（妨害注入つき）
# ---------------------------------------------------------------------------
def cat_with(bg):
    e = {"id": "cat-0001", "file": "cat-0001.png", "source": "own", "colors": ["ブルー"]}
    if bg is not _OMIT:
        e["bgTone"] = bg
    return {"schema": "klk-catalog", "version": 1, "entries": [e]}


_OMIT = object()
check("B1 未設定（キーなし）は妥当", bridge.validate_catalog(cat_with(_OMIT))[0], "")
for v in ORDER:
    check("B1b 語彙内 '%s' は妥当" % v, bridge.validate_catalog(cat_with(v))[0], "")

bad_ok, bad_err = bridge.validate_catalog(cat_with("ホワイト"))
assert not bad_ok, "妨害注入が効いていない（語彙外が通った）"
check("B2 妨害注入: 語彙外（'ホワイト'）を弾く",
      not bad_ok and any("bgTone" in e for e in bad_err), "理由=%s" % bad_err[:1])

null_ok, _ = bridge.validate_catalog(cat_with(None))
check("B3 null は未設定と同じ扱い（任意項目）", null_ok, "")

prop = {"schema": bridge.PROPOSAL_SCHEMA, "version": bridge.PROPOSAL_VERSION,
        "jobId": "abc", "items": [{"file": "a.png", "bgTone": "ダーク"}]}
ok_p, _ = bridge.validate_proposal(prop)
prop_bad = json.loads(json.dumps(prop))
prop_bad["items"][0]["bgTone"] = "グレー"
ok_pb, err_pb = bridge.validate_proposal(prop_bad)
assert not ok_pb, "妨害注入が効いていない（取り込み案で語彙外が通った）"
check("B4 取り込み案（proposal）でも語彙を検証する",
      ok_p and not ok_pb and any("bgTone" in e for e in err_pb), "正=%s 誤=%s" % (ok_p, err_pb[:1]))

# ---------------------------------------------------------------------------
# U. 画面
# ---------------------------------------------------------------------------
check("U1 絞り込みの状態に bgTone がある",
      re.search(r"var sel = \{[^}]*bgTone:\s*\[\]", CAT_HTML) is not None,
      "sel.bgTone=%s" % (re.search(r"bgTone:\s*\[\]", CAT_HTML) is not None))

check("U2 絞り込み判定が bgTone を見る（未設定は、トーンを選んだときは出ない）",
      "s.bgTone.indexOf(e.bgTone) < 0" in CAT_HTML,
      "判定=%s" % ("s.bgTone.indexOf(e.bgTone) < 0" in CAT_HTML))

check("U3 承認フォームに背景トーンの選択がある（未設定を選べる）",
      "data-bgtone" in CAT_HTML and "（未設定）" in CAT_HTML,
      "入力=%s 未設定=%s" % ("data-bgtone" in CAT_HTML, "（未設定）" in CAT_HTML))

check("U4 未設定を選ぶとキーごと落とす（空文字を書き込まない）",
      "delete it.bgTone" in CAT_HTML, "delete=%s" % ("delete it.bgTone" in CAT_HTML))

color_chips = re.findall(r'<span class="fchip color" data-val="([^"]+)"', CAT_HTML)
check("U5 ★主配色のチップ数を汚していない（16件のまま・check_klk013 S3 と両立）",
      len(color_chips) == 16 and not (set(color_chips) & set(ORDER)),
      "主配色チップ=%d件 / トーンの混入=%s" % (len(color_chips), sorted(set(color_chips) & set(ORDER))))

# ---------------------------------------------------------------------------
# D. 規約・スキル
# ---------------------------------------------------------------------------
check("D1 規約に「主配色へ足さない理由」が書かれている",
      "主配色に「ホワイト」「ブラック」を足さない" in RULES and "色相ではなく" in RULES,
      "理由=%s" % ("主配色に「ホワイト」「ブラック」を足さない" in RULES))

check("D2 規約に付ける基準がある（ライト/ダークそれぞれ）",
      "大部分の背景が白〜淡色" in RULES and "大部分の背景が黒〜濃色" in RULES,
      "基準=%s" % ("大部分の背景が白〜淡色" in RULES))

check("D3 規約が「迷ったら付けない」と言っている（嘘の絞り込みを作らない）",
      "判断が割れるもの" in RULES and "付けない" in RULES,
      "記載=%s" % ("判断が割れるもの" in RULES))

check("D4 規約が主配色モノトーンとの違いを明示している",
      "`モノトーン`（主配色）と `ライト`/`ダーク`（背景トーン）は**別物**" in RULES,
      "記載=%s" % ("は**別物**" in RULES))

check("D5 取り込みスキルが bgTone を推定項目に挙げている",
      "**背景トーン**(`bgTone`)" in SKILL and "判断が割れるものは付けない" in SKILL,
      "記載=%s" % ("**背景トーン**(`bgTone`)" in SKILL))

print("=" * 78)
print("KLK-119 背景トーン（bgTone）を主配色と別の2軸目として足す チェック")
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
