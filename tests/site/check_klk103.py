#!/usr/bin/env python3
"""
KLK-103 acceptance-condition checker — compare.html をテンプレートから書き出す。

★この checker が守っているもの:
  **「毎回同じものを書かせない」という決定そのもの。**

  compare.html の JS（約160行）はデザインではなく道具立てで、どの生成物でも中身は同じ。
  にもかかわらず毎回 LLM に書き起こさせていたため、KLK-079/080/081/092 で積み上げた
  振る舞いが**作り直しのたびに落ちた**。2026-09-07 の見本作り直しでは6項目中4項目が
  欠落した（KLK-102）。固定テンプレートにすればこの種の欠落が構造的に起きない。

  したがって検査するのは2つ:
    ① テンプレートが**契約を満たしている**こと（型セレクタ・見本ガード・幅切替…）
    ② 規約とスキルが**「書くな、道具を使え」と言っている**こと
  ②を落とすと、また生成させる指示に戻り、①のテンプレートが使われなくなる。

Run: python3 tests/site/check_klk103.py
Exit code 0 = all pass, 1 = at least one fail.
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import make_compare as mc  # noqa: E402

TEMPLATE = io.open(os.path.join(ROOT, "draft-gen", "compare_template.html"),
                   encoding="utf-8").read()
RULES = io.open(os.path.join(ROOT, ".claude", "skills", "draft-generate",
                             "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
SKILL = io.open(os.path.join(ROOT, ".claude", "skills", "draft-generate",
                             "SKILL.md"), encoding="utf-8").read()
BRIDGE = io.open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# ① テンプレートが契約を満たしているか
#    ここが落ちたら、全生成物が同じ欠落を抱える（＝影響は最大）
# ---------------------------------------------------------------------------
CONTRACT = [
    ('<select id="regen-addr"', "番地セレクタ", "KLK-078"),
    ('<select id="regen-type"', "型セレクタ本体（ラベルではなく select）", "KLK-079"),
    ('id="regen-btn"', "再生成ボタン", "KLK-012"),
    ('id="regen-msg"', "状態表示", "KLK-012"),
    ("typeSel.value !== s.current", "現在と違う型のときだけ desiredType を送る", "KLK-079"),
    ("typeApplied === false", "型が変わらなかったことを成功と同じ見た目にしない", "KLK-079"),
    ("この番地に型はありません", "プール無し番地の案内", "KLK-079"),
    ("typeSel.disabled = true", "プール無し番地で型セレクタを無効化", "KLK-079"),
    ("folder.indexOf('mockups/') !== 0", "見本ガード（mockups/ 外で固まらせない）", "KLK-081"),
    ("（見本では使えません）", "見本ガードの文言", "KLK-081"),
    ("function disableWith", "無効化ヘルパ", "KLK-081"),
    ('name="vw"', "画面幅切替のラジオ", "KLK-062"),
    ("原寸", "原寸リンク", "REQ-009"),
    ("🖨", "印刷導線", "REQ-009"),
    ("/health", "ブリッジ稼働判定", "KLK-012"),
    ("warnings", "品質警告の表示", "KLK-080"),
    ("@media print", "印刷時に chrome を隠す", "REQ-009"),
]
# ★契約は**組み上がった出力**で見る。原寸リンクや印刷導線は案の数だけ繰り返す部分で、
#   レンダラ側が組むのでテンプレート単体には無い（それが正しい）。
#   検査対象を間違えると「テンプレートに無い＝欠落」と誤報する（実際に一度そうなった）。
_ref = sorted(d for d in glob.glob(os.path.join(ROOT, "samples", "*")) if os.path.isdir(d))
RENDERED = mc.build_compare_html(_ref[0], data_folder="samples/x") if _ref else ""
missing = [(l, t) for n, l, t in CONTRACT if n not in RENDERED]
check("A ★組み上がった compare.html が積み上げた契約を全て満たす（%d項目）" % len(CONTRACT),
      bool(RENDERED) and not missing,
      "検査対象=%s / 欠落=%s" % (os.path.basename(_ref[0]) if _ref else "なし", missing or "なし"))

check("B テンプレートが案件の配色を CSS 変数で受ける（chrome 自身の色は固定）",
      all(v in TEMPLATE for v in ("--c-main", "--c-sub", "--c-accent", "--c-bg")),
      "変数=%s" % [v for v in ("--c-main", "--c-sub", "--c-accent", "--c-bg") if v in TEMPLATE])

check("C テンプレートに外部依存が無い（NFR-005）",
      not re.search(r'<(link|script)\b[^>]*\b(href|src)=', TEMPLATE, re.I)
      and not re.findall(r'https?://(?!127\.0\.0\.1|localhost)', TEMPLATE),
      "外部参照=%s" % (re.findall(r'https?://(?!127\.0\.0\.1|localhost)[^\s"\']+', TEMPLATE)[:2] or "なし"))

check("D テンプレート自身に案件固有の値が残っていない（前の案件の色や名前が漏れない）",
      "サンプルカフェ" not in TEMPLATE and "#6b7f4e" not in TEMPLATE,
      "案件名の残存=%s / 色の残存=%s"
      % ("サンプルカフェ" in TEMPLATE, "#6b7f4e" in TEMPLATE))

# 埋め残しを黙って出さないこと
try:
    mc.render("{{PROJECT}} {{NOT_FILLED}}", {"PROJECT": "x"})
    _raised = False
except ValueError:
    _raised = True
check("E 埋め残しがあれば例外を投げる（壊れた HTML を黙って出さない）",
      _raised, "例外=%s" % _raised)

# ---------------------------------------------------------------------------
# ② 規約とスキルが「書くな、道具を使え」と言っているか
# ---------------------------------------------------------------------------
seg = RULES[RULES.find("### ★13.0"):RULES.find("### 13.1")]
check("F 規約 §13.0 が「compare.html を書いてはならない」と明記している",
      bool(seg) and "書いてはならない" in seg and "make_compare.py" in seg,
      "節=%s / 禁止=%s / 道具=%s"
      % (bool(seg), "書いてはならない" in seg, "make_compare.py" in seg))

check("G §13.0 が理由（作り直しで4項目落ちた実害）を記録している",
      "4項目が欠落" in seg and "KLK-102" in seg,
      "実害の記録=%s" % ("4項目が欠落" in seg))

check("H §13.0 が「毎回同じものを書かせるな」を教訓として残している",
      "毎回同じものを書かせるな" in seg,
      "教訓=%s" % ("毎回同じものを書かせるな" in seg))

check("I SKILL.md が compare.html を書かず道具を実行するよう指示している",
      "make_compare.py" in SKILL and "書かない" in SKILL,
      "道具の指示=%s" % ("make_compare.py" in SKILL))

check("J ブリッジが生成後に自動で書き出す（利用者は何もしなくてよい）",
      "def write_compare_html" in BRIDGE and "write_compare_html(abs_folder" in BRIDGE
      and "make_compare.py" in BRIDGE,
      "ヘルパ=%s / 呼び出し=%s / テンプレート道具の参照=%s"
      % ("def write_compare_html" in BRIDGE, "write_compare_html(abs_folder" in BRIDGE,
         "make_compare.py" in BRIDGE))

# ★import はモジュール先頭に置かない。bridge.py は spec_from_file_location で
#   直接読み込まれるので、先頭に隣のモジュールの import を置くと checker が
#   丸ごと ModuleNotFoundError で落ちる（実際に10本落ちた・KLK-103 の実装時）。
check("J2 隣のモジュールをモジュール先頭で import していない（テストが読み込めなくなる）",
      not re.search(r"(?m)^import make_compare\b", BRIDGE)
      and not re.search(r"(?m)^from make_compare\b", BRIDGE),
      "先頭 import=%s" % bool(re.search(r"(?m)^(import|from) make_compare\b", BRIDGE)))

check("K 書き出し失敗で生成そのものを殺さない（fail-soft）",
      re.search(r"write_compare_html\(abs_folder[\s\S]{0,300}?except", BRIDGE) is not None,
      "try/except=%s"
      % (re.search(r"write_compare_html\(abs_folder[\s\S]{0,300}?except", BRIDGE) is not None))

# ---------------------------------------------------------------------------
# ③ 実際に組める・出荷物がテンプレート由来である
# ---------------------------------------------------------------------------
built = []
for folder in sorted(glob.glob(os.path.join(ROOT, "samples", "*"))):
    if not os.path.isdir(folder):
        continue
    try:
        html = mc.build_compare_html(folder, data_folder=os.path.relpath(folder, ROOT))
        built.append((os.path.basename(folder), len(html.splitlines()), None))
    except Exception as exc:      # noqa: BLE001
        built.append((os.path.basename(folder), 0, str(exc)))
check("L 見本3点すべてでテンプレートを組める",
      len(built) >= 3 and all(e is None for _, _, e in built),
      "結果=%s" % [(n, ln, e) for n, ln, e in built])

# 出荷中の見本が実際にテンプレート由来か（手書きに戻っていないか）
not_from_template = []
for p in sorted(glob.glob(os.path.join(ROOT, "samples", "*", "compare.html"))):
    h = io.open(p, encoding="utf-8").read()
    if "--c-main" not in h or "KLK-103" not in h:
        not_from_template.append(os.path.basename(os.path.dirname(p)))
check("M ★出荷中の見本の compare.html がテンプレート由来である",
      not not_from_template, "手書きのまま=%s" % (not_from_template or "なし"))

# 単案でも組めること（案切替は出さず、幅切替と 🔄 は出す）
single = None
for folder in sorted(glob.glob(os.path.join(ROOT, "mockups", "*"))):
    if os.path.isfile(os.path.join(folder, "index.html")):
        single = folder
        break
if single:
    h = mc.build_compare_html(single, data_folder=os.path.relpath(single, ROOT))
    check("N 単案でも組める。案切替は出さず、幅切替と 🔄 は出す（KLK-092）",
          'data-variants="1"' in h and 'name="variant"' not in h
          and 'name="vw"' in h and 'id="regen-btn"' in h,
          "variants=1:%s / 案切替なし:%s / 幅切替:%s / 🔄:%s"
          % ('data-variants="1"' in h, 'name="variant"' not in h,
             'name="vw"' in h, 'id="regen-btn"' in h))
else:
    check("N 単案でも組める", True, "単案の生成物が無い環境（照合不能・素通り）")

# 案件名のエスケープ（自由入力が HTML を壊さない／注入面を作らない）
ctx = mc.build_context("x", {"meta": {"project": '<img src=x onerror=alert(1)>"'}},
                       [("a", "index-a.html")])
check("O 案件名を HTML エスケープする（自由入力で壊れない・注入面を作らない）",
      "<img" not in ctx["PROJECT"] and "&lt;img" in ctx["PROJECT"],
      "結果=%s" % ctx["PROJECT"][:50])

# 配色の検証（CSS への注入面を作らない）
ctx2 = mc.build_context("x", {"colors": {"main": "red;} body{display:none"}},
                        [("a", "index-a.html")])
check("P 配色は #rrggbb 以外を既定色へ落とす（CSS 注入面を作らない）",
      ctx2["MAIN"] == mc.DEFAULT_COLORS["main"],
      "結果=%s" % ctx2["MAIN"])

print("=" * 78)
print("KLK-103 compare.html のテンプレート化 チェック")
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
