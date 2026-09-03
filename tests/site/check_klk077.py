#!/usr/bin/env python3
"""
KLK-077 acceptance-condition checker (static / no browser required).

カタログ同梱版（A）と、カタログなし版（B）の2種類を配れるようにした変更を検査する。

★この checker が守っているもの:
  `--with-catalog` の仕組みは KLK-069 からあったが、**README がそれに追随していなかった**。
  A を受け取った人には 56件入りで届くのに README は「カタログが空だと参考が選べないので、
  まずは何枚か登録してください」と案内していた（KLK-061 で潰した「UIと実態の食い違い」の
  README 版）。マーカーと差し替えスクリプトが揃っていることを常時見張る。

  もう一つは配布物の衛生。`.DS_Store` は **そのフォルダに以前あったファイル名を保持しうる**ので、
  削除済みの案件フォルダ名が配布物に残る余地を断つ。

★R群 = 仕掛けが揃っているか（静的）
  E群 = **実際に組み立てて**中身を確認する（B は毎回・A は catalog があるときだけ）

Run: python3 tests/site/check_klk077.py
Exit code 0 = all checks pass, 1 = at least one fail.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
README = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
SCRIPT = open(os.path.join(ROOT, "tools", "make-package.sh"), encoding="utf-8").read()
REWRITER_PATH = os.path.join(ROOT, "tools", "readme_for_catalog.py")
REWRITER = open(REWRITER_PATH, encoding="utf-8").read() if os.path.isfile(REWRITER_PATH) else ""
CATALOG_JSON = os.path.join(ROOT, "catalog", "catalog.json")

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


MARKERS = [
    "<!-- KLK-077:CATALOG-INTRO:BEGIN -->",
    "<!-- KLK-077:CATALOG-INTRO:END -->",
    "<!-- KLK-077:HANDLING-EXTRA:BEGIN -->",
    "<!-- KLK-077:HANDLING-EXTRA:END -->",
]

# ---------------------------------------------------------------------------
# R群 — 仕掛け
# ---------------------------------------------------------------------------
missing = [m for m in MARKERS if m not in README]
check(
    "R1 README.md に差し替えマーカーが4つそろっている",
    not missing,
    "欠け=%s" % (missing or "なし"),
)

check(
    "R2 リポジトリの README.md は B（カタログなし）の内容のまま",
    "カタログが空だと参考が選べない" in README
    and "実績カタログが入った状態" not in README,
    "空前提の記述=%s / 同梱前提の混入=%s"
    % ("カタログが空だと参考が選べない" in README, "実績カタログが入った状態" in README),
)

check(
    "R3 差し替えスクリプトが存在する",
    bool(REWRITER) and "def main(" in REWRITER,
    "tools/readme_for_catalog.py=%s（%d字）" % (bool(REWRITER), len(REWRITER)),
)

check(
    "R4 make-package.sh が --with-catalog のときだけ差し替えを呼ぶ",
    "readme_for_catalog.py" in SCRIPT
    and SCRIPT.index("readme_for_catalog.py") > SCRIPT.index('if [ "$WITH_CATALOG" -eq 1 ]'),
    "呼び出し=%s" % ("readme_for_catalog.py" in SCRIPT),
)

check(
    "R5 make-package.sh が .DS_Store を配布物から取り除く",
    "-name '.DS_Store' -delete" in SCRIPT,
    "削除処理=%s" % ("-name '.DS_Store' -delete" in SCRIPT),
)

check(
    "R6 A の取り扱い注意に、承認条件（社内限定・持ち出し禁止・記録・退職時削除）が全部ある",
    all(
        t in REWRITER
        for t in ["社内でのみ使用してください", "再配布はしないでください", "誰が持っているか", "退職・異動"]
    ),
    "社内限定=%s / 再配布禁止=%s / 記録=%s / 退職時=%s"
    % (
        "社内でのみ使用してください" in REWRITER,
        "再配布はしないでください" in REWRITER,
        "誰が持っているか" in REWRITER,
        "退職・異動" in REWRITER,
    ),
)

check(
    "R7 A の案内が個人名を含まない（CLAUDE.md セキュリティ規約）",
    "臼井" not in REWRITER and "理恵" not in REWRITER,
    "個人名=なし" if ("臼井" not in REWRITER and "理恵" not in REWRITER) else "個人名あり",
)

check(
    "R8 差し替えスクリプトが catalog.json の実際のキー（entries）を読む",
    'get("entries"' in REWRITER,
    "entries=%s / items(誤)=%s" % ('get("entries"' in REWRITER, 'get("items"' in REWRITER),
)

# ---------------------------------------------------------------------------
# E群 — 実際に組み立てて中身を見る
# ---------------------------------------------------------------------------
def build(*opts):
    dest = os.path.join(tempfile.mkdtemp(prefix="klk077_"), "pkg")
    proc = subprocess.run(
        ["bash", os.path.join(ROOT, "tools", "make-package.sh"), dest] + list(opts),
        capture_output=True, text=True, cwd=ROOT, timeout=600,
    )
    return dest, proc


def ds_store_count(root):
    return sum(1 for _d, _s, fs in os.walk(root) for f in fs if f == ".DS_Store")


dest_b, proc_b = build()
try:
    rb = os.path.join(dest_b, "README.md")
    body_b = open(rb, encoding="utf-8").read() if os.path.isfile(rb) else ""
    check(
        "E1 B（既定）が組み立てられ、README がリポジトリのものと一致する",
        proc_b.returncode == 0 and body_b == README,
        "exit=%s / README一致=%s" % (proc_b.returncode, body_b == README),
    )
    check(
        "E2 B にカタログが入っていない",
        not os.path.exists(os.path.join(dest_b, "catalog", "img"))
        and not os.path.exists(os.path.join(dest_b, "catalog", "catalog.json")),
        "img=%s / json=%s"
        % (
            os.path.exists(os.path.join(dest_b, "catalog", "img")),
            os.path.exists(os.path.join(dest_b, "catalog", "catalog.json")),
        ),
    )
    check(
        "E3 B に .DS_Store が1つも無い",
        ds_store_count(dest_b) == 0,
        "%d 個" % ds_store_count(dest_b),
    )
finally:
    shutil.rmtree(os.path.dirname(dest_b), ignore_errors=True)

if os.path.isfile(CATALOG_JSON):
    dest_a, proc_a = build("--with-catalog")
    try:
        ra = os.path.join(dest_a, "README.md")
        body_a = open(ra, encoding="utf-8").read() if os.path.isfile(ra) else ""
        check(
            "E4 A（--with-catalog）の README が同梱前提の案内になっている",
            proc_a.returncode == 0
            and "実績カタログが入った状態" in body_a
            and "カタログが空だと参考が選べない" not in body_a,
            "exit=%s / 同梱前提=%s / 空前提の残り=%s"
            % (
                proc_a.returncode,
                "実績カタログが入った状態" in body_a,
                "カタログが空だと参考が選べない" in body_a,
            ),
        )
        n = len(re.findall(r"現在 \*\*(\d+)件\*\*", body_a))
        check(
            "E5 A の README に実際の件数と内訳が入っている",
            n == 1 and "自社実績（`own`）" in body_a and "収集見本（`ref`）" in body_a,
            "件数表記=%d / 内訳=%s" % (n, "自社実績（`own`）" in body_a),
        )
        check(
            "E6 A の取り扱い注意が README に載っている",
            "社内でのみ使用してください" in body_a and "退職・異動" in body_a,
            "社内限定=%s / 退職時=%s"
            % ("社内でのみ使用してください" in body_a, "退職・異動" in body_a),
        )
        src_img = os.path.join(ROOT, "catalog", "img")
        dst_img = os.path.join(dest_a, "catalog", "img")
        n_src = len(os.listdir(src_img)) if os.path.isdir(src_img) else -1
        n_dst = len(os.listdir(dst_img)) if os.path.isdir(dst_img) else -2
        # catalog.json が指す画像がすべて配布物に揃っているか（部分コピーの検出）
        import json as _json
        broken = []
        if os.path.isfile(os.path.join(dest_a, "catalog", "catalog.json")):
            with open(os.path.join(dest_a, "catalog", "catalog.json"), encoding="utf-8") as fh:
                for ent in _json.load(fh).get("entries", []):
                    f = ent.get("file")
                    if f and not os.path.isfile(os.path.join(dst_img, f)):
                        broken.append(ent.get("id"))
        check(
            "E7 A にカタログが丸ごと入っている（枚数一致・参照先の欠損なし）",
            n_src == n_dst and n_src > 0 and not broken,
            "元%d枚 / 配布%d枚 / 参照欠損=%s" % (n_src, n_dst, broken or "なし"),
        )
        check(
            "E8 A に .DS_Store が1つも無い",
            ds_store_count(dest_a) == 0,
            "%d 個" % ds_store_count(dest_a),
        )
        check(
            "E9 A に .trash / .pending の中身が入っていない（消したはずの画像を配らない）",
            not os.path.exists(os.path.join(dest_a, "catalog", ".trash"))
            and not os.listdir(os.path.join(dest_a, "catalog", ".pending")),
            ".trash=%s / .pending=%s"
            % (
                os.path.exists(os.path.join(dest_a, "catalog", ".trash")),
                os.listdir(os.path.join(dest_a, "catalog", ".pending")),
            ),
        )
    finally:
        shutil.rmtree(os.path.dirname(dest_a), ignore_errors=True)
else:
    check(
        "E4-E9 A の組み立て検査",
        True,
        "catalog/catalog.json が無い環境のため skip（空カタログの環境では検査対象外）",
    )

print("=" * 78)
print("KLK-077 カタログ同梱版パッケージ（A）と README の切り替え 静的チェック")
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
