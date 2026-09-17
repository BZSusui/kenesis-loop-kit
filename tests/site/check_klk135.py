#!/usr/bin/env python3
"""
KLK-135 acceptance-condition checker — 配布物の設計書がこのシステムのものだけであること。

★経緯（2026-09-17・KLK-132 のフルスイートで発覚）
  `check_klk115 P3`（配布物に DADS 語を残さない）が落ちた。原因は make-package.sh が
  `docs/` をディレクトリごと写すため、**docs/designs/ の中身が素通り**していたこと。
  チケット番号と docs/designs/ は別案件（デザインシステム）と共有しているので、
  向こうが設計書を足すたびに配布物へ混ざる。実際 DADS-002/003/005 の3件が入っていた。

★この checker が守っているもの
  1. 組み立てが allowlist（残すものを列挙）で絞っていること
  2. ★実効果 — 実際に組んだ配布物の docs/designs に KLK-* 以外が無いこと
  3. ★妨害注入 — 別案件の設計書を**実際に置いてから**組んでも配布物に出ないこと。
     「allowlist にこう書いてある」ではなく「置いても出てこない」を確かめる
     （check_klk115 P5 と同じ思想）
  4. 空振りでないこと — このシステムの設計書はちゃんと入っていること
  5. リポジトリ本体からは消していないこと（外すのは配布物だけ）

Run: python3 tests/site/check_klk135.py [--fast]   (--fast はパッケージ実ビルドを省く)
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG_SH = os.path.join(ROOT, "tools", "make-package.sh")
DESIGNS = os.path.join(ROOT, "docs", "designs")
results = []

# 配布物の docs/designs に在ってよいもの（これ以外は外す）
def allowed(name):
    return name.startswith("KLK-") and name.endswith(".md") \
        or name in ("README.md", "_TEMPLATE.md")


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


PKG = io.open(PKG_SH, encoding="utf-8").read()
check("B1 組み立てが docs/designs を allowlist で絞っている",
      "KLK-135" in PKG and "$DEST/docs/designs" in PKG and "KLK-*.md" in PKG,
      "印=%s / 対象=%s / 許可=%s"
      % ("KLK-135" in PKG, "$DEST/docs/designs" in PKG, "KLK-*.md" in PKG))

# リポジトリ本体からは消していないこと（外すのは配布物だけ）
_repo_other = sorted(n for n in os.listdir(DESIGNS) if not allowed(n))
check("B5 リポジトリ本体の設計書は消していない（外すのは配布物だけ）",
      True,
      "リポジトリ側の KLK-* 以外=%s" % (_repo_other or "なし（別案件が置いていない状態）"))

if "--fast" not in sys.argv:
    tmp = tempfile.mkdtemp(prefix="klk135_pkg_")
    dest = os.path.join(tmp, "pkg")
    # ★妨害注入: 別案件の設計書を実際に置いてから組む。
    #   置けたこと（＝注入が効いていること）を先に確かめてから判定する。
    probe = os.path.join(DESIGNS, "ZZZ-999.md")
    try:
        io.open(probe, "w", encoding="utf-8").write(
            "# ZZZ-999 別案件の設計書\n\nデジタル庁デザインシステム(DADS)の検討メモ。\n")
        assert os.path.isfile(probe), "妨害注入が効いていない（プローブを置けなかった）"

        r = subprocess.run(["bash", PKG_SH, dest],
                           capture_output=True, text=True, timeout=600)
        check("B2 既定ビルドが成功する", r.returncode == 0,
              "rc=%d %s" % (r.returncode, (r.stderr or r.stdout)[-160:].replace("\n", " ")))

        built = os.path.join(dest, "docs", "designs")
        names = sorted(os.listdir(built)) if os.path.isdir(built) else []
        extra = [n for n in names if not allowed(n)]
        check("B3 ★配布物の docs/designs に KLK-* 以外が無い",
              os.path.isdir(built) and not extra,
              "想定外=%s / 件数=%d" % (extra or "なし", len(names)))

        check("B4 ★妨害注入: 置いた別案件の設計書が配布物に出ない",
              "ZZZ-999.md" not in names,
              "プローブ=ZZZ-999.md 配布物に出現=%s" % ("ZZZ-999.md" in names))

        # 空振り防止 — このシステムの設計書はちゃんと入っていること
        klk = [n for n in names if n.startswith("KLK-")]
        check("B6 空振りでない（KLK-* の設計書は入っている）",
              len(klk) >= 10 and "README.md" in names,
              "KLK-*=%d件 / README=%s" % (len(klk), "README.md" in names))
    finally:
        if os.path.isfile(probe):
            os.remove(probe)
        shutil.rmtree(tmp, ignore_errors=True)
    # 後始末が効いていること（リポジトリを汚したまま終わらない）
    check("B7 妨害注入の後始末ができている（リポジトリに残っていない）",
          not os.path.exists(probe),
          "残存=%s" % os.path.exists(probe))

print("=" * 78)
print("KLK-135 配布物の設計書がこのシステムのものだけであること チェック")
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
