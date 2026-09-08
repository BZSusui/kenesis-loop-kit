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
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


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
    out = set()
    for e in data.get("entries", []):
        if not isinstance(e, dict):
            continue
        for key in ("title", "client", "name", "note", "memo"):
            v = e.get(key)
            if isinstance(v, str) and len(v.strip()) >= 4:
                out.add(v.strip())
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
