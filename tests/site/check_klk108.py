#!/usr/bin/env python3
"""
KLK-108 acceptance-condition checker — 社外秘が配布物へ漏れないこと（総点検で発見）。

★見つかったこと（2026-09-08 の総点検）
  `docs/designs/KLK-017.md` に**実在の顧客名が3件**書かれており、
  `docs/` は `make-package.sh` が丸ごと同梱するため、
  **カタログを同梱しないパッケージBにも顧客名が入っていた**。

  さらに `tests/site/check_klk017.py` は「実タイトルが器へ漏れていないか」を
  見る検査なのに、照合語を**直書き**していた。つまり**その検査ファイル自身が漏洩源**だった。

★この checker が守っているもの
  **「秘密を、追跡されるファイルに書かない」。**
  漏洩を見張る仕組みが自分で秘密を持つと、守るほど漏れる。
  照合語は必ず実データ（catalog/catalog.json・Git 除外）から実行時に読む。

Run: python3 tests/site/check_klk108.py
"""
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ★「区分の言葉だけでできた名前」は誰のことも指さない（KLK-131）。
#   カタログが増えると、こういう汎用的な名前が必ず出てくる。
#   実際に「クリニックサイト」という登録が増えたとき、
#   2026-07 に書かれた docs/designs/KLK-071.md の
#   「案件名が実在に見えるものがある（『内科クリニックサイト』等）」という一文と一致し、
#   漏洩として報告された。**設計書は誰の名前も書いていない**ので、これは誤検知である。
#   誤検知を放置すると「また鳴っている」と流されるようになり、
#   本物の漏洩を見逃す。だからここで除く。
#   ★ただし**判断は実データから**行う。除外語を直書きすると、
#     この検査ファイル自身が漏洩源になる（KLK-108 が正したのがまさにそれ）。
STRUCTURAL_WORDS = ("サイト", "ページ", "ホームページ", "コーポレート", "リニューアル",
                    "版", "風", "系", "用", "向け", "デザイン", "レイアウト", "lp", "web")


def generic_vocabulary(entries):
    """カタログ自身が持つ区分の言葉を集める（純粋関数）。

    業種・テイスト・配色の値を区切り文字で割ってトークンにする。
    これらは**分類のための語**であって、誰かを指す名前ではない。
    """
    vocab = set(STRUCTURAL_WORDS)
    for e in entries:
        if not isinstance(e, dict):
            continue
        vals = [e.get("industry"), e.get("taste"), e.get("columns")]
        vals += list(e.get("colors") or [])
        vals += list(e.get("bgTones") or [])
        for v in vals:
            if not isinstance(v, str):
                continue
            for tok in re.split(r"[・/／,、（）()\s]+", v):
                tok = tok.strip()
                if len(tok) >= 2:
                    vocab.add(tok.lower())
    return vocab


def is_generic_title(title, vocab):
    """区分の言葉と記号だけでできた名前か（純粋関数）。

    ★消し込みで判断する。区分の言葉を長い順に取り除き、記号と空白を落として、
      **何も残らなければ**誰のことも指していない。
      少しでも残れば（例: 「アミュール」）従来どおり照合する＝守りは緩めない。
    """
    rest = title.lower()
    for tok in sorted(vocab, key=len, reverse=True):
        rest = rest.replace(tok, "")
    rest = re.sub(r"[\s・/／,、。（）()\[\]\-–—_~〜+&＆|｜:：;；'\"’”「」『』!！?？.．]", "", rest)
    return rest == ""


def catalog_terms():
    """カタログの実データから照合語を集める。無ければ None（照合不能）。"""
    p = os.path.join(ROOT, "catalog", "catalog.json")
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return None
    entries = [e for e in data.get("entries", []) if isinstance(e, dict)]
    vocab = generic_vocabulary(entries)
    out = set()
    for e in entries:
        for key in ("title", "client", "name", "note", "memo"):
            v = e.get(key)
            if not isinstance(v, str) or len(v.strip()) < 4:
                continue
            v = v.strip()
            if key == "title" and is_generic_title(v, vocab):
                continue          # 区分の言葉だけ＝誰も指していない
            out.add(v)
    return out


def tracked_files():
    r = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, cwd=ROOT)
    return [f for f in r.stdout.split("\0") if f]


# ---------------------------------------------------------------------------
# ★本体: Git 追跡ファイルへ社外秘が出ていないか
# ---------------------------------------------------------------------------
terms = catalog_terms()
files = tracked_files()
check("A Git 追跡ファイルを列挙できる（検査が空振りしていない）",
      len(files) > 50, "%d ファイル" % len(files))

if terms is None:
    check("B ★Git 追跡ファイルに社外秘（カタログの実タイトル等）が無い",
          True, "catalog.json が無い環境（照合不能・素通り）")
else:
    leaks = []
    for f in files:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p) or f.startswith("catalog/"):
            continue
        try:
            h = io.open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for t in terms:
            if t in h:
                leaks.append("%s ← %s" % (f, t[:30]))
    check("B ★Git 追跡ファイルに社外秘（カタログの実タイトル等）が無い",
          not leaks, "照合 %d 語 / 検出=%s" % (len(terms), leaks[:4] or "なし"))

# ---------------------------------------------------------------------------
# 漏洩を見張る検査が、自分で秘密を持っていないこと
# ---------------------------------------------------------------------------
K17 = os.path.join(ROOT, "tests", "site", "check_klk017.py")
S17 = io.open(K17, encoding="utf-8").read() if os.path.isfile(K17) else ""
check("C ★機密チェッカーが照合語を直書きしていない（自分が漏洩源にならない）",
      "SECRET_TITLES = [" not in S17,
      "直書きの配列=%s" % ("SECRET_TITLES = [" in S17))
check("D 機密チェッカーが実データから実行時に読む",
      "catalog.json" in S17 and "def _catalog_titles" in S17,
      "実データ参照=%s" % ("def _catalog_titles" in S17))
check("E カタログが無い環境では素通りする（clone 直後・配布先で落ちない）",
      "照合不能" in S17, "fail-open=%s" % ("照合不能" in S17))

# ---------------------------------------------------------------------------
# 設計書に「書かない」理由が残っているか（また書かれないように）
# ---------------------------------------------------------------------------
D17 = os.path.join(ROOT, "docs", "designs", "KLK-017.md")
SD = io.open(D17, encoding="utf-8").read() if os.path.isfile(D17) else ""
check("F 設計書に「実在の案件名は書かない」と理由つきで明記されている",
      "実在の案件名は書かない" in SD and "パッケージ" in SD,
      "明記=%s" % ("実在の案件名は書かない" in SD))

# ---------------------------------------------------------------------------
# ★実際に作ったパッケージに漏れていないこと（設定ではなく成果物で見る）
# ---------------------------------------------------------------------------
if terms is None:
    check("G ★実際に作ったパッケージに社外秘が無い", True, "照合不能・素通り")
else:
    import tempfile
    with tempfile.TemporaryDirectory() as wd:
        dest = os.path.join(wd, "pkg")
        r = subprocess.run(["bash", os.path.join(ROOT, "tools", "make-package.sh"), dest],
                           capture_output=True, text=True, cwd=ROOT, timeout=180)
        if r.returncode != 0:
            check("G ★実際に作ったパッケージに社外秘が無い", False,
                  "パッケージを作れなかった: %s" % (r.stderr or r.stdout)[-160:])
        else:
            found = []
            for base, _dirs, names in os.walk(dest):
                for n in names:
                    p = os.path.join(base, n)
                    rel = os.path.relpath(p, dest)
                    if rel.startswith("catalog" + os.sep):
                        continue          # カタログ同梱版の catalog/ は対象外（そこが本体）
                    if os.path.getsize(p) > 4 << 20:
                        continue
                    try:
                        h = io.open(p, encoding="utf-8", errors="ignore").read()
                    except OSError:
                        continue
                    for t in terms:
                        if t in h:
                            found.append("%s ← %s" % (rel, t[:30]))
            check("G ★実際に作ったパッケージ（カタログ非同梱）に社外秘が無い",
                  not found, "検出=%s" % (found[:4] or "なし"))

print("=" * 78)
print("KLK-108 社外秘が配布物へ漏れないこと チェック")
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
