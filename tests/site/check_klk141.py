#!/usr/bin/env python3
"""
KLK-141 acceptance-condition checker — 記録や雛形・配布物に個人名を入れないこと。

★見つかったこと（KLK-140 のレビュー）
  CHANGELOG.md に依頼者の呼称が書かれていた。CHANGELOG は make-package.sh で配布物へ
  そのまま入る。洗い出すと、設計書・スキルの規約・生成器のコメント・比較ページの雛形
  （draft-gen/compare_template.html）にも同じ呼称があった。雛形は make_compare.py が
  生成物ごとに書き出すので、**今後作るラフすべてに入り続ける**状態だった。

★この checker が守っているもの
  **「個人名を、追跡されるファイルにも配布物にも書かない」。**
  照合語は Git 管理外の `.private/personal-terms.txt` から実行時に読む（KLK-108 と同じ方針。
  この検査ファイル自身は照合語を持たない）。ファイルが無い環境では「照合不能・素通り」。
  出力には**ファイルと行番号だけ**を出し、一致した語は出さない。

Run: python3 tests/site/check_klk141.py
Exit code 0 = all checks pass, 1 = at least one fail.
照合語ファイルが無いときは 0 のまま、最終行に印の行
`UNVERIFIED personal-terms-missing: <素通りした ID>` を出す（KLK-143。unittest では skipped になる）。
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _private_terms as pt  # noqa: E402

ROOT = pt.ROOT
results = []
SKIP = "照合不能・素通り（.private/personal-terms.txt が無い）"
skipped_ids = []  # 照合語ファイルが無いために素通りした検査 ID（KLK-143）


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def tracked_files():
    r = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, cwd=ROOT)
    return [f for f in r.stdout.split("\0") if f]


def build(wd, *opts):
    dest = os.path.join(wd, "pkg" + "".join(o.replace("-", "_") for o in opts))
    proc = subprocess.run(["bash", os.path.join(ROOT, "tools", "make-package.sh"), dest] + list(opts),
                          capture_output=True, text=True, cwd=ROOT, timeout=600)
    return dest, proc


loaded = pt.load_terms()
terms, allows = loaded if loaded else (None, None)

# ---------------------------------------------------------------------------
# K0 検査自身が照合語を持たない（KLK-108 の教訓: 見張る側が漏洩源にならない）
# ---------------------------------------------------------------------------
own = [os.path.join(HERE, "check_klk141.py"), os.path.join(HERE, "_private_terms.py"),
       os.path.join(ROOT, "tests", "test_palette_klk141.py")]
if terms is None:
    check("K0 検査自身・共有モジュールが照合語を含まない", True, SKIP)
    skipped_ids.append("K0")
else:
    hits = [(os.path.relpath(p, ROOT), ln) for p in own for ln in pt.scan_file(p, terms, allows)]
    check("K0 検査自身・共有モジュールが照合語を含まない", not hits, pt.summarize(hits))

# ---------------------------------------------------------------------------
# K1・K2 Git 追跡下の全テキスト
# ---------------------------------------------------------------------------
files = tracked_files()
check("K1 Git 追跡ファイルを列挙できる（検査が空振りしていない）", len(files) > 50, "%d ファイル" % len(files))
if terms is None:
    check("K2 ★Git 追跡下の全テキストファイルに個人名が無い", True, SKIP)
    skipped_ids.append("K2")
else:
    hits = []
    for f in files:
        p = os.path.join(ROOT, f)
        if os.path.isfile(p):
            hits += [(f, ln) for ln in pt.scan_file(p, terms, allows)]
    check("K2 ★Git 追跡下の全テキストファイルに個人名が無い", not hits,
          "照合 %d 語 / 検出=%s" % (len(terms), pt.summarize(hits)))

# ---------------------------------------------------------------------------
# K3〜K5 実際に組み立てた配布物（設定ではなく成果物で見る）
# ---------------------------------------------------------------------------
wd = tempfile.mkdtemp(prefix="klk141_")
try:
    dest_b, proc_b = build(wd)
    ok_b = proc_b.returncode == 0 and os.path.isdir(dest_b)
    if not ok_b:
        check("K3 ★既定ビルド（パッケージB）の配布物に個人名が無い", False,
              "組み立て失敗: %s" % (proc_b.stderr or proc_b.stdout)[-160:])
    elif terms is None:
        check("K3 ★既定ビルド（パッケージB）の配布物に個人名が無い", True, SKIP)
        skipped_ids.append("K3")
    else:
        hits = pt.scan_tree(dest_b, terms, allows)
        check("K3 ★既定ビルド（パッケージB）の配布物に個人名が無い", not hits, pt.summarize(hits))
    check("K4 ★既定ビルドに .private/（照合語の置き場）が入っていない",
          ok_b and not os.path.exists(os.path.join(dest_b, ".private")),
          "組み立て=%s / .private=%s" % (ok_b, os.path.exists(os.path.join(dest_b, ".private"))))

    if terms is None:
        check("K5 ★--with-tests --with-design-system ビルドの配布物に個人名が無い", True, SKIP)
        skipped_ids.append("K5")
    else:
        dest_t, proc_t = build(wd, "--with-tests", "--with-design-system")
        if proc_t.returncode != 0:
            check("K5 ★--with-tests --with-design-system ビルドの配布物に個人名が無い", False,
                  "組み立て失敗: %s" % (proc_t.stderr or proc_t.stdout)[-160:])
        else:
            hits = pt.scan_tree(dest_t, terms, allows)
            check("K5 ★--with-tests --with-design-system ビルドの配布物に個人名が無い",
                  not hits, pt.summarize(hits))

    # -----------------------------------------------------------------------
    # K6 パッケージA（--with-catalog）で加わるテキスト
    #   A の実ビルドは画像込みで数百MBのコピーになるため行わない。
    #   --with-catalog が足すのは catalog/img・thumb（画像＝バイナリ）と catalog.json、
    #   それに readme_for_catalog.py による README の書き換えだけ。
    #   テキストはこの2つなので、それを直接見れば A の差分を網羅できる。
    # -----------------------------------------------------------------------
    if terms is None:
        check("K6 ★パッケージAで加わる catalog.json・書き換え後 README に個人名が無い", True, SKIP)
        skipped_ids.append("K6")
    else:
        cat = os.path.join(ROOT, "catalog", "catalog.json")
        hits, notes = [], []
        if os.path.isfile(cat):
            hits += [("catalog/catalog.json", ln) for ln in pt.scan_file(cat, terms, allows)]
            rd = os.path.join(wd, "readme_a.md")
            shutil.copy(os.path.join(ROOT, "README.md"), rd)
            r = subprocess.run(["python3", os.path.join(ROOT, "tools", "readme_for_catalog.py"), rd, cat],
                               capture_output=True, text=True, cwd=ROOT, timeout=60)
            if r.returncode != 0:
                notes.append("README 書き換え失敗")
            hits += [("README.md(A)", ln) for ln in pt.scan_file(rd, terms, allows)]
        else:
            notes.append("catalog.json が無い（その部分は素通り）")
        check("K6 ★パッケージAで加わる catalog.json・書き換え後 README に個人名が無い",
              not hits and "README 書き換え失敗" not in notes,
              "%s%s" % (pt.summarize(hits), (" / " + " / ".join(notes)) if notes else ""))
finally:
    shutil.rmtree(wd, ignore_errors=True)

# ---------------------------------------------------------------------------
# K7 既存の生成物 mockups/*/compare.html（Git 管理外・雛形由来のコメント）
# ---------------------------------------------------------------------------
mock = os.path.join(ROOT, "mockups")
if terms is None:
    check("K7 mockups/ の compare.html に個人名が無い", True, SKIP)
    skipped_ids.append("K7")
elif not os.path.isdir(mock):
    check("K7 mockups/ の compare.html に個人名が無い", True, "mockups/ が無い（素通り）")
else:
    hits, n = [], 0
    for d in sorted(os.listdir(mock)):
        p = os.path.join(mock, d, "compare.html")
        if os.path.isfile(p):
            n += 1
            hits += [("mockups/%s/compare.html" % d, ln) for ln in pt.scan_file(p, terms, allows)]
    check("K7 mockups/ の compare.html に個人名が無い", not hits, "%d ファイル / 検出=%s" % (n, pt.summarize(hits)))

print("=" * 78)
print("KLK-141 記録・雛形・配布物に個人名が入らないこと チェック")
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
if skipped_ids:
    print(pt.unverified_line(skipped_ids))
sys.exit(1 if failed else 0)
