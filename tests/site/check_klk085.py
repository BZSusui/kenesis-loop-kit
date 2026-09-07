#!/usr/bin/env python3
"""
KLK-085 acceptance-condition checker — 画面から要件ID・チケットIDを見えなくする。

理恵さんの指示（2026-09-04）:
  「各セクション右上にある REQ-010 / KLK-022、説明文内の（REQ-102）といった
    各種ナンバリングは、最終的に削除(不可視)としてほしい。
    ユーザーから見たら何の番号か分からないため。」

★この checker が守っているもの:
  **追跡可能性を捨てずに、利用者からは見えなくする**という両立。
  ID を消してしまうと「どの要件の実装か」が追えなくなるので、HTML コメントへ移した。
  したがって検査は「**画面に文字として出ていないこと**」と
  「**コメントとして残っていること**」の**両方**を要求する。
  片方だけだと、うっかり削除しても・うっかり表示に戻しても気づけない。

Run: python3 tests/site/check_klk085.py
Exit code 0 = all pass, 1 = at least one fail.
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ID_RE = r"(?:REQ|KLK|SCR|NFR|OQ)-\d+"

SCREENS = [
    os.path.join(ROOT, "draft-gen", "index.html"),
    os.path.join(ROOT, "draft-gen", "catalog.html"),
    os.path.join(ROOT, "palette", "index.html"),
    os.path.join(ROOT, "使い方マニュアル.html"),
]

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def visible_text(html):
    """画面に文字として出る部分だけを返す。

    コメント・script・style は除く。タグを \\x00 に置き換えるので、
    属性値（href やクラス名）も落ちる＝**見える文字だけ**が残る。
    """
    s = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    s = re.sub(r"<script\b.*?</script>", "", s, flags=re.S)
    s = re.sub(r"<style\b.*?</style>", "", s, flags=re.S)
    return [" ".join(c.split()) for c in re.sub(r"<[^>]+>", "\x00", s).split("\x00")]


# ---------------------------------------------------------------------------
# 画面に文字として出ていないこと
# ---------------------------------------------------------------------------
for path in SCREENS:
    name = os.path.basename(path)
    if not os.path.isfile(path):
        check("A 画面が存在する: %s" % name, False, path)
        continue
    html = io.open(path, encoding="utf-8").read()
    hits = []
    for chunk in visible_text(html):
        ids = re.findall(ID_RE, chunk)
        if ids:
            hits.append("%s ← 「%s」" % ("・".join(sorted(set(ids))), chunk[:56]))
    check("A %s に要件ID・チケットIDが文字として出ていない" % name,
          not hits, "検出 %d 件 %s" % (len(hits), hits[:2] or ""))

# <title> も画面（ブラウザのタブ）に出る
for path in SCREENS[:2]:
    name = os.path.basename(path)
    html = io.open(path, encoding="utf-8").read()
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    t = m.group(1).strip() if m else ""
    check("B %s の <title> が利用者に意味の分かる名前（IDを含まない）" % name,
          bool(t) and not re.search(ID_RE, t), "title=「%s」" % t)

# ---------------------------------------------------------------------------
# ★追跡可能性 — コメントとして残っていること（消してはいない）
# ---------------------------------------------------------------------------
UI = io.open(SCREENS[0], encoding="utf-8").read()
CAT = io.open(SCREENS[1], encoding="utf-8").read()

# 移設したはずの ID が、コメントとして実在するか（1つずつ名指しで確かめる）
MOVED_UI = ["SCR-001", "REQ-010", "REQ-001", "REQ-002", "REQ-005", "KLK-022",
            "REQ-101", "REQ-003", "REQ-004", "REQ-006", "REQ-008", "REQ-011",
            "REQ-102", "REQ-201"]
comments_ui = " ".join(re.findall(r"<!--(.*?)-->", UI, re.S))
missing = [i for i in MOVED_UI if i not in comments_ui]
check("C ★移した ID がコメントとして残っている（追跡可能性を捨てていない）",
      not missing, "欠落=%s" % (missing or "なし"))
check("D catalog.html の SCR-004 がコメントとして残っている",
      "SCR-004" in " ".join(re.findall(r"<!--(.*?)-->", CAT, re.S)),
      "残存=%s" % ("SCR-004" in " ".join(re.findall(r"<!--(.*?)-->", CAT, re.S))))
check("E grep で従来どおり追える（画面HTMLに ID が残っている）",
      len(set(re.findall(ID_RE, UI))) >= 20,
      "index.html の ID %d 種" % len(set(re.findall(ID_RE, UI))))

# ---------------------------------------------------------------------------
# 説明文が ID を消しても日本語として自然に読めること
# ---------------------------------------------------------------------------
# 括弧書きの ID を消した跡（空の括弧・重複した句点・宙に浮いた読点）が無いか
artifacts = []
for chunk in visible_text(UI) + visible_text(CAT):
    for pat, why in ((r"（\s*）", "空の括弧"), (r"。。", "句点の重複"),
                     (r"（\s*・", "括弧の直後に中黒"), (r"・\s*）", "中黒の直後に閉じ括弧"),
                     (r"\s・\s*。", "宙に浮いた中黒")):
        if re.search(pat, chunk):
            artifacts.append("%s: 「%s」" % (why, chunk[:50]))
check("F ID を消した跡（空の括弧・句点の重複など）が残っていない",
      not artifacts, "検出=%s" % (artifacts[:3] or "なし"))

# 空になった要素が残っていないか（レイアウトに隙間を作る）
empty = re.findall(r'<span class="(?:reqid|opt)">\s*</span>', UI)
check("G 空の <span class=\"reqid\"> が残っていない（余白の原因になる）",
      not empty, "空 span %d 個" % len(empty))

# ---------------------------------------------------------------------------
# 生成物側（§4.1.2）— 見本にも同じ規律が当たっていること
# ---------------------------------------------------------------------------
RULES = io.open(os.path.join(ROOT, ".claude", "skills", "draft-generate",
                             "templates", "DRAFT_RULES.md"), encoding="utf-8").read()
seg = RULES[RULES.find("#### 4.1.2"):RULES.find("### 4.2")]
check("H 規約 §4.1.2 が生成物への ID 混入を禁じている",
      bool(seg) and "画面に見える文字" in seg and "compare.html" in seg,
      "節=%s / compare.html への言及=%s" % (bool(seg), "compare.html" in seg))
check("I §4.1.2 が実際に混入した文字列を実例として残している（再発の目印）",
      "設定を変えて再生成（SCR-001）" in seg,
      "実例=%s" % ("設定を変えて再生成（SCR-001）" in seg))
check("J §4.1.2 が番地ラベル（MV-01 等）は対象外だと明記している",
      "番地ラベル" in seg and "別物" in seg,
      "番地の除外=%s" % ("番地ラベル" in seg))

TOOL = io.open(os.path.join(ROOT, "tools", "verify-mockup.py"), encoding="utf-8").read()
check("K verify-mockup が §4.1.2 を検査し、compare.html にも当てている",
      "check_dev_ids" in TOOL and TOOL.count("check_dev_ids") >= 3,
      "関数=%s / 呼び出し %d 箇所" % ("def check_dev_ids" in TOOL, TOOL.count("check_dev_ids")))

sample_hits = []
for p in sorted(glob.glob(os.path.join(ROOT, "samples", "*", "*.html"))):
    h = io.open(p, encoding="utf-8").read()
    for chunk in visible_text(h):
        ids = re.findall(ID_RE, chunk)
        if ids:
            sample_hits.append("%s: %s" % (os.path.basename(os.path.dirname(p)),
                                           "・".join(sorted(set(ids)))))
check("L ★見本（配布物）に ID が文字として出ていない",
      not sample_hits, "検出=%s" % (sample_hits[:3] or "なし"))

print("=" * 78)
print("KLK-085 画面から要件ID・チケットIDを見えなくする チェック")
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
