#!/usr/bin/env python3
"""
KLK-115 acceptance-condition checker — 配布パッケージにデザインシステム（DADS）が入らないこと。

★経緯（2026-09-10）
  モック生成システムとデザインシステム（DADS）は別案件として進めることになった。
  理恵さんの指示は「モック生成のパッケージに DADS 関連を含めない」「デザインシステム側で
  生成した項目が混入しないように（共有して使用している箇所は除く）」。
  リポジトリは分割しない（同日判断）ので、**組み立て時に外す**方式をとる。

★この checker が守っているもの
  1. `--with-design-system`（既定OFF）が make-package.sh にあること
  2. マーカー `<!-- DADS:BEGIN/END -->` が対象文書すべてに付いていること（付け忘れの検知）
  3. マーカーを外した結果、DADS 語が1つも残らないこと（純粋関数で検証）
  4. マーカーが壊れたら組み立てが止まること（妨害注入・壊してから判定する）
  5. ★実効果 — 実際に既定ビルドを組んで、
     (a) DADS 一式とマニュアルが入らない
     (b) 配布物の全テキストに DADS 語が1つも無い（＝参照先の無い記述も残らない）
     (c) 同梱がリポジトリ直下の固定 allowlist に収まる
     (d) ★リポジトリ直下へ実際にフォルダを置いてから組んでも、配布物に現れない
         ＝別案件（デザインシステム）が今後何を足しても混入しない。
         allowlist の文字列を読むのではなく、**置いてから組んで確かめる**

★checker 同士の分担（重複してパッケージを組まない）
  - 既定ビルド … このファイル（混入ゼロ・allowlist）と check_klk111 D1/D3
  - `--with-design-system` ビルド … check_klk111 D2（DADS 49種＋出典）、
    check_klk112 G1/G2（マニュアルが原本と同一で出典行が残る）
  「入らない」と「付ければ入る」の両方が見られている。片側だけの空検査にはならない。

Run: python3 tests/site/check_klk115.py [--fast]   (--fast はパッケージ実ビルドを省く)
"""
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG_SH = os.path.join(ROOT, "tools", "make-package.sh")
results = []

# DADS を指す語。配布物にこれらが現れたら混入とみなす（check_klk111 と同じ語彙）
FORBIDDEN_TOKENS = ("design-system", "デジタル庁", "DADS")

# マーカーで囲って配布時に外す文書
MARKED_DOCS = (
    "CLAUDE.md",
    "README.md",
    "CHANGELOG.md",
    "agents/architect.md",
    "agents/implementer.md",
    "agents/reviewer.md",
)

# 既定ビルドのトップレベルに現れてよいもの。**これと完全一致**であることを見る。
# 新しいフォルダがリポジトリ直下に増えても、ここへ足さない限り配布物には出ない。
# 逆に make-package.sh の同梱対象を増やしたら、この検査が落ちて意図的な更新を促す。
EXPECTED_TOP = {
    ".claude", "agents", "docs", "draft-gen", "palette", "samples",
    "catalog", "mockups", "tickets",
    "CHANGELOG.md", "CLAUDE.md", "LICENSE", "README.md",
    "はじめにお読みください.txt", "使い方マニュアル.html",
    "起動.bat", "起動.command",
}

MAX_SCAN_BYTES = 4 << 20


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def load_strip():
    """tools/strip-dads-sections.py を読み込む（兄弟モジュールを import しない流儀に合わせる）。"""
    path = os.path.join(ROOT, "tools", "strip-dads-sections.py")
    spec = importlib.util.spec_from_file_location("strip_dads_sections", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def dads_hits(text):
    return [t for t in FORBIDDEN_TOKENS if t in text]


def scan_tree_for_dads(top):
    """ツリー内のテキストファイルから DADS 語を含むものを返す（相対パス）。"""
    dirty = []
    for root, _dirs, files in os.walk(top):
        for f in files:
            p = os.path.join(root, f)
            try:
                if os.path.getsize(p) > MAX_SCAN_BYTES:
                    continue
                text = io.open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            hits = dads_hits(text)
            if hits:
                dirty.append("%s ← %s" % (os.path.relpath(p, top), ",".join(hits)))
    return dirty


strip = load_strip()

# ---------------------------------------------------------------------------
# S. 仕組みが備わっているか
# ---------------------------------------------------------------------------
pkg_src = io.open(PKG_SH, encoding="utf-8").read()

check("S1 make-package.sh に --with-design-system がある（既定OFF）",
      "--with-design-system" in pkg_src
      and "WITH_DESIGN_SYSTEM=0" in pkg_src
      and "WITH_DESIGN_SYSTEM=1" in pkg_src,
      "オプション=%s 既定0=%s" % ("--with-design-system" in pkg_src,
                                  "WITH_DESIGN_SYSTEM=0" in pkg_src))

# 無条件コピーの行（for f in 起動.command …）にマニュアルが残っていないこと。
# 残っていると既定ビルドへ入ってしまう。
uncond = [l for l in pkg_src.split("\n") if l.startswith("for f in 起動.command")]
check("S2 マニュアルが無条件コピーの列挙から外れている",
      len(uncond) == 1 and "デザインシステムの使い方.html" not in uncond[0],
      "無条件行=%d 記載=%s" % (len(uncond),
                               bool(uncond) and "デザインシステムの使い方.html" in uncond[0]))

check("S3 配布物から DADS 記述を外す処理が組み立てに入っている",
      "strip-dads-sections.py" in pkg_src, "呼び出し=%s" % ("strip-dads-sections.py" in pkg_src))

missing_marker = []
残存 = []
for rel in MARKED_DOCS:
    text = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
    if strip.BEGIN not in text:
        missing_marker.append(rel)
        continue
    stripped, _n = strip.strip_dads_sections(text)
    left = [l for l in stripped.split("\n") if dads_hits(l)]
    if left:
        残存.append("%s(%d行)" % (rel, len(left)))

check("S4 対象文書すべてに DADS マーカーが付いている",
      not missing_marker, "マーカー無し=%s" % (missing_marker or "なし"))
check("S5 マーカーを外すと DADS 語が1つも残らない（囲み漏れが無い）",
      not 残存, "残存=%s" % (残存 or "なし"))

# ---------------------------------------------------------------------------
# T. 妨害注入 — 壊したことを assert してから判定する
# ---------------------------------------------------------------------------
sample = io.open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8").read()

# (1) END を1つ落とす → 例外で止まらなければならない
broken = sample.replace(strip.END, "", 1)
assert broken != sample, "妨害注入が効いていない（END が見つからなかった）"
try:
    strip.strip_dads_sections(broken)
    caught = False
except ValueError:
    caught = True
check("T1 妨害注入: END を落とすと除去処理が止まる（黙って壊れたものを吐かない）",
      caught, "例外を投げた=%s" % caught)

# (2) マーカーの外へ DADS 語を足す → S5 相当の検査が落ちなければならない
injected = sample.replace("## Git運用規約", "DADS のことをここに書く\n\n## Git運用規約", 1)
assert injected != sample, "妨害注入が効いていない（注入先が見つからなかった）"
inj_stripped, _ = strip.strip_dads_sections(injected)
inj_left = [l for l in inj_stripped.split("\n") if dads_hits(l)]
check("T2 妨害注入: マーカー外に DADS 語を足すと検知される",
      len(inj_left) == 1, "検知した行数=%d" % len(inj_left))

# ---------------------------------------------------------------------------
# P. 実効果 — 実際に既定ビルドを組んで確かめる（--fast で省略可）
# ---------------------------------------------------------------------------
if "--fast" not in sys.argv:
    tmp = tempfile.mkdtemp(prefix="klk115_pkg_")
    dest = os.path.join(tmp, "pkg")

    # ★別案件のフォルダを実際にリポジトリ直下へ置いてから組む (P5)。
    #   「allowlist にこう書いてある」ではなく「置いても出てこない」を確かめる。
    #   中身には DADS 語を入れておく。混入すれば P3 でも捕まる二重の網にする。
    probe_dir = os.path.join(ROOT, "_klk115_probe_%d" % os.getpid())
    probe_file = os.path.join(probe_dir, "別案件の成果物.md")
    try:
        os.makedirs(probe_dir, exist_ok=True)
        io.open(probe_file, "w", encoding="utf-8").write(
            "デジタル庁デザインシステム(DADS)の実践物。docs/design-system/ を参照。\n")
        assert os.path.isfile(probe_file), "妨害注入が効いていない（プローブを置けなかった）"

        r = subprocess.run(["bash", PKG_SH, dest],
                           capture_output=True, text=True, timeout=600)
        check("P1 既定ビルドが成功する", r.returncode == 0,
              "rc=%d %s" % (r.returncode, (r.stderr or r.stdout)[-160:].replace("\n", " ")))

        ds_dir = os.path.join(dest, "docs", "design-system")
        manual = os.path.join(dest, "デザインシステムの使い方.html")
        check("P2 既定ビルドに DADS 一式とマニュアルが入らない",
              not os.path.exists(ds_dir) and not os.path.exists(manual),
              "design-system=%s マニュアル=%s" % (os.path.exists(ds_dir),
                                                  os.path.exists(manual)))

        dirty = scan_tree_for_dads(dest) if os.path.isdir(dest) else ["ビルド失敗"]
        check("P3 ★配布物の全テキストに DADS 語が1つも無い（参照先の無い記述も残らない）",
              not dirty, "検出=%s" % (dirty[:5] or "なし"))

        actual_top = set(os.listdir(dest)) if os.path.isdir(dest) else set()
        extra = sorted(actual_top - EXPECTED_TOP)
        missing = sorted(EXPECTED_TOP - actual_top)
        check("P4 ★同梱が固定の allowlist と一致する（増減したら気づける）",
              not extra and not missing,
              "想定外=%s 欠落=%s" % (extra or "なし", missing or "なし"))

        probe_name = os.path.basename(probe_dir)
        check("P5 ★リポジトリ直下に置いた別案件のフォルダが配布物に現れない",
              probe_name not in actual_top and not os.path.exists(
                  os.path.join(dest, probe_name)),
              "プローブ=%s 配布物に出現=%s" % (probe_name, probe_name in actual_top))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(probe_dir, ignore_errors=True)

print("=" * 78)
print("KLK-115 パッケージからデザインシステムを外す チェック")
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
