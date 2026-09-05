#!/usr/bin/env python3
"""
KLK-087 acceptance-condition checker (static / no browser required).

ページ構成（composition）— 同一セクションの複数配置・並び順・エントリ個別設定。
設計は docs/designs/KLK-086.md（086〜090 共通）。

★このチェッカーが守っているもの:
  ① **後方互換** — 既存の使い方をしている限り、生成指示書の出力が1バイトも変わらないこと。
     ここが崩れると、これまでの見本・golden・実運用がすべて巻き添えになる。
     （実挙動は smoke_klk087.node.js の P群が buildInstruction を実際に呼んで確かめる）
  ② **語彙のドリフト** — 型プールは規約（§12.1.2/§12.1.3）が正で、bridge.py と index.html は写し。
     3者がずれると「画面で選べるのに生成できない型」が生まれる。
  ③ **UI が嘘をつかない** — 生成へ反映されるのは KLK-088 からなので、それまでは画面にそう書く
     （KLK-061 と同じ「消し忘れ防止装置」。088 で注記を消すとき D2 が意図的に FAIL する）。

  R群 = 設計書 / L群 = 純ロジック / V群 = 語彙の一致 / U群 = UI / D群 = 実装中の正直さ

Run: python3 tests/site/check_klk087.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

INDEX = io.open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
DESIGN_PATH = os.path.join(ROOT, "docs", "designs", "KLK-086.md")
DESIGN = io.open(DESIGN_PATH, encoding="utf-8").read() if os.path.isfile(DESIGN_PATH) else ""
LOGIC = INDEX[INDEX.find("const COLUMN_KEYS"):INDEX.find("\nfunction render() {")]

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ===========================================================================
# R群 — 設計書
# ===========================================================================
check(
    "R1 設計書 docs/designs/KLK-086.md がある（086〜090 共通）",
    bool(DESIGN) and "KLK-087" in DESIGN and "KLK-090" in DESIGN,
    "設計書=%s（%d字）" % (bool(DESIGN), len(DESIGN)),
)
check(
    "R2 設計書が後方互換の要（plain なら composition を出さない）を明記している",
    "出力しない" in DESIGN and "バイト不変" in DESIGN,
    "出力しない=%s / バイト不変=%s" % ("出力しない" in DESIGN, "バイト不変" in DESIGN),
)
_R3 = ("全案共通", "本文合計", "レイアウト型", "インスタンス補正")
check(
    "R3 設計書が理恵さんの決定4件（並び全案共通・複製上限・個別設定・型の自動振り）を記録している",
    all(t in DESIGN for t in _R3),
    "欠け=%s" % ([t for t in _R3 if t not in DESIGN] or "なし"),
)
check(
    "R4 設計書が CTA を複製可としている（理恵さんの修正指示）",
    "CTA" in DESIGN and "同一内容" in DESIGN,
    "CTA複製可=%s" % ("同一内容" in DESIGN),
)

# ===========================================================================
# L群 — 純ロジック（render() より前＝スモークが slice する領域にあること）
# ===========================================================================
for fn in ("normalizeComposition", "normalizeCompositionEntry",
           "isPlainComposition", "normalizeMoreLink", "maxInstancesFor"):
    check(
        "L1 純関数 %s が render() より前にある（スモークで動かせる）" % fn,
        ("function %s" % fn) in LOGIC,
        "位置=%s" % (("function %s" % fn) in LOGIC),
    )

check(
    "L2 上限の定数が定義されている（各3個・合計12個・1個のみの3種）",
    "COMPOSITION_MAX_PER_KEY = 3" in LOGIC
    and "COMPOSITION_MAX_TOTAL = 12" in LOGIC
    and re.search(r"SECTION_MAX_INSTANCES\s*=\s*\{[^}]*ACCESS:\s*1[^}]*CONTACT:\s*1[^}]*SEARCH:\s*1", LOGIC),
    "各3=%s / 合計12=%s / 1個のみ3種=%s"
    % ("COMPOSITION_MAX_PER_KEY = 3" in LOGIC, "COMPOSITION_MAX_TOTAL = 12" in LOGIC,
       bool(re.search(r"SECTION_MAX_INSTANCES\s*=\s*\{[^}]*ACCESS:\s*1", LOGIC))),
)
check(
    "L3 CTA が「1個のみ」に入っていない（理恵さんの指示で複製可）",
    not re.search(r"SECTION_MAX_INSTANCES\s*=\s*\{[^}]*CTA", LOGIC),
    "CTAが1個制限に含まれる=%s" % bool(re.search(r"SECTION_MAX_INSTANCES\s*=\s*\{[^}]*CTA", LOGIC)),
)
check(
    "L4 buildInstruction が plain のとき composition を出さない",
    "if (emitComposition) { out.composition = _comp.entries; }" in LOGIC
    and "!isPlainComposition(_comp.entries, _comp.sections)" in LOGIC,
    "条件付き出力=%s" % ("if (emitComposition) { out.composition = _comp.entries; }" in LOGIC),
)
check(
    "L5 型の判定が許可リスト（そのKEYのプールに載っているか）",
    "pool.indexOf(type) >= 0" in LOGIC,
    "許可リスト=%s" % ("pool.indexOf(type) >= 0" in LOGIC),
)
check(
    "L6 moreLink が外部URLを弾く（§4.3・§1 外部依存ゼロ）",
    re.search(r"!/\^\[a-z\]\[a-z0-9\+\.\-\]\*:/i\.test\(href\)", LOGIC) is not None,
    "スキーム付きURLを弾く=%s"
    % (re.search(r"!/\^\[a-z\]\[a-z0-9\+\.\-\]\*:/i\.test\(href\)", LOGIC) is not None),
)
check(
    "L7 第1インスタンスの見出しを sectionOptions へも載せる（旧読み手への graceful degradation）",
    "const t = _comp ? (firstOf[key] || {}) : (texts[key] || {});" in LOGIC
    and "graceful degradation" in LOGIC,
    "写し=%s / 意図の明記=%s"
    % ("firstOf[key]" in LOGIC, "graceful degradation" in LOGIC),
)

# ===========================================================================
# V群 — 語彙のドリフト検出（規約 → bridge.py → index.html）
# ===========================================================================
m = re.search(r"const SECTION_TYPE_POOLS\s*=\s*\{(.*?)\n\};", LOGIC, re.S)
js_pools = {}
if m:
    for line in m.group(1).splitlines():
        mm = re.match(r"\s*([A-Z]+):\s*\[(.*?)\],", line)
        if mm:
            js_pools[mm.group(1)] = [t.strip().strip("'") for t in mm.group(2).split(",")]
py_pools = {k: list(v) for k, v in bridge.SECTION_TYPE_POOLS.items()}
# ★MV(HERO) は本文構成に置くものではない（常に先頭に1つ・並び替えも複製もしない）ので、
#   画面側の写しには**意図的に含めない**。差はここだけであるべき。
_expected_missing = {"MV"}
_missing = set(py_pools) - set(js_pools)
_extra = set(js_pools) - set(py_pools)
_diff_values = [k for k in js_pools if js_pools.get(k) != py_pools.get(k)]
check(
    "V1 index.html の型プールが bridge.py と一致（順序も。MV=HERO のみ意図的に対象外）",
    _missing == _expected_missing and not _extra and not _diff_values,
    "画面側に無い=%s（期待 %s） / 余分=%s / 中身の相違=%s"
    % (sorted(_missing), sorted(_expected_missing), sorted(_extra) or "なし", _diff_values or "なし"),
)
check(
    "V2 CTA には型プールが無い（§4.4 で自動整列するため選ばせる型がない）",
    "CTA" not in js_pools and "CTA" not in py_pools,
    "JS=%s / PY=%s" % ("CTA" in js_pools, "CTA" in py_pools),
)

# ===========================================================================
# U群 — UI
# ===========================================================================
check(
    "U1 ページ構成リストの要素がある（一覧・追加ボタン・件数表示）",
    all(t in INDEX for t in ('id="compList"', 'id="compAddBtns"', 'id="compCount"')),
    "要素=%s" % all(t in INDEX for t in ('id="compList"', 'id="compAddBtns"', 'id="compCount"')),
)
check(
    "U2 並び替え・複製・削除・設定のボタンがある",
    all(t in INDEX for t in ("'↑', '上へ移動'", "'↓', '下へ移動'", "'複製'", "'削除'")),
    "ボタン=%s" % all(t in INDEX for t in ("'↑', '上へ移動'", "'↓', '下へ移動'", "'複製'", "'削除'")),
)
check(
    "U3 状態を配列（compState）で持ち、DOM を状態の置き場にしていない",
    "let compState = [" in INDEX and "DOM を状態の置き場にしない" in INDEX,
    "配列で保持=%s / 意図の明記=%s"
    % ("let compState = [" in INDEX, "DOM を状態の置き場にしない" in INDEX),
)
check(
    "U4 動的値を textContent で描画する（注入対策）",
    "desc.textContent = compSummary(e)" in INDEX and "b.textContent = text" in INDEX,
    "textContent=%s" % ("desc.textContent = compSummary(e)" in INDEX),
)
check(
    "U5 旧チェックボックスUI（input[name=section]）が残っていない",
    'name="section"' not in INDEX and "input[name=section]" not in INDEX,
    "旧UIの残存=%s" % ('name="section"' in INDEX or "input[name=section]" in INDEX),
)
check(
    "U6 上限に達したら追加・複製を無効化する",
    "function compCanAdd(key)" in INDEX and "!compCanAdd(k)" in INDEX and "!compCanAdd(e.key)" in INDEX,
    "無効化=%s" % ("!compCanAdd(e.key)" in INDEX),
)

# ===========================================================================
# M群 — 並べ替え（KLK-091・ドラッグ&ドロップ）
# ===========================================================================
check(
    "M1 並べ替えの実処理が compMove 1本に集約されている（↑↓ とドラッグで別実装にしない）",
    # compMove / renderComposition は render() より後（構成リストの描画側）にあるので INDEX で見る
    "function compMove(from, to)" in INDEX
    and INDEX.count("compMove(idx,") == 2          # ↑ と ↓
    and "compMove(compDragFrom, to)" in INDEX,     # ドロップ
    "compMove 定義=%s / ↑↓ からの呼び出し=%d箇所 / ドロップから=%s"
    % ("function compMove(from, to)" in INDEX, INDEX.count("compMove(idx,"),
       "compMove(compDragFrom, to)" in INDEX),
)
check(
    "M2 つまみ（グリップ）だけが draggable（行や入力欄には付けない）",
    "grip.setAttribute('draggable', 'true')" in INDEX
    and "row.setAttribute('draggable'" not in INDEX,
    "グリップに付与=%s / 行に付与=%s"
    % ("grip.setAttribute('draggable', 'true')" in INDEX, "row.setAttribute('draggable'" in INDEX),
)
check(
    "M3 dragover で preventDefault し dropEffect を move にする",
    "ev.preventDefault();                       // これが無いと drop が起きない" in INDEX
    and "ev.dataTransfer.dropEffect = 'move'" in INDEX,
    "preventDefault=%s / dropEffect=%s"
    % ("これが無いと drop が起きない" in INDEX, "ev.dataTransfer.dropEffect = 'move'" in INDEX),
)
check(
    "M4 Firefox 対策で setData を呼んでいる（データが無いとドラッグが始まらない）",
    "dataTransfer.setData('text/plain'" in INDEX,
    "setData=%s" % ("dataTransfer.setData('text/plain'" in INDEX),
)
check(
    "M5 ↑↓ ボタンは残っている（ドラッグが使えない場面の手段を消さない）",
    "'↑', '上へ移動'" in INDEX and "'↓', '下へ移動'" in INDEX,
    "↑↓=%s" % ("'↑', '上へ移動'" in INDEX),
)

# ===========================================================================
# D群 — 実装中の正直さ（KLK-088 で消す注記）
# ===========================================================================
check(
    "D1 生成へ未反映であることを画面に明示している（KLK-088 まで）",
    'id="compPendingNote"' in INDEX and "まだ生成には反映されません" in INDEX,
    "注記=%s" % ("まだ生成には反映されません" in INDEX),
)
check(
    "D2 ★KLK-088 で生成対応したら、この注記を消して D1/D2 を更新すること（消し忘れ防止装置）",
    "KLK-088 で対応" in INDEX,
    "装置=%s（088 完了時にここを『注記が無いこと』の検査へ更新する）" % ("KLK-088 で対応" in INDEX),
)

# 動的スモークの存在（静的一致だけに頼らない）
SMOKE = os.path.join(ROOT, "tests", "site", "smoke_klk087.node.js")
smoke_src = io.open(SMOKE, encoding="utf-8").read() if os.path.isfile(SMOKE) else ""
check(
    "D3 実挙動を確かめる動的スモークがある（後方互換の一致を実際に突き合わせる）",
    bool(smoke_src) and "P1 従来の sections 指定と composition" in smoke_src,
    "smoke_klk087.node.js=%s" % bool(smoke_src),
)

print("=" * 78)
print("KLK-087 ページ構成（composition）静的チェック")
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
