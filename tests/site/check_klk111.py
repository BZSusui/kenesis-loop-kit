#!/usr/bin/env python3
"""
KLK-111 acceptance-condition checker — DADS導入がモック生成システムと競合しないこと。

★経緯（2026-09-09）
  別環境でデジタル庁デザインシステム(DADS)を導入した際、ワイヤーフレーム生成規約
  （WIREFRAME_RULES.md）へDADSの規則を混入させてしまい、配色設定が競合した。
  組込みは一度中止され、「DADSの配置＋設計・実装・レビュー3工程の参照ルール」に
  限定した形で再導入した。

★この checker が守っているもの
  1. 隔離 — モック生成システム（DRAFT_RULES / WIREFRAME_RULES / draft-gen/ / palette/ /
     skills / samples）に DADS への参照が「二度と」混入しないこと。配色の正は従来どおり
     各生成規約側にある。
  2. DADSデータの整全性 — 49コンポーネント・MANIFEST・参照ガイド・出典管理が揃っていること。
  3. ポリシー転記 — CLAUDE.md「ポリシー管理の原則」どおり、実行責任者
     （architect / implementer / reviewer）の定義ファイルへ転記されていること。
  4. 実効果 — 実際にパッケージを組んで、DADS一式が出典ごと同梱され、
     かつパッケージ内の生成規約も汚染されていないこと（形でなく成果物を見る）。

Run: python3 tests/site/check_klk111.py [--fast]   (--fast はパッケージ実ビルドを省く)
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DS = os.path.join(ROOT, "docs", "design-system")
results = []

# DADS を指す語。隔離対象のファイルにこれらが現れたら混入とみなす
FORBIDDEN_TOKENS = ("design-system", "デジタル庁", "DADS")

# 隔離対象（モック生成システム側）。ここに DADS 参照があってはならない
ISOLATED_PREFIXES = (
    "draft-gen/",
    "palette/",
    ".claude/skills/",
    "samples/",
)


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def find_dads_refs(text):
    """テキスト中の DADS 参照語を返す（純粋関数・wrapper が劣化検知に使う）。"""
    return [t for t in FORBIDDEN_TOKENS if t in text]


def isolated_tracked_files(root=ROOT):
    r = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, cwd=root)
    return [f for f in r.stdout.split("\0")
            if f and any(f.startswith(p) for p in ISOLATED_PREFIXES)]


def manifest_dead_links(ds_dir):
    """MANIFEST.md のリンクのうち実在しないものを返す。"""
    mf = io.open(os.path.join(ds_dir, "MANIFEST.md"), encoding="utf-8").read()
    links = re.findall(r"\]\(([^)#]+\.md)\)", mf)
    return links, [l for l in links if not os.path.exists(os.path.join(ds_dir, l))]


def component_dirs(ds_dir):
    comp = os.path.join(ds_dir, "components")
    if not os.path.isdir(comp):
        return []
    return sorted(d for d in os.listdir(comp)
                  if os.path.isdir(os.path.join(comp, d)))


def reference_guide_slugs(ds_dir):
    rg = io.open(os.path.join(ds_dir, "_REFERENCE_GUIDE.md"), encoding="utf-8").read()
    return set(re.findall(r"components/([a-z0-9-]+)/index\.md", rg))


# ---------------------------------------------------------------------------
# A. 隔離 — モック生成システムに DADS 参照が無い
# ---------------------------------------------------------------------------
contaminated = []
for rel in isolated_tracked_files():
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p) or os.path.getsize(p) > 4 << 20:
        continue
    try:
        text = io.open(p, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    hits = find_dads_refs(text)
    if hits:
        contaminated.append("%s ← %s" % (rel, ",".join(hits)))
check("A1 生成システム側(draft-gen/palette/skills/samples)に DADS 参照が無い",
      not contaminated, "検出=%s" % (contaminated[:5] or "なし"))

for label, rel in (
    ("A2 DRAFT_RULES.md", ".claude/skills/draft-generate/templates/DRAFT_RULES.md"),
    ("A3 WIREFRAME_RULES.md", ".claude/skills/wireframe-gen/templates/WIREFRAME_RULES.md"),
):
    p = os.path.join(ROOT, rel)
    ok = os.path.isfile(p)
    hits = find_dads_refs(io.open(p, encoding="utf-8").read()) if ok else ["ファイル無し"]
    check("%s が存在し DADS 参照が無い（競合の再発防止）" % label,
          ok and not hits, "検出=%s" % (hits or "なし"))

# ---------------------------------------------------------------------------
# B. DADS データの整全性
# ---------------------------------------------------------------------------
comps = component_dirs(DS)
check("B1 コンポーネントが49種そろっている", len(comps) == 49,
      "実数=%d" % len(comps))

missing_index = [d for d in comps
                 if not os.path.isfile(os.path.join(DS, "components", d, "index.md"))]
check("B2 49種すべてに index.md がある", comps and not missing_index,
      "欠落=%s" % (missing_index or "なし"))

if os.path.isfile(os.path.join(DS, "MANIFEST.md")):
    links, dead = manifest_dead_links(DS)
    check("B3 MANIFEST.md のリンクが全件解決する", links and not dead,
          "リンク%d件 / 死に=%s" % (len(links), dead[:5] or "なし"))
else:
    check("B3 MANIFEST.md のリンクが全件解決する", False, "MANIFEST.md が無い")

if os.path.isfile(os.path.join(DS, "_REFERENCE_GUIDE.md")):
    rg = reference_guide_slugs(DS)
    check("B4 _REFERENCE_GUIDE の49種一覧が実在と一致する",
          rg == set(comps) and len(rg) == 49,
          "記載のみ=%s 実在のみ=%s" % (sorted(rg - set(comps))[:3] or "なし",
                                        sorted(set(comps) - rg)[:3] or "なし"))
else:
    check("B4 _REFERENCE_GUIDE の49種一覧が実在と一致する", False, "_REFERENCE_GUIDE.md が無い")

attr_p = os.path.join(DS, "_ATTRIBUTION.md")
if os.path.isfile(attr_p):
    attr = io.open(attr_p, encoding="utf-8").read()
    need = ("出典：デジタル庁デザインシステムウェブサイト", "バージョン", "加工の有無")
    lack = [n for n in need if n not in attr]
    check("B5 _ATTRIBUTION.md に出典・バージョン・加工の有無がある",
          not lack, "欠落=%s" % (lack or "なし"))
else:
    check("B5 _ATTRIBUTION.md に出典・バージョン・加工の有無がある", False, "ファイル無し")

# ---------------------------------------------------------------------------
# C. ポリシー転記（CLAUDE.md → 実行責任者の定義ファイル）
# ---------------------------------------------------------------------------
claude_md = io.open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8").read()
check("C1 CLAUDE.md に DADS 参照ルールと適用範囲（生成規約は対象外）がある",
      "デザインシステム参照ルール" in claude_md
      and "既存の配色規約を正として維持" in claude_md,
      "セクション=%s 対象外宣言=%s" % ("デザインシステム参照ルール" in claude_md,
                                        "既存の配色規約を正として維持" in claude_md))

for label, agent in (("C2 architect", "architect"),
                     ("C3 implementer", "implementer"),
                     ("C4 reviewer", "reviewer")):
    a = io.open(os.path.join(ROOT, "agents", "%s.md" % agent), encoding="utf-8").read()
    check("%s.md へ DADS の責務が転記されている" % label,
          "DADS" in a and "design-system" in a,
          "DADS=%s design-system=%s" % ("DADS" in a, "design-system" in a))

check("C5 CLAUDE.md ポリシー管理テーブルに DADS 行がある",
      "DADS準拠・出典表記" in claude_md, "行あり=%s" % ("DADS準拠・出典表記" in claude_md))

# ---------------------------------------------------------------------------
# D. 実効果 — 実際にパッケージを組んで確かめる（--fast で省略可）
# ---------------------------------------------------------------------------
if "--fast" not in sys.argv:
    tmp = tempfile.mkdtemp(prefix="klk111_pkg_")
    dest = os.path.join(tmp, "pkg")
    try:
        r = subprocess.run(["bash", os.path.join(ROOT, "tools", "make-package.sh"), dest],
                           capture_output=True, text=True, timeout=600)
        check("D1 パッケージ実ビルドが成功する", r.returncode == 0,
              "rc=%d %s" % (r.returncode, (r.stderr or r.stdout)[-160:].replace("\n", " ")))
        pkg_ds = os.path.join(dest, "docs", "design-system")
        pkg_comps = component_dirs(pkg_ds) if os.path.isdir(pkg_ds) else []
        check("D2 ★実際に作ったパッケージに DADS 49種と出典が同梱される",
              len(pkg_comps) == 49
              and os.path.isfile(os.path.join(pkg_ds, "_ATTRIBUTION.md"))
              and os.path.isfile(os.path.join(pkg_ds, "MANIFEST.md")),
              "同梱コンポーネント=%d 出典=%s" % (
                  len(pkg_comps),
                  os.path.isfile(os.path.join(pkg_ds, "_ATTRIBUTION.md"))))
        pkg_dirty = []
        for prefix in ("draft-gen", "palette", os.path.join(".claude", "skills")):
            top = os.path.join(dest, prefix)
            for root, dirs, files in os.walk(top):
                for f in files:
                    p = os.path.join(root, f)
                    if os.path.getsize(p) > 4 << 20:
                        continue
                    try:
                        text = io.open(p, encoding="utf-8", errors="ignore").read()
                    except OSError:
                        continue
                    if find_dads_refs(text):
                        pkg_dirty.append(os.path.relpath(p, dest))
        check("D3 ★パッケージ内の生成システム側にも DADS 参照が無い",
              not pkg_dirty, "検出=%s" % (pkg_dirty[:5] or "なし"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

print("=" * 78)
print("KLK-111 DADS導入がモック生成システムと競合しないこと チェック")
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
