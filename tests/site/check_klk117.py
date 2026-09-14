#!/usr/bin/env python3
"""
KLK-117 acceptance-condition checker — 型セレクタの日本語ラベル。

★経緯（2026-09-11・実ユーザーのフィードバック）
  「生成後に型を入れ替えるとき、型名が英語のみだとどのような型なのかが掴めない」。
  84型（14セクション×6型）のマーカー（voice-slider 等）を、日本語ラベル付きで見せる。

★この checker が守っているもの
  L. ラベル表がプールと過不足なく対応し、セクション内で一意で、画面に収まる長さであること
  G. ★根拠 — **ラベルを自分で考えて自分で正しいと言わないこと**。
     各ラベルを区切り（＋／・など）で割った語の**すべて**が、
     規約 §12.1.2／§12.1.3 の**その型の説明文**に文字列として現れることを照合する。
     規約の表現を変えたのにラベルを直し忘れれば、ここが落ちる。
  B. ブリッジの純粋関数 labels_for_addr が番地から正しく引けること（型を持たない番地は空）
  U. 画面（compare_template.html）がラベルを使い、送る値はマーカーのままであること
  R. 規約 §13 がこの見せ方を定めていること

  動的な挙動（実ブリッジの /sections が labels を返す・画面が実際にラベルを描く）は
  tests/test_palette_klk117.py と e2e が見る。

Run: python3 tests/site/check_klk117.py
"""
import importlib.util
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES_PATH = os.path.join(ROOT, ".claude", "skills", "draft-generate", "templates", "DRAFT_RULES.md")
RULES = io.open(RULES_PATH, encoding="utf-8").read()
TEMPLATE = io.open(os.path.join(ROOT, "draft-gen", "compare_template.html"), encoding="utf-8").read()
results = []

# ラベルの区切り。ここで割った断片が規約の説明文に現れることを求める
SEPARATORS = "＋／/・（）()［］[]、。「」【】"
MAX_LABEL_LEN = 16          # <select> の1行に収まる上限（全角）


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def load_bridge():
    """bridge.py を読み込む（兄弟モジュールを import しない流儀に合わせる）。"""
    path = os.path.join(ROOT, "draft-gen", "bridge.py")
    spec = importlib.util.spec_from_file_location("bridge_klk117", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def normalize(text):
    """規約の飾り（**強調**・`コード`）を外して素の日本語にする（純粋関数）。"""
    return text.replace("**", "").replace("`", "")


def rule_description(marker, rules=RULES):
    r"""規約 §12.1.2／§12.1.3 から、その型の説明文を取り出す（純粋関数）。

    2つの書かれ方があるので両方を拾い、**見つかった全部をつなげて**返す
    （マーカーが複数セクションで共有される場合があるため／例: price-table）。
      (1) §12.1.3 の表行:  | <index> | `marker`（…） | 説明 |
      (2) §12.1.2 の散文:  `marker`（…）: 説明 …（次のマーカー定義の手前まで）
          各セクションの先頭型は `- **VOICE** — \`voice-cards\`: …` の形で始まるので、
          その前置きも受ける（ここを取りこぼすと「説明が無い」と誤判定する）。
    1つも見つからなければ空文字列（呼び手が「根拠なし」と判定する）。
    """
    lines = rules.split("\n")
    found = []

    # (1) 表行
    row_re = re.compile(r"^\|\s*\d\s*\|\s*`%s`[^|]*\|(?P<body>.+?)\|?\s*$" % re.escape(marker))
    for line in lines:
        m = row_re.match(line)
        if m:
            found.append(m.group("body"))

    # (2) 散文（`marker`（注記）: 説明 …。次のマーカー定義行まで続く）
    head_re = re.compile(
        r"^\s*(?:-\s*\*\*[A-Z]+\*\*\s*[—-]\s*)?`%s`(（[^）]*）)?\s*[:：]\s*(?P<body>.*)$"
        % re.escape(marker))
    next_re = re.compile(r"^\s*`[a-z0-9-]+`(（[^）]*）)?\s*[:：]")
    for i, line in enumerate(lines):
        m = head_re.match(line)
        if not m:
            continue
        body = [m.group("body")]
        for nxt in lines[i + 1:]:
            if next_re.match(nxt) or nxt.strip().startswith("- **") or not nxt.strip():
                # 次の型の定義・次のセクションの見出し・空行で止める
                break
            body.append(nxt)
        found.append(" ".join(body))

    return normalize(" ".join(found))


def label_terms(label):
    """ラベルを区切りで割り、2文字以上の語だけ返す（純粋関数）。"""
    out = []
    cur = ""
    for ch in label:
        if ch in SEPARATORS:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [s for s in (x.strip() for x in out) if len(s) >= 2]


bridge = load_bridge()
POOLS = bridge.SECTION_TYPE_POOLS
LABELS = bridge.SECTION_TYPE_LABELS

# ---------------------------------------------------------------------------
# L. ラベル表そのもの
# ---------------------------------------------------------------------------
missing_sec = sorted(set(POOLS) - set(LABELS))
extra_sec = sorted(set(LABELS) - set(POOLS))
check("L1 ラベル表がプールと同じ14セクションを持つ",
      not missing_sec and not extra_sec and len(LABELS) == 14,
      "欠け=%s 余り=%s 件数=%d" % (missing_sec or "なし", extra_sec or "なし", len(LABELS)))

gaps = []
for sec, pool in POOLS.items():
    table = LABELS.get(sec, {})
    for m in pool:
        if not table.get(m):
            gaps.append("%s:%s" % (sec, m))
    for m in table:
        if m not in pool:
            gaps.append("%s:%s(プール外)" % (sec, m))
total = sum(len(v) for v in LABELS.values())
check("L2 84型すべてにラベルがあり、プール外の型が混じっていない",
      not gaps and total == 84, "総数=%d 不一致=%s" % (total, gaps or "なし"))

dupes = []
for sec, table in LABELS.items():
    seen = {}
    for m, lab in table.items():
        if lab in seen:
            dupes.append("%s: %s と %s が同じ「%s」" % (sec, seen[lab], m, lab))
        seen[lab] = m
check("L3 セクション内でラベルが一意（見分けられる）",
      not dupes, "重複=%s" % (dupes or "なし"))

too_long = ["%s:%s(%d字)" % (sec, m, len(lab))
            for sec, table in LABELS.items() for m, lab in table.items()
            if len(lab) > MAX_LABEL_LEN]
check("L4 ラベルが %d 文字以内（セレクタの1行に収まる）" % MAX_LABEL_LEN,
      not too_long, "超過=%s" % (too_long or "なし"))

ascii_only = ["%s:%s=%s" % (sec, m, lab)
              for sec, table in LABELS.items() for m, lab in table.items()
              if not re.search(r"[ぁ-んァ-ヴ一-龯]", lab)]
check("L5 すべてのラベルに日本語が入っている（マーカーの言い換えだけで済ませない）",
      not ascii_only, "日本語なし=%s" % (ascii_only or "なし"))

# ---------------------------------------------------------------------------
# G. ★根拠 — ラベルの語が規約のその型の説明文に実在する
# ---------------------------------------------------------------------------
no_desc = []
ungrounded = []
for sec, table in LABELS.items():
    for m, lab in table.items():
        desc = rule_description(m)
        if not desc:
            no_desc.append("%s:%s" % (sec, m))
            continue
        for term in label_terms(lab):
            if term not in desc:
                ungrounded.append("%s:%s ラベル「%s」の語「%s」が規約の説明に無い" % (sec, m, lab, term))

check("G1 84型すべてが規約 §12.1.x に説明文を持つ（説明の無い型にラベルを付けていない）",
      not no_desc, "説明なし=%s" % (no_desc[:6] or "なし"))
check("G2 ★ラベルの語がすべて規約の説明文に実在する（言い換えて作っていない）",
      not ungrounded, "根拠なし=%s（%d件）" % (ungrounded[:4] or "なし", len(ungrounded)))

# 妨害注入: 規約に無い語を混ぜたラベルは G2 で捕まること（検査が空回りしていない証明）
probe_desc = rule_description("voice-slider")
assert probe_desc, "ハーネス異常: voice-slider の説明が取れない"
assert "横スクロール風1行" in probe_desc, "ハーネス異常: 期待した説明文でない"
sabotaged_terms = label_terms("横スクロール風1行＋架空の語句")
check("T1 妨害注入: 規約に無い語を足したラベルは根拠なしと判定される",
      any(term not in probe_desc for term in sabotaged_terms)
      and all(term in probe_desc for term in label_terms("横スクロール風1行")),
      "注入語の検知=%s" % [t for t in sabotaged_terms if t not in probe_desc])

# ---------------------------------------------------------------------------
# B. ブリッジの純粋関数
# ---------------------------------------------------------------------------
menu = bridge.labels_for_addr("MENU-01")
check("B1 labels_for_addr が番地から6型ぶんのラベルを返す",
      len(menu) == 6 and menu.get("tab-switch") == LABELS["MENU"]["tab-switch"],
      "MENU-01=%d件 tab-switch=%s" % (len(menu), menu.get("tab-switch")))

check("B2 連番が違っても同じプール（MENU-02 も MENU-01 と同じ）",
      bridge.labels_for_addr("MENU-02") == menu, "一致=%s" % (bridge.labels_for_addr("MENU-02") == menu))

check("B3 型を持たない番地・未知の番地は空（NAV/FOOTER/CTA・traversal）",
      bridge.labels_for_addr("NAV-01") == {}
      and bridge.labels_for_addr("FOOTER-01") == {}
      and bridge.labels_for_addr("CTA-01") == {}
      and bridge.labels_for_addr("../etc") == {},
      "NAV=%s CTA=%s 未知=%s" % (bridge.labels_for_addr("NAV-01"),
                                 bridge.labels_for_addr("CTA-01"),
                                 bridge.labels_for_addr("../etc")))

check("B4 セクションごとにラベルを持つ（同じマーカーでも引き先が違う）",
      "price-table" in bridge.labels_for_addr("MENU-01")
      and "price-table" in bridge.labels_for_addr("PRICE-01"),
      "MENU/PRICE 双方に price-table=%s" % (
          "price-table" in bridge.labels_for_addr("MENU-01")
          and "price-table" in bridge.labels_for_addr("PRICE-01")))

check("B5 /sections の応答に labels を載せている",
      '"labels": labels_for_addr(addr)' in io.open(
          os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read(),
      "応答へ追加=%s" % ('"labels": labels_for_addr(addr)' in io.open(
          os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()))

# ---------------------------------------------------------------------------
# U. 画面（compare_template.html）
# ---------------------------------------------------------------------------
check("U1 セレクタが labels を使って選択肢を作る",
      "var labels = s.labels || {};" in TEMPLATE and "labels[t]" in TEMPLATE,
      "labels 参照=%s" % ("labels[t]" in TEMPLATE))

check("U2 送る値はマーカーのまま（desiredType が日本語にならない）",
      re.search(r"typeSel\.appendChild\(opt\(t,", TEMPLATE) is not None,
      "opt の value が t=%s" % (re.search(r"opt\(t,", TEMPLATE) is not None))

check("U3 labels を返さない旧ブリッジではマーカーだけ出す（壊れない）",
      "labels[t] ? labels[t]" in TEMPLATE and ": t;" in TEMPLATE,
      "フォールバック=%s" % ("labels[t] ? labels[t]" in TEMPLATE))

check("U4 現在の型の「（現在）」は残っている（KLK-078/079 の不変条件）",
      "'（現在）'" in TEMPLATE, "（現在）=%s" % ("'（現在）'" in TEMPLATE))

check("U5 選択肢は textContent で入れる（注入対策・KLK-078 の流儀）",
      "o.textContent = label;" in TEMPLATE, "textContent=%s" % ("o.textContent = label;" in TEMPLATE))

# ---------------------------------------------------------------------------
# R. 規約
# ---------------------------------------------------------------------------
check("R1 §13 がラベル付きの表示を定めている",
      "日本語ラベル（マーカー）" in RULES and "KLK-117" in RULES,
      "規定=%s" % ("日本語ラベル（マーカー）" in RULES))

check("R2 §13 がラベルの出どころ（§12.1.x からの抜き書き）を定めている",
      "§12.1.2／§12.1.3 のその型の説明文からの抜き書き" in RULES,
      "出どころの明記=%s" % ("§12.1.2／§12.1.3 のその型の説明文からの抜き書き" in RULES))

check("R3 §13 が desiredType はマーカーのままと定めている",
      "送る `desiredType` はマーカーのまま" in RULES,
      "明記=%s" % ("送る `desiredType` はマーカーのまま" in RULES))

print("=" * 78)
print("KLK-117 型セレクタの日本語ラベル チェック")
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
